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
