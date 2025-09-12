# ============================================================
#  flux_imaging_api.py
#
#  Imaging API Server with Flux Pipelines
#    - Generate, Edit, and Variation (Flux, FluxKontext, FluxRedux)
#    - Original API + OpenAI Image API compatible endpoints
#
#  Author: Daisuke Takago (Kanazawa Institute of Technology)
#  Supported by ChatGPT (OpenAI)
#
#  Acknowledgements:
#    - Black Forest Labs for developing the Flux model family
#    - OpenAI for providing the Image API design, which inspired
#      the OpenAI-compatible endpoints implemented here
#
#  Development date: September 2025
#  License: MIT
# ============================================================

import io
import uuid
import json
import base64
import httpx
import os
from fastapi import FastAPI, Form, UploadFile, File
from fastapi.responses import JSONResponse, StreamingResponse
from PIL import Image

import torch
from diffusers import FluxPipeline, FluxKontextPipeline, FluxPriorReduxPipeline
from diffusers.quantizers import PipelineQuantizationConfig

# ファイルサーバのベースURL（環境変数から取得）
FILE_SERVER = os.getenv("FILE_SERVER", None)

# 量子化設定
pipeline_quant_config = PipelineQuantizationConfig(
    quant_backend="bitsandbytes_4bit",
    quant_kwargs={"load_in_4bit": True, "bnb_4bit_quant_type": "nf4", "bnb_4bit_compute_dtype": torch.bfloat16},
    components_to_quantize=["transformer", "text_encoder_2"],
)

# --- デフォルト設定 ---
DEFAULTS = {
    "edit": {
        "seed": 21,
        "guidance_scale": 2.5,
        "num_inference_steps": 8,
    },
    "generate": {
        "seed": 123456789,
        "guidance_scale": 3.5,
        "num_inference_steps": 8,
    },
    "variation": {
        "seed": 777,
        "guidance_scale": 2.5,
        "num_inference_steps": 8,
    }
}

# --- モデル/LoRA情報 ---
MODEL_INFO = {
    "edit": {
        "base_model": "LPX55/FLUX.1_Kontext-Lightning",
        "loras": []
    },
    "generate": {
        "base_model": "black-forest-labs/FLUX.1-dev",
        "loras": [
             {"weight_name": "FLUX.1-Turbo-Alpha.safetensors", "adapter_weight": 1.0}
        ]
    },
    "variation": {
        "base_model": "black-forest-labs/FLUX.1-Redux-dev",
        "loras": []
    }
}

# --- 編集用パイプライン (FluxKontext) ---
pipe_edit = FluxKontextPipeline.from_pretrained(
    MODEL_INFO["edit"]["base_model"],
    quantization_config=pipeline_quant_config,
    torch_dtype=torch.bfloat16,
)
pipe_edit.enable_model_cpu_offload()

# --- 生成用パイプライン (Flux) ---
pipe_gen = FluxPipeline.from_pretrained(
    MODEL_INFO["generate"]["base_model"],
    quantization_config=pipeline_quant_config,
    torch_dtype=torch.bfloat16,
)
pipe_gen.enable_model_cpu_offload()

# --- バリエーション用パイプライン (FluxPriorRedux) ---
pipe_prior_redux = FluxPriorReduxPipeline.from_pretrained(
    MODEL_INFO["variation"]["base_model"],
    quantization_config=pipeline_quant_config,
    torch_dtype=torch.bfloat16,
)
pipe_prior_redux.enable_model_cpu_offload()

app = FastAPI()


def detect_mode(has_image: bool, has_prompt: bool):
    if has_image and has_prompt:
        return "edit"
    elif has_image and not has_prompt:
        return "variation"
    elif not has_image and has_prompt:
        return "generate"
    else:
        return None


