# AUDIT-3 round 2 review evidence

Scope: audit-3-r1..0d1addd, limited to C3.1.1–C3.1.16 fixes and regressions. Phase 18–20 additions are outside this audit stop; the full suites still exercise them.

Reviewed fixes: ten-year refund entitlement and webhook idempotency; browser platform session start; platform seed and SSR testing decision; overview/navigation; company actions and support context; users; subscriptions; queues/contact; settings; jobs/audit; independent export; owner lock protection; watcher URL allowlist; comp banner; admin colour token; deletion code export exclusion.

Findings to carry into changesneeded.md after verification:
- SessionStart calls browserApiBaseUrl() with its default process.env object. Next.js only inlines explicit NEXT_PUBLIC_API_URL property reads (see lib/auth/request.ts baseUrl). Production client therefore falls back to localhost:8000. Unit tests replace the entire run function and never exercise startFromBrowser.
- Server platformApi forwards cookies but no trusted visitor identity. require_platform checks ADMIN_IP_ALLOWLIST on every request, so SSR pages check the web server's IP; enabling an allowlist for real admin addresses redirects those pages back to session start even after browser start succeeds.
- Contact/queues pages only check presence of a cookie, with no server API check/audit. Expired cookie renders page; client fetch is the sole validation. Subscriptions similarly swallows context 401/403 through isPlatformOwner. These miss C3.1.4's expired-session redirect requirement.
- Contact/queues omit pagination although endpoints return only first 50 rows. Older outstanding messages/requests cannot be reached.
- Overview navigation omits /settings, although C3.1.4 requires all new screens.

Hidden-cheating scan: only two added conditional screenshot skips; accepted phase-gate policy. Removed assertions belong to removed server-side session-start implementation, replaced by component tests; replacement tests do not cover the actual request URL.

Verification: API ruff/format/mypy passed; pytest stalled after 584 dots at 42%, interrupted with no final counts (exit 143 after SIGTERM). RLS CLI passed on a newly provisioned disposable database. Web lint/typecheck/gen/build passed; 1255 unit tests passed; 473 browser tests passed, 220 conditionally skipped (13.9 minutes). All 48 Phase 17 screenshots exist. Latest listed dev CI run: success 42513865285. Production chunk inspection confirms startFromBrowser calls the dynamic-env URL helper without arguments.
