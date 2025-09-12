# Flux Imaging API

**Flux Imaging API** は，Black Forest Labs の Flux モデルファミリーを用いた画像生成・編集・バリエーション API サーバです．  
オリジナルのエンドポイントに加え，**OpenAI Image API 互換エンドポイント**（`/v1/images/...`）も提供しています．  

- 画像生成（generate）  
- 画像編集（edit）  
- 画像バリエーション（variation）  
- LoRA 適用対応  
- OpenAI 互換レスポンス（`url` / `b64_json`）  

---

## 特徴

- **3種類のモードを自動判定**  
  - 入力画像＋プロンプト → **edit**  
  - 入力画像のみ → **variation**  
  - プロンプトのみ → **generate**  
- **LoRA対応**  
  - `MODEL_INFO` に定義された LoRA を自動ロード  
- **VRAM節約**  
  - `bitsandbytes` 4bit量子化  
  - `enable_model_cpu_offload()` によりCPUオフロード  
- **柔軟な出力形式**  
  - `FILE_SERVER` があればURL返却  
  - 未設定なら Base64 返却  

---

## エンドポイント一覧

### オリジナルAPI
| エンドポイント | 機能 | 主なパラメータ | 出力 |
|----------------|------|----------------|------|
| `POST /process` | 生成／編集／バリエーション（自動判定） | `input_image_url`, `input_file`, `prompt`, `seed`, `width`, `height`, `guidance_scale`, `num_inference_steps`, `bearer_token` | JSON（URL or Base64） |
| `POST /process/raw` | 同上 | `input_image_url`, `input_file`, `prompt`, `seed`, `width`, `height`, `guidance_scale`, `num_inference_steps`, `bearer_token` | PNGバイナリ |


### OpenAI互換API
| エンドポイント | 機能 | 対応パラメータ |
|----------------|------|----------------|
| `POST /v1/images/generations` | プロンプトから画像生成 | `prompt`, `n`, `size`, `response_format`, `seed` |
| `POST /v1/images/edits` | 入力画像を編集 | `image`, `prompt`, `n`, `size`, `response_format`, `seed` |
| `POST /v1/images/variations` | 入力画像のバリエーション生成 | `image`, `n`, `size`, `response_format`, `seed` |

---

## 使い方

### オリジナルエンドポイントの使い方例

#### 1. JSON レスポンスを取得
```bash
curl -X POST http://localhost:8000/process \
  -F "prompt=A beautiful sunrise over mountains" \
  -F "input_file=@./input.png"
```
この例では入力画像とプロンプトを与えているので **編集モード** になります．  
返り値は `FILE_SERVER` 設定の有無により，URL か Base64 付きの JSON になります．

#### 2. PNG バイナリを直接取得
```bash
curl -X POST http://localhost:8000/process/raw \
  -F "prompt=A beautiful sunrise over mountains" \
  -F "input_file=@./input.png" \
  -o result.png
```
この例では `/process/raw` を使うので PNG バイナリが直接返却されます． `-o result.png` でローカルに保存可能です．

---

### OpenAI 互換エンドポイントの使い方例

#### 1. プロンプトから画像生成
```bash
curl -X POST http://localhost:8000/v1/images/generations \
  -F "prompt=A cute cat illustration" \
  -F "n=2" \
  -F "response_format=url"
```

#### 2. 入力画像の編集
```bash
curl -X POST http://localhost:8000/v1/images/edits \
  -F "image=@./test.png" \
  -F "prompt=make it monochrome" \
  -F "response_format=b64_json"
```

#### 3. バリエーション生成
```bash
curl -X POST http://locahost:8000/v1/images/variations \
  -F "image=@./test.png" \
  -F "n=2" \
  -F "response_format=url"
```

---

### OpenAI SDK からの利用例

#### Python
```python
from openai import OpenAI
client = OpenAI(base_url="http://locahost:8000/v1", api_key="dummy-key")

# 生成
res = client.images.generate(
    prompt="A cute cat illustration",
    size="512x512",
    n=2,
    response_format="url"
)
print(res.data[0].url)

# 編集
with open("test.png", "rb") as f:
    res = client.images.edits(
        model="flux",  # ダミー
        image=f,
        prompt="make it monochrome",
        response_format="b64_json"
    )
    print(res.data[0].b64_json)
```

---

## 環境変数

- `FILE_SERVER`  
  ファイル保存用サーバのURL．設定されている場合はURL返却，未設定の場合はBase64返却になります．  

---

## ライセンス

MIT License  

---

## 謝辞

- **Black Forest Labs**: Flux モデルファミリーの開発  
- **OpenAI**: Image API の設計に着想を得ています  
