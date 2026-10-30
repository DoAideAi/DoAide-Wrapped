"""A persona badge and one roast line, picked by fixed rules from the year's numbers.

No model call and no network: the same logs always give the same badge and the same line.
"""
from __future__ import annotations

from .fmt import compact, day_label, grouped, percent

MIN_PROMPTS = 30  # ratio badges need enough prompts to mean something
WAR_AND_PEACE_TOKENS = 760_000  # about 587K words at roughly 1.3 tokens per word


def _per_prompt(stats: dict, value: float) -> float:
    return value / max(stats["totals"]["prompts"], 1)


def _shell_share(stats: dict) -> float:
    calls = stats["totals"]["tool_calls"]
    return stats["totals"]["shell"] / calls if calls >= 50 else 0.0


# name, tagline, metric, threshold, cap on strength, why, needs MIN_PROMPTS
# Strength is metric / threshold; caps keep raw volume (tokens, agents) from drowning out habits.
BADGES = (
    ("The Night Owl", "Your best work happens after 10pm.",
     lambda s: s["time"]["night_share"], 0.30, 2.0, lambda v: f"{percent(v)} of prompts after 10pm", True),
    ("The Early Bird", "You and your agent beat the sunrise.",
     lambda s: s["time"]["early_share"], 0.25, 2.0, lambda v: f"{percent(v)} of prompts before 9am", True),
    ("The Weekend Warrior", "Saturdays are for shipping.",
     lambda s: s["time"]["weekend_share"], 0.35, 2.0, lambda v: f"{percent(v)} of prompts on weekends", True),
    ("The Interrupter", "You know what you want, and it isn't that.",
     lambda s: 100 * _per_prompt(s, s["totals"]["interrupts"]), 8, 2.0,
     lambda v: f"{v:.0f} interrupts per 100 prompts", True),
    ("The Impatient One", "The next message is typed before the reply lands.",
     lambda s: 100 * _per_prompt(s, s["totals"]["queued"]), 15, 2.0,
     lambda v: f"{v:.0f} queued messages per 100 prompts", True),
    ("The Shell Whisperer", "Your agent lives in the terminal.",
     _shell_share, 0.65, 1.4, lambda v: f"{percent(v)} of tool calls ran in a shell", True),
    ("The Delegator", "One prompt, a hundred tool calls.",
     lambda s: _per_prompt(s, s["totals"]["tool_calls"]), 25, 2.0, lambda v: f"{v:.0f} tool calls per prompt", True),
    ("The Marathoner", "Streaks are a lifestyle.",
     lambda s: s["time"]["streak"]["days"], 30, 2.0, lambda v: f"a {v:.0f}-day streak", False),
    ("The Polyglot", "Why pick one agent when you can have them all?",
     lambda s: len(s["agents"]), 3, 1.5, lambda v: f"{v:.0f} different agents", False),
    ("The Token Tycoon", "Context windows fear you.",
     lambda s: s["totals"]["tokens"]["total"], 1e9, 1.0, lambda v: f"{compact(v)} tokens", False),
)


def pick_persona(stats: dict) -> dict:
    enough = stats["totals"]["prompts"] >= MIN_PROMPTS
    best = None
    for name, tagline, metric, threshold, cap, why, needs_prompts in BADGES:
        if needs_prompts and not enough:
            continue
        value = metric(stats)
        strength = min(value / threshold, cap)
        if strength >= 1 and (best is None or strength > best[0]):
            best = (strength, name, tagline, why(value))
    if best is None:
        t = stats["totals"]
        return {"name": "The Builder", "tagline": "Steady prompts, real work.",
                "why": f"{grouped(t['prompts'])} prompts across {grouped(t['sessions'])} sessions"}
    return {"name": best[1], "tagline": best[2], "why": best[3]}


def pick_roast(stats: dict) -> str:
    t, tm = stats["totals"], stats["time"]
    output = t["tokens"]["output"]
    books = output / WAR_AND_PEACE_TOKENS
    busiest = tm.get("busiest_day") or {}
    agreed = t["absolutely_right"]
    candidates = [
        (agreed >= 10, agreed / 40,
         f'Your agent told you "You\'re absolutely right" {grouped(agreed)} times. You were not always right.'),
        (t["interrupts"] >= 25, t["interrupts"] / 150,
         f"You interrupted your agent {grouped(t['interrupts'])} times. It never once interrupted you."),
        (t["queued"] >= 25, t["queued"] / 150,
         f"You queued {grouped(t['queued'])} messages while your agent was still on the last one."),
        (t["compactions"] >= 10, t["compactions"] / 60,
         f"You filled the context window {grouped(t['compactions'])} times and kept going."),
        (tm["night_share"] >= 0.25 and t["prompts"] >= 50, tm["night_share"] / 0.25,
         f"{percent(tm['night_share'])} of your prompts went out after 10pm. Your agent doesn't sleep. "
         "Apparently, neither do you."),
        (busiest.get("prompts", 0) >= 100, busiest.get("prompts", 0) / 200,
         f"On {day_label(busiest['date'])} you sent {grouped(busiest['prompts'])} prompts. Everything OK?"
         if busiest else ""),
        (books >= 10, books / 100,
         f"Your agents wrote {compact(output)} tokens. That's about {grouped(books)} copies of War and Peace."),
    ]
    live = [(score, line) for ok, score, line in candidates if ok]
    if not live:
        return (f"{grouped(t['prompts'])} prompts in, {compact(t['tokens']['total'])} tokens through. "
                "Just getting started.")
    return max(live, key=lambda item: item[0])[1]
