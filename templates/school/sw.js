'use strict';

const CACHE = 'schoolm-v2-safe-static';
const OFFLINE_PAGE = '/static/pwa/offline.html';
const CORE = [OFFLINE_PAGE, '/static/pwa/icon-192.png', '/static/pwa/icon-512.png'];

self.addEventListener('install', (e) => {
    e.waitUntil(caches.open(CACHE).then((c) => c.addAll(CORE)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
    e.waitUntil(
        caches.keys().then((keys) => Promise.all(
            keys.filter((key) => key.startsWith('schoolm-') && key !== CACHE).map((key) => caches.delete(key))
        ))
            .then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', (e) => {
    const url = new URL(e.request.url);
    if (e.request.method !== 'GET' || url.origin !== location.origin) return;

    // Account, login and form pages must always come from the server. They can
    // contain private data and rotating CSRF tokens, so they are never cached.
    if (e.request.mode === 'navigate') {
        e.respondWith(fetch(e.request).catch(() => caches.match(OFFLINE_PAGE)));
        return;
    }

    // Cache only public static assets. API and dynamic application routes keep
    // the browser's normal network behaviour and Django security checks.
    if (!url.pathname.startsWith('/static/')) return;
    e.respondWith(
        fetch(e.request)
            .then((resp) => {
                if (resp.ok) {
                    const copy = resp.clone();
                    caches.open(CACHE).then((c) => c.put(e.request, copy));
                }
                return resp;
            })
            .catch(() => caches.match(e.request))
    );
});

