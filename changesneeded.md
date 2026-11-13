# changesneeded.md — audit AUDIT-4 round 3 (2026-11-13, claude-opus-5-5)
## Result: PASS

Scope: audit-4-r2..fa0ea55 (fix PRs #108–#111 for C4.2.1–C4.2.4) plus a regression check of the code they touched. Tests at audit: api 1381/0/0, web unit 1466/0, e2e 488/0 (328 skipped, project-split as before), CI green (PRs #108–#111 all 12 checks pass). Ruff/format/mypy, web lint/typecheck, gen:api:check and build passed. check-rls ran through `tests/db/test_cli.py` in the API suite.
Counts: 0 P0 / 0 P1 / 0 P2. PASS (no P0/P1).

## Notes (no action needed)
- C4.2.1: `_limit_reads` gives a trusted peer that sends no `X-Real-IP` its own 6000/min bucket, keyed by the peer. Requests through the Railway edge always carry `X-Real-IP`, so visitors keep the 120/min bucket. Without a configured or deployed trust list nothing is trusted, so local and untrusted callers are unchanged. All three required tests are present and pass. It repeats `client_ip._within`/`_parse` inline; reusing them would be tidier, but this is not a defect.
- C4.2.2: the whole bulk CSV is streamed (hashing wrapper, plain or gzip input), and only the normalised name, number and SIC section are stored. Duplicates are still rejected across the whole file, because every occurrence of a wanted name is counted. Legacy raw-CSV datasets still read. It keeps every row rather than only sponsor names, as recorded in decisions.md (2026-11-13 00:55): a later-appearing sponsor must still match. The existing C4.1.15 tests pass unchanged. The one `type: ignore[override]` is on `_Hashing.readinto`'s buffer type.
- C4.2.3: `grep -rn text-title3 web/components web/app` returns nothing.
- C4.2.4: notice-pay now uses the shared `PresetChips` with the same two scenarios and values.
- The diff adds no new skips, xfails or eslint-disables, and no assertions were removed.
