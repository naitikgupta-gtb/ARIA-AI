"""
modules/automation_rules.py — If-This-Then-That automation.

Two trigger types for v1 (the two most commonly requested patterns):
- "app_opened": fires once when a target process name appears in the
  running-process list (checked every ~8s via psutil, already a dep)
- "time_of_day": fires daily at a given HH:MM

Actions reuse the SAME tool dispatcher as everything else (handle_tool_call
from tools.py) — an automation rule can trigger literally any tool ARIA
already has (open_app, work_mode, send_notification, whatsapp_send...).

Stored in the shared SQLite DB (memory.py's connection).
"""
import json
import threading
import time
from datetime import datetime

import psutil

from modules import memory

CHECK_SECONDS = 8
_stop_flag = threading.Event()
_executor_fn = None  # injected: executor_fn(tool_name: str, args: dict) -> str
_seen_processes = set()  # tracks which app_opened triggers have already fired this "session" of that app being open


def _ensure_table():
    conn, lock = memory.raw_connection()
    with lock:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS automation_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trigger_type TEXT NOT NULL,      -- 'app_opened' | 'time_of_day'
                trigger_value TEXT NOT NULL,     -- process name, or 'HH:MM'
                action_tool TEXT NOT NULL,
                action_args TEXT NOT NULL,       -- JSON
                enabled INTEGER NOT NULL DEFAULT 1,
                last_fired_date TEXT             -- for time_of_day, 'YYYY-MM-DD' to avoid firing twice same day
            )
        """)
        conn.commit()


def add_rule(trigger_type: str, trigger_value: str, action_tool: str, action_args: dict) -> str:
    trigger_type = trigger_type.strip().lower()
    if trigger_type not in ("app_opened", "time_of_day"):
        return "❌ trigger_type must be 'app_opened' or 'time_of_day'"
    if trigger_type == "time_of_day":
        try:
            datetime.strptime(trigger_value, "%H:%M")
        except ValueError:
            return "❌ trigger_value for time_of_day must be 'HH:MM'"

    _ensure_table()
    conn, lock = memory.raw_connection()
    with lock:
        conn.execute(
            "INSERT INTO automation_rules (trigger_type, trigger_value, action_tool, action_args, enabled) "
            "VALUES (?, ?, ?, ?, 1)",
            (trigger_type, trigger_value.strip(), action_tool, json.dumps(action_args or {})),
        )
        conn.commit()
    trigger_desc = f"when {trigger_value} opens" if trigger_type == "app_opened" else f"daily at {trigger_value}"
    return f"✅ Rule created: {trigger_desc} → {action_tool}"


def list_rules() -> str:
    _ensure_table()
    conn, lock = memory.raw_connection()
    with lock:
        rows = conn.execute(
            "SELECT id, trigger_type, trigger_value, action_tool, action_args, enabled FROM automation_rules ORDER BY id"
        ).fetchall()
    if not rows:
        return "No automation rules set up yet."
    lines = []
    for rid, ttype, tval, atool, aargs, enabled in rows:
        status = "✅" if enabled else "⏸️"
        trigger_desc = f"when '{tval}' opens" if ttype == "app_opened" else f"daily at {tval}"
        lines.append(f"[{rid}] {status} {trigger_desc} → {atool}({aargs})")
    return "\n".join(lines)


def delete_rule(rule_id: int) -> str:
    _ensure_table()
    conn, lock = memory.raw_connection()
    with lock:
        cur = conn.execute("DELETE FROM automation_rules WHERE id = ?", (rule_id,))
        conn.commit()
    return f"✅ Rule {rule_id} deleted" if cur.rowcount else f"❌ No rule with id {rule_id}"


def _running_process_names() -> set:
    names = set()
    for p in psutil.process_iter(["name"]):
        try:
            if p.info["name"]:
                names.add(p.info["name"].lower())
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return names


def _check_loop():
    global _seen_processes
    while not _stop_flag.is_set():
        try:
            _ensure_table()
            conn, lock = memory.raw_connection()
            with lock:
                rows = conn.execute(
                    "SELECT id, trigger_type, trigger_value, action_tool, action_args, last_fired_date "
                    "FROM automation_rules WHERE enabled = 1"
                ).fetchall()

            current_processes = _running_process_names()
            today = datetime.now().strftime("%Y-%m-%d")
            now_hm = datetime.now().strftime("%H:%M")

            for rid, ttype, tval, atool, aargs_json, last_fired in rows:
                args = json.loads(aargs_json)

                if ttype == "app_opened":
                    target = tval.lower()
                    is_running = any(target in name for name in current_processes)
                    was_running = target in _seen_processes
                    if is_running and not was_running:
                        _fire(atool, args, f"app_opened:{tval}")
                        _seen_processes.add(target)
                    elif not is_running and was_running:
                        _seen_processes.discard(target)

                elif ttype == "time_of_day":
                    if tval == now_hm and last_fired != today:
                        _fire(atool, args, f"time_of_day:{tval}")
                        with lock:
                            conn.execute(
                                "UPDATE automation_rules SET last_fired_date = ? WHERE id = ?", (today, rid)
                            )
                            conn.commit()
        except Exception as e:
            print(f"[ARIA] automation_rules check loop error: {e}")
        time.sleep(CHECK_SECONDS)


def _fire(tool_name: str, args: dict, trigger_desc: str):
    if _executor_fn is None:
        return
    try:
        result = _executor_fn(tool_name, args)
        memory.log_event("automation_rule", tool_name, args, f"triggered by {trigger_desc}: {result}")
    except Exception as e:
        print(f"[ARIA] automation rule action failed ({tool_name}): {e}")


def start_background_watcher(executor_fn):
    global _executor_fn
    _executor_fn = executor_fn
    if getattr(start_background_watcher, "_started", False):
        return
    start_background_watcher._started = True
    t = threading.Thread(target=_check_loop, daemon=True)
    t.start()
