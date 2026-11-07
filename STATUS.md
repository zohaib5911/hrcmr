# STATUS
Updated: 2026-11-08 Europe/London    Agent: Claude Code (Haiku 5.5, SMALL)    Branch: dev    Commit: pending (T15.5 close)
State: IN PROGRESS

## Last completed
- T15.5 — CV match: POST /soc/resume-match (PDF/DOCX up to 10 MB; contact details stripped before sending; Claude score, evidence quotes checked against the CV, gaps, suggestions; AI off = 409). Tests: 43 pure + 2 DB.
- T15.4 — Search and match API: GET /soc/search, POST /soc/match (Claude re-rank, low_confidence < 60, rules engine on top 3, 409 until rules published). Tests: 17 pure + 13 DB.

## Current task
- T15.6 — Checker UI, "Find code" embeds, PDF report (S). Not started. Read micro_plan T15.6 block and the recipes it cites (R4 PDF, R6 done-when) before starting.

## Next tasks
- T15.6 (S), T15.7 (daily rules watcher, super-admin diff/publish/rollback)

## Health
- CI on dev: not run since T15.1 (Phase 15 gate PR runs it)    CI on main: green (last PR #22)
- Last local checks: ruff check + format, mypy (app/modules/soc, app/main.py) clean. Non-DB API tests: 624 pass. SOC DB tests (match, cv, import, rules import): pass. Pre-commit hooks passed on 21e5d8b (client schema regenerated).

## Issues / suggestions
- OpenAPI component names must be unique. Pydantic qualifies a clashing name, which drops the original from web/lib/api/schema.ts. SOC models use the Soc prefix (SocCandidateOut, SocCvMatchOut, ...). After any new endpoint run `pnpm gen:api` in web and check that no names disappear.
- Body limits: every upload route must be in the limits table in api/app/main.py. The SOC CV route is there (PROOF_LIMIT). tests/test_body_limits.py enforces it.
- Architecture rule: app code may not use any `.text` attribute (it is taken for raw SQL text()). Use itertext() or other names (the stripping result field is `cleaned`).
- Test harness: the rig's `two_companies` runs `truncate users, companies cascade`, which also truncates rules_versions (rows refer to users). Tests that need published rules publish them after the rig (tests/db/test_soc_match.py).
- Test harness: temporary_database() re-provisions app_owner/app_user; do not run DB suites in parallel.
- pypdf is now a runtime dependency (moved from dev). types-defusedxml is a dev stub.
- CV stripping is pattern based. It does not remove names (the plan does not ask for it), and a street address with no street type word is not caught. The redaction layer in app/ai still runs on the request body.
- CV match does not suggest other SOC codes ("Code 3544 fits better"). That would need the search retrieval on the job title; not done in T15.5.
- The CV match response has no rules version (the disclaimer in T15.6 must show rules version and date from the checker).
- PROGRESS.md ends with an old unchecked Phase 15 list (T15.2–T15.7). The [x] lines above it are the record.
- AI ranking gating: ai_ready only. ai.ask.use is in the matrix but no code checks it (same as letters).
- Job descriptions with personal data are redacted before the call, not refused (only a body with restricted data left after redaction gets AI_REFUSED).
- Pre-existing: OpenAPI already had five qualified AddressOut names (app__modules__companies__..., app__modules__employees__personal_schemas__...). Not from SOC.

## Strategy / decisions taken
- (T15.4) Search needs soc.check.read; match needs soc.check.run (auditors can search, not match). Retrieval: 30 hits per leg (trigram, FTS, vector on index titles, vector on unit groups), fused by reciprocal rank (k = 60), top 10. Re-rank: fast=False (ANTHROPIC_MODEL_MAIN), 1,500 max tokens, strict JSON (unique candidate codes). Any unusable reply, AI error or rate limit: search order with notice, ai_ranked false.
- (T15.4) The plan's "JSON schema" is enforced by pydantic on the reply, not by an API schema feature.
- (T15.4) Response `checks` = engine CheckResult. Decimal values serialise as strings (pydantic v2 default).
- (T15.4) The embedder loads on first use (fastembed in a thread) and is kept on app.state.soc_embedder; tests set a fake there. A failure gives 503 SOC_SEARCH_UNAVAILABLE.
- (T15.5) Endpoint order: AI on (409), size (10 MB, 413), empty (422), PDF or DOCX by name (422), magic bytes (415), virus scan through app.state.files.scanner (422 infected, 503 scan down), readable text (422), SOC code exists (404), Claude (502 if the reply is unusable: no fallback, the feature is AI-only). The CV is held in memory only; nothing is stored.
- (T15.5) Quotes: every evidence quote must appear in the cleaned CV (case and spacing folded). Quotes that do not are dropped, not shown.
- (T15.5) Phone rule: a leading + with 8-13 digits, or a UK national number of 10-11 digits starting 0. A 12-digit CV date range is not treated as a phone number.
- (T15.5) Street rule: a house number, up to three capitalised words, then a street type on the same line. green, row and view are left out.

## Owner actions needed
- None for T15.5. Reminder: the AI features need ANTHROPIC_API_KEY (the CV match is hidden without it).
