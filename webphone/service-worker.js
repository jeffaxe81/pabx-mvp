/*
 * Shell PWA e notificações. Nenhum recurso de fila, gravação ou sinalização
 * SIP deve ser interceptado pelo cache offline.
 */
const CACHE_NAME = 'telefonista-shell-v4';
const APP_SHELL = [
  './',
  './index.html',
  './vendor/jssip-3.10.1.min.js',
  './remote-audio.js',
  './manifest.json',
  './icons/icon-192.png',
  './icons/icon-512.png',
];
// Comparação por URL completa evita casar '/api/.../' ou ativos de outra origem.
const APP_SHELL_URLS = new Set(APP_SHELL.map(path => new URL(path, self.registration.scope).href));

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(APP_SHELL)));
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(names =>
    Promise.all(names.filter(name => name !== CACHE_NAME).map(name => caches.delete(name)))
  ));
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET' || !APP_SHELL_URLS.has(event.request.url)) return;
  event.respondWith(caches.match(event.request).then(cached => cached || fetch(event.request)));
});

self.addEventListener('message', event => {
  if (!event.data || event.data.type !== 'incoming-call') return;
  const { peer } = event.data;
  self.registration.showNotification('Chamada recebida', {
    body: peer ? `De: ${peer}` : 'Toque para atender',
    icon: './icons/icon-192.png',
    badge: './icons/icon-192.png',
    tag: 'incoming-call',
    renotify: true,
    requireInteraction: true,
    vibrate: [200, 100, 200],
  });
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  event.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(clientList => {
    for (const client of clientList) {
      if ('focus' in client) return client.focus();
    }
    if (self.clients.openWindow) return self.clients.openWindow('./index.html');
  }));
});
