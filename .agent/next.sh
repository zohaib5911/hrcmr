#!/usr/bin/env bash
# Prints the one thing YOU should do next, for parallel agents (AGENTS.md "Quick start").
#   bash .agent/next.sh --agent <claude|codex> --tier <S|B>
# First line is always:  NEXT: <KIND> | tier: <tag> | <id> ...
#   KIND = FIX-PR (your PR is red or conflicted) | RESUME (your claimed task) | ANSWER (open ASKs, BIG only)
#        | AUDIT (BIG only) | FIX (changesneeded.md item) | TASK (micro_plan.md block) | IDLE | DONE
# Then the block itself. Reads the plan files from origin/dev, so ticks made by prs.sh count at once.
# A block is offered only when: it is open on origin/dev, nobody else has claimed it, every id it needs in
# .agent/deps.txt is ticked, and your tier may do it (SMALL: S/S! only; BIG: B first, else S, never idle).
# Automatic rules: a gate P<n> needs every other block of Phase n; an AUDIT-n needs every block above it
# and no open changesneeded.md item.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
HERE=.agent
AGENT=${AGENT_NAME:-} TIER=${AGENT_TIER:-}
while [ $# -gt 0 ]; do case $1 in --agent) AGENT=$2; shift 2;; --tier) TIER=$2; shift 2;; *) shift;; esac; done
[ -n "$AGENT" ] && [ -n "$TIER" ] || { echo "usage: bash .agent/next.sh --agent <claude|codex> --tier <S|B>"; exit 2; }
BUS="$(git rev-parse --path-format=absolute --git-common-dir)/agent-bus"
mkdir -p "$BUS"; touch "$BUS/claims.tsv" "$BUS/messages.log"
git fetch -q origin dev 2>/dev/null || true
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
git show origin/dev:micro_plan.md >"$TMP/micro_plan.md"
git show origin/dev:changesneeded.md >"$TMP/changesneeded.md" 2>/dev/null || : >"$TMP/changesneeded.md"
git show origin/dev:.agent/deps.txt >"$TMP/deps.txt" 2>/dev/null || cp "$HERE/deps.txt" "$TMP/deps.txt" 2>/dev/null || : >"$TMP/deps.txt"

block_of() {   # print the block with this id from this file
  awk -v id="$2" '/^##+ /{ if (p) exit; if ($0 ~ /^### \[.\] / && $4==id) p=1 } p' "$1"
}
claim_field() { awk -F'\t' -v t="$1" -v c="$2" '$1==t {print $c}' "$BUS/claims.tsv"; }

# 1-2. Your own claims: red or conflicted PRs first, then work in progress.
while IFS=$'\t' read -r task owner branch state pr _; do
  [ "$owner" = "$AGENT" ] || continue
  case $state in
    red|conflict) echo "NEXT: FIX-PR | tier: $TIER | $task   PR #$pr is $state: git switch $branch; gh pr checks $pr; fix, push"; exit 0;;
  esac
done <"$BUS/claims.tsv"
while IFS=$'\t' read -r task owner branch state pr _; do
  [ "$owner" = "$AGENT" ] && [ "$state" = working ] || continue
  echo "NEXT: RESUME | tier: $TIER | $task   (branch $branch)"
  block_of "$TMP/changesneeded.md" "$task"; block_of "$TMP/micro_plan.md" "$task"; exit 0
done <"$BUS/claims.tsv"

# 3. BIG answers open questions before anything else.
if [ "$TIER" = B ]; then
  asks=$(bash "$HERE/bus.sh" asks)
  if [ -n "$asks" ]; then echo "NEXT: ANSWER | tier: B | open ASKs (answer each with bus.sh decide, then bus.sh say <you> <them> ANSWER \"#<id> ...\")"; echo "$asks"; exit 0; fi
fi

# 4-5. Candidate blocks, in file order: changesneeded.md first, then micro_plan.md.
# Each line: file  id  tier  kind  ready(0/1)
awk -v F=changesneeded.md '/^### \[ \] / { t = ($0 ~ / · B( |$)/) ? "B" : "S"; print F "\t" $4 "\t" t "\tFIX" }' \
  "$TMP/changesneeded.md" >"$TMP/cands"
awk -v F=micro_plan.md -v openfix="$(grep -c '^### \[ \]' "$TMP/changesneeded.md" || true)" '
  /^## Phase / { phase = $3 }
  /^### \[.\] / {
    id = $4; ticked = ($0 ~ /^### \[x\]/); n++; ids[n] = id; tk[n] = ticked; ph[n] = phase
    if (!ticked) {
      split($0, f, " · "); tier = f[2]
      if (id ~ /^AUDIT-/) { kind = "AUDIT"; tier = "B"; ok = (openfix == 0); for (i = 1; i < n; i++) if (!tk[i]) ok = 0 }
      else if (id ~ /^P[0-9]+$/) { kind = "GATE"; ok = 1; pending_gate[n] = 1 }
      else { kind = "TASK"; ok = 1 }
      row[n] = F "\t" id "\t" tier "\t" kind; okv[n] = ok
    }
  }
  END {
    for (i = 1; i <= n; i++) if (pending_gate[i]) for (j = 1; j <= n; j++)
      if (j != i && ph[j] == ph[i] && !tk[j] && ids[j] !~ /^AUDIT-/) okv[i] = 0
    for (i = 1; i <= n; i++) if (i in row && okv[i]) print row[i]
  }' "$TMP/micro_plan.md" >>"$TMP/cands"

ticked() { grep -qE "^### \[x\] $1 " "$TMP/micro_plan.md" "$TMP/changesneeded.md"; }
deps_ok() {
  local line dep; line=$(awk -v id="$1" -F': *' '$1==id {print $2}' "$TMP/deps.txt")
  for dep in $line; do ticked "$dep" || return 1; done
}
pick() {   # first ready candidate of the wanted tier
  while IFS=$'\t' read -r file id tier kind; do
    [[ "$tier" == $1 ]] || continue
    owner=$(claim_field "$id" 2); st=$(claim_field "$id" 4)
    if [ -n "$owner" ] && [ "$st" != merged ] && [ "$owner" != "$AGENT" ]; then continue; fi
    deps_ok "$id" || continue
    echo "$file	$id	$tier	$kind"; return 0
  done <"$TMP/cands"
  return 1
}
if [ "$TIER" = B ]; then choice=$(pick 'B' || pick 'S*' || true); else choice=$(pick 'S*' || true); fi

if [ -z "$choice" ]; then
  if ! grep -q '^### \[ \]' "$TMP/micro_plan.md" "$TMP/changesneeded.md"; then echo "NEXT: DONE | tier: - | every block is ticked"; exit 0; fi
  echo "NEXT: IDLE | tier: $TIER | nothing you may start now (claimed by others, waiting on deps/PRs, or another tier)"
  bash "$HERE/bus.sh" claims; exit 0
fi
IFS=$'\t' read -r file id tier kind <<<"$choice"
[ "$kind" = GATE ] && kind=TASK
echo "NEXT: $kind | tier: $tier | $id   (claim first: bash .agent/bus.sh claim $id $AGENT)"
block_of "$TMP/$file" "$id"
