# Flux Imaging API

Flux パイプラインを利用した①画像生成・②編集・③バリエーションの3役をこなすAPI サーバです．  
独自のオリジナル API に加えて，OpenAI Image API 互換のエンドポイントも提供しています．

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
