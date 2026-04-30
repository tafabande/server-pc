// Offline SVG Icon fallback system for StreamDrop
// Automatically replaces Google Material Symbols with lightweight SVG paths

const ICON_MAP = {
  'play_arrow': 'M8 5v14l11-7z',
  'close': 'M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z',
  'search': 'M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z',
  'qr_code_2': 'M3 3v8h8V3H3zm6 6H5V5h4v4zm-6 4v8h8v-8H3zm6 6H5v-4h4v4zm4-16v8h8V3h-8zm6 6h-4V5h4v4zm-6 4h8v8h-8z',
  'download_for_offline': 'M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z',
  'screen_share': 'M20 18c1.1 0 1.99-.9 1.99-2L22 6c0-1.1-.9-2-2-2H4c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2H0v2h24v-2h-4zm-7-3.53v-2.19c-2.78 0-4.61.85-6 2.72.56-2.67 2.11-5.33 6-5.87V7l4 3.73-4 3.74z',
  'power_settings_new': 'M13 3h-2v10h2V3zm4.83 2.17l-1.42 1.42C17.99 7.86 19 9.81 19 12c0 3.87-3.13 7-7 7s-7-3.13-7-7c0-2.19 1.01-4.14 2.58-5.42L6.17 5.17C4.23 6.82 3 9.26 3 12c0 4.97 4.03 9 9 9s9-4.03 9-9c0-2.74-1.23-5.18-3.17-6.83z',
  'grid_view': 'M3 3v8h8V3H3zm6 6H5V5h4v4zm-6 4v8h8v-8H3zm6 6H5v-4h4v4zm4-16v8h8V3h-8zm6 6h-4V5h4v4zm-6 4v8h8v-8h-8zm6 6h-4v-4h4v4z',
  'star': 'M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z',
  'settings': 'M19.14,12.94c0.04-0.3,0.06-0.61,0.06-0.94c0-0.32-0.02-0.64-0.06-0.94l2.03-1.58c0.18-0.14,0.23-0.41,0.12-0.61 l-1.92-3.32c-0.12-0.22-0.37-0.29-0.59-0.22l-2.39,0.96c-0.5-0.38-1.03-0.7-1.62-0.94L14.4,2.81c-0.04-0.24-0.24-0.41-0.48-0.41 h-3.84c-0.24,0-0.43,0.17-0.47,0.41L9.25,5.35C8.66,5.59,8.12,5.92,7.63,6.29L5.24,5.33c-0.22-0.08-0.47,0-0.59,0.22L2.73,8.87 C2.62,9.08,2.66,9.34,2.86,9.48l2.03,1.58C4.84,11.36,4.8,11.69,4.8,12s0.02,0.64,0.06,0.94l-2.03,1.58 c-0.18,0.14-0.23,0.41-0.12,0.61l1.92,3.32c0.12,0.22,0.37,0.29,0.59,0.22l2.39-0.96c0.5,0.38,1.03,0.7,1.62,0.94l0.36,2.54 c0.05,0.24,0.24,0.41,0.48,0.41h3.84c0.24,0,0.43-0.17,0.47-0.41l0.36-2.54c0.59-0.24,1.13-0.56,1.62-0.94l2.39,0.96 c0.22,0.08,0.47,0,0.59-0.22l1.92-3.32c0.12-0.22,0.07-0.49-0.12-0.61L19.14,12.94z M12,15.6c-1.98,0-3.6-1.62-3.6-3.6 s1.62-3.6,3.6-3.6s3.6,1.62,3.6,3.6S13.98,15.6,12,15.6z',
  'folder_open': 'M20 6h-8l-2-2H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2zm0 12H4V8h16v10z',
  'add': 'M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z',
  'keyboard_arrow_down': 'M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6 1.41-1.41z',
  'favorite_border': 'M16.5 3c-1.74 0-3.41.81-4.5 2.09C10.91 3.81 9.24 3 7.5 3 4.42 3 2 5.42 2 8.5c0 3.78 3.4 6.86 8.55 11.54L12 21.35l1.45-1.32C18.6 15.36 22 12.28 22 8.5 22 5.42 19.58 3 16.5 3zm-4.4 15.55l-.1.1-.1-.1C7.14 14.24 4 11.39 4 8.5 4 6.5 5.5 5 7.5 5c1.54 0 3.04.99 3.57 2.36h1.87C13.46 5.99 14.96 5 16.5 5c2 0 3.5 1.5 3.5 3.5 0 2.89-3.14 5.74-7.9 10.05z',
  'picture_in_picture_alt': 'M19 11h-8v6h8v-6zm4 8V4.98C23 3.88 22.1 3 21 3H3c-1.1 0-2 .88-2 1.98V19c0 1.1.9 2 2 2h18c1.1 0 2-.9 2-2zm-2 .02H3V4.97h18v14.05z',
  'download': 'M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z',
  'replay_10': 'M11.99 5V1l-5 5 5 5V7c3.31 0 6 2.69 6 6s-2.69 6-6 6-6-2.69-6-6h-2c0 4.42 3.58 8 8 8s8-3.58 8-8-3.58-8-8-8zm-1.1 11h-.85v-3.26l-1.01.31v-.69l1.77-.63h.09V16zm4.28-1.76c0 .32-.03.6-.1.82-.07.23-.17.42-.29.57-.12.15-.27.26-.45.33-.18.07-.39.11-.63.11-.25 0-.46-.04-.64-.11-.18-.07-.33-.18-.45-.33-.12-.15-.22-.34-.29-.57-.07-.22-.1-.5-.1-.82v-1.4c0-.32.03-.6.1-.82.07-.23.17-.42.29-.57.12-.15.27-.26.45-.33.18-.07.39-.11.64-.11.24 0 .45.04.63.11.18.07.33.18.45.33.12.15.22.34.29.57.07.22.1.5.1.82v1.4zm-.85-1.48c0-.23-.02-.42-.06-.57-.04-.15-.1-.26-.17-.33-.08-.07-.18-.11-.3-.11-.13 0-.23.04-.31.11-.08.07-.14.18-.18.33-.04.15-.06.34-.06.57v1.54c0 .23.02.42.06.57.04.15.1.26.18.33.08.07.18.11.31.11.12 0 .22-.04.3-.11.07-.07.13-.18.17-.33.04-.15.06-.34.06-.57v-1.54z',
  'forward_10': 'M18 13c0 3.31-2.69 6-6 6s-6-2.69-6-6 2.69-6 6-6v4l5-5-5-5v4c-4.42 0-8 3.58-8 8s3.58 8 8 8 8-3.58 8-8h-2zm-6.1-1.76c0 .32-.03.6-.1.82-.07.23-.17.42-.29.57-.12.15-.27.26-.45.33-.18.07-.39.11-.63.11-.25 0-.46-.04-.64-.11-.18-.07-.33-.18-.45-.33-.12-.15-.22-.34-.29-.57-.07-.22-.1-.5-.1-.82v-1.4c0-.32.03-.6.1-.82.07-.23.17-.42.29-.57.12-.15.27-.26.45-.33.18-.07.39-.11.64-.11.24 0 .45.04.63.11.18.07.33.18.45.33.12.15.22.34.29.57.07.22.1.5.1.82v1.4zm-.85-1.48c0-.23-.02-.42-.06-.57-.04-.15-.1-.26-.17-.33-.08-.07-.18-.11-.3-.11-.13 0-.23.04-.31.11-.08.07-.14.18-.18.33-.04.15-.06.34-.06.57v1.54c0 .23.02.42.06.57.04.15.1.26.18.33.08.07.18.11.31.11.12 0 .22-.04.3-.11.07-.07.13-.18.17-.33.04-.15.06-.34.06-.57v-1.54zm3.95 4.24h-.85v-3.26l-1.01.31v-.69l1.77-.63h.09v4.27z',
  'skip_previous': 'M6 6h2v12H6zm3.5 6l8.5 6V6z',
  'skip_next': 'M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z',
  'fullscreen': 'M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z',
  'arrow_back': 'M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z',
  'edit': 'M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z',
  'closed_caption': 'M19 4H5c-1.11 0-2 .9-2 2v12c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm-8 7H9.5v-.5h-2v3h2V13H11v1c0 .55-.45 1-1 1H7c-.55 0-1-.45-1-1v-4c0-.55.45-1 1-1h3c.55 0 1 .45 1 1v1zm7 0h-1.5v-.5h-2v3h2V13H18v1c0 .55-.45 1-1 1h-3c-.55 0-1-.45-1-1v-4c0-.55.45-1 1-1h3c.55 0 1 .45 1 1v1z',
  'delete': 'M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z',
  'sensors': 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 14.5c-2.49 0-4.5-2.01-4.5-4.5S9.51 7.5 12 7.5s4.5 2.01 4.5 4.5-2.01 4.5-4.5 4.5zm0-7.5c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z',
  'description': 'M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z',
  'image': 'M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z',
  'movie': 'M18 4l2 4h-3l-2-4h-2l2 4h-3l-2-4H8l2 4H7L5 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V4h-4z',
  'audio_file': 'M20 2H8c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-2 5h-3v5.5c0 1.38-1.12 2.5-2.5 2.5S10 13.88 10 12.5s1.12-2.5 2.5-2.5c.57 0 1.08.19 1.5.51V5h4v2zM4 6H2v14c0 1.1.9 2 2 2h14v-2H4V6z',
  'favorite': 'M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z',
  'more_vert': 'M12 8c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm0 2c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm0 6c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2z',
  'folder': 'M10 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z',
  'text_snippet': 'M14 2H6c-1.1 0-2 .9-2 2v16c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V8l-6-6zm0 2l4 4h-4V4z',
  'pause': 'M6 19h4V5H6v14zm8-14v14h4V5h-4z',
  'water_drop': 'M12 2c-5.33 4.55-8 8.1-8 10.82 0 4.5 3.58 8.18 8 8.18s8-3.68 8-8.18C20 10.1 17.33 6.55 12 2z M12 19c-3.31 0-6-2.63-6-5.85 0-2.04 2-4.69 6-8.22 4 3.53 6 6.18 6 8.22 0 3.22-2.69 5.85-6 5.85z',
  'fast_forward': 'M4 18l8.5-6L4 6v12zm9-12v12l8.5-6L13 6z'
};

