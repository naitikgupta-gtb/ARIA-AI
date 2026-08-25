"""
modules/image_gen.py — Free AI image generation via Pollinations.ai.

No API key, no billing account, no signup — Pollinations.ai exposes a
plain GET endpoint that returns a generated image directly. Quality is
Stable-Diffusion-class, not as strong as Imagen/DALL-E, but it's genuinely
free with no usage limits, which is what was asked for.

If this project later wants sharper quality and is fine paying, swap
this module for Google Imagen or Stability AI — same call shape
(prompt in, base64 PNG out), so nothing else in tools.py/app.js needs
to change.
"""
import base64
import time
import urllib.parse
from pathlib import Path

import requests

SAVE_DIR = Path.home() / ".aria" / "generated_images"
BASE_URL = "https://image.pollinations.ai/prompt/"


def generate(prompt: str, width: int = 1024, height: int = 1024) -> dict:
    """Returns {'ok': bool, 'path': str, 'image_base64': str, 'message': str}."""
    if not prompt.strip():
        return {"ok": False, "message": "❌ Provide a prompt to generate an image from"}

    encoded = urllib.parse.quote(prompt.strip())
    url = f"{BASE_URL}{encoded}?width={width}&height={height}&nologo=true"

    try:
        # First generation can be slow (cold model start on their end) —
        # generous timeout so it doesn't look like a failure.
        resp = requests.get(url, timeout=90)
        resp.raise_for_status()
        img_bytes = resp.content
    except requests.exceptions.SSLError as e:
        return {"ok": False, "message": f"❌ SSL/certificate error reaching Pollinations.ai — often a corporate/college network intercepting HTTPS, or Windows' CA cert store needing an update: {e}"}
    except requests.exceptions.ConnectionError as e:
        return {"ok": False, "message": f"❌ Could not reach Pollinations.ai — check internet connection / firewall / VPN: {e}"}
    except requests.exceptions.Timeout:
        return {"ok": False, "message": "❌ Pollinations.ai timed out — its servers can be slow under load, try again"}
    except requests.exceptions.RequestException as e:
        return {"ok": False, "message": f"❌ Image generation failed: {type(e).__name__}: {e}"}

    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"aria_gen_{int(time.time())}.png"
    path = SAVE_DIR / filename
    path.write_bytes(img_bytes)

    return {
        "ok": True,
        "path": str(path),
        "image_base64": base64.b64encode(img_bytes).decode(),
        "message": f"✅ Image generated and saved: {path}",
    }
