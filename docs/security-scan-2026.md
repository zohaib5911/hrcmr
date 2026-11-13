# Whole-project security scan — T25.3

Date: 2026-11-13. Reviewer: codex (BIG). Baseline: `38ceed56097a410237f28bcc529d1eb216bbe29c`.

Result: **one P0 and two P1 findings fixed**, with failing-before/passing-after
regressions; no outstanding P0/P1 identified in the reviewed source. Requested
native scans are clean. Production image scans require the PR's mandatory CI jobs;
HTTPS staging/deployment acceptance remains separate, as detailed below.

Scope: plan §4 and §7, the threat model in `docs/security.md`, all registered API
routers and SQLAlchemy tables, production headers, dependencies and CI supply chain.
Severity follows `audit.md`: P0 security/tenant leakage or failing checks; P1 missing
required behaviour or security coverage; P2 non-blocking hardening. This is source
and local test evidence, not a deployed penetration test.

## Automated verification

Native versions match the CI pins. Results collected before the fixes:

| Gate | Local result |
| --- | --- |
| gitleaks 8.30.1, full history (`--log-opts=--all`, redacted) | 899 baseline / 904 checkpoint commits, 16.05 / 16.10 MB; zero leaks |
| Semgrep 1.180.0, all seven CI registry configurations | 1,190 files; zero findings, zero errors |
| pip-audit 2.10.1, frozen exported lock including development dependencies | No known vulnerabilities |
| pnpm production moderate+ and all dependencies high+ | Both report no known vulnerabilities |
| Trivy 0.75.0 config, MEDIUM/HIGH/CRITICAL | Zero findings in both Dockerfiles and scanned configuration |
| actionlint 1.7.12 | Exit 0, no findings |
| zizmor 1.30.1, offline, low+ | Three GitHub configuration files; no findings |

Docker reports no daemon inside the jail. API/web production image vulnerability
and secret scans cannot run locally; the unchanged mandatory `Image scan (api)`
and `Image scan (web)` PR jobs must pass before merge. They scan built image
archives at HIGH/CRITICAL, fixable vulnerabilities, and secrets. This report does
not claim an image pass or a deployed clean bill of health. See the T25.3 decision
in `.agent/decisions.md`.

## Manual review

The registered dependency graph has **69 router source modules and 436 method/path
pairs**: 350 tenant, 43 platform, 22 account flows, 18 public endpoints, two health
probes and one signed Stripe webhook. The frozen endpoint inventory is independently
compared against the live graph by `test_endpoint_security.py`; the role matrix
checks all six tenant roles against all 393 permission-bearing pairs. Resolving
guards is not proof of handler ownership checks: the review below also follows
resource lookup, write/audit and file-serving paths. Cross-tenant IDOR tests exercise
the handlers, using foreign IDs where fixtures provide actual records.

### Findings and fixes

**SEC-2026-01 — P0: generic file routes bypassed company-export access and expiry.**
`api/app/modules/files/service.py`, `FileService._reaches`, fell through to the
company-wide document grant for `owner_type="data_export"`. An HR admin lacks
`company.export` but could obtain archive metadata and a signed download URL when
the artifact UUID was known. Another Company Admin could bypass requester binding;
the requester could bypass the seven-day export expiry until physical cleanup.
The artifact ID is returned by the authenticated generic metadata route and may
also occur in tenant records; UUID unpredictability is not an access control.
Tenant isolation itself remained intact.

Fix: deny `data_export` artifacts at the generic file-service boundary. Only the
dedicated export route may issue their link; it checks current `company.export`,
requester identity, ready status and expiry, and writes `export.downloaded`.
`test_generic_file_routes_never_expose_company_export_artifacts` covers both ready
and expired artifacts, the requester and another same-company admin/HR admin,
metadata and download, and absence of a download audit on rejection. Existing
export tests retain the successful dedicated download and cross-company cases.
Before/after execution results are recorded below.

