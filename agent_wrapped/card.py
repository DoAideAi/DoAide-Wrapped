"""The shareable card (SVG), a page that saves it as PNG, and an optional headless-Chrome PNG.

The card states totals only: no project names, no prompt text, no file paths.
"""
from __future__ import annotations

import html
import shutil
import subprocess
import tempfile
import textwrap
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import quote

from .fmt import compact, grouped, hours_text, money, percent

W, H = 1080, 1350
M = 80  # side margin
FONT = "Inter, 'SF Pro Display', 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
LIME, PINK, CYAN, TEXT, MUTED, INK = "#c8ff4d", "#ff5fd2", "#5ff2ff", "#f5f5f7", "#aaa4c8", "#0b0716"
GLYPH = 0.58  # average glyph width in em for this font stack
CAPS_GLYPH = 0.68  # bold capitals run wider
CHROME_PATHS = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
)


class CardError(ValueError):
    pass


def _text(x, y, content, size, fill, weight=400, anchor="start", spacing=0, opacity=1.0, italic=False) -> str:
    extra = f' letter-spacing="{spacing}"' if spacing else ""
    extra += f' opacity="{opacity}"' if opacity != 1.0 else ""
    extra += ' font-style="italic"' if italic else ""
    return (
        f'<text x="{x}" y="{y}" font-family="{html.escape(FONT)}" font-size="{size}" '
        f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}"{extra}>{html.escape(content)}</text>'
    )


def fit(text: str, widest: int, largest: int, smallest: int = 20) -> int:
    """The largest font size (up to `largest`) at which `text` stays within `widest` px."""
    return max(smallest, min(largest, int(widest / (GLYPH * max(len(text), 1)))))


def cells(stats: dict, show_cost: bool) -> List[Tuple[str, str]]:
    t, tm = stats["totals"], stats["time"]
    if show_cost and t["cost_usd"] >= 1:
        last = (money(t["cost_usd"]), "API-equivalent cost")
    elif t["lines_added"]:
        last = ("+" + compact(t["lines_added"]), "lines added")
    else:
        last = (compact(t["tool_calls"]), "tool calls")
    return [
        (grouped(t["prompts"]), "prompts sent"),
        (grouped(t["sessions"]), "sessions"),
        (grouped(tm["active_days"]), "active days"),
        (grouped(tm["streak"]["days"]), "day streak"),
        (hours_text(tm["hours_with_agents"]), "with my agents"),
        last,
    ]


