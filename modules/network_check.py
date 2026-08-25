"""
modules/network_check.py — Self-diagnostic for "search/image-gen isn't
working, is it internet or is it ARIA?" moments — especially useful to
run live during a demo instead of guessing.
"""
import time

import requests

CHECKS = [
    ("Google DNS", "https://8.8.8.8"),
    ("Google.com", "https://www.google.com"),
    ("Gemini API", "https://generativelanguage.googleapis.com"),
    ("DuckDuckGo (used for search)", "https://html.duckduckgo.com"),
    ("Pollinations.ai (used for image generation)", "https://image.pollinations.ai"),
]


def check_network() -> str:
    lines = []
    any_ok = False
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
