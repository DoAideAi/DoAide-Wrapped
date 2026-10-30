"""Each parser against the fake home: the real-log quirks must not inflate or drop any count."""
from __future__ import annotations

import shutil
import sqlite3
import tempfile
import unittest
from collections import Counter
from datetime import timezone
from pathlib import Path

from agent_wrapped.model import year_window
from agent_wrapped.scan import map_files
from agent_wrapped.sources import claude_code, codex, cursor, hermes

from fakehome import build_home, epoch

Y2026 = year_window(2026, timezone.utc)
Y2025 = year_window(2025, timezone.utc)


class FakeHomeCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.home = build_home(cls.tmp)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def sessions(self, module, window=Y2026):
        return {s.id: s for s in module.parse(module.locate(self.home, {}), window)}


class ClaudeCodeTest(FakeHomeCase):
    def test_a_reply_split_over_several_lines_counts_once(self):
        a = self.sessions(claude_code)["sess-a"]
        self.assertEqual(a.assistant_messages, 4)  # msg_1, msg_2, msg_3, msg_side; <synthetic> and 2025 excluded
        self.assertEqual(
            {k: a.tokens[k] for k in ("input", "output", "cache_read", "cache_write", "total")},
            {"input": 311, "output": 142, "cache_read": 11000, "cache_write": 1000, "total": 12453},
        )

    def test_only_typed_prompts_count(self):
        a = self.sessions(claude_code)["sess-a"]
        # typed, typed while the agent worked, typed: not tool results, interrupts, slash commands,
        # meta lines, sidechain prompts, task notifications, peer messages or desktop enqueue lines
        self.assertEqual(a.prompts, [epoch("03-14 23:10:00"), epoch("03-14 23:21:30"), epoch("03-15 00:30:00")])
        self.assertEqual((a.interrupts, a.queued), (1, 1))

    def test_tools_models_and_quirks(self):
        a = self.sessions(claude_code)["sess-a"]
        self.assertEqual(a.tools, Counter({"Bash": 1, "Edit": 1, "Read": 1}))
        self.assertEqual(a.models, Counter({"claude-opus-5-5": 3, "claude-haiku-4-5-20251001": 1}))
        self.assertEqual((a.absolutely_right, a.compactions, a.api_errors), (1, 1, 1))
        self.assertEqual(a.project, "secret-client")

    def test_cost_comes_from_the_last_cost_state_or_legacy_cost_lines(self):
        sessions = self.sessions(claude_code)
        a = sessions["sess-a"]
        self.assertEqual((a.cost_usd, a.lines_added, a.lines_removed), (1.25, 120, 30))
        self.assertAlmostEqual(sessions["sess-b"].cost_usd, 0.15)

    def test_the_window_keeps_other_years_out(self):
        old = self.sessions(claude_code, Y2025)
        self.assertEqual(set(old), {"sess-a"})
        self.assertEqual(old["sess-a"].prompts, [epoch("2025-12-31 10:00:00")])
        self.assertEqual(old["sess-a"].tokens["total"], 1998)

    def test_parallel_scan_matches_serial_scan(self):
        paths = claude_code.locate(self.home, {})
        serial = map_files(claude_code.parse_file, paths, Y2026, jobs=1)
        parallel = map_files(claude_code.parse_file, paths, Y2026, jobs=2, min_parallel=1)
        self.assertEqual(sorted(serial, key=lambda s: s.id), sorted(parallel, key=lambda s: s.id))

    def test_retention_defaults_to_thirty_days(self):
        self.assertEqual(claude_code.retention(self.home, {}), (30, self.home / ".claude" / "settings.json"))
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ".claude" / "projects").mkdir(parents=True)
            (home / ".claude" / "settings.json").write_text('{"cleanupPeriodDays": 3650}', encoding="utf-8")
            self.assertEqual(claude_code.retention(home, {}), (3650, home / ".claude" / "settings.json"))

    def test_claude_config_dir_is_honoured(self):
        found = claude_code.locate(Path("/nonexistent"), {"CLAUDE_CONFIG_DIR": str(self.home / ".claude")})
        self.assertEqual(len(found), 2)