**SEC-2026-02 — P1: deletion without an export skipped required step-up.**
`api/app/modules/deletion/router.py`, `request_deletion`, checked recent
password/TOTP only inside the optional export branch. A normal Company Admin
session could start deletion and trigger the confirmation email without the
recent reauthentication required by plan §4.2. Email-code confirmation, attempt
limits, the seven-day delay and withdrawal still protected final deletion.

Fix: require step-up at handler entry for every start/resend, before any lookup,
audit, code or mail side effect. The existing client already handles
`STEP_UP_REQUIRED` and retries after password confirmation. The regression
`test_starting_deletion_without_export_requires_recent_step_up` checks denial,
no database/mail effects, then successful start after step-up. Existing authorized
API and screenshot setup flows must explicitly step up.

**SEC-2026-03 — P1: billing plan mutations skipped required step-up.**
`api/app/modules/billing/router.py`, `create_checkout_session` and `cancel_plan`,
admitted an ordinary Company Admin session without recent password/TOTP despite
plan §4.2. Checkout could call Stripe/create a customer; cancellation could change
a plan or request a refund. CSRF and `billing.manage` remained enforced.

Fix: check recent step-up before either handler accesses the provider. Reuse the
billing page's existing password sheet to retry the selected checkout plan or
cancellation, while preserving its export flow. API regressions reject requests
before any provider call/audit; existing legitimate tests explicitly step up.
Client tests check the exact checkout/cancel → step-up → same-action call sequence.
The Billing Portal is unchanged: it neither changes the selected plan nor cancels
it (portal cancellation is disabled in provider configuration).

### Shared control review

- **Identity/MFA/session lifecycle:** `auth/accounts.py`, `router.py`, `sessions.py`,
  `deps.py`, `policy.py`, `core/totp.py` and `passwords.py` implement Argon2id, breached
  password checks, hashed single-use tokens/recovery codes, encrypted TOTP, opaque
  Redis session hashes, idle/absolute expiry, session rotation/revocation and
  MFA/verified-email/current-terms/live-membership checks. Password/reset/login/MFA
  rate limits are server-side. Parent-domain cookies require trusted sibling hosts.
- **CSRF and request validation:** `core/csrf.py` applies constant-time double-submit
  validation to unsafe methods. Only `/api/v1/webhooks/` is exempt; the registered
  inventory currently contains only Stripe there. `RequestModel` forbids unknown
  fields, including nested models, and `BodyLimitMiddleware` bounds announced and
  chunked bodies. CORS uses configured origins, never a wildcard with credentials.
- **Tenant/RBAC/record scope:** `rbac/deps.py` derives company/role from live
  membership, carries scoped `Access`, enforces own/reports relations, and opens
  `TenantSession`; `db/session.py` stamps writes, filters ORM statements and
  reapplies transaction-local settings after commit. Non-owner `app_user` and
  database policies provide the second boundary. Reporting and leave-sanctioning
  graphs are distinct. Parameterised SQL stays in `db/`; the dynamic provisioner
  accepts validated identifiers and code-controlled privilege lists.
- **Platform/support:** separate cookie/token kinds; mandatory MFA, current terms,
  platform membership and optional trusted-IP allowlist. SSR assertions bind
  HMAC, timestamp, method/path/query and cookie hash. Platform access is audited.
  Owner-only refunds/deletion/write enablement have handler checks. Support
  sessions are company-bound, 30 minutes, initially read-only, require reason and
  ticket, and audit both trails. Worker/DB-owner compromise is outside tenant RLS.
- **Uploads/downloads/exports:** extension + magic-byte + size checks precede
  fail-closed ClamAV; random private keys, sanitised attachment names and 60-second
  presigned links. File owner and policy/report-specific checks are centralised.
  CV and attendance parsers have separate bounds. SEC-2026-01 closes the export
  artifact's alternate serving path. Export workers recheck requester access.
- **Stripe:** `integrations/stripe.py` authenticates raw bytes with HMAC and a
  freshness window; `billing/service.py` persists event IDs and rejects replay.
  Browser redirects do not grant entitlements. Billing links use configured origins.
