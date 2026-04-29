/**
 * StreamDrop — Reactive Material 3 Client
 */

class StreamDropApp {
    constructor() {
        window.app = this; // Ensure global access early for any sync calls
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
        this.centerOverlay = document.getElementById('play-pause-overlay');
        this.centerIcon = document.getElementById('center-play-icon');
        this.seekBar = document.getElementById('seek-bar');
        this.timeCurrent = document.getElementById('time-current');
        this.timeTotal = document.getElementById('time-total');
        this.closePlayerBtn = document.getElementById('closePlayerBtn');
        this.prevBtn = document.getElementById('prevBtn');
        this.nextBtn = document.getElementById('nextBtn');
        this.fullscreenBtn = document.getElementById('fullscreenBtn');
        this.shutdownBtn = document.getElementById('shutdownBtn');
        this.streamToggleBtn = document.getElementById('streamToggleBtn');
        this.installAppBtn = document.getElementById('installAppBtn');
        this.qrCodeBtn = document.getElementById('qrCodeBtn');
        this.qrModal = document.getElementById('qr-modal');
        this.closeQrBtn = document.getElementById('closeQrBtn');

        // PWA Install Prompt
        this.deferredPrompt = null;

        // New PWA Action Buttons
        this.favBtn = document.getElementById('fav-btn');
        this.favIcon = document.getElementById('fav-icon');
        this.pipBtn = document.getElementById('pipBtn');
        this.downloadBtn = document.getElementById('downloadCurrentBtn');
        
        // Seek Feedback
        this.seekLeft = document.getElementById('seek-feedback-left');
        this.seekRight = document.getElementById('seek-feedback-right');
        this.seekTextIndicator = document.getElementById('seek-text-indicator');
        
        // Context Menu & Dialog
        this.sheetOverlay = document.getElementById('sheetOverlay');
        this.contextSheet = document.getElementById('contextSheet');
        this.dialogOverlay = document.getElementById('dialogOverlay');
        this.renameInput = document.getElementById('renameInput');
        
        this.selectedFile = null;
        this.longPressTimer = null;
        
        // Stream UI Elements
        this.streamContainer = document.getElementById('stream-container');
        this.streamImg = document.getElementById('stream-img');
        this.streamAudio = document.getElementById('stream-audio');
        this.streamStatus = document.getElementById('streamStatus');
        this.streamModeBtn = document.getElementById('streamModeBtn');
        this.closeStreamBtn = document.getElementById('closeStreamBtn');
        this.liveCaptions = document.getElementById('live-captions');
        this.subtitleInput = document.getElementById('subtitleInput');

        this.globalProgress = document.getElementById('globalProgress');
        this.progressLabel = document.getElementById('progressLabel');
        this.progressPercent = document.getElementById('progressPercent');
        this.progressBar = document.getElementById('progressBar');

        this.folderSettings = document.getElementById('folderSettings');
        this.optimizeFolderToggle = document.getElementById('optimizeFolderToggle');

        this.localFavorites = JSON.parse(localStorage.getItem('media_favorites')) || [];

        this.hlsPlayer = null;

        // Lazy Rendering
        this.itemsPerPage = 50;
        this.visibleCount = this.itemsPerPage;
        this.observer = null;

        this.init();
    }

