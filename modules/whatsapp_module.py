"""
modules/whatsapp_module.py — WhatsApp messaging via `pywhatkit`.

This replaces an earlier Selenium-based approach that drove WhatsApp Web
by scraping its DOM directly. That approach breaks every time WhatsApp
changes a CSS class/selector, needs a persistent logged-in Chrome
profile, and is fragile to maintain. `pywhatkit` instead drives WhatsApp
Web through its own stable, documented automation (it opens
web.whatsapp.com in your default browser, waits for the page to be
ready, and simulates the send) — far less code, nothing to keep patching.

Notes / honest limitations:
- The user's WhatsApp Web session must already be logged in (same as
  scanning the QR code once, like normal).
- This only *sends* messages on command — it does not read incoming
  messages or auto-reply to them. WhatsApp's Terms of Service prohibit
  unofficial automation of the client, and reading/auto-replying at
  scale risks the number being banned. If real auto-reply is needed,
  use the official WhatsApp Business API instead — flag that clearly to
  end users rather than silently building around it.
"""
import datetime

try:
    import pywhatkit
    _HAS_PYWHATKIT = True
except Exception:
    _HAS_PYWHATKIT = False


def send_message_now(phone_number: str, message: str) -> str:
    """Send a WhatsApp message immediately via WhatsApp Web.
    `phone_number` must be in international format, e.g. '+919876543210'.
    """
    if not _HAS_PYWHATKIT:
        return "⚠️ Install pywhatkit: pip install pywhatkit"
    if not phone_number or not phone_number.startswith("+"):
        return "❌ phone_number must be in international format, e.g. +919876543210"
    try:
        pywhatkit.sendwhatmsg_instantly(
            phone_no=phone_number,
            message=message,
            wait_time=15,
            tab_close=True,
            close_time=3,
        )
        return f"✅ WhatsApp message sent to {phone_number}"
    except Exception as e:
        return f"❌ Could not send WhatsApp message: {e}"


def schedule_message(phone_number: str, message: str, send_at: str) -> str:
    """Schedule a WhatsApp message for a specific time today.
    `send_at` is 'HH:MM' 24-hour local time.
    """
    if not _HAS_PYWHATKIT:
        return "⚠️ Install pywhatkit: pip install pywhatkit"
    try:
        hour, minute = (int(x) for x in send_at.split(":"))
    except Exception:
        return "❌ send_at must be in 'HH:MM' 24-hour format"
    try:
        pywhatkit.sendwhatmsg(
            phone_no=phone_number,
            message=message,
            time_hour=hour,
            time_min=minute,
            wait_time=15,
            tab_close=True,
        )
        return f"✅ WhatsApp message to {phone_number} scheduled for {send_at}"
    except Exception as e:
        return f"❌ Could not schedule WhatsApp message: {e}"
