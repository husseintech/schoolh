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
