#!/usr/bin/env bash
# Prints the one thing to do next, so an agent doesn't have to read whole files.
# First line is always:  NEXT: <FIX|TASK|AUDIT|DONE> | tier: <tag> | <id>
# Then the block itself. What to do with it: AGENTS.md "Quick start" table.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

# Print the first block whose heading starts with "### [ ]", up to the next heading.
first_open_block() {
  awk '/^##+ /{ if (p) exit; if ($0 ~ /^### \[ \]/) p = 1 } p' "$1"
}

# 1. Open audit fixes come first.
if [ -f changesneeded.md ] && grep -q '^### \[ \]' changesneeded.md; then
  head=$(grep -m1 '^### \[ \]' changesneeded.md)
  id=$(awk '{print $4}' <<<"$head")
  if grep -qE ' · B( |$)' <<<"$head"; then tier=B; else tier=S; fi
  echo "NEXT: FIX | tier: $tier | $id   (open fixes left: $(grep -c '^### \[ \]' changesneeded.md))"
  first_open_block changesneeded.md
  exit 0
fi

# 2. All fixes ticked but the last audit round did not pass -> re-audit.
if [ -f changesneeded.md ] && grep -q '^### \[x\]' changesneeded.md && ! grep -q '^## Result: PASS' changesneeded.md; then
  echo "NEXT: AUDIT | tier: B | re-audit (all changesneeded.md fixes are ticked; see audit.md §1 'Re-audit')"
  exit 0
fi

# 3. Next block of the plan.
head=$(grep -m1 '^### \[ \]' micro_plan.md || true)
if [ -z "$head" ]; then
  echo "NEXT: DONE | tier: - | every micro_plan.md block is ticked"
  exit 0
fi
id=$(awk '{print $4}' <<<"$head")
tier=$(awk -F' · ' '{print $2}' <<<"$head")
if [[ "$id" == AUDIT-* ]]; then
  echo "NEXT: AUDIT | tier: B | $id"
else
  echo "NEXT: TASK | tier: $tier | $id"
fi
first_open_block micro_plan.md