- **Outbound/SSRF:** integration clients build fixed provider URLs with validated
  company/postcode inputs and timeouts; register/rules fetchers enforce HTTPS host
  allowlists on redirects. `test_pentest.py` inventories outbound callers and
  checks SQL, nested mass assignment, traversal and provider URL handling.
- **Secrets, PII and rendering:** settings use `SecretStr`; AES-GCM/blind indexes
  protect sensitive fields; reveals require permission, reach, step-up and audit.
  Structured log/telemetry scrubbers remove secrets/bodies and exception data;
  request logs omit query strings. AI checks enabled configuration, scrubs the
  final outbound payload and logs metadata only. Authored content is trusted code;
  user content is escaped/sanitised. Env allowlist/bundle scans and nonce CSP
  protect browser delivery. Retention, deletion and backups have privileged worker
  paths with separate launch recovery evidence in `leftover.md`.

### Router-by-router coverage

Each row refers to its source under `api/app/`. T = tenant guard + scoped database;
P = platform guard; A = account-flow guard/service; U = explicitly public; H =
health; S = Stripe signature. Mixed routers are marked together. Counts are
method/path pairs, not functions. Tests referenced by filename live in
`api/tests/` or `api/tests/db/`.

| Router source | Pairs | Boundary and reviewed handler controls |
| --- | ---: | --- |


## Deployment limits

