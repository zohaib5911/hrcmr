# audit.md — instructions for the auditor (big model only)

You are the **auditor**. Small models built the work below, following `micro_plan.md`.
Your job: find what is wrong or missing, and write it down as **small, exact fix tasks** in `changesneeded.md`
so a small model can fix them. **You don't fix code yourself** (exception: a one-line fix that makes CI green, noted in the report).
You get here from AGENTS.md "Quick start" (the owner only ever types "Read AGENTS.md and continue").
When the audit is written and pushed, go back to AGENTS.md Quick start step 2: if the next block is B, do it; otherwise
stop with the `✓ BIG-MODEL WORK DONE` message.

Don't trust anything a small model *wrote* about its work (journal, STATUS, PROGRESS, commit messages).
Trust only what you run and read yourself.

---

## 1. Work out the scope

1. `git switch dev && git pull --rebase origin dev`. The tree must be clean (if not, follow AGENTS.md §1.2 first).
2. Find what this audit covers:
   - **First audit of a stop** (an `AUDIT-n` block in `micro_plan.md` is the next open block, and `changesneeded.md` has no open items):
     scope = `git log --oneline audit-pass-<n-1>..HEAD` (for AUDIT-1, use the `chore(status): start T10.3` commit `f37f781` as the base).
   - **Re-audit after fixes** (`changesneeded.md` items are all ticked): scope = the fix commits since the last audit tag
     `audit-<n>-r<k>`, **plus** a regression check of anything those fixes touched.
3. List the tasks in scope (ids from the commit messages and `micro_plan.md`), and which are **S!** or **B**. These get the deepest review.

## 2. Run everything (one time, in this order, never in parallel)

From the repo root: `docker compose up -d --wait`. Then:
1. `cd api && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest -q`
2. `uv run python -m app.cli check-rls`
3. `cd web && pnpm lint && pnpm typecheck && pnpm test && pnpm gen:api:check && pnpm build`
4. `cd web && pnpm test:e2e`
5. `gh run list --branch dev --limit 3` (CI state).

Write down the real counts (passed / failed / skipped). **Any failure is a P0 finding.**
Then look for hidden cheating, scoped to the diff:
- `git diff <base>..HEAD | grep -nE '^\+.*(skip|xfail|only\(|\.skip\(|# type: ignore|eslint-disable|noqa|TODO|FIXME|lorem)'`
- assertions that were removed or weakened: `git diff <base>..HEAD -- '*test*' | grep -E '^-\s*(assert|expect)'`
- tests that assert nothing meaningful (only status 200, no body checks, or mocking the very thing under test).

## 3. Check each task in scope (for each: spec → code → tests)

For each task, read its `micro_plan.md` block, its `plan.md` spec lines, then its diff (`git log --grep 'Txx'` to find commits).
Check, in this order:

**A. Security and tenant safety (deepest on S!/B):**
- Every new endpoint: has `require(...)` with the right permission per plan §7; is tenant-scoped; returns 404 for another
  company's id; has tests for allowed / forbidden / cross-tenant. Grep new routes: `git diff <base>..HEAD -- api/app | grep -E '^\+.*@router\.(get|post|put|patch|delete)'`.
- New tables have RLS (check-rls passes) and are in `app/db/registry.py`.
- Audit events for RTW, salary, permissions, sponsor docs, status, deletion — in the same transaction.
- Public endpoints: rate limit, Turnstile on POST, response fields exactly as spec, uploads virus-scanned.
- No secrets, no PII in logs, no AI payload with identifiers; AI hidden without `ANTHROPIC_API_KEY`.
- SSRF: server fetches only the allowlisted hosts (plan T21.4 list).

**B. Correctness against the spec:**
- Every "Done when" in the `micro_plan.md` block and the plan lines is really met (check the code, not the claim).
- Invented figures: every rate, fee, threshold or date rule traces to `web/rates/*.json`, the rules data, or a cited GOV.UK URL.
  Spot-check at least 3 figures per calculator/rule against the live GOV.UK page.
