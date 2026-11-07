# STATUS
Updated: 2026-11-07, Europe/London    Agent: Claude Code (Opus 5.5, BIG)    Branch: dev    Commit: a49307d
State: IN PROGRESS — AUDIT-1 round 1 (scope f37f781..a49307d); PR #18 waiting on e2e before merge

## Last completed
- T11.6 — Public careers: list and posting endpoints (open external only, listed fields), apply endpoint (consent, Turnstile, rate limit, candidate and application created, confirmation and recruiter notice), careers pages.

## Current task
- AUDIT-1 round 1 (audit.md): run checks, review T10.3–T11.6, write changesneeded.md

## Next tasks
- P11 — Phase 11 gate: full API suite once, full web e2e once, phase-11 screenshots (390 and 1280, light and dark; recruitment, candidate, application, careers), 5-line summary, PR dev to main, green CI, merge
- AUDIT-1 — audit stop after P11: a big model runs audit.md (small models stop with "AUDIT NEEDED FIRST")

## Health
- CI on dev: last PR (#17, Phase 10) merged on main as 34f7aee. dev has T11.1–T11.6 checkpoints, not yet through a PR.
- Local checks run this session: careers 3 + careers.spec 2; email, notifications, applications, recruitment, candidates, convert, RBAC, guards, data-model doc 36+ pass; mypy (337 files) and ruff clean; web unit 777, typecheck, lint, gen:api clean.

## Issues / suggestions
- NOT DONE (T11.6 step 2): the optional CV upload. It needs a public upload path through the files service and ClamAV; the apply endpoint takes no file yet. Add it with the scan path in a later step or ask for a decision.
- NOT DONE (T11.6 page): the company logo. No logo field is exposed on the public pages yet.
- Turnstile: the test environment has no secret, so the verifier accepts any present token. The rejection path for a bad token is covered by code, not by a test. A test with a Turnstile secret needs a fake verifier.
- The public careers pages send the placeholder token when no Turnstile site key is set; with a secret configured on the server, the server rejects it. Production must set both keys.
- Accepting an offer does not move the application on its own (decide before the P11 audit).
- The candidate profile's header Convert button is still disabled; conversion lives on the application page.
- Rota publish inserts rota.published notifications but notifications/router.py _kinds omits that kind (left alone).
- Never overlap DB pytest and Playwright (shared PostgreSQL role passwords).

## Strategy / decisions taken
- The public guard allowlist now includes /api/v1/public/careers and /api/v1/public/postings (reviewed: each POST has Turnstile and a rate limit; each response lists its fields, tested).
- Apply: a repeat application for the same person and posting returns the same 202 and does not create a second one, so the form does not reveal who has applied.
- Apply: the candidate is found by email (case-insensitive, not archived) or created with source "Careers page".
- The applicant's confirmation is an email; recruiters get an in-app notification (recruitment.application_received) for roles with recruitment.application.read.
- Apply records an audit event with actor type system and the visitor's IP (no user).
- Closed or internal postings return 404 on both the detail page and apply.

## Owner actions needed
- None for the code. For production: set the Turnstile site key (web) and secret (API) together.
