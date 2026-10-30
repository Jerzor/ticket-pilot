#!/usr/bin/env python3
"""Builds the agent dashboard (dashboard.html) from state files. No Claude, no tokens - cron runs it every minute.

  dashboard.py          - render <dataDir>/dashboard.html
  dashboard.py --demo   - render demo/dashboard.html from the fictional data in demo/data (no network)
"""
import datetime as dt
import html
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if __name__ == "__main__" and "--demo" in sys.argv:
    os.environ["TICKET_PILOT_DATA"] = str(HERE.parent / "demo/data")
    os.environ["TICKET_PILOT_DEMO"] = "1"
sys.path.insert(0, str(HERE.parent / "lib"))
sys.path.insert(0, str(HERE))
from config import CFG, CLAUDE_BIN, DATA, DEMO, PROJECTS, STATUSES, TRACKER, issue_url  # noqa: E402
from usage import claude_usage  # noqa: E402

OUT = (HERE.parent / "demo/dashboard.html") if DEMO else DATA / "dashboard.html"

_COMMON = [("impl", "code"), ("review", "code review"), ("pushed", "push"), ("draft-mr", "draft MR"),
           ("merge-main", "merge main"), ("mr-devel-merged", "devel"), ("pipeline-devel-ok", "devel pipeline")]
STEPS = {
    # direct: devel + main right away, then time log and QA
    "direct": _COMMON + [("mr-main-merged", "main"), ("pipeline-main-ok", "main pipeline"),
                         ("tracker-time", "time log"), ("tracker-status", "to QA")],
    # two-stage: QA on devel; main + manual deploy only after "Ready to Deploy"
    "two-stage": _COMMON + [("tracker-time", "time log"), ("tracker-status", "to QA"),
                            ("mr-main-merged", "main (after QA)"), ("deploy-ok", "deploy"), ("tracker-resolved", "resolved")],
}
SCANS = CFG.get("schedule", {}).get("scans", [])
DONE_STATUSES = {STATUSES.get("testing"), STATUSES.get("resolved")}

e = html.escape


def clock():
    """Real time; in the demo the moment the last scan ended, so the snapshot is consistent on any day."""
    if DEMO:
        try:
            return dt.datetime.strptime((DATA / ".last-scan").read_text().strip().split("|")[1], "%Y-%m-%d %H:%M")
        except (OSError, IndexError, ValueError):
            pass
    return dt.datetime.now()


def read(name, default=""):
    try:
        return (DATA / name).read_text(encoding="utf-8")
    except OSError:
        return default


def running():
    if DEMO:
        return []
    try:
        out = subprocess.run(["pgrep", "-af", "claude -p"], capture_output=True, text=True).stdout
    except OSError:
        return []
    procs = []
    for line in out.splitlines():
        _, _, cmd = line.partition(" ")
        if not cmd.startswith(CLAUDE_BIN) and not cmd.startswith("claude"):
            continue
        prompt = cmd.split(" -p ", 1)[-1]
        kind = "web command" if "chat.jsonl" in prompt else "scan"
        m = re.search(r"#(\d{3,6})", prompt)
        procs.append((kind, m.group(1) if m else None, prompt[:160]))
    return procs


def next_time(times, now):
    if not times:
        return "—"
    if now.weekday() < 5:
        for t in times:
            if t > now.strftime("%H:%M"):
                return t
    return "tomorrow " + times[0] if now.weekday() < 4 else "Mon " + times[0]


def actions(today):
    rows = []
    for line in read("actions.md").splitlines():
        m = re.match(r"- (\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}) (?:\| )?(.*)", line)
        if not m or m.group(1) != today:
            continue
        parts = [p.strip() for p in m.group(3).split("|")]
        issue = parts[0] if parts and parts[0].startswith("#") else ""
        text = parts[1] if issue and len(parts) > 1 else parts[0]
        extra = parts[2] if issue and len(parts) > 2 else ""
        rows.append((m.group(2), issue, text, extra))
    return rows


def costs(today):
    total = 0.0
    for line in read("costs.log").splitlines():
        p = line.split()
        if len(p) >= 4 and p[0] == today:
            try:
                total += float(p[3])
            except ValueError:
                continue
    return total


