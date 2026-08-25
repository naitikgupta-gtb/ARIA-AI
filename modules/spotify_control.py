"""
modules/spotify_control.py — "play a song on Spotify" via voice.

Honest limitation: fully unattended "search AND auto-play the first
result" requires Spotify's Web API with OAuth (the user would have to
register a developer app and log in once) — there's no zero-setup way
to do that, unlike YouTube (which has no auth wall for watching a video).

What this DOES do without any setup: opens the desktop Spotify app
straight to search results for the query via Spotify's own URI
protocol. If Spotify Premium + Web API credentials are set up later
(see set_spotify_credentials), this module is the one place that would
gain true auto-play.
"""
import platform
import subprocess
import urllib.parse


def play(query: str) -> str:
    if not query.strip():
        return "❌ What should I search for on Spotify?"

    uri = f"spotify:search:{urllib.parse.quote(query)}"
    system = platform.system()
    try:
        if system == "Windows":
            import os
            os.startfile(uri)
        elif system == "Darwin":
            subprocess.run(["open", uri])
        elif system == "Linux":
            subprocess.run(["xdg-open", uri])
        else:
            return f"❌ Unsupported OS: {system}"
        return (
            f"✅ Opened Spotify to search results for '{query}'. "
            f"Spotify doesn't allow auto-play-the-first-result without official API "
            f"login setup — pick the track and I'll remember it's queued next time you ask."
        )
    except Exception as e:
        return f"❌ Could not open Spotify: {e}"
