"""Shared plumbing for the parsers: a process pool for many log files, read-only SQLite for databases."""
from __future__ import annotations

import shutil
import sqlite3
import tempfile
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator, List, Optional, Sequence

from .model import Session, Window

MIN_PARALLEL = 32  # below this many files, starting worker processes costs more than it saves
LOCK_WAIT = 1.0  # seconds to wait on a database another app is writing before reading a copy

FileParser = Callable[[str, float, float], Optional[Session]]


def map_files(parse_file: FileParser, paths: Sequence[Path], window: Window, jobs: int,
              min_parallel: int = MIN_PARALLEL) -> List[Session]:
    """Run parse_file(path, start, end) over every file; it must be a module-level function."""
    names = [str(p) for p in paths]
    starts, ends = [window.start] * len(names), [window.end] * len(names)
    results = None
    if jobs > 1 and len(names) >= min_parallel:
        try:
            with ProcessPoolExecutor(max_workers=jobs) as pool:
                results = list(pool.map(parse_file, names, starts, ends, chunksize=8))
        except (OSError, NotImplementedError, BrokenProcessPool):
            results = None  # sandboxes without working process pools: fall through to a serial scan
    if results is None:
        results = [parse_file(n, s, e) for n, s, e in zip(names, starts, ends)]
    return [s for s in results if s is not None]


@contextmanager
def readonly(path: Path) -> Iterator[sqlite3.Connection]:
    """Open an agent's database without ever writing to it.

    A running app can hold a lock that makes even a read-only open fail; then a private copy of the
    database (and its write-ahead log) is read instead.
    """
    con = None
    tmp = None
    try:
        try:
            con = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True, timeout=LOCK_WAIT)
            con.execute("SELECT count(*) FROM sqlite_master").fetchone()
        except sqlite3.OperationalError:
            if con is not None:
                con.close()
            tmp = tempfile.mkdtemp(prefix="agent-wrapped-")
            copy = Path(tmp) / Path(path).name
            for suffix in ("", "-wal", "-shm"):
                source = Path(str(path) + suffix)
                if source.exists():
                    shutil.copy2(source, str(copy) + suffix)
            con = sqlite3.connect(copy.as_uri() + "?mode=ro", uri=True, timeout=LOCK_WAIT)
        yield con
    finally:
        if con is not None:
            con.close()
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


def columns(con: sqlite3.Connection, table: str) -> List[str]:
    return [row[1] for row in con.execute(f"PRAGMA table_info('{table}')")]
