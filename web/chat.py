#!/usr/bin/env python3
"""User <-> agent conversation through the web page (chat.jsonl). Used by server.py, web-poll.sh and the agent session.

  chat.py pending          - unhandled user messages (ts > state.web.lastTs), format TS<tab>text
  chat.py pending --new    - same, but only messages not yet handed to a session (for web-poll.sh; stores a marker)
  chat.py say [--question] [--issue NR] [TEXT]   - agent reply (reads stdin without TEXT)
  chat.py done TS          - marks user messages up to TS as handled (state.json -> web.lastTs)
  chat.py history [--limit N] [--chars N]  - last N messages (default 30, each cut to 800 chars) - context for a fresh session
  chat.py prune            - drops messages older than 7 days (unhandled ones always stay)
"""
import fcntl
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from config import DATA  # noqa: E402

CHAT = DATA / "chat.jsonl"
STATE = DATA / "state.json"
TRIGGERED = DATA / ".web-triggered"
KEEP_DAYS = 7


def messages():
    try:
        lines = CHAT.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def append(sender, text, question=False, issue=None):
    msg = {"ts": f"{time.time():.6f}", "from": sender, "text": text.strip()}
    if question:
        msg["question"] = True
    if issue:
        msg["issue"] = str(issue).lstrip("#")
    with open(CHAT, "a", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(json.dumps(msg, ensure_ascii=False) + "\n")
    return msg


def last_handled():
    try:
        return float(json.loads(STATE.read_text(encoding="utf-8")).get("web", {}).get("lastTs", 0))
    except (OSError, ValueError, AttributeError):
        return 0.0


def pending(only_new=False):
    since = last_handled()
    if only_new:
        try:
            since = max(since, float(TRIGGERED.read_text().strip()))
        except (OSError, ValueError):
            pass
    msgs = [m for m in messages() if m.get("from") == "user" and float(m["ts"]) > since]
    if only_new and msgs:
        TRIGGERED.write_text(msgs[-1]["ts"])
    return msgs


def done(ts):
    state = json.loads(STATE.read_text(encoding="utf-8"))
    state.setdefault("web", {})["lastTs"] = ts
    tmp = STATE.with_suffix(".web.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, STATE)


def history(limit=30, chars=800):
    out = []
    for m in messages()[-limit:]:
        text = m.get("text", "")
        if len(text) > chars:
            text = text[:chars] + " […]"
        when = time.strftime("%d.%m %H:%M", time.localtime(float(m["ts"])))
        issue = f" #{m['issue']}" if m.get("issue") else ""
        out.append(f"[{when}] {m.get('from')}{issue}: {text}")
    return out


def prune():
    """Rolling window: only messages older than KEEP_DAYS go; unhandled user messages always stay."""
    cutoff = time.time() - KEEP_DAYS * 86400
    handled = last_handled()
    with open(CHAT, "r+", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        lines = f.read().splitlines()
        keep = []
        for line in lines:
            try:
                m = json.loads(line)
                ts = float(m["ts"])
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
            if ts >= cutoff or (m.get("from") == "user" and ts > handled):
                keep.append(line)
        if len(keep) == len(lines):
            return 0
        tmp = CHAT.with_suffix(".prune.tmp")
        tmp.write_text("".join(x + "\n" for x in keep), encoding="utf-8")
        os.replace(tmp, CHAT)
    return len(lines) - len(keep)


def opt(args, name, default):
    if name in args:
        i = args.index(name)
        return int(args[i + 1])
    return default


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    cmd, args = argv[0], argv[1:]
    if cmd == "pending":
        for m in pending("--new" in args):
            print(f"{m['ts']}\t{m['text']}")
    elif cmd == "say":
        question = "--question" in args
        issue = None
        if "--issue" in args:
            i = args.index("--issue")
            issue = args[i + 1]
            args = args[:i] + args[i + 2:]
        args = [a for a in args if a != "--question"]
        text = " ".join(args) if args else sys.stdin.read()
        if not text.strip():
            print("empty message", file=sys.stderr)
            return 1
        append("agent", text, question, issue)
    elif cmd == "history":
        print("\n".join(history(opt(args, "--limit", 30), opt(args, "--chars", 800))))
    elif cmd == "prune":
        prune()
    elif cmd == "done" and args:
        done(args[0])
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
