"""Cursor: the global state.vscdb SQLite database (composer sessions and their message bubbles).

Facts this parser relies on, checked against a real database:
* `composerData:<id>` rows hold a session: createdAt (epoch ms), modelConfig.modelName and
  totalLinesAdded / totalLinesRemoved;
* `bubbleId:<composer>:<bubble>` rows hold messages: type 1 is the user, type 2 the agent,
  createdAt is ISO text (sometimes missing), modelInfo.modelName ('default' means Auto);
* tokenCount is filled in for only a few bubbles, so Cursor's token total is a lower bound.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Tuple

from ..model import Session, Window, add_tokens, number, parse_ts
from ..scan import readonly

NAME = "cursor"
BUBBLES_SQL = (
    "SELECT key, json_extract(CAST(value AS TEXT), '$.type'), json_extract(CAST(value AS TEXT), '$.createdAt'), "
    "json_extract(CAST(value AS TEXT), '$.tokenCount.inputTokens'), "
    "json_extract(CAST(value AS TEXT), '$.tokenCount.outputTokens'), "
    "json_extract(CAST(value AS TEXT), '$.modelInfo.modelName') "
    "FROM cursorDiskKV WHERE key LIKE 'bubbleId:%' AND json_valid(CAST(value AS TEXT))"
)

Composer = Tuple[Session, Optional[float], Optional[str]]  # session, created, model


def db_paths(home: Path) -> List[Path]:
    tail = Path("Cursor") / "User" / "globalStorage" / "state.vscdb"
    return [
        home / "Library" / "Application Support" / tail,  # macOS
        home / ".config" / tail,  # Linux
        home / "AppData" / "Roaming" / tail,  # Windows
    ]


def locate(home: Path, env: Mapping[str, str]) -> List[Path]:
    return [path for path in db_paths(home) if path.is_file()]


def parse(paths: List[Path], window: Window, jobs: int = 1) -> List[Session]:
    sessions: List[Session] = []
    for path in paths:
        try:
            sessions.extend(parse_db(path, window))
        except sqlite3.DatabaseError:
            continue  # not a database we understand (or not one at all)
    return sessions


def parse_db(path: Path, window: Window, use_json1: bool = True) -> List[Session]:
    with readonly(path) as con:
        if "cursorDiskKV" not in {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}:
            return []
        composers = _composers(con, window)
        for key, kind, created, tokens_in, tokens_out, model in _bubbles(con, use_json1):
            _add_bubble(composers, window, key, kind, created, tokens_in, tokens_out, model)
    sessions = [entry[0] for entry in composers.values() if entry[0].events]
    for session in sessions:
        session.prompts.sort()
        session.events.sort()
    return sessions


def _json(raw):
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


def _composers(con: sqlite3.Connection, window: Window) -> Dict[str, Composer]:
    composers: Dict[str, Composer] = {}
    for key, raw in con.execute("SELECT key, value FROM cursorDiskKV WHERE key LIKE 'composerData:%'"):
        data = _json(raw)
        if not isinstance(data, dict):
            continue
        cid = key.split(":", 1)[1]
        created = parse_ts(data.get("createdAt"))
        config = data.get("modelConfig") if isinstance(data.get("modelConfig"), dict) else {}
        session = Session(NAME, cid, partial_tokens=True)
        if window.has(created):
            session.lines_added = number(data.get("totalLinesAdded"))
            session.lines_removed = number(data.get("totalLinesRemoved"))
        composers[cid] = (session, created, config.get("modelName"))
    return composers


def _bubbles(con: sqlite3.Connection, use_json1: bool) -> Iterable[tuple]:
    if use_json1:
        try:
            return con.execute(BUBBLES_SQL).fetchall()
        except sqlite3.OperationalError:
            pass  # SQLite built without JSON functions: parse in Python instead
    rows = []
    for key, raw in con.execute("SELECT key, value FROM cursorDiskKV WHERE key LIKE 'bubbleId:%'"):
        data = _json(raw)
        if isinstance(data, dict):
            tokens = data.get("tokenCount") if isinstance(data.get("tokenCount"), dict) else {}
            info = data.get("modelInfo") if isinstance(data.get("modelInfo"), dict) else {}
            rows.append((key, data.get("type"), data.get("createdAt"), tokens.get("inputTokens"),
                         tokens.get("outputTokens"), info.get("modelName")))
    return rows


def _add_bubble(composers: Dict[str, Composer], window: Window, key, kind, created, tokens_in, tokens_out,
                model) -> None:
    parts = (key or "").split(":")
    if len(parts) < 3:
        return
    entry = composers.setdefault(parts[1], (Session(NAME, parts[1], partial_tokens=True), None, None))
    session, composer_created, composer_model = entry
    ts = parse_ts(created) or composer_created
    if not window.has(ts):
        return
    if kind == 1:
        session.prompts.append(ts)
        session.events.append(ts)
    elif kind == 2:
        session.assistant_messages += 1
        session.events.append(ts)
        named = model if model and model != "default" else composer_model or model or "default"
        session.models[named] += 1
    if number(tokens_in) or number(tokens_out):
        add_tokens(session.tokens, input=number(tokens_in), output=number(tokens_out))
