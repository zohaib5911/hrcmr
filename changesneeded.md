# changesneeded.md — audit AUDIT-1 round 1 (2026-11-07, Claude Opus 5.5)
Scope: f37f781..a49307d   Tests at audit: api 784/0/0, web unit 777/0, e2e 427/0 (164 skipped, CI run on d7e526e), CI green. check-rls covered by tests/db/test_cli.py (CLI needs a local .env)

### [x] C1.1.1 · P0 · Only Convert may set Hired; nothing moves out of Hired (from T11.4/T11.5)
- **Problem:** `POST /applications/{id}/stage` accepts `stage="hired"` (`api/app/modules/recruitment/applications.py:35` `stage_error` allows offer_accepted → hired), so an application can be Hired with no employee, skipping both convert gates. It also allows hired → offer_accepted (backward move); after that, `convert_application` (`router.py:1077`, the `stage == "hired"` check) runs again and creates a **second employee** for the same candidate.
- **Fix:** in `stage_error` (pure rules), add two rules before the others: if `current == "hired"` return `"This candidate is already an employee. The application cannot change."`; if `target == "hired"` return `"Use Convert to employee to hire this candidate."`. Update `tests/test_application_stages.py` `expected()` to match (every pair still tested). Web `web/components/recruitment/application-page.tsx`: drop `hired` from the "Move to stage" options and do not show the "Move to Hired" primary button (at Offer Accepted the Convert button is the next action); hide the select when stage is `hired`.
- **Done when:** `uv run pytest tests/test_application_stages.py` passes; new DB test in `tests/db/test_convert.py`: stage → `hired` via `/stage` is 422 with no employee; after a real convert, `/stage` to `offer_accepted` is 422 and a second convert is 409 with employee count 1. `pnpm typecheck && pnpm lint`; `pnpm test:e2e recruitment.spec.ts` green.

### [x] C1.1.2 · P1 · Interview invites must carry the .ics file (from T11.4, plan L982)
- **Problem:** `create_interview` (`api/app/modules/recruitment/router.py:843-875`) queues `interview_invite` / `interview_invite_candidate` e-mails with no attachment. The `.ics` exists only as a signed-in download (`.../invite.ics`), which the candidate cannot open. Plan: "an .ics invite is emailed to interviewers and the candidate".
- **Fix:** (1) `api/app/integrations/email.py`: add `attachments: tuple[Attachment, ...] = ()` to `Message` (`Attachment` = filename, content_type, content bytes) and send them in every transport (Resend: `attachments=[{"filename", "content": base64}]`; SMTP/Mailpit: `EmailMessage.add_attachment`; the fake/log transport records them). (2) In `create_interview`, put the ics text (`interview_ics(...)`, same args as the download endpoint) into the encrypted payload as key `ics` for both e-mails. (3) In `app/modules/email/outbox.py` `_message`, when the payload has `ics`, add it as `invite.ics`, `text/calendar; method=REQUEST`, and do not pass it to the template renderer.
- **Done when:** `tests/db/test_interviews.py::test_an_interview_sends_invites_and_an_ics_file` also asserts that delivering a queued invite through the fake transport gives one `text/calendar` attachment containing `BEGIN:VCALENDAR` and the interview's `DTSTART`; e-mail unit tests still pass.

### [x] C1.1.3 · P1 · Careers apply: optional CV upload, virus-scanned (from T11.6 step 2, plan L972)
- **Problem:** `POST /public/postings/{company}/{posting}/apply` (`api/app/modules/recruitment/public.py:158`) takes JSON only; there is no CV upload. The Done-when was ticked without it.
- **Fix:** make the endpoint accept `multipart/form-data` (fields as today + optional `cv` file). Run the file through the existing files service upload (`app/modules/files/service.py` `upload`: size, extension, magic bytes, ClamAV) with the allowed types PDF/DOC/DOCX, max 10 MB, owner_type `candidate`, owner_id the candidate, uploaded_by None. Infected or invalid → 422 with no candidate/application rows (do the upload before writing rows, or in the same transaction). Web `web/components/careers/apply-form.tsx`: add an optional "CV (PDF or Word, up to 10 MB)" file input using `components/ui` and send `FormData`. Regenerate the client (`pnpm gen:api`).
- **Done when:** `tests/db/test_careers.py` new test: apply with a small PDF → a `files` row with owner_type `candidate`, scan_status `clean`; apply with the EICAR test string → 422 and no application. `pnpm gen:api:check` clean; `careers.spec.ts` green.

