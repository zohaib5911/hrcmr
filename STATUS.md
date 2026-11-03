# STATUS
Updated: 2026-11-03 07:38, Europe/London    Agent: Codex    Branch: dev    Commit: b6d99d1
State: BLOCKED — audit requested

## Last completed
- Phase 7 gate — PR #13 merged as f17ef67 after all 12 CI checks green (41595489940)

## Current task
- Phase 7 gate — complete; required owner audit
  - [x] T7.1–T7.6 implementation and affected checks
  - [x] Full API/web/browser gate; discovered failures fixed and affected checks pass
  - [x] 36 reviewed screenshots, 390/1280 px light/dark; mobile queue layout fixed
  - [x] Five-line phase summary, PR #13 and all-green CI merge; dev synced
  - [x] Stop for required owner audit
- Resume note: PR https://github.com/zohaib5911/hrcmr/pull/13 merged f17ef67. CI run 41595489940 all 12 checks green. Do not start Phase 8 until owner audit findings arrive; record them under Next tasks. Screenshots: docs/screenshots/phase-7. Migration SQL static-analysis findings fixed with equivalent literal SQL; affected migration/dossier/reporting 14 pass.

## Next tasks
- Owner high-level Phase 7 audit; implement supplied findings before Phase 8.

## Health
- CI on dev/PR: green (41595489940, b6d99d1). CI on main: post-merge run pending; merged change passed all PR checks.
- Local checks: API full 479 pass/two failures fixed/15 affected pass; API lint/format/mypy pass. Web 777, guards 32, lint/types/generated API pass. Browser full 398 pass/four stale shell assertions fixed/68 affected pass; final hub/screenshots 6 pass. Migration/dossier/reporting 14 pass after CI fix.

## Issues / suggestions
- Remove cooldown exceptions once safe: brotli after 2026-11-05, certifi after 2026-11-06, pypdf after 2026-11-12.
- Dependabot #5 pending green CI; avoid unrelated changes.

## Strategy / decisions taken
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
- Run the required Phase 7 audit with a high-level model and supply findings under Next tasks.
- Existing non-blocking setup: protect main and enable private vulnerability reporting.
