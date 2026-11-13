# Privacy review and data map (T21.5)

Reviewed against the implementation on 13 November 2026. This is engineering evidence, not
legal approval. Legal pages remain drafts requiring solicitor review. The tenant company decides
why it holds employee/candidate data; the service processes it for that company. Platform account,
security, support and billing processing have separate operational purposes. Confirm contracts,
controller roles, regions, transfer safeguards and retention notices before launch (T23.4).

## Data map

The complete table inventory is `api/app/db/registry.py`; column definitions, encryption and
foreign keys are in the corresponding model files. All tenant-table reads use RLS plus an
explicit company context. Platform access additionally requires its guarded session and permission.
The background worker has owner credentials for narrowly scoped cross-company jobs.

| Data and source | Purpose and primary store | Access / onward flow | Retention and removal |
| --- | --- | --- | --- |
| Users, names, email, password hashes, MFA, memberships, invitations; registration/admin entry | Account/authentication; Postgres `users`, `memberships`, `invitations`, `email_tokens`, `sessions`; Redis hashed-token session cache and expiring rate-limit/MFA keys | User, authorised company admins, guarded platform operations; transactional mail | Credentials never enter export. Sessions removed 90 days after expiry or revocation; cache has its own TTL. Users belonging only to a deleted tenant are removed or anonymised if referenced by retained history; multi-tenant users remain. |
| Company identity, contacts, key personnel, structure and company evidence; company admin | Administration and sponsor compliance; Postgres company/structure/personnel tables; private object files | Permission-scoped tenant views, company export, explicit mail notices, company-number/postcode lookups | Kept while account exists, removed by confirmed company deletion; payment identifiers retained in scrubbed company stub. |
| Employee identity/contact/address, NI/passport, emergency contacts, bank, assignments, compensation, employment and education; HR entry/import | HR record; Postgres employee tables, sensitive identifiers encrypted and NI blind indexed; private photos/documents | RBAC and field masks; authorised HR/pay/report/export flows; no direct vendor DB access | Ordinary archive preserves HR history; not a deletion request. Company deletion removes it. No invented general HR/payroll retention duration; tenant must set its operational/legal schedule. |
| RTW check history, share code, checker, outcome and evidence; HR checks | Right-to-work evidence; encrypted code in `rtw_checks`, `employee_documents` category `rtw_evidence`, private files | Permission-scoped RTW views and explicit downloads; export excludes share codes | All employee RTW versions and RTW-category document links expire on the second calendar anniversary of a dated leaver's `leave_date`; unreferenced bytes and file metadata removed. Candidate checks with no employment end date remain for tenant review. |
| Visa/passport/other sponsor document versions, CoS, salary, expiry and changes; HR entry | Sponsor compliance; `sponsor_documents`, `change_of_circumstances`, `org_changes`, reminders; private evidence | Permission-scoped compliance views/reports; company export; restricted values barred from AI | Sponsor documents expire one calendar year after a dated leaver, conservatively extended to the latest recorded visa expiry if later. Shared RTW evidence remains through its longer purpose. Change-report/audit snapshots are distinct history and persist until company deletion. |
| Attendance, clock location (explicit action), rota, work logs, leave/health, pay, policies, learning and receipts; employees/managers | Employment administration; tenant Postgres tables, scanned documents and generated reports | Own/team/all scopes and explicit approval/export; emails and digests use purpose-specific templates | History kept while account exists; company deletion purges it. Generated exports have a seven-day artifact life. Other generated report retention is not silently inferred from export policy. |
| Candidate identity, contact, CV, application consent and recruitment notes; public application/HR | Recruiting; `postings`, `candidates` and related tenant records; private scanned CV files | Hiring permissions and tenant export; SOC CV AI only after explicit user action | Tenant recruiting purpose/account lifetime; no automatic rejection-to-delete interval specified. No CV/prompt body in logs or telemetry. |
| Public contact/complaint submissions and register reports; visitor entry | Responding/moderation; global contact and register-report records | Guarded platform inbox; mail outbox/Resend | Not tenant data and not removed by a company's deletion. Platform operator must agree the separate support/complaint schedule before launch. |
| Sponsor/public company names, numbers, addresses, geocodes, SIC and publication differences; GOV.UK/ONS/Companies House bulk data | Public directory and provenance; global register snapshots, reduced bulk indexes and changes | Public explorer/profile/bulletin; upstream public downloads only | Publication history retained separately from tenant HR; public data can still identify sole traders. Correction/report channel and methodology explain provenance. |
| AI request inputs and outputs; explicit letter/reminder/SOC actions | Anthropic API; no stored prompts/answers; `ai_interactions` stores feature/model/status/counts/timing only | Restricted keys dropped, names labelled, identifier-like text stripped, final wire body checked; company and environment AI switches | Metadata removed at 30 days. No provider call without key/feature enabled. Ask Mady chat remains deferred. Provider retention/transfer terms require contract review. |
| Email recipient, template and encrypted variables; application events | Delivery/retry; encrypted `email_outbox`, Resend (Mailpit locally) | Recipient and configured mail provider; no address/payload in operational logs | Delivery bookkeeping is not a consent/marketing list. Global outbox/final deletion notices can outlive the tenant; provider and outbox retention must be configured operationally. |
| Subscription, Stripe customer/payment references and webhook bookkeeping | Billing; tenant subscriptions plus Stripe independent controller | Restricted Stripe API key, guarded billing UI, webhook signature checks | Accounting/subscription records survive tenant deletion as specified; solicitor/operator must confirm the applicable accounting retention period. No card data stored by this app. |
| Audit actor, IP, user agent, action, reason, masked snapshots; sensitive operations | Accountability; append-only Postgres `audit_events` | Tenant audit permission and guarded platform operations | Not a session-log table. Preserved while company exists; company purge leaves only `company.deleted` stub with company ID/date and no actor. Global platform audit history is separate. |
| Request ID, method/path/status/timing, job counts/error kinds; API/worker | JSON stdout; hosting log service. Sentry gets sanitised exception structure only when configured | Operational access; no request query in HTTP access log. SDK payload excludes request, user, breadcrumbs, tags, extras, locals, source text and exception messages | Hosted log/Sentry retention, access and regions must be configured in T23.4. Scrubbing is verified in local SDK transports; actual vendor receipt is a deployment check. |
| Encrypted DB backups and infrastructure access logs | Disaster recovery / infrastructure security; Railway plus planned separate encrypted backup bucket | Restricted operators only; Cloudflare handles edge traffic and Turnstile | Planned backup retention 35 days; nightly backup job remains a separate unfinished control, not completed by this review. Restore must reapply deletions/retention before traffic resumes (T25.3). |

