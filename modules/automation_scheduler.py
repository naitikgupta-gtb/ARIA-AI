"""
modules/automation_scheduler.py — Automation & Scheduling.

Note on scope: this covers scheduled power actions (shutdown/restart at
a delay — thin wrapper over system_control's native OS timers, which
already handle the "wait X then act" part themselves, no extra thread
needed here).

A general "run any ARIA tool at an arbitrary future time" scheduler is
a bigger piece (needs to safely re-invoke the tool dispatcher from a
background thread) and isn't built yet — set_reminder already covers
"notify me at a time"; this module covers "do this OS action after a
delay". If full arbitrary task scheduling is wanted later, this is
the file that would grow to support it.
"""
from modules import system_control


def schedule_shutdown(minutes: float) -> str:
    return system_control.shutdown(delay_seconds=int(minutes * 60))


def schedule_restart(minutes: float) -> str:
    return system_control.restart(delay_seconds=int(minutes * 60))


def cancel_scheduled_power_action() -> str:
    return system_control.cancel_shutdown()
