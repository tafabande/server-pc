(function(){'use strict';
const $=s=>document.querySelector(s),$$=s=>document.querySelectorAll(s);
const dom={pinGate:$('#pin-gate'),pinInputRow:$('#pin-input-row'),pinDigits:$$('.pin-digit'),pinError:$('#pin-error'),pinSubmit:$('#pin-submit'),dashboard:$('#dashboard'),statusIp:$('#status-ip'),qrBtn:$('#qr-btn'),shutdownBtn:$('#shutdown-btn'),streamPanel:$('#stream-panel'),streamStatus:$('#stream-status'),streamPlaceholder:$('#stream-placeholder'),streamImg:$('#stream-img'),streamViewport:$('#stream-viewport'),streamFullscreenBtn:$('#stream-fullscreen-btn'),streamAudio:$('#stream-audio'),startBtn:$('#stream-start-btn'),stopBtn:$('#stream-stop-btn'),toggleBtn:$('#stream-toggle-btn'),toggleLabel:$('#toggle-label'),qualityValue:$('#quality-value'),dropZone:$('#drop-zone'),fileInput:$('#file-input'),uploadProgress:$('#upload-progress'),progressFilename:$('#progress-filename'),progressPercent:$('#progress-percent'),progressBarFill:$('#progress-bar-fill'),galleryGrid:$('#gallery-grid'),gallery:$('#gallery-grid'),emptyState:$('#empty-state'),fileCount:$('#file-count'),qrModal:$('#qr-modal'),qrImg:$('#qr-img'),qrClose:$('#qr-close'),modalUrl:$('#modal-url'),qrCopyBtn:$('#qr-copy-btn'),lightbox:$('#lightbox'),lightboxImg:$('#lightbox-img'),lightboxVideo:$('#lightbox-video'),lightboxClose:$('#lightbox-close'),toastContainer:$('#toast-container'),clipboardText:$('#clipboard-text'),clipboardCopy:$('#clipboard-copy'),clipboardClear:$('#clipboard-clear'),syncIndicator:$('#sync-indicator'),syncLabel:$('#sync-label'),wsIndicator:$('#ws-indicator'),wsDot:$('#ws-indicator .ws-dot'),wsLabel:$('#ws-label'),nowPlaying:$('#now-playing'),npFilename:$('#np-filename'),npPlay:$('#np-play'),npPlayIcon:$('#np-play-icon'),npBack:$('#np-back'),npForward:$('#np-forward'),npCurrentTime:$('#np-current-time'),npDuration:$('#np-duration'),npProgressFill:$('#np-progress-fill'),npProgressTrack:$('#np-progress-track'),npClose:$('#np-close'),hiddenAudio:$('#hidden-audio')};

let serverUrl='',currentMode='webcam',isStreaming=false,authToken='',ws=null,wsReconnectTimer=null;
let clipboardDebounce=null,isLocalClipboardUpdate=false;
let npState={url:'',filename:'',playing:false,current_time:0,duration:0};
let currentPath = '';
let showOnlyFavorites = false;
let fileList = [];

// ═══ TOAST ═══
function toast(msg,type='info',dur=3500){const icons={success:'✓',error:'✕',info:'ℹ'};const el=document.createElement('div');el.className=`toast ${type}`;el.innerHTML=`<span class="toast-icon">${icons[type]||'ℹ'}</span><span>${msg}</span>`;dom.toastContainer.appendChild(el);setTimeout(()=>{el.classList.add('exit');setTimeout(()=>el.remove(),350)},dur)}

// Initialize
async function init() {
    initPinInput();
    initStreamControls();
    initDropZone();
    initLightbox();
    initQrModal();
    initClipboard();
    initNowPlaying();
    initAdaptiveBitrate();
    initCustomVideoPlayer();
    
    setupEventListeners();
    updateTheme();
    setupFilters();
    
    await checkAuth();
    
    // Auto-refresh gallery every minute
    setInterval(() => {
        if (!dom.dashboard.classList.contains('hidden')) {
            fetchFiles();
        }
    }, 60000);
}

function setupFilters() {
    const favBtn = document.getElementById('filter-favs');
    if (favBtn) {
        favBtn.onclick = () => {
            showOnlyFavorites = !showOnlyFavorites;
            favBtn.classList.toggle('active', showOnlyFavorites);
            fetchFiles(); // Re-fetch to handle global favorites if needed
        };
    }
}

// ═══ API ═══
async function api(path,opts={}){try{const res=await fetch(path,{credentials:'include',...opts});if(res.status===401){showPinGate();throw new Error('Session expired')}if(!res.ok){const d=await res.json().catch(()=>({}));throw new Error(d.detail||`Error ${res.status}`)}return res}catch(e){if(e.message!=='Session expired')console.error(`API ${path}:`,e);throw e}}
async function apiJson(path,opts={}){return(await api(path,opts)).json()}

// ═══ PIN AUTH ═══
function showPinGate(){dom.pinGate.classList.remove('hidden');dom.dashboard.classList.add('hidden');dom.pinDigits[0]?.focus()}
function showDashboard(){dom.pinGate.classList.add('hidden');dom.dashboard.classList.remove('hidden');loadStatus();fetchFiles();connectWebSocket()}
function initPinInput(){dom.pinDigits.forEach((inp,i)=>{inp.addEventListener('input',e=>{const v=e.target.value.replace(/\D/g,'');e.target.value=v;if(v&&i<3)dom.pinDigits[i+1].focus();if(i===3&&v)submitPin()});inp.addEventListener('keydown',e=>{if(e.key==='Backspace'&&!e.target.value&&i>0){dom.pinDigits[i-1].focus();dom.pinDigits[i-1].value=''}if(e.key==='Enter')submitPin()});inp.addEventListener('focus',()=>inp.select())});dom.pinSubmit.addEventListener('click',submitPin)}
async function submitPin(){const pin=Array.from(dom.pinDigits).map(d=>d.value).join('');if(pin.length!==4){dom.pinError.textContent='Please enter all 4 digits';return}dom.pinSubmit.disabled=true;dom.pinError.textContent='';try{const data=await apiJson('/api/auth',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pin})});authToken=data.token||'';showDashboard();toast('Authenticated successfully','success')}catch(e){dom.pinError.textContent='Invalid PIN. Try again.';dom.pinInputRow.classList.add('shake');setTimeout(()=>dom.pinInputRow.classList.remove('shake'),600);dom.pinDigits.forEach(d=>d.value='');dom.pinDigits[0].focus()}finally{dom.pinSubmit.disabled=false}}