The HTTPS staging/WAF/origin-restriction and recovery checks in `leftover.md` remain
required before launch. The P25 gate reviews CSS/script changes from T25.2/T25.4–T25.6.
| `ai/letters.py` | 2 | T; company-wide letter permission, scoped employee data, AI scrub/fallback; AI letter tests |
| `modules/access/router.py` | 12 | T; scoped membership/invitation, last-admin protection, role/invite/reset step-up; user-access tests |
| `modules/announcements/router.py` | 1 | T; published/time/region audience filter, public content only; dashboard/platform-content tests |
| `modules/attendance/batch_router.py` | 5 | T; full-scope writes and reports-filtered grid/exports; attendance-batch tests |
| `modules/attendance/clock_router.py` | 5 | T; linked employee clock, reports approval reach, scoped timesheet lock/audit; attendance-clock tests |
| `modules/attendance/import_router.py` | 5 | T; full-scope import, bounded validated/scanned workbook, tenant preview/commit; attendance-import tests |
| `modules/attendance/router.py` | 4 | T; own/reports record filters, scoped write helper and audit; attendance tests |
| `modules/audit/router.py` | 2 | T; explicit company predicate, bounded pagination, masked values and audited export; audit tests |
| `modules/auth/router.py` | 19 | A; token/session kinds, MFA, rotation, step-up, invitation/company membership; auth flow/endpoints tests |
| `modules/billing/router.py` | 5 | T/S; SEC-2026-03 plan step-up, billing permission, fixed redirects, signed replay-protected webhook; billing/stripe tests |
| `modules/companies/compliance_documents.py` | 5 | T; full document scope, scanned/owned file, scoped archive/audit; compliance-documents tests |
| `modules/companies/key_personnel_router.py` | 7 | T; company-scoped person/proof and document ownership, encrypted identifiers/audit; key-personnel tests |
| `modules/companies/router.py` | 7 | T; explicit company ID, validated fixed-host lookups, scanned logo and audit; company tests |
| `modules/companies/structure_router.py` | 13 | T; scoped location/department/designation references, archive constraints, fixed postcode lookup; structure tests |
| `modules/companies/trading_hours.py` | 2 | T; read/write grants, company/weekday-scoped upsert and audit; trading-hours tests |
| `modules/compliance/activity_router.py` | 2 | T; tenant/category-filtered audit projection, export grant and audit; compliance-activity tests |
| `modules/compliance/dossier_router.py` | 5 | T/P; shared guidance reads, platform-only audited edits, validated external links; dossier tests |
| `modules/compliance/hub_router.py` | 1 | T; company-scoped compliance aggregates and current employee reach; compliance tests |
| `modules/compliance/reminder_router.py` | 9 | T; reachable employee, scoped reminder state, scrubbed AI fallback, audited send/snooze; reminders tests |
| `modules/compliance/router.py` | 12 | T; scoped change/employee bindings, controlled status/evidence and audit; compliance-changes tests |
| `modules/compliance/sponsor_pdf.py` | 1 | T; report grant + reachable employee, escaped template and audit; export-isolation tests |
| `modules/contact/public.py` | 1 | U; bounded strict schema, rate limit/Turnstile, hashed IP, minimal response; contact-public tests |
| `modules/dashboard/router.py` | 3 | T; permission-filtered cards/onboarding, scoped aggregate data; dashboard tests |
| `modules/deletion/router.py` | 4 | T; SEC-2026-02 step-up, hashed expiring code + attempt limit, requester, delayed purge; deletion tests |
| `modules/documents/router.py` | 6 | T; full scope, scoped document/file joins, scanned uploads and archive audit; company-documents tests |
| `modules/employees/activity_router.py` | 1 | T; reachable employee, scoped/masked audit projection; employee-activity tests |
| `modules/employees/compensation_router.py` | 3 | T; reachable employee, salary permission, same-tenant references, audit; compensation tests |
| `modules/employees/document_router.py` | 3 | T; reachable employee + child/document/file ownership, scanned upload and audit; employee-documents tests |
| `modules/employees/employment_router.py` | 16 | T; reachable/locked employee, same-tenant references and child-parent bindings, audit; employment tests |
| `modules/employees/personal_router.py` | 10 | T; reachable employee, own-field whitelist, encrypted/masked identity and bank, audited step-up reveal; personal tests |
| `modules/employees/photo_router.py` | 2 | T; reachable employee, allowed edits, scanned image and clean owned read; employee-photo tests |
| `modules/employees/record_pdf.py` | 1 | T; report permission, reachable employee, escaped PDF template and audit; export-isolation tests |
| `modules/employees/router.py` | 8 | T; own/reports list/detail, same-company status/delete checks, history protection and audit; employee tests |
| `modules/exports/router.py` | 3 | T; company.export + step-up, requester + ready/expiry checks; exports/isolation tests |
| `modules/files/router.py` | 3 | T; owner reach + scan state; SEC-2026-01 denies export artifacts; files/exports tests |
| `modules/health/router.py` | 2 | H; bounded liveness/readiness output, no-store, no credentials in probe errors |
| `modules/holidays/router.py` | 9 | T; calendar/type grants, scoped settings/date upserts and audit; holidays tests |
| `modules/learning/admin_router.py` | 3 | P; platform content grant, draft/publish constraints and audit; platform-content tests |
| `modules/learning/certificates.py` | 3 | T/U; own assignment/certificate scope; minimal public verification with rate limit; certificate tests |
| `modules/learning/router.py` | 11 | T; company assignment vs own completion gates, scoped course assignment/attempts; learning tests |
| `modules/leave/request_router.py` | 11 | T; employee reach and distinct leave-sanctioning graph, scoped request state/audit; leave-requests tests |
| `modules/leave/router.py` | 7 | T; type/config grants, scoped settings and audit; leave-types tests |
| `modules/leave/workspace_router.py` | 7 | T; own/reports balance reach, tenant ledger/config and adjustments audit; leave-workspace tests |
| `modules/leave/year_end_router.py` | 2 | T; accrual-write permission, company-specific run and ledger locks/audit; leave-year-end tests |
| `modules/notifications/router.py` | 5 | T; user/company/kind filters, separate compliance feed permission; notification tests |
| `modules/organogram/router.py` | 6 | T; scoped tree mutations, reference checks, RTW overlay gated separately; organogram tests |
| `modules/pay/router.py` | 20 | T; setting-specific grants, scoped references, masked encrypted bank fields and audit; pay-settings tests |
| `modules/platform_admin/router.py` | 31 | P; owner checks for refunds/deletion, reasoned audited writes, bounded job allowlist; platform tests |
| `modules/policies/own_router.py` | 6 | T; linked employee assignment, version/receipt checks, safe preview and scoped file; policy tests |
| `modules/policies/router.py` | 13 | T; full policy scope, scanned attachments, assignment/version checks and audit; policy tests |
| `modules/rbac/platform_session.py` | 2 | A; separate cookie/token kind, mandatory MFA, live platform membership and trusted network; platform-session tests |
| `modules/recruitment/public.py` | 4 | U; company/open-external posting, rate limit, Turnstile, bounded scanned CV and minimal response; careers tests |
| `modules/recruitment/router.py` | 30 | T; full scope, same-company nested requisition/posting/application/interview/offer, conversion references and audit; recruitment tests |
| `modules/register/public.py` | 9 | U; public projection only, read/report limits, Turnstile POST, bounded queries; register-public tests |
| `modules/reports/router.py` | 3 | T; full report scope, requester binding, queue limit/lock, report_result file check; report tests |
| `modules/rota/action_router.py` | 5 | T; reports reach for bulk copy/clear, same-tenant shifts/version checks; rota-actions tests |
| `modules/rota/publish_router.py` | 3 | T; own published shifts, reports-filtered publishing/print, audit; rota-publish tests |
| `modules/rota/router.py` | 12 | T; setting-specific grants, scoped ID/reference checks and audit; rota-settings tests |
| `modules/rota/week_router.py` | 4 | T; reports reach, shift employee binding, version checks and audit; rota-week tests |
| `modules/rtw/router.py` | 7 | T; reachable employee/candidate, evidence-owner checks, append-only corrections/audit; RTW tests |
| `modules/search/router.py` | 1 | T; independently checks employee/candidate company-wide grants; bounded projected search; search tests |
| `modules/soc/checks_router.py` | 5 | T; company-scoped saved check/version, controlled confirmation and audited PDF; SOC checks tests |
| `modules/soc/cv_router.py` | 1 | T; size/magic-byte/ClamAV before parse, scrubbed bounded AI payload; SOC CV tests |
| `modules/soc/public_router.py` | 3 | U; rate limit, bounded query, published public data only; soc-public tests |
| `modules/soc/router.py` | 2 | T; SOC grants, bounded queries, scrubbed AI matching; SOC matching tests |
| `modules/soc_rules/admin_router.py` | 3 | P; platform rules grant, allowed version transitions and audit; SOC rules tests |
| `modules/sponsor_documents/router.py` | 7 | T; reachable employee + document/file owner, encrypted CoS and audit; sponsor-documents tests |
| `modules/support/router.py` | 4 | P/A; company-bound grant, owner-only write enablement, dual audit and expiry/revocation; support-mode tests |
| `modules/work_log/router.py` | 7 | T; own/reports filters, entry-owner checks and correction/removal audit; work-log tests |

