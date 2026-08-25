"""
modules/media_control.py — Media & Recording.

Audio recording uses `sounddevice` (already a dependency for the voice
engine) — reliable, cross-platform, no extra install.

Screen recording uses `ffmpeg` because doing it well in pure Python is
slow and heavy; ffmpeg is a free, extremely standard tool most
dev-focused users already have. If it's missing, this says so plainly
instead of silently failing.
"""
import platform
import subprocess
import time
from pathlib import Path

MEDIA_DIR = Path.home() / ".aria" / "recordings"


def record_audio(seconds: int = 10) -> str:
    try:
        import sounddevice as sd
        import numpy as np
        import wave
    except ImportError:
        return "⚠️ Install sounddevice + numpy: pip install sounddevice numpy"

    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    path = MEDIA_DIR / f"audio_{int(time.time())}.wav"
    fs = 44100
    try:
        recording = sd.rec(int(seconds * fs), samplerate=fs, channels=1, dtype="int16")
        sd.wait()
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(fs)
            wf.writeframes(recording.tobytes())
        return f"✅ Recorded {seconds}s of audio: {path}"
    except Exception as e:
        return f"❌ {e}"


def record_screen(seconds: int = 10) -> str:
    import shutil as sh
    if not sh.which("ffmpeg"):
        return "⚠️ ffmpeg not found on PATH. Install it from ffmpeg.org (or `winget install ffmpeg` / `brew install ffmpeg`) for screen recording."

    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    path = MEDIA_DIR / f"screen_{int(time.time())}.mp4"
    system = platform.system()
    try:
        if system == "Windows":
            cmd = ["ffmpeg", "-y", "-f", "gdigrab", "-framerate", "30", "-t", str(seconds), "-i", "desktop", str(path)]
        elif system == "Darwin":
            # Screen index varies by machine — "1" is a common default but
            # not guaranteed; if this fails, list devices with
            # `ffmpeg -f avfoundation -list_devices true -i ""` and adjust.
            cmd = ["ffmpeg", "-y", "-f", "avfoundation", "-framerate", "30", "-t", str(seconds), "-i", "1:none", str(path)]
        elif system == "Linux":
            cmd = ["ffmpeg", "-y", "-f", "x11grab", "-framerate", "30", "-t", str(seconds), "-i", ":0.0", str(path)]
        else:
            return f"❌ Unsupported OS: {system}"
        subprocess.run(cmd, capture_output=True, timeout=seconds + 15)
        if path.exists():
            return f"✅ Recorded {seconds}s of screen: {path}"
        return "❌ ffmpeg ran but no output file was produced — check permissions (Screen Recording access on macOS)."
    except Exception as e:
        return f"❌ {e}"


def play_media_file(path: str) -> str:
    system = platform.system()
    try:
        if system == "Windows":
            import os
            os.startfile(path)
        elif system == "Darwin":
            subprocess.run(["open", path])
        elif system == "Linux":
            subprocess.run(["xdg-open", path])
        return f"✅ Playing: {path}"
    except Exception as e:
        return f"❌ {e}"
