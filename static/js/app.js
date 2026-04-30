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

        // Auto-Next & Settings State
        this.autoPlayEnabled = true;
        this.autoNextCountdown = null;
        this.autoNextInterval = null;
        this.settingsPanelOpen = false;

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
        this.settingsBtn = document.getElementById('settingsBtn');
        this.shutdownBtn = document.getElementById('shutdownBtn');
        this.streamToggleBtn = document.getElementById('streamToggleBtn');
        this.installAppBtn = document.getElementById('installAppBtn');
        this.qrCodeBtn = document.getElementById('qrCodeBtn');
        this.qrModal = document.getElementById('qr-modal');
        this.closeQrBtn = document.getElementById('closeQrBtn');

        // Auto-Next UI
        this.autoNextOverlay = document.getElementById('autoNextOverlay');
        this.autoNextProgress = document.getElementById('autoNextProgress');
        this.autoNextSeconds = document.getElementById('autoNextSeconds');
        this.autoNextTitle = document.getElementById('autoNextTitle');
        this.autoNextCancel = document.getElementById('autoNextCancel');

        // Settings Panel UI
        this.playerSettingsPanel = document.getElementById('playerSettingsPanel');
        this.speedChips = document.getElementById('speedChips');
        this.autoPlayToggle = document.getElementById('autoPlayToggle');
        this.autoPlaySwitch = document.getElementById('autoPlaySwitch');
        this.subtitlesToggle = document.getElementById('subtitlesToggle');
        this.subtitlesSwitch = document.getElementById('subtitlesSwitch');

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

        // Old login UI replaced by Auth Modal logic


        this.localFavorites = JSON.parse(localStorage.getItem('media_favorites')) || [];

        this.hlsPlayer = null;

        // Lazy Rendering
        this.itemsPerPage = 50;
        this.visibleCount = this.itemsPerPage;
        this.observer = null;

        // Admin State
        this.adminOverlay = document.getElementById('admin-overlay');
        this.adminContent = document.getElementById('admin-content');
        this.profileOverlay = document.getElementById('profile-overlay');
        this.adminChip = document.getElementById('admin-chip');

        const savedTheme = localStorage.getItem('theme') || 'dark';
        document.body.setAttribute('data-theme', savedTheme);

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
        this.setupThemeIcon();
        this.initSplash();
        this.setupEventListeners();
        this.setupPlayerEvents();
        this.connectWebSocket();
        await this.verifyAuth();
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

        // Filters (Old chips logic - keeping for compatibility but sidebar is primary)
        if (this.filterChips) {
            this.filterChips.forEach(chip => {
                chip.addEventListener('click', async () => {
                    const filter = chip.dataset.filter;
                    if (this.activeFilter === filter) return;

                    this.activeFilter = filter;
                    this.filterChips.forEach(c => c.classList.toggle('active', c === chip));
                    
                    await this.loadGallery();
                });
            });
        }

        // Sidebar Active State Sync
        const navItems = document.querySelectorAll('.nav-item');
        navItems.forEach(item => {
            item.addEventListener('click', () => {
                navItems.forEach(i => i.classList.remove('active'));
                item.classList.add('active');
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

        // Auth Modal Enter Key support
        const authModal = document.getElementById('auth-modal');
        if (authModal) {
            authModal.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    this.submitAuth();
                }
            });
        }

        // Global Back Navigation
        window.addEventListener('popstate', (e) => {
            this.currentPath = e.state?.path || "";
            this.loadGallery(false);
        });

        // Context Menu Actions
        document.getElementById('renameOption').onclick = () => this.showRenameDialog();
        document.getElementById('subtitleOption').onclick = () => this.subtitleInput.click();
        document.getElementById('deleteOption').onclick = () => this.handleDelete();
        this.subtitleInput.onchange = (e) => this.handleSubtitleUploadForVideo(e);
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

        // Login logic moved to global functions

    }

    setupPlayerEvents() {
        this.closePlayerBtn.addEventListener('click', () => this.closePlayer());
        this.prevBtn.addEventListener('click', () => this.playPrev());
        this.nextBtn.addEventListener('click', () => this.playNext());
        this.fullscreenBtn.addEventListener('click', () => this.toggleFullscreen());
        this.favBtn.addEventListener('click', () => this.toggleLocalFavorite());
        this.pipBtn.addEventListener('click', () => this.togglePiP());
        this.downloadBtn.addEventListener('click', () => this.downloadCurrent());

        // Settings Button
        if (this.settingsBtn) {
            this.settingsBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggleSettingsPanel();
            });
        }

        // Speed Chips
        if (this.speedChips) {
            this.speedChips.addEventListener('click', (e) => {
                const chip = e.target.closest('.speed-chip');
                if (!chip) return;
                e.stopPropagation();
                const speed = parseFloat(chip.dataset.speed);
                this.video.playbackRate = speed;
                this.speedChips.querySelectorAll('.speed-chip').forEach(c => c.classList.remove('active'));
                chip.classList.add('active');
                this.showToast(`Speed: ${speed}×`);
            });
        }

        // Auto-Play Toggle
        if (this.autoPlayToggle) {
            this.autoPlayToggle.addEventListener('click', (e) => {
                e.stopPropagation();
                this.autoPlayEnabled = !this.autoPlayEnabled;
                this.autoPlaySwitch.classList.toggle('on', this.autoPlayEnabled);
                this.showToast(this.autoPlayEnabled ? 'Auto-Play On' : 'Auto-Play Off');
            });
        }

        // Subtitles Toggle
        if (this.subtitlesToggle) {
            this.subtitlesToggle.addEventListener('click', (e) => {
                e.stopPropagation();
                const hasTrack = this.video.textTracks && this.video.textTracks.length > 0;
                if (hasTrack) {
                    const isShowing = this.video.textTracks[0].mode === 'showing';
                    this.video.textTracks[0].mode = isShowing ? 'hidden' : 'showing';
                    this.subtitlesSwitch.classList.toggle('on', !isShowing);
                    this.showToast(!isShowing ? 'Subtitles On' : 'Subtitles Off');
                } else {
                    this.showToast('No subtitle track loaded', true);
                }
            });
        }

        // Auto-Next Cancel
        if (this.autoNextCancel) {
            this.autoNextCancel.addEventListener('click', (e) => {
                e.stopPropagation();
                this.cancelAutoNext();
            });
        }

        // Close settings panel when clicking outside
        document.addEventListener('click', (e) => {
            if (this.settingsPanelOpen && 
                !e.target.closest('.player-settings-panel') && 
                !e.target.closest('#settingsBtn')) {
                this.closeSettingsPanel();
            }
        });

        // Video State — Auto-Next on ended
        this.video.addEventListener('ended', () => this.handleVideoEnded());
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
        if (this.isConnecting || (this.ws && this.ws.readyState === WebSocket.OPEN)) return;
        
        this.isConnecting = true;
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        this.ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

        this.ws.onopen = () => {
            this.isConnecting = false;
            console.log("WebSocket connected cleanly.");
        };

        this.ws.onmessage = (event) => {
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

        this.ws.onclose = () => {
            this.isConnecting = false;
            this.ws = null;
            console.warn("🔌 WebSocket disconnected. Reconnecting in 3s...");
            setTimeout(() => this.connectWebSocket(), 3000);
        };
        
        this.ws.onerror = (err) => {
            if (this.ws) this.ws.close();
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
                const authModal = document.getElementById('auth-modal');
                if (authModal) authModal.style.display = 'flex';
                return;
            }
            
            const authModal = document.getElementById('auth-modal');
            if (authModal) authModal.style.display = 'none'; // Hide if successful

            
            const data = await response.json();
            this.allFiles = data.items || [];
            this.visibleCount = this.itemsPerPage; // Reset scroll on new folder
            
            // Build current playlist (only videos)
            this.currentPlaylist = this.allFiles.filter(f => f.type === 'video');
            
            this.updateHeroBanner(this.allFiles);

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

    async handleLogin() {
        // Obsolete, replaced by submitAuth
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
            // Check if already present to avoid duplicates
            if (!this.filteredFiles.find(f => f.filename === "LIVE_STREAM")) {
                this.filteredFiles.unshift({
                    name: "Live Desktop Stream",
                    filename: "LIVE_STREAM",
                    type: "stream",
                    is_dir: false,
                    is_virtual: true
                });
            }
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

        // Check if we should render Swimlanes (Root Home View)
        if (!this.currentPath && !this.searchQuery && this.activeFilter === 'all') {
            this.renderSwimlanes();
            return;
        }

        // Otherwise, render standard grid
        this.renderGrid(this.filteredFiles);
    }

    renderGrid(files) {
        // Get chunk for infinite scroll
        const chunk = files.slice(0, this.visibleCount);
        
        chunk.forEach(file => {
            const card = this.createMediaCard(file);
            this.gallery.appendChild(card);
        });

        // Setup Infinite Scroll Sentinel
        if (this.visibleCount < files.length) {
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

    renderSwimlanes() {
        const categories = [
            { id: 'recent', title: 'Recently Added', filter: f => !f.is_dir && f.filename !== 'LIVE_STREAM', type: 'all' },
            { id: 'movies', title: 'Movies', filter: f => f.type === 'video' && !f.is_virtual && !f.filename.toLowerCase().includes('s0') && !f.filename.toLowerCase().includes('season'), type: 'video' },
            { id: 'tv', title: 'TV Shows', filter: f => f.type === 'video' && (f.filename.toLowerCase().includes('s0') || f.filename.toLowerCase().includes('season')), type: 'tv' },
            { id: 'docs', title: 'Documents', filter: f => f.type === 'document', type: 'document' },
            { id: 'folders', title: 'Folders', filter: f => f.is_dir, type: 'all' }
        ];

        categories.forEach(cat => {
            const items = this.filteredFiles.filter(cat.filter);
            if (items.length === 0) return;

            const section = document.createElement('section');
            section.className = 'swimlane-section';
            section.innerHTML = `
                <div class="swimlane-header">
                    <h2 class="swimlane-title">${cat.title}</h2>
                    <span class="swimlane-count">${items.length} items</span>
                    <div class="spacer" style="flex:1"></div>
                    <button class="text-btn swimlane-action" onclick="app.filterByCategory('${cat.type}')">View All</button>
                </div>
                <div class="swimlane-container">
                    <div class="swimlane-scroll">
                        <!-- Items injected here -->
                    </div>
                </div>
            `;

            const scrollContainer = section.querySelector('.swimlane-scroll');
            
            // Limit swimlane items for performance
            items.slice(0, 15).forEach(file => {
                const card = this.createMediaCard(file);
                scrollContainer.appendChild(card);
            });

            this.gallery.appendChild(section);
        });

        // Add Live Stream at the very top as a Hero section
        const liveStream = this.filteredFiles.find(f => f.filename === "LIVE_STREAM");
        if (liveStream) {
            const liveCard = this.createMediaCard(liveStream);
            liveCard.classList.add('live-card-featured');
            
            // Customize featured card internal layout
            liveCard.innerHTML = `
                <div class="card-media">
                    <span class="material-symbols-rounded" style="font-size: 120px; color: var(--m3-primary);">sensors</span>
                </div>
                <div class="featured-info">
                    <div class="badge">LIVE</div>
                    <h1 class="featured-title">Desktop Stream</h1>
                    <p class="featured-desc">Stream your desktop audio and video to any device on the network instantly.</p>
                    <button class="primary-btn" style="margin-top: 24px; padding: 16px 32px; border-radius: 32px;">
                        <span class="material-symbols-rounded">play_arrow</span>
                        Watch Now
                    </button>
                </div>
            `;
            this.gallery.prepend(liveCard);
        }
    }

    createMediaCard(file) {
        const card = document.createElement('div');
        card.className = 'media-card';
        
        const isFolder = file.is_dir;
        const isVideo = file.type === 'video';
        const displayName = this.cleanFilename(file.name);
        
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

        // --- Build Glanceable Metadata Tags ---
        const metaTags = [];
        
        // Type tag
        const typeIcons = { video: 'movie', audio: 'music_note', image: 'image', document: 'description', archive: 'inventory_2' };
        const typeClass = isFolder ? 'type-folder' : `type-${file.type === 'document' ? 'doc' : file.type}`;
        const typeLabel = isFolder ? 'Folder' : (file.type || 'File');
        const typeIcon = isFolder ? 'folder' : (typeIcons[file.type] || 'draft');
        metaTags.push(`<span class="meta-tag ${typeClass}"><span class="material-symbols-rounded">${typeIcon}</span>${typeLabel}</span>`);

        // File extension tag
        if (!isFolder && file.name) {
            const ext = file.name.split('.').pop();
            if (ext && ext.length <= 5 && ext !== file.name) {
                metaTags.push(`<span class="meta-tag type-ext">.${ext.toUpperCase()}</span>`);
            }
        }

        // Size tag
        if (file.size && !isFolder) {
            metaTags.push(`<span class="meta-tag type-size"><span class="material-symbols-rounded">straighten</span>${file.size}</span>`);
        }

        // Duration tag for videos (if available)
        if (file.duration) {
            metaTags.push(`<span class="meta-tag type-video"><span class="material-symbols-rounded">schedule</span>${file.duration}</span>`);
        }

        const metaOverlay = `
            <div class="card-meta-overlay">
                <div class="meta-tags">${metaTags.join('')}</div>
                <div class="meta-title">${displayName}</div>
                ${file.size ? `<div class="meta-subtitle">${file.size} • ${file.type || 'File'}</div>` : ''}
            </div>
        `;

        card.innerHTML = `
            <div class="fav-btn ${favClass}" data-filename="${file.filename}">
                <span class="material-symbols-rounded" style="font-variation-settings: 'FILL' ${file.is_favorite ? 1 : 0}">star</span>
            </div>
            <div class="card-media">
                ${content}
            </div>
            ${videoOverlay}
            ${metaOverlay}
            <div class="info">
                <div class="title">${displayName}</div>
                <div class="subtitle">${file.size || (isFolder ? 'Folder' : file.type)}</div>
            </div>
        `;

        const favBtn = card.querySelector('.fav-btn');
        if (favBtn) {
            favBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.toggleFav(file.filename);
            });
        }

        // Mobile tap: toggle metadata overlay
        let tapTimeout = null;
        card.addEventListener('touchstart', () => {
            tapTimeout = setTimeout(() => {
                card.classList.toggle('meta-active');
            }, 300);
        }, { passive: true });
        card.addEventListener('touchend', () => clearTimeout(tapTimeout), { passive: true });

        card.addEventListener('click', (e) => {
            if (e.target.closest('.fav-btn')) return;
            if (file.type === 'stream') {
                this.openStream();
            } else {
                this.handleItemClick(file);
            }
        });
        
        card.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            if (file.is_virtual) return;
            this.openContextMenu(file);
        });

        return card;
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
        this.categoryFilter = null;
        this.updateSidebarActive(path ? null : 'home');
        this.loadGallery();
    }

    navigateToRoot() {
        this.currentPath = "";
        this.activeFilter = "all";
        this.categoryFilter = null;
        this.updateSidebarActive('home');
        this.loadGallery();
    }

    setupThemeIcon() {
        const icon = document.getElementById('theme-icon');
        if (icon) {
            icon.innerText = document.body.getAttribute('data-theme') === 'light' ? 'light_mode' : 'dark_mode';
        }
    }

    toggleTheme() {
        const body = document.body;
        const isDark = body.getAttribute('data-theme') !== 'light';
        const newTheme = isDark ? 'light' : 'dark';
        body.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        this.setupThemeIcon();
    }

    initSplash() {
        const splash = document.getElementById('splash-screen');
        const actionHub = document.getElementById('action-hub');
        const appLayout = document.querySelector('.app-layout');

        if (appLayout) appLayout.style.display = 'none';

        if (splash) {
            setTimeout(() => {
                splash.classList.add('hidden');
                setTimeout(() => {
                    splash.style.display = 'none';
                    if (actionHub) actionHub.classList.remove('hidden');
                }, 500);
            }, 2000);
        } else {
            if (actionHub) actionHub.classList.remove('hidden');
        }
    }

    hubNavigate(action) {
        const actionHub = document.getElementById('action-hub');
        const appLayout = document.querySelector('.app-layout');
        
        if (actionHub) {
            actionHub.classList.add('hidden');
            setTimeout(() => {
                actionHub.style.display = 'none';
                if (appLayout) {
                    appLayout.style.display = 'flex';
                }
                
                switch(action) {
                    case 'watch':
                        this.navigateToRoot();
                        break;
                    case 'upload':
                        this.navigateToRoot();
                        this.fileInput.click();
                        break;
                    case 'docs':
                        this.filterByCategory('document');
                        break;
                }

                if (!localStorage.getItem('onboardingCompleted')) {
                    this.startOnboarding();
                }
            }, 500);
        }
    }

    startOnboarding() {
        this.onboardingStep = 0;
        this.onboardingSteps = [
            { title: 'Welcome', text: 'Welcome to StreamDrop! This hub lets you manage all your media.' },
            { title: 'Navigation', text: 'Use the sidebar to filter between Movies, TV Shows, and Documents.' },
            { title: 'Upload', text: 'Click the + button or Send/Upload to add files to your library.' }
        ];
        
        const guide = document.getElementById('onboarding-guide');
        if (guide) {
            guide.classList.remove('hidden');
            this.updateOnboardingUI();
        }
    }

    updateOnboardingUI() {
        const step = this.onboardingSteps[this.onboardingStep];
        const title = document.getElementById('onboarding-title');
        const text = document.getElementById('onboarding-text');
        if (title) title.innerText = step.title;
        if (text) text.innerText = step.text;
    }

    nextOnboardingStep() {
        if (this.onboardingStep < this.onboardingSteps.length - 1) {
            this.onboardingStep++;
            this.updateOnboardingUI();
        } else {
            this.skipOnboarding();
        }
    }

    skipOnboarding() {
        const guide = document.getElementById('onboarding-guide');
        if (guide) guide.classList.add('hidden');
        localStorage.setItem('onboardingCompleted', 'true');
    }

    async filterByCategory(category) {
        this.currentPath = ""; // Go back to root for categories
        this.activeFilter = "all";
        this.categoryFilter = category;
        this.updateSidebarActive(category === 'video' ? 'movies' : (category === 'tv' ? 'tv' : 'docs'));
        
        await this.loadGallery();
        
        // Post-process allFiles to only show selected category
        if (category === 'tv') {
            this.filteredFiles = this.allFiles.filter(f => f.type === 'video' && (f.filename.toLowerCase().includes('s0') || f.filename.toLowerCase().includes('season')));
        } else if (category === 'video') {
            this.filteredFiles = this.allFiles.filter(f => f.type === 'video');
        } else if (category === 'document') {
            this.filteredFiles = this.allFiles.filter(f => f.type === 'document');
        }
        
        this.renderGallery();
    }

    showFavorites() {
        this.activeFilter = 'favorites';
        this.categoryFilter = null;
        this.updateSidebarActive('favorites');
        this.loadGallery();
    }

    updateSidebarActive(navId) {
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.toggle('active', item.dataset.nav === navId);
        });
    }

    // --- Player Logic ---

    async openPlayer(index) {
        if (index < 0 || index >= this.currentPlaylist.length) return;
        
        this.cancelAutoNext();
        this.closeSettingsPanel();
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
                if (typeof Hls !== 'undefined' && Hls.isSupported()) {
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
        this.cancelAutoNext();
        this.closeSettingsPanel();
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
        }, 2500);
    }

    // --- Auto-Next Countdown System ---
    handleVideoEnded() {
        // Clear saved resume time
        const currentVid = this.currentPlaylist[this.currentVideoIndex];
        if (currentVid) {
            localStorage.removeItem(`resume_${currentVid.filename}`);
        }

        if (!this.autoPlayEnabled || this.currentVideoIndex >= this.currentPlaylist.length - 1) {
            // No next video or auto-play disabled
            return;
        }

        const nextIndex = this.currentVideoIndex + 1;
        const nextItem = this.currentPlaylist[nextIndex];
        if (!nextItem) return;

        // Show countdown overlay
        this.autoNextTitle.innerText = this.cleanFilename(nextItem.name);
        this.autoNextOverlay.classList.add('visible');

        const COUNTDOWN_SECONDS = 7;
        const CIRCLE_CIRCUMFERENCE = 113.1; // 2 * PI * 18
        let remaining = COUNTDOWN_SECONDS;

        this.autoNextSeconds.innerText = remaining;
        this.autoNextProgress.style.strokeDashoffset = '0';

        this.autoNextInterval = setInterval(() => {
            remaining -= 0.1;
            const progress = 1 - (remaining / COUNTDOWN_SECONDS);
            this.autoNextProgress.style.strokeDashoffset = (progress * CIRCLE_CIRCUMFERENCE).toString();
            this.autoNextSeconds.innerText = Math.ceil(remaining);

            if (remaining <= 0) {
                this.cancelAutoNext();
                this.openPlayer(nextIndex);
            }
        }, 100);
    }

    cancelAutoNext() {
        if (this.autoNextInterval) {
            clearInterval(this.autoNextInterval);
            this.autoNextInterval = null;
        }
        if (this.autoNextOverlay) {
            this.autoNextOverlay.classList.remove('visible');
        }
    }

    // --- Floating Settings Panel ---
    toggleSettingsPanel() {
        if (this.settingsPanelOpen) {
            this.closeSettingsPanel();
        } else {
            this.openSettingsPanel();
        }
    }

    openSettingsPanel() {
        this.settingsPanelOpen = true;
        this.playerSettingsPanel.classList.add('visible');
        
        // Sync current state
        this.autoPlaySwitch.classList.toggle('on', this.autoPlayEnabled);
        
        // Sync speed chips
        const currentSpeed = this.video.playbackRate;
        this.speedChips.querySelectorAll('.speed-chip').forEach(chip => {
            chip.classList.toggle('active', parseFloat(chip.dataset.speed) === currentSpeed);
        });

        // Sync subtitle state
        const hasTrack = this.video.textTracks && this.video.textTracks.length > 0;
        const isShowing = hasTrack && this.video.textTracks[0].mode === 'showing';
        this.subtitlesSwitch.classList.toggle('on', isShowing);

        this.resetIdleTimer();
    }

    closeSettingsPanel() {
        this.settingsPanelOpen = false;
        this.playerSettingsPanel.classList.remove('visible');
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

    async handleOnTheFlySubtitleUpload(event) {
        const file = event.target.files[0];
        if (!file) return;

        const formData = new FormData();
        formData.append("file", file);
        
        this.showToast("Uploading subtitle...");
        
        try {
            const response = await fetch(`/api/upload?path=${encodeURIComponent(this.currentPath)}`, {
                method: 'POST',
                body: formData
            });

            if (response.ok) {
                this.showToast("Subtitle loaded successfully!");
                
                const track = document.createElement('track');
                track.kind = 'subtitles';
                track.label = file.name;
                track.srclang = 'en';
                track.src = URL.createObjectURL(file); 
                track.default = true;
                
                const oldTracks = this.video.querySelectorAll('track');
                oldTracks.forEach(t => t.remove());

                this.video.appendChild(track);
                
                if (this.video.textTracks && this.video.textTracks.length > 0) {
                    this.video.textTracks[0].mode = 'showing';
                }
            } else {
                this.showToast("Failed to upload subtitle.", true);
            }
        } catch (e) {
            this.showToast("Error uploading subtitle.", true);
        }
        
        event.target.value = ''; 
    }

    async handleSubtitleUploadForVideo(e) {
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

            this.showToast("Subtitles uploaded successfully!");
            this.closeContextMenu();
            await this.loadGallery();
        } catch (err) {
            console.error("Subtitle upload error:", err);
            this.showToast("Subtitle upload failed", true);
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
                this.showToast(err.detail || "Rename failed", true);
            }
        } catch (e) {
            console.error("Rename failed:", e);
        }
    }

    // --- Auth Logic ---

    async verifyAuth() {
        try {
            const res = await fetch('/api/auth/verify');
            if (res.ok) {
                this.currentUser = await res.json();
                this.updateUserUI();
                document.getElementById('auth-modal').style.display = 'none';
            } else {
                document.getElementById('auth-modal').style.display = 'flex';
            }
        } catch (error) {
            console.error("Auth verification failed", error);
        }
    }

    updateUserUI() {
        if (!this.currentUser) return;
        
        // Header Profile Chip
        document.getElementById('user-display-name').innerText = this.currentUser.display_name || this.currentUser.username;
        const avatarUrl = this.currentUser.avatar_url || `https://api.dicebear.com/7.x/avataaars/svg?seed=${this.currentUser.username}`;
        document.getElementById('user-avatar').src = avatarUrl;
        document.getElementById('user-profile-chip').classList.remove('hidden');

        // Admin Chip Visibility
        if (this.currentUser.role === 'admin') {
            this.adminChip.classList.remove('hidden');
        } else {
            this.adminChip.classList.add('hidden');
        }

        // Profile Overlay Sync
        document.getElementById('profile-avatar-large').src = avatarUrl;
        document.getElementById('profile-username').innerText = this.currentUser.display_name || this.currentUser.username;
        document.getElementById('profile-role').innerText = this.currentUser.role.toUpperCase();
    }

    toggleAuthMode() {
        this.isSignUpMode = !this.isSignUpMode;
        document.getElementById('auth-title').innerText = this.isSignUpMode ? "Create Account" : "Welcome Back";
        document.getElementById('auth-action-btn').innerText = this.isSignUpMode ? "Sign Up" : "Login";
        document.getElementById('auth-switch-text').innerText = this.isSignUpMode ? "Already have an account? Login." : "New here? Sign up instead.";
    }

    async submitAuth() {
        const user = document.getElementById('auth-username').value;
        const pass = document.getElementById('auth-password').value;
        
        if (!user || !pass) return this.showToast("Please fill all fields", true);
        
        const endpoint = this.isSignUpMode ? "/api/auth/register" : "/api/auth/login";
        
        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username: user, password: pass })
            });
            
            if (response.ok) {
                this.showToast(this.isSignUpMode ? "Account created!" : "Logged in successfully!");
                await this.verifyAuth();
                await this.loadGallery(); 
            } else {
                const data = await response.json();
                this.showToast(data.detail || "Authentication failed", true);
            }
        } catch (err) {
            this.showToast("Network error during authentication", true);
        }
    }

    toggleCCMenu() {
        const menu = document.getElementById('cc-menu');
        if (menu) menu.classList.toggle('hidden');
    }

    setSubtitles(enable) {
        if (this.video && this.video.textTracks && this.video.textTracks.length > 0) {
            this.video.textTracks[0].mode = enable ? 'showing' : 'hidden';
            this.showToast(enable ? "Subtitles On" : "Subtitles Off");
        } else if (enable) {
            this.showToast("No subtitle track loaded", true);
        }
        const menu = document.getElementById('cc-menu');
        if (menu) menu.classList.add('hidden');
    }

    updateHeroBanner(files) {
        const hero = document.getElementById('hero-banner');
        if (!hero) return;

        const videos = files.filter(f => f.type === 'video');
        if (videos.length === 0) {
            hero.classList.add('hidden');
            return;
        }

        // Use the first video or a random one as featured
        const featured = videos[0];
        document.getElementById('hero-title').innerText = this.cleanFilename(featured.name);
        document.getElementById('hero-meta').innerText = `Ready to watch in ${this.currentPath || 'Home'}`;
        
        if (featured.thumbnail_url) {
            document.getElementById('hero-bg').style.backgroundImage = `url(${featured.thumbnail_url})`;
        }

        document.getElementById('hero-play-btn').onclick = () => {
            const index = this.currentPlaylist.findIndex(v => v.filename === featured.filename);
            this.openPlayer(index);
        };

        hero.classList.remove('hidden');
    }

    openProfileSettings() {
        this.profileOverlay.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
    }

    closeProfileSettings() {
        this.profileOverlay.classList.add('hidden');
        document.body.style.overflow = '';
    }

    // --- Admin Dashboard Logic ---

    openAdminPanel() {
        this.adminOverlay.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
        this.switchAdminTab('stats');
    }

    closeAdminPanel() {
        this.adminOverlay.classList.add('hidden');
        document.body.style.overflow = '';
    }

    async switchAdminTab(tab) {
        this.currentAdminTab = tab;
        // Update active tab UI
        document.querySelectorAll('.admin-tab').forEach(el => {
            el.classList.toggle('active', el.dataset.tab === tab);
        });

        this.adminContent.innerHTML = `<div style="display:flex; justify-content:center; padding:40px;"><span class="material-symbols-rounded" style="animation:spin 1s linear infinite; font-size:32px;">sync</span></div>`;

        try {
            if (tab === 'stats') await this.renderAdminStats();
            else if (tab === 'users') await this.renderAdminUsers();
            else if (tab === 'audit') await this.renderAdminLogs();
        } catch (err) {
            this.adminContent.innerHTML = `<div style="text-align:center; padding:40px; color:var(--accent-red);">Failed to load ${tab}. Check permissions.</div>`;
        }
    }

    async renderAdminStats() {
        const res = await fetch('/api/auth/stats');
        const data = await res.json();
        
        const formatBytes = (bytes) => {
            if (bytes === 0) return '0 B';
            const k = 1024;
            const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        };

        this.adminContent.innerHTML = `
            <div class="stat-grid">
                <div class="stat-card">
                    <span class="material-symbols-rounded">person</span>
                    <div class="stat-value">${data.total_users}</div>
                    <div class="stat-label">Total Users</div>
                </div>
                <div class="stat-card">
                    <span class="material-symbols-rounded">movie</span>
                    <div class="stat-value">${data.total_media}</div>
                    <div class="stat-label">Media Files</div>
                </div>
                <div class="stat-card">
                    <span class="material-symbols-rounded">play_circle</span>
                    <div class="stat-value">${data.total_plays}</div>
                    <div class="stat-label">Total Plays</div>
                </div>
                <div class="stat-card">
                    <span class="material-symbols-rounded">storage</span>
                    <div class="stat-value">${formatBytes(data.total_storage_bytes)}</div>
                    <div class="stat-label">Storage Used</div>
                </div>
                <div class="stat-card">
                    <span class="material-symbols-rounded">history</span>
                    <div class="stat-value">${data.audit_count}</div>
                    <div class="stat-label">Audit Logs</div>
                </div>
            </div>
            
            <h3 style="margin: 24px 0 16px;">System Health</h3>
            <div class="admin-table-container">
                <table class="admin-table">
                    <thead>
                        <tr>
                            <th>Parameter</th>
                            <th>Value</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr><td>Platform</td><td>${navigator.platform}</td></tr>
                        <tr><td>Browser</td><td>${navigator.userAgent.split(' ').pop()}</td></tr>
                        <tr><td>Connection</td><td>${navigator.onLine ? 'Online' : 'Offline'}</td></tr>
                    </tbody>
                </table>
            </div>
        `;
    }

    async renderAdminLogs() {
        const res = await fetch('/api/auth/audit');
        const data = await res.json();
        const logs = data.logs || [];
        
        const getActionClass = (action) => {
            if (action.includes('DELETE') || action.includes('DEACTIVATE')) return 'badge-danger';
            if (action.includes('CREATE') || action.includes('REGISTER') || action === 'LOGIN') return 'badge-success';
            if (action.includes('UPDATE') || action.includes('EDIT')) return 'badge-warning';
            return 'badge-info';
        };

        const rows = logs.map(log => `
            <tr class="log-row">
                <td>${new Date(log.timestamp).toLocaleString()}</td>
                <td><span class="badge ${getActionClass(log.action)}">${log.action}</span></td>
                <td><div style="font-weight:600;">${log.user}</div></td>
                <td><div style="max-width:200px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; opacity:0.8;">${log.resource || '-'}</div></td>
                <td>
                    <div class="log-details" onclick="this.classList.toggle('expanded')">
                        ${log.details ? JSON.stringify(log.details) : '-'}
                    </div>
                </td>
            </tr>
        `).join('');

        this.adminContent.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;">
                <h3 style="margin:0;">Activity Audit</h3>
                <div class="search-box" style="max-width:300px;">
                    <span class="material-symbols-rounded">search</span>
                    <input type="text" placeholder="Filter logs..." oninput="app.filterAdminLogs(this.value)">
                </div>
            </div>
            <div class="admin-table-container">
                <table class="admin-table" id="audit-table">
                    <thead>
                        <tr>
                            <th>Timestamp</th>
                            <th>Action</th>
                            <th>User</th>
                            <th>Resource</th>
                            <th>Details</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${rows || '<tr><td colspan="5" style="text-align:center;">No activity logs found.</td></tr>'}
                    </tbody>
                </table>
            </div>
        `;
    }

    filterAdminLogs(query) {
        const q = query.toLowerCase();
        const rows = document.querySelectorAll('#audit-table tbody tr.log-row');
        rows.forEach(row => {
            const text = row.innerText.toLowerCase();
            row.style.display = text.includes(q) ? '' : 'none';
        });
    }

    async renderAdminUsers() {
        const res = await fetch('/api/auth/users');
        const data = await res.json();
        const users = data.users || [];
        
        const rows = users.map(u => `
            <tr data-user-id="${u.id}">
                <td>
                    <div style="display:flex; align-items:center; gap:12px;">
                        <div style="width:32px; height:32px; border-radius:50%; background:var(--m3-primary-container); color:var(--m3-on-primary-container); display:flex; align-items:center; justify-content:center; font-weight:bold; font-size:12px;">
                            ${u.username.substring(0, 2).toUpperCase()}
                        </div>
                        <div>
                            <div>${u.username} ${u.id === this.currentUser.id ? '<span style="font-size:10px; opacity:0.5;">(YOU)</span>' : ''}</div>
                            <div style="font-size:12px; opacity:0.6;">Last login: ${u.last_login ? new Date(u.last_login).toLocaleString() : 'Never'}</div>
                        </div>
                    </div>
                </td>
                <td>
                    <select class="admin-select" onchange="app.changeUserRole(${u.id}, this.value)" ${u.id === this.currentUser.id ? 'disabled' : ''}>
                        <option value="guest" ${u.role === 'guest' ? 'selected' : ''}>Guest</option>
                        <option value="family" ${u.role === 'family' ? 'selected' : ''}>Family</option>
                        <option value="admin" ${u.role === 'admin' ? 'selected' : ''}>Admin</option>
                    </select>
                </td>
                <td>
                    <span class="badge ${u.is_active ? 'active' : 'inactive'}">${u.is_active ? 'Active' : 'Disabled'}</span>
                </td>
                <td>
                    <div style="display:flex; gap:8px;">
                        <button class="icon-btn ${u.is_active ? 'danger' : 'success'}" 
                                onclick="app.toggleUserActive(${u.id}, ${u.is_active})" 
                                title="${u.is_active ? 'Deactivate' : 'Activate'}"
                                ${u.id === this.currentUser.id ? 'disabled' : ''}>
                            <span class="material-symbols-rounded">${u.is_active ? 'block' : 'check_circle'}</span>
                        </button>
                        <button class="icon-btn danger" 
                                onclick="app.deleteUser(${u.id}, '${u.username}')" 
                                title="Delete User"
                                ${u.id === this.currentUser.id ? 'disabled' : ''}>
                            <span class="material-symbols-rounded">delete</span>
                        </button>
                    </div>
                </td>
            </tr>
        `).join('');

        this.adminContent.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;">
                <h3 style="margin:0;">User Accounts</h3>
                <button class="hero-btn" onclick="app.showCreateUserModal()" style="padding: 8px 16px; font-size:13px;">
                    <span class="material-symbols-rounded" style="font-size:18px;">person_add</span>
                    Create User
                </button>
            </div>
            <div class="admin-table-container">
                <table class="admin-table">
                    <thead>
                        <tr>
                            <th>User</th>
                            <th>Role</th>
                            <th>Status</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${rows || '<tr><td colspan="4" style="text-align:center;">No users found.</td></tr>'}
                    </tbody>
                </table>
            </div>
        `;
    }

    async toggleUserActive(userId, currentStatus) {
        try {
            const res = await fetch(`/api/auth/users/${userId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ is_active: !currentStatus })
            });
            if (res.ok) {
                this.showToast(currentStatus ? "User deactivated" : "User activated");
                this.renderAdminUsers();
            } else {
                const err = await res.json();
                this.showToast(err.detail || "Action failed", "error");
            }
        } catch (e) {
            this.showToast("Network error", "error");
        }
    }

    async changeUserRole(userId, newRole) {
        try {
            const res = await fetch(`/api/auth/users/${userId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ role: newRole })
            });
            if (res.ok) {
                this.showToast(`Role updated to ${newRole}`);
                this.renderAdminUsers();
            } else {
                const err = await res.json();
                this.showToast(err.detail || "Role update failed", "error");
            }
        } catch (e) {
            this.showToast("Network error", "error");
        }
    }

    async deleteUser(userId, username) {
        if (!confirm(`Are you sure you want to PERMANENTLY delete user "${username}"? This cannot be undone.`)) return;
        
        try {
            const res = await fetch(`/api/auth/users/${userId}`, { method: 'DELETE' });
            if (res.ok) {
                this.showToast("User deleted successfully");
                this.renderAdminUsers();
            } else {
                const err = await res.json();
                this.showToast(err.detail || "Delete failed", "error");
            }
        } catch (e) {
            this.showToast("Network error", "error");
        }
    }

    showCreateUserModal() {
        const username = prompt("Enter new username:");
        if (!username) return;
        const password = prompt("Enter password (min 6 chars):");
        if (!password || password.length < 6) {
            this.showToast("Invalid password", "error");
            return;
        }
        const role = prompt("Enter role (guest/family/admin):", "guest");
        if (!['guest', 'family', 'admin'].includes(role)) {
            this.showToast("Invalid role", "error");
            return;
        }

        this.createUser(username, password, role);
    }

    async createUser(username, password, role) {
        try {
            const res = await fetch('/api/auth/users', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password, role })
            });
            if (res.ok) {
                this.showToast("User created successfully");
                this.renderAdminUsers();
            } else {
                const err = await res.json();
                this.showToast(err.detail || "Creation failed", "error");
            }
        } catch (e) {
            this.showToast("Network error", "error");
        }
    }

    async logout() {
        try {
            const res = await fetch('/api/auth/logout', { method: 'POST' });
            if (res.ok) {
                this.currentUser = null;
                this.showToast("Logged out");
                location.reload(); // Simplest way to reset state
            }
        } catch (error) {
            console.error("Logout failed", error);
        }
    }
}

// Global instance
const app = new StreamDropApp();