### Table inventory and RLS scope

SQLAlchemy's complete registry contains **102 application tables**. 71 carry
`company_id`: 69 tenant tables, plus the two pre-tenant authentication exceptions
(`sessions`, `invitations`) looked up by hashed token/user/explicit company.
`companies` is a global identity root without RLS (migration 0002, explicitly
retained by migration 0049); tenant handlers must select its ID from `Access`,
never a client-provided company context. The catalog check does not claim otherwise. Global identity/reference/provider/worker tables are deliberately not
classified as tenant data; global does not mean publicly readable. In particular,
email payloads, tokens and provider events are not exposed by public endpoints.

The catalog verification below checks a freshly migrated database as `app_user`,
including every tenant table, all policies, unsafe views/materialised views and
SECURITY DEFINER functions; it also checks the runtime role cannot bypass RLS.
The migration version table (`alembic_version`) is operational metadata in addition
to these application tables. Owner-only maintenance and platform policies are
explicit exceptions, never authority derived from a tenant UUID.

| Table | Reviewed scope | Catalog RLS |
| --- | --- | --- |
| `ai_interactions` | tenant company_id | enabled |
| `announcements` | global | deliberately global/pre-tenant, no RLS |
| `applications` | tenant company_id | enabled |
| `attendance_imports` | tenant company_id | enabled |
| `attendance_records` | tenant company_id | enabled |
| `audit_events` | tenant company_id | enabled |
| `bank_holidays` | global | deliberately global/pre-tenant, no RLS |
| `candidates` | tenant company_id | enabled |
| `certificates` | tenant company_id | enabled |
| `change_of_circumstances` | tenant company_id | enabled |
| `companies` | global identity root; explicit company ID in tenant handlers | deliberately global/pre-tenant, no RLS |
| `company_bank_accounts` | tenant company_id | enabled |
| `company_compliance_documents` | tenant company_id | enabled |
| `company_documents` | tenant company_id | enabled |
| `company_holidays` | tenant company_id | enabled |
| `contact_messages` | global | deliberately global/pre-tenant, no RLS |
| `course_assignments` | tenant company_id | enabled |
| `courses` | global | enabled |
| `data_exports` | tenant company_id | enabled |
| `day_off_patterns` | tenant company_id | enabled |
| `deletion_requests` | tenant company_id | enabled |
| `departments` | tenant company_id | enabled |
| `designations` | tenant company_id | enabled |
| `dossier_links` | global | enabled |
| `email_outbox` | global | deliberately global/pre-tenant, no RLS |
| `email_tokens` | global | deliberately global/pre-tenant, no RLS |
| `emergency_contacts` | tenant company_id | enabled |
| `employee_addresses` | tenant company_id | enabled |
| `employee_assignments` | tenant company_id | enabled |
| `employee_bank_details` | tenant company_id | enabled |
| `employee_compensation` | tenant company_id | enabled |
| `employee_documents` | tenant company_id | enabled |
| `employee_education` | tenant company_id | enabled |
| `employee_memberships` | tenant company_id | enabled |
| `employee_previous_employment` | tenant company_id | enabled |
| `employee_responsibilities` | tenant company_id | enabled |
| `employee_training_records` | tenant company_id | enabled |
| `employees` | tenant company_id | enabled |
| `feature_flags` | global | deliberately global/pre-tenant, no RLS |
| `files` | tenant company_id | enabled |
| `going_rates` | global | enabled |
| `holiday_types` | tenant company_id | enabled |
| `impersonation_sessions` | tenant company_id | enabled |
| `ineligible_codes` | global | enabled |
| `interviews` | tenant company_id | enabled |
| `invitations` | pre-tenant explicit session/invitation scope | deliberately global/pre-tenant, no RLS |
| `key_persons` | tenant company_id | enabled |
| `late_policies` | tenant company_id | enabled |
| `leave_ledger` | tenant company_id | enabled |
| `leave_requests` | tenant company_id | enabled |
| `leave_types` | tenant company_id | enabled |
| `leave_year_end_runs` | tenant company_id | enabled |
| `locations` | tenant company_id | enabled |
| `memberships` | tenant company_id | enabled |
| `notification_preferences` | tenant company_id | enabled |
| `notifications` | tenant company_id | enabled |
| `offers` | tenant company_id | enabled |
| `onboarding_dismissals` | tenant company_id | enabled |
| `org_changes` | tenant company_id | enabled |
| `organogram_levels` | tenant company_id | enabled |
| `pay_bands` | tenant company_id | enabled |
| `pay_scale_rates` | global | enabled |
| `pay_schedules` | tenant company_id | enabled |
| `payment_types` | tenant company_id | enabled |
| `platform_admins` | global | deliberately global/pre-tenant, no RLS |
| `policy_acceptances` | tenant company_id | enabled |
| `policy_documents` | tenant company_id | enabled |
| `postings` | tenant company_id | enabled |
| `register_changes` | global | deliberately global/pre-tenant, no RLS |
| `register_company_datasets` | global | deliberately global/pre-tenant, no RLS |
| `register_company_matches` | global | deliberately global/pre-tenant, no RLS |
| `register_entries` | global | deliberately global/pre-tenant, no RLS |
| `register_place_datasets` | global | deliberately global/pre-tenant, no RLS |
| `register_possible_matches` | global | deliberately global/pre-tenant, no RLS |
| `register_problem_reports` | global | deliberately global/pre-tenant, no RLS |
| `register_publications` | global | deliberately global/pre-tenant, no RLS |
| `register_sponsors` | global | deliberately global/pre-tenant, no RLS |
| `reminders` | tenant company_id | enabled |
| `report_jobs` | tenant company_id | enabled |
| `requisitions` | tenant company_id | enabled |
| `rota_weeks` | tenant company_id | enabled |
| `rtw_checks` | tenant company_id | enabled |
| `rules_versions` | global | enabled |
| `salary_rules` | global | enabled |
| `scheduled_shifts` | tenant company_id | enabled |
| `sessions` | pre-tenant explicit session/invitation scope | deliberately global/pre-tenant, no RLS |
| `shift_types` | tenant company_id | enabled |
| `shortage_list_entries` | global | enabled |
| `soc_checks` | tenant company_id | enabled |
| `soc_index_entries` | global | enabled |
| `soc_unit_groups` | global | enabled |
| `sponsor_documents` | tenant company_id | enabled |
| `stripe_events` | global | deliberately global/pre-tenant, no RLS |
| `subscriptions` | tenant company_id | enabled |
| `tax_codes` | tenant company_id | enabled |
| `terms_acceptances` | global | deliberately global/pre-tenant, no RLS |
| `terms_versions` | global | deliberately global/pre-tenant, no RLS |
| `timesheet_approvals` | tenant company_id | enabled |
| `trading_hours_days` | tenant company_id | enabled |
| `users` | global | deliberately global/pre-tenant, no RLS |
| `work_log_entries` | tenant company_id | enabled |
| `working_pattern_days` | tenant company_id | enabled |

