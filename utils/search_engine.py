import yt_dlp
import sys
import re
from urllib.parse import urlparse, parse_qs

# ── YouTube Arama sp Kodları Haritası ──────────────────────────────
# Bu filtre kodları, arama sonuçlarını belirli tipe, tarihe ve sıraya göre filtrelememizi sağlar.
SP_MAP = {
    # (type, date, sort)
    # TİPLER: "video", "channel", "playlist", "shorts"
    # TARİHLER: "any", "today" (24h), "week", "month", "year"
    # SIRALAMALAR: "relevance", "date", "views", "likes"
    
    # ── Sadece Tip Filtresi (Alaka Düzeyine Göre Sıralı) ──
    ("video", "any", "relevance"): "EgIQAQ%3D%3D",
    ("channel", "any", "relevance"): "EgIQAg%3D%3D",
    ("playlist", "any", "relevance"): "EgIQAw%3D%3D",
    
    # ── Tip: Video + Sıralama Filtreleri ──
    ("video", "any", "date"): "CAISAhAB",
    ("video", "any", "views"): "CAMSAhAB",
    ("video", "any", "likes"): "CAESAhAB",
    
    # ── Tip: Video + Yükleme Tarihi Filtreleri ──
    ("video", "today", "relevance"): "EgQIAhAB",
    ("video", "week", "relevance"): "EgQIAxAB",
    ("video", "month", "relevance"): "EgQIBBAB",
    ("video", "year", "relevance"): "EgQIBRAB",
    
    # ── Tip: Video + Tarih + Sıralama (Yükleme Tarihine Göre) ──
    ("video", "today", "date"): "CAISBAgCEAE%3D",
    ("video", "week", "date"): "CAISBAgDEAE%3D",
    ("video", "month", "date"): "CAISBAgEEAE%3D",
    ("video", "year", "date"): "CAISBAgFEAE%3D",
    
    # ── Tip: Video + Tarih + Sıralama (Görüntülenme Sayısına Göre) ──
    ("video", "today", "views"): "CAMSBAgCEAE%3D",
    ("video", "week", "views"): "CAMSBAgDEAE%3D",
    ("video", "month", "views"): "CAMSBAgEEAE%3D",
    ("video", "year", "views"): "CAMSBAgFEAE%3D",
    
    # ── Tip: Video + Tarih + Sıralama (Beğeni / Puanlama Göre) ──
    ("video", "today", "likes"): "CAESBAgCEAE%3D",
    ("video", "week", "likes"): "CAESBAgDEAE%3D",
    ("video", "month", "likes"): "CAESBAgEEAE%3D",
    ("video", "year", "likes"): "CAESBAgFEAE%3D",
    
    # ── Tip: Kanal + Sıralama Filtreleri ──
    ("channel", "any", "date"): "CAISAhAC",
    ("channel", "any", "views"): "CAMSAhAC",
    ("channel", "any", "likes"): "CAESAhAC",
    
    # ── Tip: Oynatma Listesi + Sıralama Filtreleri ──
    ("playlist", "any", "date"): "CAISAhAD",
    ("playlist", "any", "views"): "CAMSAhAD",
    ("playlist", "any", "likes"): "CAESAhAD",
}

def format_number(count: int) -> str:
    """Sayıları YouTube tarzında kısaltarak biçimlendirir (ör. 1.2M veya 450B)."""
    if count is None or not isinstance(count, (int, float)):
        return "0"
    if count >= 1_000_000:
        val = count / 1_000_000
        return f"{val:.1f} Mn" if val % 1 != 0 else f"{int(val)} Mn"
    if count >= 1_000:
        val = count / 1_000
        return f"{val:.1f} B" if val % 1 != 0 else f"{int(val)} B"
    return str(int(count))

def format_duration(seconds: int) -> str:
    """Saniye değerini 'DAKİKA:SANİYE' formatına çevirir."""
    if seconds is None:
        return "—"
    try:
        mins, secs = divmod(int(seconds), 60)
        hours, mins = divmod(mins, 60)
        if hours > 0:
            return f"{hours}:{mins:02d}:{secs:02d}"
        return f"{mins}:{secs:02d}"
    except (ValueError, TypeError):
        return "—"

