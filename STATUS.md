# STATUS
Updated: 2026-11-07 07:10, Europe/London    Agent: Claude Code (Haiku 5.5, SMALL)    Branch: dev    Commit: pending (feat T10.4)
State: IN PROGRESS

## Last completed
- T10.4 — "Draft with AI" template drafts: letter API (placeholders only, no AI call), .docx download, /documents sheet with copy/download/save.

## Current task
- none (T10.4 closed; next block is the Phase 10 gate, P10, per next.sh)

## Next tasks
- P10 — Phase 10 gate (full suite, screenshots, PR dev→main)
- AUDIT-1 is after P11 (not yet reached)

## Health
- CI on dev: mypy --strict fixed in 6e8b92f (T10.2 test); re-check on push
- CI on main: green (PR15)
- Local checks run this session: API policies 15, letters+auth 47, related worker/notifications/employees 34, reports 6, Playwright policies.spec 1; ruff/mypy (318 files) clean; web typecheck/lint, unit 777, gen:api:check clean.

## Issues / suggestions
- Rota publish inserts rota.published notifications but notifications/router.py _kinds omits that kind (not in T10.3/T10.4; left alone).
- require("document.file.write") accepts own-only scope (employees hold document.file.write_own); endpoints that are company-wide must check access.scope is Scope.ALL (policies and letters do).
- Named-people audience picker loads the first employee page only; large companies need server-side search for that picker.
- Never overlap DB pytest and Playwright (shared PostgreSQL role passwords).

## Strategy / decisions taken
- T10.4 .docx: built server-side from a minimal OOXML zip (zipfile + XML escape), no new dependency; the endpoint returns the file for the current text, so edits are kept.
- T10.4 AI label: `/auth/me` gains `ai_available` = server has ANTHROPIC_API_KEY AND the active company's ai_features_enabled. The draft endpoint itself makes no AI call yet; `source` is always "template" until T14.4.
- T10.4 letters are company-wide: require("document.file.write") plus a Scope.ALL check, so employees' own-only write is refused (403).
- T10.4 "Save as company document" uploads the .docx through the existing scanned upload path with category hr_template.
- T10.3 decisions (kept): overdue flip at 06:15 by policies_overdue_daily; remind includes overdue people; new-starter assignment on hire and by the daily job; /policies gated to policy.document.read.

## Owner actions needed
- None.
