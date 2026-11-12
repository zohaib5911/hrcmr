# micro_plan.md — the step-by-step work list (remaining work only)

This is what you build next, in order. `plan.md` is still the **spec** (what each feature must do).
This file is the **route** (which task, which files, which steps, how to check).
If the two disagree on *behaviour*, `plan.md` wins: write the conflict under "Issues" in `STATUS.md`.
Tasks T0.1–T10.2 are done and are not listed here.

---

## A. How to use this file (read once per session, ~2 minutes)

1. Run `bash .agent/next.sh`. It prints the next block to do: open items from `changesneeded.md`
   first, otherwise the first `### [ ]` block below. Do only that block.
2. The block's **Spec** line names exact `plan.md` lines. Read only those lines:
   `sed -n 956,985p plan.md`. Don't read the whole plan.
3. The **Copy** line names existing files that already solve the same kind of problem.
   Open them, then copy their structure, naming, error style and test style. Don't invent a new pattern.
4. Each numbered **Step** is one sub-step = one checkpoint (journal line + commit + push; see AGENTS.md §2).
5. When **Done when** passes: tick the block (`sed -i 's/^### \[ \] T11.1 /### [x] T11.1 /' micro_plan.md`),
   tick the same id in `PROGRESS.md` with one line, update `STATUS.md`, and make the final `feat(...)` commit.

### Tier tags (in every block title)
- **S**: a small model may do it.
- **S!**: a small model may do it, but it is high-risk. Follow every "Watch" line exactly; the auditor checks these first.
- **B**: **BIG-MODEL ONLY.** A small model must **not** start it; it stops with the "BIG MODEL TASK" message (AGENTS.md Quick start).
- **AUDIT STOP**: small models stop with the "AUDIT NEEDED FIRST" message; a big model runs `audit.md`.
  Only the auditor ticks AUDIT blocks.
- Which models are BIG or SMALL, and the exact stop messages: AGENTS.md "Quick start".

### Hard rules for every task (small models: these are where mistakes happen)
- **Never invent a figure.** No rate, fee, threshold, date rule or legal fact may be typed from memory. It comes from
  `web/rates/*.json`, from the rules data (T15.2), or from a GOV.UK page whose URL you cite next to it.
  If you need a figure that is not there: STOP with `BLOCKED — needs verified figure (<what>)`.
- **Never fake a test result.** Paste the real pass/fail counts into the journal. If a test fails and you can't fix it,
  say so in STATUS and set BLOCKED. Never mark `skip`/`xfail`, never delete or weaken an existing assertion to go green.
- **Every new endpoint:** permission via `require("<perm>")` (`api/app/modules/rbac/deps.py`), tenant-scoped query,
  404 for another company's id, audit event for sensitive writes **in the same transaction**, Pydantic models that
  extend the existing `RequestModel` (unknown fields refused). A test for: allowed role OK, disallowed role 403,
  other tenant 404.
- **New permission names** go in `api/app/core/rbac_matrix.py` (plan §7, L628–691) and the matching web gate in
  `web/lib/auth/access.ts` / `web/lib/navigation.ts`. Don't grant a permission to a role unless §7 says so.
- **New dependency** only if the block names it. `uv add <pkg>` / `pnpm add <pkg>`; the 14-day cooldown applies;
  if install refuses a too-new version, pin the newest allowed one.
- **AI code** runs only when `ANTHROPIC_API_KEY` is set **and** the company's `ai_features_enabled` is true. Otherwise the
  endpoint returns the existing "feature unavailable" error, the UI hides the button, and the non-AI fallback works.
- Don't refactor or restyle earlier work. Put suggestions under "Issues / suggestions" in STATUS.
- Never run DB pytest and Playwright at the same time (they share PostgreSQL role passwords).

---

## B. Standard recipes (blocks say "Recipe R1" etc. instead of repeating these)

**R1 — Backend module** (copy `api/app/modules/work_log/` for simple, `api/app/modules/policies/` for complex)
1. `models.py` (tenant tables carry `company_id`, as in the copied module) → add one import line in `api/app/db/registry.py`.
2. Migration in `api/alembic/versions/` named `YYYYMMDD_00NN_<name>.py` (next number after the last file).
   Copy the RLS policy lines from `20261104_0032_policy_signoffs.py`. Check with `uv run python -m app.cli check-rls`.
3. `schemas.py` → `service.py` (logic, no FastAPI imports) → `router.py` → register in `api/app/main.py` next to the others.
4. Regenerate: `uv run python -m app.cli export-data-model --output ../docs/data-model.md` (in `api/`),
   then `pnpm gen:api` (in `web/`).
5. Tests in `api/tests/db/test_<module>.py`, copying `api/tests/db/test_work_log.py` (fixtures from `tests/db/support.py`).

**R2 — App screen** (copy `web/app/(app)/work-log/page.tsx` + `web/components/work-log/`)
- Page in `web/app/(app)/<route>/page.tsx`; components in `web/components/<area>/`; use only `web/components/ui/*`.
- Data through the typed client in `web/lib/api/client.ts` (never hand-written fetch types).
- Loading, empty, error and success states; light and dark; 360 px works; keyboard reachable.
- Nav entry (if any) in `web/lib/navigation.ts`, gated by permission.

**R3 — Background job** (copy `api/app/jobs/compliance.py` + its entry in `api/app/jobs/scheduled.py`)
- Times in plan §11 (L1644–1660) are Europe/London; `scheduled.py` fields are UTC, so follow how existing jobs convert.
- The job must be idempotent (safe to run twice) and tested by calling the function directly.

**R4 — PDF** (copy `api/app/modules/employees/record_pdf.py`, WeasyPrint + Jinja). **XLSX**: copy `api/app/modules/reports/workbooks.py`.

**R5 — Public (no-login) endpoint/page**
- Rate-limited (copy `api/app/core/rate_limit.py` usage), Turnstile on every POST (`api/app/integrations/turnstile.py`),
  returns only the fields the spec lists, and a test proves nothing else leaks.
- Uploads go through `files` + the ClamAV scan (copy the employee documents upload).

**R6 — Browser test** (copy `web/tests/e2e/work-log.spec.ts`, helpers in `web/tests/e2e/helpers.ts`)
- One happy path + one forbidden-role check. Wait for hydrated data; target visible roles (see STATUS issues).
- Run one spec only: `cd web && pnpm exec playwright test <name>.spec.ts --project=production`.

