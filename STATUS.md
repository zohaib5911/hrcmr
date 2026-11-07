# STATUS
Updated: 2026-11-07 20:16 Europe/London    Agent: Claude Code (Haiku 5.5, SMALL)    Branch: dev    Commit: f169827

State: BLOCKED — audit requested (AUDIT-2 round 2)

## Last completed
- C2.1.1 – C2.1.6 (all six AUDIT-2 round 1 fixes, changesneeded.md ticked):
  - C2.1.1 letter key-point names pseudonymised before AI — 499e2f3
  - C2.1.2 leave and rota e-mails honour the e-mail preference — 5a221ec
  - C2.1.3 learning.assigned notice on new course assignment — 2705617
  - C2.1.4 ai_available honours the platform switch — 52fc451
  - C2.1.5 org chart RTW chips only for company-wide RTW readers — 47f6b51
  - C2.1.6 small polish (certificate ref case, palette debounce, empty distribution card, confirm before AI replaces typed reminder) — 6379894, cd24ba5, f169827

## Current task
- AUDIT-2 round 2: big model runs audit.md "Re-audit" over the C2.1 fixes (commits 499e2f3..f169827), then writes round-2 findings into changesneeded.md.
  - [ ] re-audit round 2 (big model)
- Resume note: `bash .agent/next.sh` shows `AUDIT`. A big model runs audit.md §1 'Re-audit', then decides P0/P1 items (fix loop) or closes AUDIT-2 and starts Phase 15.

## Next tasks
- AUDIT-2 round 2 (big model). If it has no P0/P1: Phase 15 (T15.1 S!, T15.2 B, T15.3 B).

## Health
- CI on dev: last completed run on dev is green ("Phase 14: dashboard…", success). CI for the C2.1 pushes not checked.    CI on main: green (PR #22)
- Local checks run (small model, this round):
  - api: ruff check/format on changed files clean; mypy on changed modules clean
  - api tests: letters + redaction 209 pass; leave + rota + notifications 43 pass; learning + notifications + arch + openapi 22 pass; auth endpoints + letters + openapi 37 pass; organogram 7 pass; certificates 3 pass
  - web: lint and typecheck clean; prettier clean; unit 786 pass (56 files); shortcut-provider 40 pass
  - e2e: tests/e2e/dashboard.spec.ts 2 pass (28.1 s)
  - NOT run this round: full API suite (1036) and full browser suite (430). The re-audit should run them.
  - Mutation checks (fix removed → new test fails, then restored): C2.1.1, C2.1.2, C2.1.4.

## Issues / suggestions
- C2.1.1: only full names ("First Last") are pseudonymised. A single first or last name in a key point (e.g. "Ada has a meeting") is not replaced. Not in the fix spec; for the auditor to decide.
- C2.1.5: no new test that a company's own-only RTW reader gets no chips. The done-when was the existing organogram tests, which pass. A test would need a role with employee.rtw.read_own and organogram.level.read.

## Strategy / decisions taken
- C2.1.1: `generate` takes `names`; `_ai_paragraphs` loads every employee's full name (all statuses) for the company.
- C2.1.2: the in-app notice always goes; the e-mail only when mode is "immediate". The compliance reminder e-mail is unchanged.
- C2.1.3: one learning.assigned notice per person per assign request (not per course). Recipients use the overdue job's filter (active membership, active user, verified e-mail). Assignments are read back with RETURNING, so a repeat assign notifies nobody. Added to PERSONAL_KINDS.
- C2.1.4: a `_ai_key(auth)` helper in api/app/modules/auth/router.py used at the three build_me calls.
- C2.1.5: `Scope.ALL` comparison in both the org chart and its PDF.
- C2.1.6 reminder: ConfirmDialog only when the textarea differs from record.message_draft; otherwise the button runs directly.
- Audit IDs (C2.x.y) are kept out of code comments.
- check-rls is run through tests/db/test_cli.py (the bare CLI needs the full app env).

## Owner actions needed
- Review the 8 courses (unpublished). Sponsor-licence checklist item still an owner decision.