## Verification results

- Pre-fix export regression: **4 failed / 3 deselected** (all parameterised cases
  returned 200 through generic file metadata instead of 404).
- Pre-fix deletion regression: **1 failed / 4 deselected** (returned 202 instead of
  `403 STEP_UP_REQUIRED`).
- Initial pre-fix billing regression: **2 failed / 13 deselected**; checkout
  returned 200 and cancellation reached plan validation rather than step-up.
- Post export/deletion fixes: **483 API security tests passed**, zero failed/skipped
  in 122.56 seconds. This includes endpoint/RBAC matrices, tenant session and RLS,
  real-router IDOR sweep, file/export/deletion, auth/MFA/session, platform/SSR/support,
  billing/signature/replay, nested mass assignment/SSRF, body limits, trusted IP,
  logs/telemetry, AI redaction, OpenAPI and password/TOTP suites. An earlier isolated
  authorization/RLS pass was **55 passed**; it is subsumed by this run.
- Production header/browser CSP suite: **17 passed**, including setup, enforced
  rejection of missing/wrong/replayed script nonces, matching-nonce positive
  controls, spoofed incoming headers, nonce uniqueness/propagation, cache and
  security headers. The configured web server runs the production build,
  public-env allowlist and static bundle scanner before serving it.
- Fresh migrated database catalog: **103 tables** (102 application + Alembic),
  **zero** missing tenant RLS/updated-at triggers, owner-rights views, materialised
  views or SECURITY DEFINER functions. Runtime `rolsuper=false`, `rolbypassrls=false`.
  79 tables have RLS enabled; the remaining 24 include Alembic and the deliberately
  global/pre-tenant tables shown in the inventory.
