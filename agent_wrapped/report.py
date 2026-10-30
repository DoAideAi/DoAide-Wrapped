"""Plain-text output for the terminal: the year's summary and the list of agents found."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional

from .fmt import compact, day_label, grouped, hour_label, hours_text, money, percent
from .names import SOURCE_LABELS

QUIRKS = (
    ("interrupts", "interrupts"),
    ("queued", "queued messages"),
    ("compactions", "context compactions"),
    ("absolutely_right", '"absolutely right"s'),
    ("api_errors", "API errors survived"),
)


def render_found(found: Dict[str, List[Path]]) -> str:
    lines = ["Agent logs found:"]
    for name, paths in found.items():
        label = SOURCE_LABELS.get(name, name)
        if not paths:
            lines.append(f"  {label:<12} {'-':>7}  not found")
            continue
        where = os.path.commonpath([str(p) for p in paths]) if len(paths) > 1 else str(paths[0])
        noun = "file" if len(paths) == 1 else "files"
        lines.append(f"  {label:<12} {grouped(len(paths)):>7} {noun:<5}  {where}")
    return "\n".join(lines) + "\n"


def _agent_rows(stats: dict) -> List[str]:
    rows = []
    for agent in stats["agents"]:
        tokens = compact(agent["tokens"]) + ("+" if agent["partial_tokens"] else "")
        cost = f"   {money(agent['cost_usd'])} API-equivalent" if agent["cost_usd"] >= 0.01 else ""
        rows.append(f"  {agent['name']:<12} {grouped(agent['sessions']):>7} sessions {grouped(agent['prompts']):>8} "
                    f"prompts {tokens:>9} tokens{cost}")
    return rows


def _time_rows(tm: dict) -> List[str]:
    streak = tm["streak"]
    span = f" ({day_label(streak['start'])} to {day_label(streak['end'])})" if streak["days"] else ""
    rows = [f"  Active days   {tm['active_days']} · longest streak {streak['days']} days{span}"]
    if tm["busiest_day"]:
        busiest = tm["busiest_day"]
        rows.append(f"  Busiest day   {day_label(busiest['date'])} ({grouped(busiest['prompts'])} {tm['basis']}) · "
                    f"busiest hour {hour_label(tm['busiest_hour'])}")
    longest = tm["longest_session"]
    rows.append(f"  Time          {hours_text(tm['hours_with_agents'])} with agents · "
                f"{hours_text(tm['agent_hours'])} of agent sessions (they overlap)"
                + (f" · longest session {hours_text(longest['hours'])} in {longest['agent']}" if longest else ""))
    rows.append(f"  Habits        {percent(tm['night_share'])} after 10pm · {percent(tm['early_share'])} before 9am · "
                f"{percent(tm['weekend_share'])} on weekends")
    return rows


def render(stats: dict, elapsed: Optional[float] = None, files: Optional[int] = None) -> str:
    t, tok = stats["totals"], stats["totals"]["tokens"]
    lines = [f"Agent Wrapped · {stats['period']}  (read from local logs; nothing was uploaded)", ""]
    lines += _agent_rows(stats) + [""]
    lines.append(f"  Tokens        {compact(tok['total'])}  (input {compact(tok['input'])} · output "
                 f"{compact(tok['output'])} · cache read {compact(tok['cache_read'])} · cache write "
                 f"{compact(tok['cache_write'])})")
    lines.append(f"  Prompts       {grouped(t['prompts'])} in {grouped(t['sessions'])} sessions · "
                 f"{grouped(t['assistant_messages'])} replies · {grouped(t['tool_calls'])} tool calls")
    lines += _time_rows(stats["time"])
    if stats["models"]:
        lines.append("  Models        " + " · ".join(f"{m['name']} {percent(m['share'])}" for m in stats["models"][:3]))
    if stats["tools"]:
        lines.append("  Tools         " + " · ".join(f"{c['name']} {percent(c['share'])}" for c in stats["tools"][:4]))
    if t["lines_added"] or t["lines_removed"]:
        lines.append(f"  Lines         +{grouped(t['lines_added'])} / -{grouped(t['lines_removed'])}")
    if t["cost_usd"] >= 0.01:
        lines.append(f"  Cost          {money(t['cost_usd'])} API-equivalent, as recorded by the agents")
    quirks = [f"{grouped(t[key])} {label}" for key, label in QUIRKS if t[key]]
    if quirks:
        lines.append("  Quirks        " + " · ".join(quirks))
    persona = stats["persona"]
    lines += ["", f"  Persona       {persona['name']}: {persona['tagline']} ({persona['why']})",
              f"  Roast         {stats['roast']}"]
    if stats.get("projects"):
        lines += ["", "  Top projects (listed here only, never on the card)"]
        lines += [f"    {p['name'][:32]:<32} {grouped(p['prompts']):>7} prompts {grouped(p['sessions']):>6} sessions"
                  for p in stats["projects"]]
    if stats["notes"]:
        lines.append("")
        lines += [f"  Note: {note}" for note in stats["notes"]]
    for warning in stats.get("warnings", []):
        lines += ["", f"  Heads up: {warning}"]
    if elapsed is not None and files is not None:
        lines += ["", f"  Scanned {grouped(files)} log files in {elapsed:.1f}s."]
    return "\n".join(lines) + "\n"
