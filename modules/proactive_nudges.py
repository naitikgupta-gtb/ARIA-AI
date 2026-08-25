"""
modules/proactive_nudges.py — Proactive Nudges (break reminders).

The interesting part: ARIA speaks FIRST here, unprompted. The Gemini
Live API only responds to turns it receives — so to make ARIA nudge
the user without them saying anything, this sends a synthetic text
turn like "[SYSTEM: 60 minutes have passed, gently remind the user to
take a break]" through the SAME text-input pathway as typed commands.
Gemini treats it as input and speaks a reply out loud — the user just
hears ARIA proactively saying something, which is the intended effect.

Calendar alerts note: this module intentionally does NOT implement a
full Google Calendar OAuth integration (real setup friction — a
developer project + consent screen). "Calendar alerts" are implemented
as the existing set_reminder tool phrased calendar-style ("meeting at
3pm") — ask for a real Calendar sync explicitly if that's still wanted
later, it's a bigger separate piece.
"""
import threading
import time

BREAK_INTERVAL_SECONDS = 60 * 60  # nudge every 60 minutes of active engine time
CHECK_SECONDS = 60

_stop_flag = threading.Event()
_speak_fn = None  # injected: speak_fn(text: str) -> None
_last_nudge_ts = None
_enabled = True


def set_enabled(enabled: bool):
    global _enabled
    _enabled = enabled


def is_enabled() -> bool:
    return _enabled


def _loop():
    global _last_nudge_ts
    _last_nudge_ts = time.time()
    while not _stop_flag.is_set():
        time.sleep(CHECK_SECONDS)
        if not _enabled or _speak_fn is None:
            continue
        if time.time() - _last_nudge_ts >= BREAK_INTERVAL_SECONDS:
            _last_nudge_ts = time.time()
            try:
                _speak_fn(
                    "[SYSTEM: It has been about an hour since the last break. "
                    "Gently, briefly nudge the user to stretch/rest their eyes for a "
                    "moment, in your current persona's voice. Keep it short — one or "
                    "two sentences, don't wait for a reply."
                )
            except Exception as e:
                print(f"[ARIA] proactive nudge failed: {e}")


def reset_timer():
    """Call this whenever the user is clearly active (e.g. sends a
    command) so the break clock reflects actual usage, not idle time."""
    global _last_nudge_ts
    _last_nudge_ts = time.time()


def start_background_nudges(speak_fn):
    global _speak_fn
    _speak_fn = speak_fn
    if getattr(start_background_nudges, "_started", False):
        return
    start_background_nudges._started = True
    t = threading.Thread(target=_loop, daemon=True)
    t.start()
