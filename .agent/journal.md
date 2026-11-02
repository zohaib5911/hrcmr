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
