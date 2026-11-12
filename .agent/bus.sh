#!/usr/bin/env bash
# The agent bus: how Claude Code and Codex share work when they run AT THE SAME TIME.
#
# The live state is kept inside the shared git directory (<repo>/.git/agent-bus/). Every worktree of
# this repo sees the same folder, it is never committed, and it never causes merge conflicts.
# Permanent records (ticks, PROGRESS.md, decisions.md) go to `dev` through `devcommit`, one at a time.
#
#   bash .agent/bus.sh claim   <task> <agent>       claim a task (refused if someone else has it)
#   bash .agent/bus.sh set     <task> <state> [pr]  working | pr | red | conflict | blocked | merged
#   bash .agent/bus.sh claims                       the claim table
#   bash .agent/bus.sh say     <from> <to|all> <TYPE> <text...>   TYPE: INFO ASK ANSWER WARN HANDOFF
#   bash .agent/bus.sh inbox   <agent>              messages to you or to all (new ones are marked *)
#   bash .agent/bus.sh asks                         ASK messages with no ANSWER yet
#   bash .agent/bus.sh log     <agent> <task> <text...>   journal line (replaces .agent/journal.md)
#   bash .agent/bus.sh beat    <agent> <text...>    heartbeat: what you are doing right now
#   bash .agent/bus.sh status                       one screen: heartbeats, claims, open asks, last journal lines
#   bash .agent/bus.sh decide  <agent> <id> <text...>     record a decision in .agent/decisions.md on dev
#   bash .agent/bus.sh devcommit <message> -- <cmd...>    run <cmd> in the coordinator checkout, commit, push dev
#   bash .agent/bus.sh serial -- <cmd...>           run <cmd> while no other agent runs one (Playwright, full
#                                                   suites, builds: the e2e ports 3100/3101/8100 are shared)
#
# Claim table format (claims.tsv, tab separated):  task  agent  branch  state  pr  updated
# Message format (messages.log):  YYYY-MM-DD HH:MM | from -> to | TYPE | text      (ASK ids: the line number)
set -euo pipefail

COMMON=$(git rev-parse --path-format=absolute --git-common-dir)
BUS="$COMMON/agent-bus"
COORD=$(dirname "$COMMON")          # the main checkout, always on dev; nobody does task work there
mkdir -p "$BUS/logs"
touch "$BUS/claims.tsv" "$BUS/messages.log" "$BUS/journal.log"
now() { TZ=Europe/London date '+%Y-%m-%d %H:%M'; }
epoch() { date +%s; }
lock() { exec 9>"$BUS/.lock"; flock -w 120 9; }

