// ============================================================
// VAULT — app.js  (Plyr entegrasyonlu)
// ============================================================

const state = {
    activeTab: 'search',
    filters: {
        type: 'video',
        date: 'any',
        sort: 'relevance'
    },
    currentChannelUrl: '',
    currentChannelSort: 'latest',
    activeDownloads: [],
    library: [],
    pollingInterval: null,
    currentPlayingFile: '',
    playbackPositions: {},
    player: null          // Plyr instance (tek seferlik oluşturulur)
};

// ── DOM References ────────────────────────────────────────────
const elements = {
    pageTitle: document.getElementById('page-title'),
    searchQuery: document.getElementById('search-query'),
    searchResults: document.getElementById('search-results'),
    searchLoading: document.getElementById('search-loading'),
    activeDownloadsCount: document.getElementById('active-downloads-count'),
    activeDownloadsList: document.getElementById('active-downloads-list'),
    activeDownloadsSection: document.getElementById('active-downloads-section'),
    libraryVideosList: document.getElementById('library-videos-list'),

    // Channel Overlay
    overlayChannel: document.getElementById('overlay-channel'),
    chBanner: document.getElementById('ch-banner'),
    chAvatar: document.getElementById('ch-avatar'),
    chName: document.getElementById('ch-name'),
    chVerified: document.getElementById('ch-verified'),
    chSubs: document.getElementById('ch-subs'),
    chDesc: document.getElementById('ch-desc'),
    chVideosList: document.getElementById('ch-videos-list'),

    // Player Overlay
    overlayPlayer: document.getElementById('overlay-player'),
    playerVideoTitle: document.getElementById('player-video-title'),
    videoElement: document.getElementById('vault-video-element'),

    // Toast
    toastContainer: document.getElementById('toast-container')
};

// ── Bootstrap ─────────────────────────────────────────────────
const initializeApp = () => {
    setupFilterListeners();
    initPlyr();
    refreshLibrary();
    startPollingDownloads();
};

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeApp);
} else {
    initializeApp();
}

// ── Plyr Kurulum ──────────────────────────────────────────────
function initPlyr() {
    state.player = new Plyr(elements.videoElement, {
        // Tüm ekran boyutlarında gösterilecek kontroller (Plyr.io standart yerleşimi)
        controls: [
            'play-large',   // ortadaki büyük play butonu
            'play',         // sol alttaki play/pause
            'progress',     // ilerleme çubuğu
            'current-time', // geçen süre / kalan süre (tıklayarak geçiş yapılabilir)
            'mute',         // ses aç/kapat
            'volume',       // ses slider (masaüstü)
            'captions',     // altyazı
            'settings',     // hız ve diğer ayarlar (dişli çark)
            'pip',          // resim içinde resim (Picture-in-Picture)
            'fullscreen'    // tam ekran
        ],
        settings: ['speed'],
        speed: {
            selected: 1,
            options: [0.25, 0.5, 0.75, 1, 1.25, 1.5, 1.75, 2]
        },
        keyboard: { focused: true, global: false },
        tooltips: { controls: true, seek: true },
        autoplay: false,
        // Plyr SVG sprite lokal yokken inline SVG kullanır; loadSprite açık kalmalı
        // ancak path vermeyince CDN'e düşer — false yapıp ikon yerine emoji gösterir
        // Doğru davranış: true bırak, tarayıcı cache'ler
        loadSprite: true,
        iconUrl: '/static/plyr.svg',  // lokal sprite
        i18n: {
            play: 'Oynat',
            pause: 'Durdur',
            mute: 'Sesi Kapat',
            unmute: 'Sesi Aç',
            enterFullscreen: 'Tam Ekran',
            exitFullscreen: 'Tam Ekrandan Çık',
            settings: 'Ayarlar',
            speed: 'Hız',
            normal: 'Normal',
            rewind: '10 Saniye Geri',
            fastForward: '10 Saniye İleri',
            seek: 'Konum',
            seekLabel: '{seektime} konumuna git',
            played: 'Oynatıldı',
            buffered: 'Yüklendi',
            currentTime: 'Geçen süre',
            duration: 'Toplam süre',
            volume: 'Ses',
            enableCaptions: 'Altyazıyı Aç',
            disableCaptions: 'Altyazıyı Kapat',
        }
    });

    // Plyr hazır olduğunda position restore için dinleyici
    state.player.on('ready', () => {
        console.log('[Vault] Plyr hazır.');
    });
}

