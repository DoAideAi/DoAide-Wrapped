"""Codex CLI: one rollout JSONL per session under $CODEX_HOME/sessions/YYYY/MM/DD/ (default ~/.codex).

Facts this parser relies on, checked against real rollouts:
* newer rollouts write a `token_usage_record` per model response (counted once per response_id);
  older ones only have cumulative `token_count` events, so the last one is the session total;
* OpenAI's input_tokens include cached input, so uncached input = input - cached - cache writes;
* a prompt is a `user_message` event in older rollouts; newer ones only record it as a user-role
  `response_item` message (text that starts with "<" is injected context, not typed). `task_started`
  is not a prompt: one automated Codex Desktop thread logged 3,718 turns for 17 user messages;
* `turn_aborted` is the user pressing Esc; `codex exec` runs (source "exec") and forked or
  sub-agent threads were started by a program or another agent, so their prompts don't count.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Tuple

from ..model import Session, Window, add_tokens, number, parse_ts, project_name
from ..scan import map_files

NAME = "codex"
TOOL_ITEMS = {"function_call", "custom_tool_call", "local_shell_call", "web_search_call", "tool_search_call"}


def locate(home: Path, env: Mapping[str, str]) -> List[Path]:
    base = Path(env["CODEX_HOME"]).expanduser() if env.get("CODEX_HOME") else home / ".codex"
    files: List[Path] = []
    for sub in ("sessions", "archived_sessions"):
        if (base / sub).is_dir():
            files.extend(sorted((base / sub).rglob("*.jsonl")))
    return files


def parse(paths: List[Path], window: Window, jobs: int = 1) -> List[Session]:
    return map_files(parse_file, paths, window, jobs)


def parse_file(path: str, start: float, end: float) -> Optional[Session]:
    state = _Rollout(path, Window(start, end))
    try:
        with open(path, "rb") as fh:
            for raw in fh:
                state.feed(raw)
    except OSError:
        return None
    return state.finish()


def add_usage(tokens, usage: dict) -> None:
    given = number(usage.get("input_tokens"))
    cached = number(usage.get("cached_input_tokens"))
    written = number(usage.get("cache_write_input_tokens"))
    output = number(usage.get("output_tokens"))
    add_tokens(
        tokens,
        input=max(given - cached - written, 0),
        output=output,
        cache_read=cached,
        cache_write=written,
        reasoning=number(usage.get("reasoning_output_tokens")),
        total=number(usage.get("total_tokens")) or given + output,
    )


class _Rollout:
    def __init__(self, path: str, window: Window):
        self.window = window
        self.session = Session(NAME, Path(path).stem)
        self.model = "unknown"
        self.typed = True  # False for `codex exec` runs and threads another agent started
        self.user_messages: List[Optional[float]] = []  # older rollouts: user_message events
        self.user_items: List[Optional[float]] = []  # newer rollouts: user-role response items
        self.records: Dict[str, dict] = {}  # response_id -> usage, in-window only
        self.last_total: Optional[Tuple[Optional[float], dict]] = None

    def feed(self, raw: bytes) -> None:
        try:
            event = json.loads(raw)
        except ValueError:
            return
        if not isinstance(event, dict):
            return
        handler = _HANDLERS.get(event.get("type"))
        if handler:
            payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
            handler(self, payload, parse_ts(event.get("timestamp")))

    def finish(self) -> Optional[Session]:
        s = self.session
        typed = (self.user_messages or self.user_items) if self.typed else []
        prompts = [ts for ts in typed if self.window.has(ts)]
        s.prompts = sorted(prompts)
        s.events = sorted(s.events + prompts)
        if self.records:
            for usage in self.records.values():
                add_usage(s.tokens, usage)
        elif self.last_total and self.window.has(self.last_total[0]):
            add_usage(s.tokens, self.last_total[1])
        if not s.events and not s.tokens["total"]:
            return None
        return s


def _meta(state: _Rollout, payload: dict, ts: Optional[float]) -> None:
    if payload.get("id"):
        state.session.id = str(payload["id"])
    state.session.project = state.session.project or project_name(payload.get("cwd"))
    if payload.get("source") == "exec" or payload.get("parent_thread_id") or payload.get("forked_from_id"):
        state.typed = False


def _turn_context(state: _Rollout, payload: dict, ts: Optional[float]) -> None:
    state.model = payload.get("model") or state.model
    state.session.project = state.session.project or project_name(payload.get("cwd"))


def _event(state: _Rollout, payload: dict, ts: Optional[float]) -> None:
    kind = payload.get("type")
    if kind == "user_message":
        state.user_messages.append(ts)
    elif kind == "turn_aborted" and state.window.has(ts):
        state.session.interrupts += 1
    elif kind == "token_count":
        info = payload.get("info")
        if isinstance(info, dict) and isinstance(info.get("total_token_usage"), dict):
            state.last_total = (ts, info["total_token_usage"])


def _typed_text(payload: dict) -> str:
    content = payload.get("content")
    parts = [b["text"] for b in content if isinstance(b, dict) and isinstance(b.get("text"), str)] \
        if isinstance(content, list) else []
    return "".join(parts).lstrip()


def _item(state: _Rollout, payload: dict, ts: Optional[float]) -> None:
    kind = payload.get("type")
    s = state.session
    if kind == "message" and payload.get("role") == "user":
        text = _typed_text(payload)
        if text and not text.startswith("<"):
            state.user_items.append(ts)
    elif not state.window.has(ts):
        return
    elif kind == "message" and payload.get("role") == "assistant":
        s.assistant_messages += 1
        s.models[state.model] += 1
        s.events.append(ts)
    elif kind in TOOL_ITEMS:
        s.tools[payload.get("name") or kind] += 1


def _usage_record(state: _Rollout, payload: dict, ts: Optional[float]) -> None:
    usage = payload.get("usage")
    if state.window.has(ts) and isinstance(usage, dict):
        state.records[str(payload.get("response_id") or len(state.records))] = usage


def _compacted(state: _Rollout, payload: dict, ts: Optional[float]) -> None:
    if state.window.has(ts):
        state.session.compactions += 1


_HANDLERS = {
    "session_meta": _meta,
    "turn_context": _turn_context,
    "event_msg": _event,
    "response_item": _item,
    "token_usage_record": _usage_record,
    "compacted": _compacted,
}