def extract_thumbnails(thumbnails_list) -> tuple[str, str]:
    """
    Thumbnail listesinden kare olanı avatar, 
    enine geniş olanı ise banner olarak ayrıştırır.
    """
    avatar_url = ""
    banner_url = ""
    
    if not thumbnails_list or not isinstance(thumbnails_list, list):
        return avatar_url, banner_url
        
    for thumb in thumbnails_list:
        if not thumb or "url" not in thumb:
            continue
        url = thumb["url"]
        w = thumb.get("width")
        h = thumb.get("height")
        
        if w and h:
            aspect = w / h
            if abs(aspect - 1.0) < 0.15: # Kare veya kareye yakın -> Avatar
                avatar_url = url
            elif aspect > 2.2: # Geniş -> Banner
                banner_url = url
        else:
            # Boyut bilgisi yoksa URL örüntüsüne göre tahmin
            if "=s" in url or "-c-k-c0x00" in url:
                avatar_url = url
            elif "fcrop" in url or "w1060" in url:
                banner_url = url
                
    # Fallback: Eğer hiç bulunamadıysa ilk görseli ata
    if not avatar_url and thumbnails_list:
        avatar_url = thumbnails_list[0]["url"]
        
    return avatar_url, banner_url

def is_youtube_url(query: str) -> bool:
    """Girilen sorgunun bir YouTube URL'si olup olmadığını kontrol eder."""
    return bool(re.match(r"^(https?://)?(www\.)?(youtube\.com|youtu\.be)/.*$", query))


def extract_video_id(url: str) -> str | None:
    """Try to extract a standard 11-char YouTube video id from many URL forms.

    Handles `youtu.be/ID`, `youtube.com/watch?v=ID`, `/shorts/ID`, `/embed/ID`.
    Returns the video id or None.
    """
    if not url or not isinstance(url, str):
        return None
    try:
        parsed = urlparse(url)
        netloc = (parsed.netloc or "").lower()
        path = parsed.path or ""

        # Short link: youtu.be/ID
        if "youtu.be" in netloc:
            vid = path.lstrip("/")
            if re.match(r"^[0-9A-Za-z_-]{11}$", vid):
                return vid
            # sometimes extra fragments present, take first segment
            first = vid.split("/")[0]
            if re.match(r"^[0-9A-Za-z_-]{11}$", first):
                return first

        # Standard youtube.com links
        if "youtube" in netloc:
            qs = parse_qs(parsed.query)
            if "v" in qs and qs["v"]:
                v = qs["v"][0]
                if re.match(r"^[0-9A-Za-z_-]{11}$", v):
                    return v
            # /shorts/ID or /embed/ID
            m = re.search(r"/(?:shorts|embed)/([0-9A-Za-z_-]{11})", path)
            if m:
                return m.group(1)

        return None
    except Exception:
        return None

# Resilient (Kararlı) ve hızlı arama için ortak HTTP header'lar
HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7"
}