## Active retention implementation

`api/app/jobs/retention.py` replaces the placeholder in `SCHEDULE`: daily at 02:00 UTC,
wrapped in the existing job audit/error tracking. Missing owner credentials fail visibly instead
of reporting a successful zero-row run. A running deployed worker and storage credentials are
required; local registration is not evidence that production cron has run.

Calendar-year cutoffs are inclusive; 29 February rolls to 28 February. Only `leaver`/`archived`
with a known leave date qualifies for evidence expiry. Active/unknown-date employees and candidate
checks are not guessed to have ended. HR must maintain these dates; stopping sponsorship before
employment ends needs manual review because there is no dedicated sponsorship-end field. The
conservative visa-expiry extension avoids deleting ongoing permission evidence prematurely;
reconcile this policy with the solicitor and add an explicit sponsorship-end workflow if required.

The worker uses the existing owner-only, company-bound purge capability for immutable evidence;
ordinary API users still cannot delete history. It removes all versions together, collects only
those evidence files, and checks every registered file foreign key before deleting bytes. Files
shared with an unexpired record survive for that other purpose. A fresh-process test ensures the
worker loads **all** models before export, deletion or file-reference inspection.

AI metadata: `created_at <= now - 30 days`. Sessions: `expires_at` or `revoked_at <= now - 90 days`;
active sessions are preserved. Expired export archives are deleted, and requests become
`failed/EXPIRED` with their file/expiry cleared, satisfying existing database constraints. The
controller's underlying records are unaffected by artifact expiry.

