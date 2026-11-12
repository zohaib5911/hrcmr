# AGENTS.md — rules for every AI agent on this repo (Claude Code, Codex, any other)

Claude Code and Codex now work **at the same time (parallel mode)**, each in its own git worktree. They share work
through the **agent bus** (`.agent/bus.sh`). Each task gets its own branch and PR, and **`.agent/prs.sh` merges a PR
by itself once CI is green**. Nobody waits for CI: open the PR and start the next task.
**You can be cut off at any second** (usage limit). `.agent/run.sh` restarts you when the limit resets, and your
worktree, your claims and your pushed branch let you pick up exactly where you stopped.

## Owner: how to run it
- Start both agents: `bash .agent/start.sh`. Watch: `bash .agent/start.sh attach`. State: `bash .agent/start.sh status`. Stop: `bash .agent/start.sh stop`.
- Models: Claude runs `sonnet` (SMALL) and Codex runs its configured model (`gpt-6.1-sol`, BIG). To change: `CLAUDE_MODEL=opus bash .agent/start.sh`.
- Codex runs inside `.agent/jail.sh`: it can write only to this project (and its caches), and it cannot use Docker, so keep the stack up yourself (`docker compose up -d --wait`).
- The main folder (`cmr_hr/`) is the **coordinator checkout**: it always stays on `dev` and nobody does task work in it.
  The agents work in `cmr_hr-wt/claude/` and `cmr_hr-wt/codex/`.
- Typing "Read AGENTS.md and continue" in an interactive session still works: the agent follows the same loop below.

## Quick start (every session, headless or interactive)
**0. Know who you are.** Agent name = `claude` (Claude Code) or `codex` (Codex CLI). Tier: **BIG** = Claude Opus (any
version), Claude Fable, Solo 6.1 / gpt-6.1-sol. Every other model is **SMALL**. If the runner's prompt tells you your
name and tier, use those. If you can't tell, you are SMALL.
**1. Go to your worktree.** If you are not in `cmr_hr-wt/<agent>` (interactive start in the main folder), `cd` there
(create it with `git worktree add --detach ../cmr_hr-wt/<agent> origin/dev` if it is missing). Never do task work in the main folder.
**2. Recover (§1), then run** `bash .agent/next.sh --agent <agent> --tier <S|B>` and do what it says:

