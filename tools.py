"""
tools.py — ARIA v5 Tool System
Har cheez handle karta hai: apps, files, terminal, browser, code, web, system
"""
import os
import sys
import subprocess
import shutil
import json
import time
import platform
import threading
import config
from pathlib import Path
from datetime import datetime
from typing import Any

from modules import workmode
from modules import whatsapp_module
from modules import memory
from modules import vision
from modules import search_synthesis
from modules import clipboard_manager
from modules import reminders
from modules import downloads_organizer
from modules import contacts
from modules import image_gen
from modules import mobile_control
from modules import research_agent
from modules import notion_sync
from modules import codebase_rag
from modules import security_vault
from modules import system_control
from modules import window_manager
from modules import input_automation
from modules import file_manager
from modules import media_control
from modules import automation_scheduler
from modules import maintenance
from modules import network_check
from modules import youtube_control
from modules import spotify_control
from modules import pc_hardware
from modules import software_installer
from modules import location_share
from modules import email_client
from modules import automation_rules
from modules import meeting_notes
from modules import file_search

# ── App opener (v2 — registry + Store-app aware, no more path guessing) ──────
import glob

# Each entry: exe = win32 executable name(s) to resolve via PATH / App Paths
# registry; paths = extra hardcoded fallback globs; store_hint = fuzzy name
# to resolve Microsoft Store / UWP apps (WhatsApp, Spotify-from-Store, etc.)
# via `Get-StartApps`; linux = command(s) to try on Linux.
APP_ALIASES = {
    # Browsers
    "chrome":      {"mac": "Google Chrome", "exe": ["chrome.exe"], "paths": [r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"], "linux": ["google-chrome", "chromium-browser"]},
    "firefox":     {"mac": "Firefox", "exe": ["firefox.exe"], "paths": [r"C:\Program Files\Mozilla Firefox\firefox.exe"], "linux": ["firefox"]},
    "edge":        {"mac": "Microsoft Edge", "exe": ["msedge.exe"], "paths": [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"], "linux": ["microsoft-edge"]},
    "brave":       {"mac": "Brave Browser", "exe": ["brave.exe"], "paths": [r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"], "linux": ["brave-browser"]},

    # Dev tools
    "vscode":      {"mac": "Visual Studio Code", "exe": ["Code.exe"], "paths": [r"C:\Users\%USERNAME%\AppData\Local\Programs\Microsoft VS Code\Code.exe"], "linux": ["code"]},
    "vs code":     {"mac": "Visual Studio Code", "exe": ["Code.exe"], "paths": [r"C:\Users\%USERNAME%\AppData\Local\Programs\Microsoft VS Code\Code.exe"], "linux": ["code"]},
    "terminal":    {"mac": "Terminal", "exe": ["wt.exe", "cmd.exe"], "linux": ["gnome-terminal", "xterm"]},
    "cmd":         {"exe": ["cmd.exe"], "linux": ["xterm"]},
    "powershell":  {"exe": ["powershell.exe", "pwsh.exe"], "linux": ["pwsh"]},
    "postman":     {"mac": "Postman", "exe": ["Postman.exe"], "paths": [r"C:\Users\%USERNAME%\AppData\Local\Postman\Postman.exe"], "linux": ["postman"]},
    "pycharm":     {"mac": "PyCharm", "exe": ["pycharm64.exe"], "store_hint": "PyCharm", "linux": ["pycharm"]},

    # Productivity
    "notepad":     {"mac": "TextEdit", "exe": ["notepad.exe"]},
    "notepad++":   {"mac": "TextEdit", "exe": ["notepad++.exe"], "paths": [r"C:\Program Files\Notepad++\notepad++.exe"], "linux": ["notepad++"]},
    "word":        {"mac": "Microsoft Word", "exe": ["WINWORD.EXE"], "paths": [r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE"]},
    "excel":       {"mac": "Microsoft Excel", "exe": ["EXCEL.EXE"], "paths": [r"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE"]},
    "powerpoint":  {"mac": "Microsoft PowerPoint", "exe": ["POWERPNT.EXE"], "paths": [r"C:\Program Files\Microsoft Office\root\Office16\POWERPNT.EXE"]},
    "outlook":     {"mac": "Microsoft Outlook", "exe": ["OUTLOOK.EXE"], "paths": [r"C:\Program Files\Microsoft Office\root\Office16\OUTLOOK.EXE"], "store_hint": "Outlook"},
    "obsidian":    {"mac": "Obsidian", "exe": ["Obsidian.exe"], "store_hint": "Obsidian", "linux": ["obsidian"]},

    # Media
    "spotify":     {"mac": "Spotify", "exe": ["Spotify.exe"], "paths": [r"C:\Users\%USERNAME%\AppData\Roaming\Spotify\Spotify.exe"], "store_hint": "Spotify", "linux": ["spotify"]},
    "vlc":         {"mac": "VLC", "exe": ["vlc.exe"], "paths": [r"C:\Program Files\VideoLAN\VLC\vlc.exe"], "linux": ["vlc"]},

    # Communication — these ship as Store/UWP apps on most Windows PCs, so
    # store_hint (resolved via Get-StartApps + shell:AppsFolder) is the
    # primary path, not the old hardcoded .exe guess.
    "whatsapp":    {"mac": "WhatsApp", "exe": ["WhatsApp.exe"], "store_hint": "WhatsApp", "linux": ["whatsapp-for-linux"]},
    "telegram":    {"mac": "Telegram", "exe": ["Telegram.exe"], "paths": [r"C:\Users\%USERNAME%\AppData\Roaming\Telegram Desktop\Telegram.exe"], "store_hint": "Telegram", "linux": ["telegram-desktop"]},
    "discord":     {"mac": "Discord", "exe": ["Discord.exe"], "paths": [r"C:\Users\%USERNAME%\AppData\Local\Discord\app-*\Discord.exe"], "linux": ["discord"]},
    "zoom":        {"mac": "zoom.us", "exe": ["Zoom.exe"], "paths": [r"C:\Users\%USERNAME%\AppData\Roaming\Zoom\bin\Zoom.exe"], "store_hint": "Zoom", "linux": ["zoom"]},
    "slack":       {"mac": "Slack", "exe": ["slack.exe"], "paths": [r"C:\Users\%USERNAME%\AppData\Local\slack\slack.exe"], "store_hint": "Slack", "linux": ["slack"]},
    "teams":       {"mac": "Microsoft Teams", "exe": ["ms-teams.exe", "Teams.exe"], "store_hint": "Teams", "linux": ["teams"]},

    # System
    "calculator":  {"mac": "Calculator", "exe": ["calc.exe"], "store_hint": "Calculator", "linux": ["gnome-calculator"]},
    "files":       {"mac": "Finder", "exe": ["explorer.exe"], "linux": ["nautilus"]},
    "explorer":    {"mac": "Finder", "exe": ["explorer.exe"], "linux": ["nautilus"]},
    "settings":    {"raw": "start ms-settings:", "linux": ["gnome-control-center"]},
    "task manager":{"exe": ["taskmgr.exe"]},
    "paint":       {"mac": "Preview", "exe": ["mspaint.exe"], "store_hint": "Paint"},
    "snipping tool":{"exe": ["SnippingTool.exe"], "store_hint": "Snipping Tool"},

    # AI/ML tools
    "jupyter":     {"raw": "jupyter notebook"},
    "jupyter lab": {"raw": "jupyter lab"},
}

# Sites that don't have a real desktop app most people install — just open
# them in the default browser instead of pretending they're a local .exe.
URL_APPS = {
    "youtube": "https://youtube.com",
    "netflix": "https://netflix.com",
    "github": "https://github.com",
    "gmail": "https://mail.google.com",
    "maps": "https://maps.google.com",
    "chatgpt": "https://chat.openai.com",
    "claude": "https://claude.ai",
}


def _win_app_paths_lookup(exe_name: str):
    """Resolve an .exe via the same 'App Paths' registry Windows itself
    uses for Start Menu / Run-box launches — far more reliable than a
    hardcoded Program Files guess."""
    try:
        import winreg
    except ImportError:
        return None
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            key_path = rf"Software\Microsoft\Windows\CurrentVersion\App Paths\{exe_name}"
            with winreg.OpenKey(hive, key_path) as key:
                path, _ = winreg.QueryValueEx(key, None)
                if path and os.path.isfile(path):
                    return path
        except (FileNotFoundError, OSError):
            continue
    return None


def _win_launch_store_app(hint: str) -> bool:
    """Best-effort launch of a Microsoft Store / UWP app (WhatsApp, Zoom,
    Slack, etc. when installed from the Store) by fuzzy display name,
    using Get-StartApps to find its AppID and shell:AppsFolder to run it.
    This replaces guessing an install path that doesn't exist for these
    apps on most machines."""
    ps = (
        f"$m = Get-StartApps | Where-Object {{ $_.Name -like '*{hint}*' }} "
        "| Select-Object -First 1; "
        "if ($m) { explorer.exe (\"shell:AppsFolder\\\" + $m.AppID); exit 0 } else { exit 1 }"
    )
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            timeout=15, capture_output=True,
        )
        return r.returncode == 0
    except Exception:
        return False


def open_app(app_name: str) -> str:
    name_lower = app_name.lower().strip()

    if name_lower in URL_APPS:
        import webbrowser
        webbrowser.open(URL_APPS[name_lower])
        return f"✅ Opened {app_name} in browser"

    cfg = APP_ALIASES.get(name_lower)
    is_windows = platform.system() == "Windows"
    is_mac = platform.system() == "Darwin"

    if cfg is None:
        # Unknown app name — try it verbatim as an exe/PATH command first,
        # then as a Store-app fuzzy match, before giving up.
        cfg = {"exe": [app_name], "store_hint": app_name, "mac": app_name}

    # Snapshot windows BEFORE launching anything, so we can tell which
    # window is the newly-opened app afterwards. On Windows, os.startfile /
    # subprocess / the Store-app launcher below all open their window
    # without taking focus when triggered from a background process —
    # Windows just flashes the taskbar icon instead of showing it, which
    # is why apps used to "open" but never actually appear on screen.
    _before_windows = window_manager.snapshot_window_handles()

    def _opened() -> str:
        try:
            window_manager.wait_and_focus_new_window(_before_windows, timeout=6)
        except Exception:
            pass
        return f"✅ {app_name} opened!"

    if cfg.get("raw"):
        try:
            subprocess.Popen(cfg["raw"], shell=True)
            return _opened()
        except Exception:
            pass

    if is_mac:
        # macOS uses Launch Services via the `open` command — no registry,
        # no hardcoded install paths needed, just the app's display name
        # as it appears in /Applications.
        mac_name = cfg.get("mac", app_name)
        try:
            result = subprocess.run(["open", "-a", mac_name], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return f"✅ {app_name} opened!"
            return f"❌ Could not find '{mac_name}' in /Applications on this Mac."
        except Exception as e:
            return f"❌ {e}"

    if is_windows:
        # 1. Try each exe name via App Paths registry, then plain PATH.
        for exe in cfg.get("exe", []):
            resolved = _win_app_paths_lookup(exe) or shutil.which(exe)
            if resolved:
                try:
                    os.startfile(resolved)
                    return _opened()
                except Exception:
                    continue
        # 2. Hardcoded fallback paths (with %USERNAME% expansion + globs
        #    for versioned install dirs like Discord's app-1.0.9\).
        for raw_path in cfg.get("paths", []):
            expanded = os.path.expandvars(raw_path)
            matches = glob.glob(expanded) if "*" in expanded else ([expanded] if os.path.isfile(expanded) else [])
            if matches:
                try:
                    os.startfile(matches[0])
                    return _opened()
                except Exception:
                    continue
        # 3. Store / UWP app fuzzy launch (covers WhatsApp, and Store
        #    installs of Spotify/Zoom/Slack/etc. that have no fixed .exe path).
        hint = cfg.get("store_hint")
        if hint and _win_launch_store_app(hint):
            return _opened()
        return f"❌ Could not find {app_name} installed on this PC."

    # Non-Windows: try each linux command via PATH.
    for cmd in cfg.get("linux", cfg.get("exe", [name_lower])):
        if shutil.which(cmd):
            try:
                subprocess.Popen([cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return f"✅ {app_name} opened!"
            except Exception:
                continue
    return f"❌ Could not open {app_name}"


# ══════════════════════════════════════════════════════════════════════════════
# TOOL HANDLER — dispatch table
# ══════════════════════════════════════════════════════════════════════════════

def handle_tool_call(name: str, args: dict) -> Any:
    handlers = {
        "open_app":          _tool_open_app,
        "run_terminal":      _tool_run_terminal,
        "write_file":        _tool_write_file,
        "read_file":         _tool_read_file,
        "list_directory":    _tool_list_directory,
        "delete_file":       _tool_delete_file,
        "copy_file":         _tool_copy_file,
        "move_file":         _tool_move_file,
        "create_directory":  _tool_create_directory,
        "open_browser_url":  _tool_open_browser_url,
        "web_search":        _tool_web_search,
        "take_screenshot":   _tool_take_screenshot,
        "type_text":         _tool_type_text,
        "press_keys":        _tool_press_keys,
        "click_at":          _tool_click_at,
        "get_system_info":   _tool_get_system_info,
        "get_clipboard":     _tool_get_clipboard,
        "set_clipboard":     _tool_set_clipboard,
        "create_website":    _tool_create_website,
        "run_python":        _tool_run_python,
        "install_package":   _tool_install_package,
        "get_datetime":      _tool_get_datetime,
        "speak_text":        _tool_speak_text,
        "set_volume":        _tool_set_volume,
        "open_file":         _tool_open_file,
        "find_files":        _tool_find_files,
        "zip_files":         _tool_zip_files,
        "rename_file":       _tool_rename_file,
        "get_weather":       _tool_get_weather,
        "send_notification": _tool_send_notification,
        "work_mode":         _tool_work_mode,
        "whatsapp_send":     _tool_whatsapp_send,
        "open_games_hub":    _tool_open_games_hub,
        "read_screen":       _tool_read_screen,
        "web_search_synthesis": _tool_web_search_synthesis,
        "recall_memory":     _tool_recall_memory,
        "clipboard_history": _tool_clipboard_history,
        "clipboard_restore": _tool_clipboard_restore,
        "set_reminder":      _tool_set_reminder,
        "list_reminders":    _tool_list_reminders,
        "organize_downloads": _tool_organize_downloads,
        "add_contact":       _tool_add_contact,
        "list_contacts":     _tool_list_contacts,
        "debug_error_screenshot": _tool_debug_error_screenshot,
        "generate_image":    _tool_generate_image,
        "mobile_device_status": _tool_mobile_device_status,
        "mobile_battery_info": _tool_mobile_battery_info,
        "mobile_push_file":  _tool_mobile_push_file,
        "mobile_pull_file":  _tool_mobile_pull_file,
        "mobile_open_app":   _tool_mobile_open_app,
        "mobile_close_app":  _tool_mobile_close_app,
        "mobile_tap":        _tool_mobile_tap,
        "mobile_swipe":      _tool_mobile_swipe,
        "mobile_toggle_wifi": _tool_mobile_toggle_wifi,
        "mobile_toggle_bluetooth": _tool_mobile_toggle_bluetooth,
        "deep_research":     _tool_deep_research,
        "set_notion_token":  _tool_set_notion_token,
        "notion_read_page":  _tool_notion_read_page,
        "notion_query_database": _tool_notion_query_database,
        "ingest_codebase":   _tool_ingest_codebase,
        "consult_oracle":    _tool_consult_oracle,
        "lock_system":       _tool_lock_system,
        "mute":              _tool_mute,
        "shutdown_pc":       _tool_shutdown_pc,
        "restart_pc":        _tool_restart_pc,
        "cancel_shutdown":   _tool_cancel_shutdown,
        "sleep_pc":          _tool_sleep_pc,
        "list_processes":    _tool_list_processes,
        "kill_process":      _tool_kill_process,
        "list_windows":      _tool_list_windows,
        "focus_window":      _tool_focus_window,
        "minimize_all_windows": _tool_minimize_all_windows,
        "mouse_move":        _tool_mouse_move,
        "mouse_click":       _tool_mouse_click,
        "mouse_scroll":      _tool_mouse_scroll,
        "get_mouse_position": _tool_get_mouse_position,
        "keyboard_type":     _tool_keyboard_type,
        "keyboard_press":    _tool_keyboard_press,
        "list_files":        _tool_list_files,
        "search_files":      _tool_search_files,
        "create_folder":     _tool_create_folder,
        "trash_file":        _tool_trash_file,
        "get_file_info":     _tool_get_file_info,
        "record_audio":      _tool_record_audio,
        "record_screen":     _tool_record_screen,
        "play_media_file":   _tool_play_media_file,
        "schedule_shutdown": _tool_schedule_shutdown,
        "schedule_restart":  _tool_schedule_restart,
        "disk_usage_report": _tool_disk_usage_report,
        "system_uptime":     _tool_system_uptime,
        "flush_dns":         _tool_flush_dns,
        "clear_temp_files":  _tool_clear_temp_files,
        "check_network":     _tool_check_network,
        "play_youtube":      _tool_play_youtube,
        "play_spotify":      _tool_play_spotify,
        "pc_toggle_bluetooth": _tool_pc_toggle_bluetooth,
        "pc_toggle_wifi":    _tool_pc_toggle_wifi,
        "set_brightness":    _tool_set_brightness,
        "install_software":  _tool_install_software,
        "send_my_location":  _tool_send_my_location,
        "read_recent_emails": _tool_read_recent_emails,
        "send_email":        _tool_send_email,
        "set_email_credentials": _tool_set_email_credentials,
        "add_automation_rule": _tool_add_automation_rule,
        "list_automation_rules": _tool_list_automation_rules,
        "delete_automation_rule": _tool_delete_automation_rule,
        "record_and_summarize_meeting": _tool_record_and_summarize_meeting,
        "smart_file_search": _tool_smart_file_search,
        "set_break_nudges":  _tool_set_break_nudges,
    }
    fn = handlers.get(name)
    if fn:
        result = fn(args)
        # Persistent Stored Memory: log every tool call so future sessions
        # can recall what ARIA did, via the recall_memory tool.
        try:
            summary = result if isinstance(result, str) else json.dumps(result)
            memory.log_event("tool_call", name, args, summary)
        except Exception:
            pass
        return result
    return f"Unknown tool: {name}"


# ── Tool Implementations ──────────────────────────────────────────────────────

def _tool_open_app(args):
    return open_app(args.get("app_name", ""))


def _tool_run_terminal(args):
    cmd     = args.get("command", "")
    timeout = args.get("timeout", 30)
    cwd     = args.get("working_dir", None)
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True,
            text=True, timeout=timeout, cwd=cwd
        )
        out = (result.stdout or "").strip()
        err = (result.stderr or "").strip()
        if result.returncode != 0 and err:
            return f"Exit {result.returncode}\nSTDERR: {err}\nSTDOUT: {out}"
        return out if out else (err or "Done (no output)")
    except subprocess.TimeoutExpired:
        return f"❌ Command timed out after {timeout}s"
    except Exception as e:
        return f"❌ Error: {e}"


def _tool_write_file(args):
    path    = args.get("path", "")
    content = args.get("content", "")
    mode    = args.get("mode", "w")  # 'w' overwrite, 'a' append
    try:
        p = Path(path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, mode, encoding="utf-8") as f:
            f.write(content)
        return f"✅ Written to {path} ({len(content)} chars)"
    except Exception as e:
        return f"❌ {e}"


def _tool_read_file(args):
    path      = args.get("path", "")
    max_chars = args.get("max_chars", 10000)
    try:
        p = Path(path).expanduser()
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(max_chars)
        return content + (f"\n\n[...truncated, file larger than {max_chars} chars]"
                         if p.stat().st_size > max_chars else "")
    except Exception as e:
        return f"❌ {e}"


def _tool_list_directory(args):
    path  = args.get("path", ".")
    show_hidden = args.get("show_hidden", False)
    try:
        p = Path(path).expanduser()
        items = []
        for item in sorted(p.iterdir()):
            if not show_hidden and item.name.startswith("."):
                continue
            kind = "📁" if item.is_dir() else "📄"
            size = ""
            if item.is_file():
                s = item.stat().st_size
                size = f" ({_fmt_size(s)})"
            items.append(f"{kind} {item.name}{size}")
        return "\n".join(items) if items else "(empty directory)"
    except Exception as e:
        return f"❌ {e}"


def _fmt_size(b):
    for unit in ["B", "KB", "MB", "GB"]:
        if b < 1024:
            return f"{b:.1f}{unit}"
        b /= 1024
    return f"{b:.1f}TB"


def _tool_delete_file(args):
    path = args.get("path", "")
    try:
        p = Path(path).expanduser()
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
        return f"✅ Deleted: {path}"
    except Exception as e:
        return f"❌ {e}"


def _tool_create_directory(args):
    path = args.get("path", "")
    try:
        Path(path).expanduser().mkdir(parents=True, exist_ok=True)
        return f"✅ Directory created: {path}"
    except Exception as e:
        return f"❌ {e}"


def _tool_open_browser_url(args):
    import webbrowser
    url = args.get("url", "")
    webbrowser.open(url)
    return f"✅ Opened: {url}"


def _tool_web_search(args):
    import webbrowser, urllib.parse
    query = args.get("query", "")
    engine = args.get("engine", "google")
    engines = {
        "google": f"https://www.google.com/search?q={urllib.parse.quote(query)}",
        "youtube": f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}",
        "github": f"https://github.com/search?q={urllib.parse.quote(query)}",
        "stackoverflow": f"https://stackoverflow.com/search?q={urllib.parse.quote(query)}",
    }
    url = engines.get(engine, engines["google"])
    webbrowser.open(url)
    return f"✅ Searching '{query}' on {engine}"


SCREENSHOT_DIR = Path.home() / ".aria" / "screenshots"


def _tool_take_screenshot(args):
    """Takes a screenshot, saves the FULL-resolution PNG to disk, and
    returns a resized (max 1600px wide) copy as base64 for the HUD
    preview — on a 4K/high-DPI display, a full-res base64 payload can
    be several MB, which is slow to transmit/render for what's just a
    preview thumbnail. The saved file on disk is untouched/full quality."""
    import base64
    import io
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    filename = args.get("save_path") or f"screenshot_{int(time.time())}.png"
    path = SCREENSHOT_DIR / Path(filename).name
    try:
        import pyautogui
        img = pyautogui.screenshot()
        img.save(path)  # full resolution, untouched

        preview = img
        max_width = 1600
        if img.width > max_width:
            ratio = max_width / img.width
            preview = img.resize((max_width, int(img.height * ratio)))
        buf = io.BytesIO()
        preview.save(buf, format="PNG", optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode()

        return json.dumps({
            "ok": True,
            "path": str(path),
            "image_base64": b64,
            "message": f"Screenshot saved: {path}",
        })
    except ImportError:
        return json.dumps({"ok": False, "message": "⚠️ Install pyautogui: pip install pyautogui"})
    except Exception as e:
        return json.dumps({"ok": False, "message": f"❌ {type(e).__name__}: {e}"})


def _tool_type_text(args):
    text = args.get("text", "")
    try:
        import pyautogui
        time.sleep(0.5)
        pyautogui.typewrite(text, interval=0.02)
        return f"✅ Typed: {text[:50]}..."
    except ImportError:
        return "⚠️ Install pyautogui: pip install pyautogui"
    except Exception as e:
        return f"❌ {e}"


def _tool_press_keys(args):
    keys = args.get("keys", "")  # e.g. "ctrl+c", "alt+tab", "enter"
    try:
        import pyautogui
        time.sleep(0.3)
        pyautogui.hotkey(*keys.replace("+", " ").split())
        return f"✅ Pressed: {keys}"
    except ImportError:
        return "⚠️ Install pyautogui: pip install pyautogui"
    except Exception as e:
        return f"❌ {e}"


def _tool_click_at(args):
    x = args.get("x", 0)
    y = args.get("y", 0)
    button = args.get("button", "left")
    try:
        import pyautogui
        pyautogui.click(x, y, button=button)
        return f"✅ Clicked at ({x}, {y})"
    except ImportError:
        return "⚠️ Install pyautogui: pip install pyautogui"
    except Exception as e:
        return f"❌ {e}"


def _tool_get_system_info(args):
    import psutil
    info = {
        "os": platform.system() + " " + platform.version(),
        "hostname": platform.node(),
        "cpu_percent": psutil.cpu_percent(interval=1),
        "cpu_cores": psutil.cpu_count(),
        "ram_total_gb": round(psutil.virtual_memory().total / 1e9, 1),
        "ram_used_gb": round(psutil.virtual_memory().used / 1e9, 1),
        "ram_percent": psutil.virtual_memory().percent,
        "disk_total_gb": round(psutil.disk_usage('/').total / 1e9, 1),
        "disk_used_gb": round(psutil.disk_usage('/').used / 1e9, 1),
        "disk_percent": psutil.disk_usage('/').percent,
        "python": sys.version,
        "home_dir": str(Path.home()),
        "current_dir": os.getcwd(),
    }
    return json.dumps(info, indent=2)


def _tool_get_clipboard(args):
    try:
        import pyperclip
        return pyperclip.paste() or "(clipboard empty)"
    except ImportError:
        if platform.system() == "Windows":
            r = subprocess.run("powershell Get-Clipboard", capture_output=True, text=True)
            return r.stdout.strip()
        return "⚠️ Install pyperclip: pip install pyperclip"


def _tool_set_clipboard(args):
    text = args.get("text", "")
    try:
        import pyperclip
        pyperclip.copy(text)
        return f"✅ Copied to clipboard: {text[:100]}"
    except ImportError:
        if platform.system() == "Windows":
            subprocess.run(f'echo {text} | clip', shell=True)
            return f"✅ Copied to clipboard"
        return "⚠️ Install pyperclip: pip install pyperclip"


def _tool_create_website(args):
    """Create a complete website (HTML/CSS/JS) and optionally open it."""
    name        = args.get("name", "my_website")
    description = args.get("description", "A website")
    html_content = args.get("html_content", "")
    css_content  = args.get("css_content", "")
    js_content   = args.get("js_content", "")
    output_dir   = args.get("output_dir", str(Path.home() / "Desktop" / name))
    open_browser = args.get("open_browser", True)

    try:
        p = Path(output_dir)
        p.mkdir(parents=True, exist_ok=True)

        # Write HTML
        if not html_content:
            html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{name}</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <h1>{name}</h1>
    <p>{description}</p>
    <script src="script.js"></script>
</body>
</html>"""

        (p / "index.html").write_text(html_content, encoding="utf-8")
        if css_content:
            (p / "style.css").write_text(css_content, encoding="utf-8")
        if js_content:
            (p / "script.js").write_text(js_content, encoding="utf-8")

        if open_browser:
            import webbrowser
            webbrowser.open(f"file:///{(p / 'index.html').resolve()}")

        return f"✅ Website created at {output_dir} and opened in browser"
    except Exception as e:
        return f"❌ {e}"


def _tool_run_python(args):
    """Run Python code string directly."""
    code    = args.get("code", "")
    timeout = args.get("timeout", 30)
    try:
        # Write to temp file and run
        tmp = Path("/tmp/aria_run.py") if platform.system() != "Windows" else Path(os.environ.get("TEMP", ".")) / "aria_run.py"
        tmp.write_text(code, encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(tmp)],
            capture_output=True, text=True, timeout=timeout
        )
        out = result.stdout.strip()
        err = result.stderr.strip()
        return out if out else (err or "Done")
    except subprocess.TimeoutExpired:
        return f"❌ Timed out after {timeout}s"
    except Exception as e:
        return f"❌ {e}"


def _tool_install_package(args):
    package = args.get("package", "")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", package],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            return f"✅ Installed: {package}"
        return f"❌ {result.stderr.strip()}"
    except Exception as e:
        return f"❌ {e}"


def _tool_get_datetime(args):
    fmt = args.get("format", "%Y-%m-%d %H:%M:%S")
    now = datetime.now()
    return now.strftime(fmt)


def _tool_speak_text(args):
    """TTS — text bolwao ARIA ki voice se."""
    text = args.get("text", "")
    try:
        if platform.system() == "Windows":
            subprocess.Popen(
                f'powershell -command "Add-Type -AssemblyName System.Speech; '
                f'$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; '
                f'$s.Speak(\'{text}\')"',
                shell=True
            )
        else:
            subprocess.Popen(["espeak", text], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return f"✅ Speaking: {text[:50]}"
    except Exception as e:
        return f"❌ {e}"


def _tool_set_volume(args):
    return system_control.set_volume(int(args.get("level", 50)))


def _tool_mute(args):
    return system_control.mute(bool(args.get("enable", True)))


def _tool_open_file(args):
    """Open any file with default application."""
    path = args.get("path", "")
    try:
        p = Path(path).expanduser()
        if platform.system() == "Windows":
            os.startfile(str(p))
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", str(p)])
        else:
            subprocess.Popen(["xdg-open", str(p)])
        return f"✅ Opened: {path}"
    except Exception as e:
        return f"❌ {e}"


def _tool_find_files(args):
    directory = args.get("directory", str(Path.home()))
    pattern   = args.get("pattern", "*")
    max_results = args.get("max_results", 50)
    try:
        p = Path(directory).expanduser()
        results = list(p.rglob(pattern))[:max_results]
        return "\n".join(str(r) for r in results) if results else "No files found"
    except Exception as e:
        return f"❌ {e}"


def _tool_zip_files(args):
    import zipfile
    files     = args.get("files", [])
    output    = args.get("output", "archive.zip")
    try:
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in files:
                p = Path(f).expanduser()
                if p.is_dir():
                    for sub in p.rglob("*"):
                        zf.write(sub, sub.relative_to(p.parent))
                else:
                    zf.write(p, p.name)
        return f"✅ Zipped {len(files)} item(s) to {output}"
    except Exception as e:
        return f"❌ {e}"


def _tool_get_weather(args):
    """Open weather for a city."""
    import webbrowser, urllib.parse
    city = args.get("city", "")
    url = f"https://wttr.in/{urllib.parse.quote(city)}?format=3"
    try:
        import urllib.request
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.read().decode("utf-8")
    except Exception:
        webbrowser.open(f"https://weather.com/search?q={urllib.parse.quote(city)}")
        return f"✅ Opened weather for {city}"


def _tool_send_notification(args):
    title   = args.get("title", "ARIA")
    message = args.get("message", "")
    try:
        system = platform.system()
        if system == "Windows":
            subprocess.run(
                f'powershell -command "New-BurntToastNotification -Text \'{title}\', \'{message}\'"',
                shell=True, capture_output=True
            )
        elif system == "Darwin":
            # macOS native notification via AppleScript — no extra
            # dependency needed, ships with the OS.
            safe_title = title.replace('"', '\\"')
            safe_message = message.replace('"', '\\"')
            subprocess.run(
                ["osascript", "-e", f'display notification "{safe_message}" with title "{safe_title}"'],
                capture_output=True,
            )
        elif system == "Linux":
            subprocess.run(["notify-send", title, message], capture_output=True)
        return f"✅ Notification sent"
    except Exception as e:
        return f"❌ {e}"


def _tool_work_mode(args):
    """One command → launches a whole named profile of apps/tabs together
    (e.g. 'coding': VS Code + Chrome + GitHub + terminal + Spotify) and
    best-effort tiles the resulting windows so the desktop is ready."""
    profile = args.get("profile", "")
    if not profile:
        return f"❌ Provide a profile name. Available: {', '.join(workmode.list_profiles())}"
    return workmode.run_work_mode(profile, open_app)


def _tool_whatsapp_send(args):
    """Send a WhatsApp message via pywhatkit (WhatsApp Web automation) —
    no Selenium, no DOM scraping, nothing to keep patching when WhatsApp
    changes its page. Accepts either a saved contact_name OR a raw
    phone_number directly."""
    phone   = args.get("phone_number", "").strip()
    contact_name = args.get("contact_name", "").strip()
    message = args.get("message", "")
    send_at = args.get("send_at")  # optional 'HH:MM'

    if not phone and contact_name:
        resolved = contacts.find_contact(contact_name)
        if not resolved:
            return (
                f"❌ No saved contact matching '{contact_name}' (or more than one matches). "
                f"Say 'save contact <name> <number>' first, or give the phone number directly."
            )
        phone = resolved

    if not phone:
        return "❌ Provide either a contact_name (already saved) or a phone_number."

    if send_at:
        return whatsapp_module.schedule_message(phone, message, send_at)
    return whatsapp_module.send_message_now(phone, message)


def _tool_add_contact(args):
    return contacts.add_contact(args.get("name", ""), args.get("phone_number", ""))


def _tool_list_contacts(args):
    return contacts.list_contacts()


def _tool_debug_error_screenshot(args):
    """Screenshot my error, ARIA understands and fixes it — dedicated
    coding-debug variant of screen reading."""
    return vision.debug_code_error()


def _tool_generate_image(args):
    """Free image generation via Pollinations.ai — no API key needed."""
    result = image_gen.generate(
        args.get("prompt", ""),
        width=args.get("width", 1024),
        height=args.get("height", 1024),
    )
    return json.dumps(result)


def _tool_open_games_hub(args):
    """Opens the built-in Games Hub (HTML5 Snake/Tetris + trivia quiz) —
    served locally by the app itself, no external ROMs/emulators."""
    import webbrowser
    port = os.environ.get("ARIA_PORT", "8765")
    webbrowser.open(f"http://127.0.0.1:{port}/games/")
    return "✅ Games Hub opened"


def _tool_read_screen(args):
    """Screen Reading (Desktop Eyes) — screenshot + Gemini Vision."""
    return vision.read_screen(args.get("question", ""))


def _tool_web_search_synthesis(args):
    """AI Search Combo (Live Synthesis) — scrape top results, let Gemini
    synthesize a structured Overview/Key Points/Conclusion summary."""
    query = args.get("query", "")
    if not query:
        return "❌ Provide a query"
    return search_synthesis.synthesize(query)


def _tool_recall_memory(args):
    """Persistent Stored Memory — search the local timeline of past
    tool calls and searches."""
    return memory.recall(args.get("query", ""), args.get("limit", 10))


def _tool_clipboard_history(args):
    return clipboard_manager.get_history(args.get("limit", 20))


def _tool_clipboard_restore(args):
    idx = args.get("index", 0)
    return clipboard_manager.restore_index(int(idx))


def _tool_set_reminder(args):
    return reminders.add_reminder(
        args.get("message", ""),
        at=args.get("at", ""),
        in_minutes=args.get("in_minutes", 0),
    )


def _tool_list_reminders(args):
    return reminders.list_reminders()


def _tool_organize_downloads(args):
    return downloads_organizer.organize(args.get("folder", ""))


def _tool_mobile_device_status(args):
    return mobile_control.device_status()


def _tool_mobile_battery_info(args):
    return mobile_control.battery_info()


def _tool_mobile_push_file(args):
    return mobile_control.push_file(args.get("local_path", ""), args.get("remote_path", "/sdcard/"))


def _tool_mobile_pull_file(args):
    return mobile_control.pull_file(args.get("remote_path", ""), args.get("local_path", "."))


def _tool_mobile_open_app(args):
    return mobile_control.open_app(args.get("package_name", ""))


def _tool_mobile_close_app(args):
    return mobile_control.close_app(args.get("package_name", ""))


def _tool_mobile_tap(args):
    return mobile_control.tap(int(args.get("x", 0)), int(args.get("y", 0)))


def _tool_mobile_swipe(args):
    return mobile_control.swipe(
        int(args.get("x1", 0)), int(args.get("y1", 0)),
        int(args.get("x2", 0)), int(args.get("y2", 0)),
        int(args.get("duration_ms", 300)),
    )


def _tool_mobile_toggle_wifi(args):
    return mobile_control.toggle_wifi(bool(args.get("enable", True)))


def _tool_mobile_toggle_bluetooth(args):
    return mobile_control.toggle_bluetooth(bool(args.get("enable", True)))


def _tool_deep_research(args):
    return research_agent.deep_research(args.get("query", ""))


def _tool_set_notion_token(args):
    config.set_notion_token(args.get("token", ""))
    return "✅ Notion token saved"


def _tool_notion_read_page(args):
    return notion_sync.read_page(args.get("page_id_or_url", ""))


def _tool_notion_query_database(args):
    return notion_sync.query_database(args.get("database_id_or_url", ""), args.get("limit", 10))


def _tool_ingest_codebase(args):
    return codebase_rag.ingest_codebase(args.get("folder", ""))


def _tool_consult_oracle(args):
    return codebase_rag.consult_oracle(args.get("question", ""), args.get("folder", ""))


def _tool_lock_system(args):
    return security_vault.lock_system()


def _tool_shutdown_pc(args):
    return system_control.shutdown(int(args.get("delay_seconds", 30)))


def _tool_restart_pc(args):
    return system_control.restart(int(args.get("delay_seconds", 30)))


def _tool_cancel_shutdown(args):
    return system_control.cancel_shutdown()


def _tool_sleep_pc(args):
    return system_control.sleep_now()


def _tool_list_processes(args):
    return window_manager.list_processes(int(args.get("limit", 15)))


def _tool_kill_process(args):
    return window_manager.kill_process(args.get("name_or_pid", ""))


def _tool_list_windows(args):
    return window_manager.list_windows()


def _tool_focus_window(args):
    return window_manager.focus_window(args.get("title_contains", ""))


def _tool_minimize_all_windows(args):
    return window_manager.minimize_all()


def _tool_mouse_move(args):
    return input_automation.mouse_move(int(args.get("x", 0)), int(args.get("y", 0)))


def _tool_mouse_click(args):
    return input_automation.mouse_click(
        args.get("x"), args.get("y"), args.get("button", "left"), bool(args.get("double", False))
    )


def _tool_mouse_scroll(args):
    return input_automation.mouse_scroll(int(args.get("amount", -5)))


def _tool_get_mouse_position(args):
    return input_automation.get_mouse_position()


def _tool_keyboard_type(args):
    return input_automation.keyboard_type(args.get("text", ""))


def _tool_keyboard_press(args):
    return input_automation.keyboard_press(args.get("keys", ""))


def _tool_list_files(args):
    return file_manager.list_files(args.get("folder", "."))


def _tool_search_files(args):
    return file_manager.search_files(args.get("pattern", "*"), args.get("folder", "."))


def _tool_create_folder(args):
    return file_manager.create_folder(args.get("path", ""))


def _tool_move_file(args):
    return file_manager.move_file(args.get("src", ""), args.get("dest", ""))


def _tool_copy_file(args):
    return file_manager.copy_file(args.get("src", ""), args.get("dest", ""))


def _tool_rename_file(args):
    return file_manager.rename_file(args.get("path", ""), args.get("new_name", ""))


def _tool_trash_file(args):
    """Sends to Recycle Bin/Trash, not a permanent delete — see
    file_manager.py's module docstring for why."""
    return file_manager.trash_file(args.get("path", ""))


def _tool_get_file_info(args):
    return file_manager.get_file_info(args.get("path", ""))


def _tool_record_audio(args):
    return media_control.record_audio(int(args.get("seconds", 10)))


def _tool_record_screen(args):
    return media_control.record_screen(int(args.get("seconds", 10)))


def _tool_play_media_file(args):
    return media_control.play_media_file(args.get("path", ""))


def _tool_schedule_shutdown(args):
    return automation_scheduler.schedule_shutdown(float(args.get("minutes", 5)))


def _tool_schedule_restart(args):
    return automation_scheduler.schedule_restart(float(args.get("minutes", 5)))


def _tool_disk_usage_report(args):
    return maintenance.disk_usage_report()


def _tool_system_uptime(args):
    return maintenance.system_uptime()


def _tool_flush_dns(args):
    return maintenance.flush_dns()


def _tool_clear_temp_files(args):
    return maintenance.clear_temp_files()


def _tool_check_network(args):
    """Live diagnostic — tests reachability of each external service ARIA
    depends on, so a 'search isn't working' moment can be diagnosed in
    one command instead of guessing."""
    return network_check.check_network()


def _tool_play_youtube(args):
    return youtube_control.play(args.get("query", ""))


def _tool_play_spotify(args):
    return spotify_control.play(args.get("query", ""))


def _tool_pc_toggle_bluetooth(args):
    """This PC's own Bluetooth — not the phone's (see mobile_toggle_bluetooth)."""
    return pc_hardware.toggle_bluetooth(bool(args.get("enable", True)))


def _tool_pc_toggle_wifi(args):
    """This PC's own WiFi — not the phone's."""
    return pc_hardware.toggle_wifi(bool(args.get("enable", True)))


def _tool_set_brightness(args):
    return pc_hardware.set_brightness(int(args.get("level", 70)))


def _tool_install_software(args):
    return software_installer.install(args.get("app_name", ""))


def _tool_send_my_location(args):
    return location_share.send_my_location(args.get("contact_name", ""))


def _tool_read_recent_emails(args):
    return email_client.read_recent_emails(int(args.get("limit", 5)), bool(args.get("unread_only", False)))


def _tool_send_email(args):
    return email_client.send_email(args.get("to", ""), args.get("subject", ""), args.get("body", ""))


def _tool_set_email_credentials(args):
    config.set_email_credentials(
        args.get("address", ""), args.get("app_password", ""), args.get("provider", "gmail")
    )
    return "✅ Email credentials saved"


def _tool_add_automation_rule(args):
    return automation_rules.add_rule(
        args.get("trigger_type", ""), args.get("trigger_value", ""),
        args.get("action_tool", ""), args.get("action_args", {}),
    )


def _tool_list_automation_rules(args):
    return automation_rules.list_rules()


def _tool_delete_automation_rule(args):
    return automation_rules.delete_rule(int(args.get("rule_id", 0)))


def _tool_record_and_summarize_meeting(args):
    return meeting_notes.record_and_summarize(float(args.get("minutes", 15)))


def _tool_smart_file_search(args):
    return file_search.smart_search(
        keyword=args.get("keyword", ""),
        extension=args.get("extension", ""),
        modified_within_days=args.get("modified_within_days"),
        search_root=args.get("search_root", ""),
    )


def _tool_set_break_nudges(args):
    from modules import proactive_nudges
    enable = bool(args.get("enable", True))
    proactive_nudges.set_enabled(enable)
    return f"✅ Break nudges {'enabled' if enable else 'disabled'}"


# ══════════════════════════════════════════════════════════════════════════════
# TOOL DECLARATIONS — Gemini ko batao kya kya tools available hain
# ══════════════════════════════════════════════════════════════════════════════

TOOL_DECLARATIONS = [
    {
        "name": "open_app",
        "description": (
            "Koi bhi application open karo laptop pe. "
            "Chrome, VS Code, Spotify, WhatsApp, Notepad, Calculator, Discord, "
            "Zoom, etc. Jab bhi user koi app kholne ko bole."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "app_name": {"type": "string", "description": "App ka naam, e.g. 'chrome', 'vscode', 'spotify'"}
            },
            "required": ["app_name"]
        }
    },
    {
        "name": "run_terminal",
        "description": (
            "Terminal/CMD mein koi bhi command run karo. "
            "Git, npm, pip, python scripts, system commands, file operations — sab. "
            "Jab user koi command chalane ko bole ya kuch run karne ko bole."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command":     {"type": "string", "description": "Shell command to run"},
                "working_dir": {"type": "string", "description": "Directory to run command in (optional)"},
                "timeout":     {"type": "integer", "description": "Timeout in seconds (default 30)"}
            },
            "required": ["command"]
        }
    },
    {
        "name": "write_file",
        "description": (
            "Koi bhi file likho ya create karo — code, text, HTML, CSS, Python, JSON, etc. "
            "Website banana ho, script likhni ho, notes save karne ho — sab ke liye."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path":    {"type": "string", "description": "File path, e.g. 'C:/Users/me/Desktop/hello.py'"},
                "content": {"type": "string", "description": "File content"},
                "mode":    {"type": "string", "description": "'w' for overwrite (default), 'a' for append"}
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "read_file",
        "description": "Koi bhi file padhke uska content return karo.",
        "parameters": {
            "type": "object",
            "properties": {
                "path":      {"type": "string", "description": "File path"},
                "max_chars": {"type": "integer", "description": "Max characters to read (default 10000)"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "list_directory",
        "description": "Kisi folder ke files aur subfolders list karo.",
        "parameters": {
            "type": "object",
            "properties": {
                "path":        {"type": "string", "description": "Directory path (default '.')"},
                "show_hidden": {"type": "boolean", "description": "Show hidden files?"}
            },
            "required": []
        }
    },
    {
        "name": "delete_file",
        "description": "File ya folder delete karo.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File/folder path to delete"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "create_directory",
        "description": "Naya folder/directory banao.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path to create"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "open_browser_url",
        "description": "Browser mein koi bhi URL/website kholo.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Full URL to open, e.g. 'https://github.com'"}
            },
            "required": ["url"]
        }
    },
    {
        "name": "web_search",
        "description": "Google, YouTube, GitHub ya StackOverflow pe kuch bhi search karo.",
        "parameters": {
            "type": "object",
            "properties": {
                "query":  {"type": "string", "description": "Search query"},
                "engine": {"type": "string", "description": "'google', 'youtube', 'github', 'stackoverflow'"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "take_screenshot",
        "description": "Screen ka screenshot lo aur save karo.",
        "parameters": {
            "type": "object",
            "properties": {
                "save_path": {"type": "string", "description": "Where to save screenshot (optional)"}
            },
            "required": []
        }
    },
    {
        "name": "type_text",
        "description": "Keyboard se text type karo (currently focused window mein).",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to type"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "press_keys",
        "description": "Keyboard shortcut ya key press karo. e.g. 'ctrl+c', 'alt+tab', 'enter', 'ctrl+shift+n'",
        "parameters": {
            "type": "object",
            "properties": {
                "keys": {"type": "string", "description": "Keys to press, e.g. 'ctrl+c', 'alt+f4'"}
            },
            "required": ["keys"]
        }
    },
    {
        "name": "click_at",
        "description": "Screen pe specific position pe click karo.",
        "parameters": {
            "type": "object",
            "properties": {
                "x":      {"type": "integer", "description": "X coordinate"},
                "y":      {"type": "integer", "description": "Y coordinate"},
                "button": {"type": "string",  "description": "'left', 'right', or 'middle'"}
            },
            "required": ["x", "y"]
        }
    },
    {
        "name": "get_system_info",
        "description": "System info lo — CPU, RAM, disk, OS details.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_clipboard",
        "description": "Clipboard ka content padhke batao.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "set_clipboard",
        "description": "Kuch bhi clipboard mein copy karo.",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to copy to clipboard"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "create_website",
        "description": (
            "Poora website banao HTML/CSS/JS se aur browser mein kholo. "
            "Landing pages, portfolios, tools, dashboards — kuch bhi. "
            "Agar user website banana chahta hai toh yeh tool use karo."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name":         {"type": "string", "description": "Website/project name"},
                "description":  {"type": "string", "description": "What the website is about"},
                "html_content": {"type": "string", "description": "Complete HTML content"},
                "css_content":  {"type": "string", "description": "CSS styles (optional, can be inline)"},
                "js_content":   {"type": "string", "description": "JavaScript code (optional)"},
                "output_dir":   {"type": "string", "description": "Where to save website files"},
                "open_browser": {"type": "boolean", "description": "Open in browser after creating? (default true)"}
            },
            "required": ["name", "html_content"]
        }
    },
    {
        "name": "run_python",
        "description": (
            "Python code seedha run karo. Scripts, data processing, automation, "
            "calculations, file manipulation — kuch bhi Python se karo."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "code":    {"type": "string", "description": "Python code to execute"},
                "timeout": {"type": "integer", "description": "Timeout in seconds (default 30)"}
            },
            "required": ["code"]
        }
    },
    {
        "name": "install_package",
        "description": "pip se koi bhi Python package install karo.",
        "parameters": {
            "type": "object",
            "properties": {
                "package": {"type": "string", "description": "Package name, e.g. 'requests', 'pandas', 'flask'"}
            },
            "required": ["package"]
        }
    },
    {
        "name": "get_datetime",
        "description": "Aaj ki date aur time batao.",
        "parameters": {
            "type": "object",
            "properties": {
                "format": {"type": "string", "description": "strftime format string (default '%Y-%m-%d %H:%M:%S')"}
            },
            "required": []
        }
    },
    {
        "name": "open_file",
        "description": "Koi bhi file iske default app mein kholo (PDF, image, video, document, etc.)",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to open"}
            },
            "required": ["path"]
        }
    },
    {
        "name": "find_files",
        "description": "Files dhundo — naam se, extension se, ya pattern se.",
        "parameters": {
            "type": "object",
            "properties": {
                "directory":   {"type": "string", "description": "Where to search (default home dir)"},
                "pattern":     {"type": "string", "description": "Glob pattern e.g. '*.py', '*.pdf', 'project*'"},
                "max_results": {"type": "integer", "description": "Max results (default 50)"}
            },
            "required": []
        }
    },
    {
        "name": "zip_files",
        "description": "Files ya folders ko ZIP mein compress karo.",
        "parameters": {
            "type": "object",
            "properties": {
                "files":  {"type": "array", "items": {"type": "string"}, "description": "List of file/folder paths"},
                "output": {"type": "string", "description": "Output ZIP file path"}
            },
            "required": ["files", "output"]
        }
    },
    {
        "name": "get_weather",
        "description": "Kisi city ka weather batao.",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name, e.g. 'Delhi', 'Mumbai', 'New York'"}
            },
            "required": ["city"]
        }
    },
    {
        "name": "send_notification",
        "description": "Desktop notification bhejo.",
        "parameters": {
            "type": "object",
            "properties": {
                "title":   {"type": "string", "description": "Notification title"},
                "message": {"type": "string", "description": "Notification message"}
            },
            "required": ["title", "message"]
        }
    },
    {
        "name": "work_mode",
        "description": (
            "Ek hi command par poora work environment ready karo — multiple "
            "apps aur tabs ek saath background mein launch karke, phir "
            "windows ko screen par arrange karo. E.g. 'coding' profile "
            "VS Code + Chrome + GitHub + Terminal + Spotify sab kholta hai. "
            "Available profiles: 'coding', 'study', 'meeting', 'design'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "profile": {"type": "string", "description": "Work profile name, e.g. 'coding', 'study', 'meeting', 'design'"}
            },
            "required": ["profile"]
        }
    },
    {
        "name": "whatsapp_send",
        "description": (
            "WhatsApp Web ke through message bhejo (pywhatkit se, koi "
            "browser scraping nahi). Naam bologe (contact_name) toh saved "
            "contacts mein se number khud dhoond legi — number bolna zaroori "
            "nahi. Naya contact ho toh phone_number seedha bhi de sakte ho, "
            "international format mein (e.g. '+919876543210'). send_at "
            "optional hai — diya toh 'HH:MM' 24-hour format mein schedule "
            "ho jayega, warna turant bhej dega."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "contact_name": {"type": "string", "description": "Saved contact's name — resolves to their number automatically"},
                "phone_number": {"type": "string", "description": "International format phone number, e.g. '+919876543210' — use if no saved contact"},
                "message":      {"type": "string", "description": "Message text to send"},
                "send_at":      {"type": "string", "description": "Optional 'HH:MM' 24-hour time to schedule the send"}
            },
            "required": ["message"]
        }
    },
    {
        "name": "add_contact",
        "description": "Ek contact save karo (naam + number) taaki aage se WhatsApp message sirf naam bol kar bhej sako.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Contact's name"},
                "phone_number": {"type": "string", "description": "International format, e.g. '+919876543210'"}
            },
            "required": ["name", "phone_number"]
        }
    },
    {
        "name": "list_contacts",
        "description": "Saare saved contacts (naam + number) dikhao.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "open_games_hub",
        "description": "Built-in Games Hub kholo — HTML5 Snake, Tetris, aur trivia quiz, sab local dashboard ke andar, koi external ROM/emulator nahi chahiye.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "read_screen",
        "description": (
            "Abhi ka screenshot lo aur Gemini Vision ko bhejo taaki ARIA "
            "screen par jo chal raha hai wo dekh aur samajh sake — error "
            "messages padhna, kisi app ki state batana, ya screen ke baare "
            "mein koi specific sawaal ka jawab dena."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "Optional specific question about what's on screen; empty for a general description"}
            },
            "required": []
        }
    },
    {
        "name": "web_search_synthesis",
        "description": (
            "Internet se top websites ka data nikal kar khud analyze karo, "
            "phir ek structured summary do — Overview, Key Points, "
            "Conclusion. Sirf links dikhana nahi, poora synthesis karo."
        ),
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "What to research"}},
            "required": ["query"]
        }
    },
    {
        "name": "recall_memory",
        "description": "Past searches aur actions ki local memory (timeline) mein se dhoondo — 'pichli baar maine kya pucha tha' jaise sawaalon ke liye.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Optional keyword to filter by; empty for most recent events"},
                "limit": {"type": "integer", "description": "Max results, default 10"}
            },
            "required": []
        }
    },
    {
        "name": "clipboard_history",
        "description": "Clipboard history dikhao — recently copied items ki list, index ke saath.",
        "parameters": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "description": "Max entries, default 20"}},
            "required": []
        }
    },
    {
        "name": "clipboard_restore",
        "description": "clipboard_history mein diya gaya koi purana entry (index se) wapas current clipboard mein daalo.",
        "parameters": {
            "type": "object",
            "properties": {"index": {"type": "integer", "description": "Index from clipboard_history output, 0 = most recent"}},
            "required": ["index"]
        }
    },
    {
        "name": "set_reminder",
        "description": "Ek reminder/alarm set karo. Ya to 'at' do (HH:MM 24-hour) ya 'in_minutes' do (relative), dono nahi.",
        "parameters": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Reminder text"},
                "at": {"type": "string", "description": "'HH:MM' 24-hour time today (or tomorrow if already passed)"},
                "in_minutes": {"type": "number", "description": "Minutes from now"}
            },
            "required": ["message"]
        }
    },
    {
        "name": "list_reminders",
        "description": "Saare pending (abhi tak fire nahi hue) reminders dikhao.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "organize_downloads",
        "description": "Downloads folder (ya koi bhi diya gaya folder) ko file-type ke hisaab se automatically subfolders mein sort karo — Images, Documents, Videos, Audio, Archives, Installers, Others.",
        "parameters": {
            "type": "object",
            "properties": {"folder": {"type": "string", "description": "Optional folder path; defaults to the user's Downloads folder"}},
            "required": []
        }
    },
    {
        "name": "debug_error_screenshot",
        "description": (
            "Jab user ke screen par koi code/terminal error dikh raha ho aur "
            "woh bole 'yeh error dekho' ya 'iska solution batao' — screenshot "
            "lekar error padho, root cause batao, aur concrete fix suggest karo."
        ),
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "generate_image",
        "description": "Ek prompt se free AI image generate karo (Pollinations.ai — koi API key nahi chahiye) aur HUD mein dikhao.",
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Description of the image to generate"},
                "width": {"type": "integer", "description": "Image width in pixels, default 1024"},
                "height": {"type": "integer", "description": "Image height in pixels, default 1024"}
            },
            "required": ["prompt"]
        }
    },
    {
        "name": "mobile_device_status",
        "description": "Check karo koi Android phone ADB (USB debugging) ke through connected hai ya nahi.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "mobile_battery_info",
        "description": "Connected phone ki battery/hardware telemetry dikhao.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "mobile_push_file",
        "description": "PC se koi file phone par bhejo (ADB push).",
        "parameters": {
            "type": "object",
            "properties": {
                "local_path": {"type": "string", "description": "File path on this PC"},
                "remote_path": {"type": "string", "description": "Destination path on phone, default '/sdcard/'"}
            },
            "required": ["local_path"]
        }
    },
    {
        "name": "mobile_pull_file",
        "description": "Phone se koi file PC par le aao (ADB pull).",
        "parameters": {
            "type": "object",
            "properties": {
                "remote_path": {"type": "string", "description": "File path on the phone, e.g. '/sdcard/DCIM/photo.jpg'"},
                "local_path": {"type": "string", "description": "Destination folder on this PC, default current folder"}
            },
            "required": ["remote_path"]
        }
    },
    {
        "name": "mobile_open_app",
        "description": "Phone par koi app remotely open karo (package name se, e.g. 'com.whatsapp').",
        "parameters": {
            "type": "object",
            "properties": {"package_name": {"type": "string", "description": "Android package name, e.g. 'com.whatsapp'"}},
            "required": ["package_name"]
        }
    },
    {
        "name": "mobile_close_app",
        "description": "Phone par koi app remotely band (force-stop) karo.",
        "parameters": {
            "type": "object",
            "properties": {"package_name": {"type": "string", "description": "Android package name, e.g. 'com.whatsapp'"}},
            "required": ["package_name"]
        }
    },
    {
        "name": "mobile_tap",
        "description": "Phone screen par ek specific coordinate (x, y) par remotely tap karo.",
        "parameters": {
            "type": "object",
            "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}},
            "required": ["x", "y"]
        }
    },
    {
        "name": "mobile_swipe",
        "description": "Phone screen par ek jagah se doosri jagah swipe karo.",
        "parameters": {
            "type": "object",
            "properties": {
                "x1": {"type": "integer"}, "y1": {"type": "integer"},
                "x2": {"type": "integer"}, "y2": {"type": "integer"},
                "duration_ms": {"type": "integer", "description": "Swipe duration in ms, default 300"}
            },
            "required": ["x1", "y1", "x2", "y2"]
        }
    },
    {
        "name": "mobile_toggle_wifi",
        "description": "Phone ka WiFi remotely on/off karo.",
        "parameters": {
            "type": "object",
            "properties": {"enable": {"type": "boolean", "description": "true = turn on, false = turn off"}},
            "required": ["enable"]
        }
    },
    {
        "name": "mobile_toggle_bluetooth",
        "description": "Phone ka Bluetooth remotely on/off karo.",
        "parameters": {
            "type": "object",
            "properties": {"enable": {"type": "boolean", "description": "true = turn on, false = turn off"}},
            "required": ["enable"]
        }
    },
    {
        "name": "deep_research",
        "description": "Multi-step autonomous research — pehle broad search, phir follow-up gaps identify karke deeper dig karo, phir ek combined final report do.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Research topic/question"}},
            "required": ["query"]
        }
    },
    {
        "name": "set_notion_token",
        "description": "Notion integration token save karo (ek baar setup ke liye).",
        "parameters": {
            "type": "object",
            "properties": {"token": {"type": "string", "description": "Notion internal integration token"}},
            "required": ["token"]
        }
    },
    {
        "name": "notion_read_page",
        "description": "Ek Notion page ka content padho (page integration se shared hona chahiye).",
        "parameters": {
            "type": "object",
            "properties": {"page_id_or_url": {"type": "string", "description": "Notion page URL or ID"}},
            "required": ["page_id_or_url"]
        }
    },
    {
        "name": "notion_query_database",
        "description": "Ek Notion database ke entries dikhao (database integration se shared hona chahiye).",
        "parameters": {
            "type": "object",
            "properties": {
                "database_id_or_url": {"type": "string", "description": "Notion database URL or ID"},
                "limit": {"type": "integer", "description": "Max entries, default 10"}
            },
            "required": ["database_id_or_url"]
        }
    },
    {
        "name": "ingest_codebase",
        "description": "Ek local project folder ko vector-embed karke index banao, taaki consult_oracle se uske baare mein sawaal poochh sako.",
        "parameters": {
            "type": "object",
            "properties": {"folder": {"type": "string", "description": "Absolute path to the project folder"}},
            "required": ["folder"]
        }
    },
    {
        "name": "consult_oracle",
        "description": "Pehle se ingest kiye gaye codebase ke baare mein sawaal poochho — sirf usi codebase ke context se jawab milega.",
        "parameters": {
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "Question about the codebase"},
                "folder": {"type": "string", "description": "The same folder path used in ingest_codebase"}
            },
            "required": ["question", "folder"]
        }
    },
    {
        "name": "lock_system",
        "description": "Is PC ko turant lock kar do (jaise Win+L) — unlock is PC ke apne sign-in method se hoga (PIN/password/Windows Hello).",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },

    # ── System Control ────────────────────────────────────────────────
    {
        "name": "set_volume",
        "description": "System volume ek specific level (0-100) par set karo.",
        "parameters": {"type": "object", "properties": {"level": {"type": "integer", "description": "0-100"}}, "required": ["level"]}
    },
    {
        "name": "mute",
        "description": "System audio mute ya unmute karo.",
        "parameters": {"type": "object", "properties": {"enable": {"type": "boolean", "description": "true = mute, false = unmute"}}, "required": ["enable"]}
    },
    {
        "name": "shutdown_pc",
        "description": "PC shutdown karo (default 30 second delay ke saath, taaki galti se ho jaye toh cancel kar sako).",
        "parameters": {"type": "object", "properties": {"delay_seconds": {"type": "integer", "description": "Default 30"}}, "required": []}
    },
    {
        "name": "restart_pc",
        "description": "PC restart karo (default 30 second delay).",
        "parameters": {"type": "object", "properties": {"delay_seconds": {"type": "integer", "description": "Default 30"}}, "required": []}
    },
    {
        "name": "cancel_shutdown",
        "description": "Pending shutdown/restart cancel karo.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "sleep_pc",
        "description": "PC ko turant sleep/suspend mode mein bhejo.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },

    # ── Window & Process Management ───────────────────────────────────
    {
        "name": "list_processes",
        "description": "Sabse zyada memory use karne wale running processes dikhao.",
        "parameters": {"type": "object", "properties": {"limit": {"type": "integer", "description": "Default 15"}}, "required": []}
    },
    {
        "name": "kill_process",
        "description": "Koi process band karo (naam ya PID se).",
        "parameters": {"type": "object", "properties": {"name_or_pid": {"type": "string"}}, "required": ["name_or_pid"]}
    },
    {
        "name": "list_windows",
        "description": "Saare open windows ke titles dikhao (Windows-only abhi).",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "focus_window",
        "description": "Kisi open window ko focus/activate karo (title match se).",
        "parameters": {"type": "object", "properties": {"title_contains": {"type": "string"}}, "required": ["title_contains"]}
    },
    {
        "name": "minimize_all_windows",
        "description": "Saare windows minimize karo — show desktop.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },

    # ── Input Automation ───────────────────────────────────────────────
    {
        "name": "mouse_move",
        "description": "Mouse cursor ko ek specific screen coordinate par le jao.",
        "parameters": {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}}, "required": ["x", "y"]}
    },
    {
        "name": "mouse_click",
        "description": "Mouse click karo — coordinate diya toh wahan, warna current position par.",
        "parameters": {
            "type": "object",
            "properties": {
                "x": {"type": "integer"}, "y": {"type": "integer"},
                "button": {"type": "string", "description": "'left', 'right', or 'middle'"},
                "double": {"type": "boolean", "description": "true for double-click"}
            },
            "required": []
        }
    },
    {
        "name": "mouse_scroll",
        "description": "Mouse scroll karo — positive = up, negative = down.",
        "parameters": {"type": "object", "properties": {"amount": {"type": "integer"}}, "required": ["amount"]}
    },
    {
        "name": "get_mouse_position",
        "description": "Mouse ki current screen position batao.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "keyboard_type",
        "description": "Currently focused field mein text type karo.",
        "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}
    },
    {
        "name": "keyboard_press",
        "description": "Koi key ya key-combo press karo, e.g. 'enter', 'ctrl+shift+esc'.",
        "parameters": {"type": "object", "properties": {"keys": {"type": "string", "description": "'+'-joined combo, e.g. 'ctrl+c'"}}, "required": ["keys"]}
    },

    # ── File Management ────────────────────────────────────────────────
    {
        "name": "list_files",
        "description": "Ek folder ke files/subfolders list karo.",
        "parameters": {"type": "object", "properties": {"folder": {"type": "string"}}, "required": ["folder"]}
    },
    {
        "name": "search_files",
        "description": "Ek folder (aur uske subfolders) mein pattern se files dhoondo, e.g. '*.pdf'.",
        "parameters": {"type": "object", "properties": {"pattern": {"type": "string"}, "folder": {"type": "string"}}, "required": ["pattern", "folder"]}
    },
    {
        "name": "create_folder",
        "description": "Naya folder banao.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}
    },
    {
        "name": "move_file",
        "description": "File/folder move karo.",
        "parameters": {"type": "object", "properties": {"src": {"type": "string"}, "dest": {"type": "string"}}, "required": ["src", "dest"]}
    },
    {
        "name": "copy_file",
        "description": "File/folder copy karo.",
        "parameters": {"type": "object", "properties": {"src": {"type": "string"}, "dest": {"type": "string"}}, "required": ["src", "dest"]}
    },
    {
        "name": "rename_file",
        "description": "File/folder ka naam change karo.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "new_name": {"type": "string"}}, "required": ["path", "new_name"]}
    },
    {
        "name": "trash_file",
        "description": "File/folder ko Recycle Bin/Trash mein bhejo (permanent delete nahi — recoverable hai).",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}
    },
    {
        "name": "get_file_info",
        "description": "Ek file/folder ka size, type, aur last-modified date batao.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}
    },

    # ── Media & Recording ───────────────────────────────────────────────
    {
        "name": "record_audio",
        "description": "Microphone se audio record karo aur .wav save karo.",
        "parameters": {"type": "object", "properties": {"seconds": {"type": "integer", "description": "Default 10"}}, "required": []}
    },
    {
        "name": "record_screen",
        "description": "Screen record karo (ffmpeg installed hona chahiye).",
        "parameters": {"type": "object", "properties": {"seconds": {"type": "integer", "description": "Default 10"}}, "required": []}
    },
    {
        "name": "play_media_file",
        "description": "Koi media/file uske default app mein khol kar play karo.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}
    },

    # ── Automation & Scheduling ─────────────────────────────────────────
    {
        "name": "schedule_shutdown",
        "description": "PC ko X minutes baad shutdown karne ke liye schedule karo.",
        "parameters": {"type": "object", "properties": {"minutes": {"type": "number"}}, "required": ["minutes"]}
    },
    {
        "name": "schedule_restart",
        "description": "PC ko X minutes baad restart karne ke liye schedule karo.",
        "parameters": {"type": "object", "properties": {"minutes": {"type": "number"}}, "required": ["minutes"]}
    },

    # ── Maintenance & Utility ───────────────────────────────────────────
    {
        "name": "disk_usage_report",
        "description": "Saare drives/partitions ka disk usage dikhao.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "system_uptime",
        "description": "PC kitni der se on hai batao.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "flush_dns",
        "description": "DNS cache flush karo (network issues fix karne ke liye).",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "clear_temp_files",
        "description": "OS ke temp folder se junk files clear karo.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "check_network",
        "description": "Internet aur ARIA ke external services (Gemini, DuckDuckGo, image generation) ka reachability check karo — jab search/image-gen fail ho aur pata na chale ki internet issue hai ya kuch aur.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "play_youtube",
        "description": "YouTube par koi bhi song/video seedha DHOOND KAR PLAY karo (sirf browser kholna nahi) — top result turant chalne lagta hai, user ko khud search/click nahi karna padta.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Song/video name to search and play"}},
            "required": ["query"]
        }
    },
    {
        "name": "play_spotify",
        "description": "Spotify app ko kisi song ke search results par kholta hai. Note: Spotify auto-play (bina click ke) sirf official API login se possible hai, abhi user ko top result khud select karna padega.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Song/artist to search on Spotify"}},
            "required": ["query"]
        }
    },
    {
        "name": "pc_toggle_bluetooth",
        "description": "IS PC/LAPTOP ka apna Bluetooth on/off karo (phone ka nahi — uske liye mobile_toggle_bluetooth use karo). Windows par Administrator rights chahiye ho sakte hain.",
        "parameters": {
            "type": "object",
            "properties": {"enable": {"type": "boolean", "description": "true = on, false = off"}},
            "required": ["enable"]
        }
    },
    {
        "name": "pc_toggle_wifi",
        "description": "IS PC/LAPTOP ka apna WiFi on/off karo (phone ka nahi). Windows par Administrator rights chahiye ho sakte hain.",
        "parameters": {
            "type": "object",
            "properties": {"enable": {"type": "boolean", "description": "true = on, false = off"}},
            "required": ["enable"]
        }
    },
    {
        "name": "set_brightness",
        "description": "Laptop screen ki brightness set karo (0-100). Built-in laptop panel par kaam karta hai, external monitor par nahi.",
        "parameters": {
            "type": "object",
            "properties": {"level": {"type": "integer", "description": "0-100"}},
            "required": ["level"]
        }
    },
    {
        "name": "install_software",
        "description": "Koi bhi software fully automatically install karo (winget se, koi click/wizard nahi) — e.g. 'VS Code install kar do'.",
        "parameters": {
            "type": "object",
            "properties": {"app_name": {"type": "string", "description": "e.g. 'vs code', 'chrome', 'python', 'git', 'spotify'"}},
            "required": ["app_name"]
        }
    },
    {
        "name": "send_my_location",
        "description": "Apni current approximate location (WiFi/IP-based, city-level accuracy — precise GPS nahi) ek saved contact ko WhatsApp par bhejo — emergency contact use case ke liye.",
        "parameters": {
            "type": "object",
            "properties": {"contact_name": {"type": "string", "description": "Saved contact's name"}},
            "required": ["contact_name"]
        }
    },
    {
        "name": "read_recent_emails",
        "description": "Recent emails padho (inbox se). Pehle set_email_credentials se account setup hona chahiye.",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max emails, default 5"},
                "unread_only": {"type": "boolean", "description": "Sirf unread dikhao"}
            },
            "required": []
        }
    },
    {
        "name": "send_email",
        "description": "Email bhejo/draft karo.",
        "parameters": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email address"},
                "subject": {"type": "string"},
                "body": {"type": "string"}
            },
            "required": ["to", "subject", "body"]
        }
    },
    {
        "name": "set_email_credentials",
        "description": "Email account setup karo (ek baar) — address, app password (normal password nahi — Gmail/Outlook account settings se generate karna), aur provider ('gmail' ya 'outlook').",
        "parameters": {
            "type": "object",
            "properties": {
                "address": {"type": "string"},
                "app_password": {"type": "string"},
                "provider": {"type": "string", "description": "'gmail' or 'outlook'"}
            },
            "required": ["address", "app_password"]
        }
    },
    {
        "name": "add_automation_rule",
        "description": (
            "If-this-then-that automation rule banao. trigger_type 'app_opened' (trigger_value = process name jaise 'code.exe') "
            "ya 'time_of_day' (trigger_value = 'HH:MM', daily). action_tool koi bhi existing ARIA tool ka naam ho sakta hai "
            "(e.g. 'open_app', 'send_notification'), action_args uske parameters."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "trigger_type": {"type": "string", "description": "'app_opened' or 'time_of_day'"},
                "trigger_value": {"type": "string", "description": "process name, or 'HH:MM'"},
                "action_tool": {"type": "string", "description": "Name of any existing ARIA tool"},
                "action_args": {"type": "object", "description": "Arguments for that tool"}
            },
            "required": ["trigger_type", "trigger_value", "action_tool"]
        }
    },
    {
        "name": "list_automation_rules",
        "description": "Saare automation rules dikhao.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "delete_automation_rule",
        "description": "Ek automation rule delete karo (id se, jo list_automation_rules mein dikhta hai).",
        "parameters": {
            "type": "object",
            "properties": {"rule_id": {"type": "integer"}},
            "required": ["rule_id"]
        }
    },
    {
        "name": "record_and_summarize_meeting",
        "description": "Meeting/conversation ko record karo (X minutes) aur khatam hone par automatically structured minutes banao (attendees, key points, decisions, action items). Sirf mic se sunti hai — system/loopback audio nahi.",
        "parameters": {
            "type": "object",
            "properties": {"minutes": {"type": "number", "description": "Recording duration in minutes"}},
            "required": ["minutes"]
        }
    },
    {
        "name": "smart_file_search",
        "description": (
            "Natural language file search — jab user kahe 'wo PDF jo pichle hafte download hui thi' "
            "jaisa kuch, uske structured parts nikaal ke ye call karo: keyword, extension, "
            "modified_within_days. Default folders: Desktop/Documents/Downloads/Pictures."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "Text the filename should contain"},
                "extension": {"type": "string", "description": "File type, e.g. 'pdf', 'docx'"},
                "modified_within_days": {"type": "integer", "description": "Only files modified in the last N days"},
                "search_root": {"type": "string", "description": "Optional specific folder instead of the defaults"}
            },
            "required": []
        }
    },
    {
        "name": "set_break_nudges",
        "description": "Proactive break reminders on/off karo — on hone par ARIA khud har ~1 ghante mein ek chhota break-reminder bolegi bina poochhe.",
        "parameters": {
            "type": "object",
            "properties": {"enable": {"type": "boolean"}},
            "required": ["enable"]
        }
    },
]
