import json
import os
import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import bot  # noqa: E402


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


class LisbonOffset(unittest.TestCase):
    def test_winter_and_summer(self):
        self.assertEqual(bot.lisbon_offset(utc(2026, 11, 11, 12)), 0)
        self.assertEqual(bot.lisbon_offset(utc(2026, 7, 1, 12)), 1)

    def test_switch_moments(self):
        # 2027: summer time starts Sun 28 Mar 01:00 UTC; 2026: it ended Sun 25 Oct 01:00 UTC
        self.assertEqual(bot.lisbon_offset(utc(2027, 3, 28, 0, 59)), 0)
        self.assertEqual(bot.lisbon_offset(utc(2027, 3, 28, 1, 0)), 1)
        self.assertEqual(bot.lisbon_offset(utc(2026, 10, 25, 0, 59)), 1)
        self.assertEqual(bot.lisbon_offset(utc(2026, 10, 25, 1, 0)), 0)


class Tracks(unittest.TestCase):
    def test_timeline(self):
        self.assertEqual(bot.current_track(date(2026, 11, 24)), "sql")
        self.assertEqual(bot.current_track(date(2026, 11, 25)), "saa")
        self.assertEqual(bot.current_track(date(2027, 1, 17)), "saa")
        self.assertEqual(bot.current_track(date(2027, 1, 18)), "devops")

    def test_banks_are_valid(self):
        for track in bot.TRACKS:
            bank = bot.load_questions(track)
            self.assertGreater(len(bank), 10, track)
            for item in bank:
                self.assertEqual(len(item), 3, item)
                self.assertTrue(all(isinstance(x, str) and x.strip() for x in item), item)

    def test_question_changes_daily(self):
        a = bot.question_for("saa", date(2026, 12, 1))
        b = bot.question_for("saa", date(2026, 12, 2))
        self.assertNotEqual(a, b)


class Dispatch(unittest.TestCase):
    def test_manual_run_sends_only_the_chosen_message(self):
        self.assertEqual(bot.message_type_for_run("workflow_dispatch", "", "evening", utc(2026, 11, 11, 12)), "evening")

    def test_scheduled_twins(self):
        winter = utc(2026, 12, 1, 6, 30)
        self.assertEqual(bot.message_type_for_run("schedule", "30 6 * * *", "", winter), "morning")
        self.assertIsNone(bot.message_type_for_run("schedule", "30 5 * * *", "", winter))
        summer = utc(2027, 6, 1, 5, 30)
        self.assertEqual(bot.message_type_for_run("schedule", "30 5 * * *", "", summer), "morning")
        self.assertIsNone(bot.message_type_for_run("schedule", "30 6 * * *", "", summer))

    def test_every_cron_in_workflow_is_known(self):
        wf = (Path(__file__).resolve().parent.parent / ".github/workflows/telegram-bot.yml").read_text(encoding="utf-8")
        crons = [line.split('"')[1] for line in wf.splitlines() if "cron:" in line]
        self.assertEqual(sorted(crons), sorted(bot.SCHEDULES))


class Messages(unittest.TestCase):
    def test_answer_is_hidden_and_escaped(self):
        text = bot.build_morning(date(2026, 11, 12))
        self.assertIn("<tg-spoiler>", text)
        # SQL answers contain '<' and '>' — they must be escaped for Telegram HTML
        for _, _, answer in bot.load_questions("sql"):
            if "<" in answer:
                self.assertNotIn("<", bot.html.escape(answer))

    def test_exam_countdown_disappears_after_exam(self):
        self.assertIn("days to the SAA exam", bot.build_morning(date(2026, 12, 1)))
        self.assertNotIn("days to the SAA exam", bot.build_morning(date(2027, 1, 20)))


LOG = """# Daily Log — {d}

**Track:** {track}
**Course day:**
**Hours studied today:** {hours}

---

## Feynman Test

**Concept:** joins

**What I need to revisit:**
{revisit}

---
"""


def log(d, track="SQL", hours="1.5", revisit=""):
    return LOG.format(d=d, track=track, hours=hours, revisit=revisit)


class VaultLogs(unittest.TestCase):
    def test_track(self):
        self.assertEqual(bot.parse_track(log("x", track="SAA")), "SAA")
        self.assertEqual(bot.parse_track(log("x", track="SAA / SQL / Interview / DevOps")), "")
        self.assertEqual(bot.parse_track(log("x", track="")), "")

    def test_hours_formats(self):
        for text, expected in [("2", 2), ("1.5", 1.5), ("1,5", 1.5), ("1h30", 1.5),
                               ("90 min", 1.5), ("45m", 0.75), ("2h", 2), ("", 0)]:
            self.assertAlmostEqual(bot.parse_hours(log("x", hours=text)), expected, msg=text)

    def test_revisit(self):
        self.assertEqual(bot.parse_revisit(log("x", revisit="LEFT vs\nRIGHT joins")), "LEFT vs RIGHT joins")
        self.assertEqual(bot.parse_revisit(log("x", revisit="")), "")

    def test_week_summary(self):
        today = date(2026, 11, 15)  # Sunday
        logs = {
            date(2026, 11, 8): log("8", hours="3"),          # previous week: not counted
            date(2026, 11, 12): log("12", hours="1"),
            date(2026, 11, 13): log("13", track="SAA", hours="2", revisit="VPC peering"),
            date(2026, 11, 14): log("14", hours="1h30"),
        }
        w = bot.week_summary(logs, today)
        self.assertEqual(w["days"], 3)
        self.assertEqual(w["streak"], 3)  # today not written yet, counted from yesterday
        self.assertEqual(w["hours"], {"SQL": 2.5, "SAA": 2.0})
        self.assertEqual(w["revisit"], [(date(2026, 11, 13), "VPC peering")])

    def test_weekly_message_with_and_without_vault(self):
        today = date(2026, 11, 15)
        text = bot.build_weekly(today, {date(2026, 11, 14): log("14", revisit="a < b")})
        self.assertIn("1/7", text)
        self.assertIn("a &lt; b", text)
        self.assertNotIn("Study days", bot.build_weekly(today))

    def test_no_token_means_no_vault(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(bot.fetch_logs(date(2026, 11, 1)))


if __name__ == "__main__":
    unittest.main()
