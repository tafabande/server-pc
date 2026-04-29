/**
 * StreamDrop — Reactive Material 3 Client
 */

class StreamDropApp {
    constructor() {
        this.currentPath = "";
        this.allFiles = [];
        this.filteredFiles = [];
        this.activeFilter = "all"; // "all" or "favorites"
        this.searchQuery = "";
        
        // Player State
        this.currentPlaylist = [];
        this.currentVideoIndex = 0;
        this.hideControlsTimeout = null;

        // UI Elements
        this.gallery = document.getElementById('gallery');
        this.searchInput = document.getElementById('searchInput');
        this.clearSearch = document.getElementById('clearSearch');
        this.breadcrumbs = document.getElementById('breadcrumbs');
        this.emptyState = document.getElementById('emptyState');
        this.fileInput = document.getElementById('fileInput');
        this.uploadFab = document.getElementById('uploadFab');
        this.filterChips = document.querySelectorAll('.chip');

        // Player UI Elements
        this.video = document.getElementById('main-video');
        this.playerContainer = document.getElementById('player-container');
        this.playerUI = document.getElementById('player-ui');
        this.playerTitle = document.getElementById('player-title');
        this.playBtn = document.getElementById('play-pause-btn');
        this.playIcon = document.getElementById('play-icon');
        this.seekBar = document.getElementById('seek-bar');
        this.timeDisplay = document.getElementById('time-display');
        this.speedIndicator = document.getElementById('speed-indicator');
        this.closePlayerBtn = document.getElementById('closePlayerBtn');
        this.prevBtn = document.getElementById('prevBtn');
        this.nextBtn = document.getElementById('nextBtn');
        this.fullscreenBtn = document.getElementById('fullscreenBtn');
        this.shutdownBtn = document.getElementById('shutdownBtn');
        this.streamToggleBtn = document.getElementById('streamToggleBtn');

        // New PWA Action Buttons
        this.favBtn = document.getElementById('fav-btn');
        this.favIcon = document.getElementById('fav-icon');
        this.downloadBtn = document.getElementById('downloadCurrentBtn');
        
        this.localFavorites = JSON.parse(localStorage.getItem('media_favorites')) || [];

        this.init();
    }

    async init() {
        this.setupEventListeners();
        this.setupPlayerEvents();
        this.connectWebSocket();
        await this.loadGallery();
    }

    setupEventListeners() {
        // Search
        this.searchInput.addEventListener('input', (e) => {
            this.searchQuery = e.target.value.toLowerCase();
            this.clearSearch.style.display = this.searchQuery ? 'block' : 'none';
            this.applyFilters();
        });

        this.clearSearch.addEventListener('click', () => {
            this.searchInput.value = '';
            this.searchQuery = '';
            this.clearSearch.style.display = 'none';
            this.applyFilters();
        });

        // Filters
        this.filterChips.forEach(chip => {
            chip.addEventListener('click', async () => {
                const filter = chip.dataset.filter;
                if (this.activeFilter === filter) return;

                this.activeFilter = filter;
                this.filterChips.forEach(c => c.classList.toggle('active', c === chip));
                
                await this.loadGallery();
            });
        });

        // Upload
        this.uploadFab.addEventListener('click', () => this.fileInput.click());
        this.fileInput.addEventListener('change', (e) => this.handleUpload(e));

        // Server Controls
        this.shutdownBtn.addEventListener('click', () => this.handleShutdown());
        this.streamToggleBtn.addEventListener('click', () => this.handleStreamToggle());

        // Global Back Navigation
        window.addEventListener('popstate', (e) => {
            this.currentPath = e.state?.path || "";
            this.loadGallery(false);
        });
    }

