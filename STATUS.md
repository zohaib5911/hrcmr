# STATUS
Updated: 2026-11-07 14:30, Europe/London    Agent: Claude Code (Haiku 5.5, SMALL)    Branch: dev    Commit: pending (feat T11.4)
State: IN PROGRESS

## Last completed
- T11.4 — Applications (one-step forward rule, backward moves, ended applications, history), interviews (invites and .ics), offers (draft to accepted/declined/withdrawn), pipeline bar, application page.

## Current task
- none (T11.4 closed). Next block per next.sh is T11.5 (S!, convert to employee).

## Next tasks
- T11.5 (S!) convert to employee — the current RTW check drives the gate
- T11.6 (S!) public careers pages and apply form (Turnstile, CV scan, confirmation email, recruiter notification)
- P11 gate; then AUDIT-1 (a stop: big model runs audit.md)

## Health
- CI on dev: last pushed checkpoints are not yet through PR CI; Phase 10 is on main (34f7aee).
- Local checks run this session: API DB 134 pass (applications, interviews, offers, postings, candidates, recruitment, RTW, RBAC, guards, data-model doc, email); stage rules 65 and .ics 3 pass; mypy (333 files) and ruff clean; web unit 777, typecheck and lint clean; recruitment.spec 4 pass.

## Issues / suggestions
- Accepting an offer does not move the application to Offer Accepted or Hired on its own; stages are moved by hand (not in the spec). Decide with T11.5.
- A cancelled or on-hold requisition does not close its open postings (not in the spec); applications on a closed posting cannot be created, but existing ones still move.
- The candidate profile lists the first 100 applications and the first 100 open postings; large companies will need paging there.
- The named-people pickers in interviews load the first page of active employees only.
- Rota publish inserts rota.published notifications but notifications/router.py _kinds omits that kind (left alone).
- Never overlap DB pytest and Playwright (shared PostgreSQL role passwords).

## Strategy / decisions taken
- Stage rules live in applications.py (pure), tested for all 64 stage pairs; the message is exactly "The next step from X is Y" with the pipeline labels.
- Ended applications (rejected, withdrawn) cannot change; the reason text is "This application is rejected. It cannot change."
- Interview invites: the outbox has no attachments, so the staff email carries the details and a link to the application page, where the .ics downloads (RFC 5545, UTC times, folded lines, interview notes kept out of the calendar). The candidate email carries the details and no link.
- Offers: draft, then sent, then accepted/declined/withdrawn; decided offers are final; edits are allowed only while a draft (409 otherwise).
- Pipeline counts come from one grouped query; the 8 stages always appear, zero when empty.
- Applying from a candidate profile uses the Applications tab; the header "Apply to posting" button switches to it.

## Owner actions needed
- None.
