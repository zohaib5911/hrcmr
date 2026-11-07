# STATUS
Updated: 2026-11-07 17:57 Europe/London    Agent: Claude Code (Haiku 5.5, SMALL)    Branch: dev    Commit: 691da5b

State: BLOCKED — audit requested (AUDIT-2)

## Last completed
- P14 — Phase 14 gate: PR #22 merged to main (all 13 checks green). API suite 1036 pass; web lint, typecheck, unit 786 pass; browser 430 pass (176 screenshot-only skipped); screenshots docs/screenshots/phase-14 (12 files). PROGRESS.md has the summary.
- T14.5 — AI in letter drafting (Claude paragraphs, template fallback) and reminder wording (Draft with AI button, document type and days only). 16 DB tests pass.
- T14.4 — AI server layer; fuzz test 202 pass.

## Current task
- AUDIT-2 — AUDIT STOP, covers T12.1 → P14 (and T14.4 by the big model). Not done by a small model.
  - [ ] big model runs audit.md on T12.1 → P14 (incl. T14.4)
  - [ ] writes fixes into changesneeded.md
- Resume note: a BIG model (Opus / Solo 6.1) runs audit.md fully, then writes findings to changesneeded.md and sets STATUS. Small models fix audit items next. The T14.4 redaction and AI wiring should be audited together with T14.5 (both touch app/ai and the reminder router).

## Next tasks
- After AUDIT-2 passes (no P0/P1): next phase is Phase 15 (T15.1 S!, then T15.2 B, T15.3 B).

## Health
- CI on dev: green (PR #22 all checks pass; merged to main)    CI on main: green after PR #22
- Local checks run: API full suite 1036 pass; web lint, typecheck, unit 786 pass; browser 430 pass; dashboard spec re-run 2 pass after the checklist icon change.

## Issues / suggestions
- AI wording button and AI letter path are covered by API tests only, not browser tests (the e2e server has no AI key). The auditor should look at the browser path with an AI key set.
- Reminder drawer: clicking Draft with AI replaces the textarea, including any text HR has typed. Consider a confirm step.
- Dashboard checklist: marks now use Lucide icons (Check, Circle) instead of text glyphs; a dashboard unit test for them does not exist.
- Eight launch courses (api/seed/courses) are unpublished; owner must review.
- Dashboard "sponsor licence" checklist item (plan 8.2) left out; owner decision.
- Notifications digest sent 07:00 UTC for every company.
- Learning report: people managers do not see their team's report yet.
- Ask Mady assistant panel (T14.4 part) is deferred by the owner; not built.

## Strategy / decisions taken
- T14.5: AI output is checked with find_restricted; a hit, an empty answer or any AI error falls back to the template. The letter draft still works.
- T14.5: any AI error (provider, refusal, rate limit) falls back silently to the template; the letter sheet shows a note when AI was on but the template was used.
- T14.5: reminder AI prompt gets only the document label and the threshold days; never the name or a date.
- T14.5: reminder wording is requested by a button in the drawer, not on open, so viewing a reminder does not use the 30/hour AI limit.
- P14: sponsor-licence item left out of the dashboard checklist (no company-level record to check).

## Owner actions needed
- Review the eight launch courses before publishing them (api/seed/courses). See PROGRESS.md.
- Decide how seed courses reach production.
- Decide on the sponsor-licence checklist item (plan 8.2).
- Phase 23: add a Cloudflare rate-limit rule for /careers/* (the API cannot tell visitors apart on server-rendered pages).
