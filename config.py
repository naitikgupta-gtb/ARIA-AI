"""
config.py — Per-machine storage for the customer's own Gemini API
key. Each install of ARIA keeps its own key, set once through the HUD's
Settings modal (or the ARIA_API_KEY env var for your own dev use).

Preferred backend: the OS credential store via `keyring` (Windows
Credential Manager / macOS Keychain / Linux Secret Service) — the key
never sits in a plain file. If `keyring` has no usable backend
(common on a bare Linux box with no desktop session), this falls back
to a JSON file under the user's own app-data folder. That fallback is
NOT encrypted — fine for a single-user desktop app, but flag it to
customers if you expect a shared/multi-user machine.
"""

import json
import os
import sys

SERVICE_NAME = "ARIA"
KEY_NAME = "gemini_api_key"          # kept for backward compatibility
NOTION_KEY_NAME = "notion_token"

try:
    import keyring
    _HAS_KEYRING = True
except Exception:
    _HAS_KEYRING = False


def _config_dir():
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    d = os.path.join(base, "ARIA")
    os.makedirs(d, exist_ok=True)
    return d


_FALLBACK_PATH = os.path.join(_config_dir(), "config.json")


def _file_get(name):
    try:
        with open(_FALLBACK_PATH, "r", encoding="utf-8") as f:
            return json.load(f).get(name, "")
    except (FileNotFoundError, json.JSONDecodeError):
        return ""


def _file_set(name, value):
    data = {}
    if os.path.exists(_FALLBACK_PATH):
        try:
            with open(_FALLBACK_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            data = {}
    data[name] = value
    with open(_FALLBACK_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f)


def get_secret(name: str) -> str:
    """Generic named-secret getter — same OS-credential-store-first,
    JSON-file-fallback pattern as the Gemini key, reused for anything
    else that needs a per-machine token (Notion, etc).

    Tries keyring first, but ALSO checks the file if keyring comes back
    empty — keyring.get_password() can return None/empty without ever
    raising (a disabled Credential Manager service, a restricted user
    account, or an inconsistent keyring backend can all cause this), so
    treating an empty keyring result as final would silently lose a
    value that set_secret() did successfully persist to the file."""
    if _HAS_KEYRING:
        try:
            value = keyring.get_password(SERVICE_NAME, name)
            if value:
                return value
        except Exception:
            pass
    return _file_get(name)


def set_secret(name: str, value: str) -> None:
    """Writes to BOTH keyring and the JSON file, not just keyring —
    keyring.set_password() can silently no-op (doesn't raise, but
    doesn't actually persist either) in some Windows environments,
    which previously meant the value was never written anywhere at
    all and vanished with no error shown to the user. Writing to both
    is cheap redundancy that guarantees at least one source has it."""
    value = (value or "").strip()
    if _HAS_KEYRING:
        try:
            keyring.set_password(SERVICE_NAME, name, value)
        except Exception:
            pass
    _file_set(name, value)  # always also write the file, regardless of keyring's outcome


def get_api_key() -> str:
    """Env var (your own dev/testing) wins if set, otherwise whatever
    the customer entered through Settings on this machine."""
    env_key = os.environ.get("ARIA_API_KEY", "")
    if env_key:
        return env_key
    return get_secret(KEY_NAME)


def set_api_key(key: str) -> None:
    set_secret(KEY_NAME, key)


def has_api_key() -> bool:
    return bool(get_api_key())


def masked_key() -> str:
    key = get_api_key()
    if not key:
        return ""
    return "•" * 6 + key[-4:]


def get_notion_token() -> str:
    return os.environ.get("NOTION_TOKEN", "") or get_secret(NOTION_KEY_NAME)


def set_notion_token(token: str) -> None:
    set_secret(NOTION_KEY_NAME, token)


# ── Talking persona (relationship style) ─────────────────────────────
PERSONA_KEY_NAME = "persona"
DEFAULT_PERSONA = "assistant"


def get_persona() -> str:
    return get_secret(PERSONA_KEY_NAME) or DEFAULT_PERSONA


def set_persona(persona: str) -> None:
    set_secret(PERSONA_KEY_NAME, persona)


# ── Voice gender-swap mode ────────────────────────────────────────────
# "opposite" = auto-detect speaker's voice pitch and reply in the other
#              gender's voice; "female"/"male" = always use that voice;
#              "off" = same as "female" (Gemini's default here).
VOICE_MODE_KEY_NAME = "voice_mode"
DEFAULT_VOICE_MODE = "opposite"


def get_voice_mode() -> str:
    return get_secret(VOICE_MODE_KEY_NAME) or DEFAULT_VOICE_MODE


def set_voice_mode(mode: str) -> None:
    set_secret(VOICE_MODE_KEY_NAME, mode)


# ── Email (IMAP/SMTP app-password based — no OAuth app registration) ──
EMAIL_ADDRESS_KEY = "email_address"
EMAIL_APP_PASSWORD_KEY = "email_app_password"
EMAIL_PROVIDER_KEY = "email_provider"  # 'gmail' | 'outlook'


def get_email_credentials() -> dict:
    return {
        "address": get_secret(EMAIL_ADDRESS_KEY),
        "app_password": get_secret(EMAIL_APP_PASSWORD_KEY),
        "provider": get_secret(EMAIL_PROVIDER_KEY) or "gmail",
    }


def set_email_credentials(address: str, app_password: str, provider: str = "gmail") -> None:
    set_secret(EMAIL_ADDRESS_KEY, address)
    set_secret(EMAIL_APP_PASSWORD_KEY, app_password)
    set_secret(EMAIL_PROVIDER_KEY, provider)
