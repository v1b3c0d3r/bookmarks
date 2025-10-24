// byte-to-byte comparison failure will trigger service worker update
// v20251024

self.addEventListener('install', (event) => {
  self.skipWaiting();
  self.caches.delete('bookmarks-storage');
  event.waitUntil(
    caches.open('bookmarks-storage').then((cache) => cache.addAll([
      './',
      'static/favicon.svg',
      'static/all.min.css',
      'static/fa-solid-900.woff2',
      'static/tailwind_css.js',
      'static/weblink.png',
      'static/manifest.json',
    ])),
  );
});
  
  
self.addEventListener('activate', event => {
  console.info('Service worker ready');
});
  
  
self.addEventListener('message', (event) => {
  console.log(`Got message: ${event.data}`);
});
  
  
self.addEventListener('fetch', (event) => {
  let url = event.request.url.split('?')[0];
  if (url.match('^.*/sw\.js$')) {
    console.debug(`No-cache: ${event.request.url}`);
    return false;
  }
  if (event.request.method === "POST" || event.request.method === "PUT" || event.request.method === "DELETE") {
    console.debug(`No-cache: ${event.request.url}`);
    return false;
  }
  if (event.request.method === "GET") {
    if (url.match('^.*/static/.*$')) {
      console.info('Fetching static data: cache-first');
      event.respondWith(
        caches.match(event.request.clone())
          .then(async (response) => {
            if (response) return response;
            return fetch(event.request.clone())
              .then(async (resp) => {
                if (resp && resp.status < 400) {
                  console.info(`Saving static resource ${event.request.url}`);
                  await caches.open("bookmarks-storage").then((cache) => cache.put(event.request, resp.clone()));
                }
                return resp;
              });
          }),
      );
      return;
    }
    console.info('Fetching API data: network-first');
    event.respondWith(fetch(event.request.clone())
      .then(async (response) => {
        if (response && response.status < 400) {
          console.info(`Saving API response ${event.request.url}`);
          await caches.open("bookmarks-storage").then((cache) => cache.put(event.request, response.clone()));
        }
        return response;
      })
      .catch(err => caches.match(event.request))
      ,);
    return;
  }
});
  
  
