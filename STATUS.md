# STATUS
Updated: 2026-11-07 17:07 Europe/London    Agent: Claude Code (Haiku 5.5, SMALL)    Branch: dev    Commit: 7fd75f4

State: IN PROGRESS

## Last completed
- T14.4 — AI server layer (app/integrations/anthropic.py, app/ai/redaction.py, app/ai/service.py, ai_interactions 0039); fuzz test 202 pass (cd2ff53).
- T14.3, T14.2, T14.1 — search, notifications, dashboard (see PROGRESS.md).

## Current task
- T14.5 — Wire AI into letter drafting and reminder wording (S)
  - [ ] step 1: /ai/letters/draft uses Claude when available (source "ai"), else template; only type, tone, key points sent
  - [ ] step 2: reminder review drawer gets AI-worded message when available, else template
  - [ ] tests: no-key path works; outgoing payload has no names/identifiers (assert_clean / find_restricted)
  - [ ] tick T14.5 in micro_plan and PROGRESS
- Resume note: start at api/app/ai/letters.py (create_draft) and api/app/modules/compliance/reminder_router.py. Verify with: cd api && uv run pytest -q tests/db/test_letters.py tests/db/test_reminders.py tests/test_ai_redaction.py

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