cmd=${1:-status}; shift || true
case "$cmd" in
  claim)
    task=$1 agent=$2; lock
    row=$(awk -F'\t' -v t="$task" '$1==t' "$BUS/claims.tsv")
    if [ -n "$row" ]; then
      owner=$(cut -f2 <<<"$row"); state=$(cut -f4 <<<"$row")
      if [ "$owner" != "$agent" ] && [ "$state" != "merged" ]; then
        # A claim can be taken over only when its owner has been silent for 24 hours.
        beat=$(cat "$BUS/beat-$owner.epoch" 2>/dev/null || epoch)
        if [ $(( $(epoch) - beat )) -lt 86400 ]; then echo "REFUSED: $task is claimed by $owner ($state)"; exit 1; fi
        echo "TAKEOVER: $owner silent for 24 h" >&2
      fi
    fi
    awk -F'\t' -v t="$task" '$1!=t' "$BUS/claims.tsv" >"$BUS/claims.tmp"
    printf '%s\t%s\t%s\tworking\t-\t%s\n' "$task" "$agent" "task/$task" "$(now)" >>"$BUS/claims.tmp"
    mv "$BUS/claims.tmp" "$BUS/claims.tsv"; epoch >"$BUS/beat-$agent.epoch"; echo "CLAIMED: $task by $agent (branch task/$task)" ;;
  set)
    task=$1 state=$2 pr=${3:-}; lock
    awk -F'\t' -v OFS='\t' -v t="$task" -v s="$state" -v p="$pr" -v n="$(now)" \
      '$1==t { $4=s; if (p!="") $5=p; $6=n } { print }' "$BUS/claims.tsv" >"$BUS/claims.tmp"
    mv "$BUS/claims.tmp" "$BUS/claims.tsv" ;;
  claims)
    printf 'TASK\tAGENT\tBRANCH\tSTATE\tPR\tUPDATED\n'; cat "$BUS/claims.tsv" ;;
  say)
    from=$1 to=$2 type=$3; shift 3; lock
    echo "$(now) | $from -> $to | $type | $*" >>"$BUS/messages.log"
    echo "sent (id $(wc -l <"$BUS/messages.log"))" ;;
  inbox)
    agent=$1; seen=$(cat "$BUS/seen-$agent" 2>/dev/null || echo 0)
    awk -v a="$agent" -v s="$seen" -F' \\| ' '$2 ~ ("-> (" a "|all)$") { printf "%s#%d %s\n", (NR>s?"*":" "), NR, $0 }' "$BUS/messages.log" | tail -n 20
    wc -l <"$BUS/messages.log" >"$BUS/seen-$agent" ;;
  asks)
    # An ASK is answered when a later ANSWER line starts with "#<its id>".
    awk -F' \\| ' '$3=="ASK" { a[NR]=$0 } $3=="ANSWER" && match($4,/^#[0-9]+/) { delete a[substr($4,2,RLENGTH-1)] }
      END { for (i in a) printf "#%d %s\n", i, a[i] }' "$BUS/messages.log" | sort -t'#' -k2 -n ;;
  log)
    agent=$1 task=$2; shift 2
    echo "$(now) | $agent | $task | $*" >>"$BUS/journal.log" ;;
  beat)
    agent=$1; shift
    echo "$(now) $*" >"$BUS/beat-$agent"; epoch >"$BUS/beat-$agent.epoch" ;;
  status)
    echo "== heartbeats"; for f in "$BUS"/beat-*; do [ -e "$f" ] && [[ "$f" != *.epoch ]] && echo "$(basename "$f" | sed 's/^beat-//'): $(cat "$f")"; done
    echo "== claims (not merged)"; awk -F'\t' '$4!="merged"' "$BUS/claims.tsv"
    echo "== open asks"; "$0" asks
    echo "== journal (last 10)"; tail -n 10 "$BUS/journal.log" ;;
  decide)
    agent=$1 id=$2; shift 2; text="$*"
    "$0" devcommit "docs(decisions): $id" -- bash -c 'printf -- "- %s · %s · %s — %s\n" "$1" "$2" "$3" "$4" >> .agent/decisions.md' _ "$(now)" "$agent" "$id" "$text"
    "$0" say "$agent" all ANSWER "$id: $text" >/dev/null ;;
  devcommit)
    # Serialised commit straight to dev from the coordinator checkout (ticks, decisions, PROGRESS lines).
    msg=$1; shift; [ "${1:-}" = "--" ] && shift
    exec 8>"$BUS/.devlock"; flock -w 600 8
    cd "$COORD"
    [ "$(git branch --show-current)" = dev ] || { echo "coordinator checkout $COORD is not on dev"; exit 1; }
    [ -z "$(git status --porcelain)" ] || { echo "coordinator checkout $COORD is dirty; not touching it"; exit 1; }
    git pull -q --rebase origin dev
    "$@"
    git add -A
    git diff --cached --quiet && { echo "devcommit: nothing changed"; exit 0; }
    git commit -q -m "$msg" -m "Next: bash .agent/next.sh --agent <you>"
    for i in 1 2 3; do git push -q origin dev && break; git pull -q --rebase origin dev; done
    echo "devcommit: $(git rev-parse --short HEAD) $msg" ;;
  serial)
    [ "${1:-}" = "--" ] && shift
    exec 6>"$BUS/.seriallock"
    flock -n 6 || { echo "serial: waiting for the other agent's test run..." >&2; flock -w 5400 6; }
    "$@" ;;
  *) sed -n '2,24p' "$0"; exit 1 ;;
esac
