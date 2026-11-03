# STATUS
Updated: 2026-11-03 23:33, Europe/London    Agent: Codex    Branch: dev    Commit: 35d703d
State: IN PROGRESS

## Last completed
- T10.1 — Company document library complete; API5+related49/migration7/static/client/nav15/browser3 pass.

## Current task
- T10.2 — Worker-generated XLSX reports
  - [x] Existing worker baseline and report schema/contracts
  - [ ] Seven scoped report projections and safe XLSX generation
  - [ ] Durable queue, worker/API status/download and affected tests
  - [ ] Reports workspace and real worker/browser verification
- Resume note: ReportJob tenant model/contracts and frozen migration0031 ready; worker baseline4, migration7, report lint/types pass. Next seven tenant projections/safe XLSX generation, then durable enqueue/recovery worker + scoped report API. No API/worker/UI wired yet. No report content, pay or sensitive identifiers may enter logs/audit.

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
- Earlier domain decisions remain in git history and .agent/journal.md. AI hidden without ANTHROPIC_API_KEY; Ask Mady deferred.

## Owner actions needed
- None. Existing non-blocking setup: protect main and enable private vulnerability reporting.
