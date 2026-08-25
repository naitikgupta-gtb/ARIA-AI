"""
modules/reminders.py — Voice Reminders / Alarms.

Stores reminders in the same SQLite DB memory.py uses, and runs a
background thread that checks every 20 seconds for any reminder whose
time has passed and hasn't fired yet, then calls back into the emit
function so the HUD can show a notification + ARIA can speak it.
"""
import threading
import time
from datetime import datetime, timedelta

from modules import memory

CHECK_SECONDS = 20
_stop_flag = threading.Event()
_emit_fn = None  # set by start_background_scheduler


def _ensure_table():
    conn, lock = memory.raw_connection()
    with lock:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                due_ts REAL NOT NULL,
                message TEXT NOT NULL,
                fired INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.commit()


def add_reminder(message: str, at: str = "", in_minutes: float = 0) -> str:
    """Either `at` = 'HH:MM' 24-hour today (or tomorrow if that time
    already passed today), or `in_minutes` = relative minutes from now.
    Provide exactly one."""
    _ensure_table()
    now = datetime.now()

    if at:
        try:
            hour, minute = (int(x) for x in at.split(":"))
        except Exception:
            return "❌ `at` must be 'HH:MM' 24-hour format"
        due = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if due <= now:
            due += timedelta(days=1)
    elif in_minutes:
        due = now + timedelta(minutes=float(in_minutes))
    else:
        return "❌ Provide either `at` ('HH:MM') or `in_minutes`"

    conn, lock = memory.raw_connection()
    with lock:
        conn.execute(
            "INSERT INTO reminders (due_ts, message, fired) VALUES (?, ?, 0)",
            (due.timestamp(), message),
        )
        conn.commit()
    return f"✅ Reminder set for {due.strftime('%H:%M')}: {message}"


def list_reminders() -> str:
    _ensure_table()
    conn, lock = memory.raw_connection()
    with lock:
        rows = conn.execute(
            "SELECT due_ts, message FROM reminders WHERE fired = 0 ORDER BY due_ts ASC"
        ).fetchall()
    if not rows:
        return "No pending reminders."
    lines = [f"{datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M')} — {msg}" for ts, msg in rows]
    return "\n".join(lines)


def _check_loop():
    while not _stop_flag.is_set():
        try:
            _ensure_table()
            conn, lock = memory.raw_connection()
            now_ts = time.time()
            with lock:
                due = conn.execute(
                    "SELECT id, message FROM reminders WHERE fired = 0 AND due_ts <= ?", (now_ts,)
                ).fetchall()
                for rid, message in due:
                    conn.execute("UPDATE reminders SET fired = 1 WHERE id = ?", (rid,))
                conn.commit()
            if due and _emit_fn:
                for _, message in due:
                    _emit_fn("reminder_fired", {"message": message})
        except Exception:
            pass
        time.sleep(CHECK_SECONDS)


def start_background_scheduler(emit_fn=None):
    global _emit_fn
    _emit_fn = emit_fn
    if getattr(start_background_scheduler, "_started", False):
        return
    start_background_scheduler._started = True
    t = threading.Thread(target=_check_loop, daemon=True)
    t.start()
