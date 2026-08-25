"""
engine_web.py — The realtime voice/tool engine, adapted from aria_engine.py
to emit events over Socket.IO instead of Qt signals, so a browser-based
HUD frontend can drive off the same engine the desktop GUI uses.

Behavior/tool-calling logic is unchanged. `tools.py` remains the single
source of truth for what ARIA can do.
"""

import asyncio
import base64
import json
import os
import queue as _queue
import threading
import time
import traceback

import numpy as np
import sounddevice as sd
import websockets

from prompt import get_full_prompt
from tools import TOOL_DECLARATIONS, handle_tool_call
from config import get_api_key, get_persona, get_voice_mode
from modules.voice_gender import GenderTracker

WS_URL = (
    "wss://generativelanguage.googleapis.com/ws/"
    "google.ai.generativelanguage.v1beta."
    "GenerativeService.BidiGenerateContent"
)

MIC_RATE = 16000
SPK_RATE = 24000
FRAMES = int(MIC_RATE * 10 / 1000)

# Gemini's built-in voices — picking one female-leaning and one
# male-leaning pair for the gender-swap feature. (These are Gemini's
# own real, non-robotic voices — nothing here transforms the user's
# actual voice, see modules/voice_gender.py's docstring.)
FEMALE_VOICE = "Aoede"
MALE_VOICE = "Puck"


# Model fallback list — tried in order. Index 0 is the one that was
# actually confirmed working (establishing sessions, responding) —
# gemini-3.1-flash-live-preview is kept as a fallback only, since it's a
# very new preview model that (as of testing) either isn't enabled for
# this API key yet or is having server-side stability issues — multiple
# other developers hit the exact same immediate 1011 error on it too,
# this is not specific to this app's code.
MODEL_CANDIDATES = [
    "models/gemini-2.5-flash-native-audio-preview-12-2025",
    "models/gemini-3.1-flash-live-preview",
]


def _build_setup(voice_name: str, model: str) -> dict:
    """Built fresh per-session (not a module-level constant) since
    persona, voice, and (on repeated failure) model can change between
    sessions without restarting the whole app."""
    return {
        "setup": {
            "model": model,
            "generation_config": {
                "temperature": 0.7,
                "response_modalities": ["AUDIO"],
                "speech_config": {
                    "voice_config": {"prebuilt_voice_config": {"voice_name": voice_name}}
                },
            },
            "input_audio_transcription": {},
            "output_audio_transcription": {},
            "system_instruction": {"parts": [{"text": get_full_prompt(get_persona())}]},
            "tools": [{"functionDeclarations": TOOL_DECLARATIONS}],
        }
    }


def enc(x):
    return json.dumps(x).encode()


def get_user_transcript(msg: dict) -> str:
    sc = msg.get("serverContent", {})
    t = sc.get("inputTranscription", {})
    if isinstance(t, dict) and t.get("text", "").strip():
        return t["text"].strip()
    t2 = sc.get("inputTranscript", "")
    if isinstance(t2, str) and t2.strip():
        return t2.strip()
    return ""


def _strip_heavy_payload(result) -> str:
    """Tool results shown to the user (screenshots, generated images) can
    contain a large base64 blob under 'image_base64'. Gemini never needs
    that — the HUD already displays the image directly from the raw
    tool_finished emit — so strip it before it goes back over the Live
    API connection. A large-enough function response has been observed
    to close the whole session (see engine_web.py's _recv handler)."""
    result_str = result if isinstance(result, str) else json.dumps(result)
    try:
        parsed = json.loads(result_str)
        if isinstance(parsed, dict) and "image_base64" in parsed:
            parsed = dict(parsed)
            parsed["image_base64"] = "<omitted — already shown to user in the HUD>"
            result_str = json.dumps(parsed)
    except (json.JSONDecodeError, TypeError):
        pass
    return result_str[:4000]


class VoiceSwitchRequested(Exception):
    """Internal control-flow signal — raised when the gender tracker
    decides ARIA's reply voice should flip, so `start()` can reconnect
    immediately with the new voice instead of treating it like a
    dropped-connection error (no backoff delay, no error log)."""


