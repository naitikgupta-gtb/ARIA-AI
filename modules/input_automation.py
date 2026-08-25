"""
modules/input_automation.py — Input Automation (mouse / keyboard).

Thin wrapper around pyautogui (already a dependency for screenshots).
Deliberately no "click at current app's specific button" smartness here
— that's what read_screen (vision) + a follow-up mouse_click at
coordinates is for. This module is just the raw primitives.
"""
import pyautogui

pyautogui.FAILSAFE = True  # moving mouse to a screen corner aborts — safety net


def mouse_move(x: int, y: int) -> str:
    try:
        pyautogui.moveTo(x, y, duration=0.2)
        return f"✅ Mouse moved to ({x}, {y})"
    except Exception as e:
        return f"❌ {e}"


def mouse_click(x: int = None, y: int = None, button: str = "left", double: bool = False) -> str:
    try:
        kwargs = {"button": button}
        if x is not None and y is not None:
            kwargs["x"] = x
            kwargs["y"] = y
        if double:
            pyautogui.doubleClick(**kwargs)
        else:
            pyautogui.click(**kwargs)
        where = f"({x}, {y})" if x is not None else "current position"
        return f"✅ {'Double-c' if double else 'C'}licked ({button}) at {where}"
    except Exception as e:
        return f"❌ {e}"


def mouse_scroll(amount: int) -> str:
    try:
        pyautogui.scroll(amount)
        return f"✅ Scrolled {'up' if amount > 0 else 'down'} ({amount})"
    except Exception as e:
        return f"❌ {e}"


def get_mouse_position() -> str:
    x, y = pyautogui.position()
    return f"Mouse is at ({x}, {y})"


def keyboard_type(text: str) -> str:
    try:
        pyautogui.typewrite(text, interval=0.02)
        return f"✅ Typed: {text[:60]}{'...' if len(text) > 60 else ''}"
    except Exception as e:
        return f"❌ {e}"


def keyboard_press(keys: str) -> str:
    """`keys` is a '+'-joined combo like 'ctrl+shift+esc' or a single key like 'enter'."""
    try:
        parts = [k.strip() for k in keys.lower().split("+") if k.strip()]
        if len(parts) == 1:
            pyautogui.press(parts[0])
        else:
            pyautogui.hotkey(*parts)
        return f"✅ Pressed: {keys}"
    except Exception as e:
        return f"❌ {e}"
