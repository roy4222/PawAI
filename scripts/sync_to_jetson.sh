#!/usr/bin/env bash
# WSL → Jetson manual sync — formalizes the "safe manual rsync" the team has
# used since the 6/10 ~/sync .env-deletion incident. Same exclude contract as
# `pawai jetson deploy` (tools/sync/rsync-excludes.txt). Does NOT colcon build.
set -euo pipefail
REPO_ROOT="$(git rev-parse --show-toplevel)"
JETSON_HOST="${JETSON_HOST:-jetson-nano}"
JETSON_REPO="${JETSON_REPO:-~/elder_and_dog}"
echo "rsync $REPO_ROOT/ → $JETSON_HOST:$JETSON_REPO/ (exclude contract: tools/sync/rsync-excludes.txt)"
rsync -az --delete \
  --exclude-from="$REPO_ROOT/tools/sync/rsync-excludes.txt" \
  "$REPO_ROOT/" "$JETSON_HOST:$JETSON_REPO/"
echo "✓ sync done. Remember: colcon build --packages-select <pkg> on Jetson if .py changed."
