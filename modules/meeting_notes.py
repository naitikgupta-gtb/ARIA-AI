"""
modules/meeting_notes.py — Meeting Notes Auto-Summary.

Records audio from the default microphone (same mechanism as
media_control.record_audio) for the meeting's duration, then sends the
recording to Gemini (a plain REST generateContent call, audio input —
separate from the realtime voice websocket) asking for structured
minutes: Attendees mentioned, Key Discussion Points, Decisions,
Action Items.

Honest limitation: this only captures what the MICROPHONE hears — for
an online meeting (Zoom/Teams), that means it captures whatever plays
out of the speakers AND picks up nearby voices, same as recording a
room with a phone. It does not tap system/loopback audio directly,
which would need a virtual audio cable — a real extra setup step.
"""
import base64
import json
import time
import wave
from pathlib import Path

import requests

from config import get_api_key

MEETING_DIR = Path.home() / ".aria" / "meetings"
TEXT_MODEL = "gemini-2.0-flash"
GEN_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{TEXT_MODEL}:generateContent"


def record_and_summarize(minutes: float) -> str:
    try:
        import sounddevice as sd
    except ImportError:
        return "⚠️ Install sounddevice: pip install sounddevice"

    api_key = get_api_key()
    if not api_key:
        return "❌ No Gemini API key configured — add one in Settings first."

    MEETING_DIR.mkdir(parents=True, exist_ok=True)
    path = MEETING_DIR / f"meeting_{int(time.time())}.wav"
    fs = 16000
    seconds = max(10, int(minutes * 60))

    try:
        recording = sd.rec(int(seconds * fs), samplerate=fs, channels=1, dtype="int16")
        sd.wait()
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(fs)
            wf.writeframes(recording.tobytes())
    except Exception as e:
        return f"❌ Recording failed: {e}"

    return summarize_recording(str(path))


def summarize_recording(path: str) -> str:
    api_key = get_api_key()
    if not api_key:
        return "❌ No Gemini API key configured — add one in Settings first."

    audio_bytes = Path(path).read_bytes()
    prompt = (
        "This is an audio recording of a meeting or conversation. Listen to it and produce "
        "structured minutes with exactly these headers:\n"
        "Attendees Mentioned: (names/roles referenced, if any)\n"
        "Key Discussion Points: (bulleted)\n"
        "Decisions Made: (bulleted, or 'None' if none)\n"
        "Action Items: (bulleted, with owner if mentioned)\n"
        "Keep it concise — paraphrase, don't transcribe verbatim."
    )
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": "audio/wav", "data": base64.b64encode(audio_bytes).decode()}},
            ]
        }]
    }
    try:
        resp = requests.post(
            f"{GEN_URL}?key={api_key}",
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload), timeout=90,
        )
        resp.raise_for_status()
        data = resp.json()
        summary = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        return f"{summary}\n\n(Full recording saved: {path})"
    except requests.exceptions.RequestException as e:
        return f"❌ Summarization failed: {type(e).__name__}: {e}"
    except (KeyError, IndexError):
        return "❌ Gemini returned an unexpected response for the audio summary."
