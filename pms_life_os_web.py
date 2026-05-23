from __future__ import annotations

import csv
import html
import io
import os
import sqlite3
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


APP_TITLE = "PMS Life OS"
OWNER = "Gauravh Dallvi"
DB_PATH = Path(__file__).with_name("pms_life_os.db")
HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", "8501"))


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task TEXT NOT NULL,
                category TEXT NOT NULL,
                priority TEXT NOT NULL,
                due_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Open',
                reminder_time TEXT NOT NULL,
                recurring TEXT NOT NULL DEFAULT 'None',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS followups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task TEXT NOT NULL,
                owner TEXT NOT NULL,
                category TEXT NOT NULL,
                date_created TEXT NOT NULL,
                due_date TEXT NOT NULL,
                risk TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Open',
                notes TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS communications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel TEXT NOT NULL,
                original_text TEXT NOT NULL,
                final_text TEXT NOT NULL,
                tone_score INTEGER NOT NULL,
                leadership_score INTEGER NOT NULL,
                risk_level TEXT NOT NULL,
                perception_notes TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS perception_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                week_start TEXT NOT NULL,
                reliability INTEGER NOT NULL,
                visibility INTEGER NOT NULL,
                communication INTEGER NOT NULL,
                ownership INTEGER NOT NULL,
                learning INTEGER NOT NULL,
                exercise INTEGER NOT NULL,
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS contractors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contractor TEXT NOT NULL,
                responsiveness INTEGER NOT NULL,
                quality INTEGER NOT NULL,
                delay INTEGER NOT NULL,
                claims INTEGER NOT NULL,
                risk TEXT NOT NULL,
                notes TEXT DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS memory_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                area TEXT NOT NULL,
                item_type TEXT NOT NULL,
                content TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Open',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS content_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                platform TEXT NOT NULL,
                topic TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Idea',
                publish_date TEXT,
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        if conn.execute("SELECT COUNT(*) FROM reminders").fetchone()[0] == 0:
            today = date.today()
            conn.executemany(
                "INSERT INTO reminders (task, category, priority, due_date, status, reminder_time, recurring) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    ("Review high risk follow-ups", "Office", "High", str(today), "Open", "08:30", "Daily"),
                    ("Evening reflection and score update", "Life OS", "Medium", str(today), "Open", "21:00", "Daily"),
                    ("Learning block: contracts case study", "Learning", "Medium", str(today + timedelta(days=1)), "Open", "19:30", "Weekly"),
                ],
            )
            conn.executemany(
                "INSERT INTO followups (task, owner, category, date_created, due_date, risk, status, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    ("Pending contractor claim backup", "Contracts Team", "Claims", str(today - timedelta(days=5)), str(today - timedelta(days=4)), "High", "Open", "Escalate if no documents today."),
                    ("Site progress reconciliation", "Planning", "Progress", str(today - timedelta(days=1)), str(today + timedelta(days=1)), "Medium", "Open", ""),
                ],
            )
            conn.execute(
                "INSERT INTO perception_scores (week_start, reliability, visibility, communication, ownership, learning, exercise, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (str(today - timedelta(days=today.weekday())), 7, 6, 7, 8, 6, 5, "Initial baseline."),
            )
        conn.commit()


def rows(table: str) -> list[sqlite3.Row]:
    with connect() as conn:
        return conn.execute(f"SELECT * FROM {table} ORDER BY id DESC").fetchall()


def esc(value: object) -> str:
    return html.escape("" if value is None else str(value))


def aging(due_date: str) -> int:
    try:
        return (date.today() - date.fromisoformat(due_date)).days
    except ValueError:
        return 0


def sync_escalations() -> int:
    changed = 0
    with connect() as conn:
        for row in conn.execute("SELECT id, due_date, status FROM followups").fetchall():
            if aging(row["due_date"]) > 3 and row["status"] not in ("Closed", "Done", "ESCALATE"):
                conn.execute("UPDATE followups SET status = 'ESCALATE' WHERE id = ?", (row["id"],))
                changed += 1
        conn.commit()
    return changed