def fetch_playlist_search_metadata(search_url: str) -> dict:
    """
    YouTube arama sayfasını doğrudan çekerek oynatma listelerinin video sayısı ve uploader
    bilgilerini içeren bir harita döner.
    """
    import urllib.request
    import urllib.error
    import json
    
    import urllib.parse
    metadata_map = {}
    try:
        parsed_url = urllib.parse.urlparse(search_url)
        query_params = urllib.parse.parse_qsl(parsed_url.query)
        encoded_query = urllib.parse.urlencode(query_params)
        safe_search_url = urllib.parse.urlunparse((
            parsed_url.scheme,
            parsed_url.netloc,
            parsed_url.path,
            parsed_url.params,
            encoded_query,
            parsed_url.fragment
        ))
        
        req = urllib.request.Request(safe_search_url, headers=HTTP_HEADERS)
        with urllib.request.urlopen(req, timeout=5) as response:
            html = response.read().decode("utf-8")
        
        m = re.search(r'var ytInitialData\s*=\s*(\{.*?\});', html)
        if not m:
            m = re.search(r'window\["ytInitialData"\]\s*=\s*(\{.*?\});', html)
            
        if m:
            data = json.loads(m.group(1))
            contents = data.get("contents", {}).get("twoColumnSearchResultsRenderer", {}).get("primaryContents", {}).get("sectionListRenderer", {}).get("contents", [])
            for section in contents:
                if "itemSectionRenderer" not in section:
                    continue
                items = section["itemSectionRenderer"].get("contents", [])
                for item in items:
                    # Yeni YouTube düzeni: lockupViewModel
                    if "lockupViewModel" in item:
                        vm = item["lockupViewModel"]
                        if vm.get("contentType") == "LOCKUP_CONTENT_TYPE_PLAYLIST":
                            playlist_id = vm.get("contentId")
                            if playlist_id:
                                # Video sayısı badge bilgisinden çekilir
                                video_count_text = ""
                                overlays = vm.get("contentImage", {}).get("collectionThumbnailViewModel", {}).get("primaryThumbnail", {}).get("thumbnailViewModel", {}).get("overlays", [])
                                for overlay in overlays:
                                    badge_vm = overlay.get("thumbnailOverlayBadgeViewModel", {})
                                    badges = badge_vm.get("thumbnailBadges", [])
                                    if badges:
                                        text = badges[0].get("thumbnailBadgeViewModel", {}).get("text")
                                        if text:
                                            video_count_text = text
                                            break
                                            
                                # Kanal/Yükleyici bilgisi
                                uploader = ""
                                rows = vm.get("metadata", {}).get("lockupMetadataViewModel", {}).get("metadata", {}).get("contentMetadataViewModel", {}).get("metadataRows", [])
                                if rows:
                                    parts = rows[0].get("metadataParts", [])
                                    if parts:
                                        uploader = parts[0].get("text", {}).get("content", "")
                                        
                                # Video sayısını sayıya dönüştürme
                                video_count = 0
                                if video_count_text:
                                    digits = re.findall(r'\d+', video_count_text.replace(".", "").replace(",", ""))
                                    if digits:
                                        video_count = int(digits[0])
                                        
                                metadata_map[playlist_id] = {
                                    "uploader": uploader,
                                    "video_count": video_count
                                }
                    # Eski YouTube düzeni: playlistRenderer
                    elif "playlistRenderer" in item:
                        pl = item["playlistRenderer"]
                        playlist_id = pl.get("playlistId")
                        if playlist_id:
                            video_count_text = pl.get("videoCountText", {}).get("runs", [{}])[0].get("text", "") or pl.get("videoCountText", {}).get("simpleText", "")
                            video_count = 0
                            if video_count_text:
                                digits = re.findall(r'\d+', video_count_text.replace(".", "").replace(",", ""))
                                if digits:
                                    video_count = int(digits[0])
                                    
                            uploader = pl.get("shortBylineText", {}).get("runs", [{}])[0].get("text", "") or pl.get("longBylineText", {}).get("runs", [{}])[0].get("text", "")
                            metadata_map[playlist_id] = {
                                "uploader": uploader,
                                "video_count": video_count
                            }
    except Exception as e:
        print(f"Oynatma listesi arama detayları çekilirken hata oluştu: {e}", file=sys.stderr)
        
    return metadata_map

