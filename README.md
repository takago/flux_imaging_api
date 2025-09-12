# Flux Imaging API

Flux パイプラインを利用した①画像生成・②編集・③バリエーションの3役をこなすAPI サーバです．  
独自のオリジナル API に加えて，OpenAI Image API 互換のエンドポイントも提供しています．

（VRAMが16GBあれば動かと思います）

---

## 特徴

- **3つのモード**
  - 生成 (Flux)
  - 編集 (FluxKontext)
  - バリエーション (FluxRedux + Flux)
- **エンドポイント**
  - `/process`（JSON 応答）
  - `/process/raw`（PNG バイナリ返却）
  - `/v1/images/generations`（OpenAI 互換）
  - `/v1/images/edits`（OpenAI 互換）
  - `/v1/images/variations`（OpenAI 互換）
- **出力 JSON には**
  - `width`, `height`（生成された画像のサイズ）
  - `seed`, `guidance_scale`, `num_inference_steps`
  - 使用したモデル・LoRA 情報
  が含まれます．
- **LoRA 対応**  
  `MODEL_INFO` に設定を追加することで，LoRA を適用可能です．

  
---

## インストール
### 依存関係
- Python 3.12
- [diffusers](https://github.com/huggingface/diffusers)
- [torch](https://pytorch.org/)
- fastapi
- uvicorn
- httpx
- pillow
- bitsandbytes（4bit量子化用）

### セットアップ例

```bash
git clone https://github.com/takago/flux-imaging-api.git
cd flux-imaging-api
pip install -r requirements.txt
```

---

## 起動方法

```bash
FILE_SERVER="https://サーバ名:9999" uvicorn flux_imaging_api:app --host 0.0.0.0 --port 8765
```

ファイルサーバのベースURLは環境変数で指定可能です．  
デフォルトは `http://localhost:8010` です．

```bash
export FILE_SERVER=http://your-file-server:8010
```

---

## 使用例

### 生成
```bash
curl -X POST http://localhost:8000/process      -F "prompt=a fantasy landscape"
```

### 編集
```bash
curl -X POST http://localhost:8000/process      -F "input_image_url=https://example.com/src.png"      -F "prompt=make it stylish"
```

### バリエーション
```bash
curl -X POST http://localhost:8000/process      -F "input_image_url=https://example.com/src.png"
```

### OpenAI互換エンドポイント
```bash
curl -X POST http://localhost:8000/v1/images/generations      -H "Content-Type: application/json"      -d '{"prompt":"a fantasy landscape","size":"512x512","n":1}'
```

---

## 謝辞 (Acknowledgements)

- [Black Forest Labs](https://blackforestlabs.ai/) が開発した Flux モデルファミリー  
- [OpenAI](https://openai.com/) が提供する Image API の設計（OpenAI 互換エンドポイントの参考にしました）  
- [ChatGPT (OpenAI)](https://chat.openai.com/) による設計・実装サポート  

---

## ライセンス

MIT License