def svg(stats: dict, url: str = "", show_cost: bool = True) -> str:
    t = stats["totals"]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        '<defs><linearGradient id="bg" x1="0" y1="0" x2="0.35" y2="1">'
        '<stop offset="0" stop-color="#2b1060"/><stop offset="0.55" stop-color="#140a2e"/>'
        '<stop offset="1" stop-color="#07060d"/></linearGradient>'
        f'<linearGradient id="pill" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{LIME}"/>'
        f'<stop offset="1" stop-color="{CYAN}"/></linearGradient></defs>',
        f'<rect width="{W}" height="{H}" fill="url(#bg)"/>',
        f'<circle cx="{W - 60}" cy="140" r="260" fill="{PINK}" opacity="0.10"/>',
        f'<circle cx="{W - 150}" cy="400" r="140" fill="{CYAN}" opacity="0.07"/>',
        _text(M, 110, f"AGENT WRAPPED · {stats['period'].upper()}", 30, LIME, 800, spacing=6),
        _text(M, 190, "My year in AI agents" if stats.get("year") else "My life with AI agents", 64, TEXT, 800),
    ]
    agents = " · ".join(a["name"] for a in stats["agents"])
    if agents:
        parts.append(_text(M, 244, agents, fit(agents, W - 2 * M, 34), MUTED, 600))
    hero = compact(t["tokens"]["total"])
    parts.append(_text(M - 6, 450, hero, fit(hero, W - 2 * M, 230), LIME, 900))
    parts.append(_text(M, 506, "tokens through my agents", 44, TEXT, 700))
    for i, (value, label) in enumerate(cells(stats, show_cost)):
        x = M if i % 2 == 0 else W // 2 + 20
        y = 615 + (i // 2) * 135
        parts.append(_text(x, y, value, fit(value, W // 2 - M - 20, 76), TEXT, 800))
        parts.append(_text(x, y + 40, label, 28, MUTED, 500))
    if stats["models"]:
        top = stats["models"][0]
        line = f"{top['name']} · {percent(top['share'])} of replies"
        parts.append(_text(M, 990, "MOST-USED MODEL", 24, MUTED, 700, spacing=4))
        parts.append(_text(M, 1036, line, fit(line, W - 2 * M, 42), TEXT, 700))
    parts.extend(_persona(stats))
    parts.extend(_footer(url))
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def _persona(stats: dict) -> List[str]:
    persona = stats["persona"]
    label = persona["name"].upper()
    width = int(len(label) * (CAPS_GLYPH * 30 + 3)) + 60
    parts = [
        f'<rect x="{M}" y="1066" width="{width}" height="60" rx="30" fill="url(#pill)"/>',
        _text(M + width // 2, 1107, label, 30, INK, 900, anchor="middle", spacing=3),
        _text(M, 1166, persona["why"], fit(persona["why"], W - 2 * M, 30), TEXT, 600),
    ]
    per_line = int((W - 2 * M) / (GLYPH * 27))
    for i, line in enumerate(textwrap.wrap(stats["roast"], per_line)[:2]):
        parts.append(_text(M, 1212 + i * 34, line, 27, MUTED, 500, italic=True))
    return parts


def _footer(url: str) -> List[str]:
    brand = "agent-wrapped by DoAide" + (f"  ·  {url}" if url else "")
    return [
        f'<circle cx="{M + 10}" cy="1290" r="10" fill="{LIME}"/>',
        _text(M + 30, 1300, brand, fit(brand, W - 2 * M - 30, 28), TEXT, 700),
        _text(M, 1332, "Made from local logs. Nothing left this machine.", 20, MUTED, 500),
    ]


def share_text(stats: dict, url: str = "", show_cost: bool = True) -> str:
    t, tm = stats["totals"], stats["time"]
    lead = f"My {stats['year']}" if stats.get("year") else "My life"
    parts = [f"{lead} in AI agents: {compact(t['tokens']['total'])} tokens, {grouped(t['prompts'])} prompts, "
             f"{tm['streak']['days']}-day streak."]
    if show_cost and t["cost_usd"] >= 1:
        parts.append(f"{money(t['cost_usd'])} of API-equivalent usage.")
    parts.append(f"Persona: {stats['persona']['name']}.")
    parts.append("#AgentWrapped")
    if url:
        parts.append(url)
    return " ".join(parts)


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>My Agent Wrapped</title>
<style>
body{{margin:0;background:#0b0716;color:#eee;font-family:system-ui,-apple-system,sans-serif;display:flex;
flex-direction:column;align-items:center;gap:14px;padding:18px}}
#card svg{{width:min(100%,540px);height:auto;border-radius:22px;box-shadow:0 20px 60px rgba(0,0,0,.5)}}
.row{{display:flex;gap:10px;flex-wrap:wrap;justify-content:center}}
button,a.btn{{font:600 17px system-ui,sans-serif;padding:12px 20px;border-radius:999px;border:0;
background:#c8ff4d;color:#0b0716;text-decoration:none;cursor:pointer}}
.alt{{background:#2b1f4d !important;color:#fff !important}}
textarea{{width:min(100%,540px);height:84px;background:#160f2e;color:#eee;border:1px solid #2b1f4d;
border-radius:12px;padding:10px;font:15px system-ui,sans-serif}}
p{{color:#9a94b8;font-size:13px;max-width:540px;text-align:center}}
</style></head><body>
<div id="card">{svg}</div>
<div class="row">
<button id="save">Save or share as PNG</button>
<button id="copy" class="alt">Copy post text</button>
<a class="btn alt" href="{x_url}" target="_blank" rel="noopener">Post on X</a>
</div>
<textarea id="text" readonly>{text}</textarea>
<p>Attach the PNG to your post. This page was made from logs on your computer and loads nothing from the internet.</p>
<script>
document.getElementById("save").onclick = function () {{
  var svg = document.querySelector("#card svg");
  var img = new Image();
  img.onload = function () {{
    var canvas = document.createElement("canvas");
    canvas.width = {w}; canvas.height = {h};
    canvas.getContext("2d").drawImage(img, 0, 0, {w}, {h});
    canvas.toBlob(function (blob) {{
      var file = new File([blob], "agent-wrapped.png", {{type: "image/png"}});
      if (navigator.canShare && navigator.canShare({{files: [file]}})) {{
        navigator.share({{files: [file]}}).catch(function () {{}});
        return;
      }}
      var link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = "agent-wrapped.png";
      link.click();
    }}, "image/png");
  }};
  img.src = "data:image/svg+xml;charset=utf-8," +
    encodeURIComponent(new XMLSerializer().serializeToString(svg));
}};
document.getElementById("copy").onclick = function () {{
  var box = document.getElementById("text");
  box.select();
  if (navigator.clipboard) {{ navigator.clipboard.writeText(box.value); }} else {{ document.execCommand("copy"); }}
}};
</script>
</body></html>
"""


def page(svg_text: str, text: str) -> str:
    x_url = "https://x.com/intent/post?text=" + quote(text)
    return PAGE.format(svg=svg_text, text=html.escape(text), x_url=html.escape(x_url), w=W, h=H)


def find_chrome() -> Optional[str]:
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    for path in CHROME_PATHS:
        if Path(path).exists():
            return path
    return None


def render_png(svg_text: str, out_png: Path, chrome: Optional[str] = None) -> Path:
    chrome = chrome or find_chrome()
    if not chrome:
        raise CardError("a PNG needs Chrome or Chromium; open card.html and use its save button instead")
    out_png = Path(out_png).resolve()
    with tempfile.TemporaryDirectory() as tmp:
        sheet = Path(tmp) / "card.html"
        sheet.write_text(
            '<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;padding:0;'
            f'background:#000}}svg{{display:block}}</style></head><body>{svg_text}</body></html>',
            encoding="utf-8",
        )
        command = [
            chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
            "--no-default-browser-check", "--force-device-scale-factor=1",
            f"--user-data-dir={Path(tmp) / 'profile'}", f"--window-size={W},{H}",
            f"--screenshot={out_png}", sheet.as_uri(),
        ]
        try:
            subprocess.run(command, check=True, capture_output=True, timeout=90)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            detail = (getattr(exc, "stderr", b"") or b"").decode("utf-8", "replace").strip()[-300:]
            raise CardError(f"Chrome could not render the PNG ({exc.__class__.__name__}) {detail}") from None
    if not out_png.exists():
        raise CardError(f"Chrome did not write {out_png}")
    return out_png
