"""
modules/notion_sync.py — Read Notion Reports.

Requirements the user has to set up once, on Notion's side (not
something this code can do for them):
1. Create an internal integration at notion.so/my-integrations → copy
   its "Internal Integration Token"
2. Save it in ARIA (via set_notion_token, exposed as a tool below, or
   the NOTION_TOKEN env var for dev use)
3. Open the specific Notion page/database in the browser → "..." menu
   → "Connect to" → select your integration. Notion's API can ONLY see
   pages explicitly shared with the integration this way — it can't
   silently read someone's whole workspace, by design.
"""
import json

import requests

from config import get_notion_token

API_BASE = "https://api.notion.com/v1"
HEADERS_BASE = {"Notion-Version": "2022-06-28", "Content-Type": "application/json"}


def _headers():
    token = get_notion_token()
    h = dict(HEADERS_BASE)
    h["Authorization"] = f"Bearer {token}"
    return h


import re

def _extract_id(url_or_id: str) -> str:
    """Notion page/database IDs are 32 hex characters, either bare or in
    standard UUID dash-grouping (8-4-4-4-12). URLs put this at the end,
    often prefixed by a page title also joined with dashes, e.g.:
      .../My-Page-Title-a1b2c3d4e5f647890123456789012345
      .../a1b2c3d4-e5f6-4789-a012-345678901234
    A naive "split on '-', take the last piece" breaks the second case,
    since the ID itself contains dashes — it would chop the ID down to
    just its last 12 characters. Using a regex to find the ID pattern
    (allowing optional dashes anywhere within it) handles both forms
    correctly, and strips the dashes since Notion's API accepts either
    dashed or bare 32-char hex ids."""
    tail = url_or_id.strip().split("?")[0].rstrip("/")
    tail = tail.split("/")[-1]

    # A 32-hex-char id, optionally grouped with dashes anywhere within it —
    # find the longest such match at the END of the string.
    match = re.search(r"([0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{12})$", tail)
    if match:
        return match.group(1).replace("-", "")

    # Fallback for the "Title-With-Dashes-<bareid>" case where the bare id
    # itself has no internal dashes — safe to just take the last segment.
    return tail.split("-")[-1]


def query_database(database_id_or_url: str, limit: int = 10) -> str:
    token = get_notion_token()
    if not token:
        return "❌ No Notion token configured — set one via set_notion_token first."

    db_id = _extract_id(database_id_or_url)
    try:
        resp = requests.post(
            f"{API_BASE}/databases/{db_id}/query",
            headers=_headers(), data=json.dumps({"page_size": limit}), timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as e:
        return f"❌ Notion request failed: {e}"

    rows = []
    for page in data.get("results", []):
        title = "Untitled"
        for prop in page.get("properties", {}).values():
            if prop.get("type") == "title" and prop.get("title"):
                title = "".join(t.get("plain_text", "") for t in prop["title"])
                break
        rows.append(title)

    if not rows:
        return "No entries found (or the integration isn't connected to this database yet)."
    return "\n".join(f"- {r}" for r in rows)


def read_page(page_id_or_url: str) -> str:
    token = get_notion_token()
    if not token:
        return "❌ No Notion token configured — set one via set_notion_token first."

    page_id = _extract_id(page_id_or_url)
    try:
        resp = requests.get(
            f"{API_BASE}/blocks/{page_id}/children", headers=_headers(), timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as e:
        return f"❌ Notion request failed: {e}"

    lines = []
    for block in data.get("results", []):
        btype = block.get("type")
        content = block.get(btype, {})
        rich_text = content.get("rich_text", [])
        text = "".join(t.get("plain_text", "") for t in rich_text)
        if text:
            lines.append(text)

    if not lines:
        return "Page has no readable text blocks (or isn't connected to the integration yet)."
    return "\n".join(lines)
