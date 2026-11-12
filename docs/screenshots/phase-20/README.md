# Phase 20 sponsor register

The gate captures twelve states at 390 and 1280 px, in light and dark:
explore map, trend, table, list and empty results; London region; bulletin list
and detail; current and removed sponsor profiles; methodology; register terms.
The profile and methodology captures include the report form. Each capture
checks WCAG accessibility with the shared axe helper and document overflow.

Run from `web/`:

```sh
SCREENSHOTS=1 bash /home/zohaib/cmr_hr/.agent/bus.sh serial -- pnpm exec playwright test phase20-screenshots.spec.ts --project=production
```

The isolated browser-test API ingests the saved `first.csv`
and `second.csv` publications, dated 10 and 11 November 2026, using the real
ingest with an HTTP mock. Synthetic place coordinates are applied through the
geocoding function. SSR pages and the explorer use that API; no browser API
responses are replaced. These are fictional test organisations, not a live
GOV.UK import. No optional Companies House match is seeded. The visitor rejects
optional cookies through the banner before capture.

T20.5 adds register status and rerun API endpoints, without a new screen;
their authorisation, audit and queue behavior is covered by the API suite.

All 48 captures passed the axe and overflow checks. The final browser run passed
8 tests (setup, four screenshot variants, two explorer keyboard-scroll checks,
and one real SSR/accessibility/CSP-nonce regression).

Detail pages render per request to preserve nonce CSP. Public fetch data retains
its timed cache (six hours for profiles); full HTML ISR is incompatible with
this request-specific frame, as described in the
[Next.js CSP documentation](https://nextjs.org/docs/app/guides/content-security-policy#static-vs-dynamic-rendering-with-csp).
