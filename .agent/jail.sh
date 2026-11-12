#!/usr/bin/env bash
# Runs a command (Codex) with write access to THIS project only, using bubblewrap.
#   bash .agent/jail.sh <cmd...>
# Writable: the main checkout (cmr_hr/), the agent worktrees (cmr_hr-wt/), Codex's own state (~/.codex),
# and the package caches (~/.cache, ~/.local/share/pnpm). Everything else is read-only. /tmp is private.
# The Docker socket is hidden (access to it would mean root on this machine), so start the stack yourself:
# `docker compose up -d --wait`. The network stays on (git push, gh, package installs, the local test stack).
set -euo pipefail
COMMON=$(git -C "$(dirname "$0")" rev-parse --path-format=absolute --git-common-dir)
COORD=$(dirname "$COMMON"); WTROOT="$COORD-wt"
mkdir -p "$WTROOT" "$HOME/.cache" "$HOME/.local/share/pnpm"
args=(--ro-bind / / --dev /dev --proc /proc --tmpfs /tmp --die-with-parent
      --bind "$COORD" "$COORD" --bind "$WTROOT" "$WTROOT"
      --bind "$HOME/.codex" "$HOME/.codex" --bind "$HOME/.cache" "$HOME/.cache"
      --bind "$HOME/.local/share/pnpm" "$HOME/.local/share/pnpm")
for s in /run/docker.sock /var/run/docker.sock; do
  [ -S "$s" ] && [ ! -L "$s" ] && args+=(--ro-bind /dev/null "$s")
done
exec bwrap "${args[@]}" "$@"
