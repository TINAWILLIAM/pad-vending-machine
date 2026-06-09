"""
payment_verification.py – Razorpay HMAC-SHA256 signature helpers
"""
import hmac
import hashlib
from app.config import settings
from app.utils.logger import logger


def verify_razorpay_payment_signature(
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
) -> bool:
    """
    Verify the Razorpay payment signature sent by the client.
    (Used when client reports payment complete – we re-verify anyway.)
    """
    body = f"{razorpay_order_id}|{razorpay_payment_id}"
    expected = hmac.new(
        settings.RAZORPAY_KEY_SECRET.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    match = hmac.compare_digest(expected, razorpay_signature)
    logger.debug(f"Payment signature valid={match} for order {razorpay_order_id}")
    return match


def verify_razorpay_webhook_signature(
    payload_body: bytes,
    signature_header: str,
) -> bool:
    """
    Verify the X-Razorpay-Signature header for incoming webhooks.
    payload_body must be the raw request body bytes.
    """
    expected = hmac.new(
        settings.RAZORPAY_WEBHOOK_SECRET.encode("utf-8"),
        payload_body,
        hashlib.sha256,
    ).hexdigest()
    match = hmac.compare_digest(expected, signature_header)
    logger.debug(f"Webhook signature valid={match}")
    return match
