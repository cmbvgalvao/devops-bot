"""
Learning-path Telegram bot
Carlos Galvão — commute reminder + question of the day, evening daily-log nudge, Sunday check-in

v3 (2026-11-11): follows the Learning vault's tracks by date (SQL → AWS SAA → DevOps)
    instead of the DevOps course that never started. Supabase and the dashboard are gone;
    the vault's daily logs become the progress source in sprint 2 (see BACKLOG.md).
"""

import html
import json
import os
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

QUESTIONS_DIR = Path(__file__).parent / "questions"

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


def build_weekly(today: date) -> str:
    track = current_track(today)
    days_to_exam = (EXAM_WINDOW[0] - today).days
    lines = [
        "📊 <b>Weekly check-in</b>",
        f"Track: <b>{html.escape(TRACKS[track]['name'])}</b>",
    ]
    if days_to_exam > 0:
        lines.append(f"🗓️ {days_to_exam} days to the SAA exam window")
    lines += [
        "",
        "Take 30 minutes:",
        "✅ What do I feel confident about?",
        "⚠️ What still feels shaky? (check the week's “What I need to revisit”)",
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
    send(BUILDERS[msg](today))
    print(f"[OK] Sent {msg} for {today}")


if __name__ == "__main__":
    main()
