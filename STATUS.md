# STATUS
Updated: 2026-11-08 Europe/London    Agent: Claude Code (Haiku 5.5, SMALL)    Branch: dev    Commit: d381fed
State: IN PROGRESS

## Last completed
- T15.4 — Search and match API: GET /soc/search (trigram + full-text + vector, RRF, top 10) and POST /soc/match (Claude re-rank with strict JSON, confidence and low_confidence < 60, rules engine on top 3; search order with confidence null when AI is off). Tests: 17 pure + 13 DB.
- T15.3 — Rules engine (engine.py, loader.py), 27 golden tests + 1 DB test.

## Current task
- none (T15.4 done; next block is T15.5, S!)

## Next tasks
- T15.5 (S!) CV match, then T15.6 (S) checker UI

## Health
- CI on dev: not run since T15.1 (Phase 15 gate PR runs it)    CI on main: green (last PR #22)
- Local checks run this session: ruff check + format, mypy (app/modules/soc, app/main.py) clean; pytest tests/test_soc_matching.py, tests/db/test_soc_match.py, tests/db/test_soc_import.py, tests/db/test_soc_rules_import.py, tests/test_soc_rules_engine.py, tests/test_soc_rules_source.py, tests/test_soc_source.py, tests/test_openapi.py, tests/test_architecture.py: 112 pass (before the final rename, 43 pass after it). Pre-commit hooks passed on d381fed (api client types regenerated).

## Issues / suggestions
- OpenAPI component names must be unique. Pydantic qualifies a clashing name (e.g. app__modules__...__CandidateOut) and the original name disappears from web/lib/api/schema.ts. My first draft clashed with CandidateOut (recruitment), CheckIn (rtw) and SearchOut (search). The SOC models are now prefixed Soc*. Any new model should use a unique name; check the schema diff for removed names.
- Test harness: the rig's `two_companies` runs `truncate users, companies cascade`, which also truncates rules_versions (its rows refer to users). Tests that need published rules must publish them after the rig (tests/db/test_soc_match.py does this in an autouse fixture).
- Test harness (from T15.1): temporary_database() re-provisions the shared app_owner/app_user roles; do not run DB suites in parallel.
- PROGRESS.md ends with an old unchecked Phase 15 list (T15.2–T15.7 lines after the [x] lines). The [x] lines above it are the record; the old list is stale.
- The first request that needs a query embedding loads fastembed in a thread (first run downloads about 70 MB). Until the model is loaded, /soc/search and /soc/match take longer once per process. Consider preloading at startup in T15.6 or later.
- AI ranking is gated by ai_ready (key, platform and company switches), as in letters. The matrix has ai.ask.use, but no code checks it yet. Owner to decide whether SOC AI ranking should need it (Recruiter has soc.check.run but not ai.ask.use).
- Job descriptions with personal data (an e-mail, for example) are redacted before the call, not refused. Only a body that still holds restricted data after redaction gets AI_REFUSED (422). Owner may prefer a visible warning instead.
- Pre-existing: the OpenAPI schema already had five qualified AddressOut names (app__modules__companies__..., app__modules__employees__personal_schemas__...). Not from SOC; worth a rename later.
- T15.4 search quality is unmeasured (plan: measure in T15.4/T15.6). The fixture-based tests only prove the wiring.

## Strategy / decisions taken
- (T15.4) Permissions: GET /soc/search needs soc.check.read (reference data); POST /soc/match needs soc.check.run (it runs the rules and may call AI). Auditors can search, not match.
- (T15.4) Retrieval: 30 hits per leg (trigram on index titles, English full-text on index titles, vector on index titles, vector on unit groups), merged by reciprocal rank fusion (k = 60), top 10 unit groups. The vector query is the normalised job title plus the first 1,000 characters of the description; the lexical legs use the title only.
- (T15.4) Re-rank: fast=False (ANTHROPIC_MODEL_MAIN), max 1,500 tokens. The reply must be JSON with unique candidate codes (at least one). Anything else returns the search order, with notice "The AI reply could not be read...". AI_FAILED, RATE_LIMITED and AI_UNAVAILABLE fall back to search order with notice "Not AI-ranked...". The plan's "JSON schema" is enforced by pydantic on the reply, not by an API schema feature.
- (T15.4) Match input: a `check` block (weekly hours, offered salary and per, work nation, optional CoS date (default today, Europe/London), applicant flags, optional pay-scale role and administration). The rules engine runs on the top 3 codes of the final ranking.
- (T15.4) The match answers 409 RULES_NOT_PUBLISHED before any AI call when no rules version is live (as T15.3 note asked).
- (T15.4) Response: `checks` is the engine's CheckResult (dataclasses serialised by pydantic). Decimal values come out as strings (pydantic v2 default), so T15.6 must parse them.
- (T15.4) Search needs at least 2 characters after normalising; under that it returns no results. A title with no letters or digits (e.g. "!!") is refused with 422 INVALID_JOB_TITLE.

## Owner actions needed
- None for T15.4. The SOC tables and the rules v1 must be loaded and published as before (see the earlier handover in git history: data/import_soc.py and data/import_rules.py --publish).
