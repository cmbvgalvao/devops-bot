"""
Learning-path Telegram bot
Carlos Galvão — commute reminder + question of the day, evening daily-log nudge, Sunday check-in

v3 (2026-11-11): follows the Learning vault's tracks by date (SQL → AWS SAA → DevOps)
    instead of the DevOps course that never started. Supabase and the dashboard are gone;
    the vault's daily logs become the progress source in sprint 2 (see BACKLOG.md).
v4 (2026-11-11): reads the daily logs from the vault repo (VAULT_TOKEN): the Sunday check-in
    shows study days, streak, hours per track and the week's "revisit" items; the evening
    nudge is skipped once today's log exists. Without the token it falls back to v3 behaviour.
"""

import html
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

QUESTIONS_DIR = Path(__file__).parent / "questions"

VAULT_REPO = "cmbvgalvao/devops-vault"
LOGS_DIR = "0 Daily Logs"

# Study timeline from the vault's Home note
SQL_END = date(2026, 11, 24)
EXAM_WINDOW = (date(2027, 1, 11), date(2027, 1, 17))
DEVOPS_START = date(2027, 1, 18)

TRACKS = {
    "sql":    {"name": "SQL refresh",       "bank": "sql.json"},
    "saa":    {"name": "AWS SAA",           "bank": "saa.json"},
    "devops": {"name": "DevOps Fast-Track", "bank": "devops.json"},
}

# Which UTC cron entry belongs to which message, and the Lisbon UTC offset (hours) it is meant for.
# Each message has one entry for summer time (UTC+1) and one for winter time (UTC+0);
# the run whose offset doesn't match today's is skipped, so it's 06:30 / 20:00 / 18:00 Lisbon all year.
SCHEDULES = {
    "30 5 * * *": ("morning", 1), "30 6 * * *": ("morning", 0),
    "0 19 * * *": ("evening", 1), "0 20 * * *": ("evening", 0),
    "0 17 * * 0": ("weekly", 1),  "0 18 * * 0": ("weekly", 0),
}


# ─────────────────────────────────────────────
# TIME AND TRACK
# ─────────────────────────────────────────────
def _last_sunday(year: int, month: int) -> date:
    d = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year, 12, 31)
    return d - timedelta(days=(d.weekday() + 1) % 7)


def lisbon_offset(now_utc: datetime) -> int:
    """Hours Lisbon is ahead of UTC: 1 from the last Sunday of March to the last Sunday of
    October (both at 01:00 UTC), otherwise 0. EU rule, no tz database needed."""
    start = datetime.combine(_last_sunday(now_utc.year, 3), datetime.min.time(), timezone.utc) + timedelta(hours=1)
    end = datetime.combine(_last_sunday(now_utc.year, 10), datetime.min.time(), timezone.utc) + timedelta(hours=1)
    return 1 if start <= now_utc < end else 0


def current_track(today: date) -> str:
    if today <= SQL_END:
        return "sql"
    if today < DEVOPS_START:
        return "saa"
    return "devops"


def load_questions(track: str) -> list:
    with open(QUESTIONS_DIR / TRACKS[track]["bank"], encoding="utf-8") as f:
        return json.load(f)


def question_for(track: str, today: date) -> tuple:
    bank = load_questions(track)
    return tuple(bank[today.toordinal() % len(bank)])


# ─────────────────────────────────────────────
# VAULT (daily logs)
# ─────────────────────────────────────────────
def _github(path: str, raw: bool = False):
    req = urllib.request.Request(
        f"https://api.github.com/repos/{VAULT_REPO}/contents/{urllib.parse.quote(path)}",
        headers={
            "Authorization": f"Bearer {os.environ['VAULT_TOKEN']}",
            "Accept": "application/vnd.github.raw" if raw else "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        body = resp.read().decode("utf-8")
    return body if raw else json.loads(body)


def fetch_logs(since: date) -> dict:
    """Daily logs dated `since` or later, as {date: markdown}. Returns None when the
    vault can't be read (no token, network or API error), so callers can fall back."""
    if not os.environ.get("VAULT_TOKEN"):
        return None
    try:
        logs = {}
        for item in _github(LOGS_DIR):
            m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})\.md", item["name"])
            if m and date.fromisoformat(m.group(1)) >= since:
                logs[date.fromisoformat(m.group(1))] = _github(item["path"], raw=True)
        return logs
    except Exception as e:  # never let the vault stop a message from going out
        print(f"[WARN] Could not read the vault: {e}")
        return None


def _field(text: str, label: str) -> str:
    m = re.search(rf"\*\*{re.escape(label)}:\*\*[ \t]*(.*)", text)
    return m.group(1).strip() if m else ""


def parse_track(text: str) -> str:
    """The log's **Track:** value; the template's unedited 'SAA / SQL / Interview / DevOps'
    (or an empty field) counts as not filled in."""
    value = _field(text, "Track")
    return "" if not value or value.count("/") >= 2 else value


def parse_hours(text: str) -> float:
    """**Hours studied today:** as hours. Accepts '2', '1.5', '1,5', '1h30', '90 min'."""
    value = _field(text, "Hours studied today").lower()
    if m := re.search(r"(\d+)\s*h\s*(\d+)", value):
        return int(m.group(1)) + int(m.group(2)) / 60
    if m := re.search(r"(\d+(?:[.,]\d+)?)\s*(min|m\b)", value):
        return float(m.group(1).replace(",", ".")) / 60
    if m := re.search(r"\d+(?:[.,]\d+)?", value):
        return float(m.group(0).replace(",", "."))
    return 0.0


