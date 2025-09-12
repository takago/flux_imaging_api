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
import time
import json
import httpx
import os
import base64
from fastapi import FastAPI, Form, File, UploadFile, Body
from fastapi.responses import JSONResponse, StreamingResponse
from PIL import Image

import torch
from diffusers import FluxPipeline, FluxKontextPipeline, FluxPriorReduxPipeline
from diffusers.quantizers import PipelineQuantizationConfig

# ファイルサーバのベースURL（環境変数から取得，存在しない場合は None）
FILE_SERVER = os.getenv("FILE_SERVER", None)

# 量子化設定
pipeline_quant_config = PipelineQuantizationConfig(
    quant_backend="bitsandbytes_4bit",
    quant_kwargs={"load_in_4bit": True, "bnb_4bit_quant_type": "nf4", "bnb_4bit_compute_dtype": torch.bfloat16},
    components_to_quantize=["transformer", "text_encoder_2"],
)

# --- デフォルト設定（seed は削除） ---
DEFAULTS = {
    "edit": {"guidance_scale": 2.5, "num_inference_steps": 8},
    "generate": {"guidance_scale": 3.5, "num_inference_steps": 8},
    "variation": {"guidance_scale": 2.5, "num_inference_steps": 8},
}

# --- モデル/LoRA情報 ---
MODEL_INFO = {
    "edit": {"base_model": "LPX55/FLUX.1_Kontext-Lightning", "loras": []},
    "generate": {
        "base_model": "black-forest-labs/FLUX.1-dev",
        "loras": [{"weight_name": "FLUX.1-Turbo-Alpha.safetensors", "adapter_weight": 1.0}],
    },
    "variation": {
        "base_model": "black-forest-labs/FLUX.1-Redux-dev",
        "loras": [{"weight_name": "FLUX.1-Turbo-Alpha.safetensors", "adapter_weight": 1.0}],
    },
}

# --- 編集用パイプライン (FluxKontext) ---
pipe_edit = FluxKontextPipeline.from_pretrained(
    MODEL_INFO["edit"]["base_model"],
    quantization_config=pipeline_quant_config,
    torch_dtype=torch.bfloat16,
)
if MODEL_INFO["edit"]["loras"]:
    adapter_names, adapter_weights = [], []
    for i, lora in enumerate(MODEL_INFO["edit"]["loras"]):
        adapter_name = f"edit_lora{i}"
        pipe_edit.load_lora_weights(
            pretrained_model_name_or_path_or_dict="loras_kontext",
            weight_name=lora["weight_name"],
            adapter_name=adapter_name
        )
        adapter_names.append(adapter_name)
        adapter_weights.append(lora["adapter_weight"])
    pipe_edit.set_adapters(adapter_names, adapter_weights)
pipe_edit.enable_model_cpu_offload()

# --- 生成用パイプライン (Flux) ---
pipe_gen = FluxPipeline.from_pretrained(
    MODEL_INFO["generate"]["base_model"],
    quantization_config=pipeline_quant_config,
    torch_dtype=torch.bfloat16,
)
if MODEL_INFO["generate"]["loras"]:
    adapter_names, adapter_weights = [], []
    for i, lora in enumerate(MODEL_INFO["generate"]["loras"]):
        adapter_name = f"gen_lora{i}"
        pipe_gen.load_lora_weights(
            pretrained_model_name_or_path_or_dict="loras",
            weight_name=lora["weight_name"],
            adapter_name=adapter_name
        )
        adapter_names.append(adapter_name)
        adapter_weights.append(lora["adapter_weight"])
    pipe_gen.set_adapters(adapter_names, adapter_weights)
pipe_gen.enable_model_cpu_offload()

# --- バリエーション用パイプライン (FluxPriorRedux) ---
pipe_var = FluxPipeline.from_pretrained(
    MODEL_INFO["generate"]["base_model"],
    quantization_config=pipeline_quant_config,
    text_encoder=None,
    text_encoder_2=None,
    torch_dtype=torch.bfloat16,
)
pipe_prior_redux = FluxPriorReduxPipeline.from_pretrained(
    MODEL_INFO["variation"]["base_model"],
    quantization_config=pipeline_quant_config,
    torch_dtype=torch.bfloat16,
)
if MODEL_INFO["variation"]["loras"]:
    adapter_names, adapter_weights = [], []
    for i, lora in enumerate(MODEL_INFO["variation"]["loras"]):
        adapter_name = f"var_lora{i}"
        pipe_var.load_lora_weights(
            pretrained_model_name_or_path_or_dict="loras",
            weight_name=lora["weight_name"],
            adapter_name=adapter_name
        )
        adapter_names.append(adapter_name)
        adapter_weights.append(lora["adapter_weight"])
    pipe_var.set_adapters(adapter_names, adapter_weights)
