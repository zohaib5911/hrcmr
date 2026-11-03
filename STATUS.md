# STATUS
Updated: 2026-11-03 02:15    Agent: Codex    Branch: dev    Commit: a6bf9bc
State: IN PROGRESS

## Last completed
- T7.3 — Working-day calculator, worker/org change records, reporting lifecycle and UI

## Current task
- T7.4 — Reminders engine and register
  - [x] Reminder requirements and email/notification/job patterns reviewed; baseline lint/types and 11 email/worker tests pass; queue-test minute-boundary flake fixed
  - [x] Threshold/reminder model and migration 0018; 14 migration/doc/change-regression checks pass
  - [x] Threshold/source hooks and daily job, cancellation/restore/snooze and derived-calendar refresh; 34 reminder/source/worker checks pass, final engine 5 pass
  - [ ] Scoped register/review/edit/snooze/send API with audited who/when and in-app/email delivery
  - [ ] Reminders page/register/history/review drawer (template until Phase 14)
  - [ ] Affected API/browser verification
- Resume note: Reminder engine/source hooks/daily job verified: 34 reminder+RTW+sponsor+worker checks and final 5 engine checks pass, ruff/mypy clean. Next scoped reminder schemas/router + transactional reviewed send (Reminder, Notification and encrypted EmailOutbox in one transaction), received-reminder own view, then register/drawer UI. Current engine creates 3 thresholds per sponsor/RTW version, no automatic employee sends, dedupes admin notices, resumes due after 7-day snooze, refreshes only unreported calculated deadlines as owner. RTW 21-day Expiring + due30 scenario passes. APIs/UI not started.


## Next tasks
- T7.4, T7.5, T7.6; Phase 7 gate then BLOCKED — audit requested

## Health
- CI on dev: green 41514098397 (Phase 6); T7.1 not yet run in CI. CI on main: green 41516923634.
- Local checks: T7.3 calculator 12, reporting/holiday API 13 and migration/doc 7 pass; reporting/setup browser 3 and holiday/setup browser 14 pass. T7.2 migration/doc 7, sponsor API 14, sponsor/setup browser 2 and adjacent RTW/setup 2 pass. All affected lint/types/generated API/production builds pass. Full suite/screenshots next at Phase 7 gate.


## Issues / suggestions
- Remove cooldown exceptions once safe: brotli after 2026-11-05, certifi after 2026-11-06, pypdf after 2026-11-12.
- Dependabot #5 pending green CI; avoid unrelated changes.

## Strategy / decisions taken
- T7.4: human review/send only; email outbox, notification and sent/audit state commit together, generic existing reminder_nudge email. Add RTW target to reminder schema for explicit phase scenario. Daily owner job may refresh unreported derived deadline/calendar fields while entered snapshots and reported records stay immutable.
- T7.3 verified sources: GOV.UK sponsor Part 3 (C1.13/C2.3), glossary and bank-holidays page, checked 2026-11-03. AO/Key Contact replacements get prompt-report status, other org changes standard 20 working days. Regional calendar data must cover the requested dates; do not silently ignore missing bank holidays.
- T7.2 exposes the document section of Sponsor compliance now so the feature is usable; T7.6 adds its PDF/CoC integration and notifications.
- Sponsor metadata uses employee.rtw.read/write (own-read allowed, own-file uploads alone cannot change compliance metadata; auditors can read); register uses compliance.overview.read. Renewal target/notes never change expiry. Sponsor references/CoS masked, sponsored salary permission scoped.
- RTW priority: not recorded, failed/pending, expired, missing/unclean evidence, expiring (<=60 days), verified; dates use company timezone. Share codes never returned/exported in full. Historical corrections stay historical; Company Admin can correct, HR Admin can record only. Candidate validation/routes arrive in Phase 11.
- Browser file upload uses fixtures because e2e API has no storage config; real upload/scanning/binding/download tests use local services. Mobile checks wait for responsive cards after resize.
- Employee linking requires rbac.role.assign; hierarchy CRUD deferred to T12.1. PDF HTML escaped, external resources blocked, sensitive numbers masked, salary permission scoped.
- AI hidden without ANTHROPIC_API_KEY; Ask Mady deferred.

## Owner actions needed
- None blocking. Protect main and enable private vulnerability reporting.
