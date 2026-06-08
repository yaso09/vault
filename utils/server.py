import os
import json
import socket
import threading
from pathlib import Path

# FastAPI imports
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

# Project imports
from utils.search_engine import search_youtube, get_channel_info
import utils.downloader as downloader

# ── Download Path Configuration ────────────────────────────────────
download_path = str(Path.home() / "Vault" / "videos")
try:
    os.makedirs(download_path, exist_ok=True)
except OSError:
    import tempfile
    download_path = str(Path(tempfile.gettempdir()) / "Vault" / "videos")
    os.makedirs(download_path, exist_ok=True)

# ── FastAPI Application Setup ─────────────────────────────────────
app = FastAPI(title="Vault - Video Archive API")

# Mount Static Directory
static_dir = Path(__file__).parent.parent / "static"
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# ffmpeg.wasm public directory (project_root/public/ffmpeg.wasm)
ffmpeg_wasm_dir = Path(__file__).parent.parent / "public" / "ffmpeg.wasm"

# ── Playback Position Helpers ──────────────────────────────────────

def load_positions(dl_path: str) -> dict:
    pos_file = Path(dl_path) / ".playback_positions.json"
    if pos_file.exists():
        try:
            with open(pos_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_position(dl_path: str, filepath: str, position_ms: int):
    pos_file = Path(dl_path) / ".playback_positions.json"
    positions = load_positions(dl_path)
    positions[filepath] = position_ms
    try:
        os.makedirs(dl_path, exist_ok=True)
        with open(pos_file, "w", encoding="utf-8") as f:
            json.dump(positions, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# ── Routes ────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    index_file = static_dir / "index.html"
    if index_file.exists():
        content = index_file.read_text(encoding="utf-8")
        # App.js is always injected to ensure it loads naturally in all environments (browsers & mobile webviews)
        content = content.replace("</body>", '<script src="/static/app.js"></script>\n</body>')
        return HTMLResponse(content=content)
    return HTMLResponse(content="<h2>Vault static/index.html is missing. Please create it first.</h2>")

# ── ffmpeg.wasm Static File Serving ───────────────────────────────

_FFMPEG_WASM_MIME: dict[str, str] = {
    ".wasm": "application/wasm",
    ".js":   "application/javascript",
    ".mjs":  "application/javascript",
    ".ts":   "application/typescript",
    ".map":  "application/json",
}

@app.get("/ffmpeg.wasm/{filepath:path}")
async def serve_ffmpeg_wasm(filepath: str):
    """
    Serves files from public/ffmpeg.wasm/* with correct MIME types.
    Also sets Cross-Origin isolation headers required by SharedArrayBuffer
    (used by ffmpeg.wasm threads).
    """
    full_path = ffmpeg_wasm_dir / filepath
    # Prevent directory traversal
    try:
        full_path = full_path.resolve()
        ffmpeg_wasm_dir.resolve()
        full_path.relative_to(ffmpeg_wasm_dir.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=404, detail=f"ffmpeg.wasm asset not found: {filepath}")

    suffix = full_path.suffix.lower()
    content_type = _FFMPEG_WASM_MIME.get(suffix, "application/octet-stream")

    headers = {
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Embedder-Policy": "require-corp",
        "Cache-Control": "public, max-age=31536000, immutable",
    }

    def file_iterator():
        with open(full_path, "rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                yield chunk

    return StreamingResponse(file_iterator(), media_type=content_type, headers=headers)

# ── API Endpoints ──────────────────────────────────────────────────

@app.get("/api/search")
async def api_search(q: str, type: str = "video", date: str = "any", sort: str = "relevance"):
    try:
        results = search_youtube(query=q, type_filter=type, date_filter=date, sort_filter=sort)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/channel")
async def api_channel(url: str, sort_by: str = "latest"):
    try:
        data = get_channel_info(channel_url=url, sort_by=sort_by)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class DownloadRequest(BaseModel):
    url: str
    title: str

@app.get("/api/downloads")
async def api_downloads():
    return downloader.get_all_downloads()

@app.post("/api/download")
async def api_download(req: DownloadRequest, request: Request):
    user_agent = request.headers.get("user-agent", "").lower()
    is_mobile_client = "android" in user_agent or "iphone" in user_agent or "ipad" in user_agent

    try:
        dl_id = downloader.start_download(
            url=req.url,
            title=req.title,
            download_path=download_path,
            is_mobile=is_mobile_client
        )
        return {"status": "ok", "download_id": dl_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/library")
async def api_library():
    try:
        files = []
        if os.path.exists(download_path):
            for f in sorted(os.listdir(download_path)):
                if f.endswith((".mp4", ".mkv", ".webm")):
                    full_path = os.path.join(download_path, f)
                    stat = os.stat(full_path)
                    files.append({
                        "filename": f,
                        "filepath": full_path,
                        "size": stat.st_size
                    })
        return files
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/library/{filename}")
async def api_delete_video(filename: str):
    full_path = os.path.join(download_path, filename)
    if os.path.exists(full_path):
        try:
            os.remove(full_path)
            # Remove from positions if saved
            positions = load_positions(download_path)
            if full_path in positions:
                del positions[full_path]
                pos_file = Path(download_path) / ".playback_positions.json"
                with open(pos_file, "w", encoding="utf-8") as f:
                    json.dump(positions, f, ensure_ascii=False, indent=2)
            return {"status": "ok"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    raise HTTPException(status_code=404, detail="Video file not found")

class PlaybackPositionRequest(BaseModel):
    filepath: str
    position_ms: int

@app.post("/api/library/position")
async def api_save_position(req: PlaybackPositionRequest):
    try:
        save_position(download_path, req.filepath, req.position_ms)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/library/positions")
async def api_get_positions():
    try:
        return load_positions(download_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── Robust Range Request Video Streaming ──────────────────────────

def range_requests_response(request: Request, file_path: str, content_type: str):
    """
    Returns a partial content response (HTTP 206) supporting range seeks,
    fully compatible with mobile webviews, pywebview, and standard web browsers.
    """
    file_size = os.path.getsize(file_path)
    range_header = request.headers.get("range")

    headers = {
        "content-type": content_type,
        "accept-ranges": "bytes",
    }

    if range_header:
        try:
            h = range_header.replace("bytes=", "").strip()
            parts = h.split("-")
            start = int(parts[0]) if parts[0] else 0
            end = int(parts[1]) if parts[1] else file_size - 1
        except ValueError:
            raise HTTPException(status_code=416, detail="Invalid Range Header")

        if start >= file_size or end >= file_size or start > end:
            raise HTTPException(status_code=416, detail="Invalid Range Header")

        chunk_size = end - start + 1
        headers["content-range"] = f"bytes {start}-{end}/{file_size}"
        headers["content-length"] = str(chunk_size)

        def file_iterator():
            with open(file_path, "rb") as f:
                f.seek(start)
                remaining = chunk_size
                while remaining > 0:
                    chunk = f.read(min(remaining, 1024 * 1024))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        return StreamingResponse(file_iterator(), status_code=206, headers=headers)
    else:
        headers["content-length"] = str(file_size)

        def file_iterator():
            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(1024 * 1024)
                    if not chunk:
                        break
                    yield chunk

        return StreamingResponse(file_iterator(), status_code=200, headers=headers)

@app.get("/video/{filename}")
async def stream_video(filename: str, request: Request):
    full_path = os.path.join(download_path, filename)
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="Video file not found")

    content_type = "video/mp4"
    if filename.endswith(".webm"):
        content_type = "video/webm"
    elif filename.endswith(".mkv"):
        content_type = "video/x-matroska"

    return range_requests_response(request, full_path, content_type)

# ── Server Helpers ─────────────────────────────────────────────────

def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def start_server_in_thread(host: str = "127.0.0.1", port: int = 8000):
    import uvicorn
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run)
    thread.daemon = True
    thread.start()
    return server