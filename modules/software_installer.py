"""
modules/software_installer.py — "install VS Code" fully by voice.

Uses `winget` (Windows Package Manager) — built into Windows 10/11,
nothing extra to install. Runs silently with auto-accepted agreements
so it doesn't pop up a wizard the user has to click through — that
would defeat the point of "no hand touch" automation.
"""
import platform
import subprocess

WINGET_IDS = {
    "vs code": "Microsoft.VisualStudioCode",
    "vscode": "Microsoft.VisualStudioCode",
    "visual studio code": "Microsoft.VisualStudioCode",
    "chrome": "Google.Chrome",
    "firefox": "Mozilla.Firefox",
    "python": "Python.Python.3.12",
    "git": "Git.Git",
    "node": "OpenJS.NodeJS.LTS",
    "nodejs": "OpenJS.NodeJS.LTS",
    "spotify": "Spotify.Spotify",
    "discord": "Discord.Discord",
    "zoom": "Zoom.Zoom",
    "vlc": "VideoLAN.VLC",
    "7zip": "7zip.7zip",
    "notepad++": "Notepad++.Notepad++",
    "postman": "Postman.Postman",
    "slack": "SlackTechnologies.Slack",
    "obsidian": "Obsidian.Obsidian",
    "docker": "Docker.DockerDesktop",
}


def install(app_name: str) -> str:
    if platform.system() != "Windows":
        return "⚠️ Voice-triggered install currently only wired up for Windows (winget)."

    key = app_name.lower().strip()
    winget_id = WINGET_IDS.get(key, app_name)  # fall through to raw name if not in the map

    try:
        result = subprocess.run(
            ["winget", "install", "--id", winget_id, "-e", "--silent",
             "--accept-package-agreements", "--accept-source-agreements"],
            capture_output=True, text=True, timeout=600,  # installs can genuinely take minutes
        )
        if result.returncode == 0:
            return f"✅ {app_name} installed successfully"
        # winget's own error text is usually informative enough to surface directly
        tail = (result.stdout or result.stderr or "").strip()[-400:]
        return f"❌ Install failed for {app_name}: {tail}"
    except FileNotFoundError:
        return "❌ winget not found — needs Windows 10 1809+/Windows 11 with 'App Installer' from the Microsoft Store."
    except subprocess.TimeoutExpired:
        return f"❌ Install of {app_name} timed out after 10 minutes — may still be running in the background, check manually."
    except Exception as e:
        return f"❌ {e}"