// ═══ STATUS ═══
async function loadStatus(){try{const d=await apiJson('/api/status');serverUrl=d.url;dom.statusIp.textContent=`${d.hostname} · ${d.ip}:${d.port}`;currentMode=d.stream.mode;isStreaming=d.stream.running;updateStreamUI();if(d.stream.quality)dom.qualityValue.textContent=d.stream.quality+'%'}catch(e){dom.statusIp.textContent='Disconnected'}}

dom.shutdownBtn.addEventListener('click', async () => {
    if (!confirm('Are you sure you want to stop the server? This will disconnect all users.')) return;
    try {
        await apiJson('/api/shutdown', { method: 'POST' });
        toast('Server shutting down...', 'info');
        dom.statusIp.textContent = 'Offline';
        dom.dashboard.style.opacity = '0.5';
        dom.dashboard.style.pointerEvents = 'none';
        if(ws) ws.close();
    } catch(e) {
        toast('Failed to shutdown server', 'error');
    }
});

// ═══ STREAM ═══
function updateStreamUI(){const dot=dom.streamStatus.querySelector('.stream-dot'),txt=dom.streamStatus.querySelector('span:last-child');if(isStreaming){dot.className='stream-dot live';txt.textContent='Live';dom.streamPlaceholder.classList.add('hidden');dom.streamImg.classList.remove('hidden');dom.streamImg.src='/api/stream/video?'+Date.now();if(dom.streamAudio){dom.streamAudio.src='/api/stream/audio?'+Date.now();dom.streamAudio.play().catch(e=>console.log('Audio autoplay blocked',e));}if(dom.streamFullscreenBtn)dom.streamFullscreenBtn.classList.remove('hidden');dom.startBtn.disabled=true;dom.stopBtn.disabled=false}else{dot.className='stream-dot offline';txt.textContent='Offline';dom.streamPlaceholder.classList.remove('hidden');dom.streamImg.classList.add('hidden');dom.streamImg.src='';if(dom.streamAudio){dom.streamAudio.pause();dom.streamAudio.src='';}if(dom.streamFullscreenBtn)dom.streamFullscreenBtn.classList.add('hidden');dom.startBtn.disabled=false;dom.stopBtn.disabled=true}dom.toggleLabel.textContent=currentMode==='webcam'?'Switch to Screen':'Switch to Webcam'}
function initStreamControls(){dom.startBtn.addEventListener('click',async()=>{try{dom.startBtn.disabled=true;const d=await apiJson('/api/stream/start',{method:'POST'});isStreaming=d.running;currentMode=d.mode;updateStreamUI();if(d.quality)dom.qualityValue.textContent=d.quality+'%';toast('Stream started','success')}catch(e){toast('Failed to start stream','error');dom.startBtn.disabled=false}});dom.stopBtn.addEventListener('click',async()=>{try{dom.stopBtn.disabled=true;const d=await apiJson('/api/stream/stop',{method:'POST'});isStreaming=d.running;updateStreamUI();toast('Stream stopped','info')}catch(e){toast('Failed to stop stream','error');dom.stopBtn.disabled=false}});dom.toggleBtn.addEventListener('click',async()=>{try{dom.toggleBtn.disabled=true;const d=await apiJson('/api/stream/toggle',{method:'POST'});currentMode=d.mode;isStreaming=d.running;updateStreamUI();toast(`Switched to ${currentMode}`,'info')}catch(e){toast('Failed to toggle source','error')}finally{dom.toggleBtn.disabled=false}});if(dom.streamFullscreenBtn){dom.streamFullscreenBtn.addEventListener('click',()=>{if(!document.fullscreenElement){if(dom.streamViewport)dom.streamViewport.requestFullscreen?.()||dom.streamViewport.webkitRequestFullscreen?.();}else{document.exitFullscreen?.();}});}}