# ---------- 共通処理 ----------
async def run_pipeline(file, input_image_url, prompt, bearer_token, seed, width, height,
                       guidance_scale, num_inference_steps, mode="json"):

    has_image = bool(file or input_image_url)
    has_prompt = bool(prompt)
    pipeline_mode = detect_mode(has_image, has_prompt)
    if pipeline_mode is None:
        return JSONResponse({"error": "Both image and prompt are missing"}, status_code=400)

    if seed is None:
        seed = DEFAULTS[pipeline_mode]["seed"]
    if guidance_scale is None:
        guidance_scale = DEFAULTS[pipeline_mode]["guidance_scale"]
    if num_inference_steps is None:
        num_inference_steps = DEFAULTS[pipeline_mode]["num_inference_steps"]

    generator = torch.Generator().manual_seed(seed)

    # 入力画像をロード
    init_image = None
    if file:
        init_image = Image.open(io.BytesIO(await file.read())).convert("RGB")
    elif input_image_url:
        headers = {}
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"
        async with httpx.AsyncClient(verify=False) as client:
            resp = await client.get(input_image_url, headers=headers)
            resp.raise_for_status()
            init_image = Image.open(io.BytesIO(resp.content)).convert("RGB")

    # モード別処理
    if pipeline_mode == "variation":
        pipe_prior_output = pipe_prior_redux(init_image)
        result = pipe_gen(
            generator=generator,
            guidance_scale=guidance_scale,
            num_inference_steps=num_inference_steps,
            width=width or init_image.size[0],
            height=height or init_image.size[1],
            **pipe_prior_output
        )
    elif pipeline_mode == "edit":
        img_width, img_height = init_image.size
        if width is None:
            width = img_width
        if height is None:
            height = img_height
        result = pipe_edit(
            prompt=prompt,
            image=init_image,
            generator=generator,
            guidance_scale=guidance_scale,
            num_inference_steps=num_inference_steps,
            width=width,
            height=height,
        )
    else:  # generate
        if width is None:
            width = 1024
        if height is None:
            height = 1024
        result = pipe_gen(
            prompt=prompt,
            generator=generator,
            guidance_scale=guidance_scale,
            num_inference_steps=num_inference_steps,
            width=width,
            height=height,
        )

    processed_img = result.images[0]
    out_width, out_height = processed_img.size

    # 出力処理
    if mode == "json":
        out_buf = io.BytesIO()
        processed_img.save(out_buf, format="PNG")
        out_buf.seek(0)

        if FILE_SERVER:
            # ファイルサーバにアップロード
            upload_url = f"{FILE_SERVER}/upload"
            files = {"file": (f"{uuid.uuid4()}.png", out_buf, "image/png")}
            async with httpx.AsyncClient(verify=False) as client:
                up_resp = await client.post(upload_url, files=files)
                up_resp.raise_for_status()
                result = up_resp.json()
            result_image_url = f"{FILE_SERVER}{result['url']}"
            result_image_b64 = None
        else:
            # base64埋め込み
            result_image_url = None
            result_image_b64 = base64.b64encode(out_buf.getvalue()).decode("utf-8")

        return JSONResponse({
            "input_image_url": input_image_url,
            "prompt": prompt,
            "seed": seed,
            "width": out_width,
            "height": out_height,
            "guidance_scale": guidance_scale,
            "num_inference_steps": num_inference_steps,
            "result_image_url": result_image_url,
            "result_image_b64": result_image_b64,
            "model_info": {
                "mode": pipeline_mode,
                "base_model": MODEL_INFO[pipeline_mode]["base_model"],
                "loras": MODEL_INFO[pipeline_mode]["loras"]
            }
        })
    elif mode == "raw":
        buf = io.BytesIO()
        processed_img.save(buf, format="PNG")
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")


# ---------- エンドポイント ----------
@app.post("/process")
async def process_image(
    file: UploadFile = File(None),
    input_image_url: str = Form(None),
    prompt: str = Form(""),
    bearer_token: str = Form(None),
    seed: int = Form(None),
    width: int = Form(None),
    height: int = Form(None),
    guidance_scale: float = Form(None),
    num_inference_steps: int = Form(None),
):
    return await run_pipeline(
        file, input_image_url, prompt, bearer_token, seed, width, height,
        guidance_scale, num_inference_steps, mode="json"
    )


@app.post("/process/raw")
async def process_image_raw(
    file: UploadFile = File(None),
    input_image_url: str = Form(None),
    prompt: str = Form(""),
    bearer_token: str = Form(None),
    seed: int = Form(None),
    width: int = Form(None),
    height: int = Form(None),
    guidance_scale: float = Form(None),
    num_inference_steps: int = Form(None),
):
    return await run_pipeline(
        file, input_image_url, prompt, bearer_token, seed, width, height,
        guidance_scale, num_inference_steps, mode="raw"
    )
