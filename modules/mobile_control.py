"""
modules/mobile_control.py — Mobile Control Suite (ADB-based).

Everything here is a wrapper around `adb` (Android Debug Bridge) —
Google's own official tool for talking to an Android phone from a PC.
Nothing here is a hidden backdoor: the phone owner has to explicitly
turn on USB debugging (Settings → Developer Options) and accept a
"trust this computer" prompt the first time. Without that, none of
this works at all — which is the correct, honest security model.

Requirements on the user's machine:
1. `adb` installed and on PATH (ships with Android SDK Platform-Tools —
   free download from developer.android.com, no Android Studio needed)
2. Phone: Settings → About Phone → tap "Build number" 7 times to unlock
   Developer Options → enable "USB debugging"
3. Connect via USB (or `adb tcpip`/`adb connect` for WiFi) once, accept
   the "Allow USB debugging" prompt on the phone

Two things explicitly NOT implemented here, on purpose:
- Reading SMS/notifications: modern Android blocks raw SMS reads over
  ADB for non-default-SMS apps. The real way to do this is a small
  companion Android app using NotificationListenerService — a
  separate Android (Kotlin/Java) project, not a Python/ADB trick.
- Flashlight toggle: there's no standard ADB command for it either —
  same companion-app requirement as above.
"""
import shutil
import subprocess

ADB_TIMEOUT = 15


def _adb_available() -> bool:
    return shutil.which("adb") is not None


def _run(args, timeout=ADB_TIMEOUT):
    if not _adb_available():
        return None, "❌ `adb` not found on PATH. Install Android SDK Platform-Tools and add it to PATH."
    try:
        result = subprocess.run(["adb"] + args, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0 and result.stderr.strip():
            return None, f"❌ adb error: {result.stderr.strip()}"
        return result.stdout.strip(), None
    except subprocess.TimeoutExpired:
        return None, "❌ adb command timed out — check the phone is connected and unlocked"
    except Exception as e:
        return None, f"❌ {e}"


def device_status() -> str:
    out, err = _run(["devices"])
    if err:
        return err
    lines = [l for l in out.splitlines()[1:] if l.strip()]
    if not lines:
        return "❌ No phone connected. Enable USB debugging and plug in / adb connect first."
    return "✅ Connected device(s):\n" + "\n".join(lines)


def battery_info() -> str:
    out, err = _run(["shell", "dumpsys", "battery"])
    if err:
        return err
    return out


def push_file(local_path: str, remote_path: str = "/sdcard/") -> str:
    out, err = _run(["push", local_path, remote_path], timeout=120)
    if err:
        return err
    return f"✅ Pushed {local_path} → {remote_path}"


def pull_file(remote_path: str, local_path: str = ".") -> str:
    out, err = _run(["pull", remote_path, local_path], timeout=120)
    if err:
        return err
    return f"✅ Pulled {remote_path} → {local_path}"


def open_app(package_name: str) -> str:
    out, err = _run(["shell", "monkey", "-p", package_name, "-c", "android.intent.category.LAUNCHER", "1"])
    if err:
        return err
    return f"✅ Launched {package_name}"


def close_app(package_name: str) -> str:
    out, err = _run(["shell", "am", "force-stop", package_name])
    if err:
        return err
    return f"✅ Force-stopped {package_name}"


def tap(x: int, y: int) -> str:
    out, err = _run(["shell", "input", "tap", str(x), str(y)])
    if err:
        return err
    return f"✅ Tapped ({x}, {y})"


def swipe(x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> str:
    out, err = _run(["shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration_ms)])
    if err:
        return err
    return f"✅ Swiped ({x1},{y1}) → ({x2},{y2})"


def toggle_wifi(enable: bool) -> str:
    out, err = _run(["shell", "svc", "wifi", "enable" if enable else "disable"])
    if err:
        return err
    return f"✅ WiFi {'enabled' if enable else 'disabled'}"


def toggle_bluetooth(enable: bool) -> str:
    out, err = _run(["shell", "svc", "bluetooth", "enable" if enable else "disable"])
    if err:
        return err
    return f"✅ Bluetooth {'enabled' if enable else 'disabled'}"
