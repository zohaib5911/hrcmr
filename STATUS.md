# STATUS
Updated: 2026-11-03 09:03, Europe/London    Agent: Codex    Branch: dev    Commit: 3c531a4
State: IN PROGRESS

## Last completed
- F7.7 — refresh progress header and complete T7.4–T7.6 implementation/verification entries

## Current task
- T8.1 — leave types and settings
  - [x] Verify twelve seed rules against GOV.UK; baseline settings/RBAC checks
  - [x] Models, frozen migration/backfill and signup seeds
  - [x] Scoped API/settings validation, audit and regression tests
  - [x] Leave settings UI, CRUD sheets and navigation
  - [ ] Affected browser/API/static checks and task completion
- Resume note: First production browser run reached settings; test selector also matched the field clear button. Narrowed year-start label to exact match. Rerun leave-settings spec next; API50/schema21/web777 and static checks pass.

## Next tasks

F7.1 Step-up on role change, admin/HR-admin invite, and two-step policy change (+ tests)   [high]
(Ongoing, not a task: move shared helpers into employees/access.py and core/dates.py only when a task already touches that code.)
 implement supplied findings before Phase 8.







## Health
- CI on dev: last Phase 7 PR green; no dev push workflow. CI on main: previously pending, not rechecked.
- Local checks run: affected browser/setup 63 pass; F7.1–F7.6 API/static checks pass; progress entries reviewed

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
- Supply missing docs/audits/phase7.md contents or correct path (requested).
- Existing non-blocking setup: protect main and enable private vulnerability reporting.
