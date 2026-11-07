## Result: PASS
# changesneeded.md — audit AUDIT-1 round 3 (2026-11-07, Claude Opus 5.5)
Scope: audit-1-r2 (bd134fa)..7ee40a2 (the round 2 fix commits) + regressions in body limits, careers, interview invites
Tests at audit: api 796/0/0, web unit 777/0, web lint/types/build/gen:api clean, e2e 426/1 (164 skipped) on 7ee40a2: one flaky toast locator in company.spec, fixed in 58a4718 (company.spec 15 pass); PASS stands only with a green CI re-run on PR #19
Round 1 (1/5/1) and round 2 (0/3/1) are fixed and ticked in git history (16184dc, 7ee40a2). Round 3 found no P0 or P1.
Caveat: rounds 2 and 3 were run by the same model that wrote the fixes. The guard test below makes the round 2 body-limit
class of bug fail CI from now on.

### [ ] C1.3.1 · P2 · Interview invites have no ORGANIZER (from T11.4 / C1.1.2)
- **Problem:** `interview_ics` (`api/app/modules/recruitment/ics.py`) writes `METHOD:REQUEST` with no `ORGANIZER` line. RFC 5546 requires an organizer on a REQUEST, so some clients (notably Outlook) show the e-mailed invite as a plain attachment instead of an Accept/Decline invite.
- **Fix:** add an `organizer: tuple[str, str]` argument (name, e-mail) to `interview_ics` and write `ORGANIZER;CN=<name>:mailto:<address>` after `DTSTAMP` (escaped like the attendee CN). In `_invite_text` (`api/app/modules/recruitment/router.py`), pass the company name and the sending address from `sender_of(request.app.state.settings)` (`app/modules/email/outbox.py`); use only the address part if it has a display name.
- **Done when:** `tests/test_interview_ics.py` asserts the `ORGANIZER` line; `tests/db/test_interviews.py` still passes.

## Notes (no action needed)
- C1.2.1: the careers list and posting have no API rate limit (they are server-rendered, so every visitor shares one address); only the browser-fetched logo is limited. An edge rule for `/careers/*` is an owner action for Phase 23 (in STATUS).
- C1.2.3: `tests/test_body_limits.py` checks every multipart route in the OpenAPI schema; with the old table it flags all 7 routes that were capped at 1 MB. JSON routes beside them keep the 1 MB default (tested).
- C1.2.4: staff invites list the whole panel; the candidate's copy is the same event (same UID) and names only the candidate.
- Public CV refusals are not audit-logged (no signed-in user, nothing written), by design.
