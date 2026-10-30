#!/usr/bin/env python3
"""Claude limit guard - the agent must NEVER spill into paid extra usage.

  limit-check.py start  - before a run: exit 1 when the 5-hour or weekly limit >= limits.startBelow; stores extra usage as a baseline
  limit-check.py watch  - during a run: exit 1 when a limit >= limits.killAt (margin so 100% is never crossed) or extra usage grew since start
  limit-check.py status - for the agent session: prints usage in %, writes nothing
Exit 0 = OK to work. When the counter is unavailable (network, token, 429): start retries for 90 s, then exit 2 (skip the run);
watch fails closed (exit 1 = kill).
"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from config import DATA, LIMITS  # noqa: E402
from usage import claude_usage  # noqa: E402

HEALTH = DATA / ".health.json"  # shared with the dashboard, so both don't hammer the rate-limited endpoint
BASELINE = DATA / ".credits-baseline"
START_BELOW = LIMITS.get("startBelow", 93)
KILL_AT = LIMITS.get("killAt", 97)


def usage(max_age=90, fallback=300):
    """Fresh-enough reading shared with the dashboard; on 429 accept data younger than `fallback` s (may be a function of the data)."""
    try:
        cached = json.loads(HEALTH.read_text())
    except (OSError, ValueError):
        cached = {}
    now = time.time()
    if cached.get("usage") and now - cached.get("usage_at", 0) < max_age:
        return cached["usage"]
    fresh = claude_usage()
    if fresh:
        cached.update(usage=fresh, usage_at=now)
        try:
            tmp = HEALTH.with_suffix(".lc.tmp")
            tmp.write_text(json.dumps(cached))
            os.replace(tmp, HEALTH)
        except OSError:
            pass
        return fresh
    if callable(fallback) and cached.get("usage"):
        fallback = fallback(cached["usage"])
    if cached.get("usage") and now - cached.get("usage_at", 0) < fallback:
        return cached["usage"]
    return None


def stale_ok(u):
    """How long an old reading is still safe: the headroom to KILL_AT, assuming at most 3 %-points per minute (max 30 min)."""
    used = max((u.get(k) or {}).get("utilization") or 0 for k in ("five_hour", "seven_day"))
    return min(1800, max(0, (KILL_AT - used) / 3 * 60))


def main(mode):
    # The counter answers 429 when asked too often (it can last minutes), so `watch` reads fresh data at most
    # every 60 s and trusts an older reading only as long as the headroom allows.
    u = usage(60, stale_ok) if mode == "watch" else usage()
    if mode == "status":
        if not u:
            print("usage counter unavailable")
            return 0
        print(f"session 5h {(u.get('five_hour') or {}).get('utilization', 0):.0f}% · week {(u.get('seven_day') or {}).get('utilization', 0):.0f}%")
        return 0
    for _ in range(3 if mode == "start" else 0):
        if u:
            break
        time.sleep(30)
        u = usage()
    if not u:
        # fail-closed: starting blind once ended up in paid extra usage
        print("usage counter unavailable - not risking extra usage")
        return 2 if mode == "start" else 1
    threshold = START_BELOW if mode == "start" else KILL_AT
    for key, label in (("five_hour", "session (5 h)"), ("seven_day", "weekly")):
        part = u.get(key) or {}
        used = part.get("utilization") or 0
        if used >= threshold:
            print(f"{label} limit {used:.0f}% (threshold {threshold}%), resets {part.get('resets_at')}")
            return 1
    credits = float((u.get("extra_usage") or {}).get("used_credits") or 0)
    if mode == "start":
        BASELINE.write_text(str(credits))
        return 0
    try:
        base = float(BASELINE.read_text())
    except (OSError, ValueError):
        print("no extra usage baseline - not risking paid usage")
        return 1
    if credits > base:
        print(f"extra usage grew ({base:g} -> {credits:g}) - Claude started billing")
        return 1
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("start", "watch", "status"):
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