function processIconNode(node) {
    if (node.hasAttribute('data-icon-replaced')) return;
    
    // Some icons might have extra whitespace
    const iconName = node.innerText.trim();
    
    if (ICON_MAP[iconName]) {
        // Clear text to prevent "play_arrow" from showing while SVG loads
        node.innerHTML = `<svg viewBox="0 0 24 24" width="1em" height="1em" fill="currentColor"><path d="${ICON_MAP[iconName]}"/></svg>`;
        node.setAttribute('data-icon-replaced', 'true');
        node.style.display = 'inline-flex';
        node.style.alignItems = 'center';
        node.style.justifyContent = 'center';
    }
}

function scanDOM() {
    document.querySelectorAll('.material-symbols-rounded').forEach(processIconNode);
}

// Watch for DOM changes (both newly added elements and innerText updates)
const observer = new MutationObserver(mutations => {
    let shouldScan = false;
    
    mutations.forEach(m => {
        if (m.type === 'childList') {
            m.addedNodes.forEach(node => {
                if (node.nodeType === 1) { // Element node
                    if (node.classList && node.classList.contains('material-symbols-rounded')) {
                        processIconNode(node);
                    }
                    // Find nested icons in the added tree
                    const nested = node.querySelectorAll('.material-symbols-rounded');
                    if (nested.length > 0) {
                        nested.forEach(processIconNode);
                    }
                } else if (node.nodeType === 3) { // Text node added (e.g. innerText changed)
                    if (m.target.nodeType === 1 && m.target.classList.contains('material-symbols-rounded')) {
                        m.target.removeAttribute('data-icon-replaced');
                        processIconNode(m.target);
                    }
                }
            });
        } else if (m.type === 'characterData') {
            if (m.target.parentElement && m.target.parentElement.classList.contains('material-symbols-rounded')) {
                m.target.parentElement.removeAttribute('data-icon-replaced');
                processIconNode(m.target.parentElement);
            }
        }
    });
});

// Start immediately before DOMContentLoaded
observer.observe(document.documentElement, { 
    childList: true, 
    subtree: true, 
    characterData: true 
});

// Also run on DOMContentLoaded just in case
document.addEventListener('DOMContentLoaded', scanDOM);
