# STATUS
Updated: 2026-11-03 02:56    Agent: Codex    Branch: dev    Commit: 97fd20b
State: IN PROGRESS

## Last completed
- T7.4 — Reviewed reminders, daily reconciliation, register/history and own received messages

## Current task
- T7.5 — Compliance hub and dossier
  - [ ] Requirements/patterns and affected baseline checks
  - [ ] Scoped hub overview, urgency/coverage/readiness/expiry and audit CSV APIs/tests
  - [ ] Official dossier links, editable platform store and original RTW checklist PDF/tests
  - [ ] Hub/dossier UI matching existing components and static checks
  - [ ] Affected browser verification
- Resume note: Start with company profile/key personnel/doc readiness, RTW status view and audit export patterns. Implement T7.5 only; preserve existing employee/change/reminder modules.

## Next tasks
- T7.5, T7.6; Phase 7 gate then BLOCKED — audit requested

## Health
- CI on dev: green 41514098397 (Phase 6); Phase 7 not yet run in CI. CI on main: green 41516923634.
- Local checks: T7.3 calculator 12, reporting/holiday API 13 and migration/doc 7 pass; reporting/setup browser 3 and holiday/setup browser 14 pass. T7.2 migration/doc 7, sponsor API 14, sponsor/setup browser 2 and adjacent RTW/setup 2 pass. All affected lint/types/generated API/production builds pass. Full suite/screenshots next at Phase 7 gate.


## Issues / suggestions
- Remove cooldown exceptions once safe: brotli after 2026-11-05, certifi after 2026-11-06, pypdf after 2026-11-12.
- Dependabot #5 pending green CI; avoid unrelated changes.

## Strategy / decisions taken
- Reviewed sends require a linked active verified account and use that account email; message is readable in own My Documents. The closest outstanding threshold controls Due now, including source snooze; sending it cancels older unsent thresholds as covered. Own-profile contact permission cannot reach HR create/lifecycle/48h endpoints.
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