- API Ruff check/format: **570 files clean**; mypy: **501 source files clean**.
- Billing component suite after client retry changes: **6 passed**.

The first API probe accidentally overlapped the other agent's full run and had
7 failures/44 setup errors from shared PostgreSQL role-password changes (5 passed).
It is invalid concurrency evidence, not counted as a product failure or pass.
All subsequent database/browser runs use the shared serial lock; the clean
55- and 483-test runs above replace it.
- The improved pre-fix billing probe used a real active plan for cancellation:
  **2 failed / 13 deselected**; both actions returned 200 instead of rejecting
  unauthenticated step-up state. A transition run started before the billing guard
  edit loaded (25 passed / those same 2 failed); the final rerun below uses the
  completed guards.
- Final production browser run after client changes: **18 passed** in 25.4 seconds,
  including setup, all 16 header/CSP cases and the real deletion journey through
  password step-up, emailed-code confirmation and withdrawal.
- Web ESLint and TypeScript passed after the client and test edits; billing
  component tests remain **6 passed**. No OpenAPI shape changed.

- Final API regression run on completed guards: **27 passed / zero failed or
  skipped**, in 24.52 seconds (`test_billing.py`, `test_exports.py`,
  `test_deletion.py`). This includes the seven new security regression cases and
  existing authorized checkout/cancellation/refund, export and deletion flows.