    showToast(message, isError = false) {
        const toast = document.createElement('div');
        toast.style.cssText = `
            position: fixed;
            bottom: 80px;
            left: 50%;
            transform: translateX(-50%);
            background: ${isError ? '#ffb4ab' : '#313033'};
            color: ${isError ? '#690005' : '#f4eff4'};
            padding: 12px 24px;
            border-radius: 25px;
            font-size: 14px;
            font-weight: 500;
            z-index: 9999;
            box-shadow: 0 4px 8px rgba(0,0,0,0.3);
            animation: toastIn 0.3s ease-out;
        `;
        toast.innerText = message;
        document.body.appendChild(toast);

        setTimeout(() => {
            toast.style.animation = 'toastOut 0.3s ease-in forwards';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    cleanFilename(filename) {
        return filename
            .replace(/\.[^/.]+$/, "") // Remove file extension
            .replace(/[_-]+/g, " ")   // Replace dashes and underscores
            .replace(/\b\w/g, c => c.toUpperCase()) // Title Case
            .trim();
    }

    async init() {
        this.setupEventListeners();
        this.setupPlayerEvents();
        this.connectWebSocket();
        await this.loadGallery();
        this.setupPWA();
        this.handleInitialAction();
    }

    handleInitialAction() {
        const params = new URLSearchParams(window.location.search);
        if (params.get('action') === 'stream') {
            this.openStream();
        }
    }

    setupPWA() {
        // Register Service Worker
        if ('serviceWorker' in navigator) {
            window.addEventListener('load', () => {
                navigator.serviceWorker.register('/sw.js')
                    .then(reg => console.log('SW Registered'))
                    .catch(err => console.log('SW Registration Failed', err));
            });
        }

        // Handle Install Prompt
        window.addEventListener('beforeinstallprompt', (e) => {
            // Prevent Chrome 67 and earlier from automatically showing the prompt
            e.preventDefault();
            // Stash the event so it can be triggered later.
            this.deferredPrompt = e;
            // Update UI notify the user they can add to home screen
            this.installAppBtn.style.display = 'flex';
        });

        this.installAppBtn.addEventListener('click', async () => {
            if (!this.deferredPrompt) return;
            // Show the prompt
            this.deferredPrompt.prompt();
            // Wait for the user to respond to the prompt
            const { outcome } = await this.deferredPrompt.userChoice;
            console.log(`User response to the install prompt: ${outcome}`);
            // We've used the prompt, and can't use it again, throw it away
            this.deferredPrompt = null;
            // Hide the button
            this.installAppBtn.style.display = 'none';
        });

        window.addEventListener('appinstalled', (evt) => {
            console.log('StreamDrop was installed.');
            this.installAppBtn.style.display = 'none';
        });
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

        this.shutdownBtn.addEventListener('click', () => this.handleShutdown());
        this.streamToggleBtn.addEventListener('click', () => this.handleStreamToggle());
        this.qrCodeBtn.addEventListener('click', () => this.showQRCode());
        if (this.closeQrBtn) this.closeQrBtn.addEventListener('click', () => this.qrModal.classList.add('hidden'));

        // Overlay Controls
        this.closeStreamBtn.onclick = () => this.closeStream();
        this.streamModeBtn.onclick = () => this.handleStreamToggle();

        // Global Back Navigation
        window.addEventListener('popstate', (e) => {
            this.currentPath = e.state?.path || "";
            this.loadGallery(false);
        });

        // Context Menu Actions
        document.getElementById('renameOption').onclick = () => this.showRenameDialog();
        document.getElementById('subtitleOption').onclick = () => this.subtitleInput.click();
        document.getElementById('deleteOption').onclick = () => this.handleDelete();
        this.subtitleInput.onchange = (e) => this.handleSubtitleUpload(e);
        this.sheetOverlay.onclick = () => this.closeContextMenu();
        
        // Rename Dialog Actions
        document.getElementById('cancelRename').onclick = () => this.closeRenameDialog();
        document.getElementById('confirmRename').onclick = () => this.handleRename();

        // Folder Optimization Toggle
        if (this.optimizeFolderToggle) {
            this.optimizeFolderToggle.addEventListener('change', async (e) => {
                const enabled = e.target.checked;
                try {
                    await fetch('/api/folder/optimization', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ folder_path: this.currentPath, enabled: enabled })
                    });
                } catch (err) {
                    console.error('Failed to update folder settings:', err);
                }
            });
        }
    }