// ═══ FILE UPLOAD ═══
function initDropZone(){const z=dom.dropZone;z.addEventListener('click',()=>dom.fileInput.click());dom.fileInput.addEventListener('change',e=>{if(e.target.files.length){uploadFiles(e.target.files);e.target.value=''}});['dragenter','dragover'].forEach(ev=>z.addEventListener(ev,e=>{e.preventDefault();e.stopPropagation();z.classList.add('dragover')}));['dragleave','drop'].forEach(ev=>z.addEventListener(ev,e=>{e.preventDefault();e.stopPropagation();z.classList.remove('dragover')}));z.addEventListener('drop',e=>{if(e.dataTransfer.files.length)uploadFiles(e.dataTransfer.files)})}
async function uploadFiles(fl){for(const f of Array.from(fl))await uploadSingleFile(f)}
function uploadSingleFile(file){return new Promise(resolve=>{const fd=new FormData();fd.append('file',file);const xhr=new XMLHttpRequest();dom.uploadProgress.classList.remove('hidden');dom.progressFilename.textContent=file.name;dom.progressPercent.textContent='0%';dom.progressBarFill.style.width='0%';xhr.upload.addEventListener('progress',e=>{if(e.lengthComputable){const p=Math.round(e.loaded/e.total*100);dom.progressPercent.textContent=p+'%';dom.progressBarFill.style.width=p+'%'}});xhr.addEventListener('load',()=>{dom.uploadProgress.classList.add('hidden');if(xhr.status===200){toast(`Uploaded: ${file.name}`,'success');fetchFiles()}else{let d='Upload failed';try{d=JSON.parse(xhr.responseText).detail}catch(_){}toast(d,'error')}resolve()});xhr.addEventListener('error',()=>{dom.uploadProgress.classList.add('hidden');toast('Upload failed — network error','error');resolve()});xhr.open('POST','/api/upload?path=' + encodeURIComponent(currentPath));xhr.withCredentials=true;xhr.send(fd)})}

// ═══ GALLERY ═══
async function fetchFiles() {
    try {
        let url;
        if (showOnlyFavorites) {
            url = '/api/favorites';
        } else {
            url = currentPath ? `/api/files/${encodeURIComponent(currentPath)}` : `/api/files`;
        }
        
        const data = await apiJson(url);
        fileList = data.files || [];
        renderFiles(fileList);
        updateBreadcrumb();
    } catch (error) {
        console.error("Failed to fetch files:", error);
        toast("Failed to load files", "error");
    }
}

function renderFiles(files) {
    const container = dom.gallery;
    container.innerHTML = '';
    
    if (files.length === 0) {
        dom.emptyState.classList.remove('hidden');
        dom.galleryGrid.classList.add('hidden');
        const emptyMsg = dom.emptyState.querySelector('p');
        if (emptyMsg) {
            emptyMsg.textContent = showOnlyFavorites ? 'No favorites yet' : 'No files shared yet';
        }
    } else {
        dom.emptyState.classList.add('hidden');
        dom.galleryGrid.classList.remove('hidden');
        files.forEach((file, idx) => {
            container.appendChild(createFileCard(file, idx));
        });
    }
    
    document.getElementById('file-count').textContent = `${files.length} items`;
}

function updateBreadcrumb() {
    const breadcrumb = document.getElementById('breadcrumb');
    if (!breadcrumb) return;
    
    breadcrumb.innerHTML = '';
    
    // Root link
    const rootBtn = document.createElement('button');
    rootBtn.className = `btn-text ${currentPath === '' ? 'active' : ''}`;
    rootBtn.textContent = 'Root';
    rootBtn.onclick = () => navigatePath('');
    breadcrumb.appendChild(rootBtn);
    
    if (showOnlyFavorites) {
        breadcrumb.appendChild(document.createTextNode(' / '));
        const favLabel = document.createElement('span');
        favLabel.className = 'btn-text active';
        favLabel.textContent = 'Favorites';
        breadcrumb.appendChild(favLabel);
    } else if (currentPath) {
        const parts = currentPath.split('/');
        let pathAccumulator = '';
        
        parts.forEach((part, index) => {
            breadcrumb.appendChild(document.createTextNode(' / '));
            pathAccumulator += (index === 0 ? '' : '/') + part;
            
            const partBtn = document.createElement('button');
            partBtn.className = `btn-text ${index === parts.length - 1 ? 'active' : ''}`;
            partBtn.textContent = part;
            const targetPath = pathAccumulator;
            partBtn.onclick = () => navigatePath(targetPath);
            breadcrumb.appendChild(partBtn);
        });
    }
}

function navigatePath(path) {
    currentPath = path;
    showOnlyFavorites = false;
    const favBtn = document.getElementById('filter-favs');
    if (favBtn) favBtn.classList.remove('active');
    fetchFiles();
}