**R7 — Phase gate** (every `Phase N gate` block)
1. Commit and push first. Full suite once: `cd api && uv run pytest -q`, then `cd web && pnpm lint && pnpm typecheck && pnpm test && pnpm test:e2e`.
2. Screenshots 390 + 1280 px, light + dark, of the phase's new screens into `docs/screenshots/phase-N/`
   (copy `web/tests/e2e/phase9-screenshots.spec.ts`).
3. 5-line phase summary in `PROGRESS.md`. Tick the gate.
4. PR: `gh pr create --base main --head dev --title "Phase N" --body "<summary>"`.
   Wait for checks yourself: `gh pr checks <n> --watch`. Only when all are green: `gh pr merge <n> --merge`.
   Never `--admin`. If red: fix on `dev`, push, watch again.

### Commands (run from the folder shown)
| What | Command |
|---|---|
| Stack up (repo root, once) | `docker compose up -d --wait` |
| API lint/types (`api/`) | `uv run ruff check . && uv run ruff format --check . && uv run mypy` |
| API tests, one file (`api/`) | `uv run pytest -q tests/db/test_<x>.py` |
| Web checks (`web/`) | `pnpm lint && pnpm typecheck && pnpm test` |
| Web unit, one file (`web/`) | `pnpm exec vitest run <path>` |
| Typed client stale? (`web/`) | `pnpm gen:api:check` |

---

## C. Plan line index (`plan.md`)
Definition of Done L34–44 · Security §4 L168–295 · Design QA §5.12 L439–451 · Data model §6 L452–627
(6.7 docs L572 · 6.8 recruitment L581 · 6.9 learning L593 · 6.10 SOC L598 · 6.11 billing/AI L609 · 6.12 public L617) ·
Roles §7 L628–691 · Module specs: 8.10 L927–955 · 8.11 L956–985 · 8.12 L986–1000 · 8.13 L1001–1011 · 8.14 L1012–1029 ·
8.15 L1030–1075 · 8.16 L1076–1096 · 8.17 L1097–1153 · 8.18 L1154–1176 · 8.19 L1177–1198 · 8.20 L1199–1230 · 8.21 L1231–1251 ·
Phase tasks §9: P10 L1410 · P11 L1416 · P12 L1424 · P13 L1428 · P14 L1434 · P15 L1442 · P16 L1455 · P17 L1463 · P18 L1471 ·
P19 L1477 · P20 L1484 · P21 L1490 · P22 L1497 · P23 L1503–1542 · P24 L1543 · Calculators §10 L1555–1584 ·
API catalogue §11 L1585–1661 · Launch checklist §12 L1662–1680 · Reference facts §13 L1681–1695.

---

## Phase 10 — Documents, policies and reports (finish)

### [x] T10.3 · S! · Policies and sign-offs (finish; steps 1–4 already done by Codex)
- **Spec:** plan L945–955 (8.10 policies + My Documents), L1414, API §11 item 14 (L1624).
- **Copy:** `api/app/modules/policies/*` (already built), `api/app/jobs/compliance.py`, `web/components/documents/`, `web/app/(app)/my-documents/page.tsx`.
- **Steps:**
  5. `POST /policies/{id}/remind` (pending recipients only) + daily job (R3) that marks overdue and notifies, + automatic assignment
     to new starters for policies with "send to new starters" (hook where an employee is created/hired). Tests in `api/tests/db/test_policies.py`.
  6. UI (R2): `/policies` list with acceptance progress bar; 3-step "New document" sheet (Details → Upload file → Recipients & send);
     `/policies/[id]` detail (accepted / signed / pending / overdue, Remind, New version); My Documents policy section with viewer,
     "I have read and accept" or typed-name signature, receipt.
  7. R6 spec `web/tests/e2e/policies.spec.ts`: send → employee signs → admin sees "Signed"; Employee role cannot open `/policies`.
- **Done when:** steps pass; `pnpm gen:api:check` clean; affected API tests green.
- **Watch:** keep the sponsor reminders already on My Documents. Viewer `frame-src` allows only the configured API origin.
  Sent versions are frozen (edits need a new version). Signature text is encrypted and never enters audit.

### [x] T10.4 · S · "Draft with AI" UI and API contract (feature-flagged)
- **Spec:** plan L933–938, L1415; API `POST /ai/letters/draft` (L1623); AI rules L986–1000.
- **Copy:** `api/app/modules/documents/`, `web/components/documents/`.
- **Steps:**
  1. API `POST /ai/letters/draft` in a new `api/app/ai/letters.py` router: input letter type (7), tone (3), key points (list, max 10 × 200 chars).
     For now it returns a **template draft** built from original placeholder text (`[Employee name]`, `[Start date]` …), no AI call.
     Response carries `source: "template" | "ai"`. Permission `document.file.write`. Test: placeholders only, no names accepted.
  2. Web sheet on `/documents`: type, tone, key-points list input → editable draft; actions Copy, Download .docx, Save as company document.
     The button label says "Draft with AI" only when `/auth/me` reports AI available; otherwise "Start from template".
  3. `.docx` download: add `python-docx` (API) and generate server-side, or build client-side from text; choose the simpler, record it in STATUS decisions.
- **Done when:** the template draft works with no key set; key points with an email/NI-number pattern are rejected (422); gen:api clean.

### [x] P10 · S · Phase 10 gate
- Recipe R7. Screens: documents, reports, policies list/detail/wizard, My Documents.

---

## Phase 11 — Recruitment and public careers

### [x] T11.1 · S · Requisitions
- **Spec:** plan L956–967, L1417; data model §6.8 L581–592; API item 15 (L1625–1627).
- **Copy:** R1 from `api/app/modules/work_log/`; status-change pattern from `api/app/modules/leave/` (approve).
- **Steps:**
  1. `api/app/modules/recruitment/` models (requisitions, plus the postings/candidates/applications/interviews/offers tables from §6.8 so one migration covers recruitment) + migration + registry.
  2. Requisition CRUD + `PATCH /requisitions/{id}/status`. Only `recruitment.requisition.approve` may set Open; stamps approved_at/by. Cancel = status Cancelled. Audit on status change.
  3. `/recruitment` page shell: intro line, 4 KPIs (`GET /recruitment/summary`), tabs Requisitions/Postings/Candidates/Applications with counts; Requisitions tab with sheet and status select (Cancel asks to confirm).
