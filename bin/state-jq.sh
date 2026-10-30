#!/usr/bin/env bash
# Atomic state.json update with a jq filter (the agent session may not redirect `jq … > file`): state-jq.sh [--arg k v …] '<filter>'
set -euo pipefail
source "$(dirname "$0")/common.sh"
F="$DATA/state.json"
[ -f "$F" ] || echo '{}' > "$F"
TMP=$(mktemp "$F.XXXX")
trap 'rm -f "$TMP"' EXIT
jq "$@" "$F" > "$TMP"
jq -e . "$TMP" > /dev/null
chmod 664 "$TMP"
mv "$TMP" "$F"
