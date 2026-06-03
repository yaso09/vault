// Vault JavaScript Application Logic

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
    playbackPositions: {}
};

// DOM Elements
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
    
    // Toast Container
    toastContainer: document.getElementById('toast-container')
};

// Initial Setup
const initializeApp = () => {
    setupFilterListeners();
    refreshLibrary();
    startPollingDownloads(); // Start initial poll to check if anything is running
};

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeApp);
} else {
    initializeApp();
}

// Toast Helper
function showToast(message, type = 'primary') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    let icon = 'fa-info-circle';
    if (type === 'success') icon = 'fa-check-circle';
    if (type === 'error') icon = 'fa-exclamation-circle';
    
    toast.innerHTML = `
        <i class="fa-solid ${icon}"></i>
        <span>${message}</span>
    `;
    
    elements.toastContainer.appendChild(toast);
    
    // Animate in
    setTimeout(() => toast.classList.add('show'), 50);
    
    // Remove after 3 seconds
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Tab Navigation
function switchTab(tabId) {
    state.activeTab = tabId;
    
    // Update Sidebar Active state
    document.querySelectorAll('.nav-item').forEach(item => {
        const spanText = item.querySelector('span').textContent;
        if ((tabId === 'search' && spanText === 'Ara') || 
            (tabId === 'library' && spanText === 'İndirilenler')) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });

    // Update Bottom Nav Active state
    document.querySelectorAll('.bottom-nav-item').forEach(item => {
        const spanText = item.querySelector('span').textContent;
        if ((tabId === 'search' && spanText === 'Ara') || 
            (tabId === 'library' && spanText === 'İndirilenler')) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });

    // Toggle pages
    document.querySelectorAll('.page').forEach(page => {
        page.classList.remove('active');
    });
    
    if (tabId === 'search') {
        document.getElementById('page-search').classList.add('active');
        elements.pageTitle.textContent = 'ARA';
    } else {
        document.getElementById('page-library').classList.add('active');
        elements.pageTitle.textContent = 'İNDİRİLENLER';
        refreshLibrary();
    }
}

// Filter Pills Logic
function setupFilterListeners() {
    const groups = ['type', 'date', 'sort'];
    groups.forEach(group => {
        const container = document.getElementById(`filter-${group}`);
        if (!container) return;
        
        container.querySelectorAll('.filter-pill').forEach(pill => {
            pill.addEventListener('click', () => {
                container.querySelectorAll('.filter-pill').forEach(p => p.classList.remove('active'));
                pill.classList.add('active');
                state.filters[group] = pill.getAttribute('data-value');
                
                // Proactively run search if there's already a query
                if (elements.searchQuery.value.trim()) {
                    performSearch();
                }
            });
        });
    });
}

// Handle KeyPress on Search Input
function handleSearchKeyPress(event) {
    if (event.key === 'Enter') {
        performSearch();
    }
}

// Perform Search
async function performSearch() {
    const query = elements.searchQuery.value.trim();
    if (!query) {
        showToast('Lütfen arama terimi girin.', 'error');
        return;
    }
    
    // Show Loading
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
        
        const results = await response.json();
        renderSearchResults(results);
    } catch (err) {
        showToast(err.message, 'error');
        elements.searchResults.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon-box"><i class="fa-solid fa-circle-exclamation" style="color: var(--error);"></i></div>
                <span class="empty-title">Arama Hatası</span>
                <span class="empty-desc">${err.message}</span>
            </div>
        `;
    } finally {
        elements.searchLoading.style.display = 'none';
    }
}

// Render Search Results
function renderSearchResults(results) {
    if (!results || results.length === 0) {
        elements.searchResults.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon-box"><i class="fa-solid fa-face-frown"></i></div>
                <span class="empty-title">Sonuç Bulunamadı</span>
                <span class="empty-desc">Sorgunuza veya filtrelerinize uygun sonuç bulunamadı.</span>
            </div>
        `;
        return;
    }
    
    results.forEach(item => {
        let card = document.createElement('div');
        card.className = 'result-card';
        
        if (item.type === 'channel') {
            const avatar = item.avatar || 'https://yt3.googleusercontent.com/default';
            card.innerHTML = `
                <img src="${avatar}" class="channel-card-avatar" alt="Avatar">
                <div class="media-info">
                    <div class="channel-title-row">
                        <span class="media-title" style="font-size:14px; font-weight:600;">${item.title}</span>
                        ${item.is_verified ? '<i class="fa-solid fa-circle-check verified-icon"></i>' : ''}
                    </div>
                    <span class="media-uploader">${item.subscribers} abone</span>
                    <span class="channel-info-desc">${item.description}</span>
                </div>
                <div class="download-action-btn" onclick="openChannelOverlay('${item.url}')" title="Kanalı Aç">
                    <i class="fa-solid fa-arrow-right"></i>
                </div>
            `;
            card.addEventListener('click', (e) => {
                if (!e.target.closest('.download-action-btn')) {
                    openChannelOverlay(item.url);
                }
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
                <div class="download-action-btn" onclick="triggerDownload('${item.url}', '${item.title.replace(/'/g, "\\'")}')" title="Listeyi İndir">
                    <i class="fa-solid fa-cloud-arrow-down"></i>
                </div>
            `;
        } else {
            // Standard Video / Shorts
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
                <div class="download-action-btn" onclick="triggerDownload('${item.url}', '${item.title.replace(/'/g, "\\'")}')" title="İndir">
                    <i class="fa-solid fa-arrow-down"></i>
                </div>
            `;
        }
        
        elements.searchResults.appendChild(card);
    });
}

