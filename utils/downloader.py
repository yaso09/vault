import os
import re
import time
import threading
import uuid
import glob

import yt_dlp

from .ffmpeg import ffmpeg

# Thread-safe global dictionary to track active and recently finished/failed downloads
active_downloads = {}
active_downloads_lock = threading.Lock()

# Auto-cleanup time in seconds for finished/failed downloads to keep the list clean
CLEANUP_DELAY_SECONDS = 15.0

# yt-dlp format selector:
#   bestvideo[height<=1080]  → en iyi 1080p veya altı video-only stream
#   bestaudio                → en iyi ses-only stream
# İkisi birlikte indirilir, ffmpeg ile birleştirilir.
_VIDEO_FORMAT = (
    "bestvideo[height<=1080][vcodec^=avc1]/"   # önce H.264 1080p
    "bestvideo[height<=1080][vcodec^=hev1]/"   # sonra H.265 1080p
    "bestvideo[height<=1080][vcodec!=av01]/"   # AV1 hariç her codec 1080p
    "bestvideo[vcodec^=avc1]/"                 # codec kısıtı kaldır, H.264
    "bestvideo"                                # son çare
)
_AUDIO_FORMAT = "bestaudio[ext=m4a]/bestaudio"


# ─── Format helpers ───────────────────────────────────────────────────────────

def video_fmt(video_url: str) -> dict | None:
    """
    Returns info dict of the best video-only format for the given URL,
    or None if unavailable. (Replaces pytubefix Stream object.)
    """
    ydl_opts = {"quiet": True, "no_warnings": True, "format": _VIDEO_FORMAT}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=False)
        return info.get("requested_formats", [info])[0] if info else None


def audio_fmt(video_url: str) -> dict | None:
    """
    Returns info dict of the best audio-only format for the given URL,
    or None if unavailable.
    """
    ydl_opts = {"quiet": True, "no_warnings": True, "format": _AUDIO_FORMAT}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(video_url, download=False)
        return info.get("requested_formats", [info])[0] if info else None


# ─── Public API ───────────────────────────────────────────────────────────────

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
            "completed_at": None,
        }

    thread = threading.Thread(
        target=_download_worker,
        args=(download_id, url, title, download_path, is_mobile),
    )
    thread.daemon = True
    thread.start()

    return download_id


def get_all_downloads() -> list:
    """
    Returns a snapshot list of all tracked downloads.
    Proactively cleans up old finished/failed downloads.
    """
    now = time.time()

    with active_downloads_lock:
        to_delete = [
            dl_id
            for dl_id, d in active_downloads.items()
            if d["completed_at"] and now - d["completed_at"] >= CLEANUP_DELAY_SECONDS
        ]
        for dl_id in to_delete:
            del active_downloads[dl_id]

        return list(active_downloads.values())


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _update_status(download_id: str, **kwargs):
    with active_downloads_lock:
        if download_id in active_downloads:
            active_downloads[download_id].update(kwargs)


def _fmt_speed(speed_bps: float) -> str:
    if speed_bps >= 1_048_576:
        return f"{speed_bps / 1_048_576:.1f} MiB/s"
    if speed_bps >= 1024:
        return f"{speed_bps / 1024:.1f} KiB/s"
    return f"{speed_bps:.0f} B/s"


def _make_ydl_hooks(download_id: str, phase_offset: float, phase_weight: float):
    """
    Returns a yt-dlp progress hook list that maps per-phase download progress
    onto the overall 0–1 scale, with throttling to ~4 Hz.

    yt-dlp calls the hook with a dict containing:
        status        : 'downloading' | 'finished' | 'error'
        downloaded_bytes
        total_bytes / total_bytes_estimate
        speed         : bytes/s (float or None)
        eta           : seconds remaining (int or None)
    """
    last_update_time = [0.0]

    def hook(d: dict):
        now = time.time()
        status = d.get("status")

        if status == "downloading":
            if now - last_update_time[0] < 0.25:
                return  # throttle to ~4 Hz

            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes") or 0
            pct = (downloaded / total) if total > 0 else 0.0

            raw_speed = d.get("speed") or 0.0
            speed_str = _fmt_speed(raw_speed) if raw_speed > 0 else ""

            raw_eta = d.get("eta")
            eta_str = f"{int(raw_eta)}s" if raw_eta else ""

            _update_status(
                download_id,
                progress=round(phase_offset + pct * phase_weight, 4),
                speed=speed_str,
                eta=eta_str,
                status="downloading",
            )
            last_update_time[0] = now

    return [hook]


