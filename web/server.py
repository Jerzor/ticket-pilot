#!/usr/bin/env python3
"""Dashboard over the local network (phone, second laptop) + sending commands to the agent (chat.jsonl).

Access only with the token from <dataDir>/.web-token: first visit http://<ip>:<port>/?t=<token>, then a cookie.
Binds to web.host from config (127.0.0.1 by default - set 0.0.0.0 to reach it from a phone on the same LAN).

  server.py --port N - override web.port
  server.py --demo  - serve the fictional demo data (a temporary copy, so the chat can be tried without touching the repo)
"""
import hmac
import os
import secrets
import shutil
import sys
import tempfile
import urllib.parse
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

if __name__ == "__main__" and "--demo" in sys.argv:
    demo = Path(tempfile.mkdtemp(prefix="ticket-pilot-demo-")) / "data"
    shutil.copytree(Path(__file__).resolve().parent.parent / "demo/data", demo)
    os.environ["TICKET_PILOT_DATA"] = str(demo)
    os.environ["TICKET_PILOT_DEMO"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import chat  # noqa: E402
import dashboard  # noqa: E402
from config import CFG, DATA  # noqa: E402

HOST = CFG.get("web", {}).get("host", "127.0.0.1")
PORT = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else int(CFG.get("web", {}).get("port", 8765))
TOKEN_FILE = DATA / ".web-token"
MAX_LEN = 4000


def token():
    if not TOKEN_FILE.exists():
        TOKEN_FILE.write_text(secrets.token_urlsafe(24))
        TOKEN_FILE.chmod(0o600)
    return TOKEN_FILE.read_text().strip()


TOKEN = token()


LOGIN_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ticket Pilot</title><style>
:root{--bg:#f6f7f9;--card:#fff;--fg:#1d2330;--muted:#6b7280;--line:#e5e7eb;--accent:#1d4ed8}
@media (prefers-color-scheme:dark){:root{--bg:#0f1115;--card:#181b22;--fg:#e5e7eb;--muted:#9ca3af;--line:#2a2f3a;--accent:#93c5fd}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,sans-serif;padding:16px}
form{max-width:420px;margin:12vh auto;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:20px;display:grid;gap:12px}
h1{font-size:18px;margin:0}p{margin:0;color:var(--muted);font-size:13.5px}
input{font:inherit;padding:10px;border-radius:8px;border:1px solid var(--line);background:var(--bg);color:var(--fg)}
button{font:inherit;font-weight:600;padding:10px;border-radius:8px;border:0;background:var(--accent);color:var(--card)}
</style></head><body><form method="get" action="/"><h1>Ticket Pilot</h1>
<p>This device has no access yet. Paste the token (the .web-token file in the data directory) - it is remembered for a year.</p>
<input name="t" autocomplete="off" autocapitalize="off" spellcheck="false" placeholder="token" required autofocus><button>Enter</button></form></body></html>""".encode()


class Handler(BaseHTTPRequestHandler):
    def authed(self):
        jar = cookies.SimpleCookie(self.headers.get("Cookie", ""))
        c = jar.get("t")
        return c is not None and hmac.compare_digest(c.value, TOKEN)

    def send(self, code, body=b"", ctype="text/plain; charset=utf-8", headers=()):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Frame-Options", "DENY")
        for k, v in headers:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urllib.parse.urlsplit(self.path)
        q = urllib.parse.parse_qs(url.query)
        if url.path != "/":
            return self.send(404, b"not found")
        if "t" in q:
            if not hmac.compare_digest(q["t"][0], TOKEN):
                return self.send(403, b"wrong token")
            cookie = f"t={TOKEN}; Max-Age=31536000; Path=/; HttpOnly; SameSite=Strict"
            return self.send(303, headers=[("Location", "/"), ("Set-Cookie", cookie)])
        if not self.authed():
            return self.send(403, LOGIN_PAGE, "text/html; charset=utf-8")
        self.send(200, dashboard.render(web=True).encode(), "text/html; charset=utf-8")

    def do_POST(self):
        if urllib.parse.urlsplit(self.path).path != "/send" or not self.authed():
            return self.send(403, b"forbidden")
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_LEN * 4:
            return self.send(413, b"too long")
        form = urllib.parse.parse_qs(self.rfile.read(length).decode("utf-8", "replace"))
        text = (form.get("text") or [""])[0].strip()[:MAX_LEN]
        if text:
            chat.append("user", text)
        self.send(303, headers=[("Location", "/#chat")])

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    if "--demo" in sys.argv:
        print(f"Ticket Pilot demo: http://{HOST}:{PORT}/?t={TOKEN}", flush=True)
    else:
        print(f"Ticket Pilot web: http://{HOST}:{PORT}/?t=<token from {TOKEN_FILE}>", flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