    setupPlayerEvents() {
        this.closePlayerBtn.addEventListener('click', () => this.closePlayer());
        this.prevBtn.addEventListener('click', () => this.playPrev());
        this.nextBtn.addEventListener('click', () => this.playNext());
        this.fullscreenBtn.addEventListener('click', () => this.toggleFullscreen());
        this.favBtn.addEventListener('click', () => this.toggleLocalFavorite());
        this.pipBtn.addEventListener('click', () => this.togglePiP());
        this.downloadBtn.addEventListener('click', () => this.downloadCurrent());

        // Video State
        this.video.addEventListener('ended', () => this.playNext());
        this.video.addEventListener('timeupdate', () => {
            if (this.video.currentTime > 5) {
                const currentVid = this.currentPlaylist[this.currentVideoIndex];
                if (currentVid) {
                    localStorage.setItem(`resume_${currentVid.filename}`, this.video.currentTime);
                }
            }
            if (this.video.duration) {
                const percent = (this.video.currentTime / this.video.duration) * 100;
                this.seekBar.value = percent;
                this.timeCurrent.innerText = this.formatTime(this.video.currentTime);
                this.timeTotal.innerText = this.formatTime(this.video.duration);
            }
        });

        // Seek Bar logic
        this.seekBar.addEventListener('input', (e) => {
            if (this.video.duration) {
                const time = (e.target.value / 100) * this.video.duration;
                this.video.currentTime = time;
            }
        });

        // --- Touch & Gesture Engine (Gold Standard) ---
        let touchStartX = 0;
        let touchStartY = 0;
        let scrubStartTime = 0;
        let isSwiping = false;
        let lastTapTime = 0;
        let speedTimeout;

        const isControl = (el) => el.closest('.icon-btn') || el.closest('#seek-bar');

        this.playerUI.addEventListener('touchstart', (e) => {
            if (e.touches.length > 1) return;
            if (isControl(e.target)) return;

            const touch = e.touches[0];
            touchStartX = touch.clientX;
            touchStartY = touch.clientY;
            scrubStartTime = this.video.currentTime;
            isSwiping = false;

            // 1. Double Tap Detection
            const now = Date.now();
            if (now - lastTapTime < 300) {
                const screenWidth = window.innerWidth;
                if (touchStartX > screenWidth / 2) {
                    this.seek(10);
                    this.showSeekText("+10s");
                    this.showSeekFeedback('right');
                } else {
                    this.seek(-10);
                    this.showSeekText("-10s");
                    this.showSeekFeedback('left');
                }
                clearTimeout(speedTimeout);
                lastTapTime = 0; // Avoid triple tap
                return;
            }
            lastTapTime = now;

            // 2. Start Long Press Timer (for 2x Speed)
            speedTimeout = setTimeout(() => {
                if (!isSwiping) {
                    this.video.playbackRate = 2.0;
                    this.centerIcon.innerText = 'fast_forward';
                    this.centerOverlay.classList.add('animate');
                }
            }, 500);
            
            this.resetIdleTimer();
        }, { passive: true });

        this.playerUI.addEventListener('touchmove', (e) => {
            if (!touchStartX) return;

            const touch = e.touches[0];
            const deltaX = touch.clientX - touchStartX;
            const deltaY = touch.clientY - touchStartY;

            // Horizontal swipe threshold
            if (Math.abs(deltaX) > 20 && Math.abs(deltaX) > Math.abs(deltaY)) {
                isSwiping = true;
                clearTimeout(speedTimeout);
                
                // 1px drag = 0.2s seek
                const timeDelta = (deltaX - (Math.sign(deltaX) * 20)) * 0.2;
                let newTime = scrubStartTime + timeDelta;
                newTime = Math.max(0, Math.min(this.video.duration, newTime));
                this.video.currentTime = newTime;

                this.seekTextIndicator.innerText = this.formatTime(newTime);
                this.seekTextIndicator.classList.add('visible');
                this.resetIdleTimer();
            }
        }, { passive: true });

        this.playerUI.addEventListener('touchend', () => {
            clearTimeout(speedTimeout);
            this.video.playbackRate = 1.0;
            this.centerOverlay.classList.remove('animate');
            this.centerIcon.innerText = this.video.paused ? 'play_arrow' : 'pause';
            
            if (isSwiping) {
                isSwiping = false;
                this.seekTextIndicator.classList.remove('visible');
            }
            touchStartX = 0;
        });

        // Single Tap to Toggle Playback
        this.playerUI.addEventListener('click', (e) => {
            if (isControl(e.target)) return;
            if (isSwiping) return;
            
            this.togglePlayPause();
            this.resetIdleTimer();
        });

        // Mouse fallback for PC users
        this.playerUI.addEventListener('mousedown', (e) => {
            if (isControl(e.target)) return;
            speedTimeout = setTimeout(() => {
                this.video.playbackRate = 2.0;
                this.centerIcon.innerText = 'fast_forward';
                this.centerOverlay.classList.add('animate');
            }, 500);
        });

        const stopFF = () => {
            clearTimeout(speedTimeout);
            this.video.playbackRate = 1.0;
            this.centerOverlay.classList.remove('animate');
            this.centerIcon.innerText = this.video.paused ? 'play_arrow' : 'pause';
        };

        this.playerUI.addEventListener('mouseup', stopFF);
        this.playerUI.addEventListener('mouseleave', stopFF);

        // Auto-Hide Controls
        this.playerUI.addEventListener('mousemove', () => this.resetIdleTimer());
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
                } else if (data.type === 'transcription') {
                    this.showLiveCaption(data.text);
                } else if (data.type === 'error') {
                    alert(data.message); // Device limit reached
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

    async loadGallery(pushState = true, pin = "") {
        let url = this.activeFilter === 'favorites' 
            ? '/api/favorites' 
            : `/api/files/${encodeURIComponent(this.currentPath)}`;
            
        if (pin && this.activeFilter !== 'favorites') url += `?pin=${pin}`;

        try {
            const response = await fetch(url);
            
            if (response.status === 401) {
                const userPin = prompt("This folder is locked. Enter PIN:");
                if (userPin) this.loadGallery(pushState, userPin);
                return;
            }
            
            const data = await response.json();
            this.allFiles = data.items || [];
            this.visibleCount = this.itemsPerPage; // Reset scroll on new folder
            
            // Build current playlist (only videos)
            this.currentPlaylist = this.allFiles.filter(f => f.type === 'video');

            if (pushState && this.activeFilter === 'all') {
                history.pushState({ path: this.currentPath }, '', `?path=${this.currentPath}`);
            }

            this.applyFilters();
            this.renderBreadcrumbs();
            this.updateFolderSettings();
        } catch (error) {
            console.error("Failed to load gallery:", error);
        }
    }

    async updateFolderSettings() {
        if (!this.folderSettings) return;
        
        if (this.activeFilter === 'favorites') {
            this.folderSettings.style.display = 'none';
            return;
        }

        this.folderSettings.style.display = 'flex';
        try {
            const response = await fetch(`/api/folder/optimization?folder_path=${encodeURIComponent(this.currentPath)}`);
            const data = await response.json();
            this.optimizeFolderToggle.checked = data.enabled;
        } catch (err) {
            console.error('Failed to get folder settings:', err);
        }
    }

    applyFilters() {
        this.filteredFiles = this.allFiles.filter(file => {
            const matchesSearch = file.name.toLowerCase().includes(this.searchQuery);
            return matchesSearch;
        });

        // Add "Live Stream" card if at root
        if (!this.currentPath && !this.searchQuery && this.activeFilter === 'all') {
            this.filteredFiles.unshift({
                name: "Live Desktop Stream",
                filename: "LIVE_STREAM",
                type: "stream",
                is_dir: false,
                is_virtual: true
            });
        }

        this.renderGallery();
    }

    renderGallery() {
        this.gallery.innerHTML = '';
        
        if (this.filteredFiles.length === 0) {
            this.emptyState.style.display = 'flex';
            return;
        }

        this.emptyState.style.display = 'none';

        // Get chunk
        const chunk = this.filteredFiles.slice(0, this.visibleCount);
        
        chunk.forEach(file => {
            const card = document.createElement('div');
            card.className = 'media-card';
            
            const isFolder = file.is_dir;
            const isVideo = file.type === 'video';
            
            // Thumbnail / Icon / Avatar logic
            let content = '';
            if (isFolder) {
                const initials = this.getInitials(file.name);
                content = `<div class="folder-avatar">${initials}</div>`;
            } else if (file.type === 'stream') {
                content = `<span class="material-symbols-rounded" style="font-size: 64px; color: var(--m3-primary);">sensors</span>`;
            } else if (file.thumbnail_url) {
                content = `<img src="${file.thumbnail_url}" loading="lazy" alt="${file.name}" onerror="this.src='/static/img/fallback.png'; this.onerror=null;">`;
            } else {
                const icon = this.getFileIcon(file.type);
                content = `<span class="material-symbols-rounded" style="font-size: 48px; opacity: 0.3;">${icon}</span>`;
            }

            const videoOverlay = isVideo ? `<div class="icon-overlay"><span class="material-symbols-rounded">play_arrow</span></div>` : '';
            const favClass = file.is_favorite ? 'active' : '';

            card.innerHTML = `
                <div class="fav-btn ${favClass}" data-filename="${file.filename}">
                    <span class="material-symbols-rounded" style="font-variation-settings: 'FILL' ${file.is_favorite ? 1 : 0}">star</span>
                </div>
                <div class="card-media">
                    ${content}
                </div>
                ${videoOverlay}
                <div class="info">${file.name}</div>
            `;

            // --- Use addEventListener for robust click handling ---
            
            // Star/Favorite button — must use stopPropagation to prevent triggering card click
            const favBtn = card.querySelector('.fav-btn');
            if (favBtn) {
                favBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    this.toggleFav(file.filename);
                });
            }

            // Main card click — use addEventListener (not onclick) for consistency
            card.addEventListener('click', (e) => {
                // Guard: don't fire if the fav button was clicked (extra safety)
                if (e.target.closest('.fav-btn')) return;
                
                if (file.type === 'stream') {
                    this.openStream();
                } else {
                    this.handleItemClick(file);
                }
            });
            
            // Context menu (long press / right click)
            card.addEventListener('contextmenu', (e) => {
                e.preventDefault();
                if (file.is_virtual) return; // Skip virtual items like Live Stream
                this.openContextMenu(file);
            });

            this.gallery.appendChild(card);
        });

