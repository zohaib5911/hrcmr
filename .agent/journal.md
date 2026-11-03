# Work journal (append-only, one line per step)
# YYYY-MM-DD HH:MM | agent | task | did | next
2026-11-02 15:17 | Claude Code | T4 gate | e2e isolation: per-file company fixture, fresh API per run, 1 local worker | next: full e2e run, Phase 4 summary
2026-11-02 15:19 | Claude Code | T4 gate | Cloudflare ranges weekly job + API hourly reload; PROGRESS owner table fixed | next: e2e result, Phase 4 summary, PR
2026-11-02 15:24 | Claude Code | T4 gate | STATUS rewritten; full e2e (incl. design) running | next: result, summary, PR
2026-11-02 15:35 | Claude Code | T4 gate | full suites green, summary written, gate ticked | next: PR dev->main, merge on green, then T5.1
2026-11-02 15:49 | Claude Code | T4 gate | PR #7 merged to main (CI green); asked Dependabot to rebase #5 | next: T5.1
2026-11-02 15:56 | Claude Code | T5.1 | GET /users + /company/users + tests | next: T5.2 invite flow
2026-11-02 16:01 | Claude Code | T5.2 | API done: invite/resend/cancel, role change, suspend/reactivate, reset two-step + 7 tests | next: web invite sheet + row actions
2026-11-02 16:06 | Claude Code | T5.2 | web invite sheet, row menu, e2e | next: T5.3
2026-11-02 16:10 | Claude Code | T5.3 | policy + role viewer, API+web+e2e | next: Phase 5 gate
2026-11-02 16:25 | Claude Code | Phase 5 gate | suites green, summary, PR | next: T6.1
2026-11-02 16:29 | Claude Code | T6.1 | migration 0013 + models for all 6.3 tables; reports graph now reads current assignments | next: GET /employees, /employees/summary, list page
2026-11-02 17:01 | Claude Code | T6.1 | list, summary, archived, tests | next: T6.2
2026-11-02 22:38 | Claude Code | T6.2 | recovered uncommitted T6.2 work as wip commit c9ac8c3 | next: review, run tests, finish
2026-11-02 22:39 | Claude Code | T6.2 | verified (API 3, e2e 8, lint/types clean), ticked | next: T6.3
2026-11-02 22:41 | Claude Code | T6.3 | API: profile, status, opt-out+agreement, guarded delete + 4 tests | next: web profile page /employees/[id]
2026-11-02 22:46 | Claude Code | T6.3 | web profile + e2e done, verified | next: T6.4
2026-11-02 23:20 | Claude Code | T6.4 | API: personal details, address, contacts, identity, bank, reveal + 3 tests | next: web Personal tab
2026-11-02 23:35 | Claude Code | T6.4 | web Personal tab (personal-tab.tsx, mounted on profile) lint/types/unit clean | next: e2e in employees.spec.ts
2026-11-02 23:50 | Claude Code | T6.4 | done: API + web + e2e verified | next: T6.5
2026-11-02 20:05 | Codex | T6.5 | synced dev, dispatched CI 41502580515; read requirements, lint/types clean | next employment API and tests
2026-11-02 20:15 | Codex | T6.5 | employment API, audited CRUD, role history and date-aware readers; 9 integration tests pass | next Employment tab UI
2026-11-02 20:25 | Codex | T6.4 CI | API job failed on stale generated data-model doc; regenerated and drift test passes | next push fix and verify Employment UI
2026-11-02 18:46 | Codex | T6.5 | Employment UI and explicit-save e2e written; lint/types clean | next run affected Playwright and API tests
2026-11-02 18:48 | Codex | T6.5 | initial checks found outdated reporting fixture and duplicate history locator; corrected both; whitespace is now 422 | next rerun affected tests
2026-11-02 18:50 | Codex | T6.5 | Employment complete; affected API/reporting/doc 26 pass, web unit 13 pass, browser 2 pass; lint/types/build clean | next T6.6 salary
2026-11-02 18:55 | Codex | T6.6 | salary history/preview API with permissions, tenant references and dated GOV.UK rates; 10 tests pass, lint/types clean | next hidden salary UI
2026-11-02 18:59 | Codex | T6.6 | salary UI fetches on Show only; explicit Save, preview warning and lookups; browser test written | next run Salary journey
2026-11-02 19:02 | Codex | T6.6 | complete; salary API/unit 10 pass, browser/setup 2 pass, lint/types/build clean; CI 41504657493 pending | next T6.7 Documents/PDF
2026-11-02 18:55 | Codex | relay | T6.5/T6.6 complete and pushed; handover at task boundary, CI 41504657493 pending without failures | next check CI then T6.7 Documents/PDF
2026-11-02 18:57 | Codex | T6.7 | requirements/baseline pass; WeasyPrint dependency and runtime/CI libraries added | next Documents API and PDF
2026-11-02 19:00 | Codex | T6.7 | Documents API and masked inspection PDF; 3 tests pass, lint/types clean | next Documents UI and print button
2026-11-02 19:02 | Codex | T6.7 | Documents UI and Print record implemented, browser test written | next browser verification
2026-11-02 19:04 | Codex | T6.7 | browser upload locator corrected to FileDrop full accessible label | next rerun Documents journey
2026-11-02 19:05 | Codex | T6.7 | FileDrop label lookup remains ambiguous; browser test now targets the dialog file input directly | next rerun Documents journey
2026-11-02 19:07 | Codex | T6.7 | complete; API/PDF/security 3 pass, Documents browser/setup 2 pass, lint/types/build clean | next T6.8
2026-11-02 19:08 | Codex | T6.8 | Activity API reuses audit pagination and includes owned file events; isolation/RBAC test passes | next related tab UI
2026-11-02 19:09 | Codex | T6.8 | related shells and Activity UI built, browser journey written | next browser verification
2026-11-02 19:11 | Codex | T6.8 | complete; Activity API 1 pass, browser/setup 2 pass, lint/types/build clean; previous CI now green | next Phase 6 gate integration gaps (link picker, Add photo)
2026-11-02 19:15 | Codex | Phase 6 gate | deferred linking and photo API/UI built; User Access 10 tests and targeted photo/link tests pass | next combined browser check
2026-11-02 19:18 | Codex | Phase 6 gate | link/photo browser 2 pass; list now shows uploaded avatars; screenshot spec ready, lint/types pass | next full-suite gate sequentially
2026-11-02 19:21 | Codex | Phase 6 gate | API full 421 pass/1 fixture failure; real-schema reporting fixture fixed, affected 26 pass | next web/browser gate
2026-11-02 19:22 | Codex | Phase 6 gate | web full 776 pass, guards 32 pass, lint/types/generated API clean | next full Playwright once
2026-11-02 19:27 | Codex | Phase 6 gate | full Playwright running, exec 38612, /tmp/cmr-phase6-e2e.log; no failures through component checks | next inspect this run before rerunning
2026-11-02 19:35 | Codex | Phase 6 gate | full Playwright 396 pass/144 screenshot-only skipped (11.9m); all gate checks now verified | next screenshots, summary and PR
2026-11-02 19:38 | Codex | Phase 6 gate | captured 60 QA images; fixed role-only Overview label; screenshot helper resets scroll/focus and uses modal viewport | next verify fix and recapture
2026-11-02 19:40 | Codex | Phase 6 gate | role-only fix API 3 pass; screenshot assertion narrowed to accessible Summary region after transition duplicate | next complete recapture
2026-11-02 19:43 | Codex | Phase 6 gate | recapture 5 pass, screenshots reviewed; final QA fixes zero-valued facts rendering as Not set | next final artifact refresh and PR
2026-11-02 19:46 | Codex | Phase 6 gate | final screenshots 5 pass/60 images, spot-reviewed; phase summary written; hierarchy deferral corrected to T12.1 | next PR and green CI merge
2026-11-02 19:46 | Codex | Phase 6 gate | PR #11 opened (dev to main), local gate and 60 images complete | next all-green CI then merge with --merge --auto
2026-11-02 19:52 | Codex | Phase 6 CI | patched brotli 1.2.1/pypdf 6.21.4, local audit clean/4 PDF tests pass; documented tested Jinja false-positive as email renderer does | next latest PR #11 CI
2026-11-02 20:13 | Codex | Phase 6 gate | PR #11 merged as 6acec98 after all 12 CI checks green (API 422 pass); clean dev synced | next T7.1 baseline/model/API/UI
2026-11-02 20:14 | Codex | relay | Phase 6 merged green; T7.1 requirements/source baseline ready (ruff/mypy and 3 tests pass), no RTW code yet | next rtw/models.py and migration 0015, then API/UI
2026-11-02 20:40 | Codex | T7.1 | model/migration 0015, immutable history and caller-scoped status view; 7 migration/doc checks pass | next schemas/service/router tests
2026-11-02 20:46 | Codex | T7.1 | scoped RTW record/history/correction/evidence/PDF API; 12 tests pass incl crypto, status edges, quarantine and tenant view | next employee/list UI integration
2026-11-02 20:54 | Codex | T7.1 | employee/list RTW UI, filters/deep links and masked full PDF; API 15/list 6 checks pass, web lint/types pass | next conditional form/evidence/correction browser checks
2026-11-02 20:55 | Codex | T7.1 | browser scenario prepared for all four conditionals, explicit record/upload, auto-selection, masked PDF/history and directory links | next run affected Playwright employees + rtw specs
2026-11-02 20:57 | Codex | T7.1 | production build and 15 employee/setup browser checks pass; corrected new axe invocation to existing modal mode | next rerun rtw.spec.ts only
2026-11-02 20:59 | Codex | T7.1 | RTW browser reached saved check; replaced ignored StatusChip aria-label with screen-reader context, updated scoped assertions | next rerun RTW only
2026-11-02 21:01 | Codex | T7.1 | browser verified masked record/PDF/filter; resize assertion now waits for mobile table cards and responsive layout | next finish RTW scenario
2026-11-02 21:03 | Codex | T7.1 | complete: API/PDF 15, migration/doc 7, list 6, employee browsers 15 and RTW browser/setup 2 pass | next T7.2 sponsor documents/model/API/UI
2026-11-02 21:04 | Codex | T7.2 | requirements/patterns reviewed; API area lint/types and web types pass; 15-test baseline unchanged | next sponsor document model/migration 0016
2026-11-02 21:07 | Codex | T7.2 | sponsor model/migration 0016 with encrypted refs, retained versions/withdrawals/renewal planning; migration/doc 7 pass | next scoped API and tests
2026-11-03 01:08 | Codex | T7.2 | resumed clean e2269e4; dev synced and latest CI green, model checkpoint intact | next scoped sponsor document API/tests
2026-11-03 01:11 | Codex | T7.2 | scoped document/version/renewal/withdraw/evidence/register API; 14 integration tests pass; generated types/lint/mypy pass | next employee forms and sponsored table
2026-11-03 01:14 | Codex | T7.2 | sponsor document forms/history, renewal/withdrawal and sponsored table; web types/lint pass; browser scenario ready | next affected sponsor/RTW Playwright checks
2026-11-03 01:16 | Codex | T7.2 | sponsor production browser scenario passes incl mobile/axe; corrected adjacent RTW mobile locator (grid to list) | next rerun RTW only and finish T7.2
2026-11-03 01:18 | Codex | T7.2 | RTW mobile list assertion now matches exact name, avoiding hidden Open label; sponsor scenario remains green | next rerun RTW only
2026-11-03 01:20 | Codex | T7.2 | narrowed RTW Verified assertion to accessible heading after filter state (text locator hit hidden streamed heading) | next rerun RTW then finish T7.2
2026-11-03 01:21 | Codex | T7.2 | complete: migration/doc 7, sponsor API 14, sponsor browser/setup 2 and adjacent RTW browser/setup 2 pass; lint/types/build clean | next T7.3 working days/CoC/org changes
2026-11-03 01:23 | Codex | T7.3 | official deadline/glossary/calendar sources checked; holiday baseline lint/types/tests pass; recorded AO/Key Contact exception | next pure calculator and dated examples
2026-11-03 01:24 | Codex | T7.3 | pure working-day calculator with 12 official-date examples/edge checks passes lint/types/tests | next immutable changes/org models and migration 0017
2026-11-03 01:29 | Codex | T7.3 | change/org models + migration 0017, tenant RLS and immutable snapshots/reporting; migration/doc 7 pass | next scoped API/calendar coverage/reporting tests
2026-11-03 01:36 | Codex | T7.3 | scoped change/org CRUD, snapshot/defaults, deadline preview and reported actor/date API; 19 tests pass, generated types/lint/mypy clean | next UI + test-only e2e calendar seed
2026-11-03 01:40 | Codex | T7.3 | retained document version labels + shared official 2026/27 calendar fixture seeded in e2e API; reporting/holiday API 13 pass | next employee/company change UI, browser + holiday regression
2026-11-03 01:45 | Codex | T7.3 | employee log/forms, live official-calendar preview and company Workers/Organisation register built; web types/lint pass | next browser scenario and holiday regression
2026-11-03 01:47 | Codex | T7.3 | worker/org browser scenarios prepared and statically checked | next affected compliance-changes + holidays Playwright run
2026-11-03 01:50 | Codex | T7.3 | holiday/setup browsers 14 pass; fixed described-checkbox selector and inspector stale-row state after report refresh | next rerun compliance-changes browser scenarios only
2026-11-03 01:52 | Codex | T7.3 | complete: calculator 12, reporting/holiday API 13, migration/doc 7; reporting browser/setup 3 and holiday/setup 14 pass | next T7.4 reminders engine/register
2026-11-03 01:57 | Codex | T7.4 | reminders/email/notifications/job requirements reviewed; baseline lint/types and email/worker tests pass | next model/migration 0018 and threshold service
2026-11-03 01:59 | Codex | T7.4 baseline | fixed existing worker queue-test cron minute-boundary flake; email/worker 11 pass, lint/types pass | next reminders model/migration 0018
2026-11-03 02:06 | Codex | T7.4 | reminder model/migration 0018 with RTW targets, sent immutability and owner-only derived deadline refresh; 14 migration/doc/change checks pass | next threshold service/source hooks/daily job
2026-11-03 02:15 | Codex | T7.4 | threshold/source hooks + daily job, admin notice dedupe, snooze/restore/cancellation and unreported deadline refresh; 34 checks pass, final engine 5 pass | next scoped review/send API with atomic delivery
2026-11-03 02:36 | Codex | T7.4 | reviewed/received reminder API and atomic nudge+notification+audit; 20 affected cases verified incl concurrent dedupe/rollback and self-service guards; types/lint/gen pass | next register/review and My Documents UI
2026-11-03 02:48 | Codex | T7.4 | due/register/history UI, explicit review drawer and own received messages; optional snooze draft API test passes, web types/lint pass | next browser reminder workflow
2026-11-03 02:55 | Codex | T7.4 | browser reminder workflow written; web types and targeted lint pass | next production Playwright reminders scenario
2026-11-03 02:56 | Codex | T7.4 | complete: reminder/setup production browser 2 pass incl explicit saves/snooze/send, history, own message and mobile axe | next T7.5 compliance hub/dossier
2026-11-03 02:56 | Codex | T7.5 | started compliance hub/dossier requirements and nearest patterns | next affected baseline then scoped hub APIs
2026-11-03 02:57 | Codex | T7.5 | baseline company/audit/doc 27 pass; lint/types pass; readiness and separate platform-content guard choices recorded | next scoped hub overview/activity APIs and tests
2026-11-03 03:03 | Codex | T7.5 | scoped hub overview/activity CSV implemented; 3 hub + 11 audit cases pass, generated types pass; fixed existing raw-SQL JSON default guard | next editable dossier store and original checklist PDF
2026-11-03 03:09 | Codex | T7.5 | global dossier migration 0019, verified official seeds, mandatory-MFA platform editor API and original checklist PDF; 19 dossier/migration/doc/identity + prior RBAC 16 verified | next hub/dossier/platform UI and query-tab links
2026-11-03 03:14 | Codex | T7.5 | hub/dossier/platform editor UI built; employee/change query tabs work; web types/lint pass | next browser hub links/filter/export/dossier/mobile workflow
2026-11-03 03:15 | Codex | T7.5 | hub browser workflow written and statically checked; notes checkpointed before browser run | next production hub and adjacent query-tab browser checks
2026-11-03 03:17 | Codex | T7.5 | complete: production hub/changes/RTW/setup 5 pass incl destinations/CSV/PDF/mobile axe; affected API and static checks pass | next T7.6 sponsor PDF and bell Needs attention
2026-11-03 03:17 | Codex | T7.6 | started sponsor record PDF and bell feed; general notification preferences/digests remain Phase 14 | next affected baseline and masked scoped PDF
2026-11-03 03:19 | Codex | T7.6 | baseline PDF/sponsor 15 and shell 19 pass; scoped design reviewed | next masked sponsor PDF with versions and change snapshots
2026-11-03 03:23 | Codex | T7.6 | sponsor PDF scenario 1 and own bell/privacy/route checks 2 pass; APIs/static/generated types complete | next PDF download button and live bell UI