def communication_review(text: str) -> dict[str, object]:
    lower = text.lower()
    risk_terms = ["urgent", "delay", "risk", "claim", "penalty", "escalate", "failed", "pending"]
    weak_terms = ["maybe", "try", "sorry", "actually", "just", "i think"]
    leadership_terms = ["action", "owner", "timeline", "confirm", "decision", "support", "next step"]
    risk_hits = sum(term in lower for term in risk_terms)
    weak_hits = sum(term in lower for term in weak_terms)
    leadership_hits = sum(term in lower for term in leadership_terms)
    tone = max(1, min(10, 8 - weak_hits + (1 if "please" in lower else 0)))
    leadership = max(1, min(10, 5 + leadership_hits - weak_hits))
    risk = "High" if risk_hits >= 3 else "Medium" if risk_hits else "Low"
    final = (
        "Dear Team,\n\n"
        + " ".join(text.strip().split())
        + "\n\nProposed next step: please confirm the responsible owner, committed date, and support required for closure.\n\nRegards,\nGauravh"
    )
    notes = "Add clearer ownership, deadline, and next action to improve perception." if leadership < 7 else "Strong message. Keep ownership and timeline visible."
    return {"tone": tone, "leadership": leadership, "risk": risk, "final": final, "notes": notes}


def table(headers: list[str], data: list[list[object]]) -> str:
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{esc(cell)}</td>" for cell in row) + "</tr>" for row in data)
    return f"<div class='table-wrap'><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"


def layout(active: str, content: str) -> bytes:
    nav = [
        ("Dashboard", "/"),
        ("Reminder OS", "/reminders"),
        ("Follow-up Engine", "/followups"),
        ("Communication AI", "/communication"),
        ("Perception", "/perception"),
        ("Contractors", "/contractors"),
        ("Boss Report", "/boss-report"),
        ("Memory/Life/Content", "/memory"),
        ("Export", "/export"),
    ]
    nav_html = "".join(f"<a class='{ 'active' if label == active else '' }' href='{url}'>{label}</a>" for label, url in nav)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{APP_TITLE}</title>
