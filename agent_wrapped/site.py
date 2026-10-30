"""The wrapped.doaide.com page: what the tool does, an example card and the keep-your-history tip.

    python3 -m agent_wrapped.site        rebuild site/index.html (a test fails while it is stale)

The page is static, makes no network requests and loads nothing from third parties.
"""
from __future__ import annotations

import html
import sys
from pathlib import Path

from . import card
from .sources.claude_code import KEEP_DAYS

SITE = Path(__file__).resolve().parent.parent / "site" / "index.html"
REPO = "https://github.com/DoAideAi/DoAide-Wrapped"
INSTALL = f"uvx --from git+{REPO} agent-wrapped"

# Made-up numbers for the example card; the page labels them as an example.
EXAMPLE = {
    "year": 2026,
    "period": "2026",
    "agents": [{"name": "Claude Code"}, {"name": "Codex"}, {"name": "Cursor"}],
    "totals": {"tokens": {"total": 4_200_000_000}, "prompts": 6180, "sessions": 1240, "cost_usd": 3480.0,
               "lines_added": 412_000, "tool_calls": 210_000},
    "time": {"active_days": 214, "streak": {"days": 41}, "hours_with_agents": 612.0},
    "models": [{"name": "Claude Opus 5", "share": 0.58}],
    "persona": {"name": "The Night Owl", "tagline": "Your best work happens after 10pm.",
                "why": "38% of prompts after 10pm"},
    "roast": "You interrupted your agent 412 times. It never once interrupted you.",
}

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Agent Wrapped: your year with AI coding agents</title>
<meta name="description" content="One command turns your Claude Code, Codex, Cursor and Hermes logs into a card worth posting. Nothing is uploaded.">
<style>
:root{{--ink:#0b0716;--lime:#c8ff4d;--muted:#a9a3c7;--panel:#160f2e;--line:#2b1f4d}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--ink);color:#f5f5f7;font:17px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:1040px;margin:0 auto;padding:40px 20px 60px;display:grid;gap:40px}}
.hero{{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,.9fr);gap:36px;align-items:center}}
@media (max-width:800px){{.hero{{grid-template-columns:minmax(0,1fr)}}}}
h1{{font-size:clamp(34px,5vw,54px);line-height:1.05;margin:0 0 14px}}
h2{{font-size:24px;margin:0 0 10px}}
.kicker{{color:var(--lime);font-weight:800;letter-spacing:.2em;font-size:13px}}
p{{margin:0 0 12px;color:#dcd8ee}}
.muted{{color:var(--muted);font-size:14px}}
.cmd{{display:flex;gap:8px;align-items:stretch;margin:16px 0 6px}}
code,pre{{font:15px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace}}
.cmd code,pre{{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px 14px;
overflow-x:auto;white-space:pre;flex:1;min-width:0;margin:0}}
button{{font:700 15px system-ui,sans-serif;border:0;border-radius:12px;padding:0 16px;background:var(--lime);
color:var(--ink);cursor:pointer}}
figure{{margin:0}}
figure svg{{width:100%;height:auto;border-radius:22px;box-shadow:0 20px 60px rgba(0,0,0,.5)}}
figcaption{{color:var(--muted);font-size:13px;text-align:center;margin-top:8px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:16px}}
.box{{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:18px}}
.tip{{border-color:var(--lime)}}
a{{color:var(--lime)}}
footer{{color:var(--muted);font-size:13px;border-top:1px solid var(--line);padding-top:18px}}
</style></head><body><main>
<section class="hero">
<div>
<div class="kicker">AGENT WRAPPED</div>
<h1>Your year with AI coding agents, as one card.</h1>
<p>One command reads the logs Claude Code, Codex, Cursor and Hermes Agent already keep on your
computer: tokens, prompts, streaks, your most-used model, a persona and one line of roast.
Nothing is uploaded.</p>
<div class="cmd"><code id="install">{install}</code><button data-copy="install">Copy</button></div>
<p class="muted">Needs Python 3.9+ and <a href="https://docs.astral.sh/uv/">uv</a>. Or clone
<a href="{repo}">the repository</a> and run <code>python3 -m agent_wrapped</code>.</p>
</div>
<figure>{card}<figcaption>Example card with made-up numbers. Yours is made on your machine.</figcaption></figure>
</section>
<section class="box tip">
<h2>Do this today: keep your Claude Code history</h2>
<p>Claude Code deletes session transcripts after 30 days unless you change
<code>cleanupPeriodDays</code>. Raise it now and December's card covers the year. Already-deleted
sessions can't come back.</p>
<div class="cmd"><pre id="keep">{{ "cleanupPeriodDays": {keep} }}</pre><button data-copy="keep">Copy</button></div>
<p class="muted">Add it to <code>~/.claude/settings.json</code>.
<a href="https://code.claude.com/docs/en/settings-reference#cleanupperioddays">Claude Code's settings reference</a>.</p>
</section>
<section class="grid">
<div class="box"><h2>Private by design</h2><p>Reads the logs where they are and never writes to them. Message text is
only checked to tell your prompts from tool output. No network requests. The card shows totals, never
project names, prompts or paths.</p></div>
<div class="box"><h2>Four agents, one year</h2><p>Claude Code, Codex (Desktop and CLI), Cursor and Hermes
Agent, merged into one set of numbers. Missing an agent?
<a href="{repo}/issues/new?template=new-agent.yml">Ask for it</a>.</p></div>
<div class="box"><h2>Honest numbers</h2><p>Replies that agents log over several lines count once, background-task
notifications and scripted runs don't count as prompts, and costs are what the agents themselves recorded.</p></div>
</section>
<footer>MIT licensed · <a href="{repo}">source</a> · DoAide. Not affiliated with Anthropic, OpenAI,
Anysphere (Cursor) or Nous Research.</footer>
</main>
<script>
document.querySelectorAll("button[data-copy]").forEach(function (button) {{
  button.onclick = function () {{
    var text = document.getElementById(button.dataset.copy).textContent;
    if (navigator.clipboard) {{ navigator.clipboard.writeText(text); }}
    button.textContent = "Copied";
    setTimeout(function () {{ button.textContent = "Copy"; }}, 1500);
  }};
}});
</script>
</body></html>
"""


def build() -> str:
    return PAGE.format(card=card.svg(EXAMPLE, url="wrapped.doaide.com"), install=html.escape(INSTALL),
                       keep=KEEP_DAYS, repo=REPO)


def write(path: Path = SITE) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build(), encoding="utf-8")
    return path


if __name__ == "__main__":
    print(write(Path(sys.argv[1]) if len(sys.argv) > 1 else SITE))