// ── Toast ─────────────────────────────────────────────────────
function showToast(message, type = 'primary') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    let icon = 'fa-info-circle';
    if (type === 'success') icon = 'fa-check-circle';
    if (type === 'error') icon = 'fa-exclamation-circle';

    toast.innerHTML = `<i class="fa-solid ${icon}"></i><span>${message}</span>`;
    elements.toastContainer.appendChild(toast);

    setTimeout(() => toast.classList.add('show'), 50);
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ── Tab Navigation ────────────────────────────────────────────
function switchTab(tabId) {
    state.activeTab = tabId;

    document.querySelectorAll('.nav-item').forEach(item => {
        const t = item.querySelector('span').textContent;
        item.classList.toggle('active',
            (tabId === 'search' && t === 'Ara') ||
            (tabId === 'library' && t === 'İndirilenler')
        );
    });

    document.querySelectorAll('.bottom-nav-item').forEach(item => {
        const t = item.querySelector('span').textContent;
        item.classList.toggle('active',
            (tabId === 'search' && t === 'Ara') ||
            (tabId === 'library' && t === 'İndirilenler')
        );
    });

    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));

    if (tabId === 'search') {
        document.getElementById('page-search').classList.add('active');
        elements.pageTitle.textContent = 'ARA';
    } else {
        document.getElementById('page-library').classList.add('active');
        elements.pageTitle.textContent = 'İNDİRİLENLER';
        refreshLibrary();
    }
}

// ── Filters ───────────────────────────────────────────────────
function setupFilterListeners() {
    ['type', 'date', 'sort'].forEach(group => {
        const container = document.getElementById(`filter-${group}`);
        if (!container) return;

        container.querySelectorAll('.filter-pill').forEach(pill => {
            pill.addEventListener('click', () => {
                container.querySelectorAll('.filter-pill').forEach(p => p.classList.remove('active'));
                pill.classList.add('active');
                state.filters[group] = pill.getAttribute('data-value');

                if (elements.searchQuery.value.trim()) performSearch();
            });
        });
    });
}

function handleSearchKeyPress(event) {
    if (event.key === 'Enter') performSearch();
}

// ── Search ────────────────────────────────────────────────────
async function performSearch() {
    const query = elements.searchQuery.value.trim();
    if (!query) { showToast('Lütfen arama terimi girin.', 'error'); return; }

    elements.searchLoading.style.display = 'block';
    elements.searchResults.innerHTML = '';

    try {
        const params = new URLSearchParams({
            q: query,
            type: state.filters.type,
            date: state.filters.date,
            sort: state.filters.sort
        });

        const response = await fetch(`/api/search?${params.toString()}`);
        if (!response.ok) throw new Error('Arama başarısız oldu.');

        renderSearchResults(await response.json());
    } catch (err) {
        showToast(err.message, 'error');
        elements.searchResults.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon-box"><i class="fa-solid fa-circle-exclamation" style="color:var(--error);"></i></div>
                <span class="empty-title">Arama Hatası</span>
                <span class="empty-desc">${err.message}</span>
            </div>`;
    } finally {
        elements.searchLoading.style.display = 'none';
    }
}

function renderSearchResults(results) {
    if (!results || results.length === 0) {
        elements.searchResults.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon-box"><i class="fa-solid fa-face-frown"></i></div>
                <span class="empty-title">Sonuç Bulunamadı</span>
                <span class="empty-desc">Sorgunuza veya filtrelerinize uygun sonuç bulunamadı.</span>
            </div>`;
        return;
    }

    results.forEach(item => {
        const card = document.createElement('div');
        card.className = 'result-card';

        if (item.type === 'channel') {
            const avatar = item.avatar || 'https://yt3.googleusercontent.com/default';
            card.innerHTML = `
                <img src="${avatar}" class="channel-card-avatar" alt="Avatar">
                <div class="media-info">
                    <div class="channel-title-row">
                        <span class="media-title" style="font-size:14px;font-weight:600;">${item.title}</span>
                        ${item.is_verified ? '<i class="fa-solid fa-circle-check verified-icon"></i>' : ''}
                    </div>
                    <span class="media-uploader">${item.subscribers} abone</span>
                    <span class="channel-info-desc">${item.description}</span>
                </div>
                <div class="download-action-btn" onclick="openChannelOverlay('${item.url}')" title="Kanalı Aç">
                    <i class="fa-solid fa-arrow-right"></i>
                </div>`;
            card.addEventListener('click', e => {
                if (!e.target.closest('.download-action-btn')) openChannelOverlay(item.url);
            });

        } else if (item.type === 'playlist') {
            card.innerHTML = `
                <div class="media-thumbnail-box playlist-thumbnail-box">
                    <i class="fa-solid fa-list-ul"></i>
                    <span class="duration-text">${item.video_count} video</span>
                </div>
                <div class="media-info">
                    <span class="media-title">${item.title}</span>
                    <span class="media-uploader">${item.uploader} · Oynatma Listesi</span>
                </div>
                <div class="download-action-btn" onclick="triggerDownload('${item.url}','${item.title.replace(/'/g, "\\'")}')">
                    <i class="fa-solid fa-cloud-arrow-down"></i>
                </div>`;
        } else {
            const playIcon = item.type === 'shorts' ? 'fa-bolt' : 'fa-play';
            card.innerHTML = `
                <div class="media-thumbnail-box">
                    <i class="fa-solid ${playIcon}"></i>
                    <span class="duration-text">${item.duration}</span>
                </div>
                <div class="media-info">
                    <span class="media-title">${item.title}</span>
                    <span class="media-uploader">${item.uploader}</span>
                </div>
                <div class="download-action-btn" onclick="triggerDownload('${item.url}','${item.title.replace(/'/g, "\\'")}')">
                    <i class="fa-solid fa-arrow-down"></i>
                </div>`;
        }

        elements.searchResults.appendChild(card);
    });
}

