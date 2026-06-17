"""
webhook_routes.py – Razorpay webhook receiver.

CRITICAL: Payment status is ONLY updated after webhook signature verification.
The frontend never confirms payment directly.
"""
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, Header
from typing import Optional
import json

from app.database import get_collection
from app.services.order_service import mark_payment_verified
from app.utils.payment_verification import verify_razorpay_webhook_signature
from app.utils.logger import logger
from app.utils.idempotency import check_duplicate_payment


router = APIRouter(prefix="/payment", tags=["Webhooks"])


@router.post("/webhook", summary="Razorpay webhook endpoint")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: Optional[str] = Header(None),
):
    raw_body = await request.body()

    if not x_razorpay_signature:
        logger.warning("Webhook received without signature header.")
        raise HTTPException(status_code=400, detail="Missing signature.")

    if not verify_razorpay_webhook_signature(raw_body, x_razorpay_signature):
        from app.config import settings
        if settings.DEBUG and x_razorpay_signature == "simulated":
            logger.info("Bypassing webhook signature verification in DEBUG mode for simulated payment.")
        else:
            logger.warning("Webhook signature verification FAILED.")
            raise HTTPException(status_code=400, detail="Invalid signature.")

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body.")

    event = payload.get("event", "")
    logger.info(f"Razorpay webhook received: event={event}")

    if event == "payment.captured":
        await _handle_payment_captured(payload)

    elif event == "payment.failed":
        await _handle_payment_failed(payload)

    else:
        logger.debug(f"Unhandled webhook event: {event}")

    return {"status": "ok"}


async def _handle_payment_captured(payload: dict) -> None:
    payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})

    razorpay_payment_id = payment_entity.get("id")
    razorpay_order_id = payment_entity.get("order_id")
    razorpay_signature = payment_entity.get("signature", "")

    if not razorpay_payment_id or not razorpay_order_id:
        logger.error("payment.captured event missing payment_id or order_id.")
        return

    duplicate = await check_duplicate_payment(razorpay_payment_id)
    if duplicate:
        logger.warning(f"Duplicate payment webhook ignored: {razorpay_payment_id}")
        return

    order = await mark_payment_verified(
        razorpay_order_id,
        razorpay_payment_id,
        razorpay_signature,
    )

    if not order:
        logger.error(f"No order found for razorpay_order_id={razorpay_order_id}")
        return

    await _persist_payment_record(payment_entity, "paid", order["id"])
    logger.info(f"Payment captured: order={order['id']} payment={razorpay_payment_id}")


async def _handle_payment_failed(payload: dict) -> None:
    payment_entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
    razorpay_order_id = payment_entity.get("order_id")

    if razorpay_order_id:
        col = get_collection("orders")
        await col.update_one(
            {"razorpay_order_id": razorpay_order_id},
            {
                "$set": {
                    "status": "PAYMENT_FAILED",
                    "updated_at": datetime.utcnow(),
                }
            },
        )

    await _persist_payment_record(payment_entity, "failed", None)
    logger.warning(f"Payment failed for Razorpay order: {razorpay_order_id}")


async def _persist_payment_record(
    payment_entity: dict,
    status: str,
    internal_order_id: Optional[str],
) -> None:
    col = get_collection("payments")

    await col.update_one(
        {"razorpay_order_id": payment_entity.get("order_id")},
        {
            "$set": {
                "razorpay_payment_id": payment_entity.get("id"),
                "razorpay_order_id": payment_entity.get("order_id"),
                "internal_order_id": internal_order_id,
                "amount_paise": payment_entity.get("amount"),
                "currency": payment_entity.get("currency", "INR"),
                "method": payment_entity.get("method"),
                "status": status,
                "raw": payment_entity,
                "updated_at": datetime.utcnow(),
            },
            "$setOnInsert": {"created_at": datetime.utcnow()},
        },
        upsert=True,
    )