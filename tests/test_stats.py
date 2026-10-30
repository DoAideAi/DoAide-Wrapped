"""The year's numbers, time patterns, persona and roast, from the fake home and from synthetic stats."""
from __future__ import annotations

import shutil
import tempfile
import unittest
from datetime import date, timezone

from agent_wrapped import persona, stats
from agent_wrapped.fmt import compact
from agent_wrapped.model import parse_ts, year_window
from agent_wrapped.names import pretty_model, tool_category
from agent_wrapped.sources import SOURCES, collect, locate_all

from fakehome import EXPECTED, build_home

Y2026 = year_window(2026, timezone.utc)


def wrapped(home, show_projects=False):
    found = locate_all(list(SOURCES), home, {})
    return stats.build(collect(found, Y2026), Y2026, tz=timezone.utc, year=2026, show_projects=show_projects)


class YearTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.home = build_home(cls.tmp)
        cls.stats = wrapped(cls.home)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_totals(self):
        t = self.stats["totals"]
        self.assertEqual(
            (t["sessions"], t["prompts"], t["tokens"]["total"], t["cost_usd"], t["lines_added"], t["lines_removed"],
             t["tool_calls"], t["assistant_messages"]),
            (EXPECTED["sessions"], EXPECTED["prompts"], EXPECTED["tokens"], EXPECTED["cost_usd"],
             EXPECTED["lines_added"], EXPECTED["lines_removed"], EXPECTED["tool_calls"], EXPECTED["assistant_messages"]),
        )
        self.assertEqual((t["interrupts"], t["compactions"], t["queued"], t["absolutely_right"]), (2, 2, 1, 1))
        self.assertEqual((t["edits"], t["shell"]), (2, 3))

    def test_time_patterns(self):
        tm = self.stats["time"]
        self.assertEqual(tm["active_days"], 8)
        self.assertEqual(tm["streak"], {"days": 8, "start": "2026-03-14", "end": "2026-03-21"})
        self.assertEqual(tm["busiest_day"], {"date": "2026-03-14", "prompts": 2})  # earliest of the tied days
        self.assertEqual(tm["busiest_hour"], 9)
        self.assertAlmostEqual(tm["night_share"], 3 / 11)
        self.assertAlmostEqual(tm["weekend_share"], 5 / 11)  # 14, 15 and 21 March 2026 fall on a weekend
        self.assertLessEqual(tm["hours_with_agents"], tm["agent_hours"])

    def test_agents_models_and_tools(self):
        self.assertEqual([a["name"] for a in self.stats["agents"]], ["Claude Code", "Codex", "Hermes", "Cursor"])
        models = [(m["name"], m["count"]) for m in self.stats["models"]]
        self.assertEqual(models, [("Claude Fable 5.1", 4), ("Claude Opus 5.5", 4), ("Claude Opus 4.5 High Thinking", 2),
                                  ("GPT-6.1 Sol", 2), ("Claude Haiku 4.5", 1)])
        self.assertEqual([(c["name"], c["count"]) for c in self.stats["tools"]],
                         [("Shell", 3), ("Edit", 2), ("Read", 1), ("Web", 1)])

    def test_persona_and_roast(self):
        self.assertEqual(self.stats["persona"]["name"], "The Polyglot")
        self.assertEqual(self.stats["persona"]["why"], "4 different agents")
        self.assertEqual(self.stats["roast"], "11 prompts in, 42.5K tokens through. Just getting started.")

    def test_projects_only_when_asked(self):
        self.assertNotIn("projects", self.stats)
        projects = wrapped(self.home, show_projects=True)["projects"]
        self.assertEqual(projects[0], {"name": "secret-client", "sessions": 4, "prompts": 7})


def synthetic(**changes):
    """A stats dict with neutral numbers, for exercising the persona and roast rules."""
    base = {
        "agents": [{"name": "Claude Code"}],
        "totals": {"prompts": 400, "sessions": 50, "interrupts": 0, "queued": 0, "tool_calls": 2000, "shell": 600,
                   "absolutely_right": 0, "compactions": 0, "tokens": {"total": 5_000_000, "output": 100_000}},
        "time": {"night_share": 0.1, "early_share": 0.1, "weekend_share": 0.1, "streak": {"days": 5},
                 "busiest_day": {"date": "2026-03-14", "prompts": 30}},
    }
    for path, value in changes.items():
        section, key = path.split("__")
        base[section][key] = value
    return base


