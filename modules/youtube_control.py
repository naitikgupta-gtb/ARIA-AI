"""
modules/youtube_control.py — "play any song on YouTube" without the
user picking from search results themselves.

No YouTube Data API key needed: YouTube's search results page embeds a
JSON blob (ytInitialData) in the raw HTML containing video IDs — pull
the first one out with a regex and open that video's watch URL
directly. This is the same technique many "quick YouTube search" tools
use since it needs zero setup/API key.
"""
import re
import urllib.parse
import webbrowser

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def play(query: str) -> str:
    if not query.strip():
        return "❌ What should I search for on YouTube?"

    search_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
    try:
        resp = requests.get(search_url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        return f"❌ Could not reach YouTube: {type(e).__name__}: {e}"

    match = re.search(r'"videoId":"([\w-]{11})"', resp.text)
    if not match:
        # Fallback — at least land on the search results instead of nothing.
        webbrowser.open(search_url)
        return f"⚠️ Couldn't isolate the top result, opened search results for '{query}' instead."

    video_id = match.group(1)
    watch_url = f"https://www.youtube.com/watch?v={video_id}&autoplay=1"
    webbrowser.open(watch_url)
    return f"✅ Playing on YouTube: {query}"
