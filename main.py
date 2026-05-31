import flet as ft
import os
from pathlib import Path
from search_engine import search_youtube, get_channel_info, format_number
from downloader import start_download
from player import CustomVideoPlayer

# ── Renk Paleti (Sade & Modern YouTube Koyu Teması) ─────────────────
BG_DEEP    = "#0F0F0F" # Gerçek siyah arkaplan
BG_SURFACE = "#1F1F1F" # Kartlar ve ikincil zeminler
BG_CARD    = "#282828" # Hover ve odak durumları
BORDER     = "#2C2C2C" # İnce ayırıcı çizgiler
PRIMARY    = "#FF0000" # YouTube Kırmızısı (Aksan Rengi)
TEXT_PRI   = "#FFFFFF" # Ana beyaz başlıklar
TEXT_SEC   = "#AAAAAA" # İkincil gri metinler
TEXT_DIM   = "#717171" # Çok silik metinler
COLOR_SUCCESS = "#2BA640" # Başarılı durumlar için yeşil
COLOR_ERROR   = "#FF4D4D" # Hatalı durumlar için kırmızı

async def main(page: ft.Page):
    page.title = "Vault - Video Arşivi"
    page.bgcolor = BG_DEEP
    page.padding = 0
    
    # Google Fonts Inter Entegrasyonu
    page.fonts = {
        "Inter": "https://github.com/google/fonts/raw/main/ofl/inter/Inter%5Bslnt%2Cwght%5D.ttf"
    }
    page.theme = ft.Theme(font_family="Inter")

    # Mobil platform kontrolü
    _mobile: bool = page.platform in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS) if page.platform else False

    if not _mobile:
        page.window.width = 440
        page.window.height = 840
        page.window.resizable = False

    # İndirme Klasörü Konfigürasyonu
    if _mobile:
        try:
            sp = ft.StoragePaths()
            docs_dir = await sp.get_application_documents_directory()
            download_path = str(Path(docs_dir) / "Vault" / "videos")
        except Exception:
            download_path = str(Path.home() / "Vault" / "videos")
    else:
        download_path = str(Path.home() / "Vault" / "videos")

    try:
        os.makedirs(download_path, exist_ok=True)
    except OSError:
        import tempfile
        download_path = str(Path(tempfile.gettempdir()) / "Vault" / "videos")
        os.makedirs(download_path, exist_ok=True)

    # ── Yardımcı Fonksiyonlar ─────────────────────────────────────────
    def show_snack(msg: str, color: str = PRIMARY):
        sb = ft.SnackBar(
            content=ft.Text(msg, color=TEXT_PRI, weight=ft.FontWeight.W_500, size=13),
            bgcolor=color,
            duration=3000,
            open=True,
        )
        page.overlay.append(sb)
        page.update()

    def on_page_error(e):
        show_snack(f"Sistem Hatası: {e.data[:150]}", COLOR_ERROR)

    page.on_error = on_page_error

    # ── State Değişkenleri ────────────────────────────────────────────
    # Arama Filtreleri State
    selected_type = "video"
    selected_date = "any"
    selected_sort = "relevance"
    
    # Kanal Detay State
    current_channel_data = {}
    channel_loaded_videos = []
    channel_video_cursor = 0
    channel_sort_by = "latest"

    # ── UI Kontrolleri ve Ref'ler ─────────────────────────────────────
    results_column = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)
    active_downloads_col = ft.Column(spacing=8)
    library_column = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO, expand=True)
    
    search_progress = ft.ProgressBar(color=PRIMARY, bgcolor=BORDER, value=0, visible=False)
    
    # Arama Girdisi
    search_input = ft.TextField(
        hint_text="Video adı, kanal veya link girin...",
        hint_style=ft.TextStyle(color=TEXT_DIM, size=13),
        text_style=ft.TextStyle(color=TEXT_PRI, size=13),
        border=ft.InputBorder.NONE,
        bgcolor="transparent",
        expand=True,
        cursor_color=PRIMARY,
        content_padding=ft.Padding.only(left=12, top=10, right=12, bottom=10),
    )

    # Ekran Overlay Katmanları (Video Oynatıcı ve Kanal Sayfası)
    player_overlay = ft.Container(visible=False, expand=True, bgcolor=BG_DEEP)
    channel_overlay = ft.Container(visible=False, expand=True, bgcolor=BG_DEEP)
    
    # ── KÜTÜPHANE LİSTELEME VE YENİLEME ───────────────────────────────
    def refresh_library(e=None):
        library_column.controls.clear()
        if os.path.exists(download_path):
            try:
                files = [
                    f for f in os.listdir(download_path)
                    if f.endswith((".mp4", ".mkv", ".webm"))
                ]
                if files:
                    for f in sorted(files):
                        library_column.controls.append(
                            build_library_card(f, os.path.join(download_path, f))
                        )
                else:
                    library_column.controls.append(
                        ft.Container(
                            content=ft.Column(
                                [
                                    ft.Icon(ft.Icons.VIDEO_LIBRARY_OUTLINED, color=TEXT_DIM, size=44),
                                    ft.Text("Kütüphane Boş", size=13, color=TEXT_SEC, weight=ft.FontWeight.W_600),
                                    ft.Text("İndirilen videolar burada listelenir.", size=11, color=TEXT_DIM),
                                ],
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                spacing=6,
                            ),
                            alignment=ft.Alignment.CENTER,
                            padding=ft.Padding.symmetric(vertical=80),
                        )
                    )
            except Exception as ex:
                library_column.controls.append(
                    ft.Text(f"Kütüphane listelenirken hata oluştu: {ex}", color=COLOR_ERROR, size=11)
                )
        page.update()

    # ── ARAMA KARTLARI YAPICILARI ─────────────────────────────────────
    def on_download_click(url, title):
        start_download(
            page=page,
            url=url,
            title=title,
            download_path=download_path,
            active_downloads_col=active_downloads_col,
            refresh_library_callback=refresh_library,
            show_snack_callback=show_snack,
            is_mobile=_mobile
        )
        # İndirme sekmesini görünür kılmak için İndirilenler sayfasına geçiş yapılabilir
        # Veya sadece snack bar bildirimi ile aktif indirmeler takip edilir

    def build_result_card(item: dict) -> ft.Container:
        """Homojen ve şık arama sonuç kartları tasarlar."""
        # Kart Tipi Belirleme (Kanal, Video, Playlist)
        if item["type"] == "channel":
            # Kanal Kartı Tasarımı
            avatar_src = item["avatar"] or "https://yt3.googleusercontent.com/default"
            verified_badge = ft.Icon(ft.Icons.VERIFIED_ROUNDED, color="#3EA6FF", size=14) if item["is_verified"] else ft.Container()
            
            return ft.Container(
                content=ft.Row(
                    [
                        ft.Container(
                            content=ft.Image(src=avatar_src, width=54, height=54, border_radius=27, fit=ft.BoxFit.COVER),
                            width=54, height=54,
                        ),
                        ft.Column(
                            [
                                ft.Row([
                                    ft.Text(item["title"][:36] + ("..." if len(item["title"]) > 36 else ""), size=13, color=TEXT_PRI, weight=ft.FontWeight.W_600),
                                    verified_badge
                                ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                                ft.Text(f"{item['subscribers']} abone", size=11, color=TEXT_SEC),
                                ft.Text(item["description"][:64] + ("..." if len(item["description"]) > 64 else ""), size=10, color=TEXT_DIM),
                            ],
                            expand=True,
                            spacing=3,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.ARROW_FORWARD_IOS_ROUNDED,
                            icon_color=TEXT_SEC,
                            icon_size=16,
                            on_click=lambda _: open_channel_page(item["url"])
                        )
                    ],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                border_radius=10,
                bgcolor=BG_SURFACE,
                border=ft.Border.all(1, BORDER),
                on_click=lambda _: open_channel_page(item["url"])
            )
            
        elif item["type"] == "playlist":
            # Oynatma Listesi Kartı Tasarımı
            return ft.Container(
                content=ft.Row(
                    [
                        ft.Container(
                            content=ft.Icon(ft.Icons.PLAYLIST_PLAY_ROUNDED, color=PRIMARY, size=24),
                            width=50, height=50,
                            border_radius=8,
                            bgcolor="#1E0E0E",
                            border=ft.Border.all(1, "#3A1A1A"),
                            alignment=ft.Alignment.CENTER,
                        ),
                        ft.Column(
                            [
                                ft.Text(item["title"][:48] + ("..." if len(item["title"]) > 48 else ""), size=12, color=TEXT_PRI, weight=ft.FontWeight.W_500),
                                ft.Text(f"{item['uploader']} · {item['video_count']} video", size=10, color=TEXT_SEC),
                            ],
                            expand=True,
                            spacing=4,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DOWNLOAD_ROUNDED,
                            icon_color=PRIMARY,
                            icon_size=20,
                            tooltip="Listeyi İndir",
                            on_click=lambda _: on_download_click(item["url"], item["title"])
                        ),
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                border_radius=10,
                bgcolor=BG_SURFACE,
                border=ft.Border.all(1, BORDER),
            )
            
        else:
            # Standart Video Kartı Tasarımı
            return ft.Container(
                content=ft.Row(
                    [
                        ft.Container(
                            content=ft.Column(
                                [
                                    ft.Icon(ft.Icons.PLAY_ARROW_ROUNDED, color=PRIMARY, size=22),
                                    ft.Text(item["duration"], size=9, color=TEXT_PRI, weight=ft.FontWeight.W_600),
                                ],
                                spacing=1,
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            width=50, height=50,
                            border_radius=8,
                            bgcolor="#1E0E0E",
                            border=ft.Border.all(1, "#3A1A1A"),
                            alignment=ft.Alignment.CENTER,
                        ),
                        ft.Column(
                            [
                                ft.Text(item["title"][:48] + ("..." if len(item["title"]) > 48 else ""), size=12, color=TEXT_PRI, weight=ft.FontWeight.W_500),
                                ft.Text(item["uploader"][:32], size=10, color=TEXT_SEC),
                            ],
                            expand=True,
                            spacing=4,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DOWNLOAD_ROUNDED,
                            icon_color=PRIMARY,
                            icon_size=20,
                            tooltip="İndir",
                            on_click=lambda _: on_download_click(item["url"], item["title"])
                        ),
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                border_radius=10,
                bgcolor=BG_SURFACE,
                border=ft.Border.all(1, BORDER),
            )

    # ── ARAMA ÇALIŞTIRMA MANTIĞI ──────────────────────────────────────
    def run_search(e=None):
        query = search_input.value.strip()
        if not query:
            return
            
        results_column.controls.clear()
        search_progress.visible = True
        search_progress.value = None
        page.update()

        def _search_thread():
            try:
                results = search_youtube(
                    query=query,
                    type_filter=selected_type,
                    date_filter=selected_date,
                    sort_filter=selected_sort
                )
                
                if not results:
                    results_column.controls.append(
                        ft.Container(
                            content=ft.Text("Sonuç bulunamadı.", color=TEXT_SEC, size=13),
                            padding=ft.Padding.symmetric(vertical=40),
                            alignment=ft.Alignment.CENTER
                        )
                    )
                else:
                    for item in results:
                        results_column.controls.append(build_result_card(item))
            except Exception as ex:
                results_column.controls.append(
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, color=COLOR_ERROR, size=28),
                                ft.Text("Arama Başarısız", size=13, color=COLOR_ERROR, weight=ft.FontWeight.W_600),
                                ft.Text(str(ex), size=11, color=TEXT_SEC, max_lines=4),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=6
                        ),
                        padding=ft.Padding.symmetric(vertical=30),
                        alignment=ft.Alignment.CENTER
                    )
                )
            finally:
                search_progress.visible = False
                search_progress.value = 0
                page.update()

        # Thread-safe arka plan araması başlat
        page.run_thread(_search_thread)

    search_input.on_submit = run_search

    # ── KANAL DETAY SAYFASI ───────────────────────────────────────────
    channel_content_column = ft.Column(spacing=0, scroll=ft.ScrollMode.AUTO, expand=True)

    def close_channel_page(e=None):
        channel_overlay.visible = False
        channel_content_column.controls.clear()
        page.update()

    def open_channel_page(channel_url: str):
        nonlocal current_channel_data, channel_loaded_videos, channel_video_cursor, channel_sort_by
        
        channel_overlay.visible = True
        channel_overlay.content = ft.Container(
            content=ft.Row(
                [
                    ft.ProgressRing(color=PRIMARY),
                    ft.Text("Kanal bilgileri yükleniyor...", size=13, color=TEXT_PRI)
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=12
            ),
            alignment=ft.Alignment.CENTER,
            bgcolor=BG_DEEP
        )
        page.update()
        
        channel_sort_by = "latest" # Varsayılan olarak en son yüklenenler
        
        def _load_channel_thread():
            nonlocal current_channel_data, channel_loaded_videos, channel_video_cursor
            try:
                data = get_channel_info(channel_url, sort_by=channel_sort_by)
                current_channel_data = data
                channel_loaded_videos = data.get("videos", [])
                channel_video_cursor = 0
                
                # UI Oluştur
                build_channel_page_ui()
            except Exception as ex:
                channel_overlay.content = ft.Container(
                    content=ft.Column(
                        [
                            ft.Icon(ft.Icons.ERROR_OUTLINE_ROUNDED, color=COLOR_ERROR, size=32),
                            ft.Text("Kanal Yüklenemedi", size=14, color=COLOR_ERROR, weight=ft.FontWeight.W_600),
                            ft.Text(str(ex), size=11, color=TEXT_SEC, max_lines=4),
                            ft.ElevatedButton("Geri Dön", on_click=close_channel_page, style=ft.ButtonStyle(color=TEXT_PRI, bgcolor=PRIMARY))
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=12,
                        alignment=ft.MainAxisAlignment.CENTER
                    ),
                    bgcolor=BG_DEEP
                )
                page.update()
                
        page.run_thread(_load_channel_thread)

    def change_channel_sorting(sort_type: str):
        nonlocal channel_sort_by
        if channel_sort_by == sort_type:
            return
        channel_sort_by = sort_type
        
        # Yeniden yükleniyor göstergesi
        channel_content_column.controls.clear()
        channel_content_column.controls.append(
            ft.Container(
                content=ft.ProgressRing(color=PRIMARY),
                alignment=ft.Alignment.CENTER,
                padding=ft.Padding.symmetric(vertical=40)
            )
        )
        page.update()
        
        def _reload_channel_thread():
            nonlocal current_channel_data, channel_loaded_videos, channel_video_cursor
            try:
                data = get_channel_info(current_channel_data["url"], sort_by=channel_sort_by)
                channel_loaded_videos = data.get("videos", [])
                channel_video_cursor = 0
                build_channel_page_ui()
            except Exception as ex:
                show_snack(f"Sıralama değiştirilemedi: {ex}", COLOR_ERROR)
                build_channel_page_ui()
                
        page.run_thread(_reload_channel_thread)

    def load_more_channel_videos(e=None):
        nonlocal channel_video_cursor
        
        # Kaldır eski butonu
        if channel_content_column.controls and isinstance(channel_content_column.controls[-1], ft.Container) and "Daha Fazla" in getattr(channel_content_column.controls[-1].content, "text", ""):
            channel_content_column.controls.pop()
            
        start = channel_video_cursor
        end = min(start + 10, len(channel_loaded_videos))
        
        if start >= len(channel_loaded_videos):
            return
            
        for i in range(start, end):
            video_item = channel_loaded_videos[i]
            
            # Kanal video listesi kartı
            card = ft.Container(
                content=ft.Row(
                    [
                        ft.Container(
                            content=ft.Column(
                                [
                                    ft.Icon(ft.Icons.PLAY_ARROW_ROUNDED, color=PRIMARY, size=18),
                                    ft.Text(video_item["duration"], size=8, color=TEXT_PRI),
                                ],
                                spacing=0,
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                            width=44, height=44,
                            border_radius=6,
                            bgcolor="#1E0E0E",
                            border=ft.Border.all(1, "#3A1A1A"),
                            alignment=ft.Alignment.CENTER,
                        ),
                        ft.Column(
                            [
                                ft.Text(video_item["title"][:50] + ("..." if len(video_item["title"]) > 50 else ""), size=12, color=TEXT_PRI, weight=ft.FontWeight.W_500),
                                ft.Text(video_item["uploader"], size=10, color=TEXT_SEC),
                            ],
                            expand=True,
                            spacing=3,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DOWNLOAD_ROUNDED,
                            icon_color=PRIMARY,
                            icon_size=18,
                            on_click=lambda _, u=video_item["url"], t=video_item["title"]: on_download_click(u, t)
                        )
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                ),
                padding=ft.Padding.symmetric(horizontal=12, vertical=8),
                border_radius=8,
                bgcolor=BG_SURFACE,
                border=ft.Border.all(1, BORDER),
                margin=ft.Margin.only(bottom=8)
            )
            channel_content_column.controls.append(card)
            
        channel_video_cursor = end
        
        # Eğer daha fazla video varsa "Daha Fazla Göster" butonu ekle
        if channel_video_cursor < len(channel_loaded_videos):
            load_more_btn = ft.Container(
                content=ft.TextButton(
                    "Daha Fazla Video Yükle",
                    icon=ft.Icons.ADD_ROUNDED,
                    icon_color=PRIMARY,
                    on_click=load_more_channel_videos,
                    style=ft.ButtonStyle(color=TEXT_PRI)
                ),
                alignment=ft.Alignment.CENTER,
                padding=ft.Padding.symmetric(vertical=12)
            )
            channel_content_column.controls.append(load_more_btn)
            
        page.update()

    def build_channel_page_ui():
        channel_content_column.controls.clear()
        
        # Banner görseli
        banner_container = ft.Container(height=110, bgcolor="#18181D")
        if current_channel_data.get("banner"):
            banner_container.content = ft.Image(src=current_channel_data["banner"], fit=ft.BoxFit.COVER, height=110)
        else:
            # Banner yoksa sade renk ve başlık
            banner_container.content = ft.Container(
                content=ft.Text(current_channel_data["name"].upper(), size=22, weight=ft.FontWeight.W_800, color=BORDER, style=ft.TextStyle(letter_spacing=4)),
                alignment=ft.Alignment.CENTER,
                bgcolor="#18181D"
            )
            
        # Avatar Görseli
        avatar_src = current_channel_data["avatar"] or "https://yt3.googleusercontent.com/default"
        avatar_control = ft.Container(
            content=ft.Image(src=avatar_src, width=64, height=64, border_radius=32, fit=ft.BoxFit.COVER),
            width=68, height=68,
            border_radius=34,
            border=ft.Border.all(2, BG_DEEP),
            margin=ft.Margin.only(top=-34, left=16)
        )
        
        # Kanal Bilgileri Panel
        info_panel = ft.Container(
            content=ft.Column(
                [
                    ft.Text(current_channel_data["name"], size=16, color=TEXT_PRI, weight=ft.FontWeight.W_700),
                    ft.Row(
                        [
                            ft.Text(f"{current_channel_data['subscribers']} abone", size=12, color=TEXT_SEC, weight=ft.FontWeight.W_500),
                            ft.Text("·", size=12, color=TEXT_DIM),
                            ft.Text(f"{current_channel_data['video_count']} video", size=12, color=TEXT_SEC, weight=ft.FontWeight.W_500),
                        ],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER
                    ),
                    ft.Text(
                        current_channel_data["description"][:140] + ("..." if len(current_channel_data["description"]) > 140 else ""),
                        size=11, color=TEXT_DIM,
                        max_lines=3
                    )
                ],
                spacing=4
            ),
            padding=ft.Padding.only(left=16, top=8, right=16, bottom=12)
        )
        
        # Sıralama Çipleri (Son Yüklenenler / Popüler)
        latest_chip_border = ft.Border.all(1.5, PRIMARY) if channel_sort_by == "latest" else ft.Border.all(1, BORDER)
        latest_chip_bg = "#1A0000" if channel_sort_by == "latest" else "transparent"
        latest_chip_color = PRIMARY if channel_sort_by == "latest" else TEXT_SEC
        
        popular_chip_border = ft.Border.all(1.5, PRIMARY) if channel_sort_by == "popular" else ft.Border.all(1, BORDER)
        popular_chip_bg = "#1A0000" if channel_sort_by == "popular" else "transparent"
        popular_chip_color = PRIMARY if channel_sort_by == "popular" else TEXT_SEC

        sorting_row = ft.Container(
            content=ft.Row(
                [
                    ft.GestureDetector(
                        on_tap=lambda _: change_channel_sorting("latest"),
                        content=ft.Container(
                            content=ft.Text("En Son Yüklenenler", size=11, color=latest_chip_color, weight=ft.FontWeight.W_600),
                            padding=ft.Padding.symmetric(horizontal=14, vertical=6),
                            border_radius=16,
                            bgcolor=latest_chip_bg,
                            border=latest_chip_border
                        )
                    ),
                    ft.GestureDetector(
                        on_tap=lambda _: change_channel_sorting("popular"),
                        content=ft.Container(
                            content=ft.Text("En Popüler", size=11, color=popular_chip_color, weight=ft.FontWeight.W_600),
                            padding=ft.Padding.symmetric(horizontal=14, vertical=6),
                            border_radius=16,
                            bgcolor=popular_chip_bg,
                            border=popular_chip_border
                        )
                    )
                ],
                spacing=8
            ),
            padding=ft.Padding.only(left=16, top=6, right=16, bottom=14)
        )
        
        # Ana Katmana Birleştirme
        channel_content_column.controls.extend([
            banner_container,
            avatar_control,
            info_panel,
            ft.Container(height=1, bgcolor=BORDER, margin=ft.Margin.symmetric(horizontal=16, vertical=4)),
            sorting_row,
            ft.Container(height=8)
        ])
        
        # Videoları parça parça eklemeyi başlat (ilk 10 video)
        load_more_channel_videos()
        
        # Geri butonu içeren başlığı overlay katmanına yerleştir
        channel_overlay.content = ft.Column(
            [
                ft.Container(
                    content=ft.Row(
                        [
                            ft.IconButton(ft.Icons.ARROW_BACK_ROUNDED, icon_color=TEXT_PRI, on_click=close_channel_page),
                            ft.Text("Kanal Sayfası", size=14, color=TEXT_PRI, weight=ft.FontWeight.W_600),
                        ],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER
                    ),
                    bgcolor=BG_DEEP,
                    padding=ft.Padding.symmetric(horizontal=8, vertical=4)
                ),
                channel_content_column
            ],
            spacing=0,
            expand=True
        )
        page.update()

    # ── KÜTÜPHANE KARTLARI BİLEŞENİ ───────────────────────────────────
    def play_downloaded_video(filepath: str):
        """Uygulama içi özel video oynatıcıyı açar."""
        player_overlay.visible = True
        player_overlay.content = CustomVideoPlayer(
            page=page,
            filepath=filepath,
            download_path=download_path,
            on_close=close_video_player
        )
        page.update()

    def close_video_player():
        player_overlay.visible = False
        player_overlay.content = ft.Container()
        page.update()  # Video widget'ını DOM'dan kaldır, sonra kütüphaneyi yenile
        refresh_library()

    def build_library_card(filename: str, filepath: str) -> ft.Container:
        display_name = filename
        for ext in (".mp4", ".mkv", ".webm"):
            display_name = display_name.replace(ext, "")
        display_name = display_name[:44] + ("…" if len(display_name) > 44 else "")

        try:
            size_bytes = os.path.getsize(filepath)
            size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
        except Exception:
            size_str = "— MB"

        def delete_file(e):
            try:
                os.remove(filepath)
                show_snack("Video kütüphaneden silindi.", PRIMARY)
                refresh_library()
            except Exception as ex:
                show_snack(f"Silinemedi: {ex}", COLOR_ERROR)

        return ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        content=ft.Icon(ft.Icons.VIDEO_FILE_ROUNDED, color=PRIMARY, size=22),
                        width=46, height=46,
                        border_radius=8,
                        bgcolor="#1E0E0E",
                        border=ft.Border.all(1, "#3A1A1A"),
                        alignment=ft.Alignment.CENTER,
                    ),
                    ft.Column(
                        [
                            ft.Text(display_name, size=12, color=TEXT_PRI, weight=ft.FontWeight.W_500, max_lines=2),
                            ft.Text(size_str, size=10, color=TEXT_DIM),
                        ],
                        expand=True,
                        spacing=3,
                    ),
                    ft.Row(
                        [
                            ft.IconButton(
                                icon=ft.Icons.PLAY_ARROW_ROUNDED,
                                icon_color=COLOR_SUCCESS,
                                icon_size=20,
                                tooltip="Oynat",
                                on_click=lambda _: play_downloaded_video(filepath),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                                icon_color=TEXT_DIM,
                                icon_size=18,
                                tooltip="Sil",
                                on_click=delete_file,
                            ),
                        ],
                        spacing=0,
                    ),
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
            border_radius=10,
            bgcolor=BG_SURFACE,
            border=ft.Border.all(1, BORDER),
            on_click=lambda _: play_downloaded_video(filepath)
        )

    # ── ARAMA TABİ GELİŞMİŞ FİLTRELER BÖLÜMÜ ─────────────────────────
    # Çip seçim işleyicileri
    filter_panel_visible = False
    
    filter_icon = ft.IconButton(
        icon=ft.Icons.TUNE_ROUNDED,
        icon_color=TEXT_SEC,
        icon_size=20,
        tooltip="Filtreler",
    )

    filter_drawer = ft.Container(
        visible=False,
        bgcolor=BG_SURFACE,
        border_radius=12,
        border=ft.Border.all(1, BORDER),
        padding=14,
        margin=ft.Margin.only(bottom=10)
    )

    def toggle_filter_panel(e):
        nonlocal filter_panel_visible
        filter_panel_visible = not filter_panel_visible
        filter_drawer.visible = filter_panel_visible
        filter_icon.icon_color = PRIMARY if filter_panel_visible else TEXT_SEC
        page.update()
        
    filter_icon.on_click = toggle_filter_panel

    # Filtre Değişim İşleyicileri (Custom styled clickable containers)
    def update_type_filter(val):
        nonlocal selected_type
        selected_type = val
        build_filter_drawer_content()
        page.update()
        
    def update_date_filter(val):
        nonlocal selected_date
        selected_date = val
        build_filter_drawer_content()
        page.update()
        
    def update_sort_filter(val):
        nonlocal selected_sort
        selected_sort = val
        build_filter_drawer_content()
        page.update()

    def build_filter_drawer_content():
        # Filtre Seçenekleri Satırları
        type_row = ft.Row([ft.Text("Tip:", size=11, color=TEXT_DIM, width=50)], spacing=6)
        types = [("video", "Video"), ("channel", "Kanal"), ("playlist", "Oynatma Listesi"), ("shorts", "Shorts")]
        for k, v in types:
            is_sel = selected_type == k
            type_row.controls.append(
                ft.GestureDetector(
                    on_tap=lambda _, key=k: update_type_filter(key),
                    content=ft.Container(
                        content=ft.Text(v, size=10, color=PRIMARY if is_sel else TEXT_SEC, weight=ft.FontWeight.W_600),
                        bgcolor="#1A0000" if is_sel else "transparent",
                        border=ft.Border.all(1, PRIMARY if is_sel else BORDER),
                        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                        border_radius=12
                    )
                )
            )
            
        date_row = ft.Row([ft.Text("Tarih:", size=11, color=TEXT_DIM, width=50)], spacing=6)
        dates = [("any", "Her Zaman"), ("today", "Son 24s"), ("week", "Son Hafta"), ("month", "Son Ay"), ("year", "Son Yıl")]
        # Tarih filtreleri sadece Video tipi aktifken anlamlıdır
        date_disabled = selected_type not in ("video", "shorts")
        for k, v in dates:
            is_sel = selected_date == k and not date_disabled
            date_row.controls.append(
                ft.GestureDetector(
                    on_tap=lambda _, key=k: (None if date_disabled else update_date_filter(key)),
                    content=ft.Container(
                        content=ft.Text(v, size=10, color=PRIMARY if is_sel else (TEXT_DIM if date_disabled else TEXT_SEC), weight=ft.FontWeight.W_600),
                        bgcolor="#1A0000" if is_sel else "transparent",
                        border=ft.Border.all(1, PRIMARY if is_sel else BORDER),
                        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                        border_radius=12,
                        opacity=0.4 if date_disabled else 1.0
                    )
                )
            )
            
        sort_row = ft.Row([ft.Text("Sırala:", size=11, color=TEXT_DIM, width=50)], spacing=6)
        sorts = [("relevance", "Alaka"), ("date", "Tarih"), ("views", "İzlenme"), ("likes", "Beğeni")]
        for k, v in sorts:
            is_sel = selected_sort == k
            sort_row.controls.append(
                ft.GestureDetector(
                    on_tap=lambda _, key=k: update_sort_filter(key),
                    content=ft.Container(
                        content=ft.Text(v, size=10, color=PRIMARY if is_sel else TEXT_SEC, weight=ft.FontWeight.W_600),
                        bgcolor="#1A0000" if is_sel else "transparent",
                        border=ft.Border.all(1, PRIMARY if is_sel else BORDER),
                        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                        border_radius=12
                    )
                )
            )
            
        filter_drawer.content = ft.Column(
            [type_row, date_row, sort_row],
            spacing=8
        )

    # İlk filtre çekmecesini oluştur
    build_filter_drawer_content()

    # ── ANA VIEW YAPILANDIRMASI ───────────────────────────────────────
    search_field_container = ft.Container(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.SEARCH_ROUNDED, color=PRIMARY, size=18),
                search_input,
                filter_icon,
            ],
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding.symmetric(horizontal=10, vertical=2),
        border_radius=20,
        bgcolor=BG_SURFACE,
        border=ft.Border.all(1, BORDER),
        margin=ft.Margin.only(bottom=8),
    )

    search_view_container = ft.Container(
        content=ft.Column(
            [search_field_container, filter_drawer, search_progress, results_column],
            spacing=0,
            expand=True,
        ),
        expand=True,
        visible=True,
    )

    library_view_container = ft.Container(
        content=ft.Column(
            [
                # Aktif İndirmeler Bölümü (Varsa Göster)
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.DOWNLOAD_ROUNDED, color=PRIMARY, size=12),
                                    ft.Text("AKTİF İNDİRMELER", size=10, color=TEXT_SEC, style=ft.TextStyle(letter_spacing=1.5), weight=ft.FontWeight.W_600),
                                ],
                                spacing=6,
                            ),
                            active_downloads_col,
                        ],
                        spacing=6,
                    ),
                    padding=ft.Padding.only(bottom=10),
                ),
                ft.Container(height=1, bgcolor=BORDER, margin=ft.Margin.only(bottom=8)),
                # Kütüphanedeki İndirilen Videolar
                ft.Row(
                    [
                        ft.Row(
                            [
                                ft.Icon(ft.Icons.VIDEO_LIBRARY_ROUNDED, color=PRIMARY, size=12),
                                ft.Text("KASADAKİ VİDEOLAR", size=10, color=TEXT_SEC, style=ft.TextStyle(letter_spacing=1.5), weight=ft.FontWeight.W_600),
                            ],
                            spacing=6,
                        ),
                        ft.TextButton(
                            "Yenile",
                            on_click=refresh_library,
                            style=ft.ButtonStyle(color=TEXT_SEC),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                library_column,
            ],
            spacing=0,
            expand=True,
        ),
        expand=True,
        visible=False,
    )

    # ── SAYFA DÜZENİ VE TABS GEÇİŞİ ───────────────────────────────────
    _top_header = 14 if _mobile else 40

    header = ft.Container(
        content=ft.Row(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.LOCK_ROUNDED, color=PRIMARY, size=18),
                        ft.Text(
                            "VAULT",
                            size=18,
                            weight=ft.FontWeight.W_800,
                            color=TEXT_PRI,
                            style=ft.TextStyle(letter_spacing=5),
                        ),
                    ],
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                ),
                ft.IconButton(
                    icon=ft.Icons.SETTINGS_OUTLINED,
                    icon_color=TEXT_SEC,
                    icon_size=18,
                    on_click=lambda _: (
                        page.overlay.append(dlg := ft.AlertDialog(
                            title=ft.Text("Depolama Yolu", size=14, color=TEXT_PRI, weight=ft.FontWeight.W_600),
                            content=ft.Text(download_path, size=11, color=TEXT_SEC),
                            bgcolor=BG_SURFACE,
                            open=True,
                        )) or page.update()
                    )
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER
        ),
        padding=ft.Padding.only(left=20, right=12, top=_top_header, bottom=12),
        border=ft.Border.only(bottom=ft.BorderSide(1, BORDER))
    )

    content_area = ft.Container(
        content=ft.Stack([search_view_container, library_view_container]),
        expand=True,
        padding=ft.Padding.only(left=16, top=12, right=16, bottom=12),
    )

    # Bottom Navigation Bar
    navigation_bar = ft.NavigationBar(
        bgcolor=BG_DEEP,
        border=ft.Border.only(top=ft.BorderSide(1, BORDER)),
        destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.SEARCH_ROUNDED, label="Ara"),
            ft.NavigationBarDestination(icon=ft.Icons.VIDEO_LIBRARY_ROUNDED, label="İndirilenler"),
        ],
        on_change=lambda e: switch_tab(e.control.selected_index),
        selected_index=0,
        height=62
    )

    def switch_tab(index: int):
        if index == 0:
            search_view_container.visible = True
            library_view_container.visible = False
        else:
            search_view_container.visible = False
            library_view_container.visible = True
            refresh_library()
        page.update()

    main_col = ft.Column(
        [header, content_area],
        spacing=0,
        expand=True,
    )

    # Ana sayfa kök stack yapısı (Oynatıcı ve kanal pencerelerini üst üste bindirmek için)
    root_stack = ft.Stack(
        [
            main_col,
            channel_overlay,
            player_overlay
        ],
        expand=True
    )

    # ── SAFEAREA VE BAŞLANGIÇ ÇAĞRISI ─────────────────────────────────
    if _mobile:
        page.add(ft.SafeArea(expand=True, content=root_stack))
        # Navigasyon çubuğunu doğrudan ekle
        page.navigation_bar = navigation_bar
    else:
        # Desktop
        main_col.controls.append(navigation_bar)
        page.add(root_stack)

    # İlk yüklemede kütüphaneyi yenile
    refresh_library()

ft.run(main)