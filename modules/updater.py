"""
modules/updater.py — Auto-update checker.

ARIA has a version number (CURRENT_VERSION below). On startup, this
does one lightweight HTTP GET to a JSON manifest URL you control (host
it anywhere — GitHub raw, S3, your own site) and compares versions. If
newer, it just tells the user — this checker does NOT auto-download or
auto-install anything, that's a separate step you'd add later once you
have real customers and want it fully automatic.

Point ARIA_UPDATE_URL (env var) at your own manifest, shaped like:
{
  "latest_version": "1.1.0",
  "notes": "Added work mode + games hub",
  "download_url": "https://yoursite.com/downloads/ARIA_Setup_1.1.0.exe"
}
If unset, update checks are skipped entirely (not an error) — this is
meant to be wired up once you have a real hosting URL.
"""
import os

import requests

CURRENT_VERSION = "1.1.0"


def _parse(v: str):
    try:
        return tuple(int(x) for x in v.strip().split("."))
    except Exception:
        return (0,)


def check_for_update() -> dict:
    """Returns {'update_available': bool, 'current': str, 'latest': str|None,
    'notes': str, 'download_url': str} — never raises, always safe to call."""
    manifest_url = os.environ.get("ARIA_UPDATE_URL", "").strip()
    result = {
        "update_available": False,
        "current": CURRENT_VERSION,
        "latest": None,
        "notes": "",
        "download_url": "",
    }
    if not manifest_url:
        return result  # no manifest configured yet — silently skip

    try:
        resp = requests.get(manifest_url, timeout=6)
        resp.raise_for_status()
        data = resp.json()
        latest = str(data.get("latest_version", "")).strip()
        result["latest"] = latest
        result["notes"] = data.get("notes", "")
        result["download_url"] = data.get("download_url", "")
        if latest and _parse(latest) > _parse(CURRENT_VERSION):
            result["update_available"] = True
    except Exception:
        pass  # no internet, manifest down, etc — fail silently, never blocks startup

    return result
