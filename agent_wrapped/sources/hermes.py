"""Hermes Agent: state.db under $HERMES_HOME (default ~/.hermes), plus each profile's state.db.

Sessions carry token and cost totals; messages carry timestamps, roles and tool names. Prompts in
delegated (child) sessions and in cron or programmatic runs were not typed by a person, so they
count as usage but not as prompts.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict, List, Mapping, Tuple

from ..model import Session, Window, add_tokens, number, parse_ts, project_name
from ..scan import columns, readonly

NAME = "hermes"
SESSION_COLUMNS = ("id", "source", "model", "started_at", "cwd", "parent_session_id", "input_tokens",
                   "output_tokens", "cache_read_tokens", "cache_write_tokens", "reasoning_tokens",
                   "estimated_cost_usd", "actual_cost_usd")
NOT_TYPED = {"cron", "tool", "delegate", "subagent", "webhook"}


def locate(home: Path, env: Mapping[str, str]) -> List[Path]:
    bases = [Path(env["HERMES_HOME"]).expanduser()] if env.get("HERMES_HOME") else []
    bases.append(home / ".hermes")
    profiles = home / ".hermes" / "profiles"
    if profiles.is_dir():
        bases.extend(sorted(p for p in profiles.iterdir() if p.is_dir()))
    found: List[Path] = []
    for base in bases:
        db = base / "state.db"
        if db.is_file() and db.resolve() not in [f.resolve() for f in found]:
            found.append(db)
    return found


def parse(paths: List[Path], window: Window, jobs: int = 1) -> List[Session]:
    sessions: List[Session] = []
    for path in paths:
        try:
            sessions.extend(parse_db(path, window))
        except sqlite3.DatabaseError:
            continue
    return sessions


def parse_db(path: Path, window: Window) -> List[Session]:
    with readonly(path) as con:
        present = [c for c in SESSION_COLUMNS if c in columns(con, "sessions")]
        if "id" not in present:
            return []
        sessions = _sessions(con, present, window)
        if "session_id" in columns(con, "messages"):
            _messages(con, sessions, window)
    for session, _, _ in sessions.values():
        session.prompts.sort()
        session.events.sort()
    return [s for s, _, _ in sessions.values() if s.events or s.tokens["total"]]


def _sessions(con: sqlite3.Connection, present: List[str], window: Window) -> Dict[str, Tuple[Session, str, bool]]:
    sessions: Dict[str, Tuple[Session, str, bool]] = {}
    for row in con.execute(f"SELECT {', '.join(present)} FROM sessions"):
        r = dict(zip(present, row))
        session = Session(NAME, str(r["id"]), project=project_name(r.get("cwd")))
        if window.has(parse_ts(r.get("started_at"))):
            add_tokens(
                session.tokens,
                input=number(r.get("input_tokens")),
                output=number(r.get("output_tokens")),
                cache_read=number(r.get("cache_read_tokens")),
                cache_write=number(r.get("cache_write_tokens")),
                reasoning=number(r.get("reasoning_tokens")),
            )
            session.cost_usd = float(r.get("actual_cost_usd") or r.get("estimated_cost_usd") or 0)
        typed = not r.get("parent_session_id") and (r.get("source") or "") not in NOT_TYPED
        sessions[session.id] = (session, r.get("model") or "unknown", typed)
    return sessions


def _messages(con: sqlite3.Connection, sessions: Dict[str, Tuple[Session, str, bool]], window: Window) -> None:
    tool_column = "tool_name" if "tool_name" in columns(con, "messages") else "NULL"
    query = f"SELECT session_id, role, timestamp, {tool_column} FROM messages WHERE role IN ('user', 'assistant', 'tool')"
    for session_id, role, raw_ts, tool in con.execute(query):
        entry = sessions.get(str(session_id))
        ts = parse_ts(raw_ts)
        if entry is None or not window.has(ts):
            continue
        session, model, typed = entry
        if role == "user" and typed:
            session.prompts.append(ts)
            session.events.append(ts)
        elif role == "assistant":
            session.assistant_messages += 1
            session.models[model] += 1
            session.events.append(ts)
        elif role == "tool" and tool:
            session.tools[tool] += 1