def link(url, text):
    return f'<a href="{e(url)}" target="_blank" rel="noopener">{e(text)}</a>'


def linkify(text):
    out = e(text)
    out = re.sub(r"(https?://[^\s<]+)", lambda m: f'<a href="{m.group(1)}" target="_blank" rel="noopener">↗</a>', out)
    return out


def mr_links(proj, it):
    base = (PROJECTS.get(proj) or {}).get("gitlab")
    out = []
    for key in ("draftMr", "mrDevel", "mrMain"):
        v = (it.get("release") or {}).get(key) or it.get(key)
        m = re.search(r"(\d+)$", str(v or ""))
        if base and m:
            out.append(link(f"{base}/-/merge_requests/{m.group(1)}", f"!{m.group(1)}"))
    return out


def issue_rows(state):
    rows = []
    ip_id = str((state.get("inProgress") or {}).get("id") or "")
    for nr, it in sorted(state.get("issues", {}).items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 0, reverse=True):
        proj = it.get("project", "")
        status = it.get("status", "")
        if nr == ip_id and status in ("", STATUSES.get("open")):
            status = STATUSES.get("inProgress", "In Progress")  # the session is on it, the tracker status is not saved yet
        waiting = []
        if it.get("waitingForBe"):
            waiting.append(f"backend #{it.get('beTask')} ({it.get('beTaskStatus', '?')})")
        wf = it.get("waitingFor") or ""
        if wf and not it.get("waitingForBe"):
            waiting.append(wf)
        for q in it.get("openQuestions") or []:
            waiting.append(f"answer ({q.get('to', '?')}): {q.get('q', '')}")
        spent, est = it.get("spent"), it.get("estimated")
        logged = (it.get("partialLogged") or {}).get("logged")
        if isinstance(logged, (int, float)) and (not isinstance(spent, (int, float)) or logged > spent):
            spent = logged  # the evening time log may not have updated `spent`
        hours = f"{spent:g} / {est:g} h" if isinstance(spent, (int, float)) and isinstance(est, (int, float)) else "—"
        cls = "ok" if status in DONE_STATUSES else ("wait" if waiting else "work")
        pushed = "" if it.get("branchPushed") or not it.get("branch") else ' <span class="tag">local</span>'
        rows.append(f"""<tr class="{cls}">
<td>{link(issue_url(nr), '#' + nr)}<div class="muted">{e(proj)}</div></td>
<td class="title">{e(it.get('title', ''))}</td>
<td><span class="pill {cls}">{e(status)}</span></td>
<td><code>{e(it.get('branch') or '—')}</code>{pushed} {' '.join(mr_links(proj, it))}</td>
<td class="num">{hours}</td>
<td>{'<br>'.join(e(w) for w in waiting) or '<span class="muted">—</span>'}</td>
</tr>""")
    return "\n".join(rows) or '<tr><td colspan="6" class="muted">no issues in state.json</td></tr>'


def progress(state):
    ip = state.get("inProgress")
    if not ip:
        return ""
    step = ip.get("step", "")
    proj = ip.get("project") or (state.get("issues", {}).get(str(ip.get("id")), {}) or {}).get("project")
    steps = STEPS.get((PROJECTS.get(proj) or {}).get("releaseFlow", "direct"), STEPS["direct"])
    keys = [k for k, _ in steps]
    idx = keys.index(step) if step in keys else -1
    chips = []
    for i, (k, label) in enumerate(steps):
        cls = "done" if i < idx else ("now" if i == idx else "")
        chips.append(f'<li class="{cls}">{e(label)}</li>')
    since = f" · since {e(ip['since'])}" if ip.get("since") else ""
    det = f'<div class="muted">{e(str(ip.get("details", "")))}</div>' if ip.get("details") else ""
    return f"""<div class="card"><h2>Working on: {link(issue_url(ip.get('id', '')), '#' + str(ip.get('id', '?')))} <code>{e(ip.get('branch', ''))}</code><span class="muted">{since}</span></h2>
<ol class="steps">{''.join(chips)}</ol>{det}</div>"""


def last_report():
    parts = re.split(r"\n(?=## )", read("log.md"))
    for p in reversed(parts):
        if p.startswith("## ") and len(p.strip().splitlines()) > 2:
            return p.strip()
    return ""


