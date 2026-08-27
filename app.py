"""
app.py — ARIA's single-process backend + frontend server.

Run this (directly, or via launcher.py for the native-window build) and
everything — the web HUD, the websocket bridge to the Gemini engine, and
tool execution — lives in one process on http://127.0.0.1:8765.

    python app.py
"""

import os
import threading
import time

import psutil
from flask import Flask, jsonify, request, send_from_directory
from flask_socketio import SocketIO

import config
from engine_web import run_engine_in_thread
from tools import handle_tool_call
from modules import clipboard_manager
from modules import reminders as reminders_module
from modules import updater
from modules import automation_rules
from modules import proactive_nudges

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="")
app.config["SECRET_KEY"] = os.environ.get("ARIA_SECRET", "aria-local-dev")
# Default max_http_buffer_size is 1MB — a high-res/4K screenshot's base64
# payload can exceed that easily (a raw PNG at 3840x2160 is often
# 1-3MB, larger once base64-encoded), which would silently fail to
# transmit over the socket and break the screenshot/image-gen preview.
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading", max_http_buffer_size=20_000_000)

_engine = None
_engine_thread = None
_engine_lock = threading.Lock()


def _emit(event, payload):
    # Called from the engine's background thread — SocketIO with
    # async_mode="threading" queues this safely for connected clients.
    socketio.emit(event, payload)


@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.route("/games/")
@app.route("/games/<path:subpath>")
def games_hub(subpath=None):
    """Serves the built-in HTML5 Games Hub (Snake, Tetris, trivia quiz).
    No external ROMs/emulators — these are plain static files shipped
    with the app under static/games/."""
    games_dir = os.path.join(STATIC_DIR, "games")
    return send_from_directory(games_dir, subpath or "index.html")


@app.route("/api/key/status")
def key_status():
    return jsonify({
        "configured": config.has_api_key(),
        "masked": config.masked_key(),
        "env_override": bool(os.environ.get("ARIA_API_KEY")),
    })


@app.route("/api/key", methods=["POST"])
def save_key():
    data = request.get_json(force=True, silent=True) or {}
    key = (data.get("key") or "").strip()
    if not key:
        return jsonify({"ok": False, "error": "Key can't be empty"}), 400
    config.set_api_key(key)
    # Auto-start the engine as soon as a key is saved, so the user never
    # has to separately "activate the backend" — saving the key is the
    # one and only setup step.
    global _engine, _engine_thread
    with _engine_lock:
        if _engine is None:
            _engine, _engine_thread = run_engine_in_thread(_emit)
    return jsonify({"ok": True, "masked": config.masked_key()})


@app.route("/api/persona", methods=["GET", "POST"])
def persona_route():
    if request.method == "POST":
        data = request.get_json(force=True, silent=True) or {}
        persona = data.get("persona", "assistant")
        config.set_persona(persona)
        if _engine is not None:
            _engine.request_reconnect()
        return jsonify({"ok": True, "persona": persona})
    return jsonify({"persona": config.get_persona()})


@app.route("/api/voice_mode", methods=["GET", "POST"])
def voice_mode_route():
    if request.method == "POST":
        data = request.get_json(force=True, silent=True) or {}
        mode = data.get("mode", "opposite")
        config.set_voice_mode(mode)
        if _engine is not None:
            _engine.request_reconnect()
        return jsonify({"ok": True, "mode": mode})
    return jsonify({"mode": config.get_voice_mode()})


@app.route("/api/email", methods=["POST"])
def email_route():
    data = request.get_json(force=True, silent=True) or {}
    address = (data.get("address") or "").strip()
    app_password = (data.get("app_password") or "").strip()
    provider = data.get("provider", "gmail")
    if address and app_password:
        config.set_email_credentials(address, app_password, provider)
    return jsonify({"ok": True})


