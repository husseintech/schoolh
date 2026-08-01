'use strict';

const CACHE = 'schoolm-v1';
const CORE = ['/dashboard/', '/static/pwa/icon-192.png', '/static/pwa/icon-512.png'];

self.addEventListener('install', (e) => {
    e.waitUntil(caches.open(CACHE).then((c) => c.addAll(CORE)).then(() => self.skipWaiting()));
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
    e.respondWith(
        fetch(e.request)
            .then((resp) => {
                if (resp.ok && url.pathname.startsWith('/static/')) {
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
