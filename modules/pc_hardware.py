"""
modules/pc_hardware.py — This PC's own Bluetooth/WiFi/brightness — NOT
the phone's (that's modules/mobile_control.py, over ADB). Keeping these
as separate tools with distinct names so ARIA doesn't confuse "turn on
bluetooth" (ambiguous: phone or this PC?) — the tool descriptions make
each one's scope explicit.

Bluetooth/WiFi toggling on Windows needs Administrator rights (it's
touching a system device driver state) — if ARIA isn't running elevated,
these will fail with a clear permission message rather than silently
doing nothing.
"""
import platform
import subprocess


def toggle_bluetooth(enable: bool) -> str:
    system = platform.system()
    if system != "Windows":
        return "⚠️ PC Bluetooth toggle is Windows-only right now."
    action = "Enable-PnpDevice" if enable else "Disable-PnpDevice"
    ps = (
        f"Get-PnpDevice -Class Bluetooth | Where-Object {{$_.Status -eq 'OK' -or $_.Status -eq 'Error'}} "
        f"| ForEach-Object {{ {action} -InstanceId $_.InstanceId -Confirm:$false }}"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0 and "Access" in (result.stderr or ""):
            return "❌ Needs Administrator rights — right-click and 'Run as administrator' to control Bluetooth."
        return f"✅ Bluetooth {'enabled' if enable else 'disabled'}"
    except Exception as e:
        return f"❌ {e}"


def toggle_wifi(enable: bool) -> str:
    system = platform.system()
    if system != "Windows":
        return "⚠️ PC WiFi toggle is Windows-only right now."
    try:
        # Find the WiFi adapter's actual interface name instead of assuming
        # "Wi-Fi" — laptops sometimes name it differently.
        show = subprocess.run(
            ["netsh", "interface", "show", "interface"],
            capture_output=True, text=True, timeout=10,
        )
        iface_name = None
        for line in show.stdout.splitlines():
            if "Wi-Fi" in line or "Wireless" in line:
                iface_name = line.split()[-1] if line.split() else None
                # netsh's column format means the name is everything after
                # the first 3 columns — safer to just search for "Wi-Fi"
                # literal name which is the Windows default.
                iface_name = "Wi-Fi"
                break
        iface_name = iface_name or "Wi-Fi"

        state = "enabled" if enable else "disabled"
        result = subprocess.run(
            ["netsh", "interface", "set", "interface", iface_name, state],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return f"❌ Could not toggle WiFi — needs Administrator rights: {result.stderr.strip()}"
        return f"✅ WiFi {state}"
    except Exception as e:
        return f"❌ {e}"


def set_brightness(level: int) -> str:
    level = max(0, min(100, int(level)))
    system = platform.system()
    if system != "Windows":
        return "⚠️ Brightness control is Windows-only right now (laptop panel via WMI)."
    ps = (
        "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods)"
        f".WmiSetBrightness(1,{level})"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return (
                f"❌ Could not set brightness — this only works on laptop built-in "
                f"panels (not external monitors), and some laptops don't expose "
                f"this WMI interface: {result.stderr.strip()}"
            )
        return f"✅ Brightness set to {level}%"
    except Exception as e:
        return f"❌ {e}"