// ── Download ──────────────────────────────────────────────────
async function triggerDownload(url, title) {
    try {
        const response = await fetch('/api/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, title })
        });
        if (!response.ok) throw new Error('İndirme başlatılamadı.');

        showToast(`İndirme kuyruğuna eklendi: ${title.substring(0, 30)}...`, 'success');
        startPollingDownloads();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// ── Download Polling ──────────────────────────────────────────
function startPollingDownloads() {
    if (state.pollingInterval) return;
    pollDownloads();
    state.pollingInterval = setInterval(pollDownloads, 1000);
}

function stopPollingDownloads() {
    if (state.pollingInterval) {
        clearInterval(state.pollingInterval);
        state.pollingInterval = null;
    }
}

async function pollDownloads() {
    try {
        const response = await fetch('/api/downloads');
        if (!response.ok) throw new Error('İndirme durumları alınamadı.');

        const downloads = await response.json();
        state.activeDownloads = downloads;

        const running = downloads.filter(d => d.status === 'downloading' || d.status === 'pending');
        elements.activeDownloadsCount.textContent = running.length;
        elements.activeDownloadsCount.style.display = running.length > 0 ? 'flex' : 'none';

        if (state.activeTab === 'library') renderActiveDownloads(downloads);
        if (running.length === 0 && downloads.length === 0) stopPollingDownloads();
    } catch (err) {
        console.error(err);
    }
}

function renderActiveDownloads(downloads) {
    if (!downloads || downloads.length === 0) {
        elements.activeDownloadsList.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon-box"><i class="fa-solid fa-circle-check"></i></div>
                <span class="empty-title">Aktif İndirme Yok</span>
                <span class="empty-desc">Şu anda devam eden herhangi bir indirme bulunmuyor.</span>
            </div>`;
        return;
    }

    elements.activeDownloadsList.innerHTML = '';

    downloads.forEach(d => {
        const item = document.createElement('div');
        item.className = 'download-item';

        const pct = Math.round((d.progress || 0) * 100);
        let statusText = 'Hazırlanıyor...';
        let statusColor = '';

        if (d.status === 'downloading') {
            statusText = `%${pct} · ${d.speed || '—'} · Kalan: ${d.eta || '—'}`;
        } else if (d.status === 'finished') {
            statusText = 'Tamamlandı';
            statusColor = 'color:var(--success);';
        } else if (d.status === 'failed') {
            if (!d.error.includes('exit')) {
                statusText = `Hata: ${d.error || 'Bilinmiyor'}`;
                statusColor = 'color:var(--error);';
            }
        }

        item.innerHTML = `
            <div class="download-item-thumb"><i class="fa-solid fa-film"></i></div>
            <div class="download-item-info">
                <span class="download-item-title">${d.title}</span>
                <div class="download-progress-bar">
                    <div class="download-progress-fill" style="width:${pct}%"></div>
                </div>
                <span class="download-item-status" style="${statusColor}">${statusText}</span>
            </div>`;

        elements.activeDownloadsList.appendChild(item);
    });
}

// ── Library ───────────────────────────────────────────────────
async function refreshLibrary() {
    try {
        const response = await fetch('/api/library');
        if (!response.ok) throw new Error('Kütüphane alınamadı.');
        const files = await response.json();
        state.library = files;

        const posResponse = await fetch('/api/library/positions');
        if (posResponse.ok) state.playbackPositions = await posResponse.json();

        renderLibraryGrid(files);
    } catch (err) {
        showToast(err.message, 'error');
    }
}

function renderLibraryGrid(files) {
    if (!files || files.length === 0) {
        elements.libraryVideosList.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon-box"><i class="fa-solid fa-video-slash"></i></div>
                <span class="empty-title">Kütüphane Boş</span>
                <span class="empty-desc">İndirdiğiniz videolar burada listelenir.</span>
            </div>`;
        return;
    }

    elements.libraryVideosList.innerHTML = '';

    files.forEach(f => {
        const card = document.createElement('div');
        card.className = 'lib-card';

        const savedMs = state.playbackPositions[f.filepath] || 0;
        const posLabel = savedMs > 0 ? `<span class="lib-meta-sep">·</span>${formatTime(savedMs / 1000)} konumunda` : '';
        const progressPct = savedMs > 0 && f.duration
            ? Math.min((savedMs / 1000) / f.duration * 100, 100)
            : 0;

        card.innerHTML = `
            <div class="lib-thumbnail">
                <i class="fa-solid fa-film"></i>
                ${progressPct > 0 ? `<div class="lib-progress-bar" style="width:${progressPct}%"></div>` : ''}
            </div>
            <div class="lib-info">
                <span class="lib-title" title="${f.filename}">${f.filename.replace(/\.[^/.]+$/, '')}</span>
                <div class="lib-meta">
                    <span>${formatBytes(f.size)}</span>
                    ${posLabel}
                </div>
            </div>
            <div class="lib-actions">
                <div class="lib-btn-delete" onclick="deleteVideo(event,'${f.filename.replace(/'/g, "\\'")}')">
                    <i class="fa-solid fa-trash-can"></i>
                </div>
            </div>`;

        card.addEventListener('click', e => {
            if (!e.target.closest('.lib-btn-delete')) playVideo(f.filename);
        });

        elements.libraryVideosList.appendChild(card);
    });
}

async function deleteVideo(e, filename) {
    if (e) { e.preventDefault(); e.stopPropagation(); }
    if (!confirm(`"${filename}" videosunu silmek istediğinizden emin misiniz?`)) return;

    try {
        const response = await fetch(`/api/library/${encodeURIComponent(filename)}`, { method: 'DELETE' });
        if (!response.ok) throw new Error('Video silinemedi.');
        showToast('Video başarıyla silindi.', 'success');
        refreshLibrary();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// ── Video Player (Plyr) ───────────────────────────────────────
let savePositionInterval = null;

async function playVideo(filename) {
    const file = state.library.find(f => f.filename === filename);
    if (!file) return;

    state.currentPlayingFile = file.filepath;
    elements.playerVideoTitle.textContent = filename.replace(/\.[^/.]+$/, '');

    // Overlay aç
    elements.overlayPlayer.classList.add('active');

    // Kaydedilmiş pozisyonu geri yükle
    const savedMs = state.playbackPositions[file.filepath] || 0;

    state.player.once('ready', () => {
        if (savedMs > 0) {
            // Küçük bir gecikme iframe ve mobil tarayıcılarda senkronizasyon sağlar
            setTimeout(() => {
                state.player.currentTime = savedMs / 1000;
                showToast(`${formatTime(savedMs / 1000)} konumundan devam ettiriliyor.`, 'success');

                // Oynatma işlemini süre değişiminden sonra tetikleyin
                state.player.play().catch(error => {
                    console.log("Tarayıcı otomatik oynatmayı engelledi, kullanıcı etkileşimi bekleniyor.");
                });
            }, 100);
        } else {
            state.player.play().catch(() => { });
        }
    });


    // Plyr source güncelle (bu canplay olayını tetikleyecek)
    state.player.source = {
        type: 'video',
        sources: [{
            src: `/video/${encodeURIComponent(filename)}`,
            type: 'video/mp4'
        }]
    };

    // Pozisyon kaydetme döngüsünü başlat (2 sn'de bir)
    if (savePositionInterval) clearInterval(savePositionInterval);
    savePositionInterval = setInterval(saveCurrentPlaybackPosition, 2000);
}

async function saveCurrentPlaybackPosition() {
    if (!state.currentPlayingFile || !state.player || state.player.paused) return;

    const posMs = Math.round(state.player.currentTime * 1000);
    if (posMs <= 0) return;

    try {
        await fetch('/api/library/position', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filepath: state.currentPlayingFile, position_ms: posMs })
        });
        state.playbackPositions[state.currentPlayingFile] = posMs;
    } catch (err) {
        console.error('Position save error:', err);
    }
}