async function toggleFavorite(filename, event) {
    event.stopPropagation();
    try {
        const data = await apiJson('/api/favorites/toggle', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename })
        });
        if (data.status === 'ok') {
            // Update local state and re-render
            const file = fileList.find(f => f.filename === filename);
            if (file) {
                file.is_favorite = data.favorite;
                renderFiles(fileList);
            }
        }
    } catch (error) {
        console.error("Favorite toggle failed:", error);
    }
}
// Deleted redundant loadGallery and renderGallery (replaced by fetchFiles and renderFiles)
function createFileCard(file, idx) {
    const card = document.createElement('div');
    card.className = `file-card ${file.is_dir ? 'dir-card' : ''}`;
    card.style.animationDelay = `${idx * 0.05}s`;
    
    const prev = document.createElement('div');
    prev.className = 'file-card-preview';
    
    if (file.is_dir) {
        const ic = document.createElement('div');
        ic.className = 'file-icon folder-icon';
        ic.textContent = '📁';
        prev.appendChild(ic);
        card.addEventListener('click', () => navigatePath(file.filename));
    } else if (file.type === 'image') {
        const img = document.createElement('img');
        // Add timestamp to bust browser cache for thumbnails
        const thumbUrl = file.thumbnail_url || file.serve_url;
        img.src = thumbUrl + (thumbUrl.includes('?') ? '&' : '?') + 't=' + Date.now();
        img.alt = file.name;
        img.loading = 'lazy';
        prev.appendChild(img);
        prev.addEventListener('click', (e) => { e.stopPropagation(); openLightbox(file.serve_url, null); });
    } else if (file.playable) {
        if (file.type === 'video') {
            const img = document.createElement('img');
            const thumbUrl = file.thumbnail_url || file.serve_url;
            img.src = thumbUrl + (thumbUrl.includes('?') ? '&' : '?') + 't=' + Date.now();
            img.alt = file.name;
            img.loading = 'lazy';
            prev.appendChild(img);
            
            const overlay = document.createElement('div');
            overlay.className = 'play-overlay';
            overlay.innerHTML = '<svg width="48" height="48" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>';
            prev.appendChild(overlay);
            
            prev.addEventListener('click', (e) => { e.stopPropagation(); openLightbox(null, file.stream_url || file.serve_url, file.name, file.type); });
        } else if (file.type === 'audio') {
            const ic = document.createElement('div');
            ic.className = 'file-icon';
            ic.textContent = '🎵';
            prev.appendChild(ic);
            prev.addEventListener('click', (e) => { e.stopPropagation(); playMedia(file.stream_url || file.serve_url, file.name, 'audio'); });
        }
    } else {
        const ic = document.createElement('div');
        ic.className = 'file-icon';
        ic.textContent = getFileIcon(file.type);
        prev.appendChild(ic);
    }

    const info = document.createElement('div');
    info.className = 'file-card-info';
    const nm = document.createElement('div');
    nm.className = 'file-card-name';
    nm.textContent = file.name;
    nm.title = file.name;
    
    const meta = document.createElement('div');
    meta.className = 'file-card-meta';
    const sz = document.createElement('span');
    sz.textContent = file.is_dir ? 'Folder' : file.size_formatted;
    
    const acts = document.createElement('div');
    acts.className = 'file-card-actions';
    
    // Favorite Button
    const favBtn = document.createElement('button');
    favBtn.className = `card-action-btn fav-btn ${file.is_favorite ? 'active' : ''}`;
    favBtn.title = file.is_favorite ? 'Unfavorite' : 'Favorite';
    favBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="${file.is_favorite ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l8.84-8.84 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>`;
    favBtn.addEventListener('click', e => toggleFavorite(file.filename, e));
    
    const dlBtn = document.createElement('button');
    dlBtn.className = 'card-action-btn';
    dlBtn.title = 'Download';
    dlBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>';
    dlBtn.addEventListener('click', e => { e.stopPropagation(); downloadFile(file.filename); });
    
    const delBtn = document.createElement('button');
    delBtn.className = 'card-action-btn delete';
    delBtn.title = 'Delete';
    delBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>';
    delBtn.addEventListener('click', e => { e.stopPropagation(); deleteFile(file.filename); });
    
    acts.appendChild(favBtn);
    if (!file.is_dir) acts.appendChild(dlBtn);
    acts.appendChild(delBtn);
    
    meta.appendChild(sz);
    meta.appendChild(acts);
    info.appendChild(nm);
    info.appendChild(meta);
    card.appendChild(prev);
    card.appendChild(info);
    
    return card;
}
function getFileIcon(t){return{audio:'🎵',document:'📄',archive:'📦',text:'📝',other:'📁'}[t]||'📁'}
function downloadFile(fn){const a=document.createElement('a');a.href=`/api/download/${encodeURIComponent(fn)}`;a.download=fn;document.body.appendChild(a);a.click();document.body.removeChild(a)}
async function deleteFile(fn){if(!confirm(`Delete "${fn}"?`))return;try{await apiJson(`/api/files/${encodeURIComponent(fn)}`,{method:'DELETE'});toast(`Deleted: ${fn}`,'info');fetchFiles()}catch(e){toast('Failed to delete file','error')}}

