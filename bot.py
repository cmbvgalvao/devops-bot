"""
DevOps Fast-Track Telegram Bot
Carlos Galvão — Daily reminders, progress check-ins, and interview questions

v2: Reads real progress from Supabase instead of a manual COURSE_DAY variable.
    COURSE_DAY is now calculated from the completed days in the dashboard.
"""

import os
import json
import random
import urllib.request
from datetime import datetime, timezone

# ─────────────────────────────────────────────
# CONFIG  (all values come from GitHub Secrets)
# ─────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID        = os.environ["TELEGRAM_CHAT_ID"]
SUPABASE_URL   = os.environ["SUPABASE_URL"]        # new
SUPABASE_KEY   = os.environ["SUPABASE_KEY"]        # new
MESSAGE_TYPE   = os.environ.get("MESSAGE_TYPE", "daily_reminder")

# All 28 day IDs in order — must match the dashboard data exactly
ALL_DAYS = [
    "d1","d2",                          # Week 1 — Git
    "d3","d4","d5","d6","d7",           # Week 1 — Docker
    "d8","d9","d10","d11","d12",        # Week 2 — Kubernetes
    "d13","d14",                        # Week 2 — CI/CD
    "d15","d16","d17","d18","d19",      # Week 3 — Terraform
    "d20","d21",                        # Week 3 — Monitoring
    "d22","d23","d24","d25","d26",      # Week 4 — Capstone
    "d27","d28",                        # Week 4 — Interviews
]


# ─────────────────────────────────────────────
# COURSE DATA
# ─────────────────────────────────────────────
WEEKS = [
    {"id": 1, "title": "Week 1 — Git + Docker",          "days": ["d1","d2","d3","d4","d5","d6","d7"]},
    {"id": 2, "title": "Week 2 — Kubernetes + CI/CD",    "days": ["d8","d9","d10","d11","d12","d13","d14"]},
    {"id": 3, "title": "Week 3 — Terraform + Monitoring", "days": ["d15","d16","d17","d18","d19","d20","d21"]},
    {"id": 4, "title": "Week 4 — Capstone + Interviews",  "days": ["d22","d23","d24","d25","d26","d27","d28"]},
]

INTERVIEW_QUESTIONS = [
    # Docker
    ("🐳 Docker", "What is the difference between a Docker *image* and a *container*?",
     "An image is a read-only blueprint. A container is a running instance of that image with its own writable layer on top."),
    ("🐳 Docker", "What does each Dockerfile instruction do: `FROM`, `RUN`, `COPY`, `CMD`, `ENTRYPOINT`?",
     "FROM sets the base image. RUN executes commands at build time. COPY adds files. CMD is the default command. ENTRYPOINT sets the executable that always runs."),
    ("🐳 Docker", "How do Docker volumes differ from bind mounts?",
     "Volumes are managed by Docker and stored in Docker's storage area. Bind mounts link to a specific path on the host. Use volumes for production persistence."),
    ("🐳 Docker", "What is a multi-stage build and why would you use one?",
     "A Dockerfile with multiple FROM statements. You build in a full image, then copy only the artifacts to a slim final image. Result: dramatically smaller production image."),
    ("🐳 Docker", "Explain bridge vs host network modes.",
     "Bridge creates an isolated Docker network — containers talk via DNS. Host shares the host machine's network stack directly, no isolation."),
    # Kubernetes
    ("⎈ Kubernetes", "What is a Pod and why is it the smallest deployable unit?",
     "A Pod wraps one or more containers that share the same network and storage. Kubernetes schedules Pods, not individual containers."),
    ("⎈ Kubernetes", "What is the difference between a Deployment, a StatefulSet, and a DaemonSet?",
     "Deployment: stateless apps, rolling updates. StatefulSet: stateful apps with stable identity. DaemonSet: one Pod per node (logging, monitoring)."),
    ("⎈ Kubernetes", "Name the four Service types and when to use each.",
     "ClusterIP: internal only. NodePort: exposes via node port. LoadBalancer: cloud LB. ExternalName: DNS alias."),
    ("⎈ Kubernetes", "How does a rolling update work? How would you roll back?",
     "Kubernetes gradually replaces old Pods. Roll back with: kubectl rollout undo deployment/<name>"),
    ("⎈ Kubernetes", "How would you debug a Pod stuck in CrashLoopBackOff?",
     "kubectl describe pod → events. kubectl logs → app output. Common causes: wrong CMD, missing env var, failing health check."),
    # Terraform
    ("🏗️ Terraform", "What is Terraform state and why does it matter?",
     "State maps your config to real cloud resources. Without it, Terraform can't know what already exists or plan changes."),
    ("🏗️ Terraform", "What happens if you lose your Terraform state file?",
     "Terraform loses track of everything it created. You'd have to import manually. This is why remote state with locking is critical."),
    ("🏗️ Terraform", "Explain the plan → apply → destroy lifecycle.",
     "plan previews changes. apply executes them. destroy removes all managed resources. Always plan before apply."),
    ("🏗️ Terraform", "What is a Terraform module and when do you create one?",
     "A reusable config package. Create one when you repeat the same infra pattern across environments."),
    ("🏗️ Terraform", "What is state locking and how do you implement it?",
     "Prevents concurrent apply runs. Use DynamoDB alongside your S3 remote backend."),
    # CI/CD
    ("🔄 CI/CD", "What are the typical stages of a CI/CD pipeline?",
     "Source → Lint → Unit tests → Build → Security scan → Push artifact → Deploy staging → Deploy production."),
    ("🔄 CI/CD", "How do you store and use secrets in GitHub Actions?",
     "Settings → Secrets. Reference as ${{ secrets.MY_SECRET }}. They are masked in all logs."),
    ("🔄 CI/CD", "What is the difference between Continuous Integration and Continuous Deployment?",
     "CI automatically builds and tests on every commit. CD automatically deploys after tests pass. CI is a prerequisite for CD."),
    ("🔄 CI/CD", "What are the different trigger types for a GitHub Actions workflow?",
     "push, pull_request, schedule (cron), workflow_dispatch (manual), repository_dispatch (API), release (on tag)."),
    # Scenarios
    ("🧩 Scenario", "Users are reporting 500 errors right after a new deployment. Walk through your troubleshooting.",
     "1. Check dashboards. 2. kubectl logs on new pods. 3. Compare new vs previous spec. 4. Roll back if critical. 5. Root cause after service is restored."),
    ("🧩 Scenario", "Your application is experiencing a sudden traffic spike. How do you scale it?",
     "Short term: HPA kicks in. Medium term: Cluster Autoscaler adds nodes. Long term: review resource limits and autoscaling policies."),
    ("🧩 Scenario", "Your EC2 instance was accidentally terminated. How does your IaC setup help you recover?",
     "terraform plan shows the missing resource. terraform apply recreates it in minutes. This is the core value of IaC."),
]

