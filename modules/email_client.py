"""
modules/email_client.py — Email Drafting/Reading (Gmail/Outlook).

Deliberately uses IMAP/SMTP with an app password instead of full OAuth
(Gmail/Microsoft Graph API) — OAuth needs registering a developer app
in Google Cloud Console / Azure, which is real friction for a personal
assistant. An app password is a 5-minute one-time setup in account
security settings, no developer account needed.

Setup (tell the user once):
  Gmail:   myaccount.google.com/apppasswords (needs 2FA enabled first)
  Outlook: account.live.com/proofs/AppPassword

Then: set_email_credentials(address, app_password, provider)
"""
import email
import imaplib
import smtplib
from email.mime.text import MIMEText
from email.header import decode_header

from config import get_email_credentials

PROVIDER_SERVERS = {
    "gmail": {"imap": "imap.gmail.com", "smtp": "smtp.gmail.com", "smtp_port": 587},
    "outlook": {"imap": "outlook.office365.com", "smtp": "smtp.office365.com", "smtp_port": 587},
}


def _decode(value) -> str:
    if not value:
        return ""
    parts = decode_header(value)
    out = []
    for text, enc in parts:
        if isinstance(text, bytes):
            out.append(text.decode(enc or "utf-8", errors="ignore"))
        else:
            out.append(text)
    return "".join(out)


def read_recent_emails(limit: int = 5, unread_only: bool = False) -> str:
    creds = get_email_credentials()
    if not creds["address"] or not creds["app_password"]:
        return "❌ No email account configured — use set_email_credentials first (address, app password, provider)."

    servers = PROVIDER_SERVERS.get(creds["provider"], PROVIDER_SERVERS["gmail"])
    try:
        imap = imaplib.IMAP4_SSL(servers["imap"])
        imap.login(creds["address"], creds["app_password"])
        imap.select("INBOX")

        criterion = "UNSEEN" if unread_only else "ALL"
        status, data = imap.search(None, criterion)
        if status != "OK":
            return "❌ Could not search inbox."

        ids = data[0].split()[-limit:]
        ids.reverse()  # most recent first

        lines = []
        for msg_id in ids:
            status, msg_data = imap.fetch(msg_id, "(RFC822)")
            if status != "OK":
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            subject = _decode(msg.get("Subject"))
            sender = _decode(msg.get("From"))
            date = msg.get("Date", "")
            lines.append(f"From: {sender}\nSubject: {subject}\nDate: {date}\n")

        imap.logout()
        if not lines:
            return "No emails found."
        return "\n---\n".join(lines)
    except imaplib.IMAP4.error as e:
        return f"❌ Login/IMAP error — check the app password is correct and IMAP is enabled: {e}"
    except Exception as e:
        return f"❌ {type(e).__name__}: {e}"


def send_email(to: str, subject: str, body: str) -> str:
    creds = get_email_credentials()
    if not creds["address"] or not creds["app_password"]:
        return "❌ No email account configured — use set_email_credentials first."

    servers = PROVIDER_SERVERS.get(creds["provider"], PROVIDER_SERVERS["gmail"])
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = creds["address"]
        msg["To"] = to

        with smtplib.SMTP(servers["smtp"], servers["smtp_port"]) as smtp:
            smtp.starttls()
            smtp.login(creds["address"], creds["app_password"])
            smtp.send_message(msg)
        return f"✅ Email sent to {to}: {subject}"
    except smtplib.SMTPAuthenticationError as e:
        return f"❌ Login failed — check the app password: {e}"
    except Exception as e:
        return f"❌ {type(e).__name__}: {e}"
