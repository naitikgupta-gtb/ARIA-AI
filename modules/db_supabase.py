"""
modules/db_supabase.py — Optional cloud sync via Supabase.

ARIA's default memory (modules/memory.py) is a LOCAL SQLite file at
~/.aria/aria_memory.db — fine for a single machine, but it means the
assistant "forgets" on a different device. This module is an OPTIONAL
add-on that mirrors the same timeline events into a Supabase (hosted
Postgres) table, so multiple installs of ARIA can share one memory.

Setup (one-time):
1. Create a free project at https://supabase.com
2. In the Supabase dashboard: Project Settings -> API
     - copy "Project URL"      -> this is SUPABASE_URL
     - copy "anon public" key  -> this is SUPABASE_KEY
3. In the Supabase SQL editor, run:

    create table if not exists aria_timeline (
        id bigint generated always as identity primary key,
        ts double precision not null,
        kind text not null,
        name text,
        args_json text,
        result_summary text,
        device text
    );

4. Store the two values through ARIA's existing per-machine secret
   store (same OS keyring config.py already uses for the Gemini key —
   NOT a plaintext .env file, so it's safe to keep this file in git):

    from config import set_secret
    set_secret("supabase_url", "https://xxxx.supabase.co")
    set_secret("supabase_key", "eyJhbGciOi....")

   (You can wire a small "Supabase URL / Key" pair of fields into the
   existing Settings modal next to the Gemini key field, reusing the
   same set_secret/get_secret plumbing — no new UI pattern needed.)

5. pip install supabase   (add to requirements.txt)

Usage:
    from modules import db_supabase
    db_supabase.log_event("tool_call", "search_web", {"q": "..."}, "3 results")
    db_supabase.recall("weather", limit=10)

If Supabase isn't configured (no url/key set), every function here is
a safe, silent no-op — ARIA keeps working purely on local SQLite.
"""
import json
import time

from config import get_secret

_client = None
_checked = False


def _get_client():
    """Lazily creates and caches the Supabase client. Returns None
    (and only tries once per process) if credentials aren't set or the
    `supabase` package isn't installed — callers should treat that as
    "cloud sync disabled" rather than an error."""
    global _client, _checked
    if _client is not None:
        return _client
    if _checked:
        return None
    _checked = True

    url = get_secret("supabase_url")
    key = get_secret("supabase_key")
    if not url or not key:
        return None

    try:
        from supabase import create_client
        _client = create_client(url, key)
        return _client
    except ImportError:
        print("[ARIA] db_supabase: `supabase` package not installed — run `pip install supabase`.")
        return None
    except Exception as e:
        print(f"[ARIA] db_supabase: failed to create client — {type(e).__name__}: {e}")
        return None


def is_configured() -> bool:
    return _get_client() is not None


def log_event(kind: str, name: str, args: dict | None = None,
              result_summary: str = "", device: str = "") -> None:
    """Mirrors a timeline event to Supabase. No-op if not configured.
    Never raises — a flaky network shouldn't break the calling tool."""
    client = _get_client()
    if not client:
        return
    try:
        client.table("aria_timeline").insert({
            "ts": time.time(),
            "kind": kind,
            "name": name,
            "args_json": json.dumps(args or {}),
            "result_summary": (result_summary or "")[:500],
            "device": device,
        }).execute()
    except Exception as e:
        print(f"[ARIA] db_supabase: log_event failed — {type(e).__name__}: {e}")


def recall(query: str = "", limit: int = 10):
    """Free-text search over the cloud timeline (ilike match on name /
    result_summary), most recent first. Returns [] if not configured
    or on error — never raises."""
    client = _get_client()
    if not client:
        return []
    try:
        q = client.table("aria_timeline").select("*").order("ts", desc=True).limit(limit)
        if query:
            q = q.or_(f"name.ilike.%{query}%,result_summary.ilike.%{query}%")
        return q.execute().data or []
    except Exception as e:
        print(f"[ARIA] db_supabase: recall failed — {type(e).__name__}: {e}")
        return []
