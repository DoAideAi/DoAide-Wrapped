"""Claude Code: one JSONL file per session under ~/.claude/projects/<project>/.

Also read from $CLAUDE_CONFIG_DIR and ~/.config/claude. Facts this parser relies on, checked
against real logs:
* one reply is written as several lines (one per content block) sharing message.id, each carrying
  the same usage; tokens are counted once per message id, keeping the largest output count;
* `cost-state` lines carry the session's running totalCostUSD and lines added/removed (last wins);
  older versions put costUSD on each assistant line instead;
* human prompts are `user` lines with text content; tool results, isMeta/isCompactSummary lines,
  sidechain (subagent) lines and <command-...>/<task-notification> wrappers are not prompts;
* a message typed while the agent is mid-turn arrives as a `queued_command` attachment with
  commandMode "prompt", never as a user line. Most queued_command attachments are background-task
  notifications or messages from peer agents, which are not prompts. The desktop app's
  `queue-operation` enqueue lines are its normal send path, so they say nothing about impatience.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Tuple

from ..model import Session, Window, add_tokens, number, parse_ts, project_name
from ..scan import map_files

NAME = "claude-code"
# Lines without any of these cannot matter, and skipping them avoids parsing request blobs.
NEEDLES = (b'"assistant"', b'"user"', b'"cost-state"', b'"system"', b'"queued_command"')
INTERRUPT = "[Request interrupted by user"
AGREE = "bsolutely right"  # "You're absolutely right" and "Absolutely right"
DEFAULT_RETENTION_DAYS = 30  # cleanupPeriodDays when settings.json does not set it
KEEP_DAYS = 3650  # what to suggest instead; Claude Code rejects 0


def roots(home: Path, env: Mapping[str, str]) -> List[Path]:
    candidates = [Path(p.strip()).expanduser() for p in env.get("CLAUDE_CONFIG_DIR", "").split(",") if p.strip()]
    candidates += [home / ".claude", home / ".config" / "claude"]
    found: List[Path] = []
    for base in candidates:
        projects = base / "projects"
        if projects.is_dir() and projects.resolve() not in [f.resolve() for f in found]:
            found.append(projects)
    return found


def locate(home: Path, env: Mapping[str, str]) -> List[Path]:
    return [path for root in roots(home, env) for path in sorted(root.rglob("*.jsonl"))]


def retention(home: Path, env: Mapping[str, str]) -> Tuple[int, Path]:
    """Claude Code's transcript retention (cleanupPeriodDays, default 30) and the settings file that sets it."""
    found = roots(home, env)
    default = (found[0].parent if found else home / ".claude") / "settings.json"
    for projects in found:
        path = projects.parent / "settings.json"
        try:
            settings = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        days = settings.get("cleanupPeriodDays") if isinstance(settings, dict) else None
        if isinstance(days, int) and not isinstance(days, bool):
            return days, path
    return DEFAULT_RETENTION_DAYS, default


def parse(paths: List[Path], window: Window, jobs: int = 1) -> List[Session]:
    return map_files(parse_file, paths, window, jobs)


def parse_file(path: str, start: float, end: float) -> Optional[Session]:
    state = _SessionFile(path, Window(start, end))
    try:
        with open(path, "rb") as fh:
            for raw in fh:
                if any(needle in raw for needle in NEEDLES):
                    state.feed(raw)
    except OSError:
        return None
    return state.finish()


class _SessionFile:
    def __init__(self, path: str, window: Window):
        self.window = window
        self.session = Session(NAME, Path(path).stem)
        self.usage: Dict[str, dict] = {}  # message id -> usage with the largest output seen
        self.line_cost: Dict[str, float] = {}  # message id -> legacy per-line costUSD
        self.tool_ids: set = set()
        self.agree_ids: set = set()
        self.cost_state: Optional[dict] = None

    def feed(self, raw: bytes) -> None:
        try:
            event = json.loads(raw)
        except ValueError:
            return
        if isinstance(event, dict):
            handler = _HANDLERS.get(event.get("type"))
            if handler:
                handler(self, event)

    def when(self, event: dict) -> Optional[float]:
        ts = parse_ts(event.get("timestamp"))
        return ts if self.window.has(ts) else None

    def note_project(self, event: dict) -> None:
        if not self.session.project:
            self.session.project = project_name(event.get("cwd"))

    def finish(self) -> Optional[Session]:
        s = self.session
        if not s.events:
            return None
        for usage in self.usage.values():
            add_tokens(
                s.tokens,
                input=number(usage.get("input_tokens")),
                output=number(usage.get("output_tokens")),
                cache_read=number(usage.get("cache_read_input_tokens")),
                cache_write=number(usage.get("cache_creation_input_tokens")),
            )
        if self.cost_state:
            # cost-state has no timestamp: a session that crosses the window edge counts in full.
            s.cost_usd = float(self.cost_state.get("totalCostUSD") or 0)
            s.lines_added = number(self.cost_state.get("totalLinesAdded"))
            s.lines_removed = number(self.cost_state.get("totalLinesRemoved"))
        else:
            s.cost_usd = sum(self.line_cost.values())
        s.prompts.sort()
        s.events.sort()
        return s


