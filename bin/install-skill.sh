#!/usr/bin/env bash
# Renders skill/ into ~/.claude/skills/ticket-pilot with the paths from config.json filled in.
set -euo pipefail
source "$(dirname "$0")/common.sh"
DEST="$HOME/.claude/skills/ticket-pilot"
mkdir -p "$DEST/refs"
WORKER="$(cfg .claude.workerModel)"
for f in SKILL.md refs/analysis.md refs/implementation-review.md refs/release-and-time.md refs/web-chat.md; do
  sed -e "s#{{ROOT}}#$ROOT#g" -e "s#{{DATA}}#$DATA#g" -e "s#{{SKILL}}#$DEST#g" -e "s#{{WORKER_MODEL}}#$WORKER#g" \
    "$ROOT/skill/$f" > "$DEST/$f"
done
echo "skill installed in $DEST (data: $DATA)"
