# AGENTS.md — rules for every AI agent on this repo (Claude Code, Codex, any other)

Two agents (Claude Code and Codex) work on this repo **one at a time, in relay**. The owner starts one, it works until its usage limit or a stop point, and then the owner starts the other.
**You can be cut off at any second without warning.** Work so that a different agent can continue from whatever you left behind, even if you never got to write a handover.

## Source of truth
- `plan.md`: what to build and in what order (Section 9). Follow it exactly.
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
5. Read only the plan sections the task needs.
6. Run lint, type-check and the tests for the area you'll touch. If `dev` is red, fixing it is your first task.

## 2. While working: checkpoint constantly
- **Break each task into sub-steps** (for example: model → migration → service → API → tests → UI → UI test). List them as a checklist under "Current task" in `STATUS.md`.
- **After every sub-step, do all three together:**
  1. append one line to `.agent/journal.md`: `YYYY-MM-DD HH:MM | agent | Txx | did X | next Y`;
  2. tick the sub-step and update the resume note in `STATUS.md`;
  3. commit **and push** in one go, with STATUS.md and the journal included:
     ```
     wip(Txx): <what was done>

     Next: <exact next action, file(s)>
     ```
  This way the status is never more than one sub-step behind, even if you're cut off.
- **Commit and push before** any long-running command (full test suite, Playwright, builds, big refactors).
- Don't sit on more than ~20 minutes of unpushed work.
- When a task is fully done: a final commit `feat(area): <title> (Txx)` with a `Next:` line, then tick it in `PROGRESS.md`.

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
- After Phases 7, 14 and 20: set `State: BLOCKED — audit requested` and stop. The owner runs an audit with a high-level model, and the fixes come back as tasks in `STATUS.md` "Next tasks".

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