def _assistant(state: _SessionFile, event: dict) -> None:
    message = event.get("message")
    if not isinstance(message, dict):
        return
    model = message.get("model")
    ts = state.when(event)
    if not model or model == "<synthetic>" or ts is None:
        return
    s = state.session
    state.note_project(event)
    mid = message.get("id") or event.get("requestId") or event.get("uuid") or f"line-{len(state.usage)}"
    usage = message.get("usage") if isinstance(message.get("usage"), dict) else {}
    seen = state.usage.get(mid)
    if seen is None:
        state.usage[mid] = usage
        s.assistant_messages += 1
        s.models[model] += 1
        s.events.append(ts)
    elif number(usage.get("output_tokens")) > number(seen.get("output_tokens")):
        state.usage[mid] = usage
    if isinstance(event.get("costUSD"), (int, float)):
        state.line_cost[mid] = float(event["costUSD"])
    for block in message.get("content") or []:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "tool_use":
            key = block.get("id") or f"{mid}:{len(state.tool_ids)}"
            if key not in state.tool_ids:
                state.tool_ids.add(key)
                s.tools[block.get("name") or "unknown"] += 1
        elif block.get("type") == "text" and AGREE in (block.get("text") or "") and mid not in state.agree_ids:
            state.agree_ids.add(mid)
            s.absolutely_right += 1


def _texts(message: dict):
    """(text parts, whether the message carries a tool result)."""
    content = message.get("content")
    if isinstance(content, str):
        return [content], False
    texts, tool_result = [], False
    for block in content if isinstance(content, list) else []:
        if isinstance(block, dict):
            if block.get("type") == "text":
                texts.append(block.get("text") or "")
            elif block.get("type") == "tool_result":
                tool_result = True
    return texts, tool_result


def _user(state: _SessionFile, event: dict) -> None:
    ts = state.when(event)
    message = event.get("message")
    if ts is None or not isinstance(message, dict):
        return
    if event.get("isMeta") or event.get("isCompactSummary") or event.get("isSidechain"):
        return
    texts, tool_result = _texts(message)
    s = state.session
    if any(text.lstrip().startswith(INTERRUPT) for text in texts):
        s.interrupts += 1
        return
    joined = "\n".join(texts).lstrip()
    if tool_result or not joined or joined.startswith("<"):
        return
    state.note_project(event)
    s.prompts.append(ts)
    s.events.append(ts)


def _system(state: _SessionFile, event: dict) -> None:
    if state.when(event) is None:
        return
    if event.get("subtype") == "compact_boundary":
        state.session.compactions += 1
    elif event.get("subtype") == "api_error":
        state.session.api_errors += 1


def _attachment(state: _SessionFile, event: dict) -> None:
    """A prompt typed while the agent was still working (not a task notification or peer message)."""
    queued = event.get("attachment")
    if not isinstance(queued, dict) or queued.get("type") != "queued_command":
        return
    origin = queued.get("origin") if isinstance(queued.get("origin"), dict) else {}
    text = queued.get("prompt") if isinstance(queued.get("prompt"), str) else ""
    if (queued.get("isMeta") or event.get("isSidechain") or queued.get("commandMode") not in (None, "prompt")
            or origin.get("kind") not in (None, "human") or not text.strip() or text.lstrip().startswith("<")):
        return
    ts = state.when(event)
    if ts is None:
        return
    state.note_project(event)
    state.session.prompts.append(ts)
    state.session.events.append(ts)
    state.session.queued += 1


def _cost(state: _SessionFile, event: dict) -> None:
    state.cost_state = event


_HANDLERS = {
    "assistant": _assistant,
    "user": _user,
    "system": _system,
    "attachment": _attachment,
    "cost-state": _cost,
}
