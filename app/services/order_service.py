"""
order_service.py – Business logic for order lifecycle
"""
from datetime import datetime
from bson import ObjectId
from typing import Optional

from app.database import get_collection
from app.models.order_model import OrderCreate, OrderStatus
from app.services.machine_service import get_machine_by_id, deduct_stock
from app.services.esp32_service import send_dispense_command
from app.utils.logger import logger
from app.utils.idempotency import check_duplicate_order


def _to_response(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    return doc


async def create_order(data: OrderCreate) -> dict:
    machine = await get_machine_by_id(data.machine_id)
    if not machine:
        raise ValueError("Machine not found.")

    await check_duplicate_order(data.user_id, data.machine_id)

    total_amount = sum(item.price * item.quantity for item in data.items)

    now = datetime.utcnow()
    order_doc = {
        "user_id": data.user_id,
        "machine_id": data.machine_id,
        "machine_name": machine.get("name", "Unknown"),
        "items": [item.model_dump() for item in data.items],
        "total_amount": round(total_amount, 2),
        "payment_method": "UPI",
        "status": OrderStatus.PENDING_PAYMENT,
        "razorpay_order_id": None,
        "razorpay_payment_id": None,
        "razorpay_signature": None,
        "dispense_attempts": 0,
        "dispense_error": None,
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
    }

    col = get_collection("orders")
    result = await col.insert_one(order_doc)
    order_doc["_id"] = result.inserted_id

    logger.info(f"Order created: {result.inserted_id} total=₹{total_amount}")
    return _to_response(order_doc)


async def get_order(order_id: str) -> Optional[dict]:
    col = get_collection("orders")
    doc = await col.find_one({"_id": ObjectId(order_id)})
    if doc:
        return _to_response(doc)
    return None


async def get_order_by_razorpay_id(razorpay_order_id: str) -> Optional[dict]:
    col = get_collection("orders")
    doc = await col.find_one({"razorpay_order_id": razorpay_order_id})
    if doc:
        return _to_response(doc)
    return None


async def get_user_orders(user_id: str, limit: int = 50) -> list[dict]:
    col = get_collection("orders")
    cursor = col.find({"user_id": user_id}).sort("created_at", -1).limit(limit)

    orders = []
    async for doc in cursor:
        orders.append(_to_response(doc))
    return orders


async def attach_razorpay_order(order_id: str, razorpay_order_id: str) -> None:
    col = get_collection("orders")
    await col.update_one(
        {"_id": ObjectId(order_id)},
        {
            "$set": {
                "razorpay_order_id": razorpay_order_id,
                "updated_at": datetime.utcnow(),
            }
        },
    )


async def mark_payment_verified(
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
) -> Optional[dict]:
    col = get_collection("orders")

    result = await col.find_one_and_update(
        {"razorpay_order_id": razorpay_order_id},
        {
            "$set": {
                "status": OrderStatus.PAYMENT_VERIFIED,
                "payment_method": "UPI",
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_signature": razorpay_signature,
                "updated_at": datetime.utcnow(),
            }
        },
        return_document=True,
    )

    if result:
        logger.info(f"Payment verified for Razorpay order {razorpay_order_id}")
        return _to_response(result)

    return None


async def execute_vend(order_id: str) -> dict:
    """
    Validate order, send dispense command to ESP32,
    deduct stock, increase sales volume, and update order status.
    """
    order = await get_order(order_id)
    if not order:
        raise ValueError("Order not found.")

    if order["status"] not in (OrderStatus.PAYMENT_VERIFIED, OrderStatus.FAILED_DISPENSE):
        raise ValueError(f"Order is not ready to vend. Current status: {order['status']}")

    machine = await get_machine_by_id(order["machine_id"])
    if not machine:
        raise ValueError("Machine not found.")

    items = [
        {
            "product_id": i["product_id"],
            "quantity": i["quantity"],
        }
        for i in order["items"]
    ]

    col = get_collection("orders")

    await col.update_one(
        {"_id": ObjectId(order_id)},
        {
            "$inc": {"dispense_attempts": 1},
            "$set": {
                "status": OrderStatus.DISPENSING,
                "updated_at": datetime.utcnow(),
            },
        },
    )

    machine_raw = await get_collection("machines").find_one(
        {"_id": ObjectId(order["machine_id"])}
    )

    result = await send_dispense_command(machine_raw, order_id, items)

    if result["success"]:
        await deduct_stock(order["machine_id"], items)

        products_col = get_collection("products")
        for item in items:
            await products_col.update_one(
                {"_id": ObjectId(item["product_id"])},
                {"$inc": {"sales_volume": item["quantity"]}},
            )

        await col.update_one(
            {"_id": ObjectId(order_id)},
            {
                "$set": {
                    "status": OrderStatus.COMPLETED,
                    "completed_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }
            },
        )

        logger.info(f"[VEND SUCCESS] Order {order_id} completed successfully. Status set to: {OrderStatus.COMPLETED.value}")
        return {
            "success": True,
            "message": "Items dispensed successfully!",
            "order_id": order_id,
        }

    await col.update_one(
        {"_id": ObjectId(order_id)},
        {
            "$set": {
                "status": OrderStatus.FAILED_DISPENSE,
                "dispense_error": result.get("message"),
                "updated_at": datetime.utcnow(),
            }
        },
    )

    logger.warning(f"[VEND FAILURE] Order {order_id} dispense failed: {result.get('message')}. Status set to: {OrderStatus.FAILED_DISPENSE.value}")
    return {
        "success": False,
        "message": result.get("message", "Dispense failed. Please retry."),
        "order_id": order_id,
    }