pipe_var.enable_model_cpu_offload()

app = FastAPI()


def detect_mode(input_image_url, prompt, init_image):
    if (input_image_url or init_image) and prompt:
        return "edit"
    elif (input_image_url or init_image) and not prompt:
        return "variation"
    elif not (input_image_url or init_image) and prompt:
        return "generate"
    else:
        return None


def get_generator(seed: int | None, i: int = 0):
    if seed is None:
        gen_seed = int(torch.seed())  # ランダム
    else:
        gen_seed = seed + i           # 再現性を保ちつつ複数枚対応
    return torch.Generator().manual_seed(gen_seed), gen_seed


# ---------- 共通処理 ----------
async def run_pipeline(input_image_url, prompt, bearer_token, seed, width, height,
                       guidance_scale, num_inference_steps, input_file: UploadFile = None, i: int = 0):

    init_image = None
    if input_file:
        data = await input_file.read()
        init_image = Image.open(io.BytesIO(data)).convert("RGB")
        input_image_url = None

    pipeline_mode = detect_mode(input_image_url, prompt, init_image)
    if pipeline_mode is None:
        return None, None, None  # エラー扱い

    # パラメータ設定
    if pipeline_mode == "variation":
        guidance_scale = guidance_scale or DEFAULTS["variation"]["guidance_scale"]
        num_inference_steps = num_inference_steps or DEFAULTS["variation"]["num_inference_steps"]
    elif pipeline_mode == "edit":
        guidance_scale = guidance_scale or DEFAULTS["edit"]["guidance_scale"]
        num_inference_steps = num_inference_steps or DEFAULTS["edit"]["num_inference_steps"]
    else:
        guidance_scale = guidance_scale or DEFAULTS["generate"]["guidance_scale"]
        num_inference_steps = num_inference_steps or DEFAULTS["generate"]["num_inference_steps"]

    generator, used_seed = get_generator(seed, i)

    if pipeline_mode == "variation":
        if init_image is None:
            async with httpx.AsyncClient(verify=False) as client:
                resp = await client.get(input_image_url)
                resp.raise_for_status()
                init_image = Image.open(io.BytesIO(resp.content)).convert("RGB")
        pipe_prior_output = pipe_prior_redux(init_image)
        result = pipe_var(generator=generator, guidance_scale=guidance_scale,
                          num_inference_steps=num_inference_steps,
                          width=width or init_image.size[0], height=height or init_image.size[1],
                          **pipe_prior_output)
    elif pipeline_mode == "edit":
        if init_image is None:
            headers = {}
            if bearer_token:
                headers["Authorization"] = f"Bearer {bearer_token}"
            async with httpx.AsyncClient(verify=False) as client:
                resp = await client.get(input_image_url, headers=headers)
                resp.raise_for_status()
                init_image = Image.open(io.BytesIO(resp.content)).convert("RGB")
                if width is None or height is None:
                    width, height = init_image.size
        result = pipe_edit(prompt=prompt, image=init_image, generator=generator,
                           guidance_scale=guidance_scale, num_inference_steps=num_inference_steps,
                           width=width or init_image.size[0], height=height or init_image.size[1])
    else:
        width = width or 1024
        height = height or 1024
        result = pipe_gen(prompt=prompt, generator=generator, guidance_scale=guidance_scale,
                          num_inference_steps=num_inference_steps, width=width, height=height)

    processed_img = result.images[0]
    out_buf = io.BytesIO()
    processed_img.save(out_buf, format="PNG")
    out_buf.seek(0)
    return processed_img, out_buf, used_seed


# ---------- オリジナルエンドポイント ----------
@app.post("/process")
async def process_image(
    input_image_url: str = Form(None),
    prompt: str = Form(""),
    bearer_token: str = Form(None),
    seed: int = Form(None),
    width: int = Form(None),
    height: int = Form(None),
    guidance_scale: float = Form(None),
    num_inference_steps: int = Form(None),
    input_file: UploadFile = File(None),
):
    img, buf, used_seed = await run_pipeline(input_image_url, prompt, bearer_token, seed, width, height,
                                             guidance_scale, num_inference_steps, input_file)
    if img is None:
        return JSONResponse({"error": "invalid input"}, status_code=400)
    if FILE_SERVER:
        upload_url = f"{FILE_SERVER}/upload"
        files = {"file": (f"{uuid.uuid4()}.png", buf, "image/png")}
        async with httpx.AsyncClient(verify=False) as client:
            up_resp = await client.post(upload_url, files=files)
            up_resp.raise_for_status()
            up_result = up_resp.json()
        return {"result_image_url": f"{FILE_SERVER}{up_result['url']}", "seed": used_seed}
    else:
        return {"result_image_base64": base64.b64encode(buf.getvalue()).decode("utf-8"), "seed": used_seed}


