# STATUS
Updated: 2026-11-03 23:33, Europe/London    Agent: Codex    Branch: dev    Commit: 9620587
State: IN PROGRESS

## Last completed
- T10.2 — Seven fresh private worker XLSX reports complete; backend35+worker6/migration7/static/nav15/real-worker browser3 pass.

## Current task
- T10.3 — Policies and sign-offs
  - [ ] Relevant baseline and tenant policy/version/receipt schema/contracts
  - [ ] Draft/file/audience/send/version/archive APIs and atomic notifications
  - [ ] Own accept/sign, immutable receipts, authorized viewer and access checks
  - [ ] Deadlines, reminders and automatic new-starter assignments
  - [ ] Policy wizard/list/detail and My Documents integration
  - [ ] Affected API/static and real production browser verification
- Resume note: Read plan6.7/8.10/T10.3 and policy permissions. No policy code yet. My Documents already hosts sponsor reminders; preserve them while adding policy assignments/viewer/receipts. Reports e2e server now runs the real ARQ report worker; never overlap DB pytest and Playwright.

## Next tasks
- T10.4 — Draft with AI feature-flagged UI/API contract
- Phase 10 gate — full validation/screenshots/green PR
- T11.1 — requisitions

## Health
- CI on dev: green (all12;41737189830)    CI on main: merged green PR15; main push run not checked
- Local checks run: full Phase9 API658+corrected19, web777/scripts32/browser413+retry8/UTC4; screenshot variants and axe/overflow76; T10 document baseline34 — pass.

## Issues / suggestions
- Never overlap DB pytest and Playwright: both provision shared PostgreSQL role passwords. Group DB test paths before other tests.
- Remove dependency cooldown exceptions when due: brotli after2026-11-05, certifi after2026-11-06, pypdf after2026-11-12.
- Browser assertions must wait for hydrated data and target visible roles: Next streaming can briefly retain hidden server copies. Audit document IDs after streamed copies are removed.

## Strategy / decisions taken
- Reports are generated fresh by the worker with full report permission rechecked at execution/download. Employee Detail excludes pay and sensitive identifiers. Training Completion uses current employee training records until Phase15 learning assignments exist.
- Follow existing tenant composite file references, document.file full-scope permissions and scan-gated short-lived downloads. Personal files remain on employee profiles; policies/signatures belong to T10.3.
- Report jobs stay queued until the artifact and generation audit commit atomically; row locks prevent duplicate generation. Minute sweep re-enqueues durable queued IDs with minute-scoped Redis IDs to recover crashes. Maximum three queued jobs per requester; generated artifacts require current full report permission and the requesting user.
- Earlier domain decisions remain in git history and .agent/journal.md. AI hidden without ANTHROPIC_API_KEY; Ask Mady deferred.

## Owner actions needed
- None. Existing non-blocking setup: protect main and enable private vulnerability reporting.
