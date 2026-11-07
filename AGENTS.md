# AGENTS.md — rules for every AI agent on this repo (Claude Code, Codex, any other)

Two agents (Claude Code and Codex) work on this repo **one at a time, in relay**. The owner starts one, it works until its usage limit or a stop point, and then the owner starts the other.
**You can be cut off at any second without warning.** Work so that a different agent can continue from whatever you left behind, even if you never got to write a handover.

## Quick start — the owner ALWAYS types only "Read AGENTS.md and continue" (any model, Claude Code or Codex)
The owner never tells you what to do or which tier you are. You decide, from this section, and you tell the owner which model to start next.

**0. Know your tier.** **BIG** = Claude Opus (any version), Claude Fable, Solo 6.1 (the owner may add names to this line).
Every other model is **SMALL** (Haiku, Sonnet, Luna, any mini model…). If you can't tell which model you are, you are SMALL.

1. Do §1 below (save any cut-off work, sync).
2. Run `bash .agent/next.sh`. It prints a `NEXT:` line with a kind (`FIX`, `TASK`, `AUDIT`) and the tier tag, then the block.
3. Act by this table. Repeat steps 2–3 after every finished block until you hit a stop.

| `next.sh` shows | If you are SMALL | If you are BIG |
|---|---|---|
| `FIX` tagged S/S!/P* (not `· B`) | do it | stop → **START SMALL MODEL** |
| `FIX` tagged `· B` | stop → **BIG MODEL TASK** | do it |
| `TASK` tagged S or S! | do it | stop → **START SMALL MODEL** |
| `TASK` tagged B | stop → **BIG MODEL TASK** | do it, then keep going while the next block is B |
| `AUDIT` (an `AUDIT-n` block, or a re-audit after fixes) | stop → **AUDIT NEEDED** | run `audit.md` fully, then go back to step 2 |

**How to stop:** set `STATUS.md` State (`BLOCKED — needs big model (Txx)`, `BLOCKED — audit requested (AUDIT-n)` or
`HANDED OVER — small model next`), commit `chore(status): <state>` with a `Next:` line, push. Then make your **final message
exactly one** of these (first line, word for word; one more line with the task id is fine):
- `⚠ BIG MODEL TASK — start Opus / Solo 6.1 and type: Read AGENTS.md and continue`
- `⚠ AUDIT NEEDED FIRST — start Opus / Solo 6.1 and type: Read AGENTS.md and continue`
- `✓ BIG-MODEL WORK DONE — start a small model and type: Read AGENTS.md and continue`

If you are cut off by a usage limit before you can stop, that's fine: the owner starts another model of the same size with the same sentence.

## Source of truth
- `micro_plan.md`: **the task list and steps** for all remaining work (T10.3 onward). Work through it top to bottom.
- `changesneeded.md`: fixes from the last audit. **Always done before** new `micro_plan.md` tasks. Tick each item (`### [x]`) with its fix commit.
- `audit.md`: instructions for the auditor (big model) only. Small models don't read it.
- `plan.md`: the full **spec** (behaviour, rules, data). Read only the lines a `micro_plan.md` block cites. If it conflicts with `micro_plan.md` on behaviour, `plan.md` wins: note it in STATUS.
- `deployment-requirements.txt`: accounts, keys and env var names.
- `PROGRESS.md`: permanent log; finished tasks ticked, one line each.
- `STATUS.md`: live state (current only, overwritten). It may be stale; see Recovery.
- `.agent/journal.md`: append-only work journal, one line per step. It is the cut-off safety net.
- **Git history:** every commit message carries a `Next:` line. Even if nothing else was updated, the last commit tells the next agent what to do.

