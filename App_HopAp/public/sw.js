// Service worker: cho phép "Thêm vào màn hình chính" và mở vỏ app khi mạng chập chờn.
// Dữ liệu Firebase luôn lấy trực tiếp (không cache) để không hiển thị số đo cũ như số mới.
const CACHE = 'hop-ap-v11';
const SHELL = ['./', 'index.html', 'styles.css', 'app.js', 'logic.js', 'firebase-config.js',
  'manifest.webmanifest', 'icons/icon.svg', 'icons/icon-192.png', 'icons/icon-512.png'];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (event) => {
  event.waitUntil(caches.keys()
    .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.origin !== self.location.origin) return;
  // Mạng trước (hỏi lại máy chủ, không lấy bản trong HTTP cache), cache sau khi mất mạng.
  const fresh = event.request.mode === 'navigate'
    ? new Request(event.request.url, { cache: 'no-cache', credentials: 'same-origin' })
    : new Request(event.request, { cache: 'no-cache' });
  event.respondWith(fetch(fresh)
    .then((response) => {
      const copy = response.clone();
      caches.open(CACHE).then((cache) => cache.put(event.request, copy));
      return response;
    })
    .catch(() => caches.match(event.request).then((hit) => hit || caches.match('index.html'))));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(self.clients.matchAll({ type: 'window' }).then((list) => {
    const open = list.find((c) => 'focus' in c);
    return open ? open.focus() : self.clients.openWindow('./');
  }));
});