MOTIVATIONAL = [
    "You're not starting from zero, Carlos. AWS certified, Linux daily, Python scripting — you're already halfway there. 💪",
    "Every senior DevOps engineer was once staring at their first Dockerfile. Keep going. 🐳",
    "The gap between where you are and Junior DevOps is 4 weeks of consistent work. That's it. 🎯",
    "Your OpenVPN and multi-cloud experience is genuinely rare. Terraform and K8s are just the next layer. 🏗️",
    "Struggling with something today means you'll remember it forever. The confusion is the learning. 🧠",
    "One push, one pipeline, one deployment. Stack the wins. 📈",
    "ISO 27001 + AWS cert + scripting experience. Hiring managers will notice. Keep building. ⚡",
    "The capstone project you're building is more impressive than most candidates' 2 years of experience. 🚀",
]


# ─────────────────────────────────────────────
# SUPABASE — fetch real progress
# ─────────────────────────────────────────────
def fetch_progress() -> dict:
    """
    Fetches the completed days object from Supabase.
    Returns a dict like {"d1": True, "d3": True, ...}
    Falls back to an empty dict on any error so the bot never crashes.
    """
    url = f"{SUPABASE_URL}/rest/v1/course_progress?id=eq.default&select=completed"
    req = urllib.request.Request(
        url,
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            rows = json.loads(resp.read())
            if rows and isinstance(rows, list):
                return rows[0].get("completed") or {}
    except Exception as e:
        print(f"[WARN] Supabase fetch failed: {e} — falling back to empty progress")
    return {}


def calculate_progress(completed: dict) -> dict:
    """
    Derives all progress metrics from the completed days dict.
    Returns:
        done_count     — number of days ticked
        total_count    — 28
        pct            — integer percentage
        current_day    — the next incomplete day number (1–28)
        current_week   — which week that day falls in (1–4)
        week_title     — e.g. "Week 2 — Kubernetes + CI/CD"
        week_done      — days completed in the current week
        week_total     — days in the current week (always 7)
    """
    done_count = sum(1 for d in ALL_DAYS if completed.get(d))
    total_count = len(ALL_DAYS)
    pct = round(done_count / total_count * 100)

    # Current day = first incomplete day index (1-based), capped at 28
    current_day = done_count + 1
    current_day = min(current_day, total_count)

    # Which week does the current day fall in?
    week_idx = (current_day - 1) // 7          # 0-based
    week_idx = min(week_idx, len(WEEKS) - 1)
    week = WEEKS[week_idx]

    week_done  = sum(1 for d in week["days"] if completed.get(d))
    week_total = len(week["days"])

    return {
        "done_count":   done_count,
        "total_count":  total_count,
        "pct":          pct,
        "current_day":  current_day,
        "current_week": week["id"],
        "week_title":   week["title"],
        "week_done":    week_done,
        "week_total":   week_total,
    }


# ─────────────────────────────────────────────
# TELEGRAM SENDER
# ─────────────────────────────────────────────
def send(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }).encode()
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
        if not result.get("ok"):
            raise RuntimeError(f"Telegram error: {result}")
    print(f"[OK] Message sent — type: {MESSAGE_TYPE}")


