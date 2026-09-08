import json

from django.http import HttpResponse, JsonResponse
from django.templatetags.static import static


def manifest(request):
    payload = {
        "name": "خرج من",
        "short_name": "خرج من",
        "description": "مدیریت هزینه‌های روزانه و طلب‌ها",
        "lang": "fa",
        "dir": "rtl",
        "id": "/",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "display_override": ["standalone", "minimal-ui"],
        "background_color": "#050b0d",
        "theme_color": "#07110f",
        "orientation": "portrait-primary",
        "icons": [
            {
                "src": static("expense_tracker/icons/icon-192.png"),
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any",
            },
            {
                "src": static("expense_tracker/icons/icon-512.png"),
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any maskable",
            },
        ],
        "shortcuts": [
            {
                "name": "ثبت خرج",
                "short_name": "خرج جدید",
                "url": "/#new-expense",
                "icons": [
                    {
                        "src": static("expense_tracker/icons/icon-192.png"),
                        "sizes": "192x192",
                        "type": "image/png",
                    }
                ],
            },
            {
                "name": "تراکنش‌ها",
                "short_name": "تراکنش‌ها",
                "url": "/expenses/",
                "icons": [
                    {
                        "src": static("expense_tracker/icons/icon-192.png"),
                        "sizes": "192x192",
                        "type": "image/png",
                    }
                ],
            },
        ],
    }
    response = JsonResponse(payload, json_dumps_params={"ensure_ascii": False})
    response["Content-Type"] = "application/manifest+json; charset=utf-8"
    response["Cache-Control"] = "public, max-age=3600"
    return response


def service_worker(request):
    script = r'''
const CACHE_NAME = "kharj-man-shell-v3";
const STATIC_ASSETS = [
  "/static/expense_tracker/app.css",
  "/static/expense_tracker/app.js",
  "/static/expense_tracker/icons/icon-192.png",
  "/static/expense_tracker/icons/icon-512.png"
];

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(STATIC_ASSETS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", event => {
  const request = event.request;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // Never cache authenticated HTML or financial API responses.
  // Only the expense app's static shell is cached.
  if (!url.pathname.startsWith("/static/expense_tracker/")) return;

  event.respondWith(
    caches.match(request).then(cached => {
      const fresh = fetch(request).then(response => {
        if (response && response.ok) {
          const copy = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(request, copy));
        }
        return response;
      });
      return cached || fresh;
    })
  );
});
'''
    response = HttpResponse(script, content_type="application/javascript; charset=utf-8")
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response
