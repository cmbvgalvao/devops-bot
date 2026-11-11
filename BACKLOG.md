# Backlog: Learning-path bot

The bot was built in May 2026 for a 4-week DevOps course that never started. From November 2026 it follows the learning path in the Learning vault (`devops-vault`): SQL refresh (11–24 Nov 2026), AWS SAA (exam 11–17 Jan 2027), DevOps Fast-Track (from 18 Jan 2027).

## Sprint 1 (2026-11-11): new schedule and questions — done when the manual test messages arrive
- [x] Follow the current track by date (SQL → SAA → DevOps); question banks in `questions/`.
- [x] Messages at 06:30 (commute: reminder + question of the day) and 20:00 (daily log nudge), Sunday 18:00 check-in; Lisbon time all year (DST handled in code).
- [x] Fix: a manual run sent all three messages; now it sends only the chosen one.
- [x] Fix: the answer spoiler never hid (legacy Markdown); use Telegram HTML `<tg-spoiler>`.
- [x] Drop Supabase and the dashboard (the vault becomes the source of progress in sprint 2).
- [x] Unit tests (`python -m unittest`) and a CI workflow that runs them on every push.

## Sprint 2: progress from the vault
- [ ] Carlos creates a fine-grained token with read-only access to `devops-vault` → repo secret `VAULT_TOKEN`.
- [ ] Read `0 Daily Logs/YYYY-MM-DD.md`: study days this week, streak, hours per track (from the template's **Track** and **Hours studied today** fields).
- [ ] Sunday check-in shows real numbers and the "What I need to revisit" items from the week's logs.
- [ ] Evening nudge only if today's log doesn't exist yet.

## Later
- [ ] GitHub can delay scheduled runs by hours on quiet repos (seen: a 07:00 run arriving at 15:27). If it's a problem, trigger `workflow_dispatch` from an external scheduler.
- [ ] Questions from Carlos's own flashcards in `2 AWS SAA/Flashcards`.
- [ ] Put the bot in a Docker container (DevOps track practice).