class AriaWebEngine:
    """Same engine as the desktop version, but `emit(event, data)` pushes
    to Socket.IO clients instead of Qt signals. `emit` is injected by
    server.py so this module has no Flask/SocketIO import of its own."""

    def __init__(self, emit_fn):
        self.running = True
        self._ws = None
        self._loop = None
        self.emit = emit_fn  # emit_fn(event_name: str, payload: dict)
        self._current_voice = FEMALE_VOICE
        self._gender_tracker = GenderTracker()
        self._model_index = 0  # index into MODEL_CANDIDATES

    def stop(self):
        self.running = False

    def request_reconnect(self):
        """Closes the current session so `start()`'s loop immediately
        reconnects with a freshly-built setup (new persona/voice) —
        used when the user changes Settings while already connected,
        instead of making them wait for the next natural reconnect."""
        if not self._loop or not self._ws:
            return
        asyncio.run_coroutine_threadsafe(self._ws.close(), self._loop)

    def send_text(self, text: str):
        """Thread-safe entry point for typed commands from the HUD's text
        dock — called from the Flask/SocketIO thread, so it hops onto the
        engine's own asyncio loop via run_coroutine_threadsafe instead of
        touching the websocket directly from another thread."""
        if not self._loop or not self._ws:
            return
        asyncio.run_coroutine_threadsafe(self._send_text_async(text), self._loop)

    async def _send_text_async(self, text: str):
        if not self._ws:
            return
        await self._ws.send(enc({
            "clientContent": {
                "turns": [{"role": "user", "parts": [{"text": text}]}],
                "turnComplete": True,
            }
        }))

    async def start(self):
        self._loop = asyncio.get_event_loop()
        retry = 0
        while self.running:
            attempt_started = time.monotonic()
            try:
                self.emit("status", {"state": "connecting"})
                await self._session()
                retry = 0
            except VoiceSwitchRequested:
                # Not a failure — reconnect immediately with the new voice.
                retry = 0
                continue
            except websockets.exceptions.ConnectionClosedOK:
                # We (or a persona/voice-mode change) closed this cleanly —
                # not a failure either, reconnect right away.
                retry = 0
                continue
            except Exception as e:
                retry += 1
                # If the connection died almost immediately (< 5s — never
                # really got going), the currently-selected model itself is
                # likely the problem (not enabled for this key / having a
                # bad day) — try the next candidate in MODEL_CANDIDATES on
                # the next attempt instead of hammering the same one.
                if time.monotonic() - attempt_started < 5.0 and len(MODEL_CANDIDATES) > 1:
                    self._model_index = (self._model_index + 1) % len(MODEL_CANDIDATES)
                    print(f"[ARIA] switching to fallback model: {MODEL_CANDIDATES[self._model_index]}")
                # Capped low on purpose — a 30s backoff means ARIA looks
                # "dead"/ignoring the user for half a minute after any
                # blip. 2s max keeps a drop imperceptible in a live demo.
                wait = min(1 * retry, 2)
                print(f"[ARIA] connection failed (attempt {retry}): {e!r}")
                traceback.print_exc()
                self.emit("status", {"state": "disconnected", "detail": str(e) or type(e).__name__})
                await asyncio.sleep(wait)

    async def _session(self):
        api_key = get_api_key()
        if not api_key:
            raise RuntimeError("No Gemini API key set — open Settings in the HUD and add your key")

        mode = get_voice_mode()
        if mode == "male":
            self._current_voice = MALE_VOICE
        elif mode in ("female", "off"):
            self._current_voice = FEMALE_VOICE
        # else mode == "opposite" → keep self._current_voice as tracked by
        # the gender-detection logic in _send_audio (defaults to FEMALE_VOICE
        # until a stable flip is detected).

        async with websockets.connect(
            f"{WS_URL}?key={api_key}",
            max_size=None,
            ping_interval=20,
            ping_timeout=30,
            compression=None,
        ) as ws:
            self._ws = ws
            current_model = MODEL_CANDIDATES[self._model_index]
            await ws.send(enc(_build_setup(self._current_voice, current_model)))
            await ws.recv()
            print(f"[ARIA] Gemini Live session established (model: {current_model})")
            self.emit("status", {"state": "connected"})

            audio_q = _queue.Queue()
            play_stop = threading.Event()

            def _play_thread():
                BUF = int(SPK_RATE * 0.20)
                buf = np.array([], dtype=np.float32)
                stream = sd.OutputStream(
                    samplerate=SPK_RATE, channels=1,
                    dtype="float32", blocksize=BUF, latency="high",
                )
                stream.start()
                while not play_stop.is_set():
                    try:
                        chunk = audio_q.get(timeout=0.15)
                        if chunk is None:
                            self.emit("speaking", {"state": False})
                            continue
                        self.emit("speaking", {"state": True})
                        buf = np.concatenate([buf, chunk])
                        while len(buf) >= BUF:
                            stream.write(buf[:BUF])
                            buf = buf[BUF:]
                    except _queue.Empty:
                        self.emit("speaking", {"state": False})
                stream.stop()
                stream.close()

            play_t = threading.Thread(target=_play_thread, daemon=True)
            play_t.start()

            try:
                await asyncio.gather(
                    self._send_audio(ws),
                    self._recv(ws, audio_q),
                )
            finally:
                play_stop.set()
                audio_q.put(None)
                play_t.join(timeout=2.0)

    async def _send_audio(self, ws):
        frames_per_second = max(1, MIC_RATE // FRAMES)
        frame_count = 0

        with sd.InputStream(
            samplerate=MIC_RATE, channels=1,
            dtype="int16", blocksize=FRAMES, latency="low",
        ) as mic:
            while self.running:
                pcm, _ = mic.read(FRAMES)
                level = float(np.abs(pcm).mean()) / 32768.0
                self.emit("mic_level", {"level": min(level * 8.0, 1.0)})

                # Gender-swap voice feature — only does anything when the
                # user has voice_mode set to "opposite" in Settings.
                if get_voice_mode() == "opposite":
                    self._gender_tracker.push_samples(pcm.flatten())
                    frame_count += 1
                    if frame_count >= frames_per_second:
                        frame_count = 0
                        self._gender_tracker.sample_and_classify()
                        stable = self._gender_tracker.stable_gender()
                        if stable:
                            wanted_voice = MALE_VOICE if stable == "female" else FEMALE_VOICE
                            if wanted_voice != self._current_voice:
                                self._current_voice = wanted_voice
                                self.emit("status", {"state": "connecting", "detail": f"Switching to {wanted_voice} voice"})
                                raise VoiceSwitchRequested()

                await ws.send(enc({
                    "realtimeInput": {
                        "audio": {
                            "mimeType": "audio/pcm;rate=16000",
                            "data": base64.b64encode(pcm.tobytes()).decode(),
                        }
                    }
                }))
                await asyncio.sleep(0.001)

    async def _recv(self, ws, audio_q):
        while self.running:
            try:
                raw = await ws.recv()
                msg = json.loads(raw)
            except websockets.exceptions.ConnectionClosed:
                break

            for call in msg.get("toolCall", {}).get("functionCalls", []):
                name = call.get("name", "")
                args = call.get("args", {})
                call_id = call.get("id", "")

                self.emit("tool_started", {"id": call_id, "name": name, "args": args})

                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, handle_tool_call, name, args)

                # Full, UNTRUNCATED result (including any base64 image
                # data) goes to the HUD so screenshots/generated images
                # actually render there — a real screenshot's base64 can
                # be hundreds of thousands of characters, so any fixed
                # truncation here silently breaks image rendering.
                self.emit("tool_finished", {"id": call_id, "name": name, "result": str(result)})

                # Gemini gets a STRIPPED version — sending a few hundred KB
                # of base64 image data back as a function response can blow
                # past the Live API's message size limits and silently kill
                # the whole connection. Gemini only needs to know the tool
                # succeeded, not see the image bytes.
                gemini_result = _strip_heavy_payload(result)

                await ws.send(enc({
                    "toolResponse": {
                        "functionResponses": [{
                            "id": call_id,
                            "name": name,
                            "response": {"result": gemini_result},
                        }]
                    }
                }))

            transcript = get_user_transcript(msg)
            if transcript:
                self.emit("transcript", {"speaker": "you", "text": transcript})

            sc = msg.get("serverContent", {})
            aria_text = sc.get("outputTranscription", {})
            if isinstance(aria_text, dict) and aria_text.get("text", "").strip():
                self.emit("transcript", {"speaker": "aria", "text": aria_text["text"].strip()})

            for part in sc.get("modelTurn", {}).get("parts", []):
                d = part.get("inlineData")
                if d and "audio/pcm" in d.get("mimeType", ""):
                    raw_bytes = base64.b64decode(d["data"])
                    pcm = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
                    try:
                        audio_q.put_nowait(pcm)
                    except Exception:
                        pass


def run_engine_in_thread(emit_fn):
    engine = AriaWebEngine(emit_fn)

    def _runner():
        asyncio.run(engine.start())

    t = threading.Thread(target=_runner, daemon=True)
    t.start()
    return engine, t
