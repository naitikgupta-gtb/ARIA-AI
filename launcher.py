"""
launcher.py — Single entry point for the packaged desktop app.

Starts the Flask/Socket.IO server (app.py) on a background thread,
then opens it in a native OS window via pywebview — so the end user
just double-clicks one .exe and never sees a browser tab, a console
window, or a URL bar. This is the file PyInstaller should target.

Also opens a second, small "Holographic Overlay" widget window —
frameless, transparent, always-on-top, docked in a screen corner —
showing a live mini status core. Clicking it brings the full app to
the front. Both windows share the same running backend/engine.

    python launcher.py
"""

import os
import socket
import threading
import time

import webview

from app import app, socketio

main_window = None


def _wait_for_server(port: int, timeout: float = 30.0) -> bool:
    """Actively polls the port instead of a fixed sleep. A fixed sleep
    (the old `time.sleep(1.2)`) worked on the dev machine but breaks on
    a fresh install elsewhere: PyInstaller's onefile bootloader has to
    extract the whole bundle to a temp dir on first run, antivirus/
    Windows Defender scans that freshly-written unsigned .exe (often
    several seconds), and only then does Flask/SocketIO even start
    binding — all of which can easily exceed 1.2s on a slower or
    colder machine, causing the window to load 127.0.0.1 before
    anything is listening ('refused to connect', with no retry)."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.3)
    return False


class WidgetApi:
    """Exposed to the widget's JS via pywebview's js_api bridge — the
    only thing the tiny overlay window needs to do is bring the main
    window forward when clicked."""

    def focus_main(self):
        if main_window is not None:
            try:
                main_window.restore()
            except Exception:
                pass


def _run_server():
    port = int(os.environ.get("ARIA_PORT", "8765"))
    socketio.run(app, host="127.0.0.1", port=port)


def main():
    global main_window
    port = int(os.environ.get("ARIA_PORT", "8765"))
    t = threading.Thread(target=_run_server, daemon=True)
    t.start()

    if not _wait_for_server(port, timeout=30):
        # Server never came up (crashed on startup, port blocked by
        # another process, etc.) — show a real error instead of a
        # silent/confusing browser 'refused to connect' page.
        webview.create_window(
            "ARIA — Startup Error",
            html=(
                "<body style='background:#05070c;color:#f66;font-family:sans-serif;"
                "padding:40px;'><h2>ARIA failed to start</h2>"
                "<p>The backend server didn't respond within 30 seconds. "
                "This usually means antivirus is blocking it, another app is "
                "using the port, or a required file is missing from this build.</p>"
                "<p>Try: temporarily disable antivirus and retry, or run "
                "<code>ARIA.exe</code> from a Command Prompt window to see the "
                "actual error message.</p></body>"
            ),
            width=600, height=400,
        )
        webview.start()
        return

    main_window = webview.create_window(
        "ARIA — Executive Assistant",
        f"http://127.0.0.1:{port}",
        width=1280,
        height=800,
        min_size=(960, 640),
        background_color="#05070c",
    )

    # Holographic overlay widget — small, frameless, always-on-top,
    # positioned near the top-right corner of the screen. Position is a
    # best-effort default; the user can drag it (easy_drag) to wherever
    # they want and it'll stay there for the session.
    try:
        import ctypes
        screen_w = ctypes.windll.user32.GetSystemMetrics(0)
        widget_x = screen_w - 160
    except Exception:
        widget_x = 1600  # reasonable fallback on non-Windows
    widget_y = 40

    webview.create_window(
        "ARIA Widget",
        f"http://127.0.0.1:{port}/widget.html",
        width=110,
        height=130,
        x=widget_x,
        y=widget_y,
        frameless=True,
        easy_drag=True,
        on_top=True,
        transparent=True,
        background_color="#000000",
        js_api=WidgetApi(),
    )

    webview.start()


if __name__ == "__main__":
    main()
