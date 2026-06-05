<img src="./assets/banner.svg">

<center><h1>🔒 Vault</h1></center>

**Vault**, YouTube videolarını arayıp indirmenize ve indirdiğiniz videoları yerleşik oynatıcıyla izlemenize olanak tanıyan açık kaynaklı, çok platformlu bir uygulamadır. Python ve [Flet](https://flet.dev) çerçevesi üzerine inşa edilmiştir.

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![Flet](https://img.shields.io/badge/Flet-UI-00BCD4?style=flat)](https://flet.dev)
[![yt-dlp](https://img.shields.io/badge/yt--dlp-indirici-FF0000?style=flat&logo=youtube&logoColor=white)](https://github.com/yt-dlp/yt-dlp)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux%20%7C%20Android%20%7C%20iOS-0078D4?style=flat)](https://github.com/yaso09/vault/releases)
[![License](https://img.shields.io/badge/Lisans-GPL--v3-green?style=flat)](https://www.gnu.org/licenses/gpl-3.0.html)
[![Release](https://img.shields.io/github/v/release/yaso09/vault?style=flat&color=brightgreen)](https://github.com/yaso09/vault/releases)

<p align="center">
  <img src="./assets/screen-shot-1.png">
  <img src="./assets/screen-shot-2.png">
</p>

---

## Özellikler

- 🔍 YouTube'da video, kanal ve oynatma listesi araması; tür, tarih ve sıralama filtreleri
- ⬇️ `yt-dlp` tabanlı indirme motoru — gerçek zamanlı ilerleme çubuğu, otomatik yeniden deneme
- 🎬 Yerleşik video oynatıcı — seek, ses kontrolü, oynatma hızı, tam ekran, konum kaydetme
- 📚 İndirilen videolar kütüphanesi — tek tıkla oynat veya sil
- 📺 Kanal sayfası — abone sayısı, banner, en yeni/popüler video listeleri

---

## Kurulum ve Çalıştırma

Hazır kurulum istemiyorsanız uygulamayı kaynak koddan derlemenize gerek yok — en güncel çalıştırılabilir sürümü **[Releases](https://github.com/yaso09/vault/releases)** sayfasından indirip doğrudan kullanabilirsiniz.

Kaynak koddan çalıştırmak için [uv](https://docs.astral.sh/uv/) ve [Docker](https://www.docker.com/) gereklidir. Ayrıca Windows kullanıcılarının WSL kullanması gerekmektedir.

```bash
git clone --recurse-submodules https://github.com/yaso09/vault

cd vault
uv sync

cd FFmpeg-WASI
chmod +x build.sh
./build.sh
```

### Çalıştırma

```bash
uv run main.py --desktop   # Masaüstü penceresi (Windows ve Linux'ta çalışmaz)
uv run main.py --web       # Tarayıcıda aç
uv run main.py --mobile    # Mobil görünüm (tarayıcı)
```

### Derleme

```bash
uv run flet build apk      # Android (.apk)
uv run flet build ipa      # iOS (.ipa)
uv run flet build windows  # Windows
uv run flet build macos    # macOS
uv run flet build linux    # Linux
```

> Platforma özgü gereksinimler için [Flet yayınlama belgelerine](https://flet.dev/docs/publish) bakınız.

---

## Lisans

Bu proje **[GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0.html)** lisansı altında dağıtılmaktadır. Lisansın tam metnini [`LICENSE`](LICENSE) dosyasında bulabilirsiniz.

---

> Vault; [yt-dlp](https://github.com/yt-dlp/yt-dlp), [FFmpeg-WASI](https://github.com/SebastiaanYN/FFmpeg-WASI) ve [Flet](https://flet.dev) açık kaynak projeleri üzerine inşa edilmiştir.
