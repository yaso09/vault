import asyncio
import json
import os
import time
from pathlib import Path

import flet as ft
from flet_video import PlaylistMode, Video, VideoMedia

BG_DEEP = "#0F0F0F"
BG_SURFACE = "#1F1F1F"
BORDER = "#3F3F3F"
GRADIENT_TOP = "#E6000000"
GRADIENT_BOTTOM = "#F2000000"
ACCENT = "#FF0000"
ACCENT_SOFT = "#FF4444"
PROGRESS_BG = "#59FFFFFF"
TEXT_PRI = "#FFFFFF"
TEXT_SEC = "#AAAAAA"
TEXT_DIM = "#717171"

SPEEDS = (0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0)
HIDE_CONTROLS_SEC = 3.0
SKIP_SECONDS = 10
UI_REFRESH_SEC = 0.35
SEEK_GUARD_SEC = 2.0


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


def format_time_display(seconds: float) -> str:
    if seconds is None or seconds < 0:
        seconds = 0
    mins, secs = divmod(int(seconds), 60)
    hours, mins = divmod(mins, 60)
    if hours > 0:
        return f"{hours}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"


def _icon_btn(icon, on_click, *, size=24, tooltip=None, color=TEXT_PRI):
    return ft.IconButton(
        icon=icon,
        icon_color=color,
        icon_size=size,
        tooltip=tooltip,
        on_click=on_click,
        style=ft.ButtonStyle(
            padding=ft.Padding.symmetric(horizontal=10, vertical=8),
            overlay_color="#33FFFFFF",
            shape=ft.RoundedRectangleBorder(radius=8),
        ),
    )


