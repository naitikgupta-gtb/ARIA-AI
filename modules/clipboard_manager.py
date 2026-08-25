"""
modules/clipboard_manager.py — Clipboard History.

A background thread polls the OS clipboard every couple of seconds and,
whenever it changes, stores the new value in the same SQLite DB memory.py
uses. Gives ARIA (and the user) a scrollable clipboard history instead
of only ever having the single most recent copy.
"""
import threading
import time

from modules import memory

POLL_SECONDS = 2.0
_stop_flag = threading.Event()
_last_value = None


def _ensure_table():
    conn, lock = memory.raw_connection()
    with lock:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS clipboard_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                content TEXT NOT NULL
            )
        """)
        conn.commit()


def _poll_loop():
    global _last_value
    try:
        import pyperclip
    except ImportError:
        return  # clipboard history simply won't populate without pyperclip

    _ensure_table()
    conn, lock = memory.raw_connection()

    while not _stop_flag.is_set():
        try:
            current = pyperclip.paste()
        except Exception:
            current = None
        if current and current != _last_value:
            _last_value = current
            with lock:
                conn.execute(
                    "INSERT INTO clipboard_history (ts, content) VALUES (?, ?)",
                    (time.time(), current[:5000]),
                )
                conn.commit()
        time.sleep(POLL_SECONDS)


def start_background_watch():
    """Call once at app startup. Safe to call more than once — only
    starts a single watcher thread."""
    if not _stop_flag.is_set() and getattr(start_background_watch, "_started", False):
        return
    start_background_watch._started = True
    t = threading.Thread(target=_poll_loop, daemon=True)
    t.start()


def get_history(limit: int = 20) -> str:
    _ensure_table()
    conn, lock = memory.raw_connection()
    with lock:
        rows = conn.execute(
            "SELECT ts, content FROM clipboard_history ORDER BY ts DESC LIMIT ?", (limit,)
        ).fetchall()
    if not rows:
        return "Clipboard history is empty so far."
    lines = []
    for i, (ts, content) in enumerate(rows):
        when = time.strftime("%H:%M:%S", time.localtime(ts))
        preview = content.replace("\n", " ")[:80]
        lines.append(f"[{i}] {when} — {preview}")
    return "\n".join(lines)


def restore_index(index: int) -> str:
    _ensure_table()
    conn, lock = memory.raw_connection()
    with lock:
        rows = conn.execute(
            "SELECT content FROM clipboard_history ORDER BY ts DESC LIMIT ?", (index + 1,)
        ).fetchall()
    if index < 0 or index >= len(rows):
        return f"❌ No clipboard history entry at index {index}"
    content = rows[index][0]
    try:
        import pyperclip
        pyperclip.copy(content)
        return f"✅ Restored clipboard entry [{index}] to clipboard"
    except ImportError:
        return "⚠️ Install pyperclip: pip install pyperclip"
