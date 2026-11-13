# STATUS (snapshot — live state is `bash .agent/bus.sh status`)
Updated: 2026-11-13 UTC    Agent: claude (opus, BIG)    Branch: task/AUDIT-4
State: HANDED OVER — audit fixes ready (AUDIT-4 round 2: 0 P0 / 1 P1 / 3 P2).

## Last completed
- Re-audited all 21 round-1 fixes (PRs #86–#106) against code, tests and GOV.UK/HMRC figures; all hold.
- New P1 C4.2.1: server-rendered register pages share one 120/min read-limit bucket (web server IP). Three P2 items. AUDIT-4 remains open.

## Verification
- API 1377/0/0, Ruff/format/mypy pass; check-rls via tests/db/test_cli.py.
- Web lint/typecheck, unit 1466/0, gen:api:check, build pass; e2e 488 passed/0 failed/328 skipped.