- Post-fix Semgrep rerun: **1,190 files, zero findings, zero errors**. Full-history
  gitleaks checkpoint: **904 commits, zero leaks**. Dependency, configuration and
  workflow inputs did not change after their clean scans.

All three findings are fixed in this block; no deferred P0/P1 was written into
`changesneeded.md`. Production-image CI and the existing deployed checks are
explicit limits of this local report, not local passes.

### Reproduction

Install the scanner versions listed above and use the current checkout. These
are the CI policies; no findings were suppressed or scanner thresholds relaxed.
Local scanner artifacts stay untracked because raw reports can contain source
snippets, URLs or sensitive context.

```sh
gitleaks git --config .gitleaks.toml --redact --no-banner --log-opts=--all
semgrep scan --error --metrics=off --quiet \
  --config p/default --config p/python --config p/typescript --config p/nextjs \
  --config p/dockerfile --config p/github-actions --config p/owasp-top-ten
trivy config --severity MEDIUM,HIGH,CRITICAL --exit-code 1 --skip-version-check \
  --skip-files web/Dockerfile.dockerignore .
actionlint
zizmor --offline --no-progress --min-severity low .github
```

Run frozen Python export/pip-audit and both pnpm policies exactly as in
`.github/workflows/ci.yml` (`audit` job); container image scans remain in its
`images` matrix. In a read-only home directory, set `UV_TOOL_DIR`,
`SEMGREP_SETTINGS_FILE` and `SEMGREP_LOG_FILE` to writable local cache paths.

From `api/`, the 483-case security selection was:

```sh
bash /home/zohaib/cmr_hr/.agent/bus.sh serial -- uv run pytest -q \
  tests/db/test_exports.py tests/db/test_deletion.py tests/db/test_files.py \
  tests/db/test_endpoint_security.py tests/db/test_rbac_enforcement.py \
  tests/db/test_rls_isolation.py tests/db/test_tenant_session.py \
  tests/db/test_pentest_idor.py tests/db/test_auth_flows.py \
  tests/db/test_auth_endpoints.py tests/db/test_platform_session.py \
  tests/db/test_platform_ssr.py tests/db/test_support_mode.py tests/db/test_billing.py \
  tests/test_pentest.py tests/test_body_limits.py tests/test_client_ip.py \
  tests/test_logging.py tests/test_telemetry.py tests/test_ai_redaction.py \
  tests/test_openapi.py tests/test_passwords_and_totp.py tests/test_stripe.py \
  tests/test_rbac_matrix.py
```

The final billing tests add two cases to that selection. `uv run python -m
app.cli check-rls` checks the configured database; the fresh-catalog pass used the
same five drift guards through `tests.db.support.temporary_database()` on fully
applied migrations and checked `pg_roles` plus `pg_class`/`pg_policy` as `app_user`.

From `web/`, production browser verification:

```sh
bash /home/zohaib/cmr_hr/.agent/bus.sh serial -- pnpm exec playwright test \
  tests/e2e/security-headers.spec.ts tests/e2e/journeys/account-deletion.spec.ts \
  --project production
```