@app.post("/process/raw")
async def process_image_raw(
    input_image_url: str = Form(None),
    prompt: str = Form(""),
    bearer_token: str = Form(None),
    seed: int = Form(None),
    width: int = Form(None),
    height: int = Form(None),
    guidance_scale: float = Form(None),
    num_inference_steps: int = Form(None),
    input_file: UploadFile = File(None),
):
    img, buf, used_seed = await run_pipeline(input_image_url, prompt, bearer_token, seed, width, height,
                                             guidance_scale, num_inference_steps, input_file)
    if img is None:
        return JSONResponse({"error": "invalid input"}, status_code=400)
    return StreamingResponse(buf, media_type="image/png")


# ---------- OpenAI Image API 互換エンドポイント ----------
@app.post("/v1/images/generations")
async def openai_image_generate(body: dict = Body(...)):
    prompt = body.get("prompt")
    n = body.get("n", 1)
    size = body.get("size", "1024x1024")
    response_format = body.get("response_format", "url")
    seed = body.get("seed")
    
    width, height = map(int, size.split("x"))
    results = []
    for i in range(n):
        img, buf, used_seed = await run_pipeline(None, prompt, None, seed, width, height, None, None, None, i)
        if img is None:
            return JSONResponse({"error": "invalid input"}, status_code=400)
        if response_format == "b64_json":
            results.append({"b64_json": base64.b64encode(buf.getvalue()).decode("utf-8"), "seed": used_seed})
        else:
            if not FILE_SERVER:
                return JSONResponse({"error": "FILE_SERVER not configured"}, status_code=500)
            upload_url = f"{FILE_SERVER}/upload"
            files = {"file": (f"{uuid.uuid4()}.png", buf, "image/png")}
            async with httpx.AsyncClient(verify=False) as client:
                up_resp = await client.post(upload_url, files=files)
                up_resp.raise_for_status()
                up_result = up_resp.json()
            results.append({"url": f"{FILE_SERVER}{up_result['url']}", "seed": used_seed})
    return {"created": int(time.time()), "data": results}


@app.post("/v1/images/edits")
async def openai_image_edit(
    image: UploadFile = File(...),
    prompt: str = Form(...),
    n: int = Form(1),
    size: str = Form("1024x1024"),
    response_format: str = Form("url"),
    seed: int = Form(None),
):
    width, height = map(int, size.split("x"))
    raw_bytes = await image.read()
    results = []
    for i in range(n):
        img_file = UploadFile(filename=image.filename, file=io.BytesIO(raw_bytes))
        img, buf, used_seed = await run_pipeline(None, prompt, None, seed, width, height, None, None, img_file, i)
        if img is None:
            return JSONResponse({"error": "invalid input"}, status_code=400)
        if response_format == "b64_json":
            results.append({"b64_json": base64.b64encode(buf.getvalue()).decode("utf-8"), "seed": used_seed})
        else:
            if not FILE_SERVER:
                return JSONResponse({"error": "FILE_SERVER not configured"}, status_code=500)
            upload_url = f"{FILE_SERVER}/upload"
            files = {"file": (f"{uuid.uuid4()}.png", buf, "image/png")}
            async with httpx.AsyncClient(verify=False) as client:
                up_resp = await client.post(upload_url, files=files)
                up_resp.raise_for_status()
                up_result = up_resp.json()
            results.append({"url": f"{FILE_SERVER}{up_result['url']}", "seed": used_seed})
    return {"created": int(time.time()), "data": results}


@app.post("/v1/images/variations")
async def openai_image_variation(
    image: UploadFile = File(...),
    n: int = Form(1),
    size: str = Form("1024x1024"),
    response_format: str = Form("url"),
    seed: int = Form(None),
):
    width, height = map(int, size.split("x"))
    raw_bytes = await image.read()
    results = []
    for i in range(n):
        img_file = UploadFile(filename=image.filename, file=io.BytesIO(raw_bytes))
        img, buf, used_seed = await run_pipeline(None, None, None, seed, width, height, None, None, img_file, i)
        if img is None:
            return JSONResponse({"error": "invalid input"}, status_code=400)
        if response_format == "b64_json":
            results.append({"b64_json": base64.b64encode(buf.getvalue()).decode("utf-8"), "seed": used_seed})
        else:
            if not FILE_SERVER:
                return JSONResponse({"error": "FILE_SERVER not configured"}, status_code=500)
            upload_url = f"{FILE_SERVER}/upload"
            files = {"file": (f"{uuid.uuid4()}.png", buf, "image/png")}
            async with httpx.AsyncClient(verify=False) as client:
                up_resp = await client.post(upload_url, files=files)
                up_resp.raise_for_status()
                up_result = up_resp.json()
            results.append({"url": f"{FILE_SERVER}{up_result['url']}", "seed": used_seed})
    return {"created": int(time.time()), "data": results}
