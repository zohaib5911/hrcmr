#!/usr/bin/env bash
# Prints the one thing to do next, so an agent doesn't have to read whole files.
# Order: open audit fixes in changesneeded.md first, then the first open block of micro_plan.md.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

# Print the first block whose heading starts with "### [ ]", up to the next heading.
first_open_block() {
  awk '/^##+ /{ if (p) exit; if ($0 ~ /^### \[ \]/) p = 1 } p' "$1"
}

if [ -f changesneeded.md ] && grep -q '^### \[ \]' changesneeded.md; then
  echo "== NEXT: audit fix from changesneeded.md (do these before micro_plan.md) =="
  first_open_block changesneeded.md
  echo
  echo "Open audit fixes left: $(grep -c '^### \[ \]' changesneeded.md)"
  exit 0
fi

echo "== NEXT: micro_plan.md =="
first_open_block micro_plan.md
