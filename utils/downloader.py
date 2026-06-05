import os
import time
import threading
import uuid
import glob

from pytubefix import YouTube
from pytubefix.streams import Stream

from .ffmpeg import ffmpeg

# Thread-safe global dictionary to track active and recently finished/failed downloads
active_downloads = {}
active_downloads_lock = threading.Lock()

# Auto-cleanup time in seconds for finished/failed downloads to keep the list clean
CLEANUP_DELAY_SECONDS = 15.0


# ─── Format helpers ───────────────────────────────────────────────────────────

def video_fmt(video_url: str) -> Stream | None:
    """
    Returns the best video-only Stream object for the given URL,
    or None if no adaptive video stream is available.
    """
    yt = YouTube(video_url, client="ANDROID_VR")
    streams = yt.streams.filter(only_video=True, adaptive=True)
    if not streams:
        return None
    # Sort by resolution (height), fps, then bitrate — pick the highest
    best = max(
        streams,
        key=lambda s: (
            int(s.resolution.replace("p", "")) if s.resolution else 0,
            s.fps or 0,
            s.bitrate or 0,
        ),
    )
    return best


def audio_fmt(video_url: str) -> Stream | None:
    """
    Returns the best audio-only Stream object for the given URL,
    or None if no adaptive audio stream is available.
    """
    yt = YouTube(video_url, client="ANDROID_VR")
    streams = yt.streams.filter(only_audio=True, adaptive=True)
    if not streams:
        return None
    best = max(
        streams,
        key=lambda s: (
            s.abr_as_int if hasattr(s, "abr_as_int") else (int(s.abr.replace("kbps", "")) if s.abr else 0),
            s.bitrate or 0,
        ),
    )
    return best


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


def _make_progress_hook(
    download_id: str,
    phase_offset: float,
    phase_weight: float,
    last_update_time: list,
    stream_size: int,
):
    """
    Returns a pytubefix on_progress callback that maps per-phase progress
    onto the overall 0–1 progress scale.

    Callback signature: (stream, chunk: bytes, bytes_remaining: int)

    phase_offset : where this phase starts   (e.g. 0.00 for video, 0.45 for audio)
    phase_weight : fraction of total covered (e.g. 0.45 for each, 0.10 for merge)
    stream_size  : total file size in bytes (used to derive pct)
    """
    def hook(stream: Stream, chunk: bytes, bytes_remaining: int):
        now = time.time()
        # Throttle updates to ~4 Hz to prevent lock contention
        if now - last_update_time[0] >= 0.25:
            if stream_size > 0:
                downloaded = stream_size - bytes_remaining
                pct = downloaded / stream_size
            else:
                pct = 0.0

            # Rough speed estimate based on chunk size and time delta
            elapsed = now - last_update_time[0] if last_update_time[0] > 0 else 1.0
            speed_bps = len(chunk) / elapsed if elapsed > 0 else 0
            if speed_bps >= 1_048_576:
                speed_str = f"{speed_bps / 1_048_576:.1f} MiB/s"
            elif speed_bps >= 1024:
                speed_str = f"{speed_bps / 1024:.1f} KiB/s"
            else:
                speed_str = f"{speed_bps:.0f} B/s"

            eta_str = ""
            if speed_bps > 0 and bytes_remaining > 0:
                eta_secs = int(bytes_remaining / speed_bps)
                eta_str = f"{eta_secs}s"

            _update_status(
                download_id,
                progress=round(phase_offset + pct * phase_weight, 4),
                speed=speed_str,
                eta=eta_str,
                status="downloading",
            )
            last_update_time[0] = now

    return hook


# ─── Worker ───────────────────────────────────────────────────────────────────

