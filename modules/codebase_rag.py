"""
modules/codebase_rag.py — Ingest Codebase + Consult Oracle (local RAG).

Walks a project folder, chunks its text files, embeds each chunk via
Gemini's embedding endpoint, and stores the vectors locally (a plain
JSON file per project — no separate vector-DB server to run). Querying
does a cosine-similarity search over those vectors, then asks Gemini
to answer using only the top matching chunks as context.

Kept dependency-light on purpose: numpy (already a requirement) instead
of adding chromadb/faiss, since a JSON + numpy cosine search is plenty
fast for a single developer's codebase (thousands, not millions, of
chunks) and is one less native library PyInstaller has to bundle.
"""
import hashlib
import json
from pathlib import Path

import numpy as np
import requests

from config import get_api_key

EMBED_MODEL = "gemini-embedding-001"  # text-embedding-004 was retired by Google on 2026-01-14; this is the official replacement (note: 3072-dim output vs the old model's 768-dim, but nothing here hardcodes a dimension so that's not an issue)
EMBED_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{EMBED_MODEL}:embedContent"
TEXT_MODEL = "gemini-2.5-flash"  # gemini-2.0-flash was retired by Google on 2026-06-01; 2.5-flash is the official migration target (itself scheduled to retire 2026-10-16 - re-check ai.google.dev/gemini-api/docs/changelog before then)
TEXT_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{TEXT_MODEL}:generateContent"

STORE_DIR = Path.home() / ".aria" / "codebase_index"

CODE_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs", ".c", ".cpp", ".h",
                    ".cs", ".rb", ".php", ".html", ".css", ".md", ".json", ".yaml", ".yml"}
SKIP_DIRS = {"node_modules", "venv", ".venv", "__pycache__", ".git", "dist", "build", ".next"}
CHUNK_LINES = 60


def _project_key(folder: str) -> str:
    return hashlib.sha1(str(Path(folder).resolve()).encode()).hexdigest()[:16]


def _embed(text: str) -> list:
    api_key = get_api_key()
    payload = {"content": {"parts": [{"text": text[:8000]}]}}
    resp = requests.post(f"{EMBED_URL}?key={api_key}", data=json.dumps(payload),
                          headers={"Content-Type": "application/json"}, timeout=20)
    resp.raise_for_status()
    return resp.json()["embedding"]["values"]


def _chunk_file(path: Path):
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return []
    return [
        "\n".join(lines[i:i + CHUNK_LINES])
        for i in range(0, len(lines), CHUNK_LINES) if lines[i:i + CHUNK_LINES]
    ]


def ingest_codebase(folder: str) -> str:
    if not get_api_key():
        return "❌ No Gemini API key configured — add one in Settings first."

    root = Path(folder)
    if not root.is_dir():
        return f"❌ Folder not found: {folder}"

    chunks = []
    for path in root.rglob("*"):
        if path.is_dir() or path.suffix.lower() not in CODE_EXTENSIONS:
            continue
        if any(skip in path.parts for skip in SKIP_DIRS):
            continue
        for chunk_text in _chunk_file(path):
            if chunk_text.strip():
                chunks.append({"file": str(path.relative_to(root)), "text": chunk_text})

    if not chunks:
        return f"❌ No indexable text/code files found under {folder}"

    vectors = []
    failed = 0
    for c in chunks:
        try:
            vectors.append(_embed(c["text"]))
        except Exception as e:
            print(f"[ARIA] codebase_rag: embed failed for {c['file']} — {type(e).__name__}: {e}")
            vectors.append(None)
            failed += 1

    STORE_DIR.mkdir(parents=True, exist_ok=True)
    store_path = STORE_DIR / f"{_project_key(folder)}.json"
    data = {
        "folder": str(root.resolve()),
        "chunks": [{"file": c["file"], "text": c["text"], "vector": v}
                   for c, v in zip(chunks, vectors) if v is not None],
    }
    store_path.write_text(json.dumps(data), encoding="utf-8")

    ok_count = len(data["chunks"])
    return f"✅ Indexed {ok_count} chunks from {folder} ({failed} failed to embed)."


def consult_oracle(question: str, folder: str) -> str:
    if not get_api_key():
        return "❌ No Gemini API key configured — add one in Settings first."

    store_path = STORE_DIR / f"{_project_key(folder)}.json"
    if not store_path.exists():
        return f"❌ No index found for {folder} — run ingest_codebase on it first."

    data = json.loads(store_path.read_text(encoding="utf-8"))
    chunks = data.get("chunks", [])
    if not chunks:
        return "❌ Index is empty — re-run ingest_codebase."

    try:
        q_vec = np.array(_embed(question))
    except Exception as e:
        return f"❌ Could not embed the question: {e}"

    mat = np.array([c["vector"] for c in chunks])
    sims = mat @ q_vec / (np.linalg.norm(mat, axis=1) * np.linalg.norm(q_vec) + 1e-8)
    top_idx = np.argsort(-sims)[:6]

    context = "\n\n".join(f"# {chunks[i]['file']}\n{chunks[i]['text']}" for i in top_idx)
    prompt = (
        f"Using only this codebase context, answer the question. If the "
        f"context doesn't contain the answer, say so plainly instead of guessing.\n\n"
        f"CONTEXT:\n{context}\n\nQUESTION: {question}"
    )

    try:
        resp = requests.post(
            f"{TEXT_URL}?key={get_api_key()}",
            headers={"Content-Type": "application/json"},
            data=json.dumps({"contents": [{"parts": [{"text": prompt}]}]}), timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except requests.exceptions.RequestException as e:
        return f"❌ Oracle query failed: {e}"