"""
modules/system_control.py — System Control (volume / shutdown / sleep).

Cross-platform where the OS makes it reasonable:
- Volume: pycaw (Windows Core Audio bindings) on Windows, `osascript` on
  macOS (built-in, no extra dependency), `amixer` on Linux.
- Power actions: native OS commands. macOS shutdown/restart use
  AppleScript ("tell application System Events") specifically because
  that path does NOT require sudo/admin password, unlike `shutdown -h now`.
"""
import platform
import subprocess


# ── Volume ──────────────────────────────────────────────────────────────
def _get_windows_volume_interface():
    """pycaw talks to Windows over COM, and COM requires the CALLING
    THREAD to explicitly initialize its apartment first — tool calls run
    on a background executor thread (a different one potentially each
    time), which never gets COM auto-initialized by Python. Skipping
    this call is the #1 reason pycaw silently does nothing / raises an
    opaque OSError from a thread."""
    import comtypes
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

    try:
        comtypes.CoInitialize()
    except OSError:
        pass  # already initialized on this thread — fine, not an error

    devices = AudioUtilities.GetSpeakers()
    try:
        # Standard pycaw usage — works on most releases.
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    except AttributeError:
        # Some pycaw releases changed AudioUtilities.GetSpeakers() to return
        # pycaw's own high-level `AudioDevice` wrapper (meant for listing
        # devices) instead of the raw COM IMMDevice — that wrapper has no
        # .Activate(). This is a known cross-version pycaw breakage, not an
        # environment/machine issue. Bypass the wrapper and go straight to
        # the same low-level COM calls pycaw uses internally, which are
        # stable across versions.
        from pycaw.pycaw import (
            CLSID_MMDeviceEnumerator, IMMDeviceEnumerator, IMMDevice,
            EDataFlow, ERole,
        )
        enumerator = comtypes.CoCreateInstance(
            CLSID_MMDeviceEnumerator, IMMDeviceEnumerator,
            comtypes.CLSCTX_INPROC_SERVER,
        )
        endpoint = enumerator.GetDefaultAudioEndpoint(EDataFlow.eRender.value, ERole.eMultimedia.value)
        device = endpoint.QueryInterface(IMMDevice)
        interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)

    return cast(interface, POINTER(IAudioEndpointVolume))


def set_volume(level: int) -> str:
    level = max(0, min(100, int(level)))
    system = platform.system()
    try:
        if system == "Windows":
            try:
                volume = _get_windows_volume_interface()
                volume.SetMasterVolumeLevelScalar(level / 100.0, None)
            except ImportError:
                return "⚠️ Install pycaw + comtypes: pip install pycaw comtypes"
            except Exception as e:
                print(f"[ARIA] system_control.set_volume: {type(e).__name__}: {e}")
                return f"❌ Volume control failed: {type(e).__name__}: {e}"
        elif system == "Darwin":
            subprocess.run(["osascript", "-e", f"set volume output volume {level}"], capture_output=True)
        elif system == "Linux":
            subprocess.run(["amixer", "-D", "pulse", "sset", "Master", f"{level}%"], capture_output=True)
        else:
            return f"❌ Unsupported OS: {system}"
        return f"✅ Volume set to {level}%"
    except Exception as e:
        return f"❌ {e}"


def mute(enable: bool = True) -> str:
    system = platform.system()
    try:
        if system == "Windows":
            try:
                volume = _get_windows_volume_interface()
                volume.SetMute(1 if enable else 0, None)
            except ImportError:
                return "⚠️ Install pycaw + comtypes: pip install pycaw comtypes"
            except Exception as e:
                print(f"[ARIA] system_control.mute: {type(e).__name__}: {e}")
                return f"❌ Mute control failed: {type(e).__name__}: {e}"
        elif system == "Darwin":
            subprocess.run(["osascript", "-e", f"set volume output muted {'true' if enable else 'false'}"], capture_output=True)
        elif system == "Linux":
            subprocess.run(["amixer", "-D", "pulse", "sset", "Master", "mute" if enable else "unmute"], capture_output=True)
        return f"✅ {'Muted' if enable else 'Unmuted'}"
    except Exception as e:
        return f"❌ {e}"


# ── Power ───────────────────────────────────────────────────────────────
def shutdown(delay_seconds: int = 30) -> str:
    system = platform.system()
    try:
        if system == "Windows":
            subprocess.run(["shutdown", "/s", "/t", str(delay_seconds)])
        elif system == "Darwin":
            subprocess.run(["osascript", "-e",
                             f'delay {delay_seconds}\ntell application "System Events" to shut down'])
        elif system == "Linux":
            subprocess.run(["shutdown", "-h", f"+{max(1, delay_seconds // 60)}"])
        else:
            return f"❌ Unsupported OS: {system}"
        return f"✅ Shutdown scheduled in {delay_seconds}s — say 'cancel shutdown' to stop it"
    except Exception as e:
        return f"❌ {e}"


def restart(delay_seconds: int = 30) -> str:
    system = platform.system()
    try:
        if system == "Windows":
            subprocess.run(["shutdown", "/r", "/t", str(delay_seconds)])
        elif system == "Darwin":
            subprocess.run(["osascript", "-e",
                             f'delay {delay_seconds}\ntell application "System Events" to restart'])
        elif system == "Linux":
            subprocess.run(["shutdown", "-r", f"+{max(1, delay_seconds // 60)}"])
        else:
            return f"❌ Unsupported OS: {system}"
        return f"✅ Restart scheduled in {delay_seconds}s — say 'cancel shutdown' to stop it"
    except Exception as e:
        return f"❌ {e}"


def cancel_shutdown() -> str:
    system = platform.system()
    try:
        if system == "Windows":
            subprocess.run(["shutdown", "/a"])
        elif system in ("Darwin", "Linux"):
            return "⚠️ macOS/Linux shutdown here uses a fixed AppleScript delay/`shutdown` timer — cancel manually with `sudo killall shutdown` (Mac/Linux) if needed before it fires."
        return "✅ Scheduled shutdown/restart cancelled"
    except Exception as e:
        return f"❌ {e}"


def sleep_now() -> str:
    system = platform.system()
    try:
        if system == "Windows":
            subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
        elif system == "Darwin":
            subprocess.run(["osascript", "-e", 'tell application "System Events" to sleep'])
        elif system == "Linux":
            subprocess.run(["systemctl", "suspend"])
        else:
            return f"❌ Unsupported OS: {system}"
        return "✅ Sleeping now"
    except Exception as e:
        return f"❌ {e}"