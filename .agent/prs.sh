#!/usr/bin/env bash
# Looks after every open agent PR, with no model involved. Run by .agent/run.sh before each session;
# agents may run it too. Safe to run any number of times (it holds the bus lock while merging).
#
#   task PR  (task/<id> -> dev):  all checks green -> merge, tick <id> on dev, claim = merged
#                                 a check failed    -> claim = red       (next.sh gives it back to its owner)
#                                 merge conflict    -> claim = conflict  (owner rebases on origin/dev)
#   gate PR  (dev -> main):       all checks green -> merge (the dev branch is never deleted)
# Never uses --auto (it merges instantly on this repo) or --admin.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
COMMON=$(git rev-parse --path-format=absolute --git-common-dir)
BUS="$COMMON/agent-bus"; COORD=$(dirname "$COMMON")
mkdir -p "$BUS"; touch "$BUS/claims.tsv"
exec 7>"$BUS/.prlock"; flock -n 7 || { echo "prs.sh: another run is in progress"; exit 0; }
cd "$COORD"

checks_state() {   # green | red | pending
  local b; b=$(gh pr checks "$1" --json bucket --jq '[.[].bucket] | join(" ")' 2>/dev/null || true)
  if [ -z "$b" ]; then echo pending
  elif grep -qE 'fail|cancel' <<<"$b"; then echo red
  elif grep -q pending <<<"$b"; then echo pending
  else echo green; fi
}
owner_of() { awk -F'\t' -v t="$1" '$1==t {print $2}' "$BUS/claims.tsv"; }
state_of() { awk -F'\t' -v t="$1" '$1==t {print $4}' "$BUS/claims.tsv"; }

tick() {   # tick "### [ ] <id> ·" in micro_plan.md or changesneeded.md
  local id=$1 pr=$2
  bash "$HERE/bus.sh" devcommit "chore(tick): $id merged in PR #$pr" -- bash -c '
    for f in changesneeded.md micro_plan.md; do
      [ -f "$f" ] || continue
      awk -v id="$1" -v pr="$2" -v f="$f" '\''
        !done && /^### \[ \] / && $4==id { sub(/^### \[ \] /, "### [x] "); if (f=="changesneeded.md") $0 = $0 " — fixed in PR #" pr; done=1 }
        { print }'\'' "$f" > "$f.tmp" && mv "$f.tmp" "$f"
    done' _ "$id" "$pr"
}

gh pr list --state open --json number,headRefName,baseRefName,mergeable \
  --jq '.[] | [.number, .headRefName, .baseRefName, .mergeable] | @tsv' |
while IFS=$'\t' read -r n head base mergeable; do
  if [ "$base" = dev ] && [[ "$head" == task/* ]]; then
    id=${head#task/}; owner=$(owner_of "$id"); old=$(state_of "$id")
    if [ "$mergeable" = CONFLICTING ]; then
      [ "$old" = conflict ] || { bash "$HERE/bus.sh" set "$id" conflict "$n"
        bash "$HERE/bus.sh" say prs "${owner:-all}" WARN "PR #$n ($id) has a merge conflict: rebase task/$id on origin/dev and push" >/dev/null; }
      continue
    fi
    case $(checks_state "$n") in
      green)
        [ "$mergeable" = MERGEABLE ] || continue
        if gh pr merge "$n" --merge --delete-branch >/dev/null 2>&1; then
          case $id in AUDIT-*) ;; *) tick "$id" "$n" || true;; esac   # the auditor ticks AUDIT-n itself
          bash "$HERE/bus.sh" set "$id" merged "$n"
          bash "$HERE/bus.sh" say prs all INFO "PR #$n ($id) merged into dev" >/dev/null
          # A merged gate opens the dev -> main PR (merged below, on a later run, when green).
          if [[ "$id" =~ ^P([0-9]+)$ ]] && [ -z "$(gh pr list --base main --head dev --state open --json number --jq '.[].number')" ]; then
            gh pr create --base main --head dev --title "Phase ${BASH_REMATCH[1]}" \
              --body "Phase ${BASH_REMATCH[1]} gate (PR #$n). Merged by .agent/prs.sh when every check is green." >/dev/null || true
          fi
          echo "merged #$n $id"
        fi ;;
      red)
        [ "$old" = red ] || { bash "$HERE/bus.sh" set "$id" red "$n"
          bash "$HERE/bus.sh" say prs "${owner:-all}" WARN "PR #$n ($id) CI failed: gh pr checks $n; fix on task/$id and push" >/dev/null; } ;;
      pending)
        [ "$old" = pr ] || bash "$HERE/bus.sh" set "$id" pr "$n" ;;
    esac
  elif [ "$base" = main ] && [ "$head" = dev ]; then
    if [ "$(checks_state "$n")" = green ] && [ "$mergeable" = MERGEABLE ]; then
      gh pr merge "$n" --merge >/dev/null 2>&1 && {
        bash "$HERE/bus.sh" say prs all INFO "gate PR #$n merged into main" >/dev/null; echo "merged gate #$n"; }
    fi
  fi
done
