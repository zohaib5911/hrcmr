// No authenticated pages, API responses, or employee records are cached.
const script = `self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.mode !== "navigate" || url.origin !== self.location.origin || url.pathname !== "/clock") return;
  event.respondWith(fetch(event.request).catch(() => new Response(
    '<!doctype html><html lang="en"><meta name="viewport" content="width=device-width"><title>Clock offline</title><main><h1>You are offline</h1><p>Reconnect and reload to clock in or out. No time has been recorded.</p></main></html>',
    { status: 503, headers: { "Content-Type": "text/html; charset=utf-8" } }
  )));
});`;
export function GET() {
  return new Response(script, {
    headers: {
      "Content-Type": "text/javascript",
      "Cache-Control": "no-cache",
      "Service-Worker-Allowed": "/clock",
    },
  });
}
