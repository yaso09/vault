# YT Downloader — Android APK

YouTube videolarını indirip telefonda depolayan Kivy + Flask + yt-dlp uygulaması.

## Proje Yapısı

```
ytdlp_app/
├── main.py           # Kivy uygulaması + Flask sunucu + yt-dlp mantığı
├── buildozer.spec    # Android derleme ayarları
└── www/
    └── index.html    # WebView'da gösterilen arayüz
```

## Derleme Ortamı (Ubuntu 22.04 / WSL2 önerilir)

### 1. Sistem Bağımlılıkları

```bash
sudo apt update && sudo apt install -y \
    git zip unzip openjdk-17-jdk \
    python3-pip autoconf libtool pkg-config \
    zlib1g-dev libncurses5-dev libncursesw5-dev \
    libtinfo5 cmake libffi-dev libssl-dev \
    ffmpeg
```

### 2. Python Araçları

```bash
pip install buildozer cython virtualenv
```

### 3. APK Derleme

```bash
cd ytdlp_app

# İlk derleme (20–40 dk) — SDK/NDK otomatik indirilir
buildozer android debug

# APK buraya çıkar:
ls bin/*.apk
```

### 4. Telefona Yükleme (USB bağlıyken)

```bash
buildozer android debug deploy run
```

Ya da `bin/` içindeki `.apk` dosyasını telefonuna kopyalayıp kur.

---

## Test (Bilgisayarda)

```bash
pip install flask yt-dlp kivy
python main.py
# Tarayıcıda: http://127.0.0.1:5000
```

> `android.*` import'ları bilgisayarda çalışmaz, bunlar sadece APK içinde aktif olur.
> PC testinde `AndroidWebView` satırını yorum satırına alıp Flask'ı doğrudan çalıştır.

---

## Özellikler

- ✅ YouTube URL yapıştır, MP4 veya MP3 seç, indir
- ✅ Anlık indirme ilerlemesi (SSE)
- ✅ İndirilen dosyaları listele / sil
- ✅ Dosyalar `/sdcard/YTDownloader/` klasörüne kaydedilir

## Notlar

- **FFmpeg**: APK'da FFmpeg yoksa `format = best[ext=mp4]/best` kullanılır
  (tek dosya, birleştirme gerekmez). En iyi kalite için Termux'ta
  `pkg install ffmpeg` yapılabilir.
- **Android 13+**: `READ_MEDIA_VIDEO` ve `READ_MEDIA_AUDIO` izinleri gereklidir.
- **yt-dlp**: YouTube politika değişikliklerinden etkilenebilir.
  Güncel tutmak için: `pip install -U yt-dlp`
