# changesneeded.md — audit AUDIT-3 round 3 (2026-11-12, gpt-6.1-sol)
Scope: 170a10d..9b2e3a1 (C3.2.1–C3.2.6 fixes and regressions; Phase 18–20 additions excluded). Tests at audit: api 1359/0/0, RLS CLI passed; web unit 1286/0, e2e pending; CI latest listed dev run green, latest merged fix PR #71 all checks green.
Counts: 0 P0 / 2 P1 / 0 P2. FIX NEEDED (browser verification pending).

### [ ] C3.3.1 · P1 · Preserve the current contact page when a delayed update completes (from C3.2.5)
- **Problem:** `web/components/platform/contact-admin.tsx:56-77` captures the old list `key` and `filter` in `mark()`, then applies the PATCH response to the current list rows. Start marking a message on page 1, click Next while PATCH is pending, let page 2 load, then resolve PATCH: `setRows` assigns page 1's key to page 2's rows. Page 2 disappears and stays on Loading until another navigation/reload. Changing the handled filter during PATCH has the same race. List GET effects already ignore stale responses, but the mutation does not. An isolated component probe reproduced the disappearing second-page sender.
- **Fix:** make the mutation response safe against page/filter changes. Only update state matching the request's original key, or prevent page/filter changes while it is pending; preserve the active list and handle failure without redirecting from stale results unnecessarily. Reconcile items and total when a handled change removes a row from the active filtered list. Keep the existing permission/session behavior.
- **Done when:** collected `web/components/platform/contact-admin.test.tsx` tests defer PATCH, load a distinct second page (and separately change the filter), resolve PATCH and assert the current list remains visible with the correct rows/key; cover matching-page removal and total. Targeted contact tests, lint and typecheck pass.

### [ ] C3.3.2 · P1 · Collect the platform page-entry session tests (from C3.2.4)
- **Problem:** `web/app/(admin)/platform/session-guard.test.tsx` contains sixteen cases for absent, invalid/expired and valid platform sessions on queues/contact/users/subscriptions, but `web/vitest.config.mts:18-22` includes only lib, components and tests/unit. `pnpm test` and CI silently omit every new page-entry case; the normal `vitest list` filter lists none. A temporary audit config including app tests ran all sixteen successfully, so the implementation is covered only when discovery is corrected.
- **Fix:** move this test into the existing `web/tests/unit/` tree and update the four page imports, following other page tests there (or explicitly include app tests in Vitest). Preserve all sixteen assertions and keep the tests in the normal `pnpm test` command.
- **Done when:** `cd web && pnpm exec vitest list` includes all sixteen page-entry cases; a targeted run executes them, and `pnpm test`, lint and typecheck pass.

## Notes (no action needed)
- Full API execution now completes, including the former SOC model-startup stall. The deterministic sample embedder preserves database/API assertions; no skips or weakened checks were introduced.
- Configured browser URL/CSRF handling, authenticated ingress and signed SSR visitor allowlisting/auditing, page-session validation code, independent queue paging, and the Settings navigation link match their requested fixes.
- Admin browser action testing remains subject to the recorded production-CSP decision; SSR browser tests exercise allowlisted/denied visitors and forged ingress. Deployment must provide the documented authenticated edge and separate server secrets.
- The isolated contact regression probe intentionally failed its new expected-behavior assertion (22 passed / 1 failed across the six existing contact cases, sixteen explicitly collected page cases and one probe); scratch files were removed. This is separate from the unmodified required passing web unit suite.
- Detailed review evidence: `docs/audits/audit-3-r3-review.md`. No product code changed during this audit.
