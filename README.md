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
| `POST /process/raw` | 同上 | 同上 | PNGバイナリ |


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
---

## 画像ファイルサーバ（image_file_server.py）

生成画像を保存・配布するための簡易ファイルサーバです．  
Flux Imaging API 側で `FILE_SERVER` 環境変数を設定することで，自動的にここに画像が保存され，URL が返却されます．  

### 機能

- `POST /upload`  
  画像ファイルをアップロードし，一意なID付きで保存．戻り値として `/i/{fid}` 形式の URL を返す．  
- `GET /i/{fid}`  
  保存された画像を返却する．  
- `GET /latest` （Bearer Token 認証必要）  
  最新のファイルの URL と JST での更新日時を返す．  
- `GET /latest/raw` （Bearer Token 認証必要）  
  最新のファイルを PNG 等のバイナリ形式で直接返す．  

### 認証

- 環境変数 `BEARER_TOKEN` に設定した値で認証（デフォルト: `"changeme-token"`）  
- `/latest` および `/latest/raw` のみ認証が必要．  

### 起動方法

```bash
python image_file_server.py
```

デフォルトではポート `8010` で起動します．

### 利用例

#### アップロード
```bash
curl -X POST http://localhost:8010/upload \
  -F "file=@./sample.png"
```

レスポンス例:
```json
{"url": "/i/2f4a9b3c2d7845f39f8a.png"}
```

#### 画像取得
```bash
curl -O http://localhost:8010/i/2f4a9b3c2d7845f39f8a.png
```

#### 最新の画像情報（認証あり）
```bash
curl -H "Authorization: Bearer changeme-token" http://localhost:8010/latest
```

レスポンス例:
```json
{
  "url": "https://yourserver/i/2f4a9b3c2d7845f39f8a.png",
  "updated_at": "2025-09-12T12:34:56+09:00"
}
```

#### 最新の画像を直接取得
```bash
curl -H "Authorization: Bearer changeme-token" \
     http://localhost:8010/latest/raw -o latest.png
```
## ライセンス

MIT License  

---

## 謝辞

- **Black Forest Labs**: Flux モデルファミリーの開発  
- **OpenAI**: Image API の設計に着想を得ています  