| `next.sh` says | What you do |
|---|---|
| `FIX-PR` | Your PR is red or has a conflict. `git switch task/<id>`, read `gh pr checks <n>`, fix it (or rebase on `origin/dev`), push. Done. |
| `RESUME` | You claimed this task earlier and were cut off. `git switch task/<id>` (create it from `origin/dev` if it isn't there), continue from your last journal line. |
| `ANSWER` (BIG only) | Answer every open ASK yourself, never ask the owner: `bash .agent/bus.sh decide <agent> <task-id> "<decision and why>"`, then `bash .agent/bus.sh say <agent> <asker> ANSWER "#<ask id> <short answer>"`. Then run next.sh again. |
| `AUDIT` (BIG only) | Claim it, then run `audit.md` fully on branch `task/AUDIT-n`, open the PR. |
| `FIX` / `TASK` | Claim it (`bash .agent/bus.sh claim <id> <agent>`; if REFUSED, run next.sh again), then do it (§2). |
| `IDLE` / `DONE` | Nothing you may start now. End the session (headless: last line `RUNNER: IDLE`). |

**3. One block per session.** When your PR is open (or your fix is pushed), end the session. Headless sessions end
with exactly one line: `RUNNER: DONE <id>`, `RUNNER: BLOCKED <id>` or `RUNNER: IDLE`. The runner starts a fresh
session for the next block (fresh context = fewer tokens). In an interactive session just run next.sh again.

**Tiers in parallel mode:** SMALL does only S / S! blocks. BIG takes B blocks, audits and ANSWERs first, and does S
blocks only when nothing B is ready (next.sh handles this). SMALL never does B work.

## The agent bus (`.agent/bus.sh`) — how the two agents talk
Live state lives in `<repo>/.git/agent-bus/`, which every worktree shares. It is never committed and never conflicts.
| Command | Use |
|---|---|
| `claim <id> <agent>` / `set <id> <state> [pr]` | Own a task. States: `working`, `pr`, `red`, `conflict`, `blocked`, `merged`. |
| `say <from> <to\|all> <TYPE> <text>` | Message the other agent. TYPE: `INFO`, `ASK`, `ANSWER`, `WARN`, `HANDOFF`. |
| `inbox <agent>` | Read messages to you (new ones have `*`). **Read it at the start of every session.** |
| `asks` | Open questions (an ASK is closed by an ANSWER starting `#<its id>`). |
| `log <agent> <id> <text>` | Journal line (replaces `.agent/journal.md`). |
| `beat <agent> <text>` | Heartbeat. A claim is taken over only if its owner has been silent for 24 h. |
| `decide <agent> <id> <text>` | Writes the decision into `.agent/decisions.md` on `dev`, and tells everyone. |
| `serial -- <cmd>` | Runs `<cmd>` only while no other agent runs one. **Use it for every Playwright run, full suite and `pnpm build`** (the e2e ports 3100/3101/8100 are shared). |
| `status` | Heartbeats, claims, open asks, last journal lines. |

Message format (`messages.log`): `YYYY-MM-DD HH:MM | from -> to | TYPE | text`. Keep each message to one line.
**Questions:** SMALL agents never stop to wait. Post `say <agent> all ASK "<id>: <question, options, your recommendation>"`,
`set <id> blocked`, end the session with `RUNNER: BLOCKED <id>`. When an ANSWER arrives in your inbox, `set <id> working` and continue.
Before asking, check `.agent/decisions.md`: the answer may already be there.

## Source of truth
- `micro_plan.md`: the task list and steps. `changesneeded.md`: fixes from the last audit (next.sh offers them first).
- `.agent/deps.txt`: which blocks must be merged before another may start. Blocks not listed run in parallel.
- `.agent/decisions.md`: every decision the agents took themselves (append-only, written by `bus.sh decide`).
- `plan.md`: the full spec. Read only the lines a block cites. If it conflicts with `micro_plan.md` on behaviour, `plan.md` wins.
- `leftover.md`: work parked until the owner supplies something (e.g. Stripe keys). Must be done before Phase 23.
- `audit.md`: auditor instructions (BIG only). `deployment-requirements.txt`: accounts, keys, env var names.
- `PROGRESS.md`: permanent log, written at phase gates. `STATUS.md`: a snapshot written at phase gates only; live state is `bus.sh status`.
- Git: every commit message carries a `Next:` line.

## 1. Start of every session (protect unsaved work BEFORE any pull)
1. In your worktree: `git status --short`, `git branch --show-current`, `git log -3 --format='%h %s%n%b'`,
   `bash .agent/bus.sh inbox <agent>`, and `bash .agent/bus.sh status` (your last journal lines and claims).
2. **Uncommitted changes = you were cut off.** Commit them at once on the current branch:
   `git add -A && git commit -m "wip(<id>): recovered from cut-off" -m "Next: review and finish"`, push. Then review and continue.
   **Forbidden at all times:** `git checkout .`, `git checkout -- <file>`, `git restore`, `git reset --hard`, `git clean`,
   `git stash` (any form), `git pull` with a dirty tree, force-push to `dev` or `main`. (Force-push with lease is allowed
   only on your own `task/<id>` branch after a rebase.)
3. `git fetch origin`. `bash .agent/bus.sh beat <agent> "<id>: starting"`.
4. If the stack is down: `docker compose up -d --wait` (repo root). If `dev` itself is red (CI on `dev` or a merged PR
   broke it), fixing it is your task: claim `FIX-dev`, branch `task/FIX-dev`.

## 2. Doing a block
1. Branch from the latest dev: `git switch -c task/<id> origin/dev` (the claim's branch name). One block per branch.
2. Read only the `plan.md` lines the block cites. Run lint, type-check and the tests for the area you touch.
3. **After every Step of the block:** `bash .agent/bus.sh log <agent> <id> "step N done: X (tests: real counts) | next Y"`,
   then commit and push the branch (`wip(<id>): <what>` + a `Next:` line). Push before any long command.
4. When the block's "Done when" passes: final commit `feat(area): <title> (<id>)` (or `fix(<id>): ...`), push, then
   `gh pr create --base dev --head task/<id> --title "[<id>] <title>" --body "<what, tests run with real counts>"`, and
   `bash .agent/bus.sh set <id> pr <n>`. **Don't wait for CI.** End the session.
5. **Do NOT tick** the block in `micro_plan.md`/`changesneeded.md`, and do not edit `STATUS.md`, `.agent/journal.md` or
   `PROGRESS.md` on a task branch (gates excepted). `prs.sh` ticks the block on `dev` when the PR merges. (Parallel PRs
   ticking neighbouring lines would conflict.)
6. If the block needs a decision that isn't in the plan or `decisions.md`: BIG decides the simplest safe option and records
   it with `bus.sh decide`; SMALL asks (see the bus section). Never ask the owner, except for keys, accounts or money.

## 3. Quality and style
- Change only what the task needs. Don't refactor, rename or restyle earlier work; post suggestions as `say <agent> all INFO`.
- Copy the structure, naming and test style of the nearest similar module, so Codex and Claude code looks the same.
- Two agents touch the repo at once: keep diffs small and local; don't reformat files you didn't change.
- Stop only processes you started yourself (check the PID's parent chain and its cwd are in your own worktree). Never stop the runners, the `prs` loop or the other agent's processes, and never remove a worktree you did not create.
- Never print, log or commit secrets. Never ask the owner to paste a key in chat.
- AI features show only when `ANTHROPIC_API_KEY` is set; otherwise they are hidden, with non-AI fallbacks. Ask Mady chat (T14.4) is deferred.

## 4. Speed rules (tokens and time)
- Read only the plan sections you need. Don't re-read whole files you've already seen this session.
- Run only the tests affected by your change. CI runs the rest on your PR. The full suite runs once, at phase gates.
- Wrap every Playwright run, full suite and production build in `bash .agent/bus.sh serial -- <cmd>`.
- Design QA screenshots only at phase gates (390 + 1280 px; all widths in T22.4). No tests beyond each task's "Done when".
- Keep messages and notes short.

## 5. PRs, CI and merging (`.agent/prs.sh`, run by the runner before every session; you may run it too)
- CI runs on every PR to `dev` and to `main`. `prs.sh` merges a task PR (`task/<id>` → `dev`) as soon as **every** check
  is green, deletes the branch, ticks `<id>` on `dev` and tells everyone. A red PR becomes `FIX-PR` for its owner; a
  conflict becomes `FIX-PR` too (rebase on `origin/dev`, `git push --force-with-lease`).
- Never merge red, never `--admin`, never `--auto` (it merges instantly on this repo), never force-push `dev` or `main`.
- A block whose dependencies (`deps.txt`) are not merged yet is not offered; take another one.

## 6. Phase gates and audits
- **Gate `P<n>`** (offered when every block of Phase n is merged): on `task/P<n>`, Recipe R7 steps 1–3 (full suite via
  `bus.sh serial`, screenshots, 5-line summary in `PROGRESS.md`; don't tick). PR to `dev`. When it merges, `prs.sh`
  ticks the gate; then open `gh pr create --base main --head dev --title "Phase <n>"`; `prs.sh` merges it when green.
- **Audits** (`AUDIT-n`, BIG only, offered when every block above it is merged and no fix is open): run `audit.md` on
  `task/AUDIT-n`; it writes `changesneeded.md` (and ticks `AUDIT-n` itself only on PASS). The fixes are then offered to
  every agent, and the re-audit is offered again once they are all merged. Phases 18–20 do not wait for AUDIT-3; only
  their gates do (`deps.txt`).

## 7. Model tiers
- Each block is tagged **S** (small model OK), **S!** (small model OK, high-risk: follow every "Watch" line), or **B** (big model only).
- Small models: never invent figures, never skip or weaken tests, never claim a pass you didn't see. When unsure, ASK on the bus; don't guess.
