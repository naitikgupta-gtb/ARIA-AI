"""
modules/downloads_organizer.py — Auto Downloads Organizer.

On-demand (call it whenever you want, or wire a scheduled call) sorter
that moves files in a folder (default: the user's Downloads folder)
into category subfolders by extension — Images, Documents, Videos,
Audio, Archives, Installers, Others. Never overwrites — if a name
collision happens, it appends a counter.
"""
import platform
import shutil
from pathlib import Path

CATEGORIES = {
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".heic"},
    "Documents": {".pdf", ".doc", ".docx", ".txt", ".md", ".xls", ".xlsx", ".ppt", ".pptx", ".csv"},
    "Videos": {".mp4", ".mkv", ".mov", ".avi", ".webm"},
    "Audio": {".mp3", ".wav", ".flac", ".m4a", ".ogg"},
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz"},
    "Installers": {".exe", ".msi"},
}


def _default_downloads_folder() -> Path:
    return Path.home() / "Downloads"


def _category_for(ext: str) -> str:
    ext = ext.lower()
    for cat, exts in CATEGORIES.items():
        if ext in exts:
            return cat
    return "Others"


def organize(folder: str = "") -> str:
    target = Path(folder) if folder else _default_downloads_folder()
    if not target.is_dir():
        return f"❌ Folder not found: {target}"

    moved = {}
    skipped = 0
    for item in target.iterdir():
        if item.is_dir():
            continue
        cat = _category_for(item.suffix)
        dest_dir = target / cat
        dest_dir.mkdir(exist_ok=True)
        dest_path = dest_dir / item.name
        counter = 1
        while dest_path.exists():
            dest_path = dest_dir / f"{item.stem}_{counter}{item.suffix}"
            counter += 1
        try:
            shutil.move(str(item), str(dest_path))
            moved[cat] = moved.get(cat, 0) + 1
        except Exception:
            skipped += 1

    if not moved:
        return f"Nothing to organize in {target} — already tidy."

    summary = ", ".join(f"{count} {cat}" for cat, count in moved.items())
    extra = f" ({skipped} skipped)" if skipped else ""
    return f"✅ Organized {target}: {summary}{extra}"
