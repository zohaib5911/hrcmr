# changesneeded.md — audit AUDIT-2 round 1 (2026-11-07, Claude Opus 5.5)
Scope: audit-pass-1 (afa2d28 base)..a87d511 (T12.1 → P14, incl. T14.4)
Tests at audit: api 1036/0/0 (lint, format, mypy clean; check-rls via tests/db/test_cli.py), web unit 786/0, web lint/types/build/gen:api clean, e2e 430/0 (176 screenshot-only skipped), CI green (PR #22)
Result: FIX NEEDED: 0 P0 / 3 P1 / 3 P2. AUDIT-2 stays open; re-audit after C2.1.1 to C2.1.3.

### [x] C2.1.1 · P1 · Employee names typed into letter key points reach Claude (from T14.5) — fixed in 499e2f3
- **Problem:** `api/app/ai/letters.py` `_ai_paragraphs` sends `key_points` as free text. `generate` (`api/app/ai/service.py:78`) makes a fresh `Pseudonymiser()` that knows no names, so a point such as "Meet Ada Morrow on Monday" is sent to Anthropic with the name in it. Plan 8.12: letter drafting "generic placeholders only; no identifiers". The existing test `test_ai_draft_wraps_claude_paragraphs_and_sends_only_type_tone_and_points` (`api/tests/db/test_letters.py:94`) never uses a name, so it cannot catch this.
- **Fix:**
  1. In `api/app/ai/service.py`, add a keyword argument `names: list[str] | None = None` to `generate`; right after `pseudonymiser = Pseudonymiser()`, call `pseudonymiser.label(name)` for each name (skip blanks).
  2. In `_ai_paragraphs`, load the full names of the company's employees (`select(Employee.first_name, Employee.last_name).where(Employee.company_id == access.company_id)`, all statuses) and pass `names=[f"{first} {last}" for ...]` to `generate`. `restore` then puts the names back into the draft the user sees.
- **Done when:** a new test in `api/tests/db/test_letters.py` (copy the `fake_claude` pattern of the test above) seeds an employee "Ada Morrow", drafts with key point "Meet Ada Morrow on Monday", and asserts `"Ada Morrow" not in sent[0]`, `"Employee A" in sent[0]`, and the returned `body` contains "Ada Morrow". `uv run pytest tests/db/test_letters.py tests/test_ai_redaction.py -q` passes.

### [x] C2.1.2 · P1 · Leave and rota e-mails ignore the person's e-mail preference (from T14.2) — fixed in 5a221ec
- **Problem:** T14.2 added `GET/PUT /me/notification-preferences` (immediate / daily / off, plan L1196) and the daily digest, but only `api/app/modules/policies/service.py:355` checks the mode. `api/app/modules/leave/request_router.py:174` (leave decision) and `api/app/modules/rota/publish_router.py:108` (rota published) always add an `EmailOutbox` row, so a person on "off" or "daily" still gets an immediate e-mail (and on "daily" gets it twice: now and in the digest).
- **Fix:** copy the policy pattern: `modes = await email_modes(access.db, [user ids])` from `app/modules/notifications/preferences.py`, and add the `EmailOutbox` only when `modes.get(user_id, "immediate") == "immediate"`. Keep the in-app `Notification` row always. Do not change the compliance reminder e-mail (it is a message HR chose to send).
- **Done when:** one test each in `api/tests/db/test_notifications_prefs.py`: a person with mode "off" gets the `leave.decision` / `rota.published` notification but no `EmailOutbox` row; a person with no saved mode still gets the e-mail. Existing leave and rota DB tests still pass.

### [x] C2.1.3 · P1 · No "course assigned" notice (from T13.3 / T14.2) — fixed in 2705617
- **Problem:** plan L1194 lists "course assigned" among the bell's personal notifications, and micro_plan T14.2 step 1 names the course kind. `POST /learning/assignments` (`api/app/modules/learning/router.py`, `assign_courses`) creates assignments but no `Notification`; the only learning kind is `learning.overdue` (`api/app/jobs/learning.py:26`).
- **Fix:** in `assign_courses`, after the insert, add one `Notification` (kind `learning.assigned`, title "A course has been assigned to you", link `/learning/my`) per newly created assignment's person who has an active membership (copy how `api/app/jobs/learning.py` finds the user for an employee and builds its notice). Use `.returning(CourseAssignment.employee_id, CourseAssignment.course_id)` on the insert so assigning twice does not notify twice. Add `"learning.assigned"` to `PERSONAL_KINDS` in `api/app/modules/notifications/router.py`. In-app only (no e-mail) is fine.
- **Done when:** a test in `api/tests/db/test_learning_report.py` assigns a course to a named employee twice and asserts that person has exactly one `learning.assigned` notice in `GET /notifications`.

### [x] C2.1.4 · P2 · "AI available" ignores the platform switch (from T14.4) — fixed in 52fc451
- **Problem:** `api/app/modules/auth/accounts.py:378` sets `ai_available` from the key and the company flag only; `ai_ready` (`api/app/ai/service.py:41`) also needs `settings.ai_features_enabled`. With the platform switch off, the reminder drawer shows "Draft with AI" but always gets the template.
- **Fix:** in the three `build_me(..., ai_key=...)` calls in `api/app/modules/auth/router.py` (lines ~86, 190, 408) pass `ai_key=auth.settings.anthropic_api_key is not None and auth.settings.ai_features_enabled`.
- **Done when:** a test (copy an existing `/auth/me` test) with `ai_features_enabled=False` and a key set asserts `ai_available` is false.

### [x] C2.1.5 · P2 · Org chart shows RTW chips to any role with an "own" RTW permission (from T12.1) — fixed in 47f6b51
- **Problem:** `api/app/modules/organogram/router.py:39` and `:50` use `scope_for(access.role, "employee.rtw.read") is not None`, which is true for `employee.rtw.read_own`. No current role has both that and `organogram.level.read`, so nothing leaks today, but a future grant would show everyone's RTW status.
- **Fix:** compare `is Scope.ALL` (import `Scope` from `app.core.rbac_matrix`) in both places.
- **Done when:** `uv run pytest tests/db/test_organogram.py -q` passes.

### [ ] C2.1.6 · P2 · Small polish
- **Problem / Fix:**
  - Certificate check is case-sensitive: `verify_certificate` (`api/app/modules/learning/certificates.py`) should use `ref = ref.strip().upper()` before the length check. Test: a lower-case reference still verifies.
  - Palette live search fires on every keystroke: in `web/components/app/shortcut-provider.tsx` `searchPeople`, wait 200 ms (setTimeout, cleared on the next call) before the request.
  - Dashboard "Employee distribution" card is blank with no employees (see `docs/screenshots/phase-14/dashboard-light-390.png`): show "No employees yet" in its empty state (`web/app/(app)/dashboard/` card component).
  - Reminder drawer "Draft with AI" replaces text HR typed: in `web/components/compliance/reminder-review.tsx` `draftWording`, if the textarea differs from `record.message_draft`, ask with the existing confirm dialog pattern before replacing.
- **Done when:** the touched unit/DB tests pass; `pnpm lint && pnpm typecheck` clean.

## Notes (no action needed)
- T14.4 was written by this same model (Opus); its review here is by the same model. Fuzz test (`tests/test_ai_redaction.py`) and `assert_clean` on the wire body are sound.
- Course figures spot-checked: the sexual-harassment course's "from 30 October 2026, all reasonable steps" and third-party liability match ACAS (page updated 30 October 2026). Other courses cite no figures beyond the Equality Act 2010. All 8 have 6 sections, 5 questions, a gov.uk/acas.org.uk source; all unpublished until the owner reviews them.
- Search (T14.3) gives people only to company-wide readers; managers do not find their reports. Matches the plan wording ("where the user has read permission" read as company-wide); revisit if the owner wants manager search.
- Learning report is company-wide only; managers have `learning.assignment.read_reports` but no team view (already in STATUS).
- Certificate PDF has no explicit cross-tenant test; the query filters on `company_id` and RLS covers it.
