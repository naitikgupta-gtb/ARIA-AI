"""
modules/vision.py — Screen Reading & Action ("Desktop Eyes").

Takes an instant screenshot and sends it to Gemini's vision-capable
model (a plain REST call to generateContent — separate from the
realtime audio websocket the voice engine uses) so ARIA can describe
what's on screen or answer questions about it ("what does this error
say?", "click here" localisation, etc).

Kept as a small standalone REST call (via `requests`) rather than a
heavier SDK dependency, since this is the only place that needs it.
"""
import base64
import io
import json

import requests

from config import get_api_key

VISION_MODEL = "gemini-2.5-flash"  # gemini-2.0-flash was retired by Google on 2026-06-01; 2.5-flash is the official migration target (itself scheduled to retire 2026-10-16 - re-check ai.google.dev/gemini-api/docs/changelog before then)
VISION_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{VISION_MODEL}:generateContent"
)


def _screenshot_bytes() -> bytes:
    import pyautogui
    img = pyautogui.screenshot()
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def read_screen(question: str = "") -> str:
    """Screenshots the desktop right now and asks Gemini Vision to
    describe it / answer a specific question about what's visible."""
    api_key = get_api_key()
    if not api_key:
        return "❌ No Gemini API key configured — add one in Settings first."

    try:
        img_bytes = _screenshot_bytes()
    except ImportError:
        return "⚠️ Install pyautogui: pip install pyautogui"
    except Exception as e:
        return f"❌ Could not capture screen: {e}"

    prompt = question.strip() or (
        "Describe what's currently visible on this screen — what app is "
        "open, what the user is doing, and anything that looks like an "
        "error, notification, or actionable item. Be concise."
    )
    return _ask_vision(img_bytes, prompt)


def debug_code_error() -> str:
    """Screenshots the desktop and asks Gemini Vision to specifically
    diagnose a code/terminal error visible on screen — the 'screenshot
    my error, ARIA explains and fixes it' workflow."""
    api_key = get_api_key()
    if not api_key:
        return "❌ No Gemini API key configured — add one in Settings first."

    try:
        img_bytes = _screenshot_bytes()
    except ImportError:
        return "⚠️ Install pyautogui: pip install pyautogui"
    except Exception as e:
        return f"❌ Could not capture screen: {e}"

    prompt = (
        "There is a code editor, terminal, or IDE visible in this screenshot "
        "showing an error, traceback, or stack trace. Read it carefully and answer in this structure:\n"
        "1. What the error is (in plain words)\n"
        "2. The most likely root cause\n"
        "3. A concrete fix — exact code/command changes if you can tell from what's visible\n"
        "If no error is actually visible, say so plainly instead of guessing."
    )
    return _ask_vision(img_bytes, prompt)


def _ask_vision(img_bytes: bytes, prompt: str) -> str:
    api_key = get_api_key()
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": "image/png", "data": base64.b64encode(img_bytes).decode()}},
            ]
        }]
    }
    try:
        resp = requests.post(
            f"{VISION_URL}?key={api_key}",
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return text.strip()
    except requests.exceptions.RequestException as e:
        return f"❌ Vision request failed: {e}"
    except (KeyError, IndexError):
        return "❌ Vision API returned an unexpected response."