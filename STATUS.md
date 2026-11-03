# STATUS
Updated: 2026-11-03 09:41, Europe/London    Agent: Codex    Branch: dev    Commit: 1219c75
State: IN PROGRESS

## Last completed
- T8.1 — verified leave defaults, tenant configuration API and settings UI
- F7.1–F7.7 — each completed in its own commit, pushed before T8.1

## Current task
- T8.2 — ledger and balance computation
  - [x] Confirm audit fixes/T8.1 CI green (41610450677, all twelve checks)
  - [ ] Pure entitlement/year/personal-pattern/calendar calculations and unit tests
  - [ ] Append-only tenant ledger, balance view and migration
  - [ ] Transactional grant/deduct/set and standard reconciliation service; DB tests
  - [ ] Affected lint/types/tests and completion
- Resume note: No T8.2 code yet. CI green for 0d3b86d covers all implementation before T8.2. Implement calculations first, then durable ledger and services; UI belongs to T8.4.

## Next tasks
- T8.2 — ledger and balance computation
- T8.3 — leave requests/conflicts/approvals
- T8.4 — leave workspaces and employee tab

## Health
- CI on dev: 41610450677 green (0d3b86d), all twelve checks. CI on main: not rechecked.
- Local checks run: affected leave/RBAC/auth 50 pass; schema/guards/contracts 21 pass; API ruff/format/mypy pass (235 files); web lint/types/generated contract pass; web unit 777 pass; leave browser/setup 6 pass. Audit fixes: access12, auth18 plus flow/migrations30, RBAC22 (189 routes/168 protected operations × six roles), exports8, RTW parity3 (225 combinations), error24 and affected browser63 pass.

## Issues / suggestions
- Remove cooldown exceptions once safe: brotli after 2026-11-05, certifi after 2026-11-06, pypdf after 2026-11-12.
- Dependabot #5 pending green CI; avoid unrelated changes.

## Strategy / decisions taken
- T8.1: seed existing companies in migration and new signups in their creation transaction. Store seed identity, source URL/date and original rule text. Annual 28 days includes bank holidays; carry-over 5 is a configurable company default, with statutory exceptions stated separately. Paid flags indicate paid provision subject to eligibility, not guaranteed full salary. Settings use real MM-DD dates (exclude Feb 29 for annual recurrence).
- Dossier: 8 GOV.UK publication/service links checked 2026-11-03; official HTTPS host only, no server fetch of edited URLs. Global reference links have platform-only writes, own content audit visibility and mandatory MFA; other platform permission policies deferred to Phase 17. Original checklist uses current official guide with source/date attribution.
- T7.5 readiness: profile needs legal/contact/sector/default address plus conditional sponsor-history details; company documents means at least one current clean upload (18 types are optional by applicability). Coverage valid = verified or expiring; recorded-check readiness is separate. No reportable changes is Not applicable; prompt-report replacements carry no invented deadline.
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
- docs/audits/phase7.md was absent from synced dev; queued findings in STATUS were implemented. Missing file contents/correct path requested; supply it if it contains additional acceptance details.
- Existing non-blocking setup: protect main and enable private vulnerability reporting.
