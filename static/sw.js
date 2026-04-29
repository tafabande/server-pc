self.addEventListener('install', (e) => {
    e.waitUntil(
        caches.open('media-hub-v1').then((cache) => cache.addAll([
            '/', 
            '/static/index.html', 
            '/static/js/app.js',
            '/static/css/m3.css'
        ]))
    );
});

self.addEventListener('fetch', (e) => {
    // Only cache UI requests, never the actual video streams or API calls
    const url = new URL(e.request.url);
    if (!url.pathname.startsWith('/api/')) {
        e.respondWith(
            caches.match(e.request).then((res) => res || fetch(e.request))
        );
    }
});
