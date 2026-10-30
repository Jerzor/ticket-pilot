"""Shared config for the Python parts: config.json in the repo root (or $TICKET_PILOT_CONFIG).

Falls back to config.example.json, so the demo works on a fresh clone.
$TICKET_PILOT_DATA overrides the data directory (used by the demo).
"""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def expand(p):
    return Path(os.path.expanduser(str(p)))


def _load():
    path = Path(os.environ.get("TICKET_PILOT_CONFIG") or ROOT / "config.json")
    if not path.exists():
        path = ROOT / "config.example.json"
    return json.loads(path.read_text(encoding="utf-8"))


CFG = _load()
DATA = expand(os.environ.get("TICKET_PILOT_DATA") or CFG.get("dataDir", "~/.ticket-pilot"))
DEMO = os.environ.get("TICKET_PILOT_DEMO") == "1"
PROJECTS = CFG.get("projects", {})
TRACKER = CFG.get("tracker", {})
STATUSES = TRACKER.get("statuses", {})
CLAUDE_BIN = str(expand(CFG.get("claude", {}).get("bin", "~/.local/bin/claude")))
LIMITS = CFG.get("limits", {})


def issue_url(nr):
    return TRACKER.get("url", "").rstrip("/") + TRACKER.get("issuePath", "/issues/") + str(nr)
