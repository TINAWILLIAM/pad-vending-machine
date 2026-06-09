"""
payment_routes.py – Razorpay order creation (initiate payment)
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.razorpay_service import create_razorpay_order
from app.services.order_service import get_order, attach_razorpay_order
from app.models.order_model import RazorpayOrderResponse
from app.config import settings
from app.utils.logger import logger

router = APIRouter(prefix="/payment", tags=["Payments"])


class InitiatePaymentRequest(BaseModel):
    order_id: str   # Internal order _id


@router.post(
    "/create-order",
    response_model=RazorpayOrderResponse,
    summary="Create a Razorpay payment order for an internal order",
)
async def create_payment_order(request: InitiatePaymentRequest):
    """
    Fetches the internal order, calls Razorpay to create a payment order,
    persists the Razorpay order ID, and returns everything the frontend
    needs to launch the Razorpay checkout modal.
    """
    order = await get_order(request.order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    if order.get("razorpay_order_id"):
        # Already has a Razorpay order – return it without creating a new one
        return RazorpayOrderResponse(
            order_id=request.order_id,
            razorpay_order_id=order["razorpay_order_id"],
            razorpay_key_id=settings.RAZORPAY_KEY_ID,
            amount=int(order["total_amount"] * 100),
            currency="INR",
            total_amount_inr=order["total_amount"],
        )

    try:
        rzp_order = await create_razorpay_order(
            amount_inr=order["total_amount"],
            receipt=request.order_id[:40],
            notes={"internal_order_id": request.order_id},
        )
    except Exception as exc:
        logger.error(f"Razorpay create-order failed: {exc}")
        raise HTTPException(status_code=502, detail="Payment gateway error. Please retry.")

    await attach_razorpay_order(request.order_id, rzp_order["id"])

    return RazorpayOrderResponse(
        order_id=request.order_id,
        razorpay_order_id=rzp_order["id"],
        razorpay_key_id=settings.RAZORPAY_KEY_ID,
        amount=rzp_order["amount"],
        currency=rzp_order["currency"],
        total_amount_inr=order["total_amount"],
    )