class PersonaTest(unittest.TestCase):
    def test_habits_beat_raw_volume(self):
        night = synthetic(time__night_share=0.5)
        night["totals"]["tokens"]["total"] = 50e9
        self.assertEqual(persona.pick_persona(night)["name"], "The Night Owl")
        self.assertEqual(persona.pick_persona(night)["why"], "50% of prompts after 10pm")

    def test_ratio_badges_need_enough_prompts(self):
        few = synthetic(time__night_share=0.9, totals__prompts=10)
        self.assertEqual(persona.pick_persona(few)["name"], "The Builder")

    def test_token_tycoon_only_when_nothing_else_fits(self):
        heavy = synthetic()
        heavy["totals"]["tokens"]["total"] = 3e9
        self.assertEqual(persona.pick_persona(heavy)["name"], "The Token Tycoon")

    def test_roast_picks_the_most_remarkable_line(self):
        line = persona.pick_roast(synthetic(totals__absolutely_right=400, totals__compactions=12))
        self.assertEqual(line, 'Your agent told you "You\'re absolutely right" 400 times. You were not always right.')

    def test_roast_scales_output_into_books(self):
        stats_ = synthetic()
        stats_["totals"]["tokens"]["output"] = 76_000_000
        self.assertEqual(persona.pick_roast(stats_),
                         "Your agents wrote 76M tokens. That's about 100 copies of War and Peace.")


class HelpersTest(unittest.TestCase):
    def test_parse_ts(self):
        utc = parse_ts("2026-03-14T23:10:00Z")
        self.assertEqual(utc, parse_ts("2026-03-14T23:10:00.000Z"))
        self.assertEqual(utc, parse_ts("2026-03-15T04:40:00+05:30"))
        self.assertEqual(utc, parse_ts("2026-03-15T04:40:00+0530"))
        self.assertAlmostEqual(parse_ts("2026-03-14T23:10:00.123456789Z"), utc + 0.123456, places=5)
        self.assertEqual(parse_ts(utc * 1000), utc)  # epoch milliseconds
        self.assertEqual(parse_ts(utc), utc)
        for junk in (None, True, "yesterday", "", {}):
            self.assertIsNone(parse_ts(junk))

    def test_pretty_model(self):
        cases = {
            "claude-opus-5-5": "Claude Opus 5.5",
            "claude-opus-5": "Claude Opus 5",
            "claude-fable-5-1": "Claude Fable 5.1",
            "claude-haiku-4-5-20251001": "Claude Haiku 4.5",
            "claude-4.5-opus-high-thinking": "Claude Opus 4.5 High Thinking",
            "anthropic/claude-sonnet-4-6": "Claude Sonnet 4.6",
            "gpt-6.1-sol": "GPT-6.1 Sol",
            "gpt-5.1-codex-mini": "GPT-5.1 Codex Mini",
            "gpt-4o": "GPT-4o",
            "composer-1": "Cursor Composer 1",
            "default": "Cursor Auto",
            "o3": "o3",
            "": "Unknown model",
        }
        for raw, pretty in cases.items():
            self.assertEqual(pretty_model(raw), pretty, raw)

    def test_tool_categories(self):
        self.assertEqual([tool_category(n) for n in ("Bash", "exec_command", "terminal", "apply_patch", "Edit",
                                                     "mcp__browser__click", "Agent", "frobnicate")],
                         ["Shell", "Shell", "Shell", "Edit", "Edit", "MCP", "Subagents", "Other"])

    def test_compact(self):
        self.assertEqual([compact(n) for n in (950, 12_340, 999_999, 192_000_000, 2_040_000_000, 1e9, 62.6e9)],
                         ["950", "12.3K", "1M", "192M", "2.04B", "1B", "62.6B"])

    def test_streak_and_active_time(self):
        days = [date(2026, 1, d) for d in (1, 2, 3, 5, 6)] + [date(2026, 1, 31), date(2026, 2, 1)]
        self.assertEqual(stats.longest_streak(days), (3, date(2026, 1, 1), date(2026, 1, 3)))
        self.assertEqual(stats.active_seconds([0, 60, 120, 5000, 5060]), 180)  # the 81-minute gap ends a stretch


if __name__ == "__main__":
    unittest.main()
