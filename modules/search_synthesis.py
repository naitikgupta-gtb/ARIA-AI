"""
modules/search_synthesis.py — AI Search Combo (Live Synthesis).

Pulls raw text from the top web results for a query, then asks Gemini
to synthesize a structured Overview / Key Points / Conclusion summary
instead of just dumping links — a "let the AI read the internet for
you" combo search.
"""
import json
import re
from urllib.parse import parse_qs, unquote, urlparse

import requests
from bs4 import BeautifulSoup

from config import get_api_key

TEXT_MODEL = "gemini-2.5-flash"  # gemini-2.0-flash was retired by Google on 2026-06-01; 2.5-flash is the official migration target (itself scheduled to retire 2026-10-16 - re-check ai.google.dev/gemini-api/docs/changelog before then)
TEXT_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{TEXT_MODEL}:generateContent"

# A full, browser-like header set. DuckDuckGo's HTML endpoint is quick to
# serve an "unusual traffic" / CAPTCHA page to requests that only send a
# User-Agent — Accept, Accept-Language and Referer noticeably cut down on
# that. This was the main reason the old scraper silently returned zero
# results (it caught the failure but had nothing useful to show for it).
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://duckduckgo.com/",
}


def _unwrap_ddg_link(href: str) -> str:
    """DuckDuckGo's HTML results often wrap the real URL behind a
    redirect like //duckduckgo.com/l/?uddg=<encoded-url>&rut=... .
    requests would normally follow that redirect fine on its own, but
    some of DDG's redirect pages are JS/meta-refresh based instead of a
    real 302, which silently breaks _fetch_page_text(). Unwrap it
    ourselves so we always hit the real target directly."""
    if not href:
        return href
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlparse(href)
    if "duckduckgo.com" in parsed.netloc and parsed.path == "/l/":
        qs = parse_qs(parsed.query)
        real = qs.get("uddg", [""])[0]
        if real:
            return unquote(real)
    return href


def _parse_results(html: str, max_results: int):
    soup = BeautifulSoup(html, "html.parser")
    results = []
    for r in soup.select(".result")[:max_results]:
        link_el = r.select_one(".result__a")
        snippet_el = r.select_one(".result__snippet")
        if link_el:
            results.append({
                "title": link_el.get_text(strip=True),
                "url": _unwrap_ddg_link(link_el.get("href", "")),
                "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
            })
    return results


def _fetch_top_results(query: str, max_results: int = 5):
    """Scrapes DuckDuckGo for the top result links + snippets (no API
    key needed). Tries the full HTML endpoint first, then falls back to
    the lighter lite.duckduckgo.com endpoint (different markup, and
    sometimes reachable when the main one is rate-limiting an IP).
    Best-effort — if both fail it's skipped, not fatal, but we now log
    *why* instead of swallowing it silently."""
    endpoints = [
        ("https://html.duckduckgo.com/html/", "post"),
        ("https://lite.duckduckgo.com/lite/", "post"),
    ]
    last_error = None
    for url, method in endpoints:
        try:
            if method == "post":
                resp = requests.post(url, data={"q": query}, headers=HEADERS, timeout=10)
            else:
                resp = requests.get(url, params={"q": query}, headers=HEADERS, timeout=10)

            if resp.status_code != 200:
                last_error = f"HTTP {resp.status_code} from {url}"
                print(f"[ARIA] search_synthesis: {last_error}")
                continue

            if "anomaly" in resp.text.lower() or "unusual traffic" in resp.text.lower():
                last_error = f"{url} served a bot-check page instead of results"
                print(f"[ARIA] search_synthesis: {last_error}")
                continue

            results = _parse_results(resp.text, max_results)
            if results:
                return results
            last_error = f"{url} returned 200 but no parseable results (markup may have changed)"
            print(f"[ARIA] search_synthesis: {last_error}")
        except requests.exceptions.RequestException as e:
            last_error = f"{type(e).__name__}: {e}"
            print(f"[ARIA] search_synthesis: fetch from {url} failed — {last_error}")

    if last_error:
        print(f"[ARIA] search_synthesis: all search endpoints failed, last error: {last_error}")
    return []


def _fetch_page_text(url: str, max_chars: int = 2000) -> str:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=8)
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = " ".join(soup.get_text(" ").split())
        return text[:max_chars]
    except Exception:
        return ""


def synthesize(query: str) -> str:
    api_key = get_api_key()
    if not api_key:
        return "❌ No Gemini API key configured — add one in Settings first."

    results = _fetch_top_results(query)
    if not results:
        return (
            f"❌ Couldn't fetch web results for '{query}' from either DuckDuckGo endpoint. "
            "This usually means: (1) DuckDuckGo is showing a bot-check page to this "
            "network/IP right now (common on cloud/VPS or shared IPs, or after too many "
            "quick requests) — try 'check network connection' to confirm internet works "
            "at all, then retry in a minute; or (2) an SSL/firewall issue on this network. "
            "Check the console log for the exact reason (HTTP status / bot-check / markup "
            "change) — it's printed there now instead of being hidden."
        )

    sources_text = []
    for r in results:
        page_text = _fetch_page_text(r["url"]) or r["snippet"]
        sources_text.append(f"SOURCE: {r['title']} ({r['url']})\n{page_text}")

    combined = "\n\n---\n\n".join(sources_text)
    prompt = (
        f"Based only on the following web sources, answer the query: '{query}'.\n\n"
        f"{combined}\n\n"
        "Respond in exactly this structure with these three headers:\n"
        "Overview: (2-3 sentence high-level answer)\n"
        "Key Points: (3-5 bullet points, one per line starting with '- ')\n"
        "Conclusion: (1-2 sentence takeaway)\n"
        "Do not quote sources verbatim — paraphrase everything in your own words."
    )

    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        resp = requests.post(
            f"{TEXT_URL}?key={api_key}",
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload), timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        summary = data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except requests.exceptions.RequestException as e:
        return f"❌ Synthesis request failed: {e}"
    except (KeyError, IndexError):
        return "❌ Synthesis API returned an unexpected response."

    sources_list = "\n".join(f"- {r['title']}: {r['url']}" for r in results)
    return f"{summary}\n\nSources:\n{sources_list}"