"""Claude plan usage (5-hour session window, weekly limit, extra usage) without spending tokens.

Reads the same counter as `/usage` in Claude Code, using the CLI's OAuth token.
Note: this endpoint is not a public, documented API - it may change without notice.
"""
import json
import subprocess
import time
import urllib.request
from pathlib import Path

from config import CLAUDE_BIN

CREDENTIALS = Path.home() / ".claude/.credentials.json"
USAGE_URL = "https://api.anthropic.com/api/oauth/usage"


def claude_usage():
    try:
        cred = json.loads(CREDENTIALS.read_text())["claudeAiOauth"]
        # The OAuth token lives a few hours and only the CLI refreshes it. Nothing calls the CLI overnight,
        # so the first morning check would fail. `claude auth status` costs no tokens and refreshes it.
        if cred.get("expiresAt", 0) / 1000 - time.time() < 600:
            subprocess.run([CLAUDE_BIN, "auth", "status"], capture_output=True, timeout=60)
            cred = json.loads(CREDENTIALS.read_text())["claudeAiOauth"]
        req = urllib.request.Request(USAGE_URL, headers={
            "Authorization": "Bearer " + cred["accessToken"], "anthropic-beta": "oauth-2025-04-20"})
        return json.loads(urllib.request.urlopen(req, timeout=5).read())
    except Exception:
        return None
