"""
modules/research_agent.py — Autonomous Deep Research.

Note on scope: this uses your existing Gemini API key for the
reasoning steps, NOT a locally-run Llama 3. Running Llama 3 locally
would need Ollama installed plus a GPU with real VRAM (8GB+ to get
usable speed), and would reason noticeably worse than Gemini for an
agentic multi-step task like this. Same result, zero extra hardware —
if true offline/local-only reasoning is a hard requirement later, this
is the one function that would need swapping.

Approach: round 1 gathers + synthesizes top results for the original
query (reusing search_synthesis). Gemini then reads that synthesis and
proposes 1-2 follow-up questions it still needs answered. Round 2
gathers those. A final Gemini call combines everything into one report.
"""
import json

import requests

from config import get_api_key
from modules import search_synthesis

TEXT_MODEL = "gemini-2.5-flash"  # gemini-2.0-flash was retired by Google on 2026-06-01; 2.5-flash is the official migration target (itself scheduled to retire 2026-10-16 - re-check ai.google.dev/gemini-api/docs/changelog before then)
TEXT_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{TEXT_MODEL}:generateContent"


def _ask_gemini(prompt: str) -> str:
    api_key = get_api_key()
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    resp = requests.post(
        f"{TEXT_URL}?key={api_key}",
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload), timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()


def deep_research(query: str) -> str:
    if not get_api_key():
        return "❌ No Gemini API key configured — add one in Settings first."

    # Round 1 — broad synthesis on the original query.
    round1 = search_synthesis.synthesize(query)
    if round1.startswith("❌"):
        return round1

    # Ask Gemini what's still missing / worth digging into further.
    try:
        followups_raw = _ask_gemini(
            f"Given this initial research summary for the query '{query}':\n\n{round1}\n\n"
            "Suggest exactly 2 short, specific follow-up search queries that would fill "
            "gaps or add depth. Reply with just the 2 queries, one per line, no numbering."
        )
        followups = [q.strip() for q in followups_raw.splitlines() if q.strip()][:2]
    except Exception:
        followups = []

    # Round 2 — dig into each follow-up.
    round2_parts = []
    for fq in followups:
        r = search_synthesis.synthesize(fq)
        if not r.startswith("❌"):
            round2_parts.append(f"Follow-up: {fq}\n{r}")

    if not round2_parts:
        return round1  # follow-ups failed/unavailable — first round is still a real answer

    combined_prompt = (
        f"Original query: {query}\n\n"
        f"Initial research:\n{round1}\n\n"
        f"Follow-up research:\n" + "\n\n".join(round2_parts) + "\n\n"
        "Write one final combined report with headers Overview, Key Points, "
        "Conclusion — merge everything above into a single coherent answer, "
        "don't just concatenate. Paraphrase, don't quote sources verbatim."
    )
    try:
        final_report = _ask_gemini(combined_prompt)
    except Exception:
        # Combination step failed — still return what we have rather than nothing.
        return round1 + "\n\n" + "\n\n".join(round2_parts)

    return final_report