def _safe_filename(raw: str, fallback: str = "video") -> str:
    """Strip characters that are illegal in filenames on Windows/macOS/Linux."""
    safe = re.sub(r'[\\/:*?"<>|]', "", raw).strip()
    safe = safe.rstrip(". ")  # sondaki nokta/boşluk FFmpeg'i karıştırır
    return safe or fallback


# ─── Worker ───────────────────────────────────────────────────────────────────

def _download_worker(
    download_id: str,
    url: str,
    title: str,
    download_path: str,
    is_mobile: bool,
):
    short_id = download_id[:8]
    video_tmp = os.path.join(download_path, f".tmp_{short_id}_video.mp4")
    audio_tmp = os.path.join(download_path, f".tmp_{short_id}_audio.m4a")

    def cleanup_tmp():
        for f in glob.glob(os.path.join(download_path, f".tmp_{short_id}_*")):
            try:
                os.remove(f)
            except OSError:
                pass

    _update_status(download_id, status="downloading")

    try:
        # ── 1. Resolve title for output filename ──────────────────────────────
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
            info = ydl.extract_info(url, download=False)
            safe_title = _safe_filename(info.get("title", ""), fallback=title or "video")

        output_file = os.path.join(download_path, f"{safe_title}.mp4")

        # ── 2. Download video-only stream (0 % → 45 %) ───────────────────────
        ydl_video_opts = {
            "format": _VIDEO_FORMAT,
            "outtmpl": video_tmp,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "progress_hooks": _make_ydl_hooks(download_id, 0.00, 0.45),
        }
        with yt_dlp.YoutubeDL(ydl_video_opts) as ydl:
            ydl.download([url])

        if not os.path.isfile(video_tmp):
            raise FileNotFoundError(f"Video geçici dosyası bulunamadı: {video_tmp}")

        # ── 3. Download audio-only stream (45 % → 90 %) ──────────────────────
        ydl_audio_opts = {
            "format": _AUDIO_FORMAT,
            "outtmpl": audio_tmp,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "progress_hooks": _make_ydl_hooks(download_id, 0.45, 0.45),
        }
        with yt_dlp.YoutubeDL(ydl_audio_opts) as ydl:
            ydl.download([url])

        if not os.path.isfile(audio_tmp):
            raise FileNotFoundError(f"Ses geçici dosyası bulunamadı: {audio_tmp}")

        # ── 4. Merge via WASM FFmpeg (90 % → 100 %) ──────────────────────────
        _update_status(download_id, status="merging", progress=0.90)

        # ffmpeg mounts download_path as WASI root "/".
        # Pass only basenames — no subdirectory components.
        ret = ffmpeg(
            [
                "-loglevel", "warning",
                "-i", os.path.basename(video_tmp),
                "-i", os.path.basename(audio_tmp),
                "-c:v", "copy",          # remux video as-is (no re-encode)
                "-c:a", "aac",           # encode audio to AAC for mp4 compat
                "-movflags", "+faststart",
                "-y",
                os.path.basename(output_file),
            ],
            workspace_dir=download_path,
        )

        if ret != 0:
            raise RuntimeError(f"FFmpeg birleştirme başarısız oldu (çıkış kodu: {ret})")

        # ── 5. Cleanup ────────────────────────────────────────────────────────
        cleanup_tmp()

        _update_status(
            download_id,
            progress=1.0,
            status="finished",
            completed_at=time.time(),
        )

    except Exception as ex:
        cleanup_tmp()
        _update_status(
            download_id,
            status="failed",
            error=str(ex),
            completed_at=time.time(),
        )