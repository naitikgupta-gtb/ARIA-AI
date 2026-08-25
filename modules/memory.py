"""
modules/memory.py — Persistent Stored Memory (Search Timeline).

A local SQLite database at ~/.aria/aria_memory.db that logs every tool
call and search ARIA makes, with a timestamp, so future sessions can
recall what happened before. This is the single shared store other
modules (clipboard, reminders) also use their own tables in — one file,
one connection helper, several tables.
"""
import json
import sqlite3
import threading
import time
from pathlib import Path

DB_PATH = Path.home() / ".aria" / "aria_memory.db"
_lock = threading.Lock()


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS timeline (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            kind TEXT NOT NULL,          -- 'tool_call' | 'search' | 'note'
            name TEXT,                   -- tool name / search query label
            args_json TEXT,
            result_summary TEXT
        )
    """)
    conn.commit()
    return conn


_conn = _connect()


def log_event(kind: str, name: str, args: dict | None = None, result_summary: str = "") -> None:
    with _lock:
        _conn.execute(
            "INSERT INTO timeline (ts, kind, name, args_json, result_summary) VALUES (?,?,?,?,?)",
            (time.time(), kind, name, json.dumps(args or {}), (result_summary or "")[:500]),
        )
        _conn.commit()


def recall(query: str = "", limit: int = 10) -> str:
    """Free-text search over past events — matches against name and
    result_summary. Empty query just returns the most recent events."""
    with _lock:
        if query:
            like = f"%{query}%"
            rows = _conn.execute(
                "SELECT ts, kind, name, result_summary FROM timeline "
                "WHERE name LIKE ? OR result_summary LIKE ? "
                "ORDER BY ts DESC LIMIT ?",
                (like, like, limit),
            ).fetchall()
        else:
            rows = _conn.execute(
                "SELECT ts, kind, name, result_summary FROM timeline ORDER BY ts DESC LIMIT ?",
                (limit,),
            ).fetchall()

    if not rows:
        return "No matching memory found." if query else "Memory is empty so far."

    lines = []
    for ts, kind, name, summary in rows:
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
        lines.append(f"[{when}] ({kind}) {name} — {summary}")
    return "\n".join(lines)


def raw_connection():
    """For other modules (clipboard, reminders) that want their own
    tables in the same DB file instead of a second SQLite file."""
    return _conn, _lock
