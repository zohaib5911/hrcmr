# Security notes

Decisions about the security design that are not obvious from the code. The full rules are in `plan.md` Section 4.

## Content Security Policy

- Scripts use a per-request nonce plus `strict-dynamic`; there is no `'unsafe-inline'` for scripts (`web/lib/security/csp.ts`).
- `<style>` elements use the nonce too.
- **Accepted exception:** `style-src-attr 'unsafe-inline'`. The animation library sets `style` attributes at run time (transforms and opacity while a layer opens, closes or slides), and a nonce cannot be attached to an attribute. It allows inline `style="..."` attributes only; it does not allow `<style>` elements or any script. Components may not use the `style` prop themselves (an ESLint rule bans it), so the exception is not used by our own markup. Decided by the owner on 2026-11-02.

## The visitor's IP address

`X-Real-IP` and `CF-Connecting-IP` are believed only when the connection comes from a trusted proxy
(`api/app/core/client_ip.py`). In production that is Railway's private network (override with
`TRUSTED_PROXY_CIDRS`); `CF-Connecting-IP` counts only when Railway reports that the connection to
it came from one of Cloudflare's published ranges (the weekly worker job fetches cloudflare.com/ips-v4 and /ips-v6 into Redis and the API rereads them hourly; a reply that does not look like the list is refused; the copy in `core/client_ip.py`, checked 2026-11-02, is the fallback).
Everywhere else, including a developer machine, the socket address is used and the headers are
ignored, so a forged header cannot dodge a rate limit or poison the audit trail.

## Request bodies

Every JSON request model inherits `RequestModel` (`api/app/core/schemas.py`), which refuses fields it
does not declare. A test walks the OpenAPI document and fails for any request body that does not.

## AI requests (T14.4)
- Only the API calls Anthropic (`api/app/integrations/anthropic.py`); with no `ANTHROPIC_API_KEY`, or the company's AI switch off, nothing is sent.
- `app.ai.redaction.scrub` drops restricted keys (NI, bank, passport/visa/BRP, share code, CoS, health/sickness, salary, address, date of birth, contact details), labels names (`Employee A`) and redacts identifier-like text; `assert_clean` checks the exact wire body and refuses to send if anything survives.
- Usage is logged in `ai_interactions` as metadata only (feature, model, status, token counts, duration). Rate limit: 30 per hour per user.