    setupPlayerEvents() {
        // Player Controls
        this.playBtn.addEventListener('click', () => {
            this.video.paused ? this.video.play() : this.video.pause();
        });

        this.closePlayerBtn.addEventListener('click', () => this.closePlayer());
        this.prevBtn.addEventListener('click', () => this.playPrev());
        this.nextBtn.addEventListener('click', () => this.playNext());
        this.fullscreenBtn.addEventListener('click', () => this.toggleFullscreen());
        this.favBtn.addEventListener('click', () => this.toggleLocalFavorite());
        this.downloadBtn.addEventListener('click', () => this.downloadCurrent());

        // Video State
        this.video.addEventListener('play', () => this.playIcon.innerText = 'pause');
        this.video.addEventListener('pause', () => this.playIcon.innerText = 'play_arrow');
        this.video.addEventListener('ended', () => this.playNext());

        this.video.addEventListener('timeupdate', () => {
            if (this.video.duration) {
                const percent = (this.video.currentTime / this.video.duration) * 100;
                this.seekBar.value = percent;
                this.timeDisplay.innerText = `${this.formatTime(this.video.currentTime)} / ${this.formatTime(this.video.duration)}`;
            }
        });

        // Scrubbing
        this.seekBar.addEventListener('input', (e) => {
            if (this.video.duration) {
                const time = (e.target.value / 100) * this.video.duration;
                this.video.currentTime = time;
            }
        });

        // Fast Forward (2x)
        const enableFF = () => {
            this.video.playbackRate = 2.0;
            this.speedIndicator.classList.add('active');
        };
        const disableFF = () => {
            this.video.playbackRate = 1.0;
            this.speedIndicator.classList.remove('active');
        };

        const isControl = (el) => el.closest('.icon-btn') || el.closest('#seek-bar');

        this.playerContainer.addEventListener('mousedown', (e) => {
            if (!isControl(e.target)) enableFF();
        });
        window.addEventListener('mouseup', disableFF);

        this.playerContainer.addEventListener('touchstart', (e) => {
            if (!isControl(e.target)) enableFF();
        }, { passive: true });
        window.addEventListener('touchend', disableFF);

        // Auto-Hide Controls
        const resetIdle = () => this.resetIdleTimer();
        this.playerContainer.addEventListener('mousemove', resetIdle);
        this.playerContainer.addEventListener('touchstart', resetIdle, { passive: true });
        this.playerContainer.addEventListener('click', resetIdle);
    }

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.type === 'update') {
                    console.log("🔄 Real-time update received");
                    this.loadGallery();
                }
            } catch (e) {
                // Handle raw string messages for backward compatibility
                if (event.data === "UPDATE") {
                    this.loadGallery();
                }
            }
        };

        ws.onclose = () => {
            console.warn("🔌 WebSocket disconnected. Reconnecting in 3s...");
            setTimeout(() => this.connectWebSocket(), 3000);
        };
    }

    async loadGallery(pushState = true) {
        let url = this.activeFilter === 'favorites' 
            ? '/api/favorites' 
            : `/api/files/${encodeURIComponent(this.currentPath)}`;

        try {
            const response = await fetch(url);
            const data = await response.json();
            this.allFiles = data.items || [];
            
            // Build current playlist (only videos)
            this.currentPlaylist = this.allFiles.filter(f => f.type === 'video');

            if (pushState && this.activeFilter === 'all') {
                history.pushState({ path: this.currentPath }, '', `?path=${this.currentPath}`);
            }

            this.applyFilters();
            this.renderBreadcrumbs();
        } catch (error) {
            console.error("Failed to load gallery:", error);
        }
    }

    applyFilters() {
        this.filteredFiles = this.allFiles.filter(file => {
            const matchesSearch = file.name.toLowerCase().includes(this.searchQuery);
            return matchesSearch;
        });

        this.renderGallery();
    }

    renderGallery() {
        this.gallery.innerHTML = '';
        
        if (this.filteredFiles.length === 0) {
            this.emptyState.style.display = 'flex';
            return;
        }

        this.emptyState.style.display = 'none';

        this.filteredFiles.forEach(file => {
            const card = document.createElement('div');
            card.className = 'media-card';
            
            const isFolder = file.is_dir;
            const isVideo = file.type === 'video';
            
            // Thumbnail / Icon / Avatar logic
            let content = '';
            if (isFolder) {
                const initials = this.getInitials(file.name);
                content = `<div class="folder-avatar">${initials}</div>`;
            } else if (file.thumbnail_url) {
                content = `<img src="${file.thumbnail_url}" loading="lazy" alt="${file.name}" onerror="this.src='/static/img/fallback.png'; this.onerror=null;">`;
            } else {
                const icon = this.getFileIcon(file.type);
                content = `<span class="material-symbols-rounded" style="font-size: 48px; opacity: 0.3;">${icon}</span>`;
            }

            const videoOverlay = isVideo ? `<div class="icon-overlay"><span class="material-symbols-rounded">play_arrow</span></div>` : '';
            const favClass = file.is_favorite ? 'active' : '';

            card.innerHTML = `
                <div class="fav-btn ${favClass}" onclick="event.stopPropagation(); app.toggleFav('${file.filename}')">
                    <span class="material-symbols-rounded" style="font-variation-settings: 'FILL' ${file.is_favorite ? 1 : 0}">star</span>
                </div>
                <div class="card-media">
                    ${content}
                </div>
                ${videoOverlay}
                <div class="info">${file.name}</div>
            `;

            card.onclick = () => this.handleItemClick(file);
            this.gallery.appendChild(card);
        });
    }

    renderBreadcrumbs() {
        if (this.activeFilter === 'favorites') {
            this.breadcrumbs.innerHTML = '<span class="breadcrumb-item">Favorites</span>';
            return;
        }

        const parts = this.currentPath.split('/').filter(p => p);
        let html = `<span class="breadcrumb-item" onclick="app.navigate('')">Home</span>`;
        
        let pathAccumulator = "";
        parts.forEach((part, i) => {
            pathAccumulator += (i === 0 ? '' : '/') + part;
            const current = pathAccumulator;
            html += ` <span class="material-symbols-rounded" style="font-size:16px;">chevron_right</span> `;
            html += `<span class="breadcrumb-item" onclick="app.navigate('${current}')">${part}</span>`;
        });

        this.breadcrumbs.innerHTML = html;
    }

    handleItemClick(file) {
        if (file.is_dir) {
            this.navigate(file.filename);
        } else if (file.type === 'video') {
            const index = this.currentPlaylist.findIndex(v => v.filename === file.filename);
            this.openPlayer(index);
        } else {
            const url = `/api/stream/media/${encodeURIComponent(file.filename)}`;
            window.open(url, '_blank');
        }
    }

    navigate(path) {
        this.currentPath = path;
        this.activeFilter = 'all';
        this.filterChips.forEach(c => c.classList.toggle('active', c.dataset.filter === 'all'));
        this.loadGallery();
    }

    // --- Player Logic ---

    openPlayer(index) {
        if (index < 0 || index >= this.currentPlaylist.length) return;
        
        this.currentVideoIndex = index;
        const item = this.currentPlaylist[index];
        
        this.playerTitle.innerText = item.name;
        this.video.src = `/api/stream/media/${encodeURIComponent(item.filename)}`;
        
        this.playerContainer.classList.remove('hidden');
        this.updateLocalFavIcon(item.filename);
        this.video.play();
        this.resetIdleTimer();
    }

    closePlayer() {
        this.video.pause();
        this.video.src = "";
        this.playerContainer.classList.add('hidden');
        if (document.fullscreenElement) document.exitFullscreen();
    }

    playNext() {
        if (this.currentVideoIndex < this.currentPlaylist.length - 1) {
            this.openPlayer(this.currentVideoIndex + 1);
        }
    }

    playPrev() {
        if (this.currentVideoIndex > 0) {
            this.openPlayer(this.currentVideoIndex - 1);
        }
    }

    formatTime(seconds) {
        const m = Math.floor(seconds / 60);
        const s = Math.floor(seconds % 60);
        return `${m}:${s < 10 ? '0' : ''}${s}`;
    }

    resetIdleTimer() {
        this.playerContainer.classList.remove('idle');
        clearTimeout(this.hideControlsTimeout);
        this.hideControlsTimeout = setTimeout(() => {
            if (!this.video.paused) this.playerContainer.classList.add('idle');
        }, 3000);
    }

    async toggleFullscreen() {
        if (!document.fullscreenElement) {
            try {
                await this.playerContainer.requestFullscreen();
                // Force Landscape mode on phones when entering fullscreen
                if (screen.orientation && screen.orientation.lock) {
                    try {
                        await screen.orientation.lock('landscape');
                    } catch (err) {
                        console.log("Orientation lock not supported or allowed.", err);
                    }
                }
            } catch (err) {
                console.error(`Error attempting to enable full-screen mode: ${err.message}`);
            }
        } else {
            document.exitFullscreen();
            // Return to natural orientation
            if (screen.orientation && screen.orientation.unlock) {
                screen.orientation.unlock();
            }
        }
    }

    // --- Favorites Logic ---

    async toggleFav(filename) {
        try {
            const response = await fetch('/api/favorites/toggle', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filename })
            });
            const data = await response.json();
            
            const file = this.allFiles.find(f => f.filename === filename);
            if (file) {
                file.is_favorite = data.favorite;
                this.renderGallery();
                if (this.activeFilter === 'favorites' && !data.favorite) {
                    this.loadGallery();
                }
            }
        } catch (error) {
            console.error("Fav toggle failed:", error);
        }
    }

    // --- Local Favorites (Device Specific) ---

    updateLocalFavIcon(filename) {
        const isFav = this.localFavorites.includes(filename);
        this.favIcon.innerText = isFav ? 'favorite' : 'favorite_border';
        isFav ? this.favIcon.classList.add('filled') : this.favIcon.classList.remove('filled');
    }

    toggleLocalFavorite() {
        const currentVid = this.currentPlaylist[this.currentVideoIndex];
        if (!currentVid) return;

        if (this.localFavorites.includes(currentVid.filename)) {
            this.localFavorites = this.localFavorites.filter(p => p !== currentVid.filename);
        } else {
            this.localFavorites.push(currentVid.filename);
        }
        
        localStorage.setItem('media_favorites', JSON.stringify(this.localFavorites));
        this.updateLocalFavIcon(currentVid.filename);
    }

    downloadCurrent() {
        const currentVid = this.currentPlaylist[this.currentVideoIndex];
        if (!currentVid) return;

        const a = document.createElement('a');
        a.href = `/api/download/${encodeURIComponent(currentVid.filename)}`;
        a.download = currentVid.name; 
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    }

    async handleUpload(e) {
        const files = e.target.files;
        if (!files.length) return;

        // Show loading state on FAB
        const originalContent = this.uploadFab.innerHTML;
        this.uploadFab.innerHTML = `<span class="material-symbols-rounded" style="animation: spin 1s linear infinite;">sync</span>`;
        this.uploadFab.style.pointerEvents = 'none';

        for (const file of files) {
            const formData = new FormData();
            formData.append('file', file);
            
            try {
                const target = encodeURIComponent(this.currentPath);
                const response = await fetch(`/api/upload?path=${target}`, {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) {
                    const errorText = await response.text();
                    console.error(`Upload failed with ${response.status}:`, errorText);
                    alert(`Upload failed: ${file.name}`);
                }
            } catch (error) {
                console.error("Network error during upload:", error);
                alert(`Network error during upload: ${file.name}`);
            }
        }
        
        this.uploadFab.innerHTML = originalContent;
        this.uploadFab.style.pointerEvents = 'auto';
        this.fileInput.value = '';
        // No need to manually loadGallery if WebSocket is working, 
        // but it doesn't hurt to have a fallback if we didn't receive a signal.
        await this.loadGallery();
    }

    // --- Helpers ---

    getInitials(name) {
        if (!name) return "??";
        const parts = name.trim().split(/[\s_-]+/);
        if (parts.length >= 2) {
            return (parts[0][0] + parts[1][0]).toUpperCase();
        }
        return name.substring(0, 2).toUpperCase();
    }

    getFileIcon(type) {
        switch (type) {
            case 'image': return 'image';
            case 'video': return 'movie';
            case 'audio': return 'music_note';
            case 'document': return 'description';
            case 'archive': return 'inventory_2';
            default: return 'draft';
        }
    }

    async handleShutdown() {
        if (confirm("⚠️ Are you sure you want to SHUT DOWN the server? All connections will be lost.")) {
            try {
                await fetch('/api/shutdown', { method: 'POST' });
                document.body.innerHTML = `
                    <div style="height:100vh; display:flex; flex-direction:column; align-items:center; justify-content:center; background:#121212; color:white; font-family:Inter,sans-serif;">
                        <span class="material-symbols-rounded" style="font-size:80px; color:#ffb4ab;">power_settings_new</span>
                        <h1 style="margin-top:20px;">Server Offline</h1>
                        <p style="opacity:0.7;">StreamDrop has been safely shut down.</p>
                    </div>
                `;
            } catch (e) {
                console.error("Shutdown failed:", e);
            }
        }
    }

    async handleStreamToggle() {
        try {
            const response = await fetch('/api/stream/toggle', { method: 'POST' });
            const data = await response.json();
            const icon = data.mode === 'webcam' ? 'videocam' : 'screen_share';
            this.streamToggleBtn.querySelector('.material-symbols-rounded').innerText = icon;
            
            // Show toast/snack
            console.log(`Stream mode changed to: ${data.mode}`);
        } catch (e) {
            console.error("Toggle failed:", e);
        }
    }
}

// Global instance
const app = new StreamDropApp();
window.app = app;
