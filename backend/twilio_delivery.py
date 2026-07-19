"""Twilio WhatsApp/SMS delivery.

Behavior: real send if all 3 env vars are set (TWILIO_ACCOUNT_SID,
TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM); otherwise mock-mode returns
delivered=False with a clear reason. The pipeline never fails on delivery.
"""
import os
import logging
from typing import Optional

log = logging.getLogger("cropvision.twilio")

SID = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
WHATSAPP_FROM = os.environ.get("TWILIO_WHATSAPP_FROM", "").strip()
SMS_FROM = os.environ.get("TWILIO_SMS_FROM", "").strip()


def is_configured(channel: str = "whatsapp") -> bool:
    if not (SID and TOKEN):
        return False
    if channel == "whatsapp":
        return bool(WHATSAPP_FROM)
    if channel == "sms":
        return bool(SMS_FROM)
    return False


async def send(channel: str, to: str, body: str) -> dict:
    """Return {delivered: bool, sid: str|None, error: str|None, mocked: bool}."""
    if not to:
        return {"delivered": False, "sid": None, "error": "no recipient", "mocked": True}
    if not is_configured(channel):
        return {
            "delivered": False, "sid": None, "mocked": True,
            "error": f"twilio {channel} not configured (missing env vars)",
        }
    try:
        # lazy import so backend boots even if the SDK is missing
        from twilio.rest import Client
        client = Client(SID, TOKEN)
        if channel == "whatsapp":
            from_ = f"whatsapp:{WHATSAPP_FROM}" if not WHATSAPP_FROM.startswith("whatsapp:") else WHATSAPP_FROM
            to_ = f"whatsapp:{to}" if not to.startswith("whatsapp:") else to
        else:
            from_ = SMS_FROM
            to_ = to
        msg = client.messages.create(body=body[:1400], from_=from_, to=to_)
        return {"delivered": True, "sid": msg.sid, "error": None, "mocked": False}
    except Exception as e:
        log.exception("Twilio send failed")
        return {"delivered": False, "sid": None, "error": str(e), "mocked": False}