class CodexTest(FakeHomeCase):
    def test_new_rollout(self):
        s = self.sessions(codex)["codex-1"]
        # task_started and injected <environment_context> are not prompts
        self.assertEqual(s.prompts, [epoch("03-18 10:00:02"), epoch("03-18 10:05:00")])
        self.assertEqual(s.models, Counter({"gpt-6.1-sol": 1, "gpt-6-luna": 1}))
        self.assertEqual(s.tools, Counter({"exec_command": 1, "apply_patch": 1}))
        self.assertEqual((s.interrupts, s.compactions), (1, 1))
        self.assertEqual(
            {k: s.tokens[k] for k in ("input", "cache_read", "output", "reasoning", "total")},
            {"input": 700, "cache_read": 800, "output": 150, "reasoning": 40, "total": 1650},
        )

    def test_old_rollout_uses_the_last_cumulative_total(self):
        s = self.sessions(codex)["codex-2"]
        self.assertEqual(len(s.prompts), 1)  # the user_message event; its response item is not counted again
        self.assertEqual((s.tokens["total"], s.tokens["input"], s.tokens["cache_read"], s.tokens["output"]),
                         (660, 400, 200, 60))

    def test_codex_exec_runs_are_usage_but_not_prompts(self):
        s = self.sessions(codex)["codex-3"]
        self.assertEqual((len(s.prompts), s.assistant_messages, s.tokens["total"]), (0, 1, 110))

    def test_codex_home_is_honoured(self):
        self.assertEqual(len(codex.locate(Path("/nonexistent"), {"CODEX_HOME": str(self.home / ".codex")})), 3)


class CursorTest(FakeHomeCase):
    def test_composers_and_bubbles(self):
        sessions = self.sessions(cursor)
        self.assertEqual(set(sessions), {"c1"})  # c0 only has 2025 activity
        c1 = sessions["c1"]
        self.assertEqual((len(c1.prompts), c1.assistant_messages, c1.lines_added, c1.lines_removed), (1, 2, 40, 4))
        self.assertEqual(c1.models, Counter({"claude-4.5-opus-high-thinking": 2}))  # 'default' -> composer model
        self.assertEqual((c1.tokens["input"], c1.tokens["output"], c1.tokens["total"]), (900, 90, 990))
        self.assertTrue(c1.partial_tokens)

    def test_python_fallback_matches_sqlite_json(self):
        path = cursor.locate(self.home, {})[0]
        self.assertEqual(cursor.parse_db(path, Y2026), cursor.parse_db(path, Y2026, use_json1=False))


class HermesTest(FakeHomeCase):
    def test_tokens_prompts_and_tools(self):
        sessions = self.sessions(hermes)
        self.assertEqual(set(sessions), {"h1", "h2"})
        h1, h2 = sessions["h1"], sessions["h2"]
        self.assertEqual((len(h1.prompts), h1.assistant_messages, h1.tokens["total"]), (2, 3, 26500))
        self.assertEqual(h1.tools, Counter({"terminal": 1, "web_search": 1}))
        # the delegated child session's "user" message came from the parent agent
        self.assertEqual((len(h2.prompts), h2.assistant_messages, h2.tokens["total"]), (0, 1, 110))
        self.assertAlmostEqual(h1.cost_usd + h2.cost_usd, 0.82)

    def test_a_locked_database_is_read_from_a_copy(self):
        path = hermes.locate(self.home, {})[0]
        holder = sqlite3.connect(path, isolation_level=None)
        holder.execute("BEGIN EXCLUSIVE")
        try:
            ids = {s.id for s in hermes.parse_db(path, Y2026)}
        finally:
            holder.execute("ROLLBACK")
            holder.close()
        self.assertEqual(ids, {"h1", "h2"})

    def test_profiles_are_read_once_each(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ".hermes" / "profiles" / "work").mkdir(parents=True)
            source = hermes.locate(self.home, {})[0]
            shutil.copy(source, home / ".hermes" / "state.db")
            shutil.copy(source, home / ".hermes" / "profiles" / "work" / "state.db")
            env = {"HERMES_HOME": str(home / ".hermes" / "profiles" / "work")}
            self.assertEqual(len(hermes.locate(home, env)), 2)


if __name__ == "__main__":
    unittest.main()
