/*
 * Service worker do console da telefonista.
 *
 * Duas responsabilidades:
 * 1. Cachear o "app shell" (HTML/manifest/ícones) pra abrir mais
 *    rápido e sobreviver a uma queda momentânea de rede - NÃO cacheia
 *    nada dinâmico (fila, gravações, métricas), só o essencial pra
 *    interface abrir.
 * 2. Mostrar uma notificação NATIVA do sistema operacional quando a
 *    página manda um postMessage avisando de chamada recebida - isso
 *    é o que permite perceber a chamada mesmo com a aba em segundo
 *    plano ou o notebook com a tela bloqueada (ver manual 15 pras
 *    limitações reais disso).
 */

const CACHE_NAME = 'telefonista-shell-v1';
const APP_SHELL = [
  './',
  './index.html',
  './manifest.json',
  './icons/icon-192.png',
  './icons/icon-512.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(
        names.filter((name) => name !== CACHE_NAME).map((name) => caches.delete(name))
      )
    )
  );
  self.clients.claim();
});

// Cache-first só pro app shell; qualquer outra coisa (API do
// queue-api, WSS do Asterisk) vai direto pra rede, sem interceptar -
// dados de chamada em tempo real nunca devem vir de cache.
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  const isShellRequest = APP_SHELL.some((path) => url.pathname.endsWith(path.replace('./', '/')));

  if (!isShellRequest) return;

  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request))
  );
});

// A página (index.html) manda esse postMessage quando uma chamada
// chega. O service worker é quem tem permissão de mostrar notificação
// do sistema operacional (fora da própria aba).
self.addEventListener('message', (event) => {
  if (!event.data || event.data.type !== 'incoming-call') return;

  const { peer } = event.data;
  self.registration.showNotification('Chamada recebida', {
    body: peer ? `De: ${peer}` : 'Toque para atender',
    icon: './icons/icon-192.png',
    badge: './icons/icon-192.png',
    tag: 'incoming-call',   // substitui a notificação anterior, não empilha
    renotify: true,
    requireInteraction: true,
    vibrate: [200, 100, 200],
  });
});

// Clicar na notificação foca a aba já aberta (ou abre uma nova) -
// sem isso, o clique não faz nada e a notificação só fica lá.
self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if ('focus' in client) return client.focus();
      }
      if (self.clients.openWindow) {
        return self.clients.openWindow('./index.html');
      }
    })
  );
});
