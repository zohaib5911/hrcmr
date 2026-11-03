# STATUS
Updated: 2026-11-03 23:33, Europe/London    Agent: Codex    Branch: dev    Commit: 09ecc9f
State: IN PROGRESS

## Last completed
- Phase 9 gate — PR15 merged86c51a5; all12 CI green41737189830; 76 reviewed screenshots saved.

## Current task
- T10.1 — Company documents (categories and review dates)
  - [x] Read relevant plan and verify existing document/file/RBAC baseline34
  - [x] Model, tenant migration and contracts
  - [ ] Scoped audited scanned CRUD/download API and affected tests
  - [ ] Documents workspace, upload/edit/archive and review flags
  - [ ] Production browser verification, static checks and completion log
- Resume note: CompanyDocument model/contracts and migration0030 ready; tenant composite file FK/RLS/triggers and ten category constraints. Migration7, document typing/ruff pass. Next documents/router.py full-scope scanned CRUD/download plus regression tests, then UI.

## Next tasks
- T10.2 — reports
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
- Company document CRUD uses archive for deletion, preserving scanned files and audit history; review flags use company-local day and include overdue dates.
- Follow existing tenant composite file references, document.file full-scope permissions and scan-gated short-lived downloads. Personal files remain on employee profiles; policies/signatures belong to T10.3.
- Earlier domain decisions remain in git history and .agent/journal.md. AI hidden without ANTHROPIC_API_KEY; Ask Mady deferred.

## Owner actions needed
- None. Existing non-blocking setup: protect main and enable private vulnerability reporting.
