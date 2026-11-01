// Liveness for the container platform. It skips the proxy and touches no other service.
export function GET(): Response {
  return new Response("ok", {
    headers: { "Cache-Control": "no-store", "Content-Type": "text/plain" },
  });
}
