# Flux Imaging API

Flux パイプラインを利用した画像生成・編集・バリエーション API サーバです．  
独自のオリジナル API に加えて，OpenAI Image API 互換のエンドポイントも提供しています．

---

## 特徴

- **3つのモード**  
  - 生成 (Flux)  
  - 編集 (FluxKontext)  
  - バリエーション (FluxRedux + Flux)  

- **2種類の入力**  
  - リモート画像URLを指定して処理  
  - ローカルファイルを直接アップロード  

- **2種類の出力**  
  - 環境変数 `FILE_SERVER` が設定されていれば，処理結果をファイルサーバにアップロードして `result_image_url` を返す  
  - 未設定の場合は，処理結果を base64 エンコード画像として JSON に埋め込んで返す  

- **直接PNG出力**  
  `/process/raw` を使うと，処理結果をそのまま PNG として取得可能  

- **OpenAI Image API 互換エンドポイント**  
  `/v1/images/generations`, `/v1/images/edits`, `/v1/images/variations` を提供

---

## インストール

### 依存関係
- Python 3.10+
- [diffusers](https://github.com/huggingface/diffusers)
- [torch](https://pytorch.org/)
- fastapi
- uvicorn
- httpx
- pillow
- bitsandbytes（4bit量子化用）

### セットアップ例

```bash
git clone https://github.com/<USERNAME>/flux-imaging-api.git
cd flux-imaging-api

pip install -r requirements.txt
```

---

## 起動方法

```bash
uvicorn flux_imaging_api:app --host 0.0.0.0 --port 8000
```

ファイルサーバのベースURLは環境変数で指定可能です．  
デフォルトでは外部アップロードは行わず，base64 で返却されます．

```bash
export FILE_SERVER=http://your-file-server:8010
```

---

## 使用例

### 1. 生成（プロンプトのみ）
```bash
curl -X POST http://localhost:8000/process      -F "prompt=a fantasy landscape"
```

### 2. 編集（画像＋プロンプト，ローカルファイル指定）
```bash
curl -X POST http://localhost:8000/process      -F "file=@./input.png"      -F "prompt=make it stylish"
```

### 3. 編集（画像＋プロンプト，リモートURL指定）
```bash
curl -X POST http://localhost:8000/process      -F "input_image_url=https://example.com/src.png"      -F "prompt=make it stylish"
```

### 4. バリエーション（画像のみ）
```bash
curl -X POST http://localhost:8000/process      -F "file=@./input.png"
```

### 5. 生PNGを直接取得
```bash
curl -X POST http://localhost:8000/process/raw      -F "prompt=a fantasy landscape"      -o result.png
```

### 6. OpenAI互換エンドポイント
```bash
curl -X POST http://localhost:8000/v1/images/generations      -H "Content-Type: application/json"      -d '{"prompt":"a fantasy landscape","size":"512x512","n":1}'
```

---

## 出力仕様

- `/process` の場合  
  JSON 応答に以下を含む：
  - `input_image_url`  
  - `prompt`  
  - `seed`, `guidance_scale`, `num_inference_steps`  
  - `width`, `height`  
  - `result_image_url`（FILE_SERVERありの場合）  
  - `result_image_b64`（FILE_SERVER未設定の場合）  
  - `model_info`（使用モデル・LoRA情報）  

- `/process/raw` の場合  
  - 処理結果の PNG バイナリを返却  

---

## 謝辞 (Acknowledgements)

- [Black Forest Labs](https://blackforestlabs.ai/) が開発した Flux モデルファミリー  
- [OpenAI](https://openai.com/) が提供する Image API の設計（OpenAI 互換エンドポイントの参考にしました）  
- [ChatGPT (OpenAI)](https://chat.openai.com/) による設計・実装サポート  

---

## ライセンス

MIT License
