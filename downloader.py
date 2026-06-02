import yt_dlp
import os
import time
import threading
import uuid

# Thread-safe global dictionary to track active and recently finished/failed downloads
active_downloads = {}
active_downloads_lock = threading.Lock()

# Auto-cleanup time in seconds for finished/failed downloads to keep the list clean
CLEANUP_DELAY_SECONDS = 15.0

def start_download(url: str, title: str, download_path: str, is_mobile: bool) -> str:
    """
    Starts the downloading process in a background thread and returns the unique download_id.
    """
    download_id = str(uuid.uuid4())
    
    with active_downloads_lock:
        active_downloads[download_id] = {
            "id": download_id,
            "url": url,
            "title": title,
            "progress": 0.0,
            "speed": "",
            "eta": "",
            "status": "pending",
            "error": None,
            "completed_at": None
        }

    # Start download thread
    thread = threading.Thread(target=_download_worker, args=(download_id, url, title, download_path, is_mobile))
    thread.daemon = True
    thread.start()
    
    return download_id

def get_all_downloads() -> list:
    """
    Returns a snapshot list of all tracked downloads. Proactively cleans up old finished/failed downloads.
    """
    now = time.time()
    to_delete = []
    
    with active_downloads_lock:
        for dl_id, d in active_downloads.items():
            if d["completed_at"] and (now - d["completed_at"] >= CLEANUP_DELAY_SECONDS):
                to_delete.append(dl_id)
                
        for dl_id in to_delete:
            del active_downloads[dl_id]
            
        return list(active_downloads.values())

def _download_worker(download_id: str, url: str, title: str, download_path: str, is_mobile: bool):
    output_template = os.path.join(download_path, "%(title)s.%(ext)s")
    last_update_time = [0.0]

    def progress_hook(d):
        if d["status"] == "downloading":
            now = time.time()
            # Throttling updates to 4 times per second to prevent lock contention
            if now - last_update_time[0] >= 0.25:
                pct_str = d.get("_percent_str", "").strip().replace("%", "")
                try:
                    progress = float(pct_str) / 100.0
                except Exception:
                    progress = 0.0
                
                speed = d.get("_speed_str", "").strip()
                eta = d.get("_eta_str", "").strip()
                
                with active_downloads_lock:
                    if download_id in active_downloads:
                        active_downloads[download_id].update({
                            "progress": progress,
                            "speed": speed,
                            "eta": eta,
                            "status": "downloading"
                        })
                last_update_time[0] = now
                
        elif d["status"] == "finished":
            with active_downloads_lock:
                if download_id in active_downloads:
                    active_downloads[download_id].update({
                        "progress": 1.0,
                        "status": "finished",
                        "completed_at": time.time()
                    })

    # Platform format selection
    if is_mobile:
        fmt = "best[ext=mp4]/best"
    else:
        fmt = "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best"

    ydl_opts = {
        "format": fmt,
        "outtmpl": output_template,
        "noplaylist": True,
        "progress_hooks": [progress_hook],
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4",
        
        # Connections & speed throttle bypasses
        "retries": 15,
        "fragment_retries": 15,
        "file_access_retries": 5,
        "buffersize": 1024 * 1024,
        "nocheckcertificate": True,
        
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"]
            }
        },
        
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache"
        }
    }
    
    try:
        # Mark as downloading initially
        with active_downloads_lock:
            if download_id in active_downloads:
                active_downloads[download_id]["status"] = "downloading"
                
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        # Ensure completion state is marked properly
        with active_downloads_lock:
            if download_id in active_downloads:
                active_downloads[download_id].update({
                    "progress": 1.0,
                    "status": "finished",
                    "completed_at": time.time()
                })
                
    except Exception as ex:
        # Mark as failed
        with active_downloads_lock:
            if download_id in active_downloads:
                active_downloads[download_id].update({
                    "status": "failed",
                    "error": str(ex),
                    "completed_at": time.time()
                })