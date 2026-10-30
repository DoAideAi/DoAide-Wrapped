"""The card: well-formed SVG, totals only (never projects or paths), and every line inside the frame."""
from __future__ import annotations

import copy
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET
from datetime import timezone

from agent_wrapped import card, stats
from agent_wrapped.model import year_window
from agent_wrapped.sources import SOURCES, collect, locate_all

from fakehome import build_home

SVG = "{http://www.w3.org/2000/svg}"


def texts(svg_text: str):
    return [(el.text or "", el.attrib) for el in ET.fromstring(svg_text).iter(SVG + "text")]


class CardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        home = build_home(cls.tmp)
        window = year_window(2026, timezone.utc)
        found = locate_all(list(SOURCES), home, {})
        cls.stats = stats.build(collect(found, window), window, tz=timezone.utc, year=2026)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_the_card_states_the_totals(self):
        shown = [t for t, _ in texts(card.svg(self.stats))]
        for expected in ("AGENT WRAPPED · 2026", "42.5K", "11", "8", "$2.22", "THE POLYGLOT",
                         "Claude Code · Codex · Hermes · Cursor"):
            self.assertIn(expected, shown)

    def test_the_card_never_shows_projects_or_paths(self):
        svg_text = card.svg(self.stats)
        page = card.page(svg_text, card.share_text(self.stats))
        for secret in ("secret-client", "/Users/", "projects"):
            self.assertNotIn(secret, svg_text)
            self.assertNotIn(secret, page)

    def test_hide_cost_shows_lines_instead(self):
        shown = [t for t, _ in texts(card.svg(self.stats, show_cost=False))]
        self.assertNotIn("$2.22", shown)
        self.assertIn("+160", shown)
        self.assertNotIn("$", card.share_text(self.stats, show_cost=False))

    def test_every_line_stays_inside_the_card(self):
        loud = copy.deepcopy(self.stats)
        loud["totals"]["tokens"]["total"] = 987.6e12
        loud["totals"]["prompts"] = 123_456_789
        loud["totals"]["sessions"] = 98_765_432
        loud["totals"]["cost_usd"] = 12_345_678.0
        loud["time"]["hours_with_agents"] = 8_760
        loud["models"][0]["name"] = "Claude Opus 5.5 Extended Thinking Max Context Preview Edition"
        loud["persona"] = {"name": "The Shell Whisperer", "tagline": "",
                           "why": "100% of tool calls ran in a shell, and every one of them was rm -rf node_modules"}
        loud["roast"] = "word " * 60
        loud["agents"] = [{"name": n} for n in ("Claude Code", "Codex", "Cursor", "Hermes", "Gemini CLI", "OpenCode")]
        for text, attrs in texts(card.svg(loud, url="https://wrapped.doaide.com/some/very/long/path")):
            size = float(attrs["font-size"])
            glyph = card.CAPS_GLYPH if text.isupper() else card.GLYPH
            width = len(text) * (glyph * size + float(attrs.get("letter-spacing", 0)))
            left = float(attrs["x"]) - (width / 2 if attrs.get("text-anchor") == "middle" else 0)
            self.assertLessEqual(left + width, card.W - card.M / 2, text)

    def test_markup_in_names_is_escaped(self):
        odd = copy.deepcopy(self.stats)
        odd["models"][0]["name"] = 'A&B <script>"x"</script>'
        svg_text = card.svg(odd)
        ET.fromstring(svg_text)  # still well-formed
        self.assertNotIn("<script>", svg_text)

    def test_page_has_the_card_and_a_prefilled_post(self):
        text = card.share_text(self.stats, url="https://wrapped.doaide.com")
        self.assertEqual(text, "My 2026 in AI agents: 42.5K tokens, 11 prompts, 8-day streak. "
                               "$2.22 of API-equivalent usage. Persona: The Polyglot. #AgentWrapped "
                               "https://wrapped.doaide.com")
        page = card.page(card.svg(self.stats), text)
        self.assertIn("<svg", page)
        self.assertIn("https://x.com/intent/post?text=My%202026%20in%20AI%20agents", page)


if __name__ == "__main__":
    unittest.main()
