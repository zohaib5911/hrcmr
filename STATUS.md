# STATUS
Updated: 2026-11-08 01:00 Europe/London    Agent: Claude Code (Haiku 5.5, SMALL)    Branch: dev    Commit: 00e2651

State: IN PROGRESS — C2.1.1 (small model fix)

## Last completed
- AUDIT-2 round 1 — 0 P0 / 3 P1 / 3 P2; findings in changesneeded.md. All runs green: api 1036, web unit 786, e2e 430 (176 skipped), CI green.

## Current task
- changesneeded.md C2.1.1 — P1 letter key points: pseudonymise company employee names before AI
  - [ ] step 1: `generate` in api/app/ai/service.py takes `names` and labels them before building the prompt
  - [ ] step 2: `_ai_paragraphs` in api/app/ai/letters.py loads company employee names and passes them in
  - [ ] step 3: new test in api/tests/db/test_letters.py (Ada Morrow case); run pytest for letters + redaction
- Resume note: if step 1 or 2 is half-done, `git diff` shows it. Verify with `cd api && uv run pytest tests/db/test_letters.py tests/test_ai_redaction.py -q`.

## Next tasks
- C2.1.2 → C2.1.6 (changesneeded.md, in order), then re-audit AUDIT-2 round 2 (big model).

## Health
- CI on dev: green    CI on main: green (PR #22)
- Local checks run: none yet for C2.1.1

## Issues / suggestions
- C2.1.1: the fix pseudonymises full names only ("First Last"). A single first or last name in a key point ("Ada has a meeting") is not replaced. Not in the fix spec; left for the auditor.

## Strategy / decisions taken
- check-rls is run through tests/db/test_cli.py (the bare CLI needs the full app env).

## Owner actions needed
- Review the 8 courses (unpublished). Sponsor-licence checklist item still an owner decision.
