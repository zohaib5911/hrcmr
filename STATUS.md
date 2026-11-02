# STATUS
Updated: <fill in>    Agent: Claude Code    Branch: dev    Commit: <sha>
State: HANDED OVER

## Last completed
- T4.3 — Key personnel (check PROGRESS.md)

## Current task
- T4.4 — Compliance documents — API done (migration 0008), web page not built, uncommitted
- Resume note: commit the T4.4 API work, build the web page, then do the fixes listed in "Issues / suggestions" before T4.5

## Next tasks
- T4.4, T4.5, T4.6, T4.7

## Health
- CI on dev: create branch dev from main first    CI on main: red (shell.spec.ts:300 stale assertion; Dependabot #4 red)
- Local checks run: n/a

## Issues / suggestions
- Trust CF-Connecting-IP / X-Real-IP only from trusted proxies (auth/deps.py:38-41)
- Send lockout + new-device emails (T2.3; replace SilentNotifier)
- Move email samples (samples.py) to dev-only
- Apply extra="forbid" to all request models via a shared base model
- Breached-password fallback list: use top-100k
- Remove the certifi exception after 2026-11-06

## Strategy / decisions taken
- Relay mode: Claude Code and Codex alternate; one at a time, never together
- AI features hidden unless ANTHROPIC_API_KEY is set; Ask Mady deferred
- style-src-attr 'unsafe-inline' accepted (animation library)
- Dependabot #1 (Redis 8) rejected; keep Redis 7

## Owner actions needed
- Protect main (require CI) and enable private vulnerability reporting on GitHub