// ═══ LIGHTBOX ═══
function openLightbox(imgSrc, videoSrc, filename, type) {
    dom.lightboxImg.classList.add('hidden');
    dom.lightboxVideo.classList.add('hidden');
    const container = document.getElementById('video-player-container');
    if (container) container.classList.add('hidden');

    if (videoSrc) {
        if (type === 'audio') {
            playMedia(videoSrc, filename, 'audio');
        } else {
            dom.lightboxVideo.src = videoSrc;
            dom.lightboxVideo.classList.remove('hidden');
            if (container) {
                container.classList.remove('hidden');
                document.getElementById('player-title').textContent = filename;
            }
            dom.lightbox.classList.remove('hidden');
            dom.lightboxVideo.play().catch(e => {
                if (e.name !== 'AbortError') console.error("Playback error:", e);
            });
            // Sync with Hub
            npState = {url: videoSrc, filename: filename, playing: true, current_time: 0, duration: 0};
            wsSend({type:'remote_control',action:'set',url:videoSrc,filename:filename,duration:0});
        }
    } else if (imgSrc) {
        dom.lightboxImg.src = imgSrc;
        dom.lightboxImg.classList.remove('hidden');
        dom.lightbox.classList.remove('hidden');
    }
}
function closeLightbox() {
    dom.lightbox.classList.add('hidden');
    
    // Stop sync and hide Now Playing if we were watching a video
    if (dom.lightboxVideo.src) {
        dom.lightboxVideo.pause();
        wsSend({type:'remote_control',action:'stop'});
        hideNowPlaying();
    }
    
    dom.lightboxVideo.src = '';
    dom.lightboxImg.src = '';
    
    if (document.fullscreenElement) {
        document.exitFullscreen().catch(e => {});
    }
}
function initLightbox() {
    dom.lightboxClose.addEventListener('click', closeLightbox);
    dom.lightbox.addEventListener('click', e => {
        if (e.target === dom.lightbox) closeLightbox();
    });
}

// ═══ QR MODAL ═══
function initQrModal(){dom.qrBtn.addEventListener('click',async()=>{dom.qrImg.src='/api/qr?'+Date.now();dom.modalUrl.textContent=serverUrl||window.location.origin;dom.qrModal.classList.remove('hidden')});dom.qrClose.addEventListener('click',()=>dom.qrModal.classList.add('hidden'));dom.qrModal.addEventListener('click',e=>{if(e.target===dom.qrModal)dom.qrModal.classList.add('hidden')});const copyFn=async()=>{try{await navigator.clipboard.writeText(dom.modalUrl.textContent);toast('URL copied','success')}catch(e){toast('Could not copy','error')}};dom.modalUrl.addEventListener('click',copyFn);if(dom.qrCopyBtn)dom.qrCopyBtn.addEventListener('click',copyFn);}

// ═══ WEBSOCKET ═══
function connectWebSocket(){if(ws&&ws.readyState<2)return;const proto=location.protocol==='https:'?'wss':'ws';const url=`${proto}://${location.host}/ws?token=${encodeURIComponent(authToken)}`;ws=new WebSocket(url);
ws.onopen=()=>{const dot=dom.wsIndicator?.querySelector('.ws-dot');if(dot){dot.className='ws-dot connected'}if(wsReconnectTimer){clearTimeout(wsReconnectTimer);wsReconnectTimer=null}};
ws.onclose=()=>{const dot=dom.wsIndicator?.querySelector('.ws-dot');if(dot){dot.className='ws-dot disconnected'}if(dom.wsLabel)dom.wsLabel.textContent='0 devices';wsReconnectTimer=setTimeout(connectWebSocket,3000)};
ws.onerror=()=>{};
ws.onmessage=e=>{try{const msg=JSON.parse(e.data);handleWsMessage(msg)}catch(err){}}}
function wsSend(msg){if(ws&&ws.readyState===1)ws.send(JSON.stringify(msg))}
function handleWsMessage(msg){switch(msg.type){case'clipboard':if(!isLocalClipboardUpdate&&dom.clipboardText){dom.clipboardText.value=msg.text;showSyncFlash()}break;case'file_event':fetchFiles();if(msg.action==='uploaded'&&msg.file)toast(`New file: ${msg.file.name}`,'info');break;case'remote_control':handleRemoteState(msg);break;case'bitrate':if(dom.qualityValue)dom.qualityValue.textContent=msg.quality+'%';break;case'connections':if(dom.wsLabel)dom.wsLabel.textContent=msg.count+' device'+(msg.count!==1?'s':'');break;case'pong':break}}