def parse_revisit(text: str) -> str:
    """Text under **What I need to revisit:** up to the next field or section."""
    m = re.search(r"\*\*What I need to revisit:\*\*(.*?)(?=\n\*\*|\n---|\n#|\Z)", text, re.S)
    return " ".join(m.group(1).split()) if m else ""


def week_summary(logs: dict, today: date) -> dict:
    """Study days, streak, hours per track and revisit items for the 7 days ending today."""
    week = {d: t for d, t in logs.items() if today - timedelta(days=6) <= d <= today}
    hours = {}
    for text in week.values():
        track = parse_track(text) or "Track not set"
        hours[track] = hours.get(track, 0.0) + parse_hours(text)
    # streak counts back from today, or from yesterday if today's log isn't written yet
    day = today if today in logs else today - timedelta(days=1)
    streak = 0
    while day in logs:
        streak += 1
        day -= timedelta(days=1)
    revisit = [(d, r) for d, t in sorted(week.items()) if (r := parse_revisit(t))]
    return {"days": len(week), "streak": streak, "hours": hours, "revisit": revisit}


# ─────────────────────────────────────────────
# MESSAGE BUILDERS (Telegram HTML)
# ─────────────────────────────────────────────
def build_morning(today: date) -> str:
    track = current_track(today)
    category, question, answer = question_for(track, today)
    days_to_exam = (EXAM_WINDOW[0] - today).days
    exam_line = (f"🗓️ {days_to_exam} days to the SAA exam window (11–17 Jan)\n"
                 if days_to_exam > 0 else "")
    return (
        f"☀️ <b>Good morning, Carlos</b>\n"
        f"Track: <b>{html.escape(TRACKS[track]['name'])}</b>\n"
        f"{exam_line}\n"
        f"🚆 On the train: Udemy SAA lectures (downloaded for offline).\n\n"
        f"🎯 <b>Question of the day</b> · {html.escape(category)}\n"
        f"❓ {html.escape(question)}\n\n"
        f"💡 <tg-spoiler>{html.escape(answer)}</tg-spoiler>\n"
        f"<i>Answer out loud first, then tap to reveal.</i>"
    )


def build_evening(today: date) -> str:
    return (
        f"🌙 <b>Daily log</b>\n"
        f"Before you stop: write today's log in <code>0 Daily Logs/{today.isoformat()}</code> "
        f"(template: Daily Log Template).\n"
        f"One Feynman explanation, three things learned, one struggle. 10 minutes."
    )


def _fmt_hours(h: float) -> str:
    return f"{h:.1f}".rstrip("0").rstrip(".") + " h"


def build_weekly(today: date, logs: dict = None) -> str:
    track = current_track(today)
    days_to_exam = (EXAM_WINDOW[0] - today).days
    lines = [
        "📊 <b>Weekly check-in</b>",
        f"Track: <b>{html.escape(TRACKS[track]['name'])}</b>",
    ]
    if days_to_exam > 0:
        lines.append(f"🗓️ {days_to_exam} days to the SAA exam window")
    if logs is not None:
        w = week_summary(logs, today)
        lines += ["", f"📅 Study days this week: <b>{w['days']}/7</b> · 🔥 streak: <b>{w['streak']}</b>"]
        if w["hours"]:
            per_track = ", ".join(f"{html.escape(t)} {_fmt_hours(h)}" for t, h in sorted(w["hours"].items()))
            lines.append(f"⏱️ {_fmt_hours(sum(w['hours'].values()))} ({per_track})")
        if w["revisit"]:
            lines += ["", "⚠️ <b>To revisit</b> (from your logs):"]
            lines += [f"• {d.strftime('%a')}: {html.escape(r)}" for d, r in w["revisit"]]
    lines += [
        "",
        "Take 30 minutes:",
        "✅ What do I feel confident about?",
        "⚠️ What still feels shaky?" + ("" if logs is not None else " (check the week's “What I need to revisit”)"),
        "🎯 What's my focus for next week?",
    ]
    return "\n".join(lines)


BUILDERS = {"morning": build_morning, "evening": build_evening, "weekly": build_weekly}


# ─────────────────────────────────────────────
# DISPATCH
# ─────────────────────────────────────────────
def message_type_for_run(event: str, schedule: str, chosen: str, now_utc: datetime):
    """Return the message type to send, or None when this scheduled run is the
    summer/winter twin that doesn't apply today."""
    if event != "schedule":
        return chosen
    msg, offset = SCHEDULES[schedule]
    return msg if offset == lisbon_offset(now_utc) else None


def send(text: str):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    payload = json.dumps({
        "chat_id": os.environ["TELEGRAM_CHAT_ID"],
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload, headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read())
    if not result.get("ok"):
        raise RuntimeError(f"Telegram error: {result}")


def main():
    now = datetime.now(timezone.utc)
    msg = message_type_for_run(
        os.environ.get("GITHUB_EVENT_NAME", "workflow_dispatch"),
        os.environ.get("SCHEDULE", ""),
        os.environ.get("MESSAGE_TYPE", "morning"),
        now,
    )
    if msg is None:
        print("[SKIP] Not this run's time of year (summer/winter twin).")
        return
    if msg not in BUILDERS:
        raise ValueError(f"Unknown message type: {msg}")
    today = (now + timedelta(hours=lisbon_offset(now))).date()
    if msg == "morning":
        text = build_morning(today)
    else:
        logs = fetch_logs(today - timedelta(days=30))
        if msg == "evening" and logs is not None and today in logs:
            print(f"[SKIP] Today's log ({today}) is already written.")
            return
        text = build_evening(today) if msg == "evening" else build_weekly(today, logs)
    send(text)
    print(f"[OK] Sent {msg} for {today}")


if __name__ == "__main__":
    main()
