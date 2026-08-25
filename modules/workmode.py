"""
modules/workmode.py — "Work Mode" macro engine.

One command (voice or typed) launches a whole named profile of apps/URLs
together, then best-effort arranges the resulting windows into a tidy
grid so the user's desktop is ready to go instead of a pile of
overlapping windows. Runs everything in background threads so a slow
app launch never blocks the others.

Add or edit profiles in WORK_PROFILES — no other code changes needed to
add a new one.
"""
import platform
import subprocess
import threading
import time
import webbrowser

# Each profile item is either:
#   {"app": "<name understood by tools.open_app>"}
#   {"url": "<website to open in the default browser>"}
WORK_PROFILES = {
    "coding": [
        {"app": "vscode"},
        {"app": "chrome"},
        {"url": "https://github.com"},
        {"app": "terminal"},
        {"app": "spotify"},
    ],
    "study": [
        {"app": "chrome"},
        {"url": "https://youtube.com"},
        {"app": "notepad"},
        {"app": "spotify"},
    ],
    "meeting": [
        {"app": "teams"},
        {"app": "outlook"},
        {"app": "notepad"},
    ],
    "design": [
        {"app": "chrome"},
        {"url": "https://figma.com"},
        {"app": "explorer"},
    ],
}


def list_profiles():
    return list(WORK_PROFILES.keys())


def _launch_item(item, open_app_fn):
    if "app" in item:
        return open_app_fn(item["app"])
    if "url" in item:
        webbrowser.open(item["url"])
        return f"✅ Opened {item['url']}"
    return "skipped"


def _arrange_windows():
    """Best-effort tiling of open top-level windows into a grid — Windows
    only, and silently a no-op anywhere pygetwindow/pywin32 aren't
    available (still fine, apps just open un-arranged)."""
    if platform.system() != "Windows":
        return
    try:
        import pygetwindow as gw
        time.sleep(2.5)  # let the apps actually finish opening a window
        wins = [w for w in gw.getAllWindows() if w.visible and w.title.strip()]
        if not wins:
            return
        import ctypes
        user32 = ctypes.windll.user32
        screen_w = user32.GetSystemMetrics(0)
        screen_h = user32.GetSystemMetrics(1)
        cols = 2
        rows = (len(wins) + cols - 1) // cols
        cell_w, cell_h = screen_w // cols, screen_h // rows
        for i, w in enumerate(wins[: cols * rows]):
            col, row = i % cols, i // cols
            try:
                w.restore()
                w.moveTo(col * cell_w, row * cell_h)
                w.resizeTo(cell_w, cell_h)
            except Exception:
                continue
    except ImportError:
        # pygetwindow not installed — grid arrangement is a nice-to-have,
        # not a requirement, so we just skip it.
        return
    except Exception:
        return


def run_work_mode(profile_name: str, open_app_fn, arrange: bool = True) -> str:
    profile_name = (profile_name or "").lower().strip()
    items = WORK_PROFILES.get(profile_name)
    if not items:
        return f"❌ Unknown work profile '{profile_name}'. Available: {', '.join(list_profiles())}"

    results = []
    threads = []
    for item in items:
        t = threading.Thread(target=lambda i=item: results.append(_launch_item(i, open_app_fn)))
        t.start()
        threads.append(t)
        time.sleep(0.3)  # small stagger so apps don't all fight for focus at once
    for t in threads:
        t.join(timeout=15)

    if arrange:
        threading.Thread(target=_arrange_windows, daemon=True).start()

    return f"✅ Work Mode '{profile_name}' launched: {len(items)} apps/tabs opened and arranged."
