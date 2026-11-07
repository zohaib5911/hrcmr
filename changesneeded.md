# changesneeded.md — audit AUDIT-1 round 2 (2026-11-07, Claude Opus 5.5)
Scope: audit-1-r1 (d7e526e)..16184dc (the round 1 fix commits) + regressions in files upload, e-mail delivery, body limits
Tests at audit: api 792/0/0, web unit 777/0, recruitment + careers e2e 5/0, CI on PR #19 running
Round 1 (1 P0 / 5 P1 / 1 P2) is fixed and ticked in git history (16184dc); every round 1 fix was re-read and holds,
except C1.1.3 and C1.1.7, which introduced C1.2.1 and C1.2.2 below.
Note: the round 1 fixes were written by the same model that ran this round; round 3 should be a fresh session.

### [x] C1.2.1 · P1 · Careers page reads share one rate-limit bucket for every visitor (from C1.1.7)
- **Problem:** `_limit_reads` (`api/app/modules/recruitment/public.py`) limits `careers_page` and `careers_posting` to 120 a minute per `client_ip`. Those two are fetched by the Next.js server (`web/components/careers/public-client.ts`, server-side render), which sends no visitor address, so every visitor counts against the web server's single address. Once a site gets modest traffic, the careers pages return 429 for everyone.
- **Fix:** remove the `await _limit_reads(request)` call from `careers_page` and `careers_posting` only. Keep it on `careers_logo`, which the browser fetches directly. Add one line to the `_limit_reads` docstring: the server-rendered pages are limited at the edge (Cloudflare rule, Phase 23), not here. Change `test_too_many_page_views_from_one_connection_are_refused` (`api/tests/db/test_careers.py`) to call `/public/careers/{slug}/logo` after uploading a logo (copy the upload lines from `test_the_logo_shows_on_the_careers_pages_once_uploaded`), and assert the list is still 200 after the limit is reached. Add "Cloudflare rate-limit rule for /careers/*" under Owner actions in STATUS.md, for T23.
- **Done when:** `uv run pytest tests/db/test_careers.py` passes.

### [x] C1.2.2 · P1 · A CV over 1 MB is refused before it reaches the endpoint (from C1.1.3)
- **Problem:** `BodyLimitMiddleware` (`api/app/main.py:190-196`) has no entry for `/api/v1/public/postings`, so the apply form gets the 1 MB default (`app/core/body_limit.py:20`) and any CV over ~1 MB gets 413. The form says "up to 10 MB", and the round 1 test only used a tiny PDF.
- **Fix:** add `f"{API_PREFIX}/public/postings": PROOF_LIMIT,` (11 MB) to the `limits` dict in `app/main.py`. In `tests/db/test_careers.py::test_a_cv_is_scanned_and_kept_with_the_candidate`, send a CV of about 3 MB (`PDF + b"\n%" + b"0" * 3_000_000`) for the accepted upload.
- **Done when:** that test passes with the 3 MB CV, and a test sending an 11.5 MB CV gets 413.

### [x] C1.2.3 · P1 · Other upload routes are capped at 1 MB too (policy file from T10.3; others older)
- **Problem:** the same table lacks `/policies/{id}/file` and `/policies/preview` (T10.3, in AUDIT-1 scope, missed in round 1), plus `/employees/{id}/documents`, `/employees/{id}/photo` and `/employees/{id}/opt-out-48h/agreement`. Each endpoint passes a `max_bytes` to `FileService.upload` (or uses the 25 MB default), but the middleware refuses anything over 1 MB first.
- **Fix:** for each route, find the `max_bytes` it passes (default `MAX_BYTES` = 25 MB → `UPLOAD_LIMIT`) and add a matching prefix to `limits` in `app/main.py`. `/employees` is a prefix of JSON routes too, so use a path pattern or the exact sub-paths. If `_limit_for` only does `startswith`, extend it to accept a compiled regex key, and keep the existing entries working. Add a guard test `tests/test_body_limits.py`: walk `create_app().routes`, find every route whose endpoint has an `UploadFile` parameter, and assert `_limit_for(path with ids filled in)` is greater than 1 MB.
- **Done when:** the guard test passes. A DB test uploads a 3 MB PDF to `/policies/{id}/file` and gets 200 (copy the upload lines from `tests/db/test_policies.py`).

### [x] C1.2.4 · P2 · The candidate's invite lists the interviewers' e-mail addresses (from C1.1.2)
- **Problem:** `create_interview` (`api/app/modules/recruitment/router.py`) builds one `.ics` with every attendee and attaches it to the candidate's e-mail too. `Employee.email` is the only e-mail on file (often personal), and the external candidate did not see these addresses before.
- **Fix:** build two invites with `_invite_text`. The staff copy keeps every attendee. The candidate copy has only `[(candidate_name, candidate_email)]` as attendees. Use the same UID, so both are the same event.
- **Done when:** `tests/db/test_interviews.py` asserts that the candidate's attachment does not contain the panel address and the staff attachment does.

## Notes (no action needed)
- C1.1.1 holds: no stage move into or out of Hired, and every pair of stages is tested. At Offer Accepted the page shows Convert, with no "Move to Hired".
- C1.1.2 attachment path checked by hand for SMTP (Content-Type `text/calendar; method="REQUEST"`, filename `invite.ics`). The Resend body uses `filename`, `content` (base64) and `content_type`.
- The `FileService._vet` refactor keeps every refusal code and detail; the files, company-document and employee-document tests pass unchanged.
- A refused public CV is not audit-logged (no signed-in user, and nothing is written); this is deliberate and recorded in STATUS.