DEMO_NOTE = """<div class="card muted">Demo with fictional data - a static snapshot of the dashboard. \
Issue and MR links point to example.com. Source and docs: <a href="https://github.com/Jerzor/ticket-pilot">github.com/Jerzor/ticket-pilot</a></div>"""

HEALTH = DATA / ".health.json"
CHECKS = [(TRACKER.get("name", "Tracker"), TRACKER.get("url", "").rstrip("/") + "/", "403 = no VPN"),
          ("GitLab", CFG.get("gitHost", "").rstrip("/") + "/", "")]
CHECKS += [(f"API docs {k}", p["apiDocs"], "") for k, p in PROJECTS.items() if p.get("apiDocs")]


def http_code(url):
    import urllib.error
    import urllib.request

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None

    try:
        return urllib.request.build_opener(NoRedirect).open(url, timeout=4).status
    except urllib.error.HTTPError as err:
        return err.code
    except Exception:
        return 0


USAGE_TTL = 300


def health():
    """Network checks every 60 s; the Claude counter every 5 min (strict rate limit); on error the last good data stays."""
    try:
        cached = json.loads(HEALTH.read_text())
    except (OSError, ValueError):
        cached = {}
    now = clock().timestamp()
    if DEMO:
        return dict(cached, at=now, usage_at=now)
    if now - cached.get("at", 0) < 60:
        return cached
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor() as pool:
        codes = list(pool.map(lambda c: http_code(c[1]), CHECKS))
        usage, usage_at = cached.get("usage"), cached.get("usage_at", 0)
        if now - usage_at >= USAGE_TTL:
            fresh = pool.submit(claude_usage).result()
            if fresh:
                usage, usage_at = fresh, now
    data = {"at": now, "codes": codes, "usage": usage, "usage_at": usage_at}
    try:
        tmp = HEALTH.with_suffix(".tmp")
        tmp.write_text(json.dumps(data))
        os.replace(tmp, HEALTH)
    except OSError:
        pass
    return data


def cron_active():
    if DEMO:
        return 4
    try:
        out = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
    except OSError:
        return 0
    root = str(HERE.parent)
    return sum(1 for line in out.splitlines() if line.strip() and not line.startswith("#") and root in line)


def reset_at(iso):
    try:
        t = dt.datetime.fromisoformat(iso).astimezone()
    except (TypeError, ValueError):
        return ""
    return t.strftime("%H:%M") if t.date() == clock().date() else t.strftime("%a %d.%m %H:%M")


def meter(label, pct, sub):
    pct = max(0, min(100, pct or 0))
    cls = "ok" if pct < 70 else ("wait" if pct < 90 else "bad")
    return f'''<div class="meter"><div class="mrow"><b>{e(label)}</b><span class="num">{pct:.0f}%</span></div>
<div class="bar"><i class="{cls}" style="width:{pct:.0f}%"></i></div><div class="muted">{sub}</div></div>'''


SCAN_RC = {0: "OK", 75: "Claude limit", 76: "usage counter not responding", 77: "tracker unreachable (VPN)"}


def last_scan():
    """Last run-scan.sh run from .last-scan (start|end|code) - written by the script, not by Claude."""
    try:
        start, end, rc = read(".last-scan").strip().split("|")
        a, b = (dt.datetime.strptime(x, "%Y-%m-%d %H:%M") for x in (start, end))
    except ValueError:
        return "last scan: no data"
    day = "" if a.date() == clock().date() else f"{a:%d.%m} "
    why = SCAN_RC.get(int(rc), f"error (code {rc})")
    return f"last scan: {day}{a:%H:%M}–{b:%H:%M} ({int((b - a).total_seconds() // 60)} min) — {why}"


