#!/usr/bin/env bash
# Keeps one agent working for ever, in its own git worktree, and restarts it after a usage limit.
#   bash .agent/run.sh claude        (Claude Code; CLAUDE_MODEL=sonnet by default -> SMALL)
#   bash .agent/run.sh codex         (Codex CLI;  model from ~/.codex/config.toml   -> BIG)
# Normally started by .agent/start.sh inside tmux. Stop it with Ctrl-C or `bash .agent/start.sh stop`.
#
# Each loop: merge green PRs (prs.sh) -> heartbeat -> one headless session that does ONE block ->
# read its last line:  RUNNER: DONE <id> | RUNNER: IDLE | RUNNER: BLOCKED <id>
#   DONE/BLOCKED -> start the next session after 30 s (fresh context each block keeps cost down)
#   IDLE         -> wait IDLE_SLEEP (10 min) for PRs and dependencies
#   no RUNNER line (usage limit, crash, cut off) -> wait LIMIT_SLEEP (15 min), then try again. A session
#   started while the limit is still on ends at once, so retrying costs nothing; work resumes by itself.
#
# Env overrides: CLAUDE_MODEL, CODEX_MODEL, AGENT_TIER (S|B), CLAUDE_FLAGS, CODEX_FLAGS,
#                IDLE_SLEEP, LIMIT_SLEEP, SESSION_TIMEOUT (default 4h).
set -uo pipefail
AGENT=${1:?usage: run.sh <claude|codex>}
COMMON=$(git -C "$(dirname "$0")" rev-parse --path-format=absolute --git-common-dir)
COORD=$(dirname "$COMMON"); BUS="$COMMON/agent-bus"
WT="$(dirname "$COORD")/$(basename "$COORD")-wt/$AGENT"
IDLE_SLEEP=${IDLE_SLEEP:-600} LIMIT_SLEEP=${LIMIT_SLEEP:-900} SESSION_TIMEOUT=${SESSION_TIMEOUT:-4h}
mkdir -p "$BUS/logs"

case $AGENT in
  claude) MODEL=${CLAUDE_MODEL:-sonnet}
          case $MODEL in *opus*|*fable*) DEF_TIER=B;; *) DEF_TIER=S;; esac ;;
  codex)  MODEL=${CODEX_MODEL:-$(sed -n 's/^model *= *"\(.*\)"/\1/p' ~/.codex/config.toml 2>/dev/null | head -1)}
          case $MODEL in *sol*|*solo*) DEF_TIER=B;; *) DEF_TIER=S;; esac ;;
  *) echo "agent must be claude or codex"; exit 2 ;;
esac
TIER=${AGENT_TIER:-$DEF_TIER}

setup_worktree() {
  if [ ! -d "$WT" ]; then
    git -C "$COORD" fetch -q origin dev
    git -C "$COORD" worktree add --detach "$WT" origin/dev
  fi
  # Untracked local env files (never committed) are linked from the main checkout.
  (cd "$COORD" && git ls-files --others --ignored --exclude-standard -- '.env' '.env.*' 'api/.env*' 'web/.env*') |
    while read -r f; do [ -e "$WT/$f" ] || ln -s "$COORD/$f" "$WT/$f"; done
  [ -d "$WT/web/node_modules" ] || (cd "$WT/web" && pnpm install --frozen-lockfile)
  [ -d "$WT/api/.venv" ] || (cd "$WT/api" && uv sync)
}

prompt() { cat <<EOF
Read AGENTS.md and continue.
You are agent=$AGENT, tier=$( [ "$TIER" = B ] && echo BIG || echo SMALL ), model=$MODEL. You run headless under .agent/run.sh in the
worktree $WT, at the same time as the other agent. Follow AGENTS.md "Parallel mode" (it replaces the relay rules).
Do exactly ONE block: the one \`bash .agent/next.sh --agent $AGENT --tier $TIER\` gives you. Never ask the owner and never wait:
SMALL agents post an ASK on the bus and move on; BIG agents decide and record it with bus.sh decide.
Your final message must end with exactly one of these lines:
RUNNER: DONE <id>      (PR opened or fix pushed)
RUNNER: BLOCKED <id>   (ASK posted, claim set to blocked)
RUNNER: IDLE           (next.sh said IDLE or DONE)
EOF
}

run_session() {   # $1 = log file
  local p; p=$(prompt)
  cd "$WT" || return 1
  if [ "$AGENT" = claude ]; then
    # shellcheck disable=SC2086
    timeout "$SESSION_TIMEOUT" claude -p "$p" --model "$MODEL" ${CLAUDE_FLAGS:---permission-mode auto} >"$1" 2>&1
  else
    # shellcheck disable=SC2086
    # Codex's own sandbox keeps .git read-only (it could not commit or use the bus), so it runs without it,
    # inside .agent/jail.sh instead: write access to this project, its caches and ~/.codex only, no Docker.
    timeout "$SESSION_TIMEOUT" bash "$COORD/.agent/jail.sh" codex exec -C "$WT" -m "$MODEL" \
      ${CODEX_FLAGS:---dangerously-bypass-approvals-and-sandbox} \
      "$p" >"$1" 2>&1 </dev/null
  fi
}

setup_worktree || { echo "worktree setup failed"; exit 1; }
echo "run.sh: $AGENT tier=$TIER model=$MODEL worktree=$WT"
fails=0
while true; do
  bash "$COORD/.agent/prs.sh" || true
  bash "$COORD/.agent/bus.sh" beat "$AGENT" "runner: session starting (tier $TIER)"
  log="$BUS/logs/$AGENT-$(date +%Y%m%d-%H%M%S).log"
  echo "$(date '+%F %T') session -> $log"
  run_session "$log"; rc=$?
  last=$(grep -E '^RUNNER: (DONE|BLOCKED|IDLE)' "$log" | tail -n 1)
  echo "$(date '+%F %T') rc=$rc ${last:-no RUNNER line}"
  case $last in
    "RUNNER: IDLE"*) fails=0; bash "$COORD/.agent/bus.sh" beat "$AGENT" "runner: idle, next try in $((IDLE_SLEEP/60)) min"; sleep "$IDLE_SLEEP" ;;
    "RUNNER: "*)     fails=0; sleep 30 ;;
    *) fails=$((fails+1))
       if tail -n 40 "$log" | grep -qiE 'usage limit|limit reached|hit your limit|out of (credits|usage)|quota|resets? (at|in)|429'; then
         why="usage limit"; else why="session ended without a RUNNER line (rc $rc)"; fi
       wait=$(( LIMIT_SLEEP * (fails > 4 ? 2 : 1) ))
       bash "$COORD/.agent/bus.sh" beat "$AGENT" "runner: $why; retry in $((wait/60)) min"
       echo "$(date '+%F %T') $why; sleeping $((wait/60)) min"; sleep "$wait" ;;
  esac
done