- Business rules from plan §13 (stages one-at-a-time, convert gates, posting must have an Open requisition, and so on).

**C. Consistency (what small models get wrong most):**
- Copied the nearest module's pattern (structure, naming, error envelope, test style) instead of inventing a new one.
- Duplicated logic that already exists (a second RTW form, a second e-mail sender, direct SDK calls bypassing `integrations/`).
- Earlier work changed or restyled without the task needing it.
- UI: loading / empty / error states, dark mode, 360 px, keyboard focus, uses `components/ui` only.
- Typed client regenerated; `docs/data-model.md` regenerated.

**D. Bookkeeping:** PROGRESS/micro_plan ticks match what really exists; no ticked task that is half-built.

## 4. Severity

- **P0** — must fix before anything else: failing tests/CI, security or tenant leak, data loss risk, invented legal/tax figure, faked or skipped tests.
- **P1** — must fix before the next phase: spec behaviour missing or wrong, missing permission/cross-tenant tests, missing audit event, broken UI state.
- **P2** — should fix, doesn't block: pattern drift, missing edge-case test, copy/design polish.
- Not a finding: personal style preferences, refactors the plan didn't ask for. Put those under "Notes" at most.

## 5. Write `changesneeded.md` (overwrite; keep it for small models — short and exact)

Use exactly this format. Each item must be doable by a small model in one sitting **without reading this audit**.
Sort P0 first. Split big fixes into several items. Name exact files and functions; say how to verify.

```
# changesneeded.md — audit AUDIT-<n> round <k> (<date>, <auditor model>)
Scope: <base sha>..<head sha>   Tests at audit: api <p/f/s>, web unit <p/f>, e2e <p/f>, CI <green|red>

### [ ] C<n>.<k>.1 · P0 · <short title> (from Txx)
- **Problem:** <what is wrong, with file:line>
- **Fix:** <exact steps; which existing file/pattern to copy>
- **Done when:** <test name or command that must pass>

### [ ] C<n>.<k>.2 · P1 · ...

## Notes (no action needed)
- <P2-or-lower observations, or none>
```

Then:
- If there are **no P0/P1 items**: tick the `AUDIT-<n>` block in `micro_plan.md`, and add `## Result: PASS` at the top of
  `changesneeded.md`. P2 items stay listed (small models will do them first next session, then continue the plan).
  Tag: `git tag audit-pass-<n> && git push origin audit-pass-<n>`.
- If there **are** P0/P1 items: leave the AUDIT block open. Tag `audit-<n>-r<k>` and push the tag.
- Append one line to `PROGRESS.md` under the phase: `AUDIT-<n> round <k>: <P0 count>/<P1>/<P2> — PASS|FIX NEEDED`.
- Set `STATUS.md` State to `HANDED OVER — audit fixes ready` (or `HANDED OVER — audit passed`), and commit:
  `chore(audit): AUDIT-<n> round <k> findings` with `Next: run .agent/next.sh (changesneeded.md first)`. Push.

## 6. The loop, and when it stops

Owner runs small models ("Read AGENTS.md and continue") → they fix `changesneeded.md` items one by one, ticking each,
then stop with `BLOCKED — re-audit requested` → owner runs this audit again (round k+1, scope = fix commits + regressions).
**Stop rule:** the loop ends when a round has **zero P0 and zero P1**. If the same item fails twice, the third attempt is
done by a big model (mark it `· B` in `changesneeded.md`), not handed back to a small model again.

## 7. Final message to the owner (max 5 lines)
First line: the stop message from AGENTS.md Quick start (normally `✓ BIG-MODEL WORK DONE — start a small model…`).
Then: result (PASS / FIX NEEDED), counts P0/P1/P2, the single worst finding, and any owner decision needed.