- **Done when:** non-approver setting Open → 403; approver → stamped; cross-tenant 404; page works.

### [x] T11.2 · S · Postings
- **Spec:** plan L966–969, L1418.
- **Steps:**
  1. Posting CRUD + `PATCH /postings/{id}/status` (Draft/Open/Closed). Create requires an **Open** requisition (else 422). Slug unique per company.
  2. Postings tab: full sheet (fields in L966–967), SOC code as a plain text field with a disabled "Find code" button (wired in T15.6), "Start from template" JD + "Writing it safely" expandable guide (original copy), visa-sponsorship select.
  3. Table with public link column (External + Open only, Copy button). Closing asks to confirm.
- **Done when:** closed posting → its public link field is null; posting on a non-Open requisition refused.

### [x] T11.3 · S · Candidates
- **Spec:** plan L974–977, L1419. RTW reuse: `GET/POST /candidates/{id}/rtw-checks` (L1601).
- **Copy:** RTW forms from `web/components/compliance/` / `api/app/modules/rtw/` (reuse, don't duplicate the forms).
- **Steps:**
  1. Candidate CRUD (first, last, email, phone, source) + documents (copy employee documents) + candidate RTW endpoints reusing the rtw service with a candidate owner.
  2. `/recruitment/candidates/[id]`: header (initials, name, RTW status, source, email; actions Apply to posting, Convert — disabled until T11.5), tabs Overview / Applications / Right to Work / Documents / Sponsorship check (placeholder text "Available after the checker launches" until T15.6).
- **Done when:** a candidate RTW check records and shows its status; cross-tenant 404.

### [x] T11.4 · S · Applications, interviews, offers
- **Spec:** plan L957–961 (pipeline), L978–983, L1420.
- **Steps:**
  1. Applications: create (candidate + posting), `POST /applications/{id}/stage`. **Forward moves one step only**, error text exactly "The next step from X is Y"; backward allowed; Rejected/Withdrawn end it. History rows with timestamps. Unit-test every stage pair.
  2. Interviews CRUD; on create, e-mail an `.ics` invite to interviewers and candidate (copy e-mail outbox usage from `api/app/modules/email/outbox.py`; build the .ics text by hand, RFC 5545, test its fields).
  3. Offers: create (role title, salary + per, start date) → Sent → Accepted/Declined via `PATCH /offers/{id}`.
  4. UI: pipeline bar (8 stages, counts, click filters Applications tab); `/recruitment/applications/[id]` with stepper, "Move to {next}", "Waiting on…" hint, interviews and offers panels.
- **Done when:** skipping a stage → 422 with the exact message; .ics test passes; pipeline counts match DB.

### [x] T11.5 · S! · Convert to employee
- **Spec:** plan L984, L1421, §13 L1694.
- **Copy:** employee creation in `api/app/modules/employees/` (call its service; don't duplicate it).
- **Steps:**
  1. `POST /applications/{id}/convert`: server checks **Accepted offer AND a Verified RTW check** (both, in the same transaction). Creates employee prefilled, hire date = offer start date, links RTW check and documents, application → Hired. Audit event.
  2. UI: Convert button enabled only when both gates pass, with a sheet showing the prefilled data.
- **Done when:** tests for: no offer → refused; offer not Accepted → refused; RTW not Verified → refused; both OK → employee exists, links set, one audit event; repeat call → refused (no duplicate employee).

### [x] T11.6 · S! · Public careers pages and apply form
- **Spec:** plan L970–973, L1422; public API L1636 (item 24).
- **Copy:** Recipe R5; `web/app/careers/[company]/` (folder exists, empty); marketing layout `web/app/(marketing)/layout.tsx`.
- **Steps:**
  1. Public API: `GET /public/careers/{company_slug}`, `GET /public/postings/{company_slug}/{posting_slug}` (External + Open only; others 404).
  2. `POST .../apply`: Turnstile, rate limit, optional CV upload through files + ClamAV, privacy consent required; creates candidate + application `applied_via=careers_page`; confirmation e-mail to applicant; notification to users with recruitment permission.
  3. Pages `/careers/[company]` and `/careers/[company]/[posting]` with the apply form.
- **Done when:** closed or Internal posting → 404 page and apply refused; response bodies contain only listed fields (test); missing Turnstile → refused.

### [x] P11 · S · Phase 11 gate
- Recipe R7. Screens: recruitment tabs, application detail, candidate profile, careers list/detail.

### [x] AUDIT-1 · AUDIT STOP · covers T10.3 → P11

---

## Phase 12 — Org chart

### [x] T12.1 · S · Tree API and hierarchy levels
- **Spec:** plan L1001–1011, L1425; API item 16 (L1628).
- **Steps:**
  1. `GET /organogram`: tree from Reporting Authority on **current** assignments; people without a manager under `unassigned`; cycle-safe (test a cycle doesn't hang). Visa/RTW chips only if the user has `employee.rtw.read`.
  2. Hierarchy levels CRUD (ordered list, default "Director"), labels only.
- **Done when:** tree matches a seeded 3-level fixture; cycle test passes; cross-tenant isolation test.

### [x] T12.2 · S · Canvas, list view, unassigned section, PDF export
- **Spec:** plan L1003–1010, L1426.
- **Steps:**
  1. `/organogram` canvas: pan by drag, zoom buttons + pinch, search jumps to a name, click opens inspector, "Show visa status" toggle. Build with plain SVG/CSS transforms (no new library).
  2. List view toggle and Unassigned section; keyboard reachable.
  3. `GET /organogram.pdf` (R4), multi-page for large teams.
- **Done when:** R6 spec: search finds a person and opens inspector; PDF endpoint returns a PDF for a 60-person fixture.

### [x] P12 · S · Phase 12 gate
- Recipe R7.

---

## Phase 13 — Learning

### [x] T13.1 · S · Course model, minimal editor, course player
- **Spec:** plan L1012–1029, L1429; §6.9 L593–597; API item 17 (L1629).
- **Steps:**
  1. Global (not tenant) `courses` with sections, quiz, sources (title, publisher, URL, source-updated date), reviewed date, OGL attribution; tenant `learning_assignments`. Migration.
  2. Minimal super-admin course editor under `web/app/(admin)/platform/courses/` (copy `platform/dossier-links`).
  3. Course player: section by section, progress saved (`POST /learning/assignments/{id}/progress`), keyboard friendly, quiz with pass mark.
- **Done when:** progress survives reload; quiz below pass mark doesn't complete.

### [x] T13.2 · S! · Write the 8 original courses
- **Spec:** plan L1014–1023, L1430.
- **Steps:** one course per sub-step (8 commits), as seed data files in `api/seed/courses/`. Each: 5–6 sections, 15–25 min, a 5-question check with explanations, sources from GOV.UK / ACAS / EHRC with URL + their updated date, reviewed date = today, OGL attribution if adapted.
- **Done when:** a test checks every course has ≥5 sections, exactly 5 questions, ≥1 source URL on gov.uk/acas.org.uk/equalityhumanrights.com. Owner action "Review the 8 courses" added to PROGRESS.
- **Watch:** write fresh text; no copying from GOV.UK/ACAS beyond short quotes; no legal figures unless the source page states them (cite it).

### [x] T13.3 · S · Assign wizard, report view and export, overdue job, My Learning
- **Spec:** plan L1024–1027, L1431.
- **Steps:**
  1. `POST /learning/assignments` (courses × people: everyone / departments / named, one due date); report list with filters; `GET /learning/assignments.xlsx` (R4).
  2. Overdue job `learning_overdue` 06:15 (R3) + notification.
  3. UI: `/learning` KPIs, Report and Courses views, 3-step assign wizard; `/learning/my` (Assigned to me / All courses).
- **Done when:** assigning twice doesn't duplicate; overdue job idempotent; Employee role sees only own.

### [x] T13.4 · S! · Certificates and public `/verify`
- **Spec:** plan L1027–1028, L1432; API `GET /certificates/{id}.pdf`, `GET /public/certificates/verify?ref=`.
- **Steps:**
  1. On completion: certificate with random reference (≥ 10 chars, from `secrets`, unguessable), PDF (R4).
  2. Public verify endpoint (R5): returns only holder name, course title, completion date, status. Page `/verify`.
- **Done when:** test asserts the verify response has exactly those 4 fields; rate limit test; unknown ref → generic "not found".

### [x] P13 · S · Phase 13 gate
- Recipe R7.

---

## Phase 14 — Dashboard, notifications, search, AI

### [x] T14.1 · S · Dashboard API, cards and setup checklist
- **Spec:** plan §8.2 (find with `grep -n '### 8.2' plan.md`, read to 8.3), L1435; API item 18.
- **Steps:**
  1. `GET /dashboard`: one aggregated, permission-aware response (each card omitted if the user lacks its permission). Reuse existing services; no new queries where a service exists.
  2. `GET /onboarding/checklist` + dismiss.
  3. Cards UI per 8.2 on `/dashboard`.
- **Done when:** Employee role response has no company-wide cards (test); page renders all states.

### [x] T14.2 · S · Notifications
- **Spec:** plan L1193–1196, L1436.
- **Steps:**
  1. Ensure `notifications/router.py` lists every kind now produced (policy, rota.published, course, recruitment); `PATCH /notifications/{id}`, `POST /notifications/read-all`, `GET/PUT /me/notification-preferences` (immediate / daily / off).
  2. Daily digest job (R3) honouring preferences.
  3. Bell list with "Needs attention" + personal, mark all read, links.
- **Done when:** a user never sees another user's notifications (test); digest idempotent.

### [x] T14.3 · S! · Command palette live search
- **Spec:** plan L1178, L1437; `GET /search?q=`.
- **Copy:** existing palette in `web/components/app/` (pages + recent already exist).
- **Steps:** API search over employees + candidates **only where the user has read permission**, max 8 each, min 2 chars; add People + Actions groups to palette.
- **Done when:** user without `employee.profile.read` gets no employees (test); other-tenant names never returned (test).

### [x] T14.4 · B · Anthropic integration, redaction layer, tools, assistant panel
- **Spec:** plan L986–1000, L1438, L1440–1441. Big model: also write the Phase 14 payload fuzz test here.

### [x] T14.5 · S · Wire AI into letter drafting and reminder wording
- **Spec:** plan L1439. Needs T14.4 done.
- **Copy:** `api/app/integrations/anthropic.py` (from T14.4) and its redaction helper — call them; never call the SDK directly.
- **Steps:**
  1. `/ai/letters/draft` uses Claude when available (`source: "ai"`), else the template (T10.4). Only type, tone and key points are sent.
  2. Reminder review drawer (T7.4) gets an AI-worded message when available, else the current template.
- **Done when:** with no key, both still work (test); a test asserts the outgoing payload has no employee names/identifiers (reuse T14.4's assertion helper).

### [x] P14 · S · Phase 14 gate
- Recipe R7 + run the T14.4 fuzz test.

### [x] AUDIT-2 · AUDIT STOP · covers T12.1 → P14 (and T14.4 by the big model)

---

## Phase 15 — Sponsorship Job Checker (SOC)

### [x] T15.1 · S! · ONS SOC data import and local embeddings
- **Spec:** plan L1151, L1443; §6.10 L598–608.
- **Steps:**
  1. Add `fastembed` and pgvector (Postgres extension + `pgvector` Python package). Migration for global `soc_unit_groups`, `soc_index_entries` with a vector column and a trigram index.
  2. `data/import_soc.py`: download ONS SOC 2020 coding index + structure/descriptions; save raw files in `data/raw/` with SHA-256 and source URL in a sidecar `.json`; load tables; compute embeddings.
  3. Small fixture (≈50 rows) under `api/tests/fixtures/soc/` for tests; tests never download.
- **Done when:** importer is re-runnable (no duplicates); fixture import test passes; row counts recorded in PROGRESS.
- **Watch:** find the ONS download URLs from the ONS site and record them; if not found, BLOCKED.

### [x] T15.2 · B · Rules-data importer (draft rules version, fixtures, salary rules)
### [x] T15.3 · B · Rules engine and 20+ golden tests

### [x] T15.4 · S! · Search and match API
- **Spec:** plan L1127–1131, L1446; API item 20.
- **Steps:**
  1. `GET /soc/search?q=` (trigram + full-text + vector, top 10).
  2. `POST /soc/match`: retrieval → Claude re-rank via the T14.4 integration with a JSON schema (confidence 0–100, matched duties, why runner-ups lost) → rules engine (T15.3) on top 3. Without AI: return retrieval order with `confidence: null` and a "not AI-ranked" flag.
- **Done when:** works with and without key (tests mock the AI client); confidence < 60 flagged `low_confidence`.

### [x] T15.5 · S! · CV match
- **Spec:** plan L1139–1141, L997.
- **Steps:** PDF/DOCX text extraction (pypdf / python-docx), **strip e-mail, phone, address and postcode patterns before sending** (unit tests with many formats), Claude comparison → score, evidence quotes, gaps, suggestions. Honesty guardrail text in the prompt (L1143–1146).
- **Done when:** stripping tests pass; payload test proves no contact details leave; feature hidden without key.

### [x] T15.6 · S · Checker UI, "Find code" embeds, PDF report
- **Spec:** plan L1125–1142, L1143–1146, L1448.
- **Steps:** 1. `/sponsorship-checker` inputs form. 2. Results page (best match card, 2 alternatives, eligibility chip, salary table, verdict, notes, disclaimer + rules version). 3. "Confirm this code" → `soc_checks` + PDF (R4) + fills posting/sponsor doc/designation SOC. 4. "Find code" embeds (posting sheet, candidate Sponsorship tab, visa form, designation); history list.
- **Done when:** R6 spec: check → confirm → PDF downloads; disclaimer always visible.

### [x] T15.7 · S! · Daily rules watcher and super-admin diff/publish/rollback
- **Spec:** plan L1147–1150, L1449.
- **Steps:** `rules_watch_daily` 07:00 (R3) using ETag/hash → imports into a **draft** via T15.2's importer; admin screen under `web/app/(admin)/platform/rules/` with diff, Publish, Rollback (Platform Admin only, audited).
- **Done when:** unchanged pages → no new draft; publish requires platform permission (test); old checks keep their rules version.

### [x] T15.8 · S · Public free version
- **Spec:** plan L1152, L1450; public SOC endpoints (item 24).
- **Steps:** R5 endpoints `/public/soc/search`, `/public/soc/{code}`, `/public/soc/salary-check`; page `/resources/tools/sponsorship-job-checker` (title search + salary table, no CV, no AI unless Turnstile passes).
- **Done when:** rate limit test; no tenant data reachable.

### [x] P15 · S · Phase 15 gate
- Recipe R7.

---

## Phase 16 — Billing and account lifecycle

### [x] T16.1 · B · Stripe integration and webhooks
### [x] T16.2 · B · Entitlements and payment-failed grace

### [x] T16.3 · S! · Billing page, cancel with refund
- **Spec:** plan L1084–1090, L1459.
- **Copy:** the Stripe client from T16.1 (`api/app/integrations/stripe*.py`); never call Stripe elsewhere.
- **Steps:** `/company/billing` plan card, 14-day banner with end date, Cancel (≤14 days → full refund via Refunds API; after → cancel at period end), "Payment details & invoices" → portal session, "Contact support" for plan change.
- **Done when:** tests with mocked Stripe for day 13 vs day 15; idempotency key on refund; audit event.

### [x] T16.4 · S! · Data export
- **Spec:** plan L1091, L1460; API item 22.
- **Steps:** step-up required; worker builds zip (CSV per tenant table + documents) to private storage; e-mail link valid 7 days; `GET /companies/me/exports/{id}`.
- **Done when:** export contains only the requesting company's rows (test with two tenants); no step-up → refused.

### [x] T16.5 · B · Delete account (purge executor deletes all tenant data — big model only)

### [x] T16.6 · B · Deletion code e-mail goes through the app mailer (found at the P16 gate)
- **Spec:** plan L1091 (account deletion by e-mailed code); the e2e `web/tests/e2e/account-deletion.spec.ts` needs the code to arrive.
- **Problem:** `_send_code` in `api/app/modules/deletion/router.py` (and `_email` for `deletion_scheduled`, `deletion_withdrawn`, `account_deleted`) only inserts an `EmailOutbox` row inside the request transaction. Nothing enqueues it, so it leaves only when the minute sweep runs (`email_outbox_sweep`). The e2e server runs no sweep (its worker has only `generate_report`; the auth flow uses `DirectMailer`), so the code never reaches Mailpit there. Production works within about a minute, but the code is the only way in and the page says "We have e-mailed you a code" at once.
- **Copy:** the auth routers send with `auth.mailer.send_template(...)` after the commit (`api/app/modules/access/router.py` `_send_invite` is the pattern; the mailer is `request.app.state.auth.mailer`).
- **Steps:** 1. Send `deletion_code` after `db.commit()` through the app mailer; keep the code hash in the transaction and return the code to the caller only for the send. 2. Check the DB test rig's mailer (`tests/db/test_deletion.py` `_mail` reads `email_outbox`); change `_code_for` to capture the message the way the rig can. 3. Decide in the same change whether the three other `_email` mails move too (same defect); record the choice under Strategy in STATUS. 4. Run `web/tests/e2e/account-deletion.spec.ts` and `SCREENSHOTS=1 ... phase16-screenshots.spec.ts --grep scheduled`.
- **Done when:** `account-deletion.spec.ts` passes (code arrives, confirm, scheduled date, withdraw); `tests/db/test_deletion.py` and the email/guards suites pass. No skip, no weakened assertion.

### [x] P16 · S · Phase 16 gate
- Recipe R7. **Stripe test-mode E2E is parked in `leftover.md` (L1)** — owner has no test keys yet; do not block on it.
- Done (2026-11-08): R7 steps 1–4 (API 1254, web lint/typecheck/unit 786, web e2e 436, screenshots 16/16, PROGRESS summary, PR #25 merged to main with all checks green). Stripe E2E stays in leftover.md L1.

---

## Phase 17 — Super-admin back office

### [x] T17.1 · S! · Platform admin auth and admin host routing
- **Spec:** plan L1155–1158, L1464.
- **Copy:** `api/app/modules/rbac/platform.py`, `web/app/(admin)/`, `web/tests/e2e/host-routing.spec.ts` (parts exist — extend, don't rebuild).
- **Steps:** separate cookie name, mandatory MFA, optional IP allowlist (env), every page view audited, red "Platform admin" bar.
- **Done when:** tenant session cookie on admin host → refused; no MFA → refused; tests.
- **Done (2026-11-08):** platform cookie `brand_platform_session` (`PLATFORM_SESSION_COOKIE_NAME`), issued only by `POST /api/v1/auth/platform-session` after MFA and inside `ADMIN_IP_ALLOWLIST`; guard refuses a tenant session (403 with a tenant session, 401 without), a platform token on tenant routes, no MFA, and addresses outside the allowlist; every platform request audited as `platform.access` (migration 0048); red `PlatformBar` on every admin page. Tests: `tests/db/test_platform_session.py` (7), `tests/test_platform_network.py` (8), platform tests updated to start a platform session; full API 1270 pass; web unit, lint, typecheck clean; host-routing e2e 13 pass.

### [x] T17.2 · S · Overview metrics, companies, users search
- **Spec:** plan L1160–1164, L1168, L1465. Steps: metrics endpoint, companies list/detail/actions (suspend/reactivate with reason, extend plan, mark for deletion), users search + lock/unlock. All audited.
- **Done (2026-11-08):** API only, as the steps read (the admin screens are not in this block; see STATUS). `GET /platform/metrics` (signups 24 h and 7 days, active companies, plans, paid entitled, MRR/ARR estimate at £50 a year, churn and refunds over 30 days); `GET /platform/companies` (search by name, slug or e-mail; filter by plan, status, created since, active since; paged); `GET /platform/companies/{id}` (profile, people, last platform actions); `POST .../suspend`, `.../reactivate` (reason required), `.../extend-plan` (10-year plan with an active subscription only), `.../mark-for-deletion` (owner only; erases nothing); `GET /platform/users?q=` (e-mail, 3 characters or more); `POST /platform/users/{id}/lock` and `/unlock` (sets `users.is_active`; refuses your own account). The `/platform` prefix follows T15.7, not the spec's `/admin`. Migration 0049. Tests: `tests/db/test_platform_admin.py` (7 pass); platform session, rules and network 19 pass; architecture, OpenAPI, RBAC, audit, guards and migrations 73 pass; ruff, mypy, web typecheck and gen:api:check clean.

### [x] T17.3 · B · Support mode (impersonation)
- **Done (2026-11-08):** `POST /platform/companies/{id}/impersonate` (reason + ticket ref, active company) sets a separate `brand_support_session` cookie for 30 minutes; the admin's tenant requests are that company's, seen as `company_admin`, read-only (`SUPPORT_READ_ONLY`; account routes never write in support mode). `POST /platform/impersonation/{id}/writes` turns changes on (owner level, own session, `confirm: true`) or off; `.../end` and `DELETE /auth/support-session` end it. The row is checked every request (end or expiry works at once; a late write gets `SUPPORT_SESSION_ENDED`, never lands in the admin's own company). Company-visible audit `support.session.*` plus platform `platform.support_*`; changes made in support mode carry `impersonation_session_id` and actor `platform_admin`. `/auth/me.support` drives the red tenant banner. Migration 0050. Tests: `tests/db/test_support_mode.py` 5 pass; banner unit 2 pass.

### [x] T17.4 · S! · Subscriptions and refunds, deletion and export queue, contact inbox
- **Spec:** plan L1166–1167, L1173, L1467. Refunds = owner level only, through the T16 Stripe client, idempotent, audited.
- **Done (2026-11-08):** API only, as T17.2 and T17.3's API. `GET /platform/subscriptions` reads the database only (the Stripe ids are shown for a lookup in Stripe; no Stripe call per row). `POST /platform/refunds` (owner only; `reason` and `confirm: true`) issues one full refund of the latest payment behind a purchase through the T16 client, with the self-serve key `refund-{payment_intent}`, so one payment is refunded at most once; a refunded purchase answers `ALREADY_REFUNDED`, and the plan itself changes through the existing `charge.refunded` webhook, as for a dashboard refund. `GET /platform/deletion-requests` (awaiting code, scheduled, withdrawn, completed; the code hash is never read) and `GET /platform/data-exports` (queued, ready, failed). `GET /platform/contact-messages` (handled filter) and `PATCH /platform/contact-messages/{id}` (audited only on a change). Migration 0051; `contact_messages` is global and is written by the public form in T18.1. Tests: `tests/db/test_platform_billing.py` (15 pass). Admin screens are not in this block.

### [x] T17.5 · S · Content tools and feature flags
- **Spec:** plan L1170, L1175, L1468. Full course editor, templates, guides (MDX upload + sanitised preview), dossier links, announcement banner, terms version publish (forces re-acceptance), feature flags.
- **Watch:** MDX/Markdown preview must be sanitised (no raw HTML/script).
- **Decided 2026-11-08 (answers 1–2, recorded by the agent at the owner's request; the owner can override):** templates are DOCX/PDF files in the repo under `content/templates/`, reviewed in pull requests; the admin lists them and nothing is uploaded. Guides are MDX files in the repo under `content/guides/`, compiled at build time; there is no MDX upload and no admin preview of user HTML, because MDX runs JSX and an upload would be script injection. The admin screens for both are not built here: the templates listing moves to T19.17 and the guides to T19.16. Built here: terms version publish (owner only, forces re-acceptance); feature flags; announcement banners per region (platform create and end, tenant banner); dossier links (existing `/admin/dossier-links`, audited); course editor (existing `/admin/courses`; tests pass). Tests: `tests/db/test_platform_content.py` 10 pass; web `announcement-banner` 3 pass.

### [x] T17.6 · S · Jobs dashboard, register status, rules screens, platform audit log
- **Spec:** plan L1169, L1171–1174, L1469.
- **Done (2026-11-08), owner answers 3–4 applied:** platform audit log with filters and CSV export, recorded (`/platform/audit`, `/platform/audit/export`; migration 0055); job dashboard with queue depth and failures, no arguments (`/platform/jobs/queue`, `/platform/jobs/failures`); **retry** from an allow-list of five jobs that send nothing and keep no arguments (`app/jobs/rerun.py`; queued as `rerun_<name>`; a reason is required; audited; migration 0056; `POST /platform/jobs/failures/{id}/rerun`); rules screens already built in T15.7 (versions with `diff_summary`, publish, rollback). **Register status** moved to T20.5 (owner answer 4). Tests: `tests/db/test_platform_audit_log.py` 3 pass, `tests/db/test_platform_jobs.py` 7 pass.

### [x] P17 · S · Phase 17 gate
- Recipe R7.
- Done (2026-11-09): R7 steps 1, 3 and 4 done (API full suite 1319 pass; web unit 802 pass; web e2e 437 pass, 200 screenshot-only skipped; lint and typecheck clean). Step 2 (screenshots) is parked in leftover.md L2: the new admin screens need a platform-admin seed in the e2e harness.

### [x] AUDIT-3 · AUDIT STOP · covers T15.1 → P17 (and the B tasks in them)

---

## Phase 18 — Public marketing site

### [x] T18.1 · S · Marketing pages
- **Spec:** plan L1199–1211, L1472; style §5.9 (`grep -n '### 5.9' plan.md`).
- **Steps:** one page per sub-step: Home, Features (screenshots by a Playwright script from seeded demo data, both themes), Pricing, Security, About, Contact (+ `POST /public/contact`, R5), Accessibility, Careers (own company via careers module), Sponsor compliance + Reporting duties.
- **Watch:** original copy only; brand from `brand.config.ts`; prices from config, not typed into copy.

### [x] T18.2 · S · Legal pages (DRAFT)
- **Spec:** plan L1217, L1473. Every page shows "DRAFT — requires solicitor review". Cookie policy lists the real cookies (grep the code); subprocessors = real vendors. Cookie consent per L1218–1222. Add owner action to PROGRESS.

### [x] T18.3 · S · SEO and Lighthouse ≥ 95
- **Spec:** plan L1223–1228, L1474. Metadata, OG images, JSON-LD, sitemap, robots; analytics only after consent.

### [x] T18.4 · S · Comparison page templates (unpublished)
- **Spec:** plan L1216. Templates only, unpublished by default; no competitor prices typed in.

### [x] P18 · S · Phase 18 gate
- Recipe R7 + Lighthouse on marketing pages.

---

## Phase 19 — Free tools, guides, templates

### [x] T19.1 · B · Rates data files, verified from GOV.UK and HMRC

**For T19.2–T19.15 (all S!):** spec plan L1555–1584 (row = calculator number). Each calculator:
1. Pure TS module `web/lib/calculators/<slug>.ts` that reads figures **only** from `web/rates/*.json` (T19.1).
2. Unit tests whose expected values come from a GOV.UK/HMRC worked example; put the example URL in a comment above each test.
   If no official worked example exists, test against hand-worked arithmetic from the rates file and say so in the comment.
3. Page `web/app/(marketing)/resources/tools/<slug>/page.tsx` with the shared calculator template (build the template in T19.2, reuse after).
4. Nothing entered is stored or sent (no fetch in the module; a test greps it).
- If a figure you need is not in `web/rates/`: **STOP — BLOCKED needs verified figure**.

### [x] T19.2 · S! · Calculator 1: right-to-work-october-2026-checker (+ build the shared calculator template)
### [x] T19.3 · S! · Calculator 2: sponsor-licence-cost-calculator
### [x] T19.4 · S! · Calculator 3: sponsor-reporting-deadline-calculator (reuse the working-day logic semantics from `api/tests/test_working_days.py`)
### [x] T19.5 · S! · Calculator 4: skilled-worker-visa-checker (SOC data via public SOC API, no AI)
### [x] T19.6 · S! · Calculator 5: ilr-citizenship-checker
### [x] T19.7 · S! · Calculator 6: skilled-worker-ilr-salary-calculator
### [x] T19.8 · S! · Calculator 7: holiday-entitlement-calculator
### [x] T19.9 · S! · Calculator 8: uk-take-home-salary-calculator
### [x] T19.10 · S! · Calculator 9: uk-employer-cost-calculator
### [x] T19.11 · S! · Calculator 10: uk-redundancy-pay-calculator
### [x] T19.12 · S! · Calculator 11: uk-notice-pay-calculator
### [x] T19.13 · S! · Calculator 12: uk-sick-pay-calculator
### [x] T19.14 · S! · Calculator 13: uk-minimum-wage-underpayment-checker (compare with `api/tests/test_minimum_wage.py` data if relevant)
### [x] T19.15 · S · Tool 14: risk-assessment-template (browser-only, PDF/DOCX download, saved in localStorage with try/catch)

### [x] T19.16 · S! · Guides, including the 26-question audit self-test
- **Decided 2026-11-08 (owner answer 2):** guides are MDX files in the repo under `content/guides/`, compiled at build time, reviewed in pull requests. No upload and no admin editor; the Watch rule (no raw HTML or script) applies to the MDX source, which is trusted content, and the renderer must not allow raw HTML.
- **Spec:** plan L1213. MDX, original, sources + last-reviewed date + disclaimer on each; the self-test is client-side with a score.

### [x] T19.17 · S · Templates
- **Decided 2026-11-08 (owner answer 1):** templates are DOCX/PDF files in the repo under `content/templates/` with a manifest (title, file, version, reviewed on). The platform admin lists them read-only (built here, from the manifest); nothing is uploaded. Each template is original work and needs a human review before it is published (offer letters especially).
- **Spec:** plan L1214. Original DOCX/PDF generated from MDX sources at build or by a script.

### [x] T19.18 · S · Resources hub pages
- `/resources`, `/resources/guides`, `/resources/tools`, `/resources/templates`.

### [ ] P19 · S · Phase 19 gate
- Recipe R7.

---

## Phase 20 — Public sponsor register

### [x] T20.1 · S! · Ingest pipeline
- **Spec:** plan L1232–1238, L1485; §6.12 L617–627.
- **Steps:** discover the latest CSV link by parsing the GOV.UK publication page (never hard-code the file URL; allowlisted host only) → download → hash (skip if unchanged) → parse → normalise → upsert → changes vs previous → possible renames (fuzzy). Saved HTML + CSV fixtures; tests never hit the network. Job at 10:00 and 16:00 working days (R3).
- **Done when:** running twice on the same fixture creates no new publication; diff test with two fixtures.

### [x] T20.2 · S · Geocoding, ITL1 regions, SVG map, Companies House bulk match
- **Spec:** plan L1237–1238, L1241, L1486. Original simplified SVG from ONS boundary data; Companies House match behind a flag.

### [x] T20.3 · S · Explore page
- **Spec:** plan L1239–1242, L1487.

### [x] T20.4 · S · Region pages, change bulletins, profiles, methodology, report form, sitemaps
- **Spec:** plan L1243–1251, L1488. Profiles use ISR (revalidate 6 h); sitemaps split ≤45k URLs; attribution text exactly as L1247; report form R5.

### [x] T20.5 · S · Register status and rerun (moved from T17.6)
- **Spec:** plan L1171 (sponsor register: last import, row counts, errors, rerun import). Owner answer 4 (2026-11-08): this moved here from T17.6, because the register ingest is built in T20.1.
- **Steps:** `GET /platform/register/status` (last publication, row counts, errors) and `POST /platform/register/run` (rerun through the ingest job, with a reason, audited as `platform.register_rerun`). The import sends nothing, so a rerun is safe; it goes through the same job allow-list as T17.6.

### [ ] P20 · S · Phase 20 gate
- Recipe R7.

### [ ] AUDIT-4 · AUDIT STOP · covers T18.1 → P20

---

## Phase 21 — Security hardening (all big model)

### [ ] T21.1 · B · Full security test suite and RBAC matrix coverage of every endpoint
### [ ] T21.2 · B · Threat model (`docs/security.md`)
### [ ] T21.3 · B · Dependency, container and secret scans clean; CSP enforced
### [ ] T21.4 · B · Pen-test style checks
### [ ] T21.5 · B · Privacy review
### [ ] P21 · B · Phase 21 gate

---

## Phase 22 — Quality, performance, accessibility

### [ ] T22.1 · S · Full E2E suite for the top 25 journeys
- **Spec:** plan L1498. One spec per journey under `web/tests/e2e/journeys/`; one commit per 3–5 journeys.

### [ ] T22.2 · S · Performance budgets
- **Spec:** plan L1499. Seed 1,000 employees (dev seed only); measure p95; add indexes with a migration; EXPLAIN tests for main lists.

### [ ] T22.3 · S · Accessibility audit
- **Spec:** plan L1500. axe 0 serious on every page (extend `web/tests/e2e/design-a11y.spec.ts`), reduced-motion check.

### [ ] T22.4 · S · Design QA sweep with final screenshots
- **Spec:** plan L1501, §5.12 L439–451. All widths, light/dark → `docs/screenshots/final/`.

### [ ] P22 · S · Phase 22 gate
- Recipe R7.

### [ ] AUDIT-5 · AUDIT STOP · covers Phases 21–22 — pre-deployment audit

---

## Phase 23–24 — Deployment and launch (big model + owner)

### [ ] T23.1 · B · Railway project, environments and services
### [ ] T23.2 · B · Database roles, reference data seeding, first Platform Admin
### [ ] T23.3 · B · Cloudflare DNS, TLS, WAF, rate limit, Turnstile, R2 buckets
### [ ] T23.4 · B · Resend, Stripe, Sentry and uptime monitor set-up
### [ ] T23.5 · B · GitHub Actions deploy workflows
### [ ] T23.6 · B · Backups, restore test and runbooks
### [ ] T23.7 · B · Staging acceptance
### [ ] T23.8 · B · Production go-live
### [ ] P23 · B · Phase 23 gate
### [ ] T24.1 · B · Launch checklist (plan §12) and `docs/handover.md`

---

## Phase 25 — Apple-quality visual pass and final security scan (big model, added by the owner 2026-11-12)

### [ ] T25.1 · B · Visual audit of every screen against the Apple-quality design
- **Spec:** plan §5 (L296–450): principles, typography, colour tokens, materials (glass), motion, layout, components, §5.12 QA checklist. Plan L25: no Apple trademarks, logos, SF Symbols, SF font files or device images.
- **Steps:** 1. List every route (app, admin, auth, marketing, careers, free tools) from `web/app`. 2. Screenshot each at 390 and 1280 px, light and dark, into `docs/screenshots/phase-25/before/` (copy `web/tests/e2e/phase9-screenshots.spec.ts`; run through `bus.sh serial`). 3. Check each against §5 and §5.12. Look hardest at the glass: translucent sidebar, toolbar, sheets, popovers and the marketing nav (`backdrop-filter: saturate(180%) blur(20px)` over the material tokens, hairline borders, layered soft shadows); also type scale, spacing on the 4 px grid, radius, motion, alignment and empty/loading states. 4. Write `docs/design-audit.md`: one row per screen with each gap, the §5 rule it breaks and the fix (token or component, not per-page CSS), sorted by how many screens a fix touches.
- **Done when:** `docs/design-audit.md` covers every route, and the before screenshots are saved. No app code changed.

### [ ] T25.2 · B · Make every screen look Apple-quality (glass and the rest)
- **Spec:** `docs/design-audit.md` (T25.1) and plan §5. This block may restyle earlier work (the owner's request); behaviour stays the same.
- **Steps:** 1. Fix the tokens and materials in `web/app/globals.css` first, so most screens improve at once. 2. Then the shared components in `web/components/ui/`. 3. Then the rows of `docs/design-audit.md` left over, screen by screen; tick each row there. 4. After screenshots into `docs/screenshots/phase-25/after/` (same script, same widths and themes).
- **Watch:** our own tokens and components only: no Apple logos, SF Symbols, SF font files or Apple device frames (plan L25, L308). Every glass surface falls back to a solid colour under `prefers-reduced-transparency` and when `backdrop-filter` is unsupported; motion respects `prefers-reduced-motion`; text contrast stays WCAG AA on glass in both themes; no layout shift. Don't change copy, routes or behaviour. Update the `/design` catalog and its expected tokens when tokens change.
- **Done when:** every `docs/design-audit.md` row is ticked; web lint, typecheck, unit suite and full e2e pass (e2e via `bus.sh serial`); the design and accessibility e2e specs pass in both themes.

### [ ] T25.3 · B · Whole-project security scan
- **Spec:** plan security sections; `docs/security.md` (T21.2) as the threat model; `audit.md` severity scale (P0/P1/P2).
- **Steps:** 1. Automated: gitleaks over the full history, semgrep, pip-audit, pnpm audit, Trivy images and config, actionlint and zizmor (the CI jobs, run locally), plus the CSP and security headers on the production build. 2. Manual review of every API router: auth, MFA, sessions, CSRF, RBAC matrix, RLS on every table, tenant isolation, platform admin and support mode, file uploads, exports, webhooks (Stripe signature, replay), rate limits, input validation, SSRF in fetchers, secrets handling and logging. 3. Check that T25.2 added no unsafe CSS or inline script that the CSP would need to allow. 4. Write `docs/security-scan-2026.md` with each finding, its severity and the fix.
- **Done when:** the report covers every router and table; every P0/P1 is fixed in this block with a test that fails before the fix (or, if large, written into `changesneeded.md` for the next round); the automated scans are clean.

### [ ] P25 · B · Phase 25 gate
- Recipe R7, and redeploy staging then production with the T23.5 workflows after the PR to main merges.