def _download_worker(
    download_id: str,
    url: str,
    title: str,
    download_path: str,
    is_mobile: bool,
):
    # Unique prefix for temp files so concurrent downloads never collide
    short_id = download_id[:8]
    video_tmp_name = f".tmp_{short_id}_video"
    audio_tmp_name = f".tmp_{short_id}_audio"

    def cleanup_tmp():
        """Delete all temp files belonging to this download_id."""
        for f in glob.glob(os.path.join(download_path, f".tmp_{short_id}_*")):
            try:
                os.remove(f)
            except OSError:
                pass

    _update_status(download_id, status="downloading")
    last_update = [0.0]

    try:
        # ── 1. Resolve metadata & output filename ─────────────────────────────
        yt = YouTube(url, client="ANDROID_VR")
        safe_title = (
            "".join(c for c in yt.title if c not in r'\/:*?"<>|').strip()
            or title
            or "video"
        )
        output_file = os.path.join(download_path, f"{safe_title}.mp4")

        # ── 2. Pick the best video-only stream ───────────────────────────────
        video_streams = yt.streams.filter(only_video=True, adaptive=True)
        if not video_streams:
            raise RuntimeError("Uygun video akışı bulunamadı.")

        video_stream = max(
            video_streams,
            key=lambda s: (
                int(s.resolution.replace("p", "")) if s.resolution else 0,
                s.fps or 0,
                s.bitrate or 0,
            ),
        )

        # ── 3. Download the video stream ──────────────────────────────────────
        video_size = video_stream.filesize or 0

        # Register phase-scoped progress hook (video: 0% → 45%)
        yt.register_on_progress_callback(
            _make_progress_hook(download_id, 0.00, 0.45, last_update, video_size)
        )

        # stream.download() returns the real absolute path it wrote to —
        # use it directly instead of glob so concurrent downloads never collide.
        video_ext = video_stream.subtype or "mp4"
        video_file_name = f"/{video_tmp_name}.{video_ext}"
        video_file: str = video_stream.download(
            output_path=download_path,
            filename=video_file_name,
            skip_existing=False,
        )

        if not video_file or not os.path.isfile(video_file):
            raise FileNotFoundError(
                f"Video geçici dosyası bulunamadı (beklenen: {video_tmp_name}.{video_ext})"
            )

        # ── 4. Pick the best audio-only stream ───────────────────────────────
        audio_streams = yt.streams.filter(only_audio=True, adaptive=True)
        if not audio_streams:
            raise RuntimeError("Uygun ses akışı bulunamadı.")

        # Prefer m4a/mp4a for direct AAC remux; fall back to whatever is available
        m4a_streams = [s for s in audio_streams if s.subtype == "mp4"]
        audio_stream = max(
            m4a_streams or audio_streams,
            key=lambda s: (s.bitrate or 0),
        )

        # ── 5. Download the audio stream ──────────────────────────────────────
        audio_size = audio_stream.filesize or 0

        # Fresh YouTube object so we don't fight over the single progress callback slot
        yt_audio = YouTube(url, client="ANDROID_VR")
        yt_audio.register_on_progress_callback(
            _make_progress_hook(download_id, 0.45, 0.45, last_update, audio_size)
        )

        audio_ext = audio_stream.subtype or "mp4"
        # Re-fetch by itag on the new yt object so it inherits the new callback
        audio_stream2 = yt_audio.streams.get_by_itag(audio_stream.itag)
        if audio_stream2 is None:
            audio_streams2 = yt_audio.streams.filter(only_audio=True, adaptive=True)
            m4a2 = [s for s in audio_streams2 if s.subtype == "mp4"]
            audio_stream2 = max(m4a2 or audio_streams2, key=lambda s: s.bitrate or 0)
            audio_ext = audio_stream2.subtype or "mp4"

        audio_file_name = f"/{audio_tmp_name}.{audio_ext}"
        audio_file: str = audio_stream2.download(
            output_path=download_path,
            filename=audio_file_name,
            skip_existing=False,
        )

        if not audio_file or not os.path.isfile(audio_file):
            raise FileNotFoundError(
                f"Ses geçici dosyası bulunamadı (beklenen: {audio_tmp_name}.{audio_ext})"
            )

        # ── 6. Merge via WASM FFmpeg ──────────────────────────────────────────
        _update_status(download_id, status="merging", progress=0.90)
        
        # ffmpeg mounts download_path as WASI root "/".
        # All paths passed to it must be basenames only — no subdirectory components.
        # os.path.basename() is safe here because download() always writes into
        # download_path (we pass output_path=download_path above).
        ret = ffmpeg(
            [
                "-loglevel", "warning",
                "-i", video_file_name,
                "-i", audio_file_name,
                "-c:v", "copy",       # video stream: remux as-is (no re-encode)
                "-c:a", "aac",        # audio stream: encode to AAC for mp4 compat
                "-movflags", "+faststart",
                "-y",                 # overwrite output if it already exists
                os.path.basename(output_file),
            ],
            workspace_dir=download_path,
        )

        if ret != 0:
            raise RuntimeError(f"FFmpeg birleştirme başarısız oldu (çıkış kodu: {ret})")

        # ── 7. Cleanup temp files ─────────────────────────────────────────────
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