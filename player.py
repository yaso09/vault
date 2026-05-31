import flet as ft
from flet_video import Video, VideoMedia, PlaylistMode
import json
import os
from pathlib import Path
import threading
import asyncio

# Sabit Renkler
BG_DEEP = "#0F0F0F"
BG_CARD = "#1F1F1F"
BORDER = "#3F3F3F"
COLOR_SUCCESS = "#2BA640"
TEXT_PRI = "#FFFFFF"
TEXT_SEC = "#AAAAAA"
TEXT_DIM = "#717171"

def load_positions(download_path: str) -> dict:
    """Kaydedilmiş video oynatma konumlarını JSON dosyasından yükler."""
    pos_file = Path(download_path) / ".playback_positions.json"
    if pos_file.exists():
        try:
            with open(pos_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_position(download_path: str, filepath: str, position_ms: int):
    """Videonun oynatma konumunu kaydeder."""
    pos_file = Path(download_path) / ".playback_positions.json"
    positions = load_positions(download_path)
    positions[filepath] = position_ms
    try:
        os.makedirs(download_path, exist_ok=True)
        with open(pos_file, "w", encoding="utf-8") as f:
            json.dump(positions, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def format_time_display(seconds: float) -> str:
    """Saniyeyi MM:SS formatına çevirir."""
    if seconds is None or seconds < 0:
        seconds = 0
    mins, secs = divmod(int(seconds), 60)
    hours, mins = divmod(mins, 60)
    if hours > 0:
        return f"{hours}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"

class CustomVideoPlayer(ft.Container):
    """
    Dahili video oynatma, tam ekran, oynatma hızı, ses kontrolü, kalan süre ve 
    konum kaydetme özelliklerine sahip gelişmiş ve kesintisiz video oynatıcı arayüzü.
    """
    def __init__(self, page: ft.Page, filepath: str, download_path: str, on_close):
        super().__init__()
        self.custom_page = page  # self.page Flet'te salt-okunur bir özelliktir, self.custom_page olarak saklıyoruz.
        self.filepath = filepath
        self.download_path = download_path
        self.on_close_callback = on_close
        
        self.filename = os.path.basename(filepath)
        self.display_name = self.filename
        for ext in (".mp4", ".mkv", ".webm"):
            self.display_name = self.display_name.replace(ext, "")
            
        self.expand = True
        self.bgcolor = BG_DEEP
        self.padding = ft.Padding.only(left=16, right=16, top=20, bottom=24)
        
        # State değişkenleri
        self.duration_sec = 0.0
        self.current_sec = 0.0
        self.is_seeking = False
        self.last_saved_sec = 0.0
        self._playing = True
        self._fullscreen_mode = False
        self._hide_timer = None
        self._is_alive = True  # Oynatıcı kapatılınca False; arka plan callback'lerini durdurur
        
        # Normal Mode UI Elemanları Tanımlaması
        self.play_pause_btn = ft.IconButton(
            icon=ft.Icons.PAUSE_ROUNDED,
            icon_color=TEXT_PRI,
            icon_size=32,
            on_click=self.toggle_play_pause
        )
        
        self.current_time_text = ft.Text("00:00", size=11, color=TEXT_PRI, weight=ft.FontWeight.W_500)
        self.total_time_text = ft.Text("00:00", size=11, color=TEXT_SEC)
        self.remaining_time_text = ft.Text("(Kalan: 00:00)", size=10, color=TEXT_DIM)
        
        self.seek_slider = ft.Slider(
            min=0,
            max=100,
            value=0,
            active_color=COLOR_SUCCESS,
            inactive_color=BORDER,
            on_change_start=self.on_slider_seek_start,
            on_change_end=self.on_slider_seek_end,
            expand=True
        )
        
        self.speed_btn = ft.TextButton(
            content=ft.Text("1.0x", color=TEXT_PRI, size=12, weight=ft.FontWeight.W_600),
            on_click=self.change_speed
        )
        
        self.volume_icon = ft.IconButton(
            icon=ft.Icons.VOLUME_UP_ROUNDED,
            icon_color=TEXT_PRI,
            icon_size=20,
            on_click=self.toggle_mute
        )
        
        self.volume_slider = ft.Slider(
            min=0,
            max=100,
            value=100,
            active_color=TEXT_PRI,
            inactive_color=BORDER,
            on_change=self.on_volume_change,
            width=120
        )

        # Fullscreen Mode UI Elemanları Tanımlaması
        self.fs_close_btn = ft.IconButton(
            icon=ft.Icons.FULLSCREEN_EXIT_ROUNDED,
            icon_color=TEXT_PRI,
            icon_size=28,
            on_click=self.toggle_fullscreen,
            tooltip="Tam Ekrandan Çık"
        )
        
        self.fs_play_pause_btn = ft.IconButton(
            icon=ft.Icons.PAUSE_ROUNDED,
            icon_color=TEXT_PRI,
            icon_size=48,
            on_click=self.toggle_play_pause
        )
        
        self.fs_current_time_text = ft.Text("00:00", size=11, color=TEXT_PRI, weight=ft.FontWeight.W_500)
        self.fs_total_time_text = ft.Text("00:00", size=11, color=TEXT_SEC)
        self.fs_remaining_time_text = ft.Text("(Kalan: 00:00)", size=10, color=TEXT_DIM)
        
        self.fs_seek_slider = ft.Slider(
            min=0,
            max=100,
            value=0,
            active_color=COLOR_SUCCESS,
            inactive_color=BORDER,
            on_change_start=self.on_slider_seek_start,
            on_change_end=self.on_slider_seek_end,
            expand=True
        )
        
        self.fs_volume_icon = ft.IconButton(
            icon=ft.Icons.VOLUME_UP_ROUNDED,
            icon_color=TEXT_PRI,
            icon_size=20,
            on_click=self.toggle_mute
        )
        
        self.fs_volume_slider = ft.Slider(
            min=0,
            max=100,
            value=100,
            active_color=TEXT_PRI,
            inactive_color=BORDER,
            on_change=self.on_volume_change,
            width=120
        )
        
        self.fs_speed_btn = ft.TextButton(
            content=ft.Text("1.0x", color=TEXT_PRI, size=12, weight=ft.FontWeight.W_600),
            on_click=self.change_speed
        )
        
        # Video Kontrolü
        self.video = Video(
            playlist=[VideoMedia(self.filepath)],
            autoplay=True,
            controls=None,  # Biz kendi özel arayüzümüzü kullanıyoruz
            playlist_mode=PlaylistMode.NONE,
            on_position_change=self.on_position_change,
            on_duration_change=self.on_duration_change,
            on_complete=self.on_video_complete,
            expand=True,
            aspect_ratio=16/9
        )
        
        self.build_player_ui()

    def _on_video_double_click(self, e):
        """Toggle fullscreen on double-click."""
        self.toggle_fullscreen(None)

    def build_player_ui(self):
        # Üst Kısım: Başlık ve Kapat (Normal Mode)
        self.top_bar = ft.Row(
            [
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK_ROUNDED,
                    icon_color=TEXT_PRI,
                    on_click=self.close_player,
                    tooltip="Kapat"
                ),
                ft.Text(
                    self.display_name,
                    size=14,
                    color=TEXT_PRI,
                    weight=ft.FontWeight.W_600,
                    overflow=ft.TextOverflow.ELLIPSIS,
                    expand=True
                )
            ],
            alignment=ft.MainAxisAlignment.START,
            top=0,
            left=0,
            right=0
        )
        
        # Fullscreen Overlay UI (Video Üzerine Binilecek Katman)
        fs_top_bar = ft.Row(
            [
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK_ROUNDED,
                    icon_color=TEXT_PRI,
                    on_click=self.toggle_fullscreen,
                    tooltip="Geri"
                ),
                ft.Text(
                    self.display_name,
                    size=14,
                    color=TEXT_PRI,
                    weight=ft.FontWeight.W_600,
                    overflow=ft.TextOverflow.ELLIPSIS,
                    expand=True
                ),
                self.fs_close_btn
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
        )
        
        fs_center_controls = ft.Row(
            [
                ft.IconButton(
                    icon=ft.Icons.REPLAY_10_ROUNDED,
                    icon_color=TEXT_PRI,
                    icon_size=32,
                    on_click=lambda _: self.seek_relative(-10),
                    tooltip="10sn Geri"
                ),
                self.fs_play_pause_btn,
                ft.IconButton(
                    icon=ft.Icons.FORWARD_10_ROUNDED,
                    icon_color=TEXT_PRI,
                    icon_size=32,
                    on_click=lambda _: self.seek_relative(10),
                    tooltip="10sn İleri"
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=40
        )
        
        fs_progress_row = ft.Row(
            [
                self.fs_current_time_text,
                self.fs_seek_slider,
                self.fs_total_time_text,
                self.fs_remaining_time_text
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER
        )
        
        fs_controls_row = ft.Row(
            [
                # Volume
                ft.Row(
                    [
                        self.fs_volume_icon,
                        self.fs_volume_slider
                    ],
                    spacing=0,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                ),
                # Speed
                self.fs_speed_btn
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER
        )
        
        fs_overlay_content = ft.Column(
            [
                fs_top_bar,
                ft.Container(expand=True), # Boşluk ekleyip kontrolleri iter
                fs_center_controls,
                ft.Container(expand=True),
                fs_progress_row,
                ft.Container(height=4),
                fs_controls_row
            ],
            spacing=0,
            expand=True
        )
        
        self.fullscreen_overlay = ft.Container(
            content=fs_overlay_content,
            bgcolor="#aa000000", # %66 şeffaf siyah
            padding=ft.Padding.only(left=24, right=24, top=20, bottom=24),
            visible=False,
            top=0,
            left=0,
            right=0,
            bottom=0
        )

        # Video ve Overlay'i Barındıran Stack Yapısı
        self.video_stack = ft.Stack(
            [
                self.video,
                self.fullscreen_overlay
            ],
            expand=True
        )
        
        self.video_container = ft.Container(
            content=self.video_stack,
            alignment=ft.Alignment.CENTER,
            expand=True,
            border_radius=12,
            border=ft.Border.all(1, BORDER),
            bgcolor="#000000"
        )
        
        # Hover ve tıklamaları kontrol edecek GestureDetector
        self.video_gesture_detector = ft.GestureDetector(
            content=self.video_container,
            on_double_tap=self._on_video_double_click,
            on_tap=self.on_video_tap,
            on_hover=self.on_video_hover,
            top=60,
            bottom=110,
            left=0,
            right=0
        )
        
        # Alt Kısım: Seek Bar ve Zamanlar (Normal Mode)
        self.progress_row = ft.Row(
            [
                self.current_time_text,
                self.seek_slider,
                self.total_time_text,
                self.remaining_time_text
            ],
            spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER
        )
        
        # Alt Kısım: Denetim Butonları (Normal Mode)
        self.controls_row = ft.Row(
            [
                ft.Row(
                    [
                        self.volume_icon,
                        self.volume_slider
                    ],
                    spacing=0,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                ),
                # Geri sar, Oynat/Durdur, İleri sar
                ft.Row(
                    [
                        ft.IconButton(
                            icon=ft.Icons.REPLAY_10_ROUNDED,
                            icon_color=TEXT_PRI,
                            icon_size=24,
                            on_click=lambda _: self.seek_relative(-10),
                            tooltip="10sn Geri"
                        ),
                        self.play_pause_btn,
                        ft.IconButton(
                            icon=ft.Icons.FORWARD_10_ROUNDED,
                            icon_color=TEXT_PRI,
                            icon_size=24,
                            on_click=lambda _: self.seek_relative(10),
                            tooltip="10sn İleri"
                        ),
                    ],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                ),
                # Hız ve Tam ekran
                ft.Row(
                    [
                        self.speed_btn,
                        ft.IconButton(
                            icon=ft.Icons.FULLSCREEN_ROUNDED,
                            icon_color=TEXT_PRI,
                            on_click=self.toggle_fullscreen,
                            tooltip="Tam Ekran"
                        )
                    ],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                )
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER
        )
        
        self.spacing3 = ft.Container(height=4)
        
        # Normal Mode Alt Kontroller Grubu
        self.normal_bottom_controls = ft.Column(
            [
                self.progress_row,
                self.spacing3,
                self.controls_row
            ],
            spacing=0,
            bottom=0,
            left=0,
            right=0
        )
        
        # Ana içerik Stack yapısı. Video oynatıcının sırası/yeri değişmeyecek.
        self.content = ft.Stack(
            [
                self.video_gesture_detector,
                self.top_bar,
                self.normal_bottom_controls
            ],
            expand=True
        )

    # --- Helper utilities for robust event/data handling ---
    def _to_ms(self, data):
        """Normalize event data to milliseconds (int) or return None."""
        try:
            if data is None:
                return None
            
            # If it has in_milliseconds attribute (like flet Duration)
            if hasattr(data, "in_milliseconds"):
                val = getattr(data, "in_milliseconds")
                if callable(val):
                    return int(val())
                return int(val)
                
            # If it is a timedelta object
            if hasattr(data, "total_seconds"):
                return int(data.total_seconds() * 1000)
                
            # e.data can be string or numeric
            if isinstance(data, str):
                s = data.strip().replace(",", "")
                if not s:
                    return None
                # Check for standard HH:MM:SS format
                if ":" in s:
                    parts = s.split(":")
                    if len(parts) == 3:
                        h = float(parts[0])
                        m = float(parts[1])
                        s_val = float(parts[2])
                        return int((h * 3600 + m * 60 + s_val) * 1000)
                    elif len(parts) == 2:
                        m = float(parts[0])
                        s_val = float(parts[1])
                        return int((m * 60 + s_val) * 1000)
                val = float(s)
            else:
                val = float(data)

            # Heuristic: large numbers (>10_000) are likely already milliseconds
            if val > 10000:
                return int(val)
            # Otherwise treat as seconds and convert to ms
            return int(val * 1000)
        except Exception:
            return None

    def _is_playing(self):
        """Return local playing state tracked by this wrapper."""
        return bool(getattr(self, "_playing", False))

    def _call(self, fn, *args, **kwargs):
        """Call a function that may be sync or return a coroutine.

        If the function returns a coroutine it will be scheduled safely
        from any thread. Swallows exceptions and returns False on failure.
        """
        try:
            res = fn(*args, **kwargs)
            if asyncio.iscoroutine(res):
                async def _run(c):
                    try:
                        await c
                    except Exception:
                        pass  # RuntimeError: Session closed ve benzeri hataları yut
                try:
                    self.custom_page.run_task(_run, res)
                except Exception:
                    # fallback: asyncio.ensure_future via the event loop
                    try:
                        loop = asyncio.get_event_loop()
                        loop.call_soon_threadsafe(asyncio.ensure_future, res)
                    except Exception:
                        pass
            return True
        except Exception:
            return False

    def _set_seek_value(self, seconds):
        """Safely set `seek_slider.value` in seconds, expanding `max` if needed.

        This prevents ValueError when assigning a value greater than the
        current slider max. The function accepts seconds (float/int/str).
        """
        try:
            if seconds is None:
                return
            secs = float(seconds)
        except Exception:
            return

        # determine current slider max
        try:
            raw_max = getattr(self.seek_slider, "max", None)
            max_v = float(raw_max) if raw_max is not None else 0.0
        except Exception:
            max_v = 0.0

        # If slider max is not useful, prefer duration when available
        if not max_v or max_v <= 0:
            try:
                if getattr(self, "duration_sec", 0) and self.duration_sec > 0:
                    max_v = float(self.duration_sec)
                    try:
                        self.seek_slider.max = max_v
                        self.fs_seek_slider.max = max_v
                    except Exception:
                        pass
                else:
                    # fallback default
                    max_v = max(secs, 100.0)
                    try:
                        self.seek_slider.max = max_v
                        self.fs_seek_slider.max = max_v
                    except Exception:
                        pass
            except Exception:
                max_v = max(secs, 100.0)

        # If requested seconds exceed max, try to grow max first
        if secs > max_v:
            try:
                self.seek_slider.max = secs
                self.fs_seek_slider.max = secs
                max_v = secs
            except Exception:
                # if cannot grow, clamp
                secs = max_v

        # clamp to min/max
        try:
            min_v = float(getattr(self.seek_slider, "min", 0) or 0)
        except Exception:
            min_v = 0.0
        if secs < min_v:
            secs = min_v
        if secs > max_v:
            secs = max_v

        # finally set value safely
        try:
            self.seek_slider.value = secs
            self.fs_seek_slider.value = secs
        except Exception:
            try:
                self.seek_slider.value = min(max(secs, min_v), getattr(self.seek_slider, "max", secs))
                self.fs_seek_slider.value = min(max(secs, min_v), getattr(self.fs_seek_slider, "max", secs))
            except Exception:
                pass

    def on_video_tap(self, e):
        """Video tıklama olayı. Kontroller gizliyse gösterir, görünürse durdur/oynat yapar."""
        if self._fullscreen_mode:
            if not self.fullscreen_overlay.visible:
                self.show_controls()
            else:
                self.toggle_play_pause(e)

    def on_video_hover(self, e):
        """Mouse video üzerine geldiğinde kontrolleri gösterir."""
        if self._fullscreen_mode and not self.fullscreen_overlay.visible:
            self.show_controls()
        elif self._fullscreen_mode:
            # Kontroller zaten görünür, sadece zamanlayıcıyı sıfırla
            self.reset_hide_timer()

    def show_controls(self):
        """Tam ekran kontrollerini görünür yapar ve otomatik gizleme zamanlayıcısını başlatır."""
        if self._fullscreen_mode and not self.fullscreen_overlay.visible:
            self.fullscreen_overlay.visible = True
            self.custom_page.update()
        self.reset_hide_timer()

    def hide_controls(self):
        """Tam ekran kontrollerini otomatik olarak gizler."""
        if not self._is_alive:
            return
        if self.is_seeking or not self._playing:
            self.reset_hide_timer()
            return
        if self.fullscreen_overlay.visible:
            self.fullscreen_overlay.visible = False
            try:
                self.custom_page.update()
            except Exception:
                pass

    def reset_hide_timer(self):
        """Kontrollerin otomatik gizlenmesi için 3 saniyelik zamanlayıcıyı sıfırlar."""
        if hasattr(self, "_hide_timer") and self._hide_timer:
            try:
                self._hide_timer.cancel()
            except Exception:
                pass
        self._hide_timer = threading.Timer(3.0, self.hide_controls)
        self._hide_timer.daemon = True
        self._hide_timer.start()

    def did_mount(self):
        # Kaydedilmiş son konumu yükle ve oradan başlat
        positions = load_positions(self.download_path)
        saved_ms = positions.get(self.filepath, 0)
        if saved_ms > 0:
            # Video hazır olduğunda seek yapılması için sınırlı denemelerle gecikmeyle çağır
            attempts = {"n": 0}

            def try_seek():
                if not self._is_alive:
                    return  # Oynatıcı kapandıysa retry döngüsünü de durdur
                try:
                    # Use safe caller which handles both sync and coroutine methods
                    try:
                        self._call(getattr(self.video, "seek"), saved_ms)
                    except Exception:
                        pass
                    self.current_sec = saved_ms / 1000
                    self.seek_slider.value = self.current_sec
                    self.fs_seek_slider.value = self.current_sec
                    time_str = format_time_display(self.current_sec)
                    self.current_time_text.value = time_str
                    self.fs_current_time_text.value = time_str
                    self.custom_page.update()
                except Exception:
                    attempts["n"] += 1
                    if attempts["n"] < 10:
                        threading.Timer(0.25, try_seek).start()

            threading.Timer(0.25, try_seek).start()

    def close_player(self, e=None):
        self._is_alive = False  # Tüm arka plan callback'lerini hemen durdur
        # Tam ekran aktifse çık
        if self._fullscreen_mode and self.custom_page.window:
            try:
                self.custom_page.window.full_screen = False
            except Exception:
                pass
        # Zamanlayıcıyı iptal et
        if hasattr(self, "_hide_timer") and self._hide_timer:
            try:
                self._hide_timer.cancel()
            except Exception:
                pass
                
        # Konumu son kez kaydet
        if self.video:
            try:
                current_ms = int(self.current_sec * 1000)
                save_position(self.download_path, self.filepath, current_ms)
                try:
                    self._call(getattr(self.video, "stop"))
                except Exception:
                    pass
            except Exception:
                pass
        self.on_close_callback()

    def toggle_play_pause(self, e):
        try:
            if self._is_playing():
                # Prefer native pause() if available; use safe caller
                try:
                    if hasattr(self.video, "pause"):
                        self._call(self.video.pause)
                    else:
                        setattr(self.video, "playing", False)
                except Exception:
                    pass
                self.play_pause_btn.icon = ft.Icons.PLAY_ARROW_ROUNDED
                self.fs_play_pause_btn.icon = ft.Icons.PLAY_ARROW_ROUNDED
                self._playing = False
                save_position(self.download_path, self.filepath, int(self.current_sec * 1000))
            else:
                try:
                    if hasattr(self.video, "play"):
                        self._call(self.video.play)
                    else:
                        setattr(self.video, "playing", True)
                except Exception:
                    pass
                self.play_pause_btn.icon = ft.Icons.PAUSE_ROUNDED
                self.fs_play_pause_btn.icon = ft.Icons.PAUSE_ROUNDED
                self._playing = True
        except Exception:
            pass
        self.custom_page.update()

    def toggle_mute(self, e):
        if self.video.volume > 0:
            self.volume_before_mute = self.video.volume
            self.video.volume = 0
            self.volume_slider.value = 0
            self.fs_volume_slider.value = 0
            self.volume_icon.icon = ft.Icons.VOLUME_MUTE_ROUNDED
            self.fs_volume_icon.icon = ft.Icons.VOLUME_MUTE_ROUNDED
        else:
            prev_vol = getattr(self, "volume_before_mute", 100)
            self.video.volume = prev_vol
            self.volume_slider.value = prev_vol
            self.fs_volume_slider.value = prev_vol
            self.volume_icon.icon = ft.Icons.VOLUME_UP_ROUNDED
            self.fs_volume_icon.icon = ft.Icons.VOLUME_UP_ROUNDED
        self.custom_page.update()

    def on_volume_change(self, e):
        val = int(e.control.value)
        self.video.volume = val
        self.volume_slider.value = val
        self.fs_volume_slider.value = val
        
        icon = ft.Icons.VOLUME_MUTE_ROUNDED if val == 0 else ft.Icons.VOLUME_UP_ROUNDED
        self.volume_icon.icon = icon
        self.fs_volume_icon.icon = icon
        self.custom_page.update()

    def seek_relative(self, delta_seconds: int):
        target = self.current_sec + delta_seconds
        if target < 0:
            target = 0
        if self.duration_sec and target > self.duration_sec:
            target = self.duration_sec

        target_ms = int(target * 1000)
        try:
            # Safely call seek (may be coroutine or sync)
            self._call(getattr(self.video, "seek"), target_ms)
        except Exception:
            pass
        self.current_sec = target
        self.seek_slider.value = target
        self.fs_seek_slider.value = target
        
        time_str = format_time_display(target)
        self.current_time_text.value = time_str
        self.fs_current_time_text.value = time_str
        self.custom_page.update()

    def on_slider_seek_start(self, e):
        self.is_seeking = True

    def on_slider_seek_end(self, e):
        val = e.control.value
        target_ms = int(val * 1000)
        try:
            self._call(getattr(self.video, "seek"), target_ms)
        except Exception:
            pass
        self.current_sec = val
        self.seek_slider.value = val
        self.fs_seek_slider.value = val
        self.is_seeking = False
        save_position(self.download_path, self.filepath, target_ms)
        self.custom_page.update()

    def change_speed(self, e):
        current_rate = self.video.playback_rate
        if current_rate == 1.0:
            next_rate = 1.25
        elif current_rate == 1.25:
            next_rate = 1.5
        elif current_rate == 1.5:
            next_rate = 2.0
        elif current_rate == 2.0:
            next_rate = 0.5
        else:
            next_rate = 1.0
            
        self.video.playback_rate = next_rate
        self.speed_btn.content.value = f"{next_rate}x"
        self.fs_speed_btn.content.value = f"{next_rate}x"
        self.custom_page.update()

    def toggle_fullscreen(self, e):
        """Toggle fullscreen mode (both app-level and OS-level if on desktop)."""
        self._fullscreen_mode = not self._fullscreen_mode
        
        # OS-level full_screen toggle for desktop
        if self.custom_page.window:
            try:
                self.custom_page.window.full_screen = self._fullscreen_mode
            except Exception:
                pass

        # Toggle UI visibility of normal components
        self.top_bar.visible = not self._fullscreen_mode
        self.normal_bottom_controls.visible = not self._fullscreen_mode
        
        # Reposition video gesture detector
        if self._fullscreen_mode:
            self.video_gesture_detector.top = 0
            self.video_gesture_detector.bottom = 0
        else:
            self.video_gesture_detector.top = 60
            self.video_gesture_detector.bottom = 110

        # Toggle UI visibility of fullscreen overlay components
        self.fullscreen_overlay.visible = self._fullscreen_mode
        
        # Update video container styling
        self.video_container.border_radius = 0 if self._fullscreen_mode else 12
        self.video_container.border = ft.Border.all(0, BORDER) if self._fullscreen_mode else ft.Border.all(1, BORDER)
        
        if self._fullscreen_mode:
            self.show_controls()
        else:
            # Cancel timer when returning to windowed mode
            if hasattr(self, "_hide_timer") and self._hide_timer:
                try:
                    self._hide_timer.cancel()
                except Exception:
                    pass
            self.fullscreen_overlay.visible = False
            
        self.custom_page.update()

    def on_position_change(self, e):
        if not self._is_alive or self.is_seeking:
            return
        try:
            pos_ms = self._to_ms(e.data)
            if pos_ms is None:
                return
            self.current_sec = pos_ms / 1000

            # Süre henüz bilinmiyorsa, slider max'ını pozisyona göre genişlet
            if self.duration_sec <= 0 or self.current_sec > self.duration_sec:
                safe_max = max(self.current_sec, self.seek_slider.max or 100)
                try:
                    self.seek_slider.max = safe_max
                    self.fs_seek_slider.max = safe_max
                except Exception:
                    pass

            self.seek_slider.value = min(self.current_sec, self.seek_slider.max)
            self.fs_seek_slider.value = min(self.current_sec, self.fs_seek_slider.max)
            
            time_str = format_time_display(self.current_sec)
            self.current_time_text.value = time_str
            self.fs_current_time_text.value = time_str

            # Mark as playing when position updates
            self._playing = True

            # Kalan süreyi hesapla
            remaining = max(self.duration_sec - self.current_sec, 0)
            remaining_str = f"(Kalan: {format_time_display(remaining)})"
            self.remaining_time_text.value = remaining_str
            self.fs_remaining_time_text.value = remaining_str

            # Her 3 saniyede bir diske kaydet
            if abs(self.current_sec - self.last_saved_sec) >= 3.0:
                save_position(self.download_path, self.filepath, int(self.current_sec * 1000))
                self.last_saved_sec = self.current_sec

            self.custom_page.update()
        except Exception:
            pass

    def on_duration_change(self, e):
        if not self._is_alive:
            return
        try:
            dur_ms = self._to_ms(e.data)
            if dur_ms is None:
                return
            self.duration_sec = dur_ms / 1000
            # ensure slider has a sensible max
            self.seek_slider.max = max(self.duration_sec, 1)
            self.fs_seek_slider.max = max(self.duration_sec, 1)
            
            total_str = format_time_display(self.duration_sec)
            self.total_time_text.value = total_str
            self.fs_total_time_text.value = total_str
            self.custom_page.update()
        except Exception:
            pass

    def on_video_complete(self, e):
        if not self._is_alive:
            return
        # Video bitince başa sar ve durdur
        try:
            self._call(getattr(self.video, "seek"), 0)
        except Exception:
            pass
        try:
            self._call(getattr(self.video, "pause"))
        except Exception:
            pass
        self.play_pause_btn.icon = ft.Icons.PLAY_ARROW_ROUNDED
        self.fs_play_pause_btn.icon = ft.Icons.PLAY_ARROW_ROUNDED
        self._playing = False
        self.current_sec = 0.0
        self.seek_slider.value = 0.0
        self.fs_seek_slider.value = 0.0
        self.current_time_text.value = "00:00"
        self.fs_current_time_text.value = "00:00"
        save_position(self.download_path, self.filepath, 0)
        self.custom_page.update()