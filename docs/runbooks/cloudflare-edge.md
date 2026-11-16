# Cloudflare edge settings (O6.1.7)

Set these in the Cloudflare dashboard when staging and production are provisioned (Phase 23,
T23.1/T23.3). Tick each line with the date and the zone once it is live, and check it with the
command given. Nothing here can be tested locally.

The app already sends its own headers (`web/lib/security/csp.ts`): CSP with a per-request nonce,
HSTS, `X-Frame-Options`, `Cross-Origin-Opener-Policy: same-origin` and
`Cross-Origin-Resource-Policy` (`same-site`; `cross-origin` only for `/brand/`, link previews and
icons, which e-mails and other sites embed). The edge must pass them through unchanged.

## Caching
- [ ] **Static build files cached for a year.** Cache Rule: URI path starts with `/_next/static/`
  → Eligible for cache, Edge TTL 1 year, Browser TTL "respect origin". The file names carry a
  content hash, so they never change. Check: `curl -sI https://<web>/_next/static/<any chunk>`
  shows `cf-cache-status: HIT` on the second request.
- [ ] **HTML is not cached.** Every page carries a per-request CSP nonce (decision O6.1.1), so a
  cached page would hand one nonce to every visitor. Keep the default (HTML bypasses the cache);
  add no "Cache Everything" rule. Check: a page shows `cf-cache-status: DYNAMIC` and a different
  `nonce-` value on each request.

## Transport
- [ ] **Brotli** on (Speed → Optimization → Content Optimization).
- [ ] **HTTP/3 (with QUIC)** on (Network). Check: response header `alt-svc: h3=":443"`.

## Rate limiting (WAF → Rate limiting rules)
The API limits each person and address itself (Redis); these edge rules stop floods before they
reach the origin. Count by IP; action Block for 10 minutes.
- [ ] `/api/v1/auth/*` (sign-in, sign-up, password reset, MFA, step-up): more than 30 requests per
  minute per IP.
- [ ] `/api/v1/public/*` (careers apply, contact form, public SOC lookups): more than 120 requests per
  minute per IP.
- [ ] Check: from one test address, 31 quick `POST /api/v1/auth/login` calls get a Cloudflare
  block on the 31st (the API's own limit answers 429 before that for one account).