function closePlayer() {
    // Pozisyon kaydetme döngüsünü durdur
    if (savePositionInterval) {
        clearInterval(savePositionInterval);
        savePositionInterval = null;
    }

    // Son pozisyonu kaydet
    if (state.currentPlayingFile) saveCurrentPlaybackPosition();

    // Plyr'ı durdur ve kaynağı temizle
    if (state.player) {
        state.player.pause();
        state.player.source = { type: 'video', sources: [{ src: '', type: 'video/mp4' }] };
    }

    // Overlay kapat
    elements.overlayPlayer.classList.remove('active');
    state.currentPlayingFile = '';

    // Kütüphaneyi güncelle (pozisyon etiketi yenilenir)
    refreshLibrary();
}

// ── Channel Overlay ───────────────────────────────────────────
async function openChannelOverlay(url) {
    state.currentChannelUrl = url;
    state.currentChannelSort = 'latest';

    document.querySelectorAll('.channel-sort-tab').forEach(t => {
        t.classList.toggle('active', t.getAttribute('data-sort') === 'latest');
    });

    elements.overlayChannel.classList.add('active');
    elements.chVideosList.innerHTML = '<div class="channel-loading">Yükleniyor...</div>';

    try {
        const response = await fetch(`/api/channel?url=${encodeURIComponent(url)}`);
        if (!response.ok) throw new Error('Kanal bilgileri alınamadı.');

        const data = await response.json();

        if (data.banner) {
            elements.chBanner.src = data.banner;
            elements.chBanner.style.display = 'block';
        }
        elements.chAvatar.src = data.avatar || '';
        elements.chName.childNodes[0].textContent = data.name || 'Kanal Adı';
        elements.chVerified.style.display = data.is_verified ? 'inline' : 'none';
        elements.chSubs.textContent = data.subscribers ? `${data.subscribers} Abone` : '';
        elements.chDesc.textContent = data.description || 'Açıklama bulunmuyor.';

        renderChannelVideos(data.videos || []);
    } catch (err) {
        showToast(err.message, 'error');
        elements.chVideosList.innerHTML = `<div class="empty-state"><span class="empty-title">Hata</span><span class="empty-desc">${err.message}</span></div>`;
    }
}

