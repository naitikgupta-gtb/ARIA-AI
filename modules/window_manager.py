"""
modules/window_manager.py — Window & Process Management.

Process listing/killing uses `psutil` (already a dependency). Window
listing/focusing uses `pygetwindow` on Windows (already conditional in
requirements.txt) and is a graceful no-op elsewhere rather than a crash.
"""
import platform
import time

import psutil


def list_processes(limit: int = 15) -> str:
    procs = []
    for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            procs.append(p.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    procs.sort(key=lambda p: p.get("memory_percent") or 0, reverse=True)
    lines = [f"{p['pid']:>6}  {p['name']:<28}  mem {p.get('memory_percent', 0):.1f}%" for p in procs[:limit]]
    return "PID     Name                          Memory\n" + "\n".join(lines)


def kill_process(name_or_pid: str) -> str:
    killed = []
    try:
        pid = int(name_or_pid)
        try:
            psutil.Process(pid).terminate()
            return f"✅ Terminated process {pid}"
        except psutil.NoSuchProcess:
            return f"❌ No process with PID {pid}"
    except ValueError:
        pass  # not a pid, treat as a name

    name_lower = name_or_pid.lower()
    for p in psutil.process_iter(["pid", "name"]):
        try:
            if name_lower in (p.info["name"] or "").lower():
                p.terminate()
                killed.append(p.info["name"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    if not killed:
        return f"❌ No running process matching '{name_or_pid}'"
    return f"✅ Terminated: {', '.join(killed)}"


def _force_foreground(hwnd) -> bool:
    """Windows enforces a 'foreground lock' that stops a background
    process from stealing focus outright — a bare SetForegroundWindow
    call silently no-ops in that case (no exception, the window just
    flashes/highlights in the taskbar instead of coming on screen).
    That's exactly the 'opens in taskbar but I have to click it myself'
    symptom. Escalate through three workarounds, most reliable first."""
    try:
        import ctypes
        import win32con
        import win32gui
    except ImportError:
        return False
    user32 = ctypes.windll.user32

    try:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    except Exception:
        pass

    # 1. AttachThreadInput: briefly share input state with whichever
    #    thread currently owns the foreground — a thread is allowed to
    #    hand focus to another window within that shared state, even
    #    though a bare cross-process call would be blocked.
    try:
        import win32api
        import win32process
        fg_hwnd = win32gui.GetForegroundWindow()
        fg_thread = win32process.GetWindowThreadProcessId(fg_hwnd)[0] if fg_hwnd else 0
        target_thread = win32process.GetWindowThreadProcessId(hwnd)[0]
        cur_thread = win32api.GetCurrentThreadId()
        if fg_thread:
            user32.AttachThreadInput(fg_thread, cur_thread, True)
        user32.AttachThreadInput(target_thread, cur_thread, True)
        win32gui.SetForegroundWindow(hwnd)
        user32.AttachThreadInput(target_thread, cur_thread, False)
        if fg_thread:
            user32.AttachThreadInput(fg_thread, cur_thread, False)
        if win32gui.GetForegroundWindow() == hwnd:
            return True
    except Exception:
        pass

    # 2. Simulated ALT keypress: Windows grants a foreground switch that
    #    immediately follows a real/simulated input event, even from a
    #    background process — this is Microsoft's own documented
    #    workaround for SetForegroundWindow's restriction.
    try:
        user32.keybd_event(0x12, 0, 0, 0)        # ALT down
        win32gui.SetForegroundWindow(hwnd)
        user32.keybd_event(0x12, 0, 0x0002, 0)   # ALT up
        if win32gui.GetForegroundWindow() == hwnd:
            return True
    except Exception:
        pass

    # 3. Last resort.
    try:
        win32gui.SetForegroundWindow(hwnd)
        return win32gui.GetForegroundWindow() == hwnd
    except Exception:
        return False


def snapshot_window_handles() -> set:
    """Set of currently-visible top-level window handles — call this
    right BEFORE launching an app, then pass it to
    wait_and_focus_new_window() so it knows which window is new."""
    if platform.system() != "Windows":
        return set()
    try:
        import pygetwindow as gw
        return {w._hWnd for w in gw.getAllWindows() if w.visible and w.title.strip()}
    except ImportError:
        return set()


def wait_and_focus_new_window(before_hwnds: set, timeout: float = 6.0) -> bool:
    """Polls for a new visible top-level window (not in before_hwnds)
    appearing within `timeout` seconds, and forces it to the
    foreground. Needed after os.startfile / subprocess / Store-app
    launches, none of which bring their own window to front when
    triggered from a background process."""
    if platform.system() != "Windows":
        return False
    try:
        import pygetwindow as gw
    except ImportError:
        return False

    end = time.time() + timeout
    while time.time() < end:
        try:
            current = [w for w in gw.getAllWindows() if w.visible and w.title.strip()]
        except Exception:
            current = []
        new_windows = [w for w in current if w._hWnd not in before_hwnds]
        if new_windows:
            return _force_foreground(new_windows[-1]._hWnd)
        time.sleep(0.3)
    return False


def list_windows() -> str:
    if platform.system() != "Windows":
        return "⚠️ Window listing is Windows-only right now (pygetwindow)."
    try:
        import pygetwindow as gw
        titles = [w.title for w in gw.getAllWindows() if w.visible and w.title.strip()]
        if not titles:
            return "No visible windows found."
        return "\n".join(titles)
    except ImportError:
        return "⚠️ Install pygetwindow: pip install pygetwindow"


def focus_window(title_contains: str) -> str:
    if platform.system() != "Windows":
        return "⚠️ Window focusing is Windows-only right now (pygetwindow)."
    try:
        import pygetwindow as gw
        import win32gui
        matches = [w for w in gw.getAllWindows() if title_contains.lower() in w.title.lower() and w.title.strip()]
        if not matches:
            return f"❌ No open window matching '{title_contains}'"
        win = matches[0]
        win.activate()
        # .activate() calls SetForegroundWindow under the hood, which can
        # silently no-op because of Windows' foreground lock (window stays
        # minimized/behind, only its taskbar icon flashes) — verify it
        # actually landed, and escalate with the AttachThreadInput/Alt-key
        # workaround if not.
        if win32gui.GetForegroundWindow() != win._hWnd:
            _force_foreground(win._hWnd)
        return f"✅ Focused: {win.title}"
    except ImportError:
        return "⚠️ Install pygetwindow: pip install pygetwindow"
    except Exception as e:
        return f"❌ {e}"


def minimize_all() -> str:
    system = platform.system()
    try:
        if system == "Windows":
            import pyautogui
            pyautogui.hotkey("win", "d")
        elif system == "Darwin":
            import subprocess as sp
            sp.run(["osascript", "-e", 'tell application "System Events" to keystroke "m" using {command down, option down}'])
        else:
            return "⚠️ Not implemented for this OS yet."
        return "✅ Minimized all windows"
    except Exception as e:
        return f"❌ {e}"
