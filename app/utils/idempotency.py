"""
idempotency.py – Guards against duplicate orders and duplicate payments.

Usage:
    from app.utils.idempotency import check_duplicate_order, check_duplicate_payment

Both raise HTTPException(409) if a duplicate is detected.
"""
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from app.database import get_collection


async def check_duplicate_order(user_id: str, machine_id: str, window_seconds: int = 30) -> None:
    """
    Raise 409 if the same user placed an identical order on the same machine
    within the last `window_seconds`. Prevents double-taps on 'Place Order'.
    """
    since = datetime.utcnow() - timedelta(seconds=window_seconds)
    col = get_collection("orders")
    existing = await col.find_one({
        "user_id": user_id,
        "machine_id": machine_id,
        "status": {"$in": ["PENDING_PAYMENT", "PAYMENT_VERIFIED", "DISPENSING"]},
        "created_at": {"$gte": since},
    })
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "duplicate_order",
                "message": "An active order already exists for this user and machine.",
                "existing_order_id": str(existing["_id"]),
            },
        )


async def check_duplicate_payment(razorpay_order_id: str) -> None:
    """
    Raise 409 if a payment record for this Razorpay order already exists and is paid.
    Prevents webhook replay attacks.
    """
    col = get_collection("payments")
    existing = await col.find_one({
        "razorpay_order_id": razorpay_order_id,
        "status": "paid",
    })
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "duplicate_payment",
                "message": "Payment for this Razorpay order has already been processed.",
                "razorpay_order_id": razorpay_order_id,
            },
        )
