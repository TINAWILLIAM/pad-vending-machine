"""
iot_routes.py – IoT / ESP32 communication endpoints.

These routes are called BY the ESP32 (machine → backend), not by the frontend.
"""
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Any

from app.database import get_collection
from app.models.machine_model import MachineStatus
from app.services.machine_service import get_machine_by_id, update_machine_status
from app.services.esp32_service import process_pending_commands
from app.utils.logger import logger

router = APIRouter(prefix="/iot", tags=["IoT / ESP32"])


# ── Request schemas ───────────────────────────────────────────────────────────

class DispenseCommandRequest(BaseModel):
    machine_id: str
    order_id: str
    items: list  # [{"product_id": ..., "quantity": ...}]


class MachineStatusUpdate(BaseModel):
    machine_id: str
    status: MachineStatus
    firmware_version: Optional[str] = None
    temperature_c: Optional[float] = None
    extra: Optional[dict[str, Any]] = None


class DispenseResultUpdate(BaseModel):
    order_id: str
    machine_id: str
    success: bool
    message: Optional[str] = None
    items_dispensed: Optional[list] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/command/dispense", summary="[Admin] Push a dispense command to an ESP32 machine")
async def push_dispense_command(request: DispenseCommandRequest):
    """
    Backend-initiated dispense (admin / retry path).
    Typically called from order_service.execute_vend — kept here as a
    REST-accessible endpoint for testing.
    """
    from app.services.esp32_service import send_dispense_command
    machine_raw = await get_collection("machines").find_one({"machine_code": request.machine_id})
    if not machine_raw:
        from bson import ObjectId
        try:
            machine_raw = await get_collection("machines").find_one({"_id": ObjectId(request.machine_id)})
        except Exception:
            pass

    if not machine_raw:
        raise HTTPException(status_code=404, detail="Machine not found.")

    result = await send_dispense_command(machine_raw, request.order_id, request.items)
    return result


@router.post("/status-update", summary="[ESP32 → Backend] Machine heartbeat / status report")
async def machine_status_update(update: MachineStatusUpdate):
    """
    Called by the ESP32 periodically to report its health.
    Backend updates machine status and flushes pending commands when the
    machine comes back online.
    """
    machine = await get_machine_by_id(update.machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found.")

    # Update status in DB
    await update_machine_status(update.machine_id, update.status)

    # Persist telemetry
    await get_collection("machine_telemetry").insert_one({
        "machine_id": update.machine_id,
        "status": update.status,
        "firmware_version": update.firmware_version,
        "temperature_c": update.temperature_c,
        "extra": update.extra or {},
        "recorded_at": datetime.utcnow(),
    })

    # If machine just came online, try to flush queued commands
    if update.status == MachineStatus.ONLINE:
        machine_raw = await get_collection("machines").find_one({"machine_code": update.machine_id})
        if machine_raw:
            await process_pending_commands(machine_raw)

    logger.info(f"[IoT] Machine {update.machine_id} status → {update.status}")
    return {"message": "Status received.", "machine_id": update.machine_id}


@router.post("/dispense-result", summary="[ESP32 → Backend] Report result of a dispense operation")
async def dispense_result(result: DispenseResultUpdate):
    """
    ESP32 calls this after attempting to dispense items to confirm success or failure.
    """
    from app.models.order_model import OrderStatus
    from app.services.machine_service import deduct_stock
    from datetime import datetime
    from bson import ObjectId

    col = get_collection("orders")
    order = await col.find_one({"_id": ObjectId(result.order_id)})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    current_status = order.get("status")

    if current_status == OrderStatus.COMPLETED:
        logger.info(f"[IoT] Order {result.order_id} is already COMPLETED. Skipping duplicate status update and stock deduction.")
        return {"message": "Order already completed."}

    if current_status not in (OrderStatus.DISPENSING, OrderStatus.FAILED_DISPENSE):
        logger.warning(f"[IoT] Order {result.order_id} status is {current_status}. Dispense result ignored (no stock deduction).")
        return {"message": f"Order status is {current_status}. Action ignored."}

    if result.success:
        items = result.items_dispensed or []
        if items:
            await deduct_stock(result.machine_id, items)

        await col.update_one(
            {"_id": ObjectId(result.order_id)},
            {
                "$set": {
                    "status": OrderStatus.COMPLETED,
                    "completed_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        logger.info(f"[IoT] Dispense SUCCESS for order {result.order_id}")
    else:
        await col.update_one(
            {"_id": ObjectId(result.order_id)},
            {
                "$set": {
                    "status": OrderStatus.FAILED_DISPENSE,
                    "dispense_error": result.message,
                    "updated_at": datetime.utcnow(),
                }
            },
        )
        logger.warning(f"[IoT] Dispense FAILED for order {result.order_id}: {result.message}")

    return {"message": "Result recorded."}


@router.get("/pending-commands/{machine_id}", summary="[ESP32] Poll for pending commands")
async def get_pending_commands(machine_id: str):
    """
    ESP32 polls this endpoint to get any queued commands when it reconnects.
    """
    col = get_collection("pending_commands")
    cursor = col.find({"machine_id": machine_id, "status": "queued"})
    commands = []
    async for cmd in cursor:
        cmd["id"] = str(cmd.pop("_id"))
        commands.append(cmd)

    # Mark as delivered
    if commands:
        ids = [c["id"] for c in commands]
        from bson import ObjectId
        await col.update_many(
            {"_id": {"$in": [ObjectId(i) for i in ids]}},
            {"$set": {"status": "delivered", "delivered_at": datetime.utcnow()}},
        )

    return {"commands": commands}