# ─────────────────────────────────────────────
# MESSAGE BUILDERS
# ─────────────────────────────────────────────
def build_daily_reminder(p: dict) -> str:
    return (
        f"☀️ *Good morning, Carlos!*\n\n"
        f"Today is *Day {p['current_day']}* of your DevOps fast-track.\n"
        f"📅 You're in *{p['week_title']}*\n"
        f"📊 Progress: {p['done_count']}/{p['total_count']} days complete ({p['pct']}%)\n\n"
        f"Your target for today:\n"
        f"• 15 min — review yesterday's concepts\n"
        f"• 60 min — study new material\n"
        f"• 90 min — hands-on lab\n"
        f"• 15 min — write down 3 things you learned\n\n"
        f"_{random.choice(MOTIVATIONAL)}_"
    )


def build_interview_question(p: dict) -> str:
    # Rotate through questions based on day of year so each day is different
    day_index = datetime.now(timezone.utc).timetuple().tm_yday % len(INTERVIEW_QUESTIONS)
    category, question, answer = INTERVIEW_QUESTIONS[day_index]

    return (
        f"🎯 *Interview Question of the Day*\n\n"
        f"*Category:* {category}\n\n"
        f"❓ {question}\n\n"
        f"||💡 *Answer:* {answer}||\n\n"
        f"_Tap the spoiler to reveal. Try answering out loud first — 2 minutes max._\n\n"
        f"_You are on Day {p['current_day']} — {p['pct']}% through the course._"
    )


def build_progress_checkin(p: dict) -> str:
    bars_filled = round(p["pct"] / 10)
    overall_bar = "█" * bars_filled + "░" * (10 - bars_filled)

    week_pct = round(p["week_done"] / p["week_total"] * 100) if p["week_total"] else 0
    week_bars = round(week_pct / 10)
    week_bar  = "█" * week_bars + "░" * (10 - week_bars)

    # Personalised nudge based on real completion rate
    if p["pct"] == 0:
        nudge = "_No days marked complete yet. Open the dashboard and tick off your first day._"
    elif p["pct"] < 25:
        nudge = "_Strong start. Momentum builds from here — consistency beats intensity._"
    elif p["pct"] < 50:
        nudge = "_You're building the foundation. Docker and Git are the hardest mental shift. It gets cleaner from here._"
    elif p["pct"] < 75:
        nudge = "_Past the halfway point. Kubernetes and Terraform are clicking. Keep the lab work hands-on._"
    elif p["pct"] < 100:
        nudge = "_Final stretch. The capstone is where it all comes together. Make it public._"
    else:
        nudge = "_Course complete. The work now is to keep the projects alive and start applying. 🚀_"

    return (
        f"📊 *Weekly Progress Check-in*\n\n"
        f"*Overall:* `{overall_bar}` {p['pct']}%\n"
        f"*This week:* `{week_bar}` {week_pct}% — {p['week_title']}\n"
        f"*Days done:* {p['done_count']} of {p['total_count']}\n\n"
        f"Take 30 minutes now to ask yourself:\n"
        f"✅ What do I feel confident about?\n"
        f"⚠️ What still feels shaky?\n"
        f"🎯 What's my focus for next week?\n\n"
        f"{nudge}"
    )


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    completed = fetch_progress()
    p = calculate_progress(completed)
    print(f"[INFO] Progress: {p['done_count']}/{p['total_count']} days, day {p['current_day']}, {p['pct']}%")

    dispatch = {
        "daily_reminder":     build_daily_reminder,
        "interview_question": build_interview_question,
        "progress_checkin":   build_progress_checkin,
    }
    builder = dispatch.get(MESSAGE_TYPE)
    if not builder:
        raise ValueError(f"Unknown MESSAGE_TYPE: {MESSAGE_TYPE}")

    send(builder(p))


if __name__ == "__main__":
    main()
