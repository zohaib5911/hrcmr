# STATUS
Updated: 2026-11-07 12:15, Europe/London    Agent: Claude Code (Haiku 5.5, SMALL)    Branch: dev    Commit: pending (feat T11.3)
State: IN PROGRESS

## Last completed
- T11.3 — Candidates: CRUD with archive; right-to-work checks through the shared RTW service with a candidate owner; candidate documents as owned files; candidates tab and profile.

## Current task
- none (T11.3 closed). Next block per next.sh is T11.4 (applications, interviews, offers).

## Next tasks
- T11.4 — Applications, interviews, offers (the pipeline bar lands here; Apply to posting becomes live)
- T11.5 (S!) convert to employee (the RTW gate uses the current candidate check); T11.6 (S!) public careers and apply form; P11 gate; AUDIT-1

## Health
- CI on dev: PR #17 merged as 34f7aee (green on f993540). dev pushed through T11.2.
- Local checks run this session: candidate, RTW, files, employee documents, recruitment, postings, RBAC and guards, data-model doc: 60 pass; mypy/ruff clean (326 files); web unit 777; typecheck, lint, gen:api clean; recruitment.spec pass.

## Issues / suggestions
- Candidate document uploads go through the generic POST /files with owner_type candidate; only full-scope roles can attach them (matches recruitment being company-wide).
- The candidate RTW status is worked out in Python (status_of) for candidates, the same as for employees; the SQL view is employee-only. Keep them in step if the rules change.
- A candidate's archived state does not yet hide applications (none exist until T11.4).
- Rota publish inserts rota.published notifications but notifications/router.py _kinds omits that kind (left alone).
- Never overlap DB pytest and Playwright (shared PostgreSQL role passwords).

## Strategy / decisions taken
- Candidate RTW reuses rtw_checks with subject_type "candidate". _out and _validate now take the row's own subject type for the evidence file check; employee behaviour is unchanged.
- Candidate RTW uses recruitment.candidate.read / write, not the employee RTW permissions. Both reads and writes are company-wide only.
- Candidate documents are files with owner_type "candidate"; the files owner check returns 404 for a candidate that is not in this company.
- Archive sets archived_at (DELETE /candidates/{id} returns 204); archived candidates are hidden unless include_archived is set.
- The Sponsorship check tab and the Applications tab are placeholders until T11.4 and T15.6; Apply to posting and Convert are disabled.

## Owner actions needed
- None.
