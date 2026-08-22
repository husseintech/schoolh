'use strict';

// Passive service worker. It exists only to enable web-push notifications.
// Crucially it does NOT intercept page/fetch requests: that way `window.print()`
// (the programmatic print button) reuses the browser HTTP cache and behaves
// exactly like the native right-click "Print", which was much faster.
const CACHE = 'schoolm-v4';

self.addEventListener('install', (e) => {
    self.skipWaiting();
});

self.addEventListener('activate', (e) => {
    e.waitUntil(
        caches.keys().then((keys) => Promise.all(keys.map((k) => caches.delete(k))))
            .then(() => self.clients.claim())
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
