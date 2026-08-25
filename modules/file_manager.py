"""
modules/file_manager.py — File Management.

Deletion deliberately goes to the OS Recycle Bin/Trash (via
`send2trash`) instead of permanently unlinking files — a voice/text
command is one misheard word away from "delete my project" turning
into something unrecoverable. Recycle Bin gives a safety net; if the
user really wants permanent delete, that's still available manually.
"""
import shutil
from pathlib import Path


def list_files(folder: str) -> str:
    p = Path(folder)
    if not p.is_dir():
        return f"❌ Folder not found: {folder}"
    entries = sorted(p.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
    lines = [f"{'📁' if e.is_dir() else '📄'} {e.name}" for e in entries[:200]]
    if not lines:
        return f"{folder} is empty."
    return "\n".join(lines)


def search_files(pattern: str, folder: str) -> str:
    p = Path(folder)
    if not p.is_dir():
        return f"❌ Folder not found: {folder}"
    matches = list(p.rglob(pattern))
    if not matches:
        return f"No files matching '{pattern}' under {folder}"
    return "\n".join(str(m.relative_to(p)) for m in matches[:100])


def create_folder(path: str) -> str:
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        return f"✅ Created folder: {path}"
    except Exception as e:
        return f"❌ {e}"


def move_file(src: str, dest: str) -> str:
    try:
        shutil.move(src, dest)
        return f"✅ Moved {src} → {dest}"
    except Exception as e:
        return f"❌ {e}"


def copy_file(src: str, dest: str) -> str:
    try:
        src_p = Path(src)
        if src_p.is_dir():
            shutil.copytree(src, dest)
        else:
            shutil.copy2(src, dest)
        return f"✅ Copied {src} → {dest}"
    except Exception as e:
        return f"❌ {e}"


def rename_file(path: str, new_name: str) -> str:
    try:
        p = Path(path)
        new_path = p.with_name(new_name)
        p.rename(new_path)
        return f"✅ Renamed to {new_path}"
    except Exception as e:
        return f"❌ {e}"


def trash_file(path: str) -> str:
    try:
        import send2trash
        send2trash.send2trash(path)
        return f"✅ Moved to Recycle Bin/Trash: {path}"
    except ImportError:
        return "⚠️ Install send2trash: pip install send2trash"
    except Exception as e:
        return f"❌ {e}"


def get_file_info(path: str) -> str:
    p = Path(path)
    if not p.exists():
        return f"❌ Not found: {path}"
    stat = p.stat()
    size_mb = stat.st_size / (1024 * 1024)
    import time
    return (
        f"{p.name}\n"
        f"Type: {'Folder' if p.is_dir() else 'File'}\n"
        f"Size: {size_mb:.2f} MB\n"
        f"Modified: {time.strftime('%Y-%m-%d %H:%M', time.localtime(stat.st_mtime))}"
    )