### [x] C1.1.4 · P1 · Careers posting page shows the company logo (from T11.6, plan L971)
- **Problem:** `CareersPostingDetail` / `CareersPage` (`public.py:42-61`) carry no logo, and the pages show none. Companies have `logo_file_id` (`companies/models.py:89`).
- **Fix:** add `logo_url: str | None` to both response models: a short-lived signed URL for the logo file when `logo_file_id` is set and the file is `clean` (copy how `GET /company` serves the logo in `api/app/modules/companies/router.py`), else None. Show it in `web/app/careers/[company]/page.tsx` and `[posting]/page.tsx` (plain `<img>` with the company name as alt, max height 48 px). Add `logo_url` to `LIST_KEYS` / `DETAIL_KEYS` in `tests/db/test_careers.py`. Check the CSP `img-src` allows the storage origin.
- **Done when:** field-list test passes with `logo_url`; a test with a logo set returns a non-null URL; `pnpm gen:api:check` clean.
- **As built:** `has_logo` plus a public `GET /public/careers/{slug}/logo` that streams the clean file, copying `GET /company/logo` and `has_logo` (no storage origin added to the CSP).

### [x] C1.1.5 · P1 · Careers tests for the refusal paths (from T11.6 Done when)
- **Problem:** `tests/db/test_careers.py` has no test for: Turnstile rejecting a token, an **Internal** open posting being 404 (detail and apply), the 429 rate limit, or another company's posting slug under this company's slug.
- **Fix:** add tests in `tests/db/test_careers.py`: (a) set `rig["app"].state.auth.turnstile` to a fake whose `verify` returns False → apply is 400 `TURNSTILE_FAILED` and no application/candidate row; restore after. (b) open posting with visibility `internal` → GET detail 404, apply 404, not in the list. (c) call apply 21 times from one client (or lower the limit by monkeypatching `APPLY_PER_CONNECTION`) → 429 `RATE_LIMITED`. (d) open external posting in company B; `GET /public/postings/{slug A}/{posting slug B}` → 404.
- **Done when:** the four new tests pass.

### [x] C1.1.6 · P1 · Convert: cross-tenant test (from T11.5)
- **Problem:** `tests/db/test_convert.py` never calls convert with another company's application id.
- **Fix:** add a test: a company-B admin calls `POST /applications/{company A app id}/convert` → 404, and company A's application stage is unchanged.
- **Done when:** the new test passes.

### [x] C1.1.7 · P2 · Public careers GETs are not rate-limited (from T11.6, plan L1636)
- **Problem:** plan item 24: public endpoints are rate-limited. Only `apply` uses `RateLimiter`; `careers_page` and `careers_posting` (`public.py:114,138`) have none.
- **Fix:** add a per-connection limit (e.g. `("careers.read", 120, 60)`) to both GETs using the same `RateLimiter(...).hit` code as `apply`, returning the same 429 envelope.
- **Done when:** a test hitting the list over the limit gets 429 (monkeypatch the limit low).

## Fixes (applied by the auditor at the owner's request, same session)
- All 7 items fixed on dev: 26f92e6 (C1.1.1, C1.1.6), 6a6d203 (C1.1.2), d7b0a46 (C1.1.3, C1.1.5), 0044639 (C1.1.4, C1.1.7).
- After the fixes: api 792 pass, web unit 777, recruitment + careers browser specs 5 pass, gen:api clean.
- A re-audit (round 2) by a big model is still due: scope `audit-1-r1..HEAD`.

## Notes (no action needed)
- Convert copies the candidate's current RTW check onto the employee (a new row) rather than re-pointing it; the convert audit event names the new check id. Fine against plan L984.
- Accepting an offer does not move the application to Offer Accepted on its own; the plan does not ask for it. Owner may decide later.
- `rota.published` notifications are not in `notifications/router.py` `_kinds` (pre-existing, outside this scope).
- Pushing to `dev` while a gate PR is open restarts its CI; batch checkpoint pushes until the gate PR is merged.
