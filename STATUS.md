# STATUS
Updated: 2026-11-02 19:46 (Europe/London)    Agent: Codex    Branch: dev    Commit: da06829
State: IN PROGRESS

## Last completed
- T6.8 plus Phase 6 integration/QA — employee linking, photos, role-only Overview and zero values

## Current task
- Phase 6 gate
  - [x] Deferred User Access employee linking and tests
  - [x] Scanned profile photo upload/view and tests
  - [x] Full suite once and affected failure/QA checks
  - [x] 60 screenshots at 390/1280, light/dark; five-line phase summary
  - [x] Open PR #11 dev to main
  - [ ] Merge only on all-green CI
- Resume note: Phase 6 PR #11 is open: https://github.com/zohaib5911/hrcmr/pull/11 . Wait for every CI check on the latest head to be green; fix any red on dev. Then gh pr merge 11 --merge --auto (no admin/bypass), sync clean dev and start T7.1. Local gate/evidence complete; no full-suite repeat needed.


## Next tasks
- Phase 6 PR/merge, T7.1 through T7.6, Phase 7 gate then BLOCKED — audit requested

## Health
- CI on dev: prior run 41504657493 green; PR #11 CI pending. CI on main: previous run red (fix included on dev).
- Local checks run: API full 421 pass/1 destructive fixture failure fixed, affected RBAC/User Access 26 pass; Overview QA API 3 pass. Web 776 pass, guards 32 pass, full Playwright 396 pass/144 screenshot-only skipped; final screenshots 5 pass (60 images). Ruff/mypy/eslint/tsc/generated API/build clean.

## Issues / suggestions
- Remove certifi exception after 2026-11-06; Dependabot #5 pending green CI.

## Strategy / decisions taken
- Link/unlink requires rbac.role.assign (Company Admin): it changes self-service reach. Own account linking allowed; duplicate employee links refused. Photos require full employee.profile.write, excluding contact-only own writes.
- T6.8 shells preserve workspace employee/month context; later modules replace named components. Activity includes direct employee and owned-file events.
- PDF uses plan-specified WeasyPrint, lazy import, escaped text, blocked resources, masked numbers and scoped salary. Native libraries/fonts installed in runtime and CI.
- Documents/photos reuse scanned FileService with employee associations; clean-only delivery.
- Hierarchy CRUD is T12.1 (corrected old Phase 9 comments); roles use effective dates. Salary fetches only on Show salary.
- AI hidden without ANTHROPIC_API_KEY; Ask Mady deferred.

## Owner actions needed
- None blocking. Protect main and enable private vulnerability reporting.
