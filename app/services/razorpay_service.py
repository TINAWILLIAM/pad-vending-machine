"""
razorpay_service.py – Razorpay order creation and utilities
"""
import razorpay
from app.config import settings
from app.utils.logger import logger


def get_razorpay_client() -> razorpay.Client:
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


async def create_razorpay_order(amount_inr: float, receipt: str, notes: dict | None = None) -> dict:
    """
    Create a Razorpay order.
    amount_inr – amount in Indian Rupees (will be converted to paise).
    receipt    – short unique identifier (typically internal order_id).
    Returns the full Razorpay order dict.
    """
    client = get_razorpay_client()
    amount_paise = int(round(amount_inr * 100))

    payload = {
        "amount": amount_paise,
        "currency": "INR",
        "receipt": receipt[:40],   # Razorpay receipt limit = 40 chars
        "notes": notes or {},
        "payment_capture": 1,      # Auto-capture
    }

    try:
        order = client.order.create(data=payload)
        logger.info(f"Razorpay order created: {order['id']}  amount=₹{amount_inr}")
        return order
    except Exception as exc:
        logger.error(f"Razorpay order creation failed: {exc}")
        raise


async def fetch_razorpay_payment(payment_id: str) -> dict:
    """Fetch payment details from Razorpay."""
    client = get_razorpay_client()
    try:
        payment = client.payment.fetch(payment_id)
        return payment
    except Exception as exc:
        logger.error(f"Razorpay fetch payment failed: {exc}")
        raise


async def initiate_refund(payment_id: str, amount_paise: int, notes: dict | None = None) -> dict:
    """Initiate a full or partial refund."""
    client = get_razorpay_client()
    try:
        refund = client.payment.refund(payment_id, {"amount": amount_paise, "notes": notes or {}})
        logger.info(f"Refund initiated: payment={payment_id} amount_paise={amount_paise}")
        return refund
    except Exception as exc:
        logger.error(f"Razorpay refund failed: {exc}")
        raise
