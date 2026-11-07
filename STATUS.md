# STATUS
Updated: 2026-11-07 10:30, Europe/London    Agent: Claude Code (Haiku 5.5, SMALL)    Branch: dev    Commit: pending (feat T11.2)
State: IN PROGRESS

## Last completed
- T11.2 — Postings: CRUD, Draft/Open/Closed, open-requisition rule, unique slugs, public link only while external and open, postings tab with sheet and JD guide.

## Current task
- none (T11.2 closed). Next block per next.sh is T11.3 (candidates).

## Next tasks
- T11.3 — Candidates
- T11.4 — Applications, interviews, offers (pipeline bar lands here)
- T11.5 (S!) convert to employee; T11.6 (S!) public careers pages and apply form; P11 gate; AUDIT-1

## Health
- CI on dev: PR #17 (Phase 10 gate) merged as 34f7aee after all checks green on f993540.
- Local checks run this session: postings + recruitment DB 7 pass; route/guard/data-model 32 pass; web unit 777; typecheck/lint/gen:api clean; ruff and mypy (325 files) clean.

## Issues / suggestions
- Public link uses the company slug and the web origin from settings; the careers route itself is built in T11.6, so the link is not yet reachable.
- A cancelled or on-hold requisition does not close its open postings automatically (not in the spec). Consider closing them when the requisition leaves Open, decided with T11.4.
- No browser test for postings yet; add one with T11.6 (public careers), which needs the link to resolve.
- The SOC "Find code" button is disabled until T15.6.
- Rota publish inserts rota.published notifications but notifications/router.py _kinds omits that kind (left alone).
- Never overlap DB pytest and Playwright (shared PostgreSQL role passwords).

## Strategy / decisions taken
- Posting slug: the title, lower-cased and hyphenated, numbered -2, -3 when taken in the company.
- Opening a posting (create or status change) requires its requisition to be open; a foreign requisition gets the same refusal as a missing one.
- Public link is computed, not stored: external + open only; closing removes it immediately.
- The JD template and the "Writing it safely" guide are original wording written for this app; the template keeps [placeholders].
- Status changes that go backwards (open to draft) are refused with 409.

## Owner actions needed
- None.
