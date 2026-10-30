#!/usr/bin/env bash
# Every minute, 24/7: new user messages from the web page (chat.jsonl) -> a full agent session via run-scan.sh.
# No messages = zero tokens.
set -u
source "$(dirname "$0")/common.sh"
[ -e "$DATA/.paused" ] && exit 0                                       # paused manually
[ -e "$DATA/.limit-hit" ] && exit 0                                    # Claude limit - wait until a scan confirms the reset
[ -e "$DATA/.lock" ] && ! flock -n "$DATA/.lock" true && exit 0        # a run is in progress - try again in a minute
"$ROOT/bin/tracker-check.sh" >/dev/null || exit 0                      # no VPN -> the message waits, not marked as delivered

# --new: each message is handed to a session once; if the session drops it, the next scan picks it up (step 0)
MSGS=$(python3 "$ROOT/web/chat.py" pending --new) || exit 0
[ -n "$MSGS" ] || exit 0
python3 "$ROOT/web/chat.py" prune
# conversation context (last 30 messages) - every session starts fresh
HIST=$(python3 "$ROOT/web/chat.py" history --limit 30)

"$ROOT/bin/run-scan.sh" "/ticket-pilot - handle new user messages from the web page (chat.jsonl). Handle them first per refs/web-chat.md, then a regular scan only if the last one was >= 45 min ago. Messages (TS<tab>text):
$MSGS

Conversation so far (oldest first; full messages: chat.py history --chars 100000):
$HIST"
rc=$?
# Claude never started (73 lock busy, 76 usage counter down, 77 no VPN) -> forget the "delivered" marker, so the next
# minute hands the same messages over again. Not after a crash: retrying every minute could burn tokens in a loop.
case $rc in 73|76|77) rm -f "$DATA/.web-triggered" ;; esac
exit $rc