class CustomVideoPlayer(ft.Container):
    """Video oynatıcı — UI güncellemeleri yalnızca Flet ana döngüsünde, hafif patch ile."""

    def __init__(self, page: ft.Page, filepath: str, download_path: str, on_close):
        super().__init__()
        self.custom_page = page
        self.filepath = filepath
        self.download_path = download_path
        self.on_close_callback = on_close

        self.filename = os.path.basename(filepath)
        self.display_name = self.filename
        for ext in (".mp4", ".mkv", ".webm", ".avi", ".mov"):
            self.display_name = self.display_name.replace(ext, "")

        self.expand = True
        self.bgcolor = BG_DEEP
        self.padding = 0

        self.duration_sec = 0.0
        self.current_sec = 0.0
        self.is_seeking = False
        self.last_saved_sec = 0.0
        self._playing = True
        self._fullscreen_mode = False
        self._controls_visible = True
        self._is_alive = True
        self._keyboard_bound = False
        self.volume_before_mute = 100

        self._last_progress_ui_at = 0.0
        self._progress_ui_generation = 0
        self._hide_generation = 0
        self._seek_guard_generation = 0
        self._layout_dirty = False

        self._build_controls()
        self._build_layout()
        self._bind_keyboard()

    # ── UI oluşturma ─────────────────────────────────────────────────

    def _build_controls(self):
        self.play_pause_btn = _icon_btn(
            ft.Icons.PAUSE_ROUNDED, self.toggle_play_pause, size=36, tooltip="Oynat / Duraklat"
        )
        self.rewind_btn = _icon_btn(
            ft.Icons.REPLAY_10_ROUNDED,
            lambda _: self.seek_relative(-SKIP_SECONDS),
            size=28,
            tooltip=f"{SKIP_SECONDS} sn geri",
        )
        self.forward_btn = _icon_btn(
            ft.Icons.FORWARD_10_ROUNDED,
            lambda _: self.seek_relative(SKIP_SECONDS),
            size=28,
            tooltip=f"{SKIP_SECONDS} sn ileri",
        )

        self.current_time_text = ft.Text(
            "0:00", size=12, color=TEXT_PRI, weight=ft.FontWeight.W_600
        )
        self.total_time_text = ft.Text("0:00", size=12, color=TEXT_SEC)

        self.seek_slider = ft.Slider(
            min=0,
            max=100,
            value=0,
            active_color=ACCENT,
            inactive_color=PROGRESS_BG,
            thumb_color=ACCENT_SOFT,
            on_change=self.on_slider_change,
            on_change_start=self.on_slider_seek_start,
            on_change_end=self.on_slider_seek_end,
            expand=True,
        )

        self.volume_icon = _icon_btn(ft.Icons.VOLUME_UP_ROUNDED, self.toggle_mute, size=22)
        self.volume_slider = ft.Slider(
            min=0,
            max=100,
            value=100,
            active_color=TEXT_PRI,
            inactive_color=PROGRESS_BG,
            on_change=self.on_volume_change,
            width=88,
        )

        self.speed_label = ft.Text("1×", size=12, color=TEXT_PRI, weight=ft.FontWeight.W_600)
        self.speed_btn = ft.TextButton(
            content=self.speed_label,
            on_click=self.cycle_speed,
            style=ft.ButtonStyle(
                padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                shape=ft.RoundedRectangleBorder(radius=8),
            ),
        )
        self.fullscreen_btn = _icon_btn(
            ft.Icons.FULLSCREEN_ROUNDED, self.toggle_fullscreen, size=22, tooltip="Tam ekran"
        )

        self.video = Video(
            playlist=[VideoMedia(self.filepath)],
            autoplay=True,
            controls=None,
            playlist_mode=PlaylistMode.NONE,
            on_position_change=self.on_position_change,
            on_duration_change=self.on_duration_change,
            on_complete=self.on_video_complete,
            expand=True,
        )

    def _build_layout(self):
        progress_row = ft.Row(
            [
                self.current_time_text,
                ft.Text("/", size=12, color=TEXT_DIM),
                self.total_time_text,
                self.seek_slider,
            ],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        transport_row = ft.Row(
            [
                ft.Row(
                    [self.volume_icon, self.volume_slider],
                    spacing=0,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row(
                    [self.rewind_btn, self.play_pause_btn, self.forward_btn],
                    spacing=4,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row(
                    [self.speed_btn, self.fullscreen_btn],
                    spacing=4,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        self.controls_panel = ft.Container(
            content=ft.Column(
                [progress_row, ft.Container(height=4), transport_row],
                spacing=0,
                tight=True,
            ),
            padding=ft.Padding.symmetric(horizontal=4, vertical=10),
            bgcolor=BG_SURFACE,
            border_radius=ft.BorderRadius.only(bottom_left=12, bottom_right=12),
        )
        self.top_bar = ft.Container(
            content=ft.Row(
                [
                    _icon_btn(ft.Icons.ARROW_BACK_ROUNDED, self.close_player, size=24, tooltip="Kapat"),
                    ft.Text(
                        self.display_name,
                        size=15,
                        color=TEXT_PRI,
                        weight=ft.FontWeight.W_600,
                        overflow=ft.TextOverflow.ELLIPSIS,
                        expand=True,
                    ),
                ],
                spacing=4,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.only(left=4, right=4, top=8, bottom=4),
        )
        self._video_box = ft.Container(content=self.video, expand=True, bgcolor="#000000")
        self.video_surface = ft.GestureDetector(
            content=self._video_box,
            on_tap=self.on_video_tap,
            on_double_tap=self._on_video_double_click,
            expand=True,
            mouse_cursor=ft.MouseCursor.CLICK,
        )
        self.video_frame = ft.Container(
            content=self.video_surface,
            expand=True,
            border=ft.Border.all(1, BORDER),
            border_radius=ft.BorderRadius.only(top_left=12, top_right=12),
            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        )
        self._player_column = ft.Column(
            [self.top_bar, self.video_frame, self.controls_panel],
            spacing=0,
            expand=True,
        )
        self._player_shell = ft.Container(
            content=self._player_column,
            padding=ft.Padding.symmetric(horizontal=12, vertical=12),
            expand=True,
        )
        self.content = self._player_shell

    # ── Thread-safe UI (Flet ana döngüsü) ────────────────────────────

    def _run_on_ui(self, fn):
        """Arka plan / video callback'lerinden UI işlemini ana döngüye taşır."""
        if not self._is_alive:
            return

        async def _wrapper():
            if self._is_alive:
                fn()

        try:
            self.custom_page.run_task(_wrapper)
        except Exception:
            try:
                fn()
            except Exception:
                pass

    def _patch_controls(self, *controls):
        for ctrl in controls:
            try:
                ctrl.update()
            except RuntimeError:
                pass
            except Exception:
                pass

    def _request_progress_ui(self):
        """Konum güncellemesi: tam sayfa değil, yalnızca ilerleme kontrolleri."""
        if not self._is_alive or self.is_seeking:
            return
        now = time.monotonic()
        if now - self._last_progress_ui_at < UI_REFRESH_SEC:
            return
        self._last_progress_ui_at = now
        self._progress_ui_generation += 1
        gen = self._progress_ui_generation

        def _patch():
            if not self._is_alive or gen != self._progress_ui_generation:
                return
            self._patch_controls(
                self.seek_slider,
                self.current_time_text,
                self.total_time_text,
                self.play_pause_btn,
            )

        self._run_on_ui(_patch)

    def _request_layout_ui(self):
        """Tam ekran / kabuk değişikliklerinde bir kez layout yenile."""
        if not self._is_alive:
            return
        self._layout_dirty = True

        def _flush():
            if not self._is_alive or not self._layout_dirty:
                return
            self._layout_dirty = False
            try:
                self.update()
            except RuntimeError:
                pass
            except Exception:
                pass

        self._run_on_ui(_flush)

    def _arm_seek_guard(self):
        """Slider seek bayrağı takılırsa otomatik sıfırla."""
        self._seek_guard_generation += 1
        gen = self._seek_guard_generation

        async def _guard():
            await asyncio.sleep(SEEK_GUARD_SEC)
            if self._is_alive and gen == self._seek_guard_generation and self.is_seeking:
                self.is_seeking = False

        try:
            self.custom_page.run_task(_guard)
        except Exception:
            pass

    # ── Klavye ────────────────────────────────────────────────────────

    def _bind_keyboard(self):
        if self._keyboard_bound:
            return

        def on_key(e: ft.KeyboardEvent):
            if not self._is_alive:
                return
            key = (e.key or "").lower()
            if key == " ":
                self.toggle_play_pause(None)
            elif key in ("arrowleft", "j"):
                self.seek_relative(-SKIP_SECONDS)
            elif key in ("arrowright", "l"):
                self.seek_relative(SKIP_SECONDS)
            elif key == "arrowup":
                self._nudge_volume(10)
            elif key == "arrowdown":
                self._nudge_volume(-10)
            elif key == "f":
                self.toggle_fullscreen(None)
            elif key == "m":
                self.toggle_mute(None)
            elif key == "escape":
                if self._fullscreen_mode:
                    self.toggle_fullscreen(None)
                else:
                    self.close_player(None)

        try:
            self.custom_page.on_keyboard_event = on_key
            self._keyboard_bound = True
        except Exception:
            pass

    def _unbind_keyboard(self):
        if not self._keyboard_bound:
            return
        try:
            self.custom_page.on_keyboard_event = None
        except Exception:
            pass
        self._keyboard_bound = False

    # ── Tam ekran (YouTube tarzı: gizli, tıklama/hareketle görünür) ───

    def _layout_windowed(self):
        """Kontroller videonun altında, her zaman görünür."""
        self.video_frame.content = self.video_surface
        self._player_column.controls = [self.top_bar, self.video_frame, self.controls_panel]
        self.controls_panel.bgcolor = BG_SURFACE
        self.controls_panel.border_radius = ft.BorderRadius.only(
            bottom_left=12, bottom_right=12
        )

    def _layout_cinema(self):
        """Tam ekran: video tam alan, kontroller üst üste bindirilmiş katman."""
        cinema_stack = ft.Stack(
            [
                self._video_box,
                ft.Container(
                    content=self.top_bar,
                    top=0,
                    left=0,
                    right=0,
                    gradient=ft.LinearGradient(
                        begin=ft.Alignment(0, -1),
                        end=ft.Alignment(0, 1),
                        colors=[GRADIENT_TOP, "#00000000"],
                    ),
                ),
                ft.Container(
                    content=self.controls_panel,
                    left=0,
                    right=0,
                    bottom=0,
                    gradient=ft.LinearGradient(
                        begin=ft.Alignment(0, 1),
                        end=ft.Alignment(0, 0),
                        colors=[GRADIENT_BOTTOM, GRADIENT_TOP, "#00000000"],
                        stops=[0.0, 0.55, 1.0],
                    ),
                ),
            ],
            expand=True,
        )
        self.video_frame.content = ft.GestureDetector(
            content=cinema_stack,
            on_tap=self.on_video_tap,
            on_double_tap=self._on_video_double_click,
            on_hover=self._reveal_cinema_controls,
            on_enter=self._reveal_cinema_controls,
            hover_interval=40,
            expand=True,
            mouse_cursor=ft.MouseCursor.CLICK,
        )
        self._player_column.controls = [self.video_frame]
        self.controls_panel.bgcolor = None
        self.controls_panel.border_radius = 0

    def _set_controls_visible(self, visible: bool):
        self._controls_visible = visible
        self.controls_panel.visible = visible
        self.top_bar.visible = visible
        self._patch_controls(self.controls_panel, self.top_bar)

    def _reveal_cinema_controls(self, _e=None):
        if self._fullscreen_mode:
            self.show_controls()

    def show_controls(self):
        if not self._fullscreen_mode:
            return
        self._set_controls_visible(True)
        self.reset_hide_timer()

    def _keep_cinema_controls_awake(self):
        """Tam ekranda kontrol kullanımında otomatik gizlemeyi yeniden başlat."""
        if self._fullscreen_mode and self._controls_visible and self._playing:
            self.reset_hide_timer()

    def hide_controls(self):
        if not self._is_alive or not self._fullscreen_mode:
            return
        if self.is_seeking or not self._playing:
            return
        self._set_controls_visible(False)

    def reset_hide_timer(self):
        self._hide_generation += 1
        gen = self._hide_generation
        if not self._fullscreen_mode or not self._playing:
            return

        async def _hide_later():
            await asyncio.sleep(HIDE_CONTROLS_SEC)
            if not self._is_alive or gen != self._hide_generation:
                return
            self.hide_controls()

        try:
            self.custom_page.run_task(_hide_later)
        except Exception:
            pass

    # ── Video olayları ───────────────────────────────────────────────

    def _on_video_double_click(self, _e):
        self.toggle_fullscreen(None)

    def on_video_tap(self, _e):
        if self._fullscreen_mode:
            if not self._controls_visible:
                self.show_controls()
                return
        self.toggle_play_pause(None)

    # ── Yardımcılar ───────────────────────────────────────────────────

    def _to_ms(self, data):
        try:
            if data is None:
                return None
            if hasattr(data, "in_milliseconds"):
                val = getattr(data, "in_milliseconds")
                return int(val() if callable(val) else val)
            if hasattr(data, "total_seconds"):
                return int(data.total_seconds() * 1000)
            if isinstance(data, str):
                s = data.strip().replace(",", "")
                if not s:
                    return None
                if ":" in s:
                    parts = s.split(":")
                    if len(parts) == 3:
                        h, m, s_val = float(parts[0]), float(parts[1]), float(parts[2])
                        return int((h * 3600 + m * 60 + s_val) * 1000)
                    if len(parts) == 2:
                        m, s_val = float(parts[0]), float(parts[1])
                        return int((m * 60 + s_val) * 1000)
                val = float(s)
            else:
                val = float(data)
            if val > 10000:
                return int(val)
            return int(val * 1000)
        except Exception:
            return None

    def _call_video(self, fn, *args, **kwargs):
        try:
            res = fn(*args, **kwargs)
            if asyncio.iscoroutine(res):

                async def _run(coro):
                    try:
                        await coro
                    except Exception:
                        pass

                try:
                    self.custom_page.run_task(_run, res)
                except Exception:
                    pass
            return True
        except Exception:
            return False

    def _apply_slider_bounds(self, seconds: float) -> float:
        if self.duration_sec > 0:
            max_v = self.duration_sec
        else:
            max_v = max(float(self.seek_slider.max or 100), seconds, 1.0)
        if self.seek_slider.max != max_v:
            self.seek_slider.max = max_v
        return max(0.0, min(seconds, max_v))

    def _update_time_labels(self):
        self.current_time_text.value = format_time_display(self.current_sec)
        if self.duration_sec > 0:
            self.total_time_text.value = format_time_display(self.duration_sec)

    def _update_volume_icon(self, val: int):
        self.volume_icon.icon = (
            ft.Icons.VOLUME_MUTE_ROUNDED if val == 0 else ft.Icons.VOLUME_UP_ROUNDED
        )
        self._patch_controls(self.volume_icon)

    # ── Yaşam döngüsü ─────────────────────────────────────────────────

    def did_mount(self):
        saved_ms = load_positions(self.download_path).get(self.filepath, 0)
        if saved_ms > 0:
            self.custom_page.run_task(self._restore_position, saved_ms)

    async def _restore_position(self, saved_ms: int, attempt: int = 0):
        if not self._is_alive or attempt >= 10:
            return
        try:
            self._call_video(getattr(self.video, "seek"), saved_ms)
            self.current_sec = saved_ms / 1000
            self.seek_slider.value = self._apply_slider_bounds(self.current_sec)
            self._update_time_labels()
            self._patch_controls(self.seek_slider, self.current_time_text, self.total_time_text)
        except Exception:
            await asyncio.sleep(0.25)
            await self._restore_position(saved_ms, attempt + 1)

    def close_player(self, e=None):
        self._is_alive = False
        self._hide_generation += 1
        self._progress_ui_generation += 1
        self._seek_guard_generation += 1
        self._unbind_keyboard()
        if self._fullscreen_mode and self.custom_page.window:
            try:
                self.custom_page.window.full_screen = False
            except Exception:
                pass
        if self.video:
            try:
                save_position(self.download_path, self.filepath, int(self.current_sec * 1000))
                self._call_video(getattr(self.video, "stop"))
            except Exception:
                pass
        self.on_close_callback()

    # ── Kontroller ────────────────────────────────────────────────────

    def toggle_play_pause(self, e):
        try:
            if self._playing:
                if hasattr(self.video, "pause"):
                    self._call_video(self.video.pause)
                else:
                    self.video.playing = False
                self.play_pause_btn.icon = ft.Icons.PLAY_ARROW_ROUNDED
                self._playing = False
                save_position(self.download_path, self.filepath, int(self.current_sec * 1000))
            else:
                if hasattr(self.video, "play"):
                    self._call_video(self.video.play)
                else:
                    self.video.playing = True
                self.play_pause_btn.icon = ft.Icons.PAUSE_ROUNDED
                self._playing = True
        except Exception:
            pass
        self._patch_controls(self.play_pause_btn)
        if self._fullscreen_mode:
            if self._playing:
                self.reset_hide_timer()
            else:
                self.show_controls()

    def toggle_mute(self, e):
        self._keep_cinema_controls_awake()
        if self.video.volume > 0:
            self.volume_before_mute = int(self.volume_slider.value or 100)
            self.video.volume = 0
            self.volume_slider.value = 0
        else:
            self.video.volume = self.volume_before_mute
            self.volume_slider.value = self.volume_before_mute
        self._update_volume_icon(int(self.volume_slider.value or 0))
        self._patch_controls(self.volume_slider)

    def on_volume_change(self, e):
        val = int(e.control.value)
        self.video.volume = val
        self._update_volume_icon(val)

    def cycle_speed(self, e):
        self._keep_cinema_controls_awake()
        current = float(getattr(self.video, "playback_rate", 1.0) or 1.0)
        try:
            idx = SPEEDS.index(current)
        except ValueError:
            idx = SPEEDS.index(1.0)
        self.set_playback_rate(SPEEDS[(idx + 1) % len(SPEEDS)])

    def set_playback_rate(self, rate: float):
        try:
            self.video.playback_rate = rate
        except Exception:
            pass
        self.speed_label.value = f"{rate:g}×"
        self._patch_controls(self.speed_label)

    def seek_relative(self, delta_seconds: int):
        self._keep_cinema_controls_awake()
        target = self.current_sec + delta_seconds
        if self.duration_sec > 0:
            target = max(0.0, min(target, self.duration_sec))
        else:
            target = max(0.0, target)
        self._seek_to(target)

    def _seek_to(self, seconds: float):
        seconds = self._apply_slider_bounds(seconds)
        target_ms = int(seconds * 1000)
        self._call_video(getattr(self.video, "seek"), target_ms)
        self.current_sec = seconds
        self.seek_slider.value = seconds
        self._update_time_labels()
        save_position(self.download_path, self.filepath, target_ms)
        self._patch_controls(self.seek_slider, self.current_time_text)

    def on_slider_change(self, e):
        if not self.is_seeking:
            return
        self.current_time_text.value = format_time_display(float(e.control.value))
        self._patch_controls(self.current_time_text)

    def on_slider_seek_start(self, e):
        self.is_seeking = True
        self._arm_seek_guard()
        if self._fullscreen_mode:
            self.show_controls()

    def on_slider_seek_end(self, e):
        try:
            self._seek_to(float(e.control.value))
        finally:
            self.is_seeking = False
            self._seek_guard_generation += 1

    def toggle_fullscreen(self, e):
        self._fullscreen_mode = not self._fullscreen_mode
        if self.custom_page.window:
            try:
                self.custom_page.window.full_screen = self._fullscreen_mode
            except Exception:
                pass

        shell = self._player_shell
        video_wrap = self.video_frame

        if self._fullscreen_mode:
            shell.padding = 0
            video_wrap.border_radius = 0
            video_wrap.border = ft.Border.all(0, "#00000000")
            self.fullscreen_btn.icon = ft.Icons.FULLSCREEN_EXIT_ROUNDED
            self._layout_cinema()
            self._hide_generation += 1
            self._set_controls_visible(False)
        else:
            shell.padding = ft.Padding.symmetric(horizontal=12, vertical=12)
            video_wrap.border_radius = ft.BorderRadius.only(top_left=12, top_right=12)
            video_wrap.border = ft.Border.all(1, BORDER)
            self.fullscreen_btn.icon = ft.Icons.FULLSCREEN_ROUNDED
            self._hide_generation += 1
            self._layout_windowed()
            self._set_controls_visible(True)

        self._patch_controls(self.fullscreen_btn)
        self._request_layout_ui()

    def on_position_change(self, e):
        if not self._is_alive or self.is_seeking:
            return
        try:
            pos_ms = self._to_ms(e.data)
            if pos_ms is None:
                return
            self.current_sec = pos_ms / 1000
            self.seek_slider.value = self._apply_slider_bounds(self.current_sec)
            self._update_time_labels()
            if self._playing:
                self.play_pause_btn.icon = ft.Icons.PAUSE_ROUNDED

            if abs(self.current_sec - self.last_saved_sec) >= 3.0:
                save_position(self.download_path, self.filepath, int(self.current_sec * 1000))
                self.last_saved_sec = self.current_sec

            self._request_progress_ui()
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
            self.seek_slider.max = max(self.duration_sec, 1)
            self.total_time_text.value = format_time_display(self.duration_sec)

            def _patch():
                self._patch_controls(self.seek_slider, self.total_time_text)

            self._run_on_ui(_patch)
        except Exception:
            pass

    def on_video_complete(self, e):
        if not self._is_alive:
            return
        try:
            self._call_video(getattr(self.video, "seek"), 0)
            self._call_video(getattr(self.video, "pause"))
        except Exception:
            pass
        self.play_pause_btn.icon = ft.Icons.PLAY_ARROW_ROUNDED
        self._playing = False
        self.current_sec = 0.0
        self.seek_slider.value = 0.0
        self._update_time_labels()
        save_position(self.download_path, self.filepath, 0)

        def _patch():
            self._patch_controls(
                self.play_pause_btn, self.seek_slider, self.current_time_text
            )

        self._run_on_ui(_patch)

    def _nudge_volume(self, delta: int):
        val = max(0, min(100, int(self.volume_slider.value or 0) + delta))
        self.volume_slider.value = val
        self.video.volume = val
        self._update_volume_icon(val)
        self._patch_controls(self.volume_slider)
