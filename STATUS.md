# STATUS
Updated: 2026-11-07 17:14 Europe/London    Agent: Claude Code (Haiku 5.5, SMALL)    Branch: dev    Commit: cce2539

State: IN PROGRESS

## Last completed
- T14.5 — AI in letter drafting (Claude paragraphs, template fallback) and reminder wording (Draft with AI button, document type and days only); API 16 DB tests pass, browser 8 pass (PROGRESS.md).
- T14.4 — AI server layer (app/integrations/anthropic.py, app/ai/redaction.py, app/ai/service.py, ai_interactions 0039); fuzz test 202 pass (cd2ff53).
- T14.3, T14.2, T14.1 — search, notifications, dashboard (see PROGRESS.md).

## Current task
- P14 — Phase 14 gate (S): full API suite, full web checks and e2e, screenshots 390+1280 light+dark, PROGRESS summary, PR dev->main, merge when green. Then AUDIT-2 stop (big model).
  - [ ] full API suite (cd api && uv run pytest -q)
  - [ ] web lint, typecheck, unit, e2e (full)
  - [ ] fuzz test tests/test_ai_redaction.py (202)
  - [ ] screenshots phase-14
  - [ ] PROGRESS phase summary
  - [ ] PR dev->main, CI green, merge
- Resume note: run the full API suite first (no Playwright at the same time), then web e2e.

## Next tasks
- P14 (S): phase gate (R7 + T14.4 fuzz test), then AUDIT-2 (big model stop).

## Health
- CI on dev: not run for T14.x yet (dev has commits after PR #21)    CI on main: green
- Local checks run: T14.4 — fuzz 202 pass (21:35). T14.5 — not run yet.

## Issues / suggestions
- Eight launch courses (api/seed/courses) are unpublished; owner must review. See PROGRESS.md.
- Dashboard "sponsor licence" checklist item (plan 8.2) left out; owner decision.
- Notifications digest sent 07:00 UTC for every company.
- Learning report: people managers do not see their team's report yet.

## Strategy / decisions taken
- T14.5: AI output is restricted-checked with find_restricted; a hit or any AI error falls back to the template (the draft still works).
- T14.5: AI reminder wording is requested by a button in the drawer (not on open), so viewing a reminder does not use the 30/hour AI limit.
- T14.5: reminder AI prompt gets only the document label and the threshold days; no name, no date.

## Owner actions needed
- Review the eight launch courses before publishing them (api/seed/courses). See PROGRESS.md.
- Decide how seed courses reach production.
- Decide on the sponsor-licence checklist item (plan 8.2).
