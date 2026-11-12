# STATUS (snapshot — live state is `bash .agent/bus.sh status`)
Updated: 2026-11-12 21:12 UTC    Agent: codex (gpt-6.1-sol, BIG)    Branch: task/AUDIT-4
State: HANDED OVER — audit fixes ready (AUDIT-4 round 1: 1 P0 / 19 P1 / 1 P2).

## Last completed
- Reviewed T18.1–P20 against the spec, implementation and tests, including phase implementations already present but expressly excluded from AUDIT-3. Checked calculator figures against live primary government sources.
- Recorded 21 exact fix tasks and dependencies. C4.1.1 (lost public register read limits) must merge first. AUDIT-4 remains open.
- Independently reproduced 13 calculator acceptance failures, five missing read-limit failures, stale same-day profiles/duplicate bulletins and skipped A→B→A imports. Temporary probes removed; evidence in docs/audits/audit-4-r1-review.md.

## Verification
- Required API suite: 1363 passed / 0 failed / 0 skipped; Ruff/format/mypy pass. RLS CLI passed on a fresh migrated database.
- Web lint/typecheck, unit 1309 passed, generated API client, production build and bundle scan passed.
- Required browser run: 485 passed / 1 failed / 328 expected screenshot-only skips. The mobile employee filter scroller failed keyboard-focus accessibility.
- Permitted audit one-line fix c221577 adds tabIndex=0 to that wrapper. Post-fix lint/types, employee-list unit 6 passed and all shell accessibility cases plus setup 9 passed. Full suite not rerun; its initial failure is preserved above.
- Latest listed dev CI successful: 43302217904 at fa331d0. Audit PR CI belongs to the coordinator; do not wait.

## Ready next
- Follow the coordinator next.sh: changesneeded.md first, starting C4.1.1. Other tasks cover register import/enrichment/admin UI, calculator correctness/data/spec gaps, and malformed risk draft recovery.
- SSP partial-week rounding follows dated HMRC payment tables; the conflicting prose example and decision C4.1.12 are documented.

## Parked work
- Existing template human review and solicitor review of legal drafts remain required before publication/launch.
- Existing Stripe test credentials and other parked work remain in leftover.md. No new owner input is needed for this audit.
- True ONS map geometry and interaction are already scheduled by the owner in T25.2.
