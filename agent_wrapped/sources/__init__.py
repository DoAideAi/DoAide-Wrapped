"""The agents Agent Wrapped can read. Each module exposes locate(home, env) and parse(paths, window, jobs)."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Mapping, Sequence

from ..model import Session, Window
from . import claude_code, codex, cursor, hermes

SOURCES = {
    claude_code.NAME: claude_code,
    codex.NAME: codex,
    cursor.NAME: cursor,
    hermes.NAME: hermes,
}


def locate_all(names: Sequence[str], home: Path, env: Mapping[str, str]) -> Dict[str, List[Path]]:
    return {name: SOURCES[name].locate(home, env) for name in names}


def collect(found: Dict[str, List[Path]], window: Window, jobs: int = 1) -> Dict[str, List[Session]]:
    return {name: SOURCES[name].parse(paths, window, jobs) if paths else [] for name, paths in found.items()}
