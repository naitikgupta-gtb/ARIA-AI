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
import threading
import time

import webview

from app import app, socketio

main_window = None


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
    time.sleep(1.2)  # give Flask a moment to bind before the windows load it

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
