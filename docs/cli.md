# Vault CLI

Vault, komut satırından tam olarak kontrol edilebilir. Aşağıda tüm komutlar ve kullanım örnekleri yer almaktadır.

## Kullanım

```bash
vault [GLOBAL_OPTS] KOMUT [ARGS]
```

## Global Seçenekler

| Bayrak           | Varsayılan | Açıklama                              |
|------------------|------------|---------------------------------------|
| `-p, --port`     | `8000`     | Sunucu portu                          |
| `--verbose`      | —          | Detaylı log çıktısı (DEBUG seviyesi)  |

## Komutlar

### `run` — Sunucuyu başlatır

```bash
vault run --desktop
vault run --web
vault run --mobile
vault -p 8080 run --desktop
```

Flag'lerden biri zorunludur:
- `--web` — Sadece sunucuyu başlatır, URL'yi yazdırır
- `--desktop` — Sunucuyu başlatır ve varsayılan tarayıcıda açar
- `--mobile` — Sunucuyu başlatır ve Flet WebView mobil penceresinde açar

### `download <URL>` — Video veya oynatma listesi indirir

```bash
vault download "https://youtube.com/watch?v=..."
vault download "https://youtube.com/watch?v=..." -f 1080p
vault download "https://youtube.com/watch?v=..." -o "C:\Videos"
vault download "https://youtube.com/watch?v=..." --audio-only
vault download "https://youtube.com/watch?v=..." --no-merge
```

| Bayrak                | Varsayılan      | Açıklama                                           |
|-----------------------|-----------------|----------------------------------------------------|
| `-f, --format`        | `best`          | Video formatı: best, 1080p, 720p, 480p, 360p      |
| `-o, --output`        | `~/Vault/videos`| Çıktı dizini                                       |
| `--audio-only`        | —               | Sadece ses indir (MP3)                             |
| `--no-merge`          | —               | Video ve ses ayrı dosyalar olarak kalsın           |

### `search <QUERY>` — YouTube'da arama yapar

```bash
vault search "lofi music"
vault search "lofi music" --type channel
vault search "lofi music" --type playlist --sort views --limit 20
```

| Bayrak           | Varsayılan   | Açıklama                                          |
|------------------|--------------|---------------------------------------------------|
| `-t, --type`     | `video`      | Arama tipi: video, channel, playlist, shorts      |
| `-s, --sort`     | `relevance`  | Sıralama: relevance, date, views, likes           |
| `-d, --date`     | `any`        | Tarih filtresi: any, today, week, month, year     |
| `-l, --limit`    | `10`         | Gösterilecek sonuç sayısı                         |

### `info <URL>` — Video/kanal/playlist bilgisi gösterir

```bash
vault info "https://youtube.com/watch?v=..."
vault info "https://youtube.com/playlist?list=..."
vault info "https://youtube.com/@channel"
```

Çıktı JSON formatındadır.

## Örnekler

```bash
# Videoyu 1080p olarak belirli bir klasöre indir
vault download "https://youtube.com/watch?v=dQw4w9WgXcQ" -f 1080p -o "C:\Users\me\Videos"

# Kanal ara
vault search "lofi girl" --type channel

# Sunucuyu 9090 portunda başlat
vault -p 9090 run --desktop

# Sadece ses indir
vault download "https://youtube.com/watch?v=dQw4w9WgXcQ" --audio-only

# Detaylı log ile çalıştır
vault --verbose run --web
```
