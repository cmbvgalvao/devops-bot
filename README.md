# learning-path-bot

A Telegram bot that keeps a personal learning path on track. GitHub Actions runs it on a schedule; no server.

| Lisbon time | Message |
|---|---|
| 06:30 daily | Reminder for the commute + question of the day (answer hidden behind a spoiler) |
| 20:00 daily | Nudge to write the daily log in the Learning vault (skipped if today's log is already there) |
| 18:00 Sunday | Weekly check-in: study days, streak, hours per track and the week's "What I need to revisit" items, read from the daily logs |

The question follows the current track by date: SQL refresh (to 24 Nov 2026), AWS SAA (to the exam in mid-January 2027), then DevOps. Question banks are in `questions/`.

**How it works:** each message has two cron entries (summer and winter time); `bot.py` works out Lisbon's UTC offset and skips the one that doesn't apply, so times stay right all year. Telegram credentials are repository secrets (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`). The daily logs come from the private vault repo through the GitHub API, with a fine-grained token that can only read that repo (`VAULT_TOKEN`). If the vault can't be read, the bot sends the plain messages instead.

**Test it:** Actions → Telegram Daily Bot → Run workflow → choose a message. Unit tests: `python -m unittest discover -s tests` (also run by CI on every push).

Plans: [BACKLOG.md](BACKLOG.md).

License: [MIT](LICENSE).
