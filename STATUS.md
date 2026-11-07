# STATUS
Updated: 2026-11-07 09:10, Europe/London    Agent: Claude Code (Haiku 5.5, SMALL)    Branch: dev    Commit: pending (feat T11.1)
State: IN PROGRESS

## Last completed
- T11.1 — Requisitions: models and migration 0033 for all six recruitment tables; requisition CRUD, approval-gated status changes (stamped), summary; /recruitment page with KPIs, tabs and requisition sheet.

## Current task
- none (T11.1 closed). Next block per next.sh is T11.2 (postings).

## Next tasks
- T11.2 — Postings (full sheet, SOC placeholder, JD template, statuses, public link copy)
- T11.3, T11.4, T11.5, T11.6, P11 gate, AUDIT-1 after P11

## Health
- CI on dev: PR #17 (dev→main, Phase 10 gate) — checks green except end-to-end at last check; see PR.
- Local checks run this session: requisitions/migrations/RLS/guards 64 pass; web unit 777; typecheck/lint clean; recruitment.spec pass; gen:api:check clean; full API 690 and full web e2e 423 at the gate.

## Issues / suggestions
- Postings, candidates and applications tabs show counts and a placeholder until T11.2–T11.4; the Applications pipeline bar (8 stages) lands with applications in T11.4.
- Rota publish inserts rota.published notifications but notifications/router.py _kinds omits that kind (not in T11.x; left alone).
- Requisition budgets are shown in GBP via Intl formatting; there is no currency field yet.
- Never overlap DB pytest and Playwright (shared PostgreSQL role passwords).

## Strategy / decisions taken
- The recruitment migration (0033) is hand-written from the 6.8 spec; the migration tests were updated with the six table names; RLS and updated_at triggers are applied to each table.
- Requisition status rules: cancelled is terminal; open needs recruitment.requisition.approve (checked in the handler, so a recruiter gets 403); each approval re-stamps approved_at/approved_by.
- Cancel is a separate confirmed action in the sheet (the status select offers Draft, Open, On hold, Filled).
- Requisitions are company-wide: requests with only own-scope access are refused (same as policies).
- Postings and the rest are tables only for now; summary counts read them.

## Owner actions needed
- None.
