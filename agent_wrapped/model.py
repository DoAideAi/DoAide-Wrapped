"""The normalized session every source parser produces, and the helpers they share.

A Session holds counts and timestamps only. Parsers read prompt text just far enough to tell a
human prompt from a tool result, an interrupt or a slash command; no text is ever stored.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

TOKEN_KINDS = ("input", "output", "cache_read", "cache_write")


@dataclass(frozen=True)
class Window:
    """The time range being wrapped: [start, end) in epoch seconds."""

    start: float
    end: float

    def has(self, ts: Optional[float]) -> bool:
        return ts is not None and self.start <= ts < self.end


ALL_TIME = Window(0.0, float("inf"))


def year_window(year: int, tz=None) -> Window:
    """Calendar year `year` in `tz`, or in the machine's local time when tz is None."""
    first = datetime(year, 1, 1, tzinfo=tz).timestamp()
    return Window(first, datetime(year + 1, 1, 1, tzinfo=tz).timestamp())


@dataclass
class Session:
    source: str
    id: str
    project: str = ""
    prompts: List[float] = field(default_factory=list)  # when a human sent a prompt
    events: List[float] = field(default_factory=list)  # prompts and replies, for active time
    assistant_messages: int = 0
    models: Counter = field(default_factory=Counter)  # model -> assistant messages
    tools: Counter = field(default_factory=Counter)  # tool name -> calls
    tokens: Counter = field(default_factory=Counter)  # TOKEN_KINDS, "reasoning" and "total"
    cost_usd: float = 0.0  # only what the agent itself recorded
    lines_added: int = 0
    lines_removed: int = 0
    interrupts: int = 0
    compactions: int = 0
    queued: int = 0
    absolutely_right: int = 0
    api_errors: int = 0
    partial_tokens: bool = False  # the agent stores token counts for some messages only


def add_tokens(tokens: Counter, input=0, output=0, cache_read=0, cache_write=0, reasoning=0, total=None) -> None:
    """Add one usage record. Reasoning tokens are part of output, so they never add to the total."""
    kinds = {"input": input, "output": output, "cache_read": cache_read, "cache_write": cache_write}
    for kind, value in kinds.items():
        tokens[kind] += value
    tokens["reasoning"] += reasoning
    tokens["total"] += sum(kinds.values()) if total is None else total


def number(value) -> int:
    """A count from a log field: ints and floats count, anything else (None, text, bools) is 0."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    return int(value)


def project_name(cwd) -> str:
    """The last path component of a working directory, for the optional --show-projects list."""
    if not isinstance(cwd, str) or not cwd.strip():
        return ""
    return re.split(r"[\\/]", cwd.strip().rstrip("/\\"))[-1] or cwd.strip()


_ISO = re.compile(r"^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})(?:\.(\d+))?\s*(Z|[+-]\d{2}:?\d{2})?$", re.I)


def parse_ts(value) -> Optional[float]:
    """Epoch seconds from ISO-8601 text, epoch seconds or epoch milliseconds; None if unreadable.

    Python 3.9's fromisoformat rejects a trailing Z and fractions that are not 3 or 6 digits long,
    so the text is normalized first. Text without a zone is read as UTC, which is what agents write.
    """
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        seconds = float(value)
        return seconds / 1000.0 if seconds > 1e11 else seconds
    if not isinstance(value, str):
        return None
    match = _ISO.match(value.strip())
    if not match:
        return None
    day, clock, fraction, zone = match.groups()
    fraction = (fraction or "0")[:6].ljust(6, "0")
    if zone is None or zone.upper() == "Z":
        zone = "+00:00"
    elif ":" not in zone:
        zone = zone[:3] + ":" + zone[3:]
    try:
        return datetime.fromisoformat(f"{day}T{clock}.{fraction}{zone}").timestamp()
    except ValueError:
        return None
