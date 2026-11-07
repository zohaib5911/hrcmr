# STATUS
Updated: 2026-11-07 19:57 Europe/London    Agent: Claude Code (Opus 5.5, BIG)    Branch: dev    Commit: bff57ab
State: HANDED OVER — audit fixes ready

## Last completed
- AUDIT-2 round 1 — 0 P0 / 3 P1 / 3 P2; findings in changesneeded.md. All runs green: api 1036, web unit 786, e2e 430 (176 skipped), CI green.

## Current task
- changesneeded.md C2.1.1 → C2.1.6 (small model, in order)
  - [ ] C2.1.1 P1 letter key points: pseudonymise company employee names before AI
  - [ ] C2.1.2 P1 leave/rota e-mails honour e-mail preference
  - [ ] C2.1.3 P1 course-assigned notice
  - [ ] C2.1.4 P2 ai_available honours platform switch
  - [ ] C2.1.5 P2 org chart RTW chips only for company-wide RTW readers
  - [ ] C2.1.6 P2 small polish
- Resume note: each item names files, fix and test. Tick each (### [x]) with its fix commit. Then stop with BLOCKED — re-audit requested (AUDIT-2 round 2).

## Next tasks
- Re-audit AUDIT-2 round 2 (big model), then Phase 15 (T15.1 S!, T15.2 B, T15.3 B).

## Health
- CI on dev: green    CI on main: green (PR #22)
- Local checks run: api ruff/format/mypy/pytest 1036 pass; web lint/typecheck/unit 786/gen:api/build pass; e2e 430 pass, 176 skipped.

## Issues / suggestions
- Same as changesneeded.md Notes. Owner: review the eight launch courses before publishing.

## Strategy / decisions taken
- check-rls is run through tests/db/test_cli.py (the bare CLI needs the full app env).

## Owner actions needed
- Review the 8 courses (unpublished). Sponsor-licence checklist item still an owner decision.