def search_youtube(
    query: str,
    type_filter: str = "video",
    date_filter: str = "any",
    sort_filter: str = "relevance"
) -> list[dict]:
    """
    Belirtilen filtreler ve sıralama seçenekleriyle YouTube araması gerçekleştirir.
    Geriye homojenleştirilmiş bir sonuç listesi döner.
    """
    query = query.strip()
    if not query:
        return []
        
    is_url = is_youtube_url(query)

    query_is_video = bool(is_url and extract_video_id(query) is not None)
    
    # Shorts özel durumu
    if type_filter == "shorts" and not is_url:
        query_str = f"{query} shorts"
        type_mapped = "video"
    else:
        query_str = query
        type_mapped = type_filter
        
    # URL veya Arama URL'si belirleme
    if is_url:
        search_url = query_str
    else:
        # sp filtresini bul
        sp_code = SP_MAP.get((type_mapped, date_filter, sort_filter))
        if sp_code:
            search_url = f"https://www.youtube.com/results?search_query={query_str}&sp={sp_code}"
        else:
            # Eşleşme yoksa varsayılan
            if type_mapped == "channel":
                search_url = f"https://www.youtube.com/results?search_query={query_str}&sp=EgIQAg%253D%253D"
            elif type_mapped == "playlist":
                search_url = f"https://www.youtube.com/results?search_query={query_str}&sp=EgIQAw%253D%253D"
            else:
                search_url = f"https://www.youtube.com/results?search_query={query_str}&sp=EgIQAQ%253D%253D"

    # Oynatma listesi aramalarında video sayısı ve uploader bilgisini çekmek için ön-tarama
    playlist_metadata_map = {}
    if type_mapped == "playlist" and not is_url:
        playlist_metadata_map = fetch_playlist_search_metadata(search_url)

    ydl_opts = {
        "quiet": True,
        "extract_flat": True,
        "no_warnings": True,
        "playlist_items": "1-30",          # En fazla 30 sonuç getir (hız optimizasyonu)
        
        # Kararlılık seçenekleri
        "retries": 10,
        "nocheckcertificate": True,
        "http_headers": HTTP_HEADERS,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"]
            }
        }
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(search_url, download=False)
        if not info:
            return []
            
        entries = info.get("entries", [info]) if "entries" in info or is_url else []
        if not entries and "entries" not in info:
            entries = [info]
            
        results = []
        for entry in entries:
            if not entry:
                continue
                
            entry_type = entry.get("_type")
            url = (
                entry.get("webpage_url")
                or entry.get("url")
                or (f"https://www.youtube.com/watch?v={entry['id']}" if entry.get("id") else None)
            )
            if not url:
                continue
                
            # Sonucun kanal mı, oynatma listesi mi yoksa video mu olduğunu anlama
            ie_key = entry.get("ie_key")
            
            # Oynatma listesi kontrolünü en önce yap (bazı oynatma listelerinin URL'lerinde kanal adı geçtiği için misclassification önlenir)
            is_playlist = (
                ie_key == "YoutubePlaylist" 
                or "/playlist" in url 
                or "list=" in url 
                or entry.get("playlist_count") is not None
            )
            
            if is_playlist:
                is_channel = False
            elif query_is_video:
                is_channel = False
            else:
                is_channel = (
                    ie_key == "YoutubeTab" 
                    or "/channel/" in url 
                    or "/@" in url 
                    or entry.get("channel_follower_count") is not None
                )
            
            # Ortak veri yapısı
            title = entry.get("title") or "Başlıksız"
            
            if is_channel:
                avatar, banner = extract_thumbnails(entry.get("thumbnails"))
                results.append({
                    "type": "channel",
                    "title": title,
                    "url": url,
                    "id": entry.get("id"),
                    "subscribers": format_number(entry.get("channel_follower_count")),
                    "avatar": avatar,
                    "description": entry.get("description") or "",
                    "is_verified": entry.get("channel_is_verified", False)
                })
            elif is_playlist:
                playlist_id = entry.get("id")
                meta = playlist_metadata_map.get(playlist_id, {})
                results.append({
                    "type": "playlist",
                    "title": title,
                    "url": url,
                    "id": playlist_id,
                    "video_count": meta.get("video_count") or entry.get("playlist_count") or entry.get("video_count") or 0,
                    "uploader": meta.get("uploader") or entry.get("uploader") or entry.get("channel") or "Bilinmiyor"
                })
            else:
                # Video veya Shorts
                duration = format_duration(entry.get("duration"))
                results.append({
                    "type": "shorts" if type_filter == "shorts" or (entry.get("duration") and entry.get("duration") <= 60 and "shorts" in url) else "video",
                    "title": title,
                    "url": url,
                    "id": entry.get("id"),
                    "duration": duration,
                    "uploader": entry.get("uploader") or entry.get("channel") or "Bilinmiyor"
                })
                
        return results

