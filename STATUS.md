# STATUS
Updated: 2026-11-07 16:00, Europe/London    Agent: Claude Code (Haiku 5.5, SMALL)    Branch: dev    Commit: pending (feat T11.5)
State: IN PROGRESS

## Last completed
- T11.5 — Convert to employee: both gates (accepted offer, verified RTW), employee created through the shared service, documents and RTW check linked, application Hired, one audit event; the convert sheet is on the application page.

## Current task
- none (T11.5 closed). Next block per next.sh is T11.6 (S!, public careers and apply form).

## Next tasks
- T11.6 (S!) public careers pages and apply form (Turnstile, CV scan, confirmation email, recruiter notification) — Recipe R5
- P11 gate (R7); then AUDIT-1, an audit stop: small models stop with "AUDIT NEEDED FIRST"

## Health
- CI on dev: Phase 10 on main (34f7aee). dev carries T11.1–T11.5 checkpoints, not yet through a PR.
- Local checks run this session: convert 3, with employees, profile, policies, applications, interviews, offers, postings, candidates, recruitment, RTW, RBAC, guards and data-model doc 77 pass; mypy (335 files) and ruff clean; web unit 777, typecheck, lint, gen:api clean.

## Issues / suggestions
- Convert writes one audit event (recruitment.candidate.converted) and does not write employee.created; the employee id is in its details. Policy new-starter assignments, if any, add their own audit events.
- The convert sheet is not browser-tested: a real clean scan is needed for the evidence file, which the e2e API cannot seed. Add it when the e2e harness can attach scanned files.
- Accepting an offer does not move the application on its own; stages are moved by hand until a decision is made.
- The candidate profile's header Convert button is still disabled; conversion lives on the application page.
- Rota publish inserts rota.published notifications but notifications/router.py _kinds omits that kind (left alone).
- Never overlap DB pytest and Playwright (shared PostgreSQL role passwords).

## Strategy / decisions taken
- "Verified" means the candidate's current check is exactly verified (clean evidence, not expiring). An expiring check blocks conversion until renewed.
- rtw_checks are immutable in the database, so the verified check is copied to the employee (history stays on the candidate) rather than moved.
- Candidate documents are moved to the employee (owner changed), so the copied check's evidence stays valid.
- Converting needs the caller to have employee write scope (ALL) as well as recruitment.candidate.convert, so recruiters cannot create employees.
- Employee creation moved into app/modules/employees/service.py (add_employee); the employees route and the conversion both use it.
- Conversion moves the application to Hired with a history entry, and a repeat call returns 409 ALREADY_CONVERTED.

## Owner actions needed
- None.
