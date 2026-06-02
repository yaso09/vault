import os
import argparse
import sys
import threading
import time
from pathlib import Path
import socket
import json

# FastAPI imports
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

# Project imports
from search_engine import search_youtube, get_channel_info
import downloader

# Defensive GUI imports - ensures headless/server-only runs don't crash on import
try:
    import webview
except ImportError:
    webview = None

# ── Playback Position Helpers (Decoupled from player.py/Flet) ──────

def load_positions(download_path: str) -> dict:
    pos_file = Path(download_path) / ".playback_positions.json"
    if pos_file.exists():
        try:
            with open(pos_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_position(download_path: str, filepath: str, position_ms: int):
    pos_file = Path(download_path) / ".playback_positions.json"
    positions = load_positions(download_path)
    positions[filepath] = position_ms
    try:
        os.makedirs(download_path, exist_ok=True)
        with open(pos_file, "w", encoding="utf-8") as f:
            json.dump(positions, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

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
static_dir = Path(__file__).parent / "static"
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    index_file = static_dir / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h2>Vault static/index.html is missing. Please create it first.</h2>")

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

# ── Server Helper ──────────────────────────────────────────────────

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

# ── Platform Detection ─────────────────────────────────────────────

def detect_mode() -> str:
    is_android = (
        "ANDROID_ROOT" in os.environ or 
        "TERMUX_VERSION" in os.environ or 
        os.path.exists("/system/build.prop") or 
        os.path.exists("/data/data/com.termux")
    )
    if is_android:
        return "mobile"
    return "desktop"

# ── Main Entry ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Vault - Video Archive App (FastAPI + HTML)")
    parser.add_argument("--web", action="store_true", help="Launch live on localhost")
    parser.add_argument("--desktop", action="store_true", help="Launch live and open as pywebview window")
    parser.add_argument("--mobile", action="store_true", help="Launch live and open as Flet WebView mobile version")
    
    args = parser.parse_args()
    
    # Determine which mode to run
    mode = None
    if args.web:
        mode = "web"
    elif args.desktop:
        mode = "desktop"
    elif args.mobile:
        mode = "mobile"
    else:
        # Default: auto-detect by OS
        mode = detect_mode()
        print(f"Platform algılandı. Varsayılan başlatma modu: --{mode}")

    # Set up host and port
    host = "127.0.0.1"
    port = 8000
    
    # Solve port conflicts if 8000 is occupied
    while is_port_in_use(port):
        port += 1
        
    url = f"http://{host}:{port}"
    
    print(f"Vault backend server başlatılıyor: {url}")
    start_server_in_thread(host, port)
    
    # Wait for the FastAPI server to initialize fully
    time.sleep(0.8)

    if mode == "web":
        print(f"Uygulama yayında! Lütfen tarayıcınızda açın: {url}")
        # Keep main thread alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nVault durduruldu.")
            
    elif mode == "desktop":
        if webview is None:
            print("Hata: 'pywebview' masaüstü paketi yüklü değil. --web modu olarak çalıştırılıyor.")
            print(f"Uygulama yayında! Lütfen tarayıcınızda açın: {url}")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
            return
            
        print("Desktop Penceresi (pywebview) açılıyor...")
        try:
            webview.create_window("Vault - Video Arşivi", url, width=440, height=840, resizable=False)
            webview.start()
        except Exception as e:
            print(f"Grafiksel masaüstü penceresi başlatılamadı: {e}")
            print(f"Düşüş modu: Sunucu yayında kalmaya devam ediyor: {url}")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
                
    elif mode == "mobile":
        # Dynamic import of Flet elements to ensure headless environments don't crash
        try:
            import flet as ft
            try:
                import flet_webview as fwv
                HAS_FLET_WEBVIEW = True
            except ImportError:
                fwv = None
                HAS_FLET_WEBVIEW = False
        except ImportError:
            print("Hata: 'flet' mobil paketi yüklü değil. --web modu olarak çalıştırılıyor.")
            print(f"Uygulama yayında! Lütfen tarayıcınızda açın: {url}")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
            return

        print("Flet WebView (Mobil Görünüm) açılıyor...")
        
        def run_flet_app(page: ft.Page):
            page.title = "Vault Mobile"
            page.padding = 0
            page.spacing = 0
            page.window.width = 440
            page.window.height = 840
            page.window.resizable = True
            
            if HAS_FLET_WEBVIEW:
                wv = fwv.WebView(url=url, expand=True)
                page.add(wv)
            else:
                page.add(
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Icon(ft.Icons.WARNING_ROUNDED, color="amber", size=48),
                                ft.Text("flet-webview bu platformda desteklenmiyor/yüklü değil.", size=16, weight="bold"),
                                ft.Text(f"Lütfen tarayıcınızdan şu adrese gidin: {url}", size=14)
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=10
                        ),
                        alignment=ft.Alignment.CENTER,
                        expand=True
                    )
                )
                
        try:
            ft.app(target=run_flet_app)
        except Exception as e:
            print(f"Flet mobil arayüzü başlatılamadı: {e}")
            print(f"Düşüş modu: Sunucu yayında kalmaya devam ediyor: {url}")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass

if __name__ == "__main__":
    main()
