#!/usr/bin/env bash
# `pnpm test:e2e` runs this. Locally, two agents share the e2e ports (3100, 3101, 8100), and Playwright
# would reuse the other agent's servers, so a run waits for the agents' serial lock (.agent/bus.sh serial).
# In CI, or with no agent bus, or inside `bus.sh serial` already, it runs Playwright straight away.
set -euo pipefail
COMMON=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null || true)
LOCK="${COMMON:+$COMMON/agent-bus/.seriallock}"
if [ -n "${CI:-}" ] || [ -n "${AGENT_SERIAL_HELD:-}" ] || [ -z "$LOCK" ] || [ ! -d "$(dirname "$LOCK")" ]; then
  exec playwright test "$@"
fi
exec 6>"$LOCK"
flock -n 6 || { echo "e2e: waiting for the other agent's test run..." >&2; flock -w 5400 6; }
AGENT_SERIAL_HELD=1 playwright test "$@"