## Where to work
- Both agents use the **same local folder** (Codex CLI and Claude Code on the owner's machine), so even uncommitted work survives a cut-off.
- Work on branch **`dev`**. `main` is protected. At each phase gate, open a PR `dev → main` and merge only when CI is green.

## 1. Start of every session (order matters — protect unsaved work BEFORE any pull)
1. **Look first, change nothing:**
   - `git branch --show-current`: must be `dev`. If it isn't, and step 2 finds unsaved changes, do NOT switch branches yet.
   - `git status --short`: uncommitted changes mean the last agent was cut off mid-work.
   - `git log -5 --format='%h %s%n%b'`: read the latest `Next:` lines.
   - `tail -n 30 .agent/journal.md`, then compare with `STATUS.md`. **If they disagree, git and the journal win over STATUS.**
2. **If there are uncommitted changes, save them first:**
   - **Forbidden at all times:** `git checkout .`, `git checkout -- <file>`, `git restore`, `git reset --hard`, `git clean`, `git stash` (any form), and `git pull` while the tree is dirty.
   - Run `git add -A && git commit -m "wip(Txx): recovered from cut-off" -m "Next: review and finish"` **immediately**, before doing anything else. Save first, judge later.
   - Then review that commit's diff and run the related tests. If the work is good, continue it; if it's broken, fix it in the next commit. Never throw it away.
3. **Only now sync** (the working tree must be clean): `git switch dev` if needed, then `git pull --rebase origin dev`.
   - If the rebase hits a conflict, stop: run `git rebase --abort` and set `State: BLOCKED — merge conflict` in STATUS with the file names. Don't guess.
   - Then `git push origin dev`.
4. Write the corrected state into `STATUS.md` (yourself as the agent, State IN PROGRESS, the task, the sub-steps). Commit and push: `chore(status): start Txx (Codex|Claude)`.
5. Run `bash .agent/next.sh`; read only the `plan.md` lines that block cites.
6. Run lint, type-check and the tests for the area you'll touch. If `dev` is red, fixing it is your first task.

## 2. While working: checkpoint constantly
- **Sub-steps are the numbered Steps of the `micro_plan.md` block.** At task start, copy them as a checklist under "Current task" in `STATUS.md`.
- **After every sub-step (slim checkpoint), do both together:**
  1. append one line to `.agent/journal.md`: `YYYY-MM-DD HH:MM | agent | Txx | step N done: X (tests: real counts) | next Y`;
  2. commit **and push** in one go, with the journal included:
     ```
     wip(Txx): <what was done>

     Next: <exact next action, file(s)>
     ```
  `STATUS.md` is rewritten only at task start, task end, BLOCKED and handover. Between those, the journal and the
  `Next:` lines are the live state (Recovery in §1 already trusts them over STATUS).
- **Commit and push before** any long-running command (full test suite, Playwright, builds, big refactors).
- Don't sit on more than ~20 minutes of unpushed work.
- When a task is fully done: tick it in `micro_plan.md` (`### [x]`) and in `PROGRESS.md` (one line), rewrite `STATUS.md`,
  then a final commit `feat(area): <title> (Txx)` with a `Next:` line.

## 3. Quality and style
- One task at a time, in plan order.
- Change only what the task needs. Don't refactor, rename or restyle earlier work; write suggestions under "Issues / suggestions" in STATUS.
- Copy the structure, naming and test style of the nearest similar module, so Codex and Claude code looks the same.
- If a decision isn't in the plan, make the simplest safe choice and record it under "Strategy / decisions".
- Never print, log or commit secrets. Never ask the owner to paste a key in chat.
- AI features show only when `ANTHROPIC_API_KEY` is set; otherwise they are hidden, with non-AI fallbacks. Ask Mady chat (T14.4) is deferred.

## 4. Speed rules (tokens and time)
- Read only the plan sections you need. Don't re-read whole files you've already seen this session.
- Run only the tests affected by your change. The full suite runs once, at phase gates, never in parallel.
- Design QA screenshots only at phase gates (390 + 1280 px; all widths in T22.4).
- No tests beyond each task's "Done when".
- Keep messages and notes short. Final message to the owner: at most 3 lines.

## 5. Before you stop (if you get the chance)
1. Nothing uncommitted (done commit, or a `wip` commit with a `Next:` line).
2. `STATUS.md` fully filled in (template below), State = HANDED OVER or BLOCKED.
3. Commit and push: `chore(status): handover after Txx (agent)`.
If you are cut off before this, that's fine: the journal, the `Next:` lines and Recovery (step 1.2) cover it.

## 6. Phase gates and audits
- At the end of each phase: run the full suite once, save the screenshots, and write a 5-line phase summary in `PROGRESS.md`. Then open a PR `dev → main`.
- **You have standing permission to merge that PR yourself, without asking:**
  - merge only when **all** CI checks are green, using `gh pr merge <n> --merge --auto` (it waits for green);
  - never use `--admin`, bypass branch protection, or force-push `main`;
  - if CI fails, fix it on `dev` and push; never merge red;
  - after merging, `git pull` on `dev` and continue with the next task. Don't wait for the merge to finish before starting it.
- Gate PRs: `--auto` merges instantly on this repo, so wait for checks yourself (`gh pr checks <n> --watch`) and merge only when all are green (`micro_plan.md` Recipe R7).
- **Audit stops** are the `AUDIT-n` blocks in `micro_plan.md` (after Phases 11, 14, 17, 20 and 22). Stop there with
  `State: BLOCKED — audit requested (AUDIT-n)`. A big model runs `audit.md` and writes the fixes into `changesneeded.md`;
  small models fix them first, then the loop repeats until an audit round has no P0/P1 items.

## 7. Model tiers
- Each `micro_plan.md` block is tagged **S** (small model OK), **S!** (small model OK, high-risk: follow every "Watch" line), or **B** (big model only).
- Who is BIG and what each tier does on each kind of block: the table in "Quick start". A big model never does S/S! blocks (that wastes the expensive model); it hands back.
- Small models: never invent figures, never skip/weaken tests, never claim a pass you didn't see. When unsure, set BLOCKED with the question; don't guess.

## STATUS.md template (overwrite fully each time)
```
# STATUS
Updated: <date time, Europe/London>    Agent: <Claude Code | Codex>    Branch: dev    Commit: <short sha>
State: IN PROGRESS | HANDED OVER | BLOCKED (<reason>)

## Last completed
- Txx — <one line>

## Current task
- Txx — <title>
  - [x] sub-step 1
  - [ ] sub-step 2   <- here
- Resume note: <exact next action, files, what is half-done, how to verify>

## Next tasks
- Txx, Txx, Txx

## Health
- CI on dev: green | red (<why>)    CI on main: green | red
- Local checks run: <areas> — pass/fail

## Issues / suggestions
- <bugs, tech debt, things for the other agent or the auditor>

## Strategy / decisions taken
- <choices not in the plan, and why>

## Owner actions needed
- <real blockers or decisions only>
```