// ═══ CLIPBOARD SYNC ═══
function initClipboard(){if(!dom.clipboardText)return;dom.clipboardText.addEventListener('input',()=>{isLocalClipboardUpdate=true;clearTimeout(clipboardDebounce);dom.syncIndicator?.classList.add('syncing');if(dom.syncLabel)dom.syncLabel.textContent='Syncing...';clipboardDebounce=setTimeout(()=>{wsSend({type:'clipboard',text:dom.clipboardText.value});dom.syncIndicator?.classList.remove('syncing');if(dom.syncLabel)dom.syncLabel.textContent='Synced';isLocalClipboardUpdate=false},300)});
dom.clipboardCopy?.addEventListener('click',async()=>{try{await navigator.clipboard.writeText(dom.clipboardText.value);toast('Copied to clipboard','success')}catch(e){toast('Copy failed','error')}});
dom.clipboardClear?.addEventListener('click',()=>{dom.clipboardText.value='';wsSend({type:'clipboard',text:''});toast('Clipboard cleared','info')})}
function showSyncFlash(){dom.syncIndicator?.classList.add('syncing');if(dom.syncLabel)dom.syncLabel.textContent='Received';setTimeout(()=>{dom.syncIndicator?.classList.remove('syncing');if(dom.syncLabel)dom.syncLabel.textContent='Synced'},800)}

// ═══ NOW PLAYING / REMOTE CONTROL ═══
function playMedia(url,filename,mediaType){npState={url,filename,playing:true,current_time:0,duration:0};wsSend({type:'remote_control',action:'set',url,filename,duration:0});showNowPlaying();if(mediaType==='audio'){dom.hiddenAudio.src=url;dom.hiddenAudio.play()}}
function showNowPlaying(){dom.nowPlaying.classList.remove('hidden');dom.dashboard.classList.add('has-now-playing');dom.npFilename.textContent=npState.filename||'Unknown';updateNpPlayIcon()}
function hideNowPlaying(){dom.nowPlaying.classList.add('hidden');dom.dashboard.classList.remove('has-now-playing');dom.hiddenAudio.pause();dom.hiddenAudio.src='';npState={url:'',filename:'',playing:false,current_time:0,duration:0}}
function updateNpPlayIcon(){const playing=npState.playing;dom.npPlayIcon.innerHTML=playing?'<rect x="6" y="4" width="4" height="16"/><rect x="14" y="4" width="4" height="16"/>':'<polygon points="5 3 19 12 5 21 5 3"/>'}
function handleRemoteState(msg){npState.url=msg.url||npState.url;npState.filename=msg.filename||npState.filename;npState.playing=msg.playing!==undefined?msg.playing:npState.playing;npState.current_time=msg.current_time||0;npState.duration=msg.duration||npState.duration;if(!npState.url){hideNowPlaying();return}showNowPlaying();updateNpProgress();
if(msg.action==='play'){dom.hiddenAudio.play?.();dom.lightboxVideo&&!dom.lightboxVideo.paused||dom.lightboxVideo.play?.()}else if(msg.action==='pause'){dom.hiddenAudio.pause?.();dom.lightboxVideo?.pause?.()}else if(msg.action==='seek'){if(dom.hiddenAudio.src)dom.hiddenAudio.currentTime=npState.current_time;if(dom.lightboxVideo.src)dom.lightboxVideo.currentTime=npState.current_time}}
function updateNpProgress(){const pct=npState.duration>0?(npState.current_time/npState.duration*100):0;dom.npProgressFill.style.width=pct+'%';dom.npCurrentTime.textContent=formatTime(npState.current_time);dom.npDuration.textContent=formatTime(npState.duration)}
function formatTime(s){if(!s||isNaN(s))return'0:00';const m=Math.floor(s/60),sec=Math.floor(s%60);return m+':'+(sec<10?'0':'')+sec}
function initNowPlaying(){dom.npPlay?.addEventListener('click',()=>{npState.playing=!npState.playing;wsSend({type:'remote_control',action:npState.playing?'play':'pause'});updateNpPlayIcon();if(npState.playing){dom.hiddenAudio.play?.()}else{dom.hiddenAudio.pause?.()}});
dom.npBack?.addEventListener('click',()=>{npState.current_time=Math.max(0,npState.current_time-10);wsSend({type:'remote_control',action:'seek',time:npState.current_time});if(dom.hiddenAudio.src)dom.hiddenAudio.currentTime=npState.current_time;updateNpProgress()});
dom.npForward?.addEventListener('click',()=>{npState.current_time=Math.min(npState.duration,npState.current_time+10);wsSend({type:'remote_control',action:'seek',time:npState.current_time});if(dom.hiddenAudio.src)dom.hiddenAudio.currentTime=npState.current_time;updateNpProgress()});
dom.npProgressTrack?.addEventListener('click',e=>{const rect=dom.npProgressTrack.getBoundingClientRect();const pct=(e.clientX-rect.left)/rect.width;npState.current_time=pct*npState.duration;wsSend({type:'remote_control',action:'seek',time:npState.current_time});if(dom.hiddenAudio.src)dom.hiddenAudio.currentTime=npState.current_time;updateNpProgress()});
dom.npClose?.addEventListener('click',()=>{wsSend({type:'remote_control',action:'stop'});hideNowPlaying()});
// Audio time updates
dom.hiddenAudio?.addEventListener('timeupdate',()=>{npState.current_time=dom.hiddenAudio.currentTime;npState.duration=dom.hiddenAudio.duration||0;updateNpProgress();wsSend({type:'remote_control',action:'timeupdate',time:npState.current_time,duration:npState.duration})});
dom.hiddenAudio?.addEventListener('ended',()=>{npState.playing=false;updateNpPlayIcon()})}

