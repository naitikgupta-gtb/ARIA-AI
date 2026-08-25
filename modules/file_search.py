"""
modules/file_search.py — Voice-based Natural Language File Search.

The clever part: this module itself does NO natural-language parsing.
Gemini's function-calling already does that — "the PDF I downloaded
last week" gets turned into structured args (extension='.pdf',
modified_within_days=7) by the model BEFORE this function is even
called. This just does the boring, precise filesystem filtering part.
"""
import time
from pathlib import Path

DEFAULT_SEARCH_FOLDERS = ["Desktop", "Documents", "Downloads", "Pictures"]


def _default_roots() -> list:
    home = Path.home()
    return [home / f for f in DEFAULT_SEARCH_FOLDERS if (home / f).is_dir()]


def smart_search(
    keyword: str = "",
    extension: str = "",
    modified_within_days: int = None,
    search_root: str = "",
    limit: int = 30,
) -> str:
    roots = [Path(search_root)] if search_root else _default_roots()
    roots = [r for r in roots if r.is_dir()]
    if not roots:
        return "❌ No valid folders to search (checked Desktop/Documents/Downloads/Pictures)."

    ext = extension.lower().lstrip(".")
    keyword_lower = keyword.lower()
    cutoff_ts = time.time() - modified_within_days * 86400 if modified_within_days else None

    matches = []
    for root in roots:
        try:
            for path in root.rglob("*"):
                if path.is_dir():
                    continue
                if ext and path.suffix.lower().lstrip(".") != ext:
                    continue
                if keyword_lower and keyword_lower not in path.name.lower():
                    continue
                if cutoff_ts and path.stat().st_mtime < cutoff_ts:
                    continue
                matches.append(path)
        except (PermissionError, OSError):
            continue

    if not matches:
        criteria = []
        if keyword: criteria.append(f"name contains '{keyword}'")
        if extension: criteria.append(f"type .{ext}")
        if modified_within_days: criteria.append(f"modified in last {modified_within_days} days")
        return f"❌ No files found matching: {', '.join(criteria) or 'any criteria'}"

    matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    lines = []
    for path in matches[:limit]:
        mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(path.stat().st_mtime))
        lines.append(f"{path} (modified {mtime})")
    return "\n".join(lines)