2026-11-03 06:46 | Codex | T7.6 | recovered PDF/bell UI; web types/lint and shell 19 pass; browser assertions added | next sponsor/reminder Playwright
2026-11-03 06:50 | Codex | T7.6 | reminder/setup browser pass incl bell read/live actions; sponsor transition selector hit duplicate hidden Visa route | next visible locator and sponsor rerun
2026-11-03 06:54 | Codex | T7.6 | complete: PDF download sponsor/setup 2 pass; reminder/setup 2 pass incl bell read/live actions; web types/lint and shell 19 pass | next Phase 7 full suite/screenshots/PR then audit stop
2026-11-03 06:54 | Codex | relay | T7.6 complete and pushed; Phase 7 gate outstanding, no gate suites started | next sequential full checks, screenshots and PR then audit stop
2026-11-03 07:00 | Codex | Phase 7 gate | ruff/format pass; fixed three reminder test typing errors, mypy 225 files passes | next full API suite then web/browser sequentially
2026-11-03 07:03 | Codex | Phase 7 gate | screenshot spec prepared for 390/1280 light/dark (9 views each), targeted lint passes; full API running session 96032 log /tmp/cmr-phase7-api.log | next inspect API then web gate
2026-11-03 07:07 | Codex | Phase 7 gate | API full 479 pass/2 fail; normalized hyphenated operation IDs and updated encrypted-field inventory; affected 15 pass, lint/types/gen pass | next full web checks then Playwright
2026-11-03 07:13 | Codex | Phase 7 gate | full web unit/static/generated-contract and node guard checks pass; screenshot tuple type fixed | next full Playwright once, then screenshot capture/review
2026-11-03 07:29 | Codex | Phase 7 gate | full Playwright 398 pass/148 screenshot skips/4 stale shell assertions (built hub/My Documents and reminder title); expectations updated | next shell rerun plus Phase 7 screenshots
2026-11-03 07:34 | Codex | Phase 7 gate | affected shell/setup 68 pass; screenshot wait mistakenly matched persistent status, narrowed to Loading messages | next screenshot-only capture and review
2026-11-03 07:38 | Codex | Phase 7 gate | screenshot/setup 5 pass/36 images; visual review caught narrow mobile hub title beside long CTA; stacked mobile queue rows | next affected hub browser and recapture
2026-11-03 07:42 | Codex | Phase 7 gate | final hub/screenshots 6 pass, 36 images refreshed/reviewed; mobile queue readable; five-line phase summary recorded | next dev-main PR, all-green CI merge, mandatory audit stop
2026-11-03 07:44 | Codex | Phase 7 gate | PR #13 opened dev to main, local gate/screenshots complete | next inspect all CI, fix failures then merge green and mandatory audit stop
2026-11-03 07:21 | Codex | Phase 7 CI | Semgrep flagged fixed-constant migration SQL; replaced assembly with literal identical statements; migrations/dossier/reporting 14 pass, ruff pass | next new CI run all green then merge/audit stop
2026-11-03 07:38 | Codex | Phase 7 gate | PR #13 merged f17ef67 after all 12 checks green (41595489940); dev synced; 36 reviewed screenshots saved | next mandatory owner audit, do not start Phase 8
2026-11-03 07:38 | Codex | journal correction | intermediate gate timestamps were manually estimated; git commit/run times determine exact chronology | next use clock-derived London time
2026-11-03 07:38 | Codex | relay | Phase 7 completed/merged; State BLOCKED audit requested; post-merge main CI 41597645539 pending | next owner audit findings, no Phase 8 work
2026-11-03 08:48 | Codex | F7.1 | guards and UI confirmation complete; access 12 pass, ruff/mypy/web lint/types pass | next F7.2 auth audit events
2026-11-03 08:53 | Codex | F7.2 | transactional authentication audit events with private pre-tenant inserts and no credentials; auth endpoints 18 pass; auth flows and migrations 30 pass; ruff/mypy pass | next F7.3 — every registered route against all six roles
2026-11-03 08:54 | Codex | F7.3 | exercise every effective route guard for six roles; prevent deferred-router enumeration from passing vacuously; RBAC 22 pass; ruff/mypy pass | next F7.4 — cross-company PDF and dossier isolation tests
2026-11-03 08:55 | Codex | F7.4 | foreign PDF IDs match missing-record 404s without render/audit; shared global dossier and tenant download audit verified; PDF/dossier isolation and related tests 8 pass; ruff/mypy pass | next F7.5 — Python/SQL RTW status parity on identical data
2026-11-03 08:57 | Codex | F7.5 | Python and SQL RTW status parity for 225 identical outcome/expiry/evidence cases in three timezones plus absent checks; RTW parity 3 pass (225 combinations); ruff/mypy pass | next F7.6 — deterministic browser waits and Redis-isolated error tests
2026-11-03 08:58 | Codex | F7.6 | remove fixed waits from all five functional specs (audit already awaits animations); stub Redis in error tests; error tests 24 pass; ruff/mypy and web lint/types pass; affected Playwright next | next F7.7 — refresh PROGRESS header and T7.4–T7.6 entries after affected browser run
2026-11-03 09:01 | Codex | F7.7 | refresh progress header and complete T7.4–T7.6 implementation/verification entries; affected browser/setup 63 pass; F7.1–F7.6 API/static checks pass; progress entries reviewed | next T8.1 — source verification; models/migration; service/API; UI; affected checks
2026-11-03 09:03 | Codex | T8.1 | GOV.UK seed rules checked; baseline running; model/seed strategy recorded | next frozen migration and signup seeding
2026-11-03 09:06 | Codex | T8.1 | leave model, frozen backfill/sign-up seeds and source record complete; migration/doc/signup 9 pass, ruff/mypy pass | next scoped API and tests
2026-11-03 09:08 | Codex | T8.1 | scoped leave CRUD/settings, validation/audit and generated client complete; leave/RBAC/auth 50 pass, ruff/mypy pass | next leave settings UI and browser flow
2026-11-03 09:12 | Codex | T8.1 | leave settings/forms/guidance UI and browser workflow ready; lint/types pass, API schema21 and web777 pass | next targeted production browser and finish
2026-11-03 09:13 | Codex | T8.1 | production UI reached seeded settings; narrowed ambiguous year-field browser selector | next targeted browser rerun
2026-11-03 09:15 | Codex | T8.1 | production CRUD/settings workflow passes; corrected mobile guidance accessible-name mismatch from axe | next final focused browser run
2026-11-03 09:16 | Codex | T8.1 | complete: source-backed defaults, migration/signup seeds, scoped audited settings/CRUD and UI; API50/schema21/web777/browser6 pass, static clean | next handover; T8.2 queued
2026-11-03 09:17 | Codex | relay | F7.1–F7.7 each committed; T8.1 complete and pushed, all affected checks pass | next T8.2 ledger; absent audit document noted in STATUS
2026-11-03 09:22 | Codex | CI before T8.2 | clean dev synced; gh run list shows no audit/T8.1 run; dispatched 41610450677 at 0d3b86d | next fix red or confirm green before T8.2
2026-11-03 09:41 | Codex | T8.2 | all twelve CI jobs green for audit fixes/T8.1 at 0d3b86d (41610450677); start ledger/calculations | next pure calculations/unit tests
2026-11-03 09:44 | Codex | T8.2 | pure calculations and 27 cases pass; ruff/mypy clean; standard-day units and exact fraction arithmetic | next append-only ledger/view migration
2026-11-03 09:47 | Codex | T8.2 | ledger/view migration, cross-tenant FKs, immutable movements and initial reconcile/manual services; mypy clean | next escalated migration and service DB tests
2026-11-03 09:51 | Codex | T8.2 | schema/settings17 and initial ledger15 pass; scoped company query fixed; expanded monthly/year/stamping/validation cases; type-sheet bank inclusion toggle | next final affected tests/static/browser
2026-11-03 09:54 | Codex | T8.2 | complete: calculations28, ledger20, guards31, migration/settings17, browser6 pass; static clean; exact deduction arithmetic covers unequal weekdays | next T8.3 requests/approvals/attendance
2026-11-03 09:56 | Codex | T8.3 | start request/model/counter/approval/attendance sub-steps after completed T8.2 | next request and attendance models/migration
2026-11-03 09:57 | Codex | T8.3 | request/attendance models and migration with tenant FKs; schema inventory updated; lint/types pass | next migration roundtrip then counter/API
2026-11-03 10:05 | Codex | T8.3 | migration8 pass; counter, scoped request/approval API, self guard, atomic booking/notifications written; static clean, schema generated | next scenario/RBAC/rollback tests
