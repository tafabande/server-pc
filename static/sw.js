const CACHE_NAME = 'streamdrop-v2';
const ASSETS = [
    '/',
    '/static/index.html',
    '/static/js/app.js',
    '/static/css/m3.css',
    '/static/img/icon-192.png',
    '/static/img/icon-512.png',
    '/static/img/screenshot-mobile.png',
    '/static/img/screenshot-desktop.png',
    'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap',
    'https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200'
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