// ═══ ADAPTIVE BITRATE ═══
let lastFrameTime=0,slowFrameCount=0,fastFrameCount=0,currentQuality=75;
function initAdaptiveBitrate(){if(!dom.streamImg)return;dom.streamImg.addEventListener('load',()=>{const now=performance.now();if(lastFrameTime>0){const delta=now-lastFrameTime;if(delta>250){slowFrameCount++;fastFrameCount=0;if(slowFrameCount>5&&currentQuality>25){currentQuality=Math.max(25,currentQuality-10);wsSend({type:'bitrate',quality:currentQuality});slowFrameCount=0}}else if(delta<100){fastFrameCount++;slowFrameCount=0;if(fastFrameCount>20&&currentQuality<90){currentQuality=Math.min(90,currentQuality+5);wsSend({type:'bitrate',quality:currentQuality});fastFrameCount=0}}else{slowFrameCount=Math.max(0,slowFrameCount-1);fastFrameCount=Math.max(0,fastFrameCount-1)}}lastFrameTime=now})}

// ═══ AUTH CHECK ═══
async function checkAuth(){try{const d=await apiJson('/api/status');authToken=document.cookie.split('streamdrop_session=')[1]?.split(';')[0]||'';showDashboard()}catch(e){showPinGate()}}

// ═══ CUSTOM VIDEO PLAYER ═══
function initCustomVideoPlayer() {
    const vid = dom.lightboxVideo;
    const container = document.getElementById('video-player-container');
    if(!container) return;
    
    const overlay = document.getElementById('player-overlay');
    const spinner = document.getElementById('player-spinner');
    const centerAction = document.getElementById('player-center-action');
    const centerPlayIcon = document.getElementById('center-play-icon');
    const centerPauseIcon = document.getElementById('center-pause-icon');
    const btnPlay = document.getElementById('player-play');
    const btnPlayIcon = document.getElementById('btn-play-icon');
    const btnPauseIcon = document.getElementById('btn-pause-icon');
    const btnRewind = document.getElementById('player-rewind');
    const btnForward = document.getElementById('player-forward');
    const timeCurrent = document.getElementById('player-time-current');
    const timeTotal = document.getElementById('player-time-total');
    const muteBtn = document.getElementById('player-mute');
    const iconVolUp = document.getElementById('icon-vol-up');
    const iconVolMute = document.getElementById('icon-vol-mute');
    const volSlider = document.getElementById('player-volume');
    const fullscreenBtn = document.getElementById('player-fullscreen');
    const iconFs = document.getElementById('icon-fullscreen');
    const iconFsExit = document.getElementById('icon-fullscreen-exit');
    const progressWrap = document.getElementById('player-progress-wrap');
    const progressFill = document.getElementById('player-progress-fill');
    const progressBuffered = document.getElementById('player-progress-buffered');
    const progressThumb = document.querySelector('.player-progress-thumb');

    let inactivityTimer = null;
    let isScrubbing = false;

    const bottomControls = overlay.querySelector('.player-bottom-controls');
    let isHoveringControls = false;

    if (bottomControls) {
        bottomControls.addEventListener('mouseenter', () => {
            isHoveringControls = true;
            showOverlay();
        });
        bottomControls.addEventListener('mouseleave', () => {
            isHoveringControls = false;
            showOverlay();
        });
    }

    function showOverlay() {
        overlay.classList.remove('idle');
        clearTimeout(inactivityTimer);
        if (!vid.paused && !isHoveringControls) {
            inactivityTimer = setTimeout(() => {
                if (!isHoveringControls && !vid.paused) overlay.classList.add('idle');
            }, 3000);
        }
    }

    container.addEventListener('mousemove', showOverlay);
    container.addEventListener('touchstart', showOverlay, {passive: true});
    container.addEventListener('mouseleave', () => {
        if (!vid.paused) overlay.classList.add('idle');
    });

    function togglePlay() {
        if(vid.paused) vid.play(); else vid.pause();
    }
    
    centerAction.addEventListener('click', togglePlay);
    btnPlay.addEventListener('click', togglePlay);
    vid.addEventListener('click', togglePlay);

    btnRewind.addEventListener('click', (e) => { e.stopPropagation(); vid.currentTime = Math.max(0, vid.currentTime - 10); });
    btnForward.addEventListener('click', (e) => { e.stopPropagation(); vid.currentTime = Math.min(vid.duration, vid.currentTime + 10); });

    muteBtn.addEventListener('click', () => {
        vid.muted = !vid.muted;
        iconVolUp.classList.toggle('hidden', vid.muted);
        iconVolMute.classList.toggle('hidden', !vid.muted);
        volSlider.value = vid.muted ? 0 : vid.volume;
    });

    volSlider.addEventListener('input', (e) => {
        vid.volume = e.target.value;
        vid.muted = vid.volume === 0;
        iconVolUp.classList.toggle('hidden', vid.muted);
        iconVolMute.classList.toggle('hidden', !vid.muted);
    });

    fullscreenBtn.addEventListener('click', () => {
        if (!document.fullscreenElement) {
            container.requestFullscreen?.() || container.webkitRequestFullscreen?.();
        } else {
            document.exitFullscreen?.();
        }
    });

    document.addEventListener('fullscreenchange', () => {
        const isFs = !!document.fullscreenElement;
        container.classList.toggle('fullscreen', isFs);
        iconFs.classList.toggle('hidden', isFs);
        iconFsExit.classList.toggle('hidden', !isFs);
    });

    vid.addEventListener('play', () => {
        centerPlayIcon.classList.add('hidden'); centerPauseIcon.classList.remove('hidden');
        btnPlayIcon.classList.add('hidden'); btnPauseIcon.classList.remove('hidden');
        centerAction.classList.remove('hidden');
        setTimeout(() => centerAction.classList.add('hidden'), 500);
        showOverlay();
        npState.playing = true;
        wsSend({type:'remote_control',action:'play'});
    });

    vid.addEventListener('pause', () => {
        centerPlayIcon.classList.remove('hidden'); centerPauseIcon.classList.add('hidden');
        btnPlayIcon.classList.remove('hidden'); btnPauseIcon.classList.add('hidden');
        centerAction.classList.remove('hidden');
        showOverlay();
        npState.playing = false;
        wsSend({type:'remote_control',action:'pause'});
    });

    vid.addEventListener('waiting', () => spinner.classList.remove('hidden'));
    vid.addEventListener('playing', () => spinner.classList.add('hidden'));

    vid.addEventListener('timeupdate', () => {
        if(!isScrubbing && vid.duration) {
            const pct = (vid.currentTime / vid.duration) * 100;
            progressFill.style.width = pct + '%';
            progressThumb.style.left = pct + '%';
        }
        timeCurrent.textContent = formatTime(vid.currentTime);
        
        // Sync progress
        npState.current_time = vid.currentTime;
        npState.duration = vid.duration || 0;
        updateNpProgress();
        wsSend({type:'remote_control',action:'timeupdate',time:vid.currentTime,duration:vid.duration});
    });

    vid.addEventListener('loadedmetadata', () => {
        timeTotal.textContent = formatTime(vid.duration);
    });

    vid.addEventListener('progress', () => {
        if (vid.duration > 0 && vid.buffered.length > 0) {
            const bufferedEnd = vid.buffered.end(vid.buffered.length - 1);
            progressBuffered.style.width = ((bufferedEnd / vid.duration) * 100) + '%';
        }
    });

    function scrub(e) {
        const rect = progressWrap.getBoundingClientRect();
        let pct = (e.clientX - rect.left) / rect.width;
        pct = Math.max(0, Math.min(1, pct));
        progressFill.style.width = (pct * 100) + '%';
        progressThumb.style.left = (pct * 100) + '%';
        vid.currentTime = pct * vid.duration;
    }

    progressWrap.addEventListener('mousedown', (e) => {
        isScrubbing = true;
        progressWrap.classList.add('scrubbing');
        scrub(e);
        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
    });

    progressWrap.addEventListener('touchstart', (e) => {
        isScrubbing = true;
        progressWrap.classList.add('scrubbing');
        scrub(e.touches[0]);
        document.addEventListener('touchmove', onTouchMove, {passive: false});
        document.addEventListener('touchend', onTouchEnd);
    }, {passive: true});

    function onMouseMove(e) { if(isScrubbing) scrub(e); }
    function onMouseUp() { 
        isScrubbing = false; 
        progressWrap.classList.remove('scrubbing');
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);
    }
    function onTouchMove(e) { if(isScrubbing) scrub(e.touches[0]); e.preventDefault(); }
    function onTouchEnd() {
        isScrubbing = false;
        progressWrap.classList.remove('scrubbing');
        document.removeEventListener('touchmove', onTouchMove);
        document.removeEventListener('touchend', onTouchEnd);
    }

    document.addEventListener('keydown', (e) => {
        if(dom.lightbox.classList.contains('hidden') || !container || container.classList.contains('hidden')) return;
        if(e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

        switch(e.code) {
            case 'Space': e.preventDefault(); togglePlay(); break;
            case 'ArrowLeft': e.preventDefault(); vid.currentTime = Math.max(0, vid.currentTime - 10); showOverlay(); break;
            case 'ArrowRight': e.preventDefault(); vid.currentTime = Math.min(vid.duration, vid.currentTime + 10); showOverlay(); break;
            case 'ArrowUp': e.preventDefault(); vid.volume = Math.min(1, vid.volume + 0.1); volSlider.value = vid.volume; showOverlay(); break;
            case 'ArrowDown': e.preventDefault(); vid.volume = Math.max(0, vid.volume - 0.1); volSlider.value = vid.volume; showOverlay(); break;
            case 'KeyF': e.preventDefault(); fullscreenBtn.click(); break;
            case 'KeyM': e.preventDefault(); muteBtn.click(); break;
            case 'Escape': e.preventDefault(); closeLightbox(); break;
        }
    });
}

// ═══ INIT ═══
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init()})();
