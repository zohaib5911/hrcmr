# STATUS
Updated: 2026-11-03 23:33, Europe/London    Agent: Codex    Branch: dev    Commit: 35d703d
State: IN PROGRESS

## Last completed
- T10.1 — Company document library complete; API5+related49/migration7/static/client/nav15/browser3 pass.

## Current task
- T10.2 — Worker-generated XLSX reports
  - [x] Existing worker baseline and report schema/contracts
  - [x] Seven scoped report projections and safe XLSX generation
  - [x] Durable queue, worker/API status/download and affected tests
  - [ ] Reports workspace and real worker/browser verification
- Resume note: Report enqueue/status/recent API, real ARQ generation/recovery and private File artifacts ready; combined reports/projections/worker/files/docs/OpenAPI35 plus final worker6 pass, mypy220/ruff/client clean. Next Reports workspace (7 request cards, recent jobs/poll/download), then real worker production browser. E2E API currently has no worker; extend tests.e2e_server with a real ARQ report worker using isolated Redis12 and its test engines/storage. No Playwright while DB pytest runs (now finished).

## Next tasks
- T10.3 — policies and sign-offs
- T10.4 — Draft with AI feature-flagged UI/API contract

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