function closeChannelOverlay() {
    elements.overlayChannel.classList.remove('active');
    state.currentChannelUrl = '';
}

function sortChannelVideos(sort) {
    state.currentChannelSort = sort;
    document.querySelectorAll('.channel-sort-tab').forEach(t => {
        t.classList.toggle('active', t.getAttribute('data-sort') === sort);
    });
    openChannelOverlay(state.currentChannelUrl);
}

function renderChannelVideos(videos) {
    if (!videos || videos.length === 0) {
        elements.chVideosList.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon-box"><i class="fa-solid fa-video-slash"></i></div>
                <span class="empty-title">Video Bulunamadı</span>
            </div>`;
        return;
    }

    elements.chVideosList.innerHTML = '';

    videos.forEach(v => {
        const item = document.createElement('div');
        item.className = 'channel-video-item';
        item.innerHTML = `
            <div class="media-thumbnail-box" style="width:90px;height:52px;flex-shrink:0;">
                <i class="fa-solid fa-play"></i>
                <span class="duration-text">${v.duration || ''}</span>
            </div>
            <div class="media-info">
                <span class="media-title" style="font-size:12px;">${v.title}</span>
                <span class="media-uploader">${v.view_count || ''}</span>
            </div>
            <div class="download-action-btn" onclick="triggerDownload('${v.url}','${v.title.replace(/'/g, "\\'")}')">
                <i class="fa-solid fa-arrow-down"></i>
            </div>`;
        elements.chVideosList.appendChild(item);
    });
}

// ── Helpers ───────────────────────────────────────────────────
function formatBytes(bytes) {
    if (!bytes) return '—';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1073741824) return `${(bytes / 1048576).toFixed(1)} MB`;
    return `${(bytes / 1073741824).toFixed(2)} GB`;
}

function formatTime(seconds) {
    if (!seconds || isNaN(seconds)) return '0:00';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    return `${m}:${String(s).padStart(2, '0')}`;
}