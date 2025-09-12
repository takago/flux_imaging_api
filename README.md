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
| エンドポイント | 機能 | 出力 |
|----------------|------|------|
| `POST /process` | 生成／編集／バリエーション（自動判定） | JSON（URL or Base64） |
| `POST /process/raw` | 同上 | PNGバイナリ |

### OpenAI互換API
| エンドポイント | 機能 | 対応パラメータ |
|----------------|------|----------------|
| `POST /v1/images/generations` | プロンプトから画像生成 | `prompt`, `n`, `size`, `response_format` |
| `POST /v1/images/edits` | 入力画像を編集 | `image`, `prompt`, `size`, `response_format` |
| `POST /v1/images/variations` | 入力画像のバリエーション生成 | `image`, `n`, `size`, `response_format` |

---

## 使い方

### curl での利用例

#### 1. プロンプトから画像生成 (OpenAI-Image-API)
```bash
curl -k -X POST http://localhost:8000/v1/images/generations \
  -F "prompt=A cute cat illustration" \
  -F "response_format=url" \
  | jq 

curl -k -X POST http://localhost:8000/v1/images/generations \
  -F "prompt=A cute cat illustration" \
  -F "response_format=b64_json" \
  | jq -r '.data[0].b64_json' | base64 -d > test.png
```

#### 2. 入力画像の編集 (OpenAI-Image-API)
```bash
curl -k -X POST http://localhost:8000/v1/images/edits \
  -F "image=@./test.png" \
  -F "prompt=make it monochrome" \
  -F "response_format=url" \
  | jq 

curl -k -X POST http://localhost:8000/v1/images/edits \
  -F "image=@./test.png" \
  -F "prompt=make it monochrome" \
  | jq -r '.data[0].b64_json' | base64 -d > edit_test.png
```

#### 3. バリエーション生成 (OpenAI-Image-API)
```bash
curl -k -X POST http://localhost:8000/v1/images/variations \
  -F "image=@./test.png" \
  -F "n=2" \
  -F "response_format=url" \
  | jq
```

---

### OpenAI SDK からの利用例

#### Python
```python
from openai import OpenAI
client = OpenAI(base_url="http://localhost:8000/v1", api_key="dummy-key")

# 生成
res = client.images.generate(
    prompt="A cute cat illustration",
    size="512x512",
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
