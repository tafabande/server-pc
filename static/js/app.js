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
            
            // Thumbnail / Icon
            let content = '';
            if (isFolder) {
                content = `<span class="material-symbols-rounded" style="font-size: 64px; opacity: 0.5;">folder</span>`;
            } else if (file.thumb_url) {
                content = `<img src="${file.thumb_url}" loading="lazy">`;
            } else {
                content = `<span class="material-symbols-rounded" style="font-size: 48px; opacity: 0.3;">draft</span>`;
            }

            const videoOverlay = isVideo ? `<div class="icon-overlay"><span class="material-symbols-rounded">play_arrow</span></div>` : '';
            const favClass = file.is_favorite ? 'active' : '';

            card.innerHTML = `
                <div class="fav-btn ${favClass}" onclick="event.stopPropagation(); app.toggleFav('${file.filename}')">
                    <span class="material-symbols-rounded" style="font-variation-settings: 'FILL' ${file.is_favorite ? 1 : 0}">star</span>
                </div>
                <div style="width:100%; height:100%; display:flex; align-items:center; justify-content:center;">
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

    toggleFullscreen() {
        if (!document.fullscreenElement) {
            this.playerContainer.requestFullscreen().catch(err => {
                console.error(`Error attempting to enable full-screen mode: ${err.message}`);
            });
        } else {
            document.exitFullscreen();
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

    async handleUpload(e) {
        const files = e.target.files;
        if (!files.length) return;

        for (const file of files) {
            const formData = new FormData();
            formData.append('file', file);
            
            try {
                await fetch(`/api/upload?path=${encodeURIComponent(this.currentPath)}`, {
                    method: 'POST',
                    body: formData
                });
            } catch (error) {
                console.error("Upload failed:", error);
            }
        }
        this.fileInput.value = '';
    }
}

// Global instance
const app = new StreamDropApp();
window.app = app;
