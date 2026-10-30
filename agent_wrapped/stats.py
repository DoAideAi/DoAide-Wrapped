"""The year's numbers from normalized sessions: totals, time patterns, top models and tools."""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

from . import __version__
from .model import TOKEN_KINDS, Session, Window
from .names import SOURCE_LABELS, pretty_model, tool_category
from .persona import pick_persona, pick_roast

IDLE_GAP = 30 * 60  # a pause longer than this ends a stretch of active time
NIGHT_HOURS = frozenset({22, 23, 0, 1, 2, 3, 4})
EARLY_HOURS = frozenset({5, 6, 7, 8})
COUNTS = ("assistant_messages", "lines_added", "lines_removed", "interrupts", "compactions", "queued",
          "absolutely_right", "api_errors")


def local(ts: float, tz=None) -> datetime:
    return datetime.fromtimestamp(ts, tz) if tz is not None else datetime.fromtimestamp(ts)


def active_seconds(times: Sequence[float], gap: float = IDLE_GAP) -> float:
    """Time covered by activity: steps of up to `gap` between consecutive events count."""
    ordered = sorted(times)
    return sum(step for step in (b - a for a, b in zip(ordered, ordered[1:])) if 0 < step <= gap)


def longest_streak(days) -> Tuple[int, Optional[date], Optional[date]]:
    best: Tuple[int, Optional[date], Optional[date]] = (0, None, None)
    run, run_start, previous = 0, None, None
    for day in sorted(set(days)):
        if previous is not None and day - previous == timedelta(days=1):
            run += 1
        else:
            run, run_start = 1, day
        if run > best[0]:
            best = (run, run_start, day)
        previous = day
    return best


def build(by_source: Dict[str, List[Session]], window: Window, tz=None, year: Optional[int] = None,
          show_projects: bool = False) -> dict:
    sessions = [s for group in by_source.values() for s in group]
    models: Counter = Counter()
    tools: Counter = Counter()
    for s in sessions:
        models.update(s.models)
        tools.update(s.tools)
    stats = {
        "tool": f"agent-wrapped {__version__}",
        "year": year,
        "period": str(year) if year else "all time",
        "agents": _agents(by_source),
        "totals": _totals(sessions, tools),
        "time": _time(sessions, tz),
        "models": _ranked(models, 5, pretty_model),
        "tools": _ranked(tools, 6, tool_category),
        "notes": _notes(sessions),
    }
    stats["persona"] = pick_persona(stats)
    stats["roast"] = pick_roast(stats)
    if show_projects:
        stats["projects"] = _projects(sessions)
    return stats


def _ranked(counter: Counter, limit: int, label) -> List[dict]:
    merged: Counter = Counter()
    for key, value in counter.items():
        merged[label(key)] += value
    total = sum(merged.values()) or 1
    ordered = sorted(merged.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]
    return [{"name": name, "count": n, "share": n / total} for name, n in ordered]


def _agents(by_source: Dict[str, List[Session]]) -> List[dict]:
    rows = []
    for name, group in by_source.items():
        if group:
            rows.append({
                "id": name,
                "name": SOURCE_LABELS.get(name, name),
                "sessions": len(group),
                "prompts": sum(len(s.prompts) for s in group),
                "tokens": sum(s.tokens["total"] for s in group),
                "cost_usd": round(sum(s.cost_usd for s in group), 2),
                "partial_tokens": any(s.partial_tokens for s in group),
            })
    return sorted(rows, key=lambda r: (-r["prompts"], -r["sessions"], r["id"]))


def _totals(sessions: List[Session], tools: Counter) -> dict:
    tokens: Counter = Counter()
    for s in sessions:
        tokens.update(s.tokens)
    categories: Counter = Counter()
    for name, calls in tools.items():
        categories[tool_category(name)] += calls
    totals = {key: sum(getattr(s, key) for s in sessions) for key in COUNTS}
    totals.update({
        "sessions": len(sessions),
        "prompts": sum(len(s.prompts) for s in sessions),
        "tool_calls": sum(tools.values()),
        "edits": categories["Edit"],
        "shell": categories["Shell"],
        "tokens": {kind: tokens[kind] for kind in TOKEN_KINDS + ("reasoning", "total")},
        "cost_usd": round(sum(s.cost_usd for s in sessions), 2),
    })
    return totals


def _time(sessions: List[Session], tz) -> dict:
    prompts = sorted(ts for s in sessions for ts in s.prompts)
    events = sorted(ts for s in sessions for ts in s.events)
    stamps = [local(ts, tz) for ts in (prompts or events)]
    days = Counter(stamp.date() for stamp in stamps)
    hours, weekdays = [0] * 24, [0] * 7
    for stamp in stamps:
        hours[stamp.hour] += 1
        weekdays[stamp.weekday()] += 1
    counted = len(stamps) or 1
    streak, first, last = longest_streak(days)
    busiest = min(days.items(), key=lambda kv: (-kv[1], kv[0])) if days else None
    longest = max(sessions, key=lambda s: active_seconds(s.events), default=None)
    return {
        "basis": "prompts" if prompts else "events",
        "active_days": len(days),
        "streak": {"days": streak, "start": first.isoformat() if first else None,
                   "end": last.isoformat() if last else None},
        "busiest_day": {"date": busiest[0].isoformat(), "prompts": busiest[1]} if busiest else None,
        "busiest_hour": max(range(24), key=lambda h: (hours[h], -h)) if stamps else None,
        "hours": hours,
        "weekdays": weekdays,
        "night_share": sum(hours[h] for h in NIGHT_HOURS) / counted,
        "early_share": sum(hours[h] for h in EARLY_HOURS) / counted,
        "weekend_share": (weekdays[5] + weekdays[6]) / counted,
        "hours_with_agents": round(active_seconds(events) / 3600, 1),
        "agent_hours": round(sum(active_seconds(s.events) for s in sessions) / 3600, 1),
        "longest_session": {"hours": round(active_seconds(longest.events) / 3600, 1),
                            "agent": SOURCE_LABELS.get(longest.source, longest.source)} if longest else None,
    }


def _projects(sessions: List[Session]) -> List[dict]:
    session_count: Counter = Counter()
    prompt_count: Counter = Counter()
    for s in sessions:
        name = s.project or "(unknown)"
        session_count[name] += 1
        prompt_count[name] += len(s.prompts)
    ordered = sorted(session_count, key=lambda n: (-prompt_count[n], -session_count[n], n))[:10]
    return [{"name": n, "sessions": session_count[n], "prompts": prompt_count[n]} for n in ordered]


def _notes(sessions: List[Session]) -> List[str]:
    notes = []
    if any(s.partial_tokens for s in sessions):
        notes.append("Cursor stores token counts for only some messages, so its token total is a lower bound.")
    if any(s.cost_usd for s in sessions):
        notes.append("Cost is the API-equivalent amount the agents recorded; subscription plans bill differently.")
    return notes
