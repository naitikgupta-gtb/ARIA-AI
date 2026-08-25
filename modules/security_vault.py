"""
modules/security_vault.py — Lock System Vault.

`lock_system()` locks the OS session the standard, built-in way — the
same thing Win+L does. Whatever sign-in method the user already has
configured in Windows Settings (PIN, password, fingerprint, or face
via Windows Hello) is what handles unlocking. That's deliberate: Windows
Hello is Microsoft's own tested, certified biometric stack with secure
hardware-backed storage — reimplementing face recognition here with
OpenCV/face_recognition would be far less secure, could be defeated
with a photo, and would give a false sense of protection. If a user
wants biometric login, the honest fix is "turn on Windows Hello in
Settings → Accounts → Sign-in options", not a custom face-recognition
lockdown living inside a third-party app.
"""
import platform
import subprocess


def lock_system() -> str:
    system = platform.system()
    try:
        if system == "Windows":
            subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], timeout=5)
        elif system == "Darwin":
            subprocess.run(
                ["/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession", "-suspend"],
                timeout=5,
            )
        elif system == "Linux":
            for cmd in (["loginctl", "lock-session"], ["xdg-screensaver", "lock"]):
                try:
                    subprocess.run(cmd, timeout=5)
                    break
                except FileNotFoundError:
                    continue
        else:
            return f"❌ Unsupported OS: {system}"
        return "✅ System locked. Unlock uses whatever sign-in method is set up in your OS settings (PIN/password/Windows Hello)."
    except Exception as e:
        return f"❌ Could not lock system: {e}"


def windows_hello_status() -> str:
    """Best-effort check of whether Windows Hello is set up — informational
    only, does not configure or replace it. Not available outside Windows."""
    if platform.system() != "Windows":
        return "Windows Hello is Windows-only."
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance -Namespace root/cimv2/security/microsofttpm "
             "-ClassName Win32_Tpm -ErrorAction SilentlyContinue) -ne $null"],
            capture_output=True, text=True, timeout=10,
        )
        return (
            "Can't fully verify Windows Hello configuration from here — "
            "check Settings → Accounts → Sign-in options on this PC directly. "
            f"(TPM presence check output: {result.stdout.strip() or 'unknown'})"
        )
    except Exception as e:
        return f"❌ {e}"