// Trigger Download
async function triggerDownload(url, title) {
    try {
        const response = await fetch('/api/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, title })
        });
        
        if (!response.ok) throw new Error('İndirme başlatılamadı.');
        
        showToast(`İndirme kuyruğuna eklendi: ${title.substring(0, 30)}...`, 'success');
        
        // Start polling immediately to show progress
        startPollingDownloads();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// Download Polling
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
        
        // Update badge counts
        const running = downloads.filter(d => d.status === 'downloading' || d.status === 'pending');
        elements.activeDownloadsCount.textContent = running.length;
        
        if (running.length > 0) {
            elements.activeDownloadsCount.style.display = 'flex';
        } else {
            elements.activeDownloadsCount.style.display = 'none';
        }
        
        // If on Library tab, render
        if (state.activeTab === 'library') {
            renderActiveDownloads(downloads);
        }
        
        // If there are zero active downloads, stop polling eventually
        if (running.length === 0 && downloads.length === 0) {
            stopPollingDownloads();
        }
    } catch (err) {
        console.error(err);
    }
}

// Render Active Downloads
function renderActiveDownloads(downloads) {
    if (!downloads || downloads.length === 0) {
        elements.activeDownloadsList.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon-box"><i class="fa-solid fa-circle-check"></i></div>
                <span class="empty-title">Aktif İndirme Yok</span>
                <span class="empty-desc">Şu anda devam eden herhangi bir indirme bulunmuyor.</span>
            </div>
        `;
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
            statusColor = 'color: var(--success);';
        } else if (d.status === 'failed') {
            statusText = `Hata: ${d.error || 'Bilinmiyor'}`;
            statusColor = 'color: var(--error);';
        }
        
        item.innerHTML = `
            <div class="download-item-thumb">
                <i class="fa-solid fa-film"></i>
            </div>
            <div class="download-item-info">
                <span class="download-item-title">${d.title}</span>
                <div class="download-progress-bar">
                    <div class="download-progress-fill" style="width: ${pct}%"></div>
                </div>
                <span class="download-item-status" style="${statusColor}">${statusText}</span>
            </div>
        `;
        
        elements.activeDownloadsList.appendChild(item);
    });
}

// Refresh Library (Downloaded videos)
async function refreshLibrary() {
    try {
        const response = await fetch('/api/library');
        if (!response.ok) throw new Error('Kütüphane alınamadı.');
        
        const files = await response.json();
        state.library = files;
        
        // Fetch saved positions as well
        const posResponse = await fetch('/api/library/positions');
        if (posResponse.ok) {
            state.playbackPositions = await posResponse.json();
        }
        
        renderLibraryGrid(files);
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// Render Library
function renderLibraryGrid(files) {
    if (!files || files.length === 0) {
        elements.libraryVideosList.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon-box"><i class="fa-solid fa-video-slash"></i></div>
                <span class="empty-title">Kütüphane Boş</span>
                <span class="empty-desc">İndirdiğiniz videolar burada listelenir.</span>
            </div>
        `;
        return;
    }
    
    elements.libraryVideosList.innerHTML = '';
    
    files.forEach(f => {
        const card = document.createElement('div');
        card.className = 'lib-card';
        
        const savedMs = state.playbackPositions[f.filepath] || 0;
        const posLabel = savedMs > 0 ? `<span class="lib-meta-sep">·</span>${formatTime(savedMs / 1000)} konumunda` : '';
        const progressPct = savedMs > 0 && f.duration ? Math.min((savedMs / 1000) / f.duration * 100, 100) : 0;
        
        card.innerHTML = `
            <div class="lib-thumbnail">
                <i class="fa-solid fa-film"></i>
                ${progressPct > 0 ? `<div class="lib-progress-bar" style="width:${progressPct}%"></div>` : ''}
            </div>
            <div class="lib-info">
                <span class="lib-title" title="${f.filename}">${f.filename.replace(/\.[^/.]+$/, "")}</span>
                <div class="lib-meta">
                    <span>${formatBytes(f.size)}</span>
                    ${posLabel}
                </div>
            </div>
            <div class="lib-actions">
                <div class="lib-btn-delete" onclick="deleteVideo(event, '${f.filename.replace(/'/g, "\\'")}')" title="Sil">
                    <i class="fa-solid fa-trash-can"></i>
                </div>
            </div>
        `;
        
        card.addEventListener('click', (e) => {
            if (!e.target.closest('.lib-btn-delete')) {
                playVideo(f.filename);
            }
        });
        
        elements.libraryVideosList.appendChild(card);
    });
}

