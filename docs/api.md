# API Referansı

Vault, FastAPI tabanlı REST API sunar. Tüm uç noktalar `http://localhost:8000` üzerinden erişilebilir.

## Temel Uç Noktalar

| Yöntem | Uç Nokta | Açıklama |
|--------|----------|----------|
| `GET` | `/` | Ana sayfa — `index.html` + `app.js` enjeksiyonu |
| `GET` | `/api/search?q=&type=&date=&sort=` | YouTube araması (video/kanal/playlist/shorts) |
| `GET` | `/api/channel?url=&sort_by=` | Kanal bilgisi ve video listesi (latest/popular) |
| `GET` | `/api/downloads` | Tüm indirme durumları (aktif + bitmiş) |
| `POST` | `/api/download` | `{url, title}` ile indirme başlatma |
| `GET` | `/api/library` | İndirilen video dosyalarının listesi |
| `DELETE` | `/api/library/{filename}` | Video dosyası silme |
| `POST` | `/api/library/position` | `{filepath, position_ms}` oynatma konumu kaydetme |
| `GET` | `/api/library/positions` | Tüm kayıtlı oynatma konumları |
| `GET` | `/video/{filename}` | Video akışı (HTTP Range Request, 206 Partial Content) |

## Arama Filtreleri

`/api/search` uç noktası aşağıdaki parametreleri destekler:

| Parametre | Değerler | Varsayılan | Açıklama |
|-----------|----------|-----------|----------|
| `q` | metin | — | Arama sorgusu (zorunlu) |
| `type` | `video`, `channel`, `playlist`, `shorts` | `video` | Arama tipi |
| `date` | `any`, `today`, `week`, `month`, `year` | `any` | Yükleme tarihi filtresi |
| `sort` | `relevance`, `date`, `views`, `likes` | `relevance` | Sıralama düzeni |

### Örnek İstek

```
GET /api/search?q=lofi%20music&type=video&date=week&sort=views
```

### Örnek Yanıt

```json
{
  "results": [
    {
      "title": "lofi hip hop radio - beats to relax/study to",
      "channel": "Lofi Girl",
      "url": "https://youtube.com/watch?v=...",
      "duration": "2:30:00",
      "view_count": 50000000,
      "thumbnail": "https://i.ytimg.com/vi/.../hqdefault.jpg"
    }
  ]
}
```

## İndirme İşlemi

### İndirme Başlatma

```
POST /api/download
Content-Type: application/json

{
  "url": "https://youtube.com/watch?v=...",
  "title": "Video Başlığı"
}
```

Yanıt:

```json
{
  "status": "ok",
  "download_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### İndirme Durumu Sorgulama

```
GET /api/downloads
```

Yanıt:

```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "url": "https://youtube.com/watch?v=...",
    "title": "Video Başlığı",
    "progress": 0.45,
    "speed": "2.5 MiB/s",
    "eta": "30s",
    "status": "downloading",
    "error": null,
    "completed_at": null
  }
]
```

İndirme 2 aşamalıdır:
- **%0–45:** Video akışı indiriliyor
- **%45–90:** Ses akışı indiriliyor
- **%90–100:** WASM FFmpeg ile video + ses birleştiriliyor

## Video Kütüphanesi

### Video Listesi

```
GET /api/library
```

Yanıt:

```json
[
  {
    "filename": "lofi hip hop radio.mp4",
    "filepath": "/home/user/Vault/videos/lofi hip hop radio.mp4",
    "size": 104857600
  }
]
```

### Video Silme

```
DELETE /api/library/lofi%20hip%20hop%20radio.mp4
```

Yanıt:

```json
{
  "status": "ok"
}
```

## Oynatma Konumu

### Konum Kaydetme

```
POST /api/library/position
Content-Type: application/json

{
  "filepath": "/home/user/Vault/videos/lofi hip hop radio.mp4",
  "position_ms": 123456
}
```

### Konumları Okuma

```
GET /api/library/positions
```

## Video Akışı

Video dosyaları `/video/{filename}` üzerinden HTTP Range Request (206 Partial Content) ile akış olarak sunulur. Bu sayede arayıp tarama (seek) desteği plyr.io oynatıcı ile sorunsuz çalışır.

Desteklenen formatlar:
- `.mp4` → `video/mp4`
- `.webm` → `video/webm`
- `.mkv` → `video/x-matroska`

## Port Yönetimi

Varsayılan port 8000'dir. Eğer meşgulse otomatik olarak bir üst port denenir. Port numarası `-p`/`--port` parametresi ile değiştirilebilir.
