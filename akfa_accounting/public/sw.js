const CACHE_NAME = 'akfa-hr-v1';
const urlsToCache = [
    '/app/mobile-hr',
    '/assets/akfa_accounting/js/pwa_init.js',
    '/assets/frappe/css/desk.min.css',
    '/assets/frappe/js/desk.min.js'
];

self.addEventListener('install', function (event) {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(function (cache) {
                console.log('Opened cache');
                // We do not strictly enforce caching to avoid issues with dynamic content
                // return cache.addAll(urlsToCache);
            })
    );
});

self.addEventListener('fetch', function (event) {
    // Network first strategy
    event.respondWith(
        fetch(event.request).catch(function () {
            return caches.match(event.request);
        })
    );
});
