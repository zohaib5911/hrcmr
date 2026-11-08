# changesneeded.md — audit AUDIT-2 round 2 (2026-11-08, Claude Opus 5.5)
## Result: PASS
Scope: audit-2-r1 (a87d511)..fcfa2b5 (fix commits 499e2f3..f169827 for C2.1.1 to C2.1.6, plus regression of touched areas)
Tests at audit: api 1043/0/0 (ruff, format, mypy clean; check-rls via tests/db/test_cli.py 4/0), web unit 786/0, web lint/types/build/gen:api clean, e2e 430/0 (176 screenshot-only skipped), CI green on last dev PR run (#22; C2.1 pushes run CI at the Phase 15 gate PR)
Counts: 0 P0 / 0 P1 / 0 P2. AUDIT-2 closed; Phase 15 next.

No open items.

## Notes (no action needed)
- Round 1 items C2.1.1 to C2.1.6 re-checked in code: the fixes match the specs, the new tests assert behaviour (wire body, outbox rows, notice counts, `/auth/me`), and there are no skips or weakened assertions in the diff.
- C2.1.1: only full names ("First Last") are labelled. A lone first name in a key point still goes to the AI. That's acceptable: a first name alone is a weak identifier, and matching it would mangle ordinary words ("May", "Will"). Revisit if the owner wants stricter handling.
- C2.1.2: people on "daily" get leave and rota notices in the digest. `send_digests` picks up every undigested notice, whatever its kind.
- C2.1.5: there is no dedicated test for an own-only RTW reader, because no current role has both `employee.rtw.read_own` and `organogram.level.read`. The `Scope.ALL` comparison is right.
- C2.1.6: after an AI draft, a second "Draft with AI" asks again before replacing it. That's harmless (the text is unsaved).
