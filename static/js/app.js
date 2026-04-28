/**
 * StreamDrop — Frontend Application
 * Handles PIN auth, stream controls, file upload/gallery, QR, toasts.
 */

(function () {
    'use strict';

    // ═══ DOM REFERENCES ═══════════════════════════════
    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    const dom = {
        // PIN Gate
        pinGate: $('#pin-gate'),
        pinInputRow: $('#pin-input-row'),
        pinDigits: $$('.pin-digit'),
        pinError: $('#pin-error'),
        pinSubmit: $('#pin-submit'),
        // Dashboard
        dashboard: $('#dashboard'),
        // Header
        statusIp: $('#status-ip'),
        qrBtn: $('#qr-btn'),
        // Stream
        streamPanel: $('#stream-panel'),
        streamStatus: $('#stream-status'),
        streamPlaceholder: $('#stream-placeholder'),
        streamImg: $('#stream-img'),
        startBtn: $('#stream-start-btn'),
        stopBtn: $('#stream-stop-btn'),
        toggleBtn: $('#stream-toggle-btn'),
        toggleLabel: $('#toggle-label'),
        // Quick Share
        dropZone: $('#drop-zone'),
        fileInput: $('#file-input'),
        uploadProgress: $('#upload-progress'),
        progressFilename: $('#progress-filename'),
        progressPercent: $('#progress-percent'),
        progressBarFill: $('#progress-bar-fill'),
        galleryGrid: $('#gallery-grid'),
        emptyState: $('#empty-state'),
        fileCount: $('#file-count'),
        // QR Modal
        qrModal: $('#qr-modal'),
        qrImg: $('#qr-img'),
        qrClose: $('#qr-close'),
        modalUrl: $('#modal-url'),
        // Lightbox
        lightbox: $('#lightbox'),
        lightboxImg: $('#lightbox-img'),
        lightboxClose: $('#lightbox-close'),
        // Toasts
        toastContainer: $('#toast-container'),
    };

    // ═══ STATE ═════════════════════════════════════════
    let serverUrl = '';
    let currentMode = 'webcam';
    let isStreaming = false;

    // ═══ TOAST SYSTEM ═════════════════════════════════
    function toast(message, type = 'info', duration = 3500) {
        const icons = { success: '✓', error: '✕', info: 'ℹ' };
        const el = document.createElement('div');
        el.className = `toast ${type}`;
        el.innerHTML = `<span class="toast-icon">${icons[type] || 'ℹ'}</span><span>${message}</span>`;
        dom.toastContainer.appendChild(el);

        setTimeout(() => {
            el.classList.add('exit');
            setTimeout(() => el.remove(), 350);
        }, duration);
    }

    // ═══ API HELPERS ══════════════════════════════════
    async function api(path, options = {}) {
        try {
            const res = await fetch(path, {
                credentials: 'include',
                ...options,
            });

            if (res.status === 401) {
                // Session expired — show PIN gate
                showPinGate();
                throw new Error('Session expired');
            }

            if (!res.ok) {
                const data = await res.json().catch(() => ({}));
                throw new Error(data.detail || `Error ${res.status}`);
            }

            return res;
        } catch (err) {
            if (err.message !== 'Session expired') {
                console.error(`API ${path}:`, err);
            }
            throw err;
        }
    }

    async function apiJson(path, options = {}) {
        const res = await api(path, options);
        return res.json();
    }

    // ═══ PIN AUTH ══════════════════════════════════════
    function showPinGate() {
        dom.pinGate.classList.remove('hidden');
        dom.dashboard.classList.add('hidden');
        dom.pinDigits[0].focus();
    }

    function showDashboard() {
        dom.pinGate.classList.add('hidden');
        dom.dashboard.classList.remove('hidden');
        loadStatus();
        loadGallery();
    }

    function initPinInput() {
        dom.pinDigits.forEach((input, i) => {
            input.addEventListener('input', (e) => {
                const val = e.target.value.replace(/\D/g, '');
                e.target.value = val;
                if (val && i < 3) {
                    dom.pinDigits[i + 1].focus();
                }
                // Auto-submit when all 4 digits entered
                if (i === 3 && val) {
                    submitPin();
                }
            });

            input.addEventListener('keydown', (e) => {
                if (e.key === 'Backspace' && !e.target.value && i > 0) {
                    dom.pinDigits[i - 1].focus();
                    dom.pinDigits[i - 1].value = '';
                }
                if (e.key === 'Enter') {
                    submitPin();
                }
            });

            // Select all text on focus for easy re-entry
            input.addEventListener('focus', () => input.select());
        });

        dom.pinSubmit.addEventListener('click', submitPin);
    }

    async function submitPin() {
        const pin = Array.from(dom.pinDigits).map(d => d.value).join('');
        if (pin.length !== 4) {
            dom.pinError.textContent = 'Please enter all 4 digits';
            return;
        }

        dom.pinSubmit.disabled = true;
        dom.pinError.textContent = '';

        try {
            await apiJson('/api/auth', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ pin }),
            });
            showDashboard();
            toast('Authenticated successfully', 'success');
        } catch (err) {
            dom.pinError.textContent = 'Invalid PIN. Try again.';
            dom.pinInputRow.classList.add('shake');
            setTimeout(() => dom.pinInputRow.classList.remove('shake'), 600);
            // Clear inputs
            dom.pinDigits.forEach(d => (d.value = ''));
            dom.pinDigits[0].focus();
        } finally {
            dom.pinSubmit.disabled = false;
        }
    }

    // ═══ STATUS ═══════════════════════════════════════
    async function loadStatus() {
        try {
            const data = await apiJson('/api/status');
            serverUrl = data.url;
            dom.statusIp.textContent = `${data.hostname} · ${data.ip}:${data.port}`;
            currentMode = data.stream.mode;
            isStreaming = data.stream.running;
            updateStreamUI();
        } catch (err) {
            dom.statusIp.textContent = 'Disconnected';
        }
    }

    // ═══ STREAM CONTROLS ══════════════════════════════
    function updateStreamUI() {
        const statusDot = dom.streamStatus.querySelector('.stream-dot');
        const statusText = dom.streamStatus.querySelector('span:last-child');

        if (isStreaming) {
            statusDot.className = 'stream-dot live';
            statusText.textContent = 'Live';
            dom.streamPlaceholder.classList.add('hidden');
            dom.streamImg.classList.remove('hidden');
            dom.streamImg.src = '/api/stream/video?' + Date.now();
            dom.startBtn.disabled = true;
            dom.stopBtn.disabled = false;
        } else {
            statusDot.className = 'stream-dot offline';
            statusText.textContent = 'Offline';
            dom.streamPlaceholder.classList.remove('hidden');
            dom.streamImg.classList.add('hidden');
            dom.streamImg.src = '';
            dom.startBtn.disabled = false;
            dom.stopBtn.disabled = true;
        }

        dom.toggleLabel.textContent =
            currentMode === 'webcam' ? 'Switch to Screen' : 'Switch to Webcam';
    }

    function initStreamControls() {
        dom.startBtn.addEventListener('click', async () => {
            try {
                dom.startBtn.disabled = true;
                const data = await apiJson('/api/stream/start', { method: 'POST' });
                isStreaming = data.running;
                currentMode = data.mode;
                updateStreamUI();
                toast('Stream started', 'success');
            } catch (err) {
                toast('Failed to start stream', 'error');
                dom.startBtn.disabled = false;
            }
        });

        dom.stopBtn.addEventListener('click', async () => {
            try {
                dom.stopBtn.disabled = true;
                const data = await apiJson('/api/stream/stop', { method: 'POST' });
                isStreaming = data.running;
                updateStreamUI();
                toast('Stream stopped', 'info');
            } catch (err) {
                toast('Failed to stop stream', 'error');
                dom.stopBtn.disabled = false;
            }
        });

        dom.toggleBtn.addEventListener('click', async () => {
            try {
                dom.toggleBtn.disabled = true;
                const data = await apiJson('/api/stream/toggle', { method: 'POST' });
                currentMode = data.mode;
                isStreaming = data.running;
                updateStreamUI();
                toast(`Switched to ${currentMode}`, 'info');
            } catch (err) {
                toast('Failed to toggle source', 'error');
            } finally {
                dom.toggleBtn.disabled = false;
            }
        });
    }

    // ═══ FILE UPLOAD ══════════════════════════════════
    function initDropZone() {
        const zone = dom.dropZone;

        // Click to browse
        zone.addEventListener('click', () => dom.fileInput.click());

        // File input change
        dom.fileInput.addEventListener('change', (e) => {
            if (e.target.files.length) {
                uploadFiles(e.target.files);
                e.target.value = '';
            }
        });

        // Drag events
        ['dragenter', 'dragover'].forEach(evt => {
            zone.addEventListener(evt, (e) => {
                e.preventDefault();
                e.stopPropagation();
                zone.classList.add('dragover');
            });
        });

        ['dragleave', 'drop'].forEach(evt => {
            zone.addEventListener(evt, (e) => {
                e.preventDefault();
                e.stopPropagation();
                zone.classList.remove('dragover');
            });
        });

        zone.addEventListener('drop', (e) => {
            if (e.dataTransfer.files.length) {
                uploadFiles(e.dataTransfer.files);
            }
        });
    }

    async function uploadFiles(fileList) {
        const files = Array.from(fileList);

        for (const file of files) {
            await uploadSingleFile(file);
        }
    }

    function uploadSingleFile(file) {
        return new Promise((resolve) => {
            const formData = new FormData();
            formData.append('file', file);

            const xhr = new XMLHttpRequest();

            // Show progress
            dom.uploadProgress.classList.remove('hidden');
            dom.progressFilename.textContent = file.name;
            dom.progressPercent.textContent = '0%';
            dom.progressBarFill.style.width = '0%';

            xhr.upload.addEventListener('progress', (e) => {
                if (e.lengthComputable) {
                    const pct = Math.round((e.loaded / e.total) * 100);
                    dom.progressPercent.textContent = `${pct}%`;
                    dom.progressBarFill.style.width = `${pct}%`;
                }
            });

            xhr.addEventListener('load', () => {
                dom.uploadProgress.classList.add('hidden');
                if (xhr.status === 200) {
                    toast(`Uploaded: ${file.name}`, 'success');
                    loadGallery();
                } else {
                    let detail = 'Upload failed';
                    try { detail = JSON.parse(xhr.responseText).detail; } catch (_) {}
                    toast(detail, 'error');
                }
                resolve();
            });

            xhr.addEventListener('error', () => {
                dom.uploadProgress.classList.add('hidden');
                toast('Upload failed — network error', 'error');
                resolve();
            });

            xhr.open('POST', '/api/upload');
            xhr.withCredentials = true;
            xhr.send(formData);
        });
    }

    // ═══ GALLERY ══════════════════════════════════════
    async function loadGallery() {
        try {
            const data = await apiJson('/api/files');
            renderGallery(data.files);
        } catch (err) {
            // Silently fail — may be auth issue
        }
    }

    function renderGallery(files) {
        dom.galleryGrid.innerHTML = '';
        dom.fileCount.textContent = `${files.length} file${files.length !== 1 ? 's' : ''}`;

        if (files.length === 0) {
            dom.emptyState.classList.remove('hidden');
            return;
        }

        dom.emptyState.classList.add('hidden');

        files.forEach((file, index) => {
            const card = createFileCard(file, index);
            dom.galleryGrid.appendChild(card);
        });
    }

    function createFileCard(file, index) {
        const card = document.createElement('div');
        card.className = 'file-card';
        card.style.animationDelay = `${index * 0.05}s`;

        // Preview
        const preview = document.createElement('div');
        preview.className = 'file-card-preview';

        if (file.type === 'image') {
            const img = document.createElement('img');
            img.src = file.thumbnail_url || file.serve_url;
            img.alt = file.name;
            img.loading = 'lazy';
            preview.appendChild(img);
            // Click to open lightbox
            preview.addEventListener('click', () => openLightbox(file.serve_url));
        } else if (file.type === 'video') {
            const video = document.createElement('video');
            video.src = file.serve_url;
            video.muted = true;
            video.preload = 'metadata';
            video.addEventListener('mouseenter', () => { video.currentTime = 0; video.play(); });
            video.addEventListener('mouseleave', () => video.pause());
            preview.appendChild(video);
            preview.addEventListener('click', () => openLightbox(null, file.serve_url));
        } else {
            const icon = document.createElement('div');
            icon.className = 'file-icon';
            icon.textContent = getFileIcon(file.type);
            preview.appendChild(icon);
        }

        // Info
        const info = document.createElement('div');
        info.className = 'file-card-info';

        const name = document.createElement('div');
        name.className = 'file-card-name';
        name.textContent = file.name;
        name.title = file.name;

        const meta = document.createElement('div');
        meta.className = 'file-card-meta';

        const size = document.createElement('span');
        size.textContent = file.size_formatted;

        const actions = document.createElement('div');
        actions.className = 'file-card-actions';

        // Download button
        const dlBtn = document.createElement('button');
        dlBtn.className = 'card-action-btn';
        dlBtn.title = 'Download';
        dlBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
        </svg>`;
        dlBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            downloadFile(file.name);
        });

        // Delete button
        const delBtn = document.createElement('button');
        delBtn.className = 'card-action-btn delete';
        delBtn.title = 'Delete';
        delBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
        </svg>`;
        delBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            deleteFile(file.name);
        });

        actions.appendChild(dlBtn);
        actions.appendChild(delBtn);
        meta.appendChild(size);
        meta.appendChild(actions);
        info.appendChild(name);
        info.appendChild(meta);

        card.appendChild(preview);
        card.appendChild(info);

        return card;
    }

    function getFileIcon(type) {
        const icons = {
            audio: '🎵',
            document: '📄',
            archive: '📦',
            text: '📝',
            other: '📁',
        };
        return icons[type] || '📁';
    }

    function downloadFile(filename) {
        const a = document.createElement('a');
        a.href = `/api/download/${encodeURIComponent(filename)}`;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    }

    async function deleteFile(filename) {
        if (!confirm(`Delete "${filename}"?`)) return;

        try {
            await apiJson(`/api/files/${encodeURIComponent(filename)}`, {
                method: 'DELETE',
            });
            toast(`Deleted: ${filename}`, 'info');
            loadGallery();
        } catch (err) {
            toast('Failed to delete file', 'error');
        }
    }

    // ═══ LIGHTBOX ═════════════════════════════════════
    function openLightbox(imgSrc, videoSrc) {
        if (imgSrc) {
            dom.lightboxImg.src = imgSrc;
            dom.lightboxImg.style.display = 'block';
        }
        // For video, we reuse the lightbox image element but it could be extended
        if (videoSrc) {
            dom.lightboxImg.src = videoSrc;
            dom.lightboxImg.style.display = 'block';
        }
        dom.lightbox.classList.remove('hidden');
    }

    function closeLightbox() {
        dom.lightbox.classList.add('hidden');
        dom.lightboxImg.src = '';
    }

    function initLightbox() {
        dom.lightboxClose.addEventListener('click', closeLightbox);
        dom.lightbox.addEventListener('click', (e) => {
            if (e.target === dom.lightbox) closeLightbox();
        });
    }

    // ═══ QR CODE MODAL ════════════════════════════════
    function initQrModal() {
        dom.qrBtn.addEventListener('click', async () => {
            dom.qrImg.src = '/api/qr?' + Date.now();
            dom.modalUrl.textContent = serverUrl || window.location.origin;
            dom.qrModal.classList.remove('hidden');
        });

        dom.qrClose.addEventListener('click', () => {
            dom.qrModal.classList.add('hidden');
        });

        dom.qrModal.addEventListener('click', (e) => {
            if (e.target === dom.qrModal) dom.qrModal.classList.add('hidden');
        });

        // Click URL to copy
        dom.modalUrl.addEventListener('click', async () => {
            try {
                await navigator.clipboard.writeText(dom.modalUrl.textContent);
                toast('URL copied to clipboard', 'success');
            } catch {
                toast('Could not copy URL', 'error');
            }
        });
    }

    // ═══ AUTO-CHECK AUTH ══════════════════════════════
    async function checkAuth() {
        try {
            await apiJson('/api/files');
            // Already authenticated
            showDashboard();
        } catch {
            showPinGate();
        }
    }

    // ═══ INIT ═════════════════════════════════════════
    function init() {
        initPinInput();
        initStreamControls();
        initDropZone();
        initLightbox();
        initQrModal();

        // Check if already authenticated (session cookie still valid)
        checkAuth();

        // Refresh gallery every 10 seconds
        setInterval(() => {
            if (!dom.dashboard.classList.contains('hidden')) {
                loadGallery();
            }
        }, 10000);
    }

    // Start when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