        // Setup Infinite Scroll Sentinel
        if (this.visibleCount < this.filteredFiles.length) {
            const sentinel = document.createElement('div');
            sentinel.className = 'sentinel';
            sentinel.style.height = '20px';
            sentinel.style.width = '100%';
            this.gallery.appendChild(sentinel);

            if (this.observer) this.observer.disconnect();
            this.observer = new IntersectionObserver((entries) => {
                if (entries[0].isIntersecting) {
                    this.visibleCount += this.itemsPerPage;
                    this.renderGallery();
                }
            }, { rootMargin: '200px' });
            this.observer.observe(sentinel);
        }
    }

    renderBreadcrumbs() {
        if (this.activeFilter === 'favorites') {
            this.breadcrumbs.innerHTML = '';
            const span = document.createElement('span');
            span.className = 'breadcrumb-item';
            span.innerText = 'Favorites';
            this.breadcrumbs.appendChild(span);
            return;
        }

        this.breadcrumbs.innerHTML = '';
        
        // Home
        const home = document.createElement('span');
        home.className = 'breadcrumb-item';
        home.innerText = 'Home';
        home.onclick = () => this.navigate('');
        this.breadcrumbs.appendChild(home);

        const parts = this.currentPath.split('/').filter(p => p);
        let pathAccumulator = "";
        
        parts.forEach((part, i) => {
            const separator = document.createElement('span');
            separator.className = 'material-symbols-rounded';
            separator.style.fontSize = '16px';
            separator.innerText = 'chevron_right';
            this.breadcrumbs.appendChild(separator);

            pathAccumulator += (i === 0 ? '' : '/') + part;
            const current = pathAccumulator;
            
            const item = document.createElement('span');
            item.className = 'breadcrumb-item';
            item.innerText = part;
            item.onclick = () => this.navigate(current);
            this.breadcrumbs.appendChild(item);
        });
    }

    handleItemClick(file) {
        if (file.is_dir) {
            this.navigate(file.filename);
        } else if (file.type === 'video') {
            const index = this.currentPlaylist.findIndex(v => v.filename === file.filename);
            this.openPlayer(index);
        } else if (file.type === 'text' && (file.name.endsWith('.txt') || file.name.endsWith('.md'))) {
            if (typeof openEditor === 'function') {
                openEditor(file.filename);
            } else {
                window.open(`/api/download/${encodeURIComponent(file.filename)}`, '_blank');
            }
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

    async openPlayer(index) {
        if (index < 0 || index >= this.currentPlaylist.length) return;
        
        this.currentVideoIndex = index;
        const item = this.currentPlaylist[index];
        
        this.playerTitle.innerText = this.cleanFilename(item.name);
        
        // Clean up previous HLS instance if any
        if (this.hlsPlayer) {
            this.hlsPlayer.destroy();
            this.hlsPlayer = null;
        }

        const hlsUrl = `/api/stream/hls/${encodeURIComponent(item.filename)}/index.m3u8`;
        const directUrl = `/api/stream/media/${encodeURIComponent(item.filename)}`;

        // Check if HLS playlist exists
        try {
            const headResponse = await fetch(hlsUrl, { method: 'HEAD' });
            if (headResponse.ok) {
                console.log("HLS stream found, attempting playback");
                if (Hls.isSupported()) {
                    this.hlsPlayer = new Hls();
                    this.hlsPlayer.loadSource(hlsUrl);
                    this.hlsPlayer.attachMedia(this.video);
                } else if (this.video.canPlayType('application/vnd.apple.mpegurl')) {
                    // Safari native support
                    this.video.src = hlsUrl;
                } else {
                    // Fallback if HLS not supported at all
                    this.video.src = directUrl;
                }
            } else {
                throw new Error("No HLS");
            }
        } catch (e) {
            console.log("Falling back to direct Byte-Range stream");
            this.video.src = directUrl;
        }
        
        // Subtitles
        const oldTrack = this.video.querySelector('track');
        if (oldTrack) oldTrack.remove();

        if (item.subtitles_url) {
            const track = document.createElement('track');
            track.kind = 'subtitles';
            track.label = 'English';
            track.srclang = 'en';
            track.src = item.subtitles_url;
            track.default = true;
            this.video.appendChild(track);
            console.log("Subtitle track added:", item.subtitles_url);
        }

        this.playerContainer.classList.remove('hidden');
        this.updateLocalFavIcon(item.filename);
        
        // Check local storage for resume time
        const savedTime = localStorage.getItem(`resume_${item.filename}`);
        if (savedTime) {
            this.video.currentTime = parseFloat(savedTime);
            this.showToast("Resumed from last played position");
        }

        this.video.play().catch(e => console.error("Playback prevented:", e));
        this.resetIdleTimer();
    }

    closePlayer() {
        if (this.hlsPlayer) {
            this.hlsPlayer.destroy();
            this.hlsPlayer = null;
        }
        this.video.pause();
        this.video.removeAttribute('src'); // Better than src="" to fully stop loading
        this.video.load();
        this.playerContainer.classList.add('hidden');
        if (document.fullscreenElement) document.exitFullscreen();
    }

    togglePlayPause() {
        if (this.video.paused) {
            this.video.play();
            this.animateCenterIcon('play_arrow');
        } else {
            this.video.pause();
            this.animateCenterIcon('pause');
        }
    }

    animateCenterIcon(iconName) {
        this.centerIcon.innerText = iconName;
        this.centerOverlay.classList.remove('animate');
        void this.centerOverlay.offsetWidth; // Force reflow
        this.centerOverlay.classList.add('animate');
        
        setTimeout(() => {
            this.centerOverlay.classList.remove('animate');
        }, 500);
    }

    seek(seconds) {
        if (!this.video.duration) return;
        this.video.currentTime = Math.max(0, Math.min(this.video.duration, this.video.currentTime + seconds));
        this.resetIdleTimer();
    }

    showSeekText(text) {
        this.seekTextIndicator.innerText = text;
        this.seekTextIndicator.classList.add('visible');
        setTimeout(() => this.seekTextIndicator.classList.remove('visible'), 600);
    }

    showSeekFeedback(side) {
        const el = side === 'left' ? this.seekLeft : this.seekRight;
        if (!el) return;
        el.classList.remove('animate');
        void el.offsetWidth; // Force reflow
        el.classList.add('animate');
        setTimeout(() => el.classList.remove('animate'), 600);
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

    async togglePiP() {
        try {
            if (document.pictureInPictureElement) {
                await document.exitPictureInPicture();
            } else if (document.pictureInPictureEnabled && this.video.readyState >= 2) {
                await this.video.requestPictureInPicture();
            }
        } catch (error) {
            console.error("PiP failed:", error);
            this.showToast("PiP not supported on this device", true);
        }
    }

    // --- Favorites Logic ---

    async toggleFav(filename) {
        if (filename === 'LIVE_STREAM') return; // Virtual items cannot be favorited
        
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

    async downloadCurrent() {
        const currentVid = this.currentPlaylist[this.currentVideoIndex];
        if (!currentVid) return;

        this.updateProgressUI(`Downloading: ${currentVid.name}`, 0);

        try {
            const response = await fetch(`/api/download/${encodeURIComponent(currentVid.filename)}`);
            if (!response.ok) throw new Error("Download failed");

            const contentLength = response.headers.get('content-length');
            if (!contentLength) {
                // Fallback if no content length (unlikely on this server)
                window.location.href = `/api/download/${encodeURIComponent(currentVid.filename)}`;
                this.updateProgressUI("", 0, false);
                return;
            }

            const total = parseInt(contentLength, 10);
            
            // Memory Optimization: If file > 100MB, use native download 
            // to avoid crashing browser with large Blobs
            if (total > 100 * 1024 * 1024) {
                console.log("File large, using native download for memory safety");
                window.location.href = `/api/download/${encodeURIComponent(currentVid.filename)}`;
                this.updateProgressUI("", 0, false);
                return;
            }

            let loaded = 0;

            const reader = response.body.getReader();
            const chunks = [];

            while(true) {
                const { done, value } = await reader.read();
                if (done) break;

                chunks.push(value);
                loaded += value.length;
                this.updateProgressUI(`Downloading: ${currentVid.name}`, (loaded / total) * 100);
            }

            const blob = new Blob(chunks);
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = currentVid.name;
            document.body.appendChild(a);
            a.click();
            URL.revokeObjectURL(url);
            document.body.removeChild(a);

        } catch (err) {
            console.error("Download failed:", err);
            // Final fallback
            window.location.href = `/api/download/${encodeURIComponent(currentVid.filename)}`;
        }

        this.updateProgressUI("", 0, false);
    }

    updateProgressUI(label, percent, visible = true) {
        if (!visible) {
            this.globalProgress.classList.add('hidden');
            return;
        }
        this.globalProgress.classList.remove('hidden');
        this.progressLabel.innerText = label;
        this.progressPercent.innerText = `${Math.round(percent)}%`;
        this.progressBar.style.width = `${percent}%`;
    }

    async handleUpload(e) {
        const files = e.target.files;
        if (!files.length) return;

        const uploadIcon = document.getElementById('uploadIcon');
        const progressCircle = document.getElementById('uploadProgress');
        
        // Show loading state
        uploadIcon.innerText = 'sync';
        uploadIcon.style.animation = 'spin 1s linear infinite';
        this.uploadFab.style.pointerEvents = 'none';
        progressCircle.style.display = 'block';

        let totalUploaded = 0;
        const totalSize = Array.from(files).reduce((acc, f) => acc + f.size, 0);

        for (const file of files) {
            let lastFileUploaded = 0;
            await new Promise((resolve, reject) => {
                const xhr = new XMLHttpRequest();
                const formData = new FormData();
                formData.append('file', file);

                xhr.upload.addEventListener('progress', (ev) => {
                    if (ev.lengthComputable) {
                        const filePercent = (ev.loaded / ev.total) * 100;
                        progressCircle.style.background = `conic-gradient(var(--m3-primary) ${filePercent}%, transparent 0)`;
                        
                        // Global progress
                        const currentTotal = totalUploaded + ev.loaded;
                        const overallPercent = (currentTotal / totalSize) * 100;
                        this.updateProgressUI(`Uploading: ${file.name}`, overallPercent);
                    }
                });

                xhr.onload = () => {
                    if (xhr.status >= 200 && xhr.status < 300) {
                        totalUploaded += file.size;
                        resolve();
                    } else reject(new Error(xhr.responseText));
                };
                xhr.onerror = () => reject(new Error("Network error"));

                const target = encodeURIComponent(this.currentPath);
                xhr.open('POST', `/api/upload?path=${target}`);
                xhr.send(formData);
            });
        }
        
        // Reset state
        this.updateProgressUI("", 0, false);
        uploadIcon.innerText = 'add';
        uploadIcon.style.animation = 'none';
        this.uploadFab.style.pointerEvents = 'auto';
        progressCircle.style.display = 'none';
        this.fileInput.value = '';
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
            
            // Update both buttons (header and overlay)
            this.streamToggleBtn.querySelector('.material-symbols-rounded').innerText = icon;
            this.streamModeBtn.querySelector('.material-symbols-rounded').innerText = icon;
            
            // Update title in overlay
            const title = data.mode === 'webcam' ? 'Live Webcam Stream' : 'Live Desktop Stream';
            this.streamContainer.querySelector('.title').innerText = title;

            console.log(`Stream mode changed to: ${data.mode}`);
        } catch (e) {
            console.error("Toggle failed:", e);
        }
    }

    async openStream() {
        try {
            // 1. Start the stream on the backend
            const response = await fetch('/api/stream/start', { method: 'POST' });
            const data = await response.json();
            
            // 2. Update UI
            const icon = data.mode === 'webcam' ? 'videocam' : 'screen_share';
            const title = data.mode === 'webcam' ? 'Live Webcam Stream' : 'Live Desktop Stream';
            
            this.streamModeBtn.querySelector('.material-symbols-rounded').innerText = icon;
            this.streamContainer.querySelector('.title').innerText = title;
            this.streamStatus.innerText = "Live";
            
            // Clear old captions
            this.liveCaptions.innerHTML = "";
            
            // 3. Show overlay
            this.streamContainer.classList.remove('hidden');
            
            // 4. Set stream sources (use a timestamp to bust cache)
            const t = Date.now();
            this.streamImg.src = `/api/stream/video?t=${t}`;
            this.streamAudio.src = `/api/stream/audio?t=${t}`;
            this.streamAudio.play().catch(e => console.log("Audio autoplay blocked", e));
            
            // 5. Hide gallery scroll
            document.body.style.overflow = 'hidden';
        } catch (e) {
            console.error("Failed to open stream:", e);
        }
    }

    showLiveCaption(text) {
        const caption = document.createElement('div');
        caption.className = 'caption-segment';
        caption.innerText = text;
        
        this.liveCaptions.appendChild(caption);
        
        // Auto-scroll to bottom
        this.liveCaptions.scrollTop = this.liveCaptions.scrollHeight;
        
        // Keep only last 20 segments to save DOM memory
        while (this.liveCaptions.childNodes.length > 20) {
            this.liveCaptions.removeChild(this.liveCaptions.firstChild);
        }
    }

    async handleSubtitleUpload(e) {
        const file = e.target.files[0];
        if (!file || !this.selectedFile) return;

        const formData = new FormData();
        formData.append('file', file);
        
        this.updateProgressUI(`Uploading Subtitles: ${file.name}`, 0);

        try {
            await new Promise((resolve, reject) => {
                const xhr = new XMLHttpRequest();
                xhr.upload.addEventListener('progress', (ev) => {
                    if (ev.lengthComputable) {
                        const percent = (ev.loaded / ev.total) * 100;
                        this.updateProgressUI(`Uploading Subtitles: ${file.name}`, percent);
                    }
                });

                xhr.onload = () => {
                    if (xhr.status >= 200 && xhr.status < 300) resolve();
                    else reject(new Error(xhr.responseText));
                };
                xhr.onerror = () => reject(new Error("Network error"));

                xhr.open('POST', `/api/upload/subtitles?video_filename=${encodeURIComponent(this.selectedFile.filename)}`);
                xhr.send(formData);
            });

            alert("Subtitles uploaded successfully!");
            this.closeContextMenu();
            await this.loadGallery();
        } catch (err) {
            console.error("Subtitle upload error:", err);
            alert("Subtitle upload failed");
        }
        
        this.updateProgressUI("", 0, false);
        this.subtitleInput.value = "";
    }

    async closeStream() {
        try {
            // 1. Stop stream on backend
            await fetch('/api/stream/stop', { method: 'POST' });
            
            // 2. Hide overlay
            this.streamContainer.classList.add('hidden');
            
            // 3. Clear sources
            this.streamImg.src = "";
            this.streamAudio.src = "";
            
            // 4. Restore scroll
            document.body.style.overflow = '';
        } catch (e) {
            console.error("Failed to close stream:", e);
        }
    }

    async showQRCode() {
        const qrContainer = document.getElementById("qrcode");
        qrContainer.innerHTML = ""; // Clear old code

        if (typeof QRCode === 'undefined') {
            console.error("QRCode library not loaded");
            return;
        }

        let targetUrl = window.location.origin;
        
        try {
            // Fetch actual network IP from backend so it works even if accessed via localhost
            const res = await fetch('/api/status');
            if (res.ok) {
                const data = await res.json();
                if (data.url) targetUrl = data.url;
            }
        } catch (e) {
            console.warn("Could not fetch server IP for QR code, using current origin.");
        }

        new QRCode(qrContainer, {
            text: targetUrl,
            width: 200,
            height: 200,
            colorDark : "#000000",
            colorLight : "#ffffff"
        });

        this.qrModal.classList.remove('hidden');
    }

    // --- File Management ---

    openContextMenu(file) {
        this.selectedFile = file;
        this.sheetOverlay.classList.add('active');
        this.contextSheet.classList.add('active');
        
        // Haptic feedback if available
        if (window.navigator.vibrate) {
            window.navigator.vibrate(50);
        }
    }

    closeContextMenu() {
        this.sheetOverlay.classList.remove('active');
        this.contextSheet.classList.remove('active');
        this.selectedFile = null;
    }

    async handleDelete() {
        if (!this.selectedFile) return;
        
        const confirmMsg = this.selectedFile.is_dir 
            ? `Delete folder "${this.selectedFile.name}" and all its contents?`
            : `Delete "${this.selectedFile.name}"?`;
            
        if (confirm(confirmMsg)) {
            try {
                const response = await fetch(`/api/files/${encodeURIComponent(this.selectedFile.filename)}`, {
                    method: 'DELETE'
                });
                if (response.ok) {
                    this.closeContextMenu();
                    await this.loadGallery();
                } else {
                    alert("Delete failed");
                }
            } catch (e) {
                console.error("Delete failed:", e);
            }
        }
    }

    showRenameDialog() {
        if (!this.selectedFile) return;
        this.renameInput.value = this.selectedFile.name;
        this.dialogOverlay.classList.add('active');
        this.renameInput.focus();
    }

    closeRenameDialog() {
        this.dialogOverlay.classList.remove('active');
        this.closeContextMenu();
    }

    async handleRename() {
        const newName = this.renameInput.value.trim();
        if (!newName || !this.selectedFile || newName === this.selectedFile.name) {
            this.closeRenameDialog();
            return;
        }

        try {
            const response = await fetch(`/api/files/${encodeURIComponent(this.selectedFile.filename)}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ new_name: newName })
            });

            if (response.ok) {
                this.closeRenameDialog();
                await this.loadGallery();
            } else {
                const err = await response.json();
                alert(err.detail || "Rename failed");
            }
        } catch (e) {
            console.error("Rename failed:", e);
        }
    }
}

// Global instance
const app = new StreamDropApp();
// window.app is set inside the constructor
