import os, uuid, pathlib, datetime
from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Depends
from fastapi.responses import FileResponse
from starlette.middleware.cors import CORSMiddleware
from typing import Optional
 
TMP_DIR = "/tmp/imgtmp"
os.makedirs(TMP_DIR, exist_ok=True)
 
BEARER_TOKEN = os.environ.get("BEARER_TOKEN", "changeme-token")
 
app = FastAPI(title="Image File Server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)
 
@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    data = await file.read()
    if not data:
        raise HTTPException(400, "empty file upload")
 
    ext = pathlib.Path(file.filename).suffix.lower() or ".bin"
    if ext not in [".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".mp4", "webm"]:
        ext = ".bin"
    fid = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(TMP_DIR, fid)
 
    with open(path, "wb") as f:
        f.write(data)
    os.utime(path, None)
    return {"url": f"/i/{fid}"}
 
@app.get("/i/{fid}")
def get_file(fid: str):
    path = os.path.join(TMP_DIR, fid)
    if not os.path.isfile(path):
        raise HTTPException(404, "not found")
    os.utime(path, None)
    return FileResponse(path)
 
def require_bearer_token(request: Request):
    auth: Optional[str] = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = auth.split(" ", 1)[1]
    if token != BEARER_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")
 
@app.get("/latest")
def latest(request: Request, _: None = Depends(require_bearer_token)):
    files = [os.path.join(TMP_DIR, f) for f in os.listdir(TMP_DIR)]
    files = [f for f in files if os.path.isfile(f)]
    if not files:
        raise HTTPException(404, "no files")
 
    latest_file = max(files, key=os.path.getmtime)
    fid = os.path.basename(latest_file)
 
    # 日本時間（UTC+9）での更新日時
    jst = datetime.timezone(datetime.timedelta(hours=9))
    mtime = datetime.datetime.fromtimestamp(
        os.path.getmtime(latest_file), tz=jst
    )
 
    # caddyを通すと"http://"で返すので，"https://"に書き換える
    return {
        "url": str(request.base_url).replace("http://", "https://") + f"i/{fid}",
        "updated_at": mtime.isoformat()  # JSTのISO8601形式
    }
 
@app.get("/latest/raw")
def latest_raw(_: None = Depends(require_bearer_token)):
    files = [os.path.join(TMP_DIR, f) for f in os.listdir(TMP_DIR)]
    files = [f for f in files if os.path.isfile(f)]
    if not files:
        raise HTTPException(404, "no files")
 
    latest_file = max(files, key=os.path.getmtime)
    return FileResponse(latest_file)
 
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010)

