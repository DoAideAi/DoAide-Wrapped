"""agent-wrapped: your year with AI coding agents, from the logs already on this machine.

    agent-wrapped                  this year: a summary here, plus card.svg and card.html
    agent-wrapped --year 2025      another year (--all-time for everything)
    agent-wrapped --png            also card.png (needs Chrome or Chromium)
    agent-wrapped --json           the numbers as JSON, no card
    agent-wrapped --list           which agents were found, and where

Reads Claude Code, Codex, Cursor and Hermes Agent logs. Nothing is uploaded, and the card shows
totals only: no project names, prompts or paths.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from . import __version__, card, report, stats
from .model import ALL_TIME, year_window
from .sources import SOURCES, claude_code, collect, locate_all


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-wrapped",
        description=__doc__.split("\n\n")[0],
        epilog="\n\n".join(__doc__.split("\n\n")[1:]),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--year", type=int, help="calendar year to wrap (default: this year)")
    parser.add_argument("--all-time", action="store_true", help="wrap everything in the logs")
    parser.add_argument("--sources", help="comma-separated subset of: " + ", ".join(SOURCES))
    parser.add_argument("--out", help="folder for the card (default: ./agent-wrapped-<year>)")
    parser.add_argument("--png", action="store_true", help="also render card.png with headless Chrome or Chromium")
    parser.add_argument("--no-open", action="store_true", help="don't open the card in a browser")
    parser.add_argument("--json", action="store_true", help="print the numbers as JSON and stop")
    parser.add_argument("--show-projects", action="store_true",
                        help="list top projects in the terminal and the JSON (never on the card)")
    parser.add_argument("--hide-cost", action="store_true", help="leave the API-equivalent cost off the card")
    parser.add_argument("--url", default="", help="link printed in the card's footer")
    parser.add_argument("--utc", action="store_true", help="count days and hours in UTC instead of local time")
    parser.add_argument("--jobs", type=int, default=min(8, os.cpu_count() or 1),
                        help="worker processes for reading log files (default: up to 8)")
    parser.add_argument("--home", help="read agent logs under this folder instead of your home folder "
                                       "(CLAUDE_CONFIG_DIR, CODEX_HOME and HERMES_HOME are then ignored)")
    parser.add_argument("--list", action="store_true", help="show which agents were found and where, then stop")
    parser.add_argument("--version", action="version", version=f"agent-wrapped {__version__}")
    return parser


def _names(value: Optional[str]) -> List[str]:
    names = [part.strip() for part in (value or "").split(",") if part.strip()] or list(SOURCES)
    unknown = [n for n in names if n not in SOURCES]
    if unknown:
        raise ValueError(f"unknown source {', '.join(unknown)}; choose from {', '.join(SOURCES)}")
    return names


def _tilde(path: Path, home: Path) -> str:
    try:
        return "~/" + str(path.relative_to(home))
    except ValueError:
        return str(path)


def _warnings(found, home: Path, env) -> List[str]:
    """Things that make the numbers smaller than the year really was, and how to fix them."""
    if not found.get(claude_code.NAME):
        return []
    days, settings = claude_code.retention(home, env)
    if days >= 365:
        return []
    return [f"Claude Code deletes transcripts after {days} days (cleanupPeriodDays), so older sessions are "
            f"missing here. Add \"cleanupPeriodDays\": {claude_code.KEEP_DAYS} to {_tilde(settings, home)} to "
            "keep the rest of the year."]


def _write_card(result: dict, args) -> List[Path]:
    slug = result["period"].replace(" ", "-")
    out = Path(args.out) if args.out else Path.cwd() / f"agent-wrapped-{slug}"
    out.mkdir(parents=True, exist_ok=True)
    show_cost = not args.hide_cost
    svg_text = card.svg(result, url=args.url, show_cost=show_cost)
    (out / "card.svg").write_text(svg_text, encoding="utf-8")
    (out / "card.html").write_text(card.page(svg_text, card.share_text(result, args.url, show_cost)),
                                   encoding="utf-8")
    written = [out / "card.svg", out / "card.html"]
    if args.png:
        written.append(card.render_png(svg_text, out / "card.png"))
    return written


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        names = _names(args.sources)
    except ValueError as exc:
        print(f"agent-wrapped: {exc}", file=sys.stderr)
        return 2
    home = Path(args.home).expanduser() if args.home else Path.home()
    env = {} if args.home else dict(os.environ)
    found = locate_all(names, home, env)
    if args.list:
        sys.stdout.write(report.render_found(found))
        return 0
    tz = timezone.utc if args.utc else None
    year = None if args.all_time else (args.year or datetime.now(tz).year)
    window = ALL_TIME if year is None else year_window(year, tz)
    started = time.time()
    result = stats.build(collect(found, window, max(1, args.jobs)), window, tz=tz, year=year,
                         show_projects=args.show_projects)
    result["warnings"] = _warnings(found, home, env)
    elapsed = time.time() - started
    if not result["totals"]["sessions"]:
        print(f"agent-wrapped: no agent activity found for {result['period']}.", file=sys.stderr)
        sys.stderr.write(report.render_found(found))
        return 1
    if args.json:
        print(json.dumps(result, indent=2))
        return 0
    sys.stdout.write(report.render(result, elapsed, sum(len(paths) for paths in found.values())))
    try:
        written = _write_card(result, args)
    except card.CardError as exc:
        print(f"agent-wrapped: {exc}", file=sys.stderr)
        return 1
    print("\nYour card:")
    for path in written:
        print(f"  {path}")
    page = written[1]
    if not args.no_open and sys.stdout.isatty():
        webbrowser.open(page.resolve().as_uri())
    print('\nOpen card.html and press "Save or share as PNG". #AgentWrapped')
    return 0