@socketio.on("connect")
def on_connect():
    global _engine, _engine_thread
    # If a key is already configured (returning user), auto-start the
    # engine on connect instead of waiting for a manual ENGAGE click.
    with _engine_lock:
        if _engine is None and config.has_api_key():
            _engine, _engine_thread = run_engine_in_thread(_emit)
    _emit("status", {"state": "connected" if _engine else "idle"})


@socketio.on("start_engine")
def on_start_engine():
    global _engine, _engine_thread
    with _engine_lock:
        if _engine is None:
            _engine, _engine_thread = run_engine_in_thread(_emit)


@socketio.on("stop_engine")
def on_stop_engine():
    global _engine, _engine_thread
    with _engine_lock:
        if _engine is not None:
            _engine.stop()
            _engine = None
            _engine_thread = None
    _emit("status", {"state": "idle"})


@socketio.on("text_command")
def on_text_command(data):
    """The dock text input sends typed commands here — same engine, same
    tools, just text in instead of voice in. Requires the engine to
    already be running (auto-started above once a key is configured)."""
    text = (data.get("text") or "").strip()
    if not text:
        return
    _emit("transcript", {"speaker": "you", "text": text})
    if _engine is None:
        _emit("transcript", {"speaker": "aria", "text": "Engine not running yet — add your API key in Settings first."})
        return
    _engine.send_text(text)


@socketio.on("quick_action")
def on_quick_action(data):
    """Sidebar buttons in the HUD call tools directly, off the socket
    thread, so a slow tool (e.g. a big file op) can't stall the UI."""
    tool_name = data.get("tool")
    args = data.get("args", {})
    call_id = f"ui-{tool_name}"
    _emit("tool_started", {"id": call_id, "name": tool_name, "args": args})

    def _run():
        try:
            result = handle_tool_call(tool_name, args)
        except Exception as e:
            result = f"error: {e}"
        # Full, UNTRUNCATED result — a real screenshot/generated image's
        # base64 payload is hundreds of thousands of characters, and any
        # fixed truncation here silently breaks JSON.parse() on the
        # frontend, which then can't render the image at all.
        _emit("tool_finished", {"id": call_id, "name": tool_name, "result": str(result)})

    threading.Thread(target=_run, daemon=True).start()


def _stats_loop():
    while True:
        try:
            _emit("sysinfo", {"cpu": psutil.cpu_percent(), "ram": psutil.virtual_memory().percent})
        except Exception as e:
            # Without this, a single transient psutil/socketio hiccup
            # kills this bare `while True` loop forever — the Session
            # Core CPU/RAM rings then just stay blank for the rest of
            # the session, with no error visible anywhere.
            print(f"[ARIA] _stats_loop: {type(e).__name__}: {e}")
        time.sleep(2)


def main():
    port = int(os.environ.get("ARIA_PORT", "8765"))
    threading.Thread(target=_stats_loop, daemon=True).start()

    # Background feature threads — run independently of the voice engine
    # so clipboard history / reminders keep working even before ENGAGE.
    clipboard_manager.start_background_watch()
    reminders_module.start_background_scheduler(emit_fn=_emit)

    # If-this-then-that rules — actions dispatch through the same tool
    # handler as everything else, so a rule can trigger any ARIA tool.
    automation_rules.start_background_watcher(executor_fn=handle_tool_call)

    # Proactive break nudges — speaks through whichever engine is
    # currently connected. Looked up lazily (not bound at startup) since
    # the engine may not exist yet, or may reconnect/change over time.
    def _speak_via_engine(text):
        if _engine is not None:
            _engine.send_text(text)
    proactive_nudges.start_background_nudges(speak_fn=_speak_via_engine)

    # Auto-update check — one-shot, non-blocking, never fails startup.
    def _update_check():
        info = updater.check_for_update()
        if info["update_available"]:
            _emit("update_available", info)
    threading.Thread(target=_update_check, daemon=True).start()

    print(f"ARIA server starting on http://127.0.0.1:{port}")
    socketio.run(app, host="127.0.0.1", port=port, allow_unsafe_werkzeug=True, load_dotenv=False)


if __name__ == "__main__":
    main()