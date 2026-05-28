// Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
// SPDX-License-Identifier: MIT
// GalleryControl Service Worker
// Version: 1.0.0

const CACHE_NAME = 'gallerycontrol-v1';

// Static assets to precache on install
const PRECACHE_ASSETS = [
  '/manifest.json',
  '/icon-192x192.png',
  '/icon-512x512.png',
  '/apple-touch-icon.png'
];

// Install event: precache static assets
self.addEventListener('install', (event) => {
  console.log('[SW] Installing service worker...');
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('[SW] Precaching static assets');
        return cache.addAll(PRECACHE_ASSETS);
      })
      .then(() => {
        // Skip waiting to activate immediately
        return self.skipWaiting();
      })
  );
});

// Activate event: clean up old caches
self.addEventListener('activate', (event) => {
  console.log('[SW] Activating service worker...');
  event.waitUntil(
    caches.keys()
      .then(cacheNames => {
        return Promise.all(
          cacheNames
            .filter(name => name !== CACHE_NAME)
            .map(name => {
              console.log('[SW] Deleting old cache:', name);
              return caches.delete(name);
            })
        );
      })
      .then(() => {
        // Take control of all pages immediately
        return self.clients.claim();
      })
  );
});

// Notify all clients to reload so the browser hits the guardian login page
function notifyClientsToReload() {
  self.clients.matchAll({ type: 'window' }).then(clients => {
    clients.forEach(client => client.postMessage({ type: 'guardian-locked' }));
  });
}

// Fetch event: handle requests
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Let the browser handle navigation requests (HTML pages) and API/WS calls directly.
  // This ensures guardian redirects work naturally for page loads.
  if (event.request.mode === 'navigate' || url.pathname.startsWith('/api/') || url.pathname.startsWith('/ws/')) {
    return;
  }

  // For static subresources (JS, CSS, images): try cache first, then network
  event.respondWith(
    caches.match(event.request)
      .then(cachedResponse => {
        if (cachedResponse) {
          // Return cached response, but check for guardian redirect in background
          event.waitUntil(
            fetch(event.request, { redirect: 'manual' })
              .then(networkResponse => {
                if (networkResponse.type === 'opaqueredirect') {
                  // Guardian is locked — purge cache and notify clients to reload
                  caches.delete(CACHE_NAME).then(() => notifyClientsToReload());
                  return;
                }
                if (networkResponse.ok) {
                  caches.open(CACHE_NAME)
                    .then(cache => cache.put(event.request, networkResponse));
                }
              })
              .catch(() => { /* Ignore network errors */ })
          );
          return cachedResponse;
        }

        // Not in cache — fetch from network
        return fetch(event.request)
          .then(networkResponse => {
            // Cache successful responses
            if (networkResponse.ok && event.request.method === 'GET') {
              const responseToCache = networkResponse.clone();
              caches.open(CACHE_NAME)
                .then(cache => cache.put(event.request, responseToCache));
            }
            return networkResponse;
          });
      })
  );
});

// Message event: handle messages from the app
self.addEventListener('message', (event) => {
  if (event.data === 'skipWaiting') {
    self.skipWaiting();
  }
});
