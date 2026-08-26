"""
modules/network_check.py — Self-diagnostic for "search/image-gen isn't
working, is it internet or is it ARIA?" moments — especially useful to
run live during a demo instead of guessing.
"""
import time

import requests

from config import get_api_key

# Plain reachability checks — any HTTP response (even an error page) means
# the network path to that host is open, so these just test connectivity.
CHECKS = [
    ("Google DNS", "https://8.8.8.8"),
    ("Google.com", "https://www.google.com"),
    ("DuckDuckGo (used for search)", "https://html.duckduckgo.com"),
    ("Pollinations.ai (used for image generation)", "https://image.pollinations.ai"),
]


def _check_gemini_api() -> str:
    """The Gemini API domain has no homepage — a bare GET to
    https://generativelanguage.googleapis.com/ always returns 404 even
    when everything is working perfectly, which used to make this
    checker cry wolf every single time. Hit a real, lightweight
    endpoint (list models) with the actual configured key instead, so
    the status code is an actual signal: 200 = key+network both fine,
    400/403 = key itself is invalid/expired, anything else = network
    issue reaching Google at all."""
    label = "Gemini API"
    api_key = get_api_key()
    if not api_key:
        return f"⚠️ {label}: skipped — no API key configured in Settings yet."
    try:
        start = time.time()
        resp = requests.get(
            "https://generativelanguage.googleapis.com/v1beta/models",
            params={"key": api_key}, timeout=6,
        )
        ms = int((time.time() - start) * 1000)
        if resp.status_code == 200:
            return f"✅ {label}: reachable, key is valid ({ms}ms)"
        if resp.status_code in (400, 403):
            return f"❌ {label}: reachable, but the API key was rejected (HTTP {resp.status_code}) — check/replace it in Settings."
        return f"⚠️ {label}: reachable but returned HTTP {resp.status_code} — unexpected, may be a temporary Google-side issue."
    except requests.exceptions.SSLError as e:
        return f"❌ {label}: SSL/certificate error — {type(e).__name__}"
    except requests.exceptions.ConnectionError:
        return f"❌ {label}: unreachable (blocked/no route)"
    except requests.exceptions.Timeout:
        return f"❌ {label}: timed out"
    except Exception as e:
        return f"❌ {label}: {type(e).__name__}: {e}"


def check_network() -> str:
    lines = [_check_gemini_api()]
    any_ok = lines[0].startswith("✅")
    for label, url in CHECKS:
        try:
            start = time.time()
            resp = requests.get(url, timeout=6)
            ms = int((time.time() - start) * 1000)
            lines.append(f"✅ {label}: reachable ({resp.status_code}, {ms}ms)")
            any_ok = True
        except requests.exceptions.SSLError as e:
            lines.append(f"❌ {label}: SSL/certificate error — {type(e).__name__}")
        except requests.exceptions.ConnectionError:
            lines.append(f"❌ {label}: unreachable (blocked/no route)")
        except requests.exceptions.Timeout:
            lines.append(f"❌ {label}: timed out")
        except Exception as e:
            lines.append(f"❌ {label}: {type(e).__name__}: {e}")

    verdict = (
        "\n\nVerdict: internet works, but a specific service above is blocked/down."
        if any_ok else
        "\n\nVerdict: nothing is reachable — this PC has no internet access right now "
        "(check WiFi/Ethernet, or a firewall/VPN/campus network blocking outbound HTTPS)."
    )
    return "\n".join(lines) + verdict