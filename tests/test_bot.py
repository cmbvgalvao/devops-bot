import json
import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
