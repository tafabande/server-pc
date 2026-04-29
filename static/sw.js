const CACHE_NAME = 'streamdrop-v8';
const ASSETS = [
    '/',
    '/static/index.html',
    '/static/js/app.js?v=7',
    '/static/js/editor.js?v=7',
    '/static/js/offline-icons.js?v=8',
    '/static/css/m3.css?v=8',
    '/static/img/icon-192.png',
    '/static/img/icon-512.png'
];

self.addEventListener('install', (e) => {
    e.waitUntil(
        caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS))
    );
    self.skipWaiting();
});

self.addEventListener('activate', (e) => {
    e.waitUntil(
        caches.keys().then((keys) => {
            return Promise.all(
                keys.map((key) => {
                    if (key !== CACHE_NAME) {
                        return caches.delete(key);
                    }
                })
            );
        })
    );
});

self.addEventListener('fetch', (e) => {
    const url = new URL(e.request.url);
    
    // Ignore API, stream, and shared paths (dynamic content)
    if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/shared/') || url.pathname.startsWith('/stream')) {
        return;
    }

    e.respondWith(
        caches.match(e.request).then((response) => {
            return response || fetch(e.request);
        })
    );
});
