'use strict';

const CACHE = 'schoolm-v3';
// Pre-cache every static asset the pages (and the print preview) need, so the
// first print is instant instead of re-downloading everything over a slow link.
const PRECACHE = [
    '/static/vendor/bootstrap/css/bootstrap.min.css',
    '/static/vendor/bootstrap/css/bootstrap.rtl.min.css',
    '/static/vendor/bootstrap-icons/bootstrap-icons.css',
    '/static/vendor/select2/css/select2.min.css',
    '/static/vendor/select2/css/select2-bootstrap-5-theme.rtl.min.css',
    '/static/vendor/leaflet/leaflet.css',
    '/static/vendor/jquery/jquery.min.js',
    '/static/vendor/bootstrap/js/bootstrap.bundle.min.js',
    '/static/vendor/select2/js/select2.min.js',
    '/static/vendor/leaflet/leaflet.js',
    '/static/vendor/bootstrap-icons/fonts/bootstrap-icons.woff2?1bb88866b4085542c8ed5fb61b9393dd',
    '/static/pwa/icon-192.png',
    '/static/pwa/icon-512.png',
    '/dashboard/'
];

self.addEventListener('install', (e) => {
    e.waitUntil(
        caches.open(CACHE)
            .then((c) => Promise.all(PRECACHE.map((u) => c.add(u).catch(() => {}))))
            .then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', (e) => {
    e.waitUntil(
        caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
            .then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', (e) => {
    const url = new URL(e.request.url);
    if (e.request.method !== 'GET' || url.origin !== location.origin) return;
    // Static assets are immutable (hashed by WhiteNoise) -> cache-first so the browser
    // serves them instantly. This is what makes print preview fast on slow connections.
    if (url.pathname.startsWith('/static/')) {
        e.respondWith(
            caches.match(e.request).then((cached) => {
                if (cached) return cached;
                return fetch(e.request).then((resp) => {
                    if (resp.ok) {
                        const copy = resp.clone();
                        caches.open(CACHE).then((c) => c.put(e.request, copy));
                    }
                    return resp;
                }).catch(() => cached);
            })
        );
        return;
    }
    // Navigations and other requests: network-first with cache fallback (keeps data fresh).
    e.respondWith(
        fetch(e.request)
            .then((resp) => {
                if (resp.ok) {
                    const copy = resp.clone();
                    caches.open(CACHE).then((c) => c.put(e.request, copy));
                }
                return resp;
            })
            .catch(() => caches.match(e.request).then((m) => m || caches.match('/dashboard/')))
    );
});

self.addEventListener('push', (e) => {
    let data = { title: 'النظام المدرسي', body: 'لديك إشعار جديد', url: '/dashboard/' };
    try {
        if (e.data) data = Object.assign(data, e.data.json());
    } catch (err) {
        if (e.data) data.body = e.data.text();
    }
    e.waitUntil(
        self.registration.showNotification(data.title, {
            body: data.body,
            icon: '/static/pwa/icon-192.png',
            badge: '/static/pwa/icon-192.png',
            dir: 'rtl',
            lang: 'ar',
            data: { url: data.url },
        })
    );
});

self.addEventListener('notificationclick', (e) => {
    e.notification.close();
    const url = (e.notification.data && e.notification.data.url) || '/dashboard/';
    e.waitUntil(
        self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((list) => {
            for (const client of list) {
                if (client.url.startsWith(location.origin) && 'focus' in client) {
                    client.navigate(url);
                    return client.focus();
                }
            }
            return self.clients.openWindow(url);
        })
    );
});