Storage deletion precedes database commit, matching company deletion. Storage errors abort the
transaction and the next run retries; deleting an absent object is idempotent. R2 and Postgres
cannot share a transaction: a crash after bytes are removed can temporarily leave a dead reference
until retry. Monitor failed jobs and reconcile immediately. No sensitive row or object key is
written into the job audit; only handled counts/error class.

## Export and deletion verification

`tests/db/test_exports.py` and `test_export_isolation.py` exercise real worker archives, own-tenant
rows/documents, requester-only expiring links, step-up, role revocation, and exclusions (session,
credential/code hashes, bank account fields, share codes, IP and storage keys). This is the company
export defined by T16.4, not a complete individual subject-access response; excluded personal data
needs an authorised response through the relevant HR process.

`tests/db/test_deletion.py` exercises the six-digit confirmation, seven-day window, withdrawal,
permissions/isolation, Stripe cancellation failure/retry, actual object/tenant purge, multi-company
users and the retained company/audit/accounting stubs. It runs the real executor against test
storage and a Stripe fake; real Stripe test-mode delivery remains parked separately in L1.

## AI, logging and Sentry verification

`tests/test_ai_redaction.py` captures the actual Anthropic HTTP request after 200 independently
seeded fuzz cases, checks restricted identifiers and employee names, and proves an unsanitised
body is refused before transport. It checks the boundary, not a real model response.

`api/app/core/logging.py` recursively drops the specification's sensitive keys plus health,
contact/identity and body/payload/prompt carriers, masks URL credentials and labelled secrets,
and redacts NI/passport/share-code/salary patterns even in third-party messages. HTTP client INFO
URLs and uvicorn query-bearing access logging stay disabled. Tests capture JSON emitted by both
structlog and stdlib logging, including formatted exceptions. This does not make arbitrary free
text safe: callers must continue logging fixed event names and approved metadata, never records,
CVs, addresses, employee names or exception bodies containing those values.

`api/app/core/telemetry.py` and `web/lib/security/telemetry.ts` allowlist event ID/time/platform/level
and exception class with symbol/line-only frames. Everything else is discarded, including exception
messages, request bodies, cookies/headers, URL/query, source context/locals, user, extra, tags and
breadcrumbs. Before-send never inspects the raw SDK hint. Automatic integrations, tracing and
breadcrumbs are disabled; browser global error handlers, Next request errors, API unhandled errors
and failed worker jobs use this same boundary. No DSN means no reporting. No replay, console capture
or AI instrumentation is enabled.

Python SDK 2.73 replaces deprecated `send_default_pii=False` with explicit `data_collection` category
opt-outs, including user info, cookies, bodies, query parameters and stack variables. Browser uses
`sendDefaultPii: false`. The final before-send allowlist applies regardless of SDK collection changes.
Tests use actual Python/browser SDK transports and assert that sensitive sentinels never enter the
event payload. See the [Python SDK options](https://docs.sentry.io/platforms/python/configuration/options/)
and [Next.js SDK setup](https://docs.sentry.io/platforms/javascript/guides/nextjs/manual-setup/).

Before launch (T23.4), send synthetic failures in web/API/worker on staging, verify reception with
no PII in each configured project, and set vendor retention/access/region. Verify the daily job's
successful `job.finished` audit and a repeat no-op against synthetic expired data, and validate
source maps without publishing sensitive source. Real vendor receipt and deployed scheduling
cannot be claimed from the local transport tests.
