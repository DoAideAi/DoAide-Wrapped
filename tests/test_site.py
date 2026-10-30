"""The committed wrapped.doaide.com page matches its generator and loads nothing from elsewhere."""
from __future__ import annotations

import re
import unittest

from agent_wrapped import site


class SiteTest(unittest.TestCase):
    def test_committed_page_is_current(self):
        self.assertTrue(site.SITE.exists(), "run: python3 -m agent_wrapped.site")
        self.assertEqual(site.SITE.read_text(encoding="utf-8"), site.build(),
                         "site/index.html is stale; run: python3 -m agent_wrapped.site")

    def test_page_loads_nothing_from_third_parties(self):
        page = site.build()
        self.assertIsNone(re.search(r'<(script|img|link|iframe)[^>]+(src|href)="https?://', page))
        self.assertNotIn("@import", page)

    def test_page_carries_the_install_command_and_the_retention_tip(self):
        page = site.build()
        self.assertIn("uvx --from git+https://github.com/DoAideAi/DoAide-Wrapped agent-wrapped", page)
        self.assertIn('{ "cleanupPeriodDays": 3650 }', page)
        self.assertIn("Example card with made-up numbers", page)


if __name__ == "__main__":
    unittest.main()