def health_card():
    h = health()
    rows = []
    for (name, url, hint), code in zip(CHECKS, h.get("codes", [])):
        ok = code not in (0, 403) and code < 500
        why = "no connection" if code == 0 else f"HTTP {code}"
        if not ok and hint:
            why += f" ({hint})"
        rows.append(f'<li><span class="dot {"ok" if ok else "bad"}"></span>{e(name)} <span class="muted">{e(why)}</span></li>')
    n = cron_active()
    rows.append(f'<li><span class="dot {"ok" if n else "bad"}"></span>Cron <span class="muted">{"on (" + str(n) + " entries)" if n else "off"}</span></li>')
    u = h.get("usage")
    if u:
        meters = [
            meter("Session limit (5 h)", (u.get("five_hour") or {}).get("utilization"), "resets " + reset_at((u.get("five_hour") or {}).get("resets_at"))),
            meter("Weekly limit", (u.get("seven_day") or {}).get("utilization"), "resets " + reset_at((u.get("seven_day") or {}).get("resets_at"))),
        ]
        ex = u.get("extra_usage") or {}
        if ex.get("is_enabled"):
            d = 10 ** ex.get("decimal_places", 2)
            meters.append(meter("Extra usage (month)", ex.get("utilization"),
                                f'{ex.get("used_credits", 0) / d:.2f} / {ex.get("monthly_limit", 0) / d:.2f} {e(ex.get("currency", ""))}'))
        claude = "".join(meters)
        age = (clock().timestamp() - h.get("usage_at", 0)) / 60
        stale = f' — <b class="bad">STALE reading ({age:.0f} min), counter not responding</b>' if age > 15 else ""
        claude += f'<div class="muted">Claude counter from {dt.datetime.fromtimestamp(h.get("usage_at", 0)):%H:%M}{stale}</div>'
    else:
        claude = '<div class="muted">Claude limit: no data (token expired or no network)</div>'
    when = dt.datetime.fromtimestamp(h.get("at", 0)).strftime("%H:%M:%S")
    return f'''<div class="card"><h2>Health <span class="muted">checked {when}</span></h2><div class="health">
<ul class="checks">{"".join(rows)}</ul><div>{claude}</div></div></div>'''


def cost_card(today):
    return f'''<div class="card"><h2>Cost today</h2><div class="big">${costs(today):.2f}</div>
<div class="muted">API-equivalent cost of today's agent sessions (from costs.log)</div></div>'''


def chat_card(web):
    import chat
    msgs = chat.messages()[-40:]
    handled = chat.last_handled()
    items = []
    for i, m in enumerate(msgs):
        t = dt.datetime.fromtimestamp(float(m["ts"]))
        when = t.strftime("%H:%M") if t.date() == clock().date() else t.strftime("%d.%m %H:%M")
        user = m.get("from") == "user"
        cls = "me" if user else "bot"
        if user and float(m["ts"]) > handled:
            cls += " pending"
        # a question is closed by a user reply or a later agent message about the same issue
        answered = any(x.get("from") == "user" or (m.get("issue") and x.get("issue") == m.get("issue")) for x in msgs[i + 1:])
        if not user and m.get("question") and not answered:
            cls += " ask"
        iss = f'<span class="iss">#{e(m["issue"])}</span> ' if m.get("issue") else ""
        note = '<div class="muted">waiting for the agent</div>' if "pending" in cls else ""
        items.append(f'<li class="{cls}"><time>{e(when)}</time>{iss}<div class="msg">{linkify(m.get("text", ""))}</div>{note}</li>')
    feed = "\n".join(items) or '<li class="muted">no messages</li>'
    if web:
        form = """<form method="post" action="send" id="send"><textarea name="text" id="text" rows="3" maxlength="4000"
placeholder="e.g. take 1042 / release 1042 / an answer to a question"></textarea><button>Send</button></form>
<div class="muted">Checked every minute, 24/7. A reply usually comes in 1–2 min, or after the current job finishes.</div>"""
    else:
        form = '<div class="muted">Sending works on the page served by server.py.</div>'
    return f'<div class="card" id="chat"><h2>Conversation</h2><ul class="chat">{feed}</ul>{form}</div>'


def main():
    page = render(web=False)
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(page, encoding="utf-8")
    os.replace(tmp, OUT)
    if DEMO:
        print(OUT)


