"""
modules/maintenance.py — Maintenance & Utility.
"""
import platform
import subprocess
import time
from pathlib import Path

import psutil


def disk_usage_report() -> str:
    lines = []
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except (PermissionError, OSError):
            continue
        total_gb = usage.total / (1024 ** 3)
        used_gb = usage.used / (1024 ** 3)
        lines.append(f"{part.device} ({part.mountpoint}): {used_gb:.1f} / {total_gb:.1f} GB used ({usage.percent}%)")
    return "\n".join(lines) if lines else "Could not read disk usage."


def system_uptime() -> str:
    uptime_seconds = time.time() - psutil.boot_time()
    hours, rem = divmod(int(uptime_seconds), 3600)
    minutes, _ = divmod(rem, 60)
    return f"System has been up for {hours}h {minutes}m"


def flush_dns() -> str:
    system = platform.system()
    try:
        if system == "Windows":
            subprocess.run(["ipconfig", "/flushdns"], capture_output=True)
        elif system == "Darwin":
            subprocess.run(["dscacheutil", "-flushcache"], capture_output=True)
            subprocess.run(["killall", "-HUP", "mDNSResponder"], capture_output=True)
        elif system == "Linux":
            subprocess.run(["systemd-resolve", "--flush-caches"], capture_output=True)
        else:
            return f"❌ Unsupported OS: {system}"
        return "✅ DNS cache flushed"
    except Exception as e:
        return f"❌ {e}"


def clear_temp_files() -> str:
    """Only clears files inside the OS's own designated temp folder, and
    ONLY items untouched for 6+ hours — a real bug was found where this
    deleted the entire temp tree unconditionally, including subfolders
    other currently-running applications (browser, IDE, installers) were
    actively using. Age-gating is a simple, effective guard: anything a
    live process still cares about has almost certainly been touched
    more recently than that. Subdirectories are still skipped entirely
    rather than recursively deleted — a stray live subfolder is exactly
    the failure mode to avoid, not worth the extra few MB freed."""
    import tempfile
    import time as _time

    temp_dir = Path(tempfile.gettempdir())
    freed_mb = 0.0
    removed = 0
    skipped = 0
    skipped_dirs = 0
    cutoff = _time.time() - 6 * 3600

    for item in temp_dir.iterdir():
        try:
            if item.is_file():
                if item.stat().st_mtime > cutoff:
                    skipped += 1  # touched recently — likely still in use, leave it
                    continue
                size = item.stat().st_size
                item.unlink()
                freed_mb += size / (1024 * 1024)
                removed += 1
            elif item.is_dir():
                # Deliberately NOT recursing into/removing subdirectories —
                # too easy to catch a live app's working folder in the blast
                # radius. Only loose top-level files are fair game.
                skipped_dirs += 1
        except Exception:
            skipped += 1
    return (
        f"✅ Cleared temp folder: {removed} old files removed (~{freed_mb:.1f} MB freed), "
        f"{skipped} recent/in-use files skipped, {skipped_dirs} subfolders left untouched (safety)"
    )
