import yt_dlp
import os
import flet as ft
import time

def start_download(
    page: ft.Page,
    url: str,
    title: str,
    download_path: str,
    active_downloads_col: ft.Column,
    refresh_library_callback,
    show_snack_callback,
    is_mobile: bool
):
    """
    Belirtilen videonun indirilmesini başlatır.
    İndirme işlemini thread-safe şekilde Flet'in run_thread mekanizması ile arka planda yürütür.
    UI güncellemeleri aşırı kasmayı önlemek için 0.25 saniyede bir olacak şekilde rate-limit (throttling) edilmiştir.
    """
    # UI Sabit Renkleri
    COLOR_SUCCESS = "#2BA640"
    COLOR_BORDER = "#3F3F3F"
    COLOR_CARD = "#1F1F1F"
    COLOR_TEXT_PRI = "#FFFFFF"
    COLOR_TEXT_SEC = "#AAAAAA"
    COLOR_ERROR = "#FF4D4D"

    short_title = title[:40] + ("…" if len(title) > 40 else "")
    progress_bar = ft.ProgressBar(color=COLOR_SUCCESS, bgcolor=COLOR_BORDER, value=0.0)
    status_text = ft.Text("Hazırlanıyor...", size=10, color=COLOR_TEXT_SEC)

    # İndirme Kartı UI Bileşeni
    card = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.DOWNLOADING_ROUNDED, color=COLOR_SUCCESS, size=16),
                        ft.Text(short_title, size=11, color=COLOR_TEXT_PRI, expand=True, weight=ft.FontWeight.W_500),
                    ],
                    spacing=8,
                ),
                progress_bar,
                status_text,
            ],
            spacing=6,
        ),
        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
        border_radius=10,
        bgcolor=COLOR_CARD,
        border=ft.Border.all(1, COLOR_BORDER),
    )
    
    # Aktif indirmeler sütununa kartı ekle ve UI güncelle
    active_downloads_col.controls.append(card)
    page.update()
    show_snack_callback(f"İndirme başladı: {short_title}", COLOR_SUCCESS)

    # UI kasmalarını önlemek için rate-limit zaman damgası (mutable array closure referansı)
    last_update_time = [0.0]

    def safe_update():
        """Session kapatılmış/yıkılmış olsa bile page.update() güvenle çağırır."""
        try:
            page.update()
        except RuntimeError:
            pass  # An attempt to fetch destroyed session. -> sessizce yok say

    def _download_thread():
        output_template = os.path.join(download_path, "%(title)s.%(ext)s")

        def progress_hook(d):
            if d["status"] == "downloading":
                now = time.time()
                # Arayüz kasmalarını önlemek için UI güncellemelerini saniyede en fazla 4 kez (0.25sn aralıkla) yapıyoruz
                if now - last_update_time[0] >= 0.25:
                    pct_str = d.get("_percent_str", "").strip().replace("%", "")
                    try:
                        progress_bar.value = float(pct_str) / 100
                    except Exception:
                        progress_bar.value = None
                    
                    speed = d.get("_speed_str", "").strip()
                    eta = d.get("_eta_str", "").strip()
                    status_text.value = f"İndiriliyor: %{pct_str} · {speed} · Kalan: {eta}"
                    safe_update()
                    last_update_time[0] = now
                    
            elif d["status"] == "finished":
                # İndirme bitince gecikmesiz olarak hemen %100 göster
                progress_bar.value = 1.0
                progress_bar.color = COLOR_SUCCESS
                status_text.value = "Tamamlandı ✓"
                safe_update()

        # Platforma göre format seçimi
        # Mobilde MP4 tek parça tercih edilir; masaüstünde mümkünse 1080p MP4 tercih et
        if is_mobile:
            fmt = "best[ext=mp4]/best"
        else:
            # Tercih: mp4 video <=1080p + m4a audio, yoksa 1080p video+audio, en son fallback best
            fmt = "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best"

        ydl_opts = {
            "format": fmt,
            "outtmpl": output_template,
            "noplaylist": True,
            "progress_hooks": [progress_hook],
            "quiet": True,
            "no_warnings": True,
            "merge_output_format": "mp4",
            
            # ── [Bug 2 Çözümü] Bağlantı Kesilmesi & Hız Sınırını Aşma Ayarları ──
            "retries": 15,                     # Ağ kopmalarına karşı 15 kez tekrar dene
            "fragment_retries": 15,            # Hatalı video fragmanları için 15 kez tekrar dene
            "file_access_retries": 5,          # Dosya kilitlenmelerinde 5 kez dene
            "buffersize": 1024 * 1024,         # 1 MB tampon bellek kullanarak akışı sabitle
            "nocheckcertificate": True,        # SSL sertifika hatalarını yok say
            
            # YouTube hız yavaşlatma (throttling) engelleme argümanları
            "extractor_args": {
                "youtube": {
                    "player_client": ["android", "web"]
                }
            },
            
            # Gerçekçi tarayıcı User-Agent bilgisi ekleyerek YouTube filtrelerini aş
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "*/*",
                "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache"
            }
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            # Tamamlandığında UI durumunu temizle ve listeyi yenile
            status_text.value = "Kütüphaneye Eklendi ✓"
            progress_bar.value = 1.0
            
            # Listeden bu indirme kartını kaldır veya tamamlandı durumunda tut
            if card in active_downloads_col.controls:
                # 1.5 saniye sonra aktif indirmelerden kartı yavaşça kaldır
                time.sleep(1.5)
                active_downloads_col.controls.remove(card)
                
            safe_update()
            
            # Kütüphaneyi anında yenile ve başarılı snack göster
            refresh_library_callback()
            show_snack_callback("Video kütüphanenize eklendi!", COLOR_SUCCESS)
            
        except Exception as ex:
            status_text.value = f"Hata: {ex}"
            progress_bar.color = COLOR_ERROR
            progress_bar.value = 1.0
            safe_update()
            show_snack_callback(f"İndirme başarısız: {str(ex)[:80]}", COLOR_ERROR)

    # Flet'in dahili ve güvenli thread mekanizmasını kullanarak arka planda çalıştır
    page.run_thread(_download_thread)