"""The command end to end against a fake home: summary, card files, JSON, filters and failure modes."""
from __future__ import annotations

import io
import json
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from agent_wrapped.cli import main

from fakehome import EXPECTED, build_home


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.home = build_home(self.tmp)
        self.out = self.tmp / "out"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(["--home", str(self.home), "--utc", "--no-open", *args])
        return code, out.getvalue(), err.getvalue()

    def test_summary_and_card(self):
        code, out, _ = self.run_cli("--year", "2026", "--out", str(self.out))
        self.assertEqual(code, 0)
        for expected in ("Agent Wrapped · 2026", "Claude Code", "42.5K", "The Polyglot", "Scanned 7 log files"):
            self.assertIn(expected, out)
        ET.fromstring((self.out / "card.svg").read_text(encoding="utf-8"))
        self.assertIn("Save or share as PNG", (self.out / "card.html").read_text(encoding="utf-8"))

    def test_json_has_the_numbers_and_no_projects(self):
        code, out, _ = self.run_cli("--year", "2026", "--json")
        data = json.loads(out)
        self.assertEqual(code, 0)
        t = data["totals"]
        self.assertEqual((t["sessions"], t["prompts"], t["tokens"]["total"], t["cost_usd"]),
                         (EXPECTED["sessions"], EXPECTED["prompts"], EXPECTED["tokens"], EXPECTED["cost_usd"]))
        self.assertNotIn("projects", data)
        self.assertNotIn("secret-client", out)

    def test_show_projects_lists_them_outside_the_card(self):
        code, out, _ = self.run_cli("--year", "2026", "--show-projects", "--out", str(self.out))
        self.assertEqual(code, 0)
        self.assertIn("secret-client", out)
        self.assertNotIn("secret-client", (self.out / "card.svg").read_text(encoding="utf-8"))

    def test_claude_code_retention_warning(self):
        _, out, _ = self.run_cli("--year", "2026", "--json")
        self.assertEqual(len(json.loads(out)["warnings"]), 1)
        self.assertIn('"cleanupPeriodDays": 3650 to ~/.claude/settings.json', json.loads(out)["warnings"][0])
        (self.home / ".claude" / "settings.json").write_text('{"cleanupPeriodDays": 3650}', encoding="utf-8")
        _, out, _ = self.run_cli("--year", "2026", "--json")
        self.assertEqual(json.loads(out)["warnings"], [])

    def test_list_shows_what_was_found(self):
        code, out, _ = self.run_cli("--list")
        self.assertEqual(code, 0)
        self.assertRegex(out, r"Claude Code\s+2 files")
        self.assertRegex(out, r"Codex\s+3 files")
        self.assertRegex(out, r"Cursor\s+1 file ")
        self.assertRegex(out, r"Hermes\s+1 file ")

    def test_another_year_and_all_time(self):
        _, out, _ = self.run_cli("--year", "2025", "--json")
        self.assertEqual((json.loads(out)["totals"]["sessions"], json.loads(out)["totals"]["prompts"]), (3, 3))
        _, out, _ = self.run_cli("--all-time", "--json")
        data = json.loads(out)
        self.assertEqual((data["period"], data["totals"]["prompts"]), ("all time", EXPECTED["prompts"] + 3))

    def test_sources_filter(self):
        _, out, _ = self.run_cli("--year", "2026", "--sources", "codex", "--json")
        data = json.loads(out)
        self.assertEqual([a["name"] for a in data["agents"]], ["Codex"])
        self.assertEqual(data["warnings"], [])  # Claude Code was not read, so its retention is not our business

    def test_bad_input_and_empty_home(self):
        code, _, err = self.run_cli("--sources", "copilot")
        self.assertEqual(code, 2)
        self.assertIn("unknown source copilot", err)
        empty = self.tmp / "empty"
        empty.mkdir()
        out, err_buf = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err_buf):
            code = main(["--home", str(empty), "--no-open"])
        self.assertEqual(code, 1)
        self.assertIn("no agent activity found", err_buf.getvalue())


if __name__ == "__main__":
    unittest.main()
