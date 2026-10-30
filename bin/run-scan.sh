#!/usr/bin/env bash
# Started by cron: one scan in a fresh, non-interactive Claude Code session with a restricted tool allowlist.
# Optional $1 = a custom prompt (web messages, evening time log).
set -u
source "$(dirname "$0")/common.sh"
LOG="$DATA/log.md"

# allowlist: browser (tracker/GitLab), read tools, edits only in project repos and the data dir, a fixed set of shell commands
ALLOWED=(
  "mcp__claude-in-chrome" "Read" "Glob" "Grep" "Agent" "Skill" "TodoWrite"
  "Edit(/$DATA/**)" "Write(/$DATA/**)"
  "Bash(git:*)" "Bash(npm:*)" "Bash(npx:*)" "Bash(node:*)"
  "Bash(mv:*)" "Bash(ln:*)" "Bash(cd:*)" "Bash(ls:*)" "Bash(cat:*)" "Bash(head:*)" "Bash(tail:*)" "Bash(grep:*)"
  "Bash(wc:*)" "Bash(diff:*)" "Bash(date:*)" "Bash(jq:*)" "Bash(sort:*)" "Bash(find:*)" "Bash(notify-send:*)"
  "Bash(python3 $ROOT/web/chat.py:*)"
  "Bash($ROOT/bin/state-jq.sh:*)"
  "Bash($ROOT/bin/eslint-new.sh:*)"
  "Bash(python3 $ROOT/guard/limit-check.py status)"
)
while read -r repo; do
  ALLOWED+=("Edit(/$(expand "$repo")/**)")
done < <(jq -r '.projects[].repo' "$CONFIG")

cd "$(expand "$(cfg .workspace)")" || exit 1
exec 9>"$DATA/.lock"
flock -w 60 9 || { echo "- $(date '+%F %H:%M') skipped: previous run still in progress" >> "$LOG"; exit 0; }

# start/end/exit code for the dashboard - written by this script, independent of what Claude reports
START=$(date '+%F %H:%M')
LIMIT_RE='usage limit|rate.?limit|limit reached|hit your limit|limit will reset|out of (extra )?usage'

(
  echo
  echo "## $(date '+%F %H:%M')"
  # without VPN Claude would only get 403s - do not start it at all (zero tokens)
  if ! WHY=$("$ROOT/bin/tracker-check.sh"); then
    echo "- skipped: $WHY - Claude not started, next attempt per cron"
    exit 77
  fi
  # never extra usage: no start above limits.startBelow, and a watchdog kills the session at limits.killAt or when billing starts
  WHY=$(python3 "$ROOT/guard/limit-check.py" start); lc=$?
  if [ $lc -eq 2 ]; then
    echo "- skipped: $WHY (no answer for 90 s) - next run per cron"
    exit 76
  elif [ $lc -ne 0 ]; then
    echo "- not started: $WHY - waiting for the reset"
    exit 75
  fi
  rm -f "$DATA/.limit-killed"
  (
    while sleep 30; do
      WHY=$(python3 "$ROOT/guard/limit-check.py" watch) && continue
      echo "$WHY" > "$DATA/.limit-killed"
      pkill -TERM -f "^$CLAUDE -p "
      break
    done
  ) &
  GUARD=$!
  # main session (scan, tracker, time log, web chat) on a cheaper model; analysis, code, review and arbiter go to subagents (skill)
  JSON=$(timeout "$(cfg .claude.timeout)" "$CLAUDE" -p "${1:-/ticket-pilot (cron run, no user at the terminal)}

[run start by the clock: $START - use this time in log.md, status.txt and checkedAt; any later time only from \`date\`]" \
    --model "$(cfg .claude.model)" --chrome --allowedTools "${ALLOWED[@]}" --output-format json < /dev/null 2>"$DATA/.last-stderr")
  rc=$?
  kill $GUARD 2>/dev/null
  if [ -e "$DATA/.limit-killed" ]; then
    echo "- interrupted: $(cat "$DATA/.limit-killed") - will resume after the reset (step 0)"
    rm -f "$DATA/.limit-killed"
    exit 75
  fi
  if [ $rc -ne 0 ] && { echo "$JSON"; cat "$DATA/.last-stderr"; } | grep -qiE "$LIMIT_RE"; then
    echo "- Claude limit reached - run did not start / was cut, resumes after the reset"
    exit 75
  fi
  echo "$JSON" | jq -r '.result // "no result"'
  echo "$(date '+%F %H:%M') scan $(echo "$JSON" | jq -r '.total_cost_usd // 0')" >> "$DATA/costs.log"
  exit $rc
) >> "$LOG"
rc=$?

notify() { notify-send -a "Ticket Pilot" "$@" 2>/dev/null; }
if [ $rc -eq 75 ]; then
  # one notification per outage, then silence until the first successful run
  echo "last scan: $(date '+%F %H:%M') - paused: Claude limit, resumes after reset" > "$DATA/status.txt"
  if [ ! -e "$DATA/.limit-hit" ]; then
    date '+%F %H:%M' > "$DATA/.limit-hit"
    notify "⏸ Paused - Claude limit" "Resumes by itself after the limit resets."
  fi
elif [ $rc -eq 77 ]; then
  echo "last scan: $(date '+%F %H:%M') - skipped: tracker unreachable (VPN)" > "$DATA/status.txt"
  if [ ! -e "$DATA/.vpn-down" ]; then
    date '+%F %H:%M' > "$DATA/.vpn-down"
    notify "🔌 No VPN - waiting" "Tracker unreachable. Next attempt per cron."
  fi
elif [ $rc -eq 76 ]; then
  echo "last scan: $(date '+%F %H:%M') - skipped: usage counter not responding" > "$DATA/status.txt"
elif [ $rc -ne 0 ]; then
  echo "last scan: $(date '+%F %H:%M') - error (code $rc), see log.md" > "$DATA/status.txt"
  notify -u critical "⚠ Scan failed" "Code $rc - check Chrome/VPN and $LOG"
fi
# checkedAt = run start by the clock (Claude tends to invent minutes); only for a full cron scan
[ $rc -eq 0 ] && [ -z "${1:-}" ] && "$ROOT/bin/state-jq.sh" --arg t "$START" '.checkedAt=$t' 2>/dev/null
if [ $rc -eq 0 ] && [ -e "$DATA/.limit-hit" ]; then
  echo "- $(date '+%F %H:%M') Claude limit renewed (paused since $(cat "$DATA/.limit-hit"))" >> "$LOG"
  rm -f "$DATA/.limit-hit"
  notify "▶ Running again" "Claude limit renewed."
fi
echo "$START|$(date '+%F %H:%M')|$rc" > "$DATA/.last-scan"
[ $rc -ne 77 ] && rm -f "$DATA/.vpn-down"
python3 "$ROOT/web/dashboard.py" 2>/dev/null