<style>
:root {{ color-scheme: light; --ink:#172033; --muted:#647085; --line:#d8dee9; --accent:#0f766e; --warn:#b45309; --danger:#b91c1c; --bg:#f7f8fb; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; font-family:Segoe UI, Arial, sans-serif; background:var(--bg); color:var(--ink); }}
.shell {{ display:grid; grid-template-columns:240px 1fr; min-height:100vh; }}
aside {{ background:#fff; border-right:1px solid var(--line); padding:18px 14px; position:sticky; top:0; height:100vh; }}
.brand {{ font-size:22px; font-weight:800; margin-bottom:4px; }}
.owner {{ color:var(--muted); font-size:13px; margin-bottom:18px; }}
nav a {{ display:block; padding:10px 12px; border-radius:8px; color:var(--ink); text-decoration:none; margin-bottom:4px; font-size:14px; }}
nav a.active, nav a:hover {{ background:#e6f4f1; color:#075e57; }}
main {{ padding:22px; }}
h1 {{ margin:0 0 4px; font-size:30px; }}
h2 {{ margin:26px 0 10px; font-size:20px; }}
.sub {{ color:var(--muted); margin-bottom:20px; }}
.grid {{ display:grid; grid-template-columns:repeat(6,minmax(120px,1fr)); gap:12px; }}
.card {{ background:#fff; border:1px solid var(--line); border-radius:8px; padding:14px; }}
.kpi-label {{ color:var(--muted); font-size:12px; font-weight:700; text-transform:uppercase; }}
.kpi-value {{ font-size:30px; font-weight:800; margin-top:4px; }}
.split {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; }}
form {{ background:#fff; border:1px solid var(--line); border-radius:8px; padding:14px; margin-bottom:16px; }}
.fields {{ display:grid; grid-template-columns:repeat(3,1fr); gap:10px; }}
label {{ display:block; color:var(--muted); font-size:12px; font-weight:700; margin-bottom:4px; }}
input, select, textarea {{ width:100%; border:1px solid var(--line); border-radius:6px; padding:9px; font:inherit; background:#fff; }}
textarea {{ min-height:90px; }}
button, .button {{ border:0; border-radius:6px; background:var(--accent); color:#fff; padding:10px 14px; font-weight:700; text-decoration:none; cursor:pointer; display:inline-block; }}
.table-wrap {{ overflow:auto; background:#fff; border:1px solid var(--line); border-radius:8px; }}
        table {{ width:100%; border-collapse:collapse; font-size:14px; }}
        th, td {{ padding:9px 10px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }}
        th {{ background:#f0f3f7; font-size:12px; text-transform:uppercase; color:var(--muted); }}
        .notice {{ border-left:4px solid var(--warn); background:#fff8eb; padding:10px 12px; margin-bottom:14px; }}
        .pill {{ display:inline-block; border:1px solid var(--line); border-radius:999px; padding:5px 10px; margin:3px; background:#fff; }}
        .report-section {{ background:#fff; border:1px solid var(--line); border-radius:8px; padding:14px; margin-bottom:14px; }}
        .report-section h2 {{ margin-top:0; }}
        .report-list {{ margin:0; padding-left:18px; }}
        .report-list li {{ margin:7px 0; }}
        .risk {{ color:var(--danger); font-weight:700; }}
        .copy-box {{ width:100%; min-height:280px; resize:vertical; white-space:pre-wrap; }}
        @media (max-width:900px) {{ .shell {{ grid-template-columns:1fr; }} aside {{ position:relative; height:auto; }} .grid,.split,.fields {{ grid-template-columns:1fr; }} }}
        </style>
</head>
<body>
<div class="shell">
<aside><div class="brand">{APP_TITLE}</div><div class="owner">Owner: {OWNER}</div><nav>{nav_html}</nav></aside>
<main><h1>{active}</h1><div class="sub">Office, perception, follow-up, reminders, learning, coaching and consultancy operating system.</div>{content}</main>
</div>
</body>
</html>""".encode("utf-8")


def kpi(label: str, value: object) -> str:
    return f"<div class='card'><div class='kpi-label'>{esc(label)}</div><div class='kpi-value'>{esc(value)}</div></div>"


class App(BaseHTTPRequestHandler):
    def send_html(self, active: str, content: str) -> None:
        body = layout(active, content)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def redirect(self, path: str) -> None:
        self.send_response(303)
        self.send_header("Location", path)
        self.end_headers()

    def form(self) -> dict[str, str]:
        length = int(self.headers.get("Content-Length", "0"))
        data = self.rfile.read(length).decode("utf-8")
        return {k: v[0] for k, v in parse_qs(data).items()}

    def do_GET(self) -> None:  # noqa: N802
        sync_escalations()
        path = urlparse(self.path).path
        if path == "/":
            return self.send_html("Dashboard", self.dashboard())
        if path == "/reminders":
            return self.send_html("Reminder OS", self.reminders())
        if path == "/followups":
            return self.send_html("Follow-up Engine", self.followups())
        if path == "/communication":
            return self.send_html("Communication AI", self.communication())
        if path == "/perception":
            return self.send_html("Perception", self.perception())
        if path == "/contractors":
            return self.send_html("Contractors", self.contractors())
        if path == "/boss-report":
            return self.send_html("Boss Report", self.boss_report())
        if path == "/memory":
            return self.send_html("Memory/Life/Content", self.memory())
        if path == "/export":
            return self.export_csv()
        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        data = self.form()
        path = urlparse(self.path).path
        with connect() as conn:
            if path == "/reminders":
                conn.execute(
                    "INSERT INTO reminders (task, category, priority, due_date, status, reminder_time, recurring) VALUES (?, ?, ?, ?, 'Open', ?, ?)",
                    (data["task"], data["category"], data["priority"], data["due_date"], data["reminder_time"], data["recurring"]),
                )
                return self.redirect("/reminders")
            if path == "/followups":
                conn.execute(
                    "INSERT INTO followups (task, owner, category, date_created, due_date, risk, status, notes) VALUES (?, ?, ?, ?, ?, ?, 'Open', ?)",
                    (data["task"], data["owner"], data["category"], str(date.today()), data["due_date"], data["risk"], data.get("notes", "")),
                )
                return self.redirect("/followups")
            if path == "/communication":
                review = communication_review(data["original_text"])
                conn.execute(
                    "INSERT INTO communications (channel, original_text, final_text, tone_score, leadership_score, risk_level, perception_notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (data["channel"], data["original_text"], review["final"], review["tone"], review["leadership"], review["risk"], review["notes"]),
                )
                return self.redirect("/communication")
            if path == "/perception":
                conn.execute(
                    "INSERT INTO perception_scores (week_start, reliability, visibility, communication, ownership, learning, exercise, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (data["week_start"], data["reliability"], data["visibility"], data["communication"], data["ownership"], data["learning"], data["exercise"], data.get("notes", "")),
                )
                return self.redirect("/perception")
            if path == "/contractors":
                conn.execute(
                    "INSERT INTO contractors (contractor, responsiveness, quality, delay, claims, risk, notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (data["contractor"], data["responsiveness"], data["quality"], data["delay"], data["claims"], data["risk"], data.get("notes", "")),
                )
                return self.redirect("/contractors")
            if path == "/memory":
                if data.get("kind") == "content":
                    conn.execute(
                        "INSERT INTO content_items (platform, topic, status, publish_date, notes) VALUES (?, ?, ?, ?, ?)",
                        (data["platform"], data["topic"], data["status"], data["publish_date"], data.get("notes", "")),
                    )
                else:
                    conn.execute(
                        "INSERT INTO memory_items (area, item_type, content, status) VALUES (?, ?, ?, ?)",
                        (data["area"], data["item_type"], data["content"], data["status"]),
                    )
                return self.redirect("/memory")
        self.send_error(404)

    def dashboard(self) -> str:
        reminders = rows("reminders")
        followups = rows("followups")
        scores = rows("perception_scores")
        open_tasks = sum(r["status"] in ("Open", "Pending") for r in reminders)
        delayed = sum(aging(f["due_date"]) > 0 for f in followups)
        high_risk = sum(f["risk"] == "High" for f in followups)
        latest = scores[0] if scores else None
        perception = round(sum(latest[k] for k in ["reliability", "visibility", "communication", "ownership", "learning", "exercise"]) / 6, 1) if latest else 0
        due = [r for r in reminders if r["status"] not in ("Done", "Closed") and r["due_date"] <= str(date.today())]
        content = "<div class='grid'>" + "".join(
            [kpi("Open Tasks", open_tasks), kpi("Delayed", delayed), kpi("High Risk", high_risk), kpi("Perception", perception), kpi("Learning", latest["learning"] if latest else 0), kpi("Exercise", latest["exercise"] if latest else 0)]
        ) + "</div>"
        content += "<h2>Morning Executive Dashboard</h2>" + table(["Task", "Category", "Priority", "Due", "Reminder", "Recurring"], [[r["task"], r["category"], r["priority"], r["due_date"], r["reminder_time"], r["recurring"]] for r in due])
        content += "<h2>Evening Review Prompt</h2><div class='notice'>What was completed today, what stayed pending, what risk needs escalation, and what one habit protects tomorrow?</div>"
        return content

    def reminders(self) -> str:
        form = """
        <form method="post"><div class="fields">
        <p><label>Task</label><input name="task" required></p>
        <p><label>Category</label><select name="category"><option>Office</option><option>Learning</option><option>Finance</option><option>Coaching</option><option>Vastu</option><option>Content</option><option>Family</option><option>Health</option><option>Spiritual</option></select></p>
        <p><label>Priority</label><select name="priority"><option>High</option><option>Medium</option><option>Low</option></select></p>
        <p><label>Due Date</label><input type="date" name="due_date" required></p>
        <p><label>Reminder Time</label><input type="time" name="reminder_time" value="08:30" required></p>
        <p><label>Recurring</label><select name="recurring"><option>None</option><option>Daily</option><option>Weekly</option><option>Monthly</option></select></p>
        </div><button>Add Reminder</button></form>
        """
        data = [[r["id"], r["task"], r["category"], r["priority"], r["due_date"], r["status"], r["reminder_time"], r["recurring"]] for r in rows("reminders")]
        return form + table(["ID", "Task", "Category", "Priority", "Due", "Status", "Reminder", "Recurring"], data)

    def followups(self) -> str:
        form = """
        <form method="post"><div class="fields">
        <p><label>Task</label><input name="task" required></p><p><label>Owner</label><input name="owner" required></p>
        <p><label>Category</label><select name="category"><option>Claims</option><option>Progress</option><option>Billing</option><option>Design</option><option>Contract</option><option>Site</option><option>Client</option></select></p>
        <p><label>Due Date</label><input type="date" name="due_date" required></p>
        <p><label>Risk</label><select name="risk"><option>High</option><option>Medium</option><option>Low</option></select></p>
        <p><label>Notes</label><input name="notes"></p></div><button>Add Follow-up</button></form>
        """
        data = [[f["id"], f["task"], f["owner"], f["category"], f["date_created"], f["due_date"], f["risk"], f["status"], aging(f["due_date"]), "ESCALATE" if aging(f["due_date"]) > 3 and f["status"] != "Closed" else f["status"]] for f in rows("followups")]
        return form + table(["ID", "Task", "Owner", "Category", "Created", "Due", "Risk", "Status", "Aging", "Computed"], data)

    def communication(self) -> str:
        form = """
        <form method="post"><p><label>Input Type</label><select name="channel"><option>Email</option><option>WhatsApp</option><option>Escalation</option></select></p>
        <p><label>Email / WhatsApp / Escalation</label><textarea name="original_text" required></textarea></p><button>Review and Rewrite</button></form>
        """
        data = [[c["created_at"], c["channel"], c["tone_score"], c["leadership_score"], c["risk_level"], c["perception_notes"], c["final_text"]] for c in rows("communications")]
        return form + table(["Created", "Channel", "Tone", "Leadership", "Risk", "Perception", "Final Version"], data)

    def perception(self) -> str:
        today = date.today()
        week = today - timedelta(days=today.weekday())
        form = f"""
        <form method="post"><div class="fields">
        <p><label>Week Start</label><input type="date" name="week_start" value="{week}" required></p>
        {''.join(f'<p><label>{name.title()}</label><input type="number" min="1" max="10" name="{name}" value="7"></p>' for name in ["reliability","visibility","communication","ownership","learning","exercise"])}
        </div><p><label>Notes</label><textarea name="notes"></textarea></p><button>Save Weekly Score</button></form>
        """
        data = []
        for s in rows("perception_scores"):
            avg = round(sum(s[k] for k in ["reliability", "visibility", "communication", "ownership", "learning", "exercise"]) / 6, 1)
            data.append([s["week_start"], s["reliability"], s["visibility"], s["communication"], s["ownership"], s["learning"], s["exercise"], avg, s["notes"]])
        return form + table(["Week", "Reliability", "Visibility", "Communication", "Ownership", "Learning", "Exercise", "Weekly Score", "Notes"], data)

    def contractors(self) -> str:
        form = """
        <form method="post"><div class="fields">
        <p><label>Contractor</label><input name="contractor" required></p>
        <p><label>Responsiveness</label><input type="number" min="1" max="10" name="responsiveness" value="6"></p>
        <p><label>Quality</label><input type="number" min="1" max="10" name="quality" value="6"></p>
        <p><label>Delay</label><input type="number" min="0" max="10" name="delay" value="3"></p>
        <p><label>Claims</label><input type="number" min="0" max="10" name="claims" value="3"></p>
        <p><label>Risk</label><select name="risk"><option>High</option><option>Medium</option><option>Low</option></select></p>
        </div><p><label>Notes</label><textarea name="notes"></textarea></p><button>Save Contractor</button></form>
        """
        data = []
        for c in rows("contractors"):
            traffic = "Red" if c["risk"] == "High" or c["delay"] >= 7 or c["claims"] >= 7 or c["responsiveness"] <= 3 or c["quality"] <= 3 else "Yellow" if c["risk"] == "Medium" or c["delay"] >= 4 or c["claims"] >= 4 else "Green"
            data.append([c["contractor"], c["responsiveness"], c["quality"], c["delay"], c["claims"], c["risk"], traffic, c["notes"]])
        return form + table(["Contractor", "Responsiveness", "Quality", "Delay", "Claims", "Risk", "Traffic", "Notes"], data)

    def boss_report(self) -> str:
        reminders = rows("reminders")
        followups = rows("followups")
        completed = [r for r in reminders if r["status"] in ("Done", "Closed")]
        pending = [r for r in reminders if r["status"] not in ("Done", "Closed")]
        risks = [f for f in followups if f["risk"] == "High" or f["status"] == "ESCALATE"]

        completed_items = [f"<li>{esc(r['task'])}</li>" for r in completed] or ["<li>No completed items marked yet.</li>"]
        pending_items = [
            f"<li><strong>{esc(r['task'])}</strong><br>Due: {esc(r['due_date'])} | Priority: {esc(r['priority'])} | Reminder: {esc(r['reminder_time'])}</li>"
            for r in pending
        ] or ["<li>No pending reminder items.</li>"]
        risk_items = [
            f"<li><strong>{esc(f['task'])}</strong><br>Owner: {esc(f['owner'])} | Due: {esc(f['due_date'])} | Aging: <span class='risk'>{aging(f['due_date'])} days</span> | Status: {esc(f['status'])}</li>"
            for f in risks
        ] or ["<li>No high-risk or escalated follow-ups.</li>"]
        actions = [
            "Confirm owners for escalated or high-risk items.",
            "Close daily commitments before evening review.",
            "Send one concise update for every delayed follow-up.",
        ]

        report = [f"Daily Summary - {date.today():%d %b %Y}", "", "Completed:"]
        report += [f"- {r['task']}" for r in completed] or ["- None marked completed yet."]
        report += ["", "Pending:"]
        report += [f"- {r['task']} | Due: {r['due_date']} | Priority: {r['priority']} | Reminder: {r['reminder_time']}" for r in pending] or ["- No pending reminder items."]
        report += ["", "Risks:"]
        report += [f"- {f['task']} | Owner: {f['owner']} | Due: {f['due_date']} | Aging: {aging(f['due_date'])} | Status: {f['status']}" for f in risks] or ["- No high-risk or escalated follow-ups."]
        report += ["", "Action Required:", "- Confirm owners for escalated/high-risk items.", "- Close daily commitments before evening review."]
        copy_ready = esc(chr(10).join(report))

        return f"""
        <div class="grid">
            {kpi("Completed", len(completed))}
            {kpi("Pending", len(pending))}
            {kpi("Risks", len(risks))}
            {kpi("Report Date", date.today().strftime("%d %b"))}
        </div>

        <div class="split">
            <section class="report-section">
                <h2>Completed</h2>
                <ul class="report-list">{''.join(completed_items)}</ul>
            </section>
            <section class="report-section">
                <h2>Pending</h2>
                <ul class="report-list">{''.join(pending_items)}</ul>
            </section>
        </div>

        <section class="report-section">
            <h2>Risks</h2>
            <ul class="report-list">{''.join(risk_items)}</ul>
        </section>

        <section class="report-section">
            <h2>Action Required</h2>
            <ul class="report-list">{''.join(f"<li>{esc(action)}</li>" for action in actions)}</ul>
        </section>

        <section class="report-section">
            <h2>Copy-ready Boss Update</h2>
            <textarea class="copy-box" readonly>{copy_ready}</textarea>
        </section>
        """

    def memory(self) -> str:
        areas = ["Office", "Learning", "Finance", "Coaching", "Vastu", "Content", "Family", "Health", "Spiritual"]
        form = """
        <form method="post"><div class="fields">
        <p><label>Area</label><select name="area">""" + "".join(f"<option>{a}</option>" for a in areas) + """</select></p>
        <p><label>Capture Type</label><select name="item_type"><option>Idea</option><option>Pending</option><option>Lesson</option><option>Follow-up</option></select></p>
        <p><label>Status</label><select name="status"><option>Open</option><option>Parked</option><option>Done</option></select></p>
        </div><p><label>Capture</label><textarea name="content" required></textarea></p><button>Save Memory</button></form>
        <h2>Life OS Areas</h2><div>""" + "".join(f"<span class='pill'>{a}</span>" for a in areas) + """</div>
        <h2>Content System</h2>
        <form method="post"><input type="hidden" name="kind" value="content"><div class="fields">
        <p><label>Platform</label><select name="platform"><option>LinkedIn</option><option>Instagram</option><option>YouTube</option></select></p>
        <p><label>Topic</label><input name="topic" required></p>
        <p><label>Status</label><select name="status"><option>Idea</option><option>Draft</option><option>Scheduled</option><option>Published</option></select></p>
        <p><label>Publish Date</label><input type="date" name="publish_date"></p><p><label>Notes</label><input name="notes"></p>
        </div><button>Save Content</button></form>
        """
        memory_data = [[m["area"], m["item_type"], m["content"], m["status"], m["created_at"]] for m in rows("memory_items")]
        content_data = [[c["platform"], c["topic"], c["status"], c["publish_date"], c["notes"]] for c in rows("content_items")]
        return form + "<h2>Memory OS</h2>" + table(["Area", "Type", "Content", "Status", "Created"], memory_data) + "<h2>Content Plan</h2>" + table(["Platform", "Topic", "Status", "Publish", "Notes"], content_data)

    def export_csv(self) -> None:
        output = io.StringIO()
        writer = csv.writer(output)
        for table_name in ["reminders", "followups", "communications", "perception_scores", "contractors", "memory_items", "content_items"]:
            data = rows(table_name)
            writer.writerow([table_name.upper()])
            if data:
                writer.writerow(data[0].keys())
                for row in data:
                    writer.writerow([row[key] for key in row.keys()])
            writer.writerow([])
        body = output.getvalue().encode("utf-8-sig")
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", f"attachment; filename=pms_life_os_{date.today().isoformat()}.csv")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    init_db()
    server = ThreadingHTTPServer((HOST, PORT), App)
    print(f"{APP_TITLE} running at http://127.0.0.1:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
