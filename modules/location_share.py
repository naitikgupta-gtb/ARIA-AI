"""
modules/location_share.py — "send my location to my emergency contact".

Honest limitation up front: a laptop usually has no GPS chip. This uses
IP-based geolocation (free, no key, via ip-api.com), which is accurate
to roughly city/neighborhood level — NOT precise GPS coordinates. Good
enough for "which city am I in", not good enough to actually be relied
on as a precise emergency-locator. Say this plainly to the user rather
than implying GPS-grade accuracy.
"""
import requests

from modules import contacts, whatsapp_module


def get_approx_location() -> dict:
    """Returns {'ok': bool, 'city':..., 'lat':..., 'lon':..., 'maps_url':..., 'message':...}"""
    try:
        resp = requests.get("http://ip-api.com/json/", timeout=8)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "success":
            return {"ok": False, "message": f"❌ Location lookup failed: {data.get('message', 'unknown error')}"}
        lat, lon = data["lat"], data["lon"]
        maps_url = f"https://www.google.com/maps?q={lat},{lon}"
        return {
            "ok": True,
            "city": f"{data.get('city', '')}, {data.get('regionName', '')}, {data.get('country', '')}",
            "lat": lat, "lon": lon, "maps_url": maps_url,
            "message": f"Approximate location: {data.get('city', '')} ({maps_url})",
        }
    except requests.exceptions.RequestException as e:
        return {"ok": False, "message": f"❌ Could not determine location: {type(e).__name__}: {e}"}


def send_my_location(contact_name: str) -> str:
    loc = get_approx_location()
    if not loc["ok"]:
        return loc["message"]

    phone = contacts.find_contact(contact_name)
    if not phone:
        return f"❌ No saved contact matching '{contact_name}' — save one first with add_contact."

    text = (
        f"📍 My approximate location (from Wi-Fi/IP, city-level accuracy — not precise GPS): "
        f"{loc['city']}\n{loc['maps_url']}"
    )
    result = whatsapp_module.send_message_now(phone, text)
    if result.startswith("✅"):
        return f"✅ Sent approximate location to {contact_name} ({loc['city']}) — note: this is city-level accuracy, not precise GPS."
    return result