def get_channel_info(channel_url: str, sort_by: str = "latest") -> dict:
    """
    Belirtilen kanal URL'sinden kanal detaylarını ve videolarını çeker.
    Kanalın tüm geçmişini değil, sadece ilk 30 videosunu çekerek sayfa yüklemesini aşırı hızlandırır (Optimization B).
    """
    # YouTube kanal video sekmesini ekle (Base URL sonundaki slash karakterini rstrip ile temizleyerek çift slash oluşmasını önle)
    base_url = channel_url.split("/videos")[0].split("/shorts")[0].split("/playlists")[0].rstrip("/")
    
    if sort_by == "popular":
        fetch_url = f"{base_url}/videos?view=0&sort=p"
    else: # latest
        fetch_url = f"{base_url}/videos"
        
    ydl_opts = {
        "quiet": True,
        "extract_flat": True,
        "no_warnings": True,
        "playlist_items": "1-30",          # [Optimization B] Sadece ilk 30 videoyu çekerek sayfa yüklenmesini INSTANT (anlık) yapar!
        
        # Kararlılık seçenekleri
        "retries": 10,
        "nocheckcertificate": True,
        "http_headers": HTTP_HEADERS,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"]
            }
        }
    }
    
    # Kanal videolarını çekme işleminde hata toleransı (Fallback Extraction) eklenmiştir.
    # Eğer doğrudan /videos linki başarısız olursa, yt-dlp'nin kanalın ana sayfasından otomatik çıkarması sağlanır.
    info = None
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(fetch_url, download=False)
    except Exception:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(base_url, download=False)
        except Exception:
            pass

    if not info:
        raise ValueError("Kanal bilgileri alınamadı.")
        
    avatar, banner = extract_thumbnails(info.get("thumbnails"))
    
    # Videoları dönüştür
    raw_entries = info.get("entries", [])
    videos = []
    for entry in raw_entries:
        if not entry:
            continue
        url = entry.get("url") or (f"https://www.youtube.com/watch?v={entry['id']}" if entry.get("id") else None)
        if not url:
            continue
            
        videos.append({
            "title": entry.get("title") or "Başlıksız",
            "url": url,
            "id": entry.get("id"),
            "duration": format_duration(entry.get("duration")),
            "uploader": info.get("channel") or info.get("uploader") or "Kanal Sahibi"
        })
        
    return {
        "name": info.get("channel") or info.get("uploader") or info.get("title") or "Bilinmeyen Kanal",
        "url": base_url,
        "avatar": avatar,
        "banner": banner,
        "subscribers": format_number(info.get("channel_follower_count")),
        "video_count": info.get("playlist_count") or len(videos),
        "description": info.get("description") or "Açıklama bulunmuyor.",
        "videos": videos
    }

def get_playlist_info(playlist_url: str) -> dict:
    """
    Belirtilen oynatma listesi URL'sinden liste detaylarını ve videolarını çeker.
    """
    ydl_opts = {
        "quiet": True,
        "extract_flat": True,
        "no_warnings": True,
        "playlist_items": "1-50",          # Sadece ilk 50 videoyu çekerek sayfa yüklenmesini çok hızlı yapar!
        
        # Kararlılık seçenekleri
        "retries": 10,
        "nocheckcertificate": True,
        "http_headers": HTTP_HEADERS,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"]
            }
        }
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(playlist_url, download=False)
        if not info:
            raise ValueError("Oynatma listesi bilgileri alınamadı.")
            
        raw_entries = info.get("entries", [])
        videos = []
        for entry in raw_entries:
            if not entry:
                continue
            url = entry.get("url") or (f"https://www.youtube.com/watch?v={entry['id']}" if entry.get("id") else None)
            if not url:
                continue
                
            videos.append({
                "title": entry.get("title") or "Başlıksız",
                "url": url,
                "id": entry.get("id"),
                "duration": format_duration(entry.get("duration")),
                "uploader": entry.get("uploader") or info.get("uploader") or info.get("channel") or "Bilinmeyen Uploader"
            })
            
        return {
            "name": info.get("title") or "Bilinmeyen Oynatma Listesi",
            "url": playlist_url,
            "uploader": info.get("uploader") or info.get("channel") or "Bilinmeyen Oluşturucu",
            "video_count": info.get("playlist_count") or info.get("video_count") or len(videos),
            "description": info.get("description") or "Oynatma Listesi Arşivi",
            "videos": videos
        }