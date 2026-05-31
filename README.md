# 🔒 Vault

**Vault**, YouTube videolarını arayıp indirmenize ve indirdiğiniz videoları yerleşik oynatıcıyla izlemenize olanak tanıyan açık kaynaklı bir masaüstü ve Android uygulamasıdır. Flet çerçevesi üzerine Python ile geliştirilmiştir.

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat&logo=python&logoColor=white)
![Flet](https://img.shields.io/badge/Flet-UI-00BCD4?style=flat)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Android-0078D4?style=flat)
![License](https://img.shields.io/badge/License-GPLv3-green?style=flat)

---

## İçindekiler

- [Özellikler](#özellikler)
- [Gereksinimler](#gereksinimler)
- [Kurulum](#kurulum)
- [Kullanım](#kullanım)
- [Proje Yapısı](#proje-yapısı)
- [Katkıda Bulunma](#katkıda-bulunma)
- [Lisans](#lisans)
- [Geliştirici](#geliştirici)

---

## Özellikler

### 🔍 Arama
- Video, kanal, oynatma listesi ve Shorts türlerinde filtrelenmiş YouTube araması
- Yükleme tarihi filtresi (son 24 saat, hafta, ay, yıl)
- Sıralama seçenekleri: alaka düzeyi, tarih, izlenme, beğeni
- Doğrudan YouTube URL'si girişi

### 📺 Kanal Sayfası
- Kanal bilgileri, abone sayısı ve banner gösterimi
- En son / en popüler videolara göre sıralama
- Kanal videoları listesinden tek tıkla indirme

### ⬇️ İndirme
- `yt-dlp` tabanlı yüksek güvenilirlikli indirme motoru
- Masaüstünde 1080p MP4, mobilde en iyi tek parça MP4 formatı otomatik seçimi
- Gerçek zamanlı ilerleme çubuğu (yüzde, hız, kalan süre)
- Ağ kopması ve YouTube hız sınırına karşı otomatik yeniden deneme (15 kez)
- Aynı anda birden fazla video indirme desteği

### 🎬 Video Oynatıcı
- Oynat/Durdur, ileri/geri sarma (±10 saniye)
- Seek çubuğu ve kalan süre göstergesi
- Ses kontrolü ve sessiz modu
- Oynatma hızı (0.5×, 1.0×, 1.25×, 1.5×, 2.0×)
- Tam ekran modu (çift tıkla veya butonla)
- **Oynatma konumu kaydetme** — video kapatılıp tekrar açıldığında kaldığı yerden devam eder

### 📚 Kütüphane
- İndirilen videoların liste görünümü (dosya boyutu ile birlikte)
- Tek tıkla oynatma veya silme
- İndirme tamamlandığında kütüphane otomatik güncellenir

---

## Gereksinimler

| Gereksinim | Sürüm |
|---|---|
| [uv](https://docs.astral.sh/uv/) | En güncel kararlı sürüm |
| Python | 3.11 veya üstü (`uv` tarafından otomatik yönetilir) |
| flet | En güncel kararlı sürüm |
| flet-video | En güncel kararlı sürüm |
| yt-dlp | En güncel kararlı sürüm |

> **Not:** Android derleme için [Flet'in mobil derleme belgelerine](https://flet.dev/docs/publish/android) bakınız.

---

## Kurulum

> **Hazır kurulum istemiyorsanız:** Uygulamayı kaynak koddan derlemenize gerek yok. Doğrudan çalıştırılabilir sürümü [**Releases**](https://github.com/yaso09/vault/releases) sayfasından indirip kurabilirsiniz.

Kaynak koddan çalıştırmak için aşağıdaki adımları izleyin. Bu proje bağımlılık ve ortam yönetimi için **[uv](https://docs.astral.sh/uv/)** kullanmaktadır.

### 1. uv'yi yükleyin (henüz yüklü değilse)

```bash
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Linux / macOS
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Depoyu klonlayın

```bash
git clone https://github.com/yaso09/vault.git
cd vault
```

### 3. Bağımlılıkları yükleyin

```bash
uv sync
```

`uv sync` komutu; `pyproject.toml` dosyasına göre sanal ortamı otomatik oluşturur, doğru Python sürümünü indirir ve tüm bağımlılıkları yükler.

### 4. Uygulamayı başlatın

```bash
uv run python main.py
```

---

## Kullanım

### Masaüstü (Windows)

```bash
uv run python main.py
```

Uygulama 440 × 840 piksel sabit boyutlu bir pencerede açılır.

### Android

Flet CLI ile APK derleyip cihaza yükleyebilirsiniz:

```bash
flet build apk
```

Derleme talimatları için: [https://flet.dev/docs/publish/android](https://flet.dev/docs/publish/android)

### İndirme konumu

| Platform | Varsayılan Konum |
|---|---|
| Windows | `%USERPROFILE%\Vault\videos\` |
| Android | Uygulama belgeler dizini / `Vault/videos/` |

Mevcut indirme konumu; **⚙ Ayarlar** simgesine tıklayarak görüntülenebilir.

---

## Proje Yapısı

```
vault/
├── main.py            # Uygulama giriş noktası; UI düzeni, sekme navigasyonu
├── player.py          # CustomVideoPlayer sınıfı; oynatma, tam ekran, konum kaydetme
├── downloader.py      # yt-dlp tabanlı indirme motoru; ilerleme çubuğu, thread yönetimi
└── search_engine.py   # YouTube arama ve kanal bilgisi; filtre/sıralama desteği
```

### Modül Sorumlulukları

**`main.py`**
Uygulamanın ana döngüsünü, Flet `Page` yapılandırmasını, sekme navigasyonunu (Ara / İndirilenler), arama sonuç kartlarını ve kütüphane görünümünü barındırır. Oynatıcı ve kanal sayfası, ana içeriğin üzerine `Stack` katmanı olarak bindirilir.

**`player.py`**
`CustomVideoPlayer`, `ft.Container`'ı genişletir. Normal mod ve tam ekran mod için ayrı kontrol katmanları içerir. Oynatma konumları `~/.playback_positions.json` dosyasına kaydedilir. Tüm arka plan thread callback'leri `_is_alive` flag'i ile korunur; session kapatılsa bile crash oluşmaz.

**`downloader.py`**
`start_download()` fonksiyonu `page.run_thread()` ile arka planda çalışır. İlerleme güncellemeleri 0.25 saniyelik rate-limit ile kasma önlenerek yapılır. Tüm `page.update()` çağrıları `safe_update()` wrapper'ı üzerinden geçer; yıkılmış session hatalarına karşı korumalıdır.

**`search_engine.py`**
`search_youtube()` ve `get_channel_info()` fonksiyonlarını içerir. YouTube'un `sp` parametresiyle çalışan önceden derlenmiş filtre kodu tablosu (`SP_MAP`) ile tip, tarih ve sıralama filtrelerini destekler. Arama sonuçları video, kanal ve oynatma listesi türleri için normalleştirilmiş bir sözlük yapısına dönüştürülür.

---

## Katkıda Bulunma

Her türlü katkıya açığız!

1. Bu depoyu forklayın
2. Yeni bir dal oluşturun: `git checkout -b ozellik/yeni-ozellik`
3. Değişikliklerinizi işleyin: `git commit -m 'Yeni özellik: ...'`
4. Dalınızı gönderin: `git push origin ozellik/yeni-ozellik`
5. Bir Pull Request açın

Hata bildirmek için lütfen [Issues](https://github.com/yaso09/vault/issues) bölümünü kullanın.

---

## Lisans

Bu proje **GNU General Public License v3.0** lisansı altında dağıtılmaktadır.

Lisansın tam metni için [`LICENSE`](LICENSE) dosyasına bakınız ya da şu adresi ziyaret edin:
[https://www.gnu.org/licenses/gpl-3.0.html](https://www.gnu.org/licenses/gpl-3.0.html)

---

## Geliştirici

**Yasir Eymen Kayabaşı**

- GitHub: [@yaso09](https://github.com/yaso09)

---

> Vault; yt-dlp ve Flet açık kaynak projeleri üzerine inşa edilmiştir. Bu araçların geliştiricilerine teşekkürler.