def render(web=False):
    now = clock()
    today = now.strftime("%Y-%m-%d")
    try:
        state = json.loads(read("state.json", "{}"))
    except json.JSONDecodeError:
        state = {}
    procs = running()
    limit = read(".limit-hit").strip()
    paused = (DATA / ".paused").exists()
    status = read("status.txt").strip() or "no status.txt"

    if limit:
        banner = ("limit", f"⏸ Paused: Claude limit (since {e(limit)}) — resumes after reset")
    elif paused:
        banner = ("limit", "⏸ Paused manually")
    elif procs or state.get("inProgress"):
        ip = state.get("inProgress") or {}
        what = f"#{ip['id']} ({ip.get('step', '')})" if ip.get("id") else ", ".join("#" + n for _, n, _ in procs if n)
        kind = "web command" if any(k == "web command" for k, _, _ in procs) else "scan"
        banner = ("run", f"● Working: {e(kind)}{(' — ' + e(what)) if what else ''}")
    else:
        banner = ("idle", "○ Waiting for the next run")
    proc_list = "".join(f'<li><b>{e(k)}</b> <span class="muted">{e(p)}…</span></li>' for k, _, p in procs)

    acts = actions(today)
    act_html = "\n".join(
        f'<li><time>{e(t)}</time> <span class="iss">{e(i)}</span> {e(txt)} {linkify(x)}</li>' for t, i, txt, x in reversed(acts)
    ) or '<li class="muted">nothing changed today</li>'

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ticket Pilot</title>
<style>
:root{{--bg:#f6f7f9;--card:#fff;--fg:#1d2330;--muted:#6b7280;--line:#e5e7eb;--ok:#15803d;--okbg:#dcfce7;--wait:#b45309;--waitbg:#fef3c7;--run:#1d4ed8;--runbg:#dbeafe;--work:#6d28d9;--workbg:#ede9fe;--bad:#dc2626}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0f1115;--card:#181b22;--fg:#e5e7eb;--muted:#9ca3af;--line:#2a2f3a;--ok:#4ade80;--okbg:#14321f;--wait:#fbbf24;--waitbg:#3a2a0a;--run:#93c5fd;--runbg:#172554;--work:#c4b5fd;--workbg:#2e1065;--bad:#f87171}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,sans-serif;padding:16px}}
main{{max-width:1200px;margin:0 auto;display:grid;gap:14px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}}
h1{{font-size:18px;margin:0}}h2{{font-size:15px;margin:0 0 10px}}
.top{{display:flex;flex-wrap:wrap;gap:10px 24px;align-items:center;justify-content:space-between}}
.banner{{font-weight:600;padding:6px 12px;border-radius:999px}}
.banner.run{{background:var(--runbg);color:var(--run)}}.banner.idle{{background:var(--line)}}.banner.limit{{background:var(--waitbg);color:var(--wait)}}
.muted{{color:var(--muted);font-size:12.5px}}a{{color:var(--run)}}code{{font-size:12.5px}}.bad{{color:var(--bad)}}
table{{width:100%;border-collapse:collapse}}th,td{{text-align:left;padding:8px 6px;border-top:1px solid var(--line);vertical-align:top}}
th{{font-size:12px;color:var(--muted);font-weight:600;border-top:0}}.num{{white-space:nowrap;font-variant-numeric:tabular-nums}}
.title{{max-width:340px}}.pill{{padding:2px 8px;border-radius:999px;font-size:12.5px;white-space:nowrap}}
.pill.ok{{background:var(--okbg);color:var(--ok)}}.pill.wait{{background:var(--waitbg);color:var(--wait)}}.pill.work{{background:var(--workbg);color:var(--work)}}
.tag{{font-size:11px;padding:1px 6px;border-radius:6px;background:var(--waitbg);color:var(--wait)}}
.steps{{list-style:none;display:flex;flex-wrap:wrap;gap:6px;padding:0;margin:0 0 6px}}
.steps li{{padding:4px 10px;border-radius:999px;border:1px solid var(--line);font-size:12.5px;color:var(--muted)}}
.steps li.done{{background:var(--okbg);color:var(--ok);border-color:transparent}}.steps li.now{{background:var(--runbg);color:var(--run);border-color:var(--run);font-weight:600}}
ul.feed{{list-style:none;margin:0;padding:0}}ul.feed li{{padding:6px 0;border-top:1px solid var(--line)}}ul.feed li:first-child{{border-top:0}}
time{{font-variant-numeric:tabular-nums;color:var(--muted);margin-right:6px}}.iss{{font-weight:600;margin-right:4px}}
main,.grid{{grid-template-columns:minmax(0,1fr)}}.grid{{display:grid;gap:14px}}@media (min-width:821px){{.grid{{grid-template-columns:minmax(0,2fr) minmax(0,1fr)}}}}@media (max-width:820px){{.title{{max-width:none}}}}
.tablewrap{{overflow-x:auto}}.big{{font-size:22px;font-weight:600}}
.health{{display:grid;grid-template-columns:1fr 1fr;gap:6px 24px}}@media (max-width:820px){{.health{{grid-template-columns:1fr}}}}
ul.checks{{list-style:none;margin:0;padding:0}}ul.checks li{{padding:4px 0}}
.dot{{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:8px}}.dot.ok{{background:var(--ok)}}.dot.bad{{background:var(--bad)}}
.meter{{margin-bottom:10px}}.mrow{{display:flex;justify-content:space-between}}
.bar{{height:8px;border-radius:4px;background:var(--line);overflow:hidden;margin:4px 0 2px}}.bar i{{display:block;height:100%}}
.bar i.ok{{background:var(--ok)}}.bar i.wait{{background:var(--wait)}}.bar i.bad{{background:var(--bad)}}
ul.chat{{list-style:none;margin:0 0 12px;padding:0;display:flex;flex-direction:column;gap:8px;max-height:60vh;overflow-y:auto}}
ul.chat li{{max-width:85%;padding:8px 12px;border-radius:12px;border:1px solid var(--line)}}
ul.chat li.bot{{align-self:flex-start}}ul.chat li.me{{align-self:flex-end;background:var(--runbg)}}
ul.chat li.pending{{border-style:dashed}}ul.chat li.ask{{background:var(--waitbg);border-color:var(--wait)}}
.msg{{white-space:pre-wrap;overflow-wrap:anywhere}}
form#send{{display:flex;gap:8px;align-items:flex-end}}
textarea{{flex:1;font:inherit;padding:8px;border-radius:8px;border:1px solid var(--line);background:var(--bg);color:var(--fg);resize:vertical}}
button{{font:inherit;font-weight:600;padding:8px 16px;border-radius:8px;border:0;background:var(--run);color:var(--card);cursor:pointer}}details pre{{white-space:pre-wrap;font-size:12.5px;margin:8px 0 0}}
</style></head><body><main>
{DEMO_NOTE if DEMO and not web else ''}
<div class="card top"><h1>Ticket Pilot</h1><span class="banner {banner[0]}">{banner[1]}</span>
<span class="muted"><b>{e(last_scan())}</b><br>{e(status)}<br>next scan {e(next_time(SCANS, now))} · refreshed {now:%H:%M:%S}</span></div>
{('<div class="card"><h2>Processes</h2><ul class="feed">' + proc_list + '</ul></div>') if procs else ''}
{health_card()}
{progress(state)}
{chat_card(web)}
<div class="card"><h2>Issues</h2><div class="tablewrap"><table>
<tr><th>Issue</th><th>Title</th><th>Status</th><th>Branch / MR</th><th>Hours</th><th>Waiting for</th></tr>
{issue_rows(state)}</table></div></div>
<div class="grid">
<div class="card"><h2>Today ({now:%d.%m})</h2><ul class="feed">{act_html}</ul>
<details><summary class="muted" style="margin-top:12px">last report from log.md</summary><pre>{e(last_report())}</pre></details></div>
{cost_card(today)}
</div></main>
<script>
// reload every 30 s, but not while typing a message
const ta = document.getElementById("text");
try {{ if (ta) {{ ta.value = localStorage.getItem("draft") || ""; ta.oninput = () => localStorage.setItem("draft", ta.value); }} }} catch (_) {{}}
document.getElementById("send")?.addEventListener("submit", () => {{ try {{ localStorage.removeItem("draft"); }} catch (_) {{}} }});
const chat = document.querySelector("ul.chat"); if (chat) chat.scrollTop = chat.scrollHeight;
if (!{'true' if DEMO and not web else 'false'}) setInterval(() => {{ if (!ta || (!ta.value.trim() && document.activeElement !== ta)) location.reload(); }}, 30000);
</script></body></html>"""


if __name__ == "__main__":
    main()
