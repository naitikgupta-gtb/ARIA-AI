"""
modules/contacts.py — Local contact book (name → phone number).

Lets WhatsApp sending work by saying a name instead of dictating a full
phone number every time. Stored in the same SQLite DB memory.py uses.
Lookup is case-insensitive and matches partial names (e.g. "rahul"
matches a saved contact "Rahul Sharma").
"""
from modules import memory


def _ensure_table():
    conn, lock = memory.raw_connection()
    with lock:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS contacts (
                name TEXT PRIMARY KEY,
                phone_number TEXT NOT NULL
            )
        """)
        conn.commit()


def add_contact(name: str, phone_number: str) -> str:
    name = name.strip()
    phone_number = phone_number.strip()
    if not name or not phone_number:
        return "❌ Provide both a name and a phone number"
    if not phone_number.startswith("+"):
        return "❌ phone_number must be in international format, e.g. +919876543210"

    _ensure_table()
    conn, lock = memory.raw_connection()
    with lock:
        conn.execute(
            "INSERT INTO contacts (name, phone_number) VALUES (?, ?) "
            "ON CONFLICT(name) DO UPDATE SET phone_number = excluded.phone_number",
            (name.lower(), phone_number),
        )
        conn.commit()
    return f"✅ Saved contact: {name} → {phone_number}"


def find_contact(name: str) -> str | None:
    """Case-insensitive, partial match. Returns the phone number, or
    None if nothing matches (or more than one contact matches — in that
    case the caller should ask the user to be more specific)."""
    _ensure_table()
    conn, lock = memory.raw_connection()
    needle = name.strip().lower()
    with lock:
        exact = conn.execute("SELECT phone_number FROM contacts WHERE name = ?", (needle,)).fetchone()
        if exact:
            return exact[0]
        matches = conn.execute(
            "SELECT phone_number FROM contacts WHERE name LIKE ?", (f"%{needle}%",)
        ).fetchall()
    if len(matches) == 1:
        return matches[0][0]
    return None  # zero or ambiguous multiple matches


def list_contacts() -> str:
    _ensure_table()
    conn, lock = memory.raw_connection()
    with lock:
        rows = conn.execute("SELECT name, phone_number FROM contacts ORDER BY name").fetchall()
    if not rows:
        return "No contacts saved yet."
    return "\n".join(f"{name} — {phone}" for name, phone in rows)
