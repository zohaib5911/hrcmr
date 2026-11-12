# AUDIT-3 round 3 review evidence

Scope: audit-3-r2 (170a10d)..9b2e3a1, limited to C3.2.1–C3.2.6 and regressions. Later Phase 18–20 additions are outside code-review scope; full suites still exercise them.

Reviewed spec: micro_plan T17.1–T17.6 and plan L1155–1175, prior changesneeded C3.2.1–C3.2.6, and the recorded authenticated-ingress/SSR decision.

- C3.2.1 injects the same deterministic embedder used to load the SOC database sample. It guards against accidental model startup and preserves endpoint/database/rate-limit assertions. Full API run pending.
- C3.2.2 reuses baseUrl() with explicit public env reads for session start and CSV export. New tests exercise startFromBrowser with real client/CSRF middleware and mocked fetch, plus configured CSV origin and filters.
- C3.2.3 authenticates ingress with a separate secret, validates the IP, signs a short-lived GET assertion bound to URL and cookie, and verifies it before network allowlisting and audit context creation. Direct API requests retain existing proxy trust. API coverage includes allowed/denied visitors, forged and stale signatures, cookie and URL replay, and recorded IP/UA. Browser tests simulate ingress for SSR; client-action coverage follows the existing production-CSP decision. Deployment contract and secret scanning updated.
- C3.2.4 calls audited /platform/context on queues/contact/users/subscriptions and redirects 401/403; browser components handle UNAUTHENTICATED and FORBIDDEN. Finding: its new app/(admin)/platform/session-guard.test.tsx is outside vitest.config.mts include globs (lib, components, tests/unit only). Its sixteen page-entry cases are not collected by pnpm test.
- C3.2.5 adds independent offset/total and filter resets; list GET effects cancel stale responses. Investigate contact mark mutation: a delayed PATCH captures old key/filter but maps current rows, potentially overwriting a newly loaded page with the old key. It also preserves stale total after removing a filtered row.
- C3.2.6 adds Settings to overview navigation and its href assertion.

Hidden-cheating scan of scoped diff: no added skip/xfail/only/type-ignore/eslint-disable/noqa/TODO/FIXME. Two removed query assertions were strengthened to include limit/offset. New tables/endpoints/legal figures: none in the six fixes.

Verification in progress: Ruff and format passed (552 files), mypy passed (489 source files). Full API suite running under coordinator serial lock. No final result asserted yet.
