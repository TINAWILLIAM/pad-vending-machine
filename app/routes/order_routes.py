"""
order_routes.py – Order creation, retrieval, history, and vend-now
"""
from fastapi import APIRouter, HTTPException, status

from app.models.order_model import OrderCreate, OrderResponse, VendNowRequest
from app.services.order_service import (
    create_order,
    get_order,
    get_user_orders,
    execute_vend,
)
from app.utils.logger import logger

router = APIRouter(prefix="/order", tags=["Orders"])


@router.post(
    "/create",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new order from cart",
)
async def create_new_order(data: OrderCreate):
    try:
        order = await create_order(data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return order


@router.get("/{order_id}", response_model=OrderResponse, summary="Fetch a single order")
async def fetch_order(order_id: str):
    order = await get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")
    return order


@router.get(
    "/history/{user_id}",
    response_model=list[OrderResponse],
    summary="Get order history for a user",
)
async def order_history(user_id: str, limit: int = 50):
    orders = await get_user_orders(user_id, limit=limit)
    return orders


@router.post("/vend", summary="Trigger dispense after payment verification")
async def vend_now(request: VendNowRequest):
    """
    Called by the frontend when the user clicks 'Vend Now'.
    Validates payment status and sends dispense command to ESP32.
    """
    try:
        result = await execute_vend(request.order_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not result["success"]:
        raise HTTPException(status_code=503, detail=result["message"])

    return result