// Delete Video (Safe implementation with event propagation prevention)
async function deleteVideo(e, filename) {
    if (e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
    if (!confirm(`"${filename}" videosunu silmek istediğinizden emin misiniz?`)) return;
    
    try {
        const response = await fetch(`/api/library/${encodeURIComponent(filename)}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) throw new Error('Video silinemedi.');
        
        showToast('Video başarıyla silindi.', 'success');
        refreshLibrary();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

// Play Video
let savePositionInterval = null;

async function playVideo(filename) {
    // Find the file path from state
    const file = state.library.find(f => f.filename === filename);
    if (!file) return;
    
    state.currentPlayingFile = file.filepath;
    elements.playerVideoTitle.textContent = filename.replace(/\.[^/.]+$/, "");
    
    // Set video source
    elements.videoElement.src = `/video/${encodeURIComponent(filename)}`;
    
    // Open player modal overlay
    elements.overlayPlayer.classList.add('active');
    
    // Try to restore playback position
    const savedMs = state.playbackPositions[file.filepath] || 0;
    
    elements.videoElement.onloadedmetadata = () => {
        if (savedMs > 0) {
            elements.videoElement.currentTime = savedMs / 1000;
            showToast(`Video ${formatTime(savedMs / 1000)} konumundan devam ettiriliyor.`, 'success');
        }
    };
    
    // Set up position saving interval (every 2 seconds)
    if (savePositionInterval) clearInterval(savePositionInterval);
    savePositionInterval = setInterval(saveCurrentPlaybackPosition, 2000);
}

// Save Playback Position
async function saveCurrentPlaybackPosition() {
    if (!state.currentPlayingFile || elements.videoElement.paused) return;
    
    const posMs = Math.round(elements.videoElement.currentTime * 1000);
    
    try {
        await fetch('/api/library/position', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                filepath: state.currentPlayingFile,
                position_ms: posMs
            })
        });
        
        // Cache locally in state
        state.playbackPositions[state.currentPlayingFile] = posMs;
    } catch (err) {
        console.error("Position save error:", err);
    }
}

// Close Video Player
function closePlayer() {
    // Clear save interval
    if (savePositionInterval) {
        clearInterval(savePositionInterval);
        savePositionInterval = null;
    }
    
    // Save one final position
    if (state.currentPlayingFile) {
        saveCurrentPlaybackPosition();
    }
    
    // Stop video
    elements.videoElement.pause();
    elements.videoElement.src = '';
    
    // Hide overlay
    elements.overlayPlayer.classList.remove('active');
    
    state.currentPlayingFile = '';
    
    // Refresh library list to display updated playback positions
    refreshLibrary();
}

// Channel Overlay Browsing
async function openChannelOverlay(url) {
    state.currentChannelUrl = url;
    state.currentChannelSort = 'latest';
    
    // Set sorting tabs
    document.querySelectorAll('.channel-sort-tab').forEach(t => {
        if (t.getAttribute('data-sort') === 'latest') t.classList.add('active');
        else t.classList.remove('active');
    });
    
    // Show Overlay
    elements.overlayChannel.classList.add('active');
    elements.chVideosList.innerHTML = `<div style="text-align:center; padding: 40px; color:var(--text-sec);"><i class="fa-solid fa-spinner fa-spin" style="font-size:24px; margin-bottom:8px;"></i><br>Kanal yükleniyor...</div>`;
    
    elements.chBanner.style.display = 'none';
    elements.chName.innerHTML = 'Kanal Yükleniyor...';
    elements.chSubs.textContent = '';
    elements.chDesc.textContent = '';
    
    loadChannelData();
}

async function loadChannelData() {
    try {
        const params = new URLSearchParams({
            url: state.currentChannelUrl,
            sort_by: state.currentChannelSort
        });
        
        const response = await fetch(`/api/channel?${params.toString()}`);
        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || 'Kanal yüklenemedi.');
        }
        
        const data = await response.json();
        
        // Render Header
        if (data.banner) {
            elements.chBanner.src = data.banner;
            elements.chBanner.style.display = 'block';
        } else {
            elements.chBanner.style.display = 'none';
        }
        
        elements.chAvatar.src = data.avatar || 'https://yt3.googleusercontent.com/default';
        elements.chName.innerHTML = `${data.name} ${data.is_verified ? '<i class="fa-solid fa-circle-check verified-icon" id="ch-verified"></i>' : ''}`;
        elements.chSubs.textContent = `${data.subscribers} abone · ${data.video_count} video`;
        elements.chDesc.textContent = data.description || 'Açıklama bulunmuyor.';
        
        // Render Videos
        renderChannelVideos(data.videos);
    } catch (err) {
        showToast(err.message, 'error');
        elements.chVideosList.innerHTML = `<div style="text-align:center; padding: 40px; color:var(--error);"><i class="fa-solid fa-circle-exclamation" style="font-size:24px; margin-bottom:8px;"></i><br>${err.message}</div>`;
    }
}

function renderChannelVideos(videos) {
    if (!videos || videos.length === 0) {
        elements.chVideosList.innerHTML = `<div style="text-align:center; padding: 40px; color:var(--text-dim);">Videolar yüklenemedi veya kanalda video yok.</div>`;
        return;
    }
    
    elements.chVideosList.innerHTML = '';
    
    videos.forEach(v => {
        const item = document.createElement('div');
        item.className = 'result-card';
        item.innerHTML = `
            <div class="media-thumbnail-box">
                <i class="fa-solid fa-play"></i>
                <span class="duration-text">${v.duration}</span>
            </div>
            <div class="media-info">
                <span class="media-title">${v.title}</span>
                <span class="media-uploader">${v.uploader}</span>
            </div>
            <div class="download-action-btn" onclick="triggerDownload('${v.url}', '${v.title.replace(/'/g, "\\'")}')" title="İndir">
                <i class="fa-solid fa-arrow-down"></i>
            </div>
        `;
        elements.chVideosList.appendChild(item);
    });
}

function sortChannelVideos(sortType) {
    if (state.currentChannelSort === sortType) return;
    
    state.currentChannelSort = sortType;
    
    document.querySelectorAll('.channel-sort-tab').forEach(t => {
        if (t.getAttribute('data-sort') === sortType) t.classList.add('active');
        else t.classList.remove('active');
    });
    
    elements.chVideosList.innerHTML = `<div style="text-align:center; padding: 40px; color:var(--text-sec);"><i class="fa-solid fa-spinner fa-spin" style="font-size:24px; margin-bottom:8px;"></i><br>Yeniden sıralanıyor...</div>`;
    loadChannelData();
}

function closeChannelOverlay() {
    elements.overlayChannel.classList.remove('active');
    state.currentChannelUrl = '';
}

// Helpers for format sizes and times
function formatBytes(bytes, decimals = 2) {
    if (!+bytes) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))} ${sizes[i]}`;
}

function formatTime(seconds) {
    if (isNaN(seconds) || seconds === null) return '—';
    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    if (hrs > 0) {
        return `${hrs}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}
