"""
otp_service.py – Generate, store, send, and verify 4-digit OTPs
"""
import random
import string
from datetime import datetime, timedelta

import httpx

from app.config import settings
from app.database import get_collection
from app.utils.logger import logger


# ── Helpers ───────────────────────────────────────────────────────────────────

def _generate_otp(length: int = 4) -> str:
    return "".join(random.choices(string.digits, k=length))


def _otp_email_body(otp: str, email: str) -> str:
    return f"""
<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;background:#f4f4f4;padding:30px">
  <div style="max-width:480px;margin:auto;background:#fff;border-radius:10px;padding:32px;box-shadow:0 2px 8px rgba(0,0,0,.1)">
    <h2 style="color:#d63384;margin-top:0">🩸 Pad Vending Machine</h2>
    <p style="font-size:16px;color:#333">Hello,</p>
    <p style="font-size:15px;color:#555">
      Your one-time password (OTP) is:
    </p>
    <div style="text-align:center;margin:24px 0">
      <span style="font-size:42px;font-weight:bold;letter-spacing:12px;color:#d63384">{otp}</span>
    </div>
    <p style="font-size:13px;color:#888">
      This OTP is valid for <strong>{settings.OTP_EXPIRE_MINUTES} minutes</strong>.
      Please do not share it with anyone.
    </p>
    <hr style="border:none;border-top:1px solid #eee;margin:24px 0">
    <p style="font-size:12px;color:#aaa;text-align:center">
      If you did not request this OTP, you can safely ignore this email.
    </p>
  </div>
</body>
</html>
"""


# ── Core functions ────────────────────────────────────────────────────────────

async def generate_and_store_otp(email: str) -> str:
    """Create a new OTP, persist it (replacing any existing one), return the code."""
    otp = _generate_otp()
    expires_at = datetime.utcnow() + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)

    col = get_collection("otps")
    await col.delete_many({"email": email})   # Invalidate old OTPs for this email
    await col.insert_one({
        "email": email,
        "otp": otp,
        "expires_at": expires_at,
        "used": False,
        "created_at": datetime.utcnow(),
    })
    logger.debug(f"OTP stored for {email} (expires {expires_at})")
    return otp


async def send_otp_email(email: str, otp: str) -> None:
    """Send the OTP to the given email address via Brevo transactional email API."""
    if not settings.BREVO_API_KEY:
        logger.error("BREVO_API_KEY is not configured in settings")
        raise ValueError("Email service is temporarily unavailable due to missing credentials.")

    headers = {
        "accept": "application/json",
        "api-key": settings.BREVO_API_KEY,
        "content-type": "application/json"
    }

    payload = {
        "sender": {
            "name": settings.FROM_NAME,
            "email": settings.FROM_EMAIL
        },
        "to": [
            {
                "email": email
            }
        ],
        "subject": "Your Pad Vending OTP",
        "htmlContent": _otp_email_body(otp, email)
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://api.brevo.com/v3/smtp/email",
                json=payload,
                headers=headers
            )
            response_json = response.json()
            if response.status_code >= 400:
                logger.error(f"Failed to send OTP email to {email} via Brevo. Status: {response.status_code}. Response: {response_json}")
                raise ValueError(f"Brevo API error: {response_json.get('message', 'Unknown error')}")
            
            logger.info(f"OTP email sent to {email} via Brevo. Message ID: {response_json.get('messageId')}")
    except Exception as exc:
        logger.error(f"Failed to send OTP email to {email} via Brevo: {exc}")
        raise


async def verify_otp(email: str, otp: str) -> bool:
    """
    Return True if the OTP is valid and mark it as used.
    Raises ValueError with a human-readable message on failure.
    """
    col = get_collection("otps")
    record = await col.find_one({"email": email, "used": False})

    if not record:
        raise ValueError("No active OTP found for this email. Please request a new one.")

    if record["expires_at"] < datetime.utcnow():
        raise ValueError("OTP has expired. Please request a new one.")

    if record["otp"] != otp:
        raise ValueError("Invalid OTP. Please try again.")

    # Mark as used
    await col.update_one({"_id": record["_id"]}, {"$set": {"used": True}})
    logger.info(f"OTP verified for {email}")
    return True
