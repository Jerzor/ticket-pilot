#!/usr/bin/env bash
# Evening retry of today's time log, only when the afternoon run did not finish it (limit, error). Otherwise exits without Claude.
set -u
source "$(dirname "$0")/common.sh"
[ "$(jq -r '.hoursFilledFor // ""' "$DATA/state.json" 2>/dev/null)" = "$(date +%F)" ] && exit 0
exec "$ROOT/bin/run-scan.sh" "/ticket-pilot - evening run: ONLY today's ($(date +%F)) time log per the \"Time log\" section, then set hoursFilledFor. Do nothing else."
