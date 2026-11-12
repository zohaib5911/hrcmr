#!/usr/bin/env bash
# Start / watch / stop both agents in one tmux session called "agents".
#   bash .agent/start.sh            start Claude Code and Codex (each restarts itself after a usage limit)
#   bash .agent/start.sh attach     watch them (Ctrl-b n = next window, Ctrl-b d = leave them running)
#   bash .agent/start.sh status     heartbeats, claims, open questions, last journal lines
#   bash .agent/start.sh stop       stop both (work in progress stays in the worktrees and on the bus)
# Pick the models with env vars, e.g.  CLAUDE_MODEL=opus bash .agent/start.sh
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
case ${1:-start} in
  start)
    tmux has-session -t agents 2>/dev/null && { echo "already running: bash .agent/start.sh attach"; exit 0; }
    tmux new-session -d -s agents -n claude "bash '$HERE/run.sh' claude; read -r -p 'claude runner stopped; Enter to close'"
    tmux new-window -t agents -n codex "bash '$HERE/run.sh' codex; read -r -p 'codex runner stopped; Enter to close'"
    tmux new-window -t agents -n bus "watch -n 30 bash '$HERE/bus.sh' status"
    echo "started. watch: bash .agent/start.sh attach" ;;
  attach) exec tmux attach -t agents ;;
  status) bash "$HERE/bus.sh" status ;;
  stop)   tmux kill-session -t agents && echo stopped ;;
  *) sed -n '2,8p' "$0" ;;
esac
