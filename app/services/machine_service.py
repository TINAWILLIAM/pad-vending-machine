"""
machine_service.py – Business logic for vending machines
"""
from datetime import datetime
from bson import ObjectId
from typing import Optional

from app.database import get_collection
from app.models.machine_model import MachineRegister, MachineUpdate, StockUpdate, MachineStatus
from app.utils.location_utils import find_nearest_machine
from app.utils.logger import logger


def _to_response(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    return doc


async def register_machine(data: MachineRegister) -> dict:
    col = get_collection("machines")
    existing = await col.find_one({"machine_code": data.machine_code})
    if existing:
        raise ValueError(f"Machine code '{data.machine_code}' already exists.")

    now = datetime.utcnow()
    machine_doc = {
        **data.model_dump(),
        "location": data.location.model_dump(),
        "status": MachineStatus.OFFLINE,
        "stock": {},
        "last_seen": None,
        "created_at": now,
        "updated_at": now,
    }
    result = await col.insert_one(machine_doc)
    machine_doc["_id"] = result.inserted_id
    logger.info(f"Machine registered: {data.machine_code}")
    return _to_response(machine_doc)


async def get_machine_by_id(machine_id: str) -> Optional[dict]:
    col = get_collection("machines")
    try:
        doc = await col.find_one({"_id": ObjectId(machine_id)})
    except Exception:
        doc = await col.find_one({"machine_code": machine_id})
    if doc:
        return _to_response(doc)
    return None


async def get_all_machines() -> list[dict]:
    col = get_collection("machines")
    cursor = col.find({})
    machines = []
    async for doc in cursor:
        machines.append(_to_response(doc))
    return machines


async def update_machine(machine_id: str, data: MachineUpdate) -> Optional[dict]:
    col = get_collection("machines")
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow()

    result = await col.find_one_and_update(
        {"_id": ObjectId(machine_id)},
        {"$set": update_data},
        return_document=True,
    )
    if result:
        return _to_response(result)
    return None


async def update_machine_status(machine_id: str, status: MachineStatus) -> None:
    col = get_collection("machines")
    await col.update_one(
        {"_id": ObjectId(machine_id)},
        {"$set": {"status": status, "last_seen": datetime.utcnow(), "updated_at": datetime.utcnow()}},
    )


async def update_stock(machine_id: str, data: StockUpdate) -> dict:
    col = get_collection("machines")
    stock_key = f"stock.{data.product_id}"
    result = await col.find_one_and_update(
        {"_id": ObjectId(machine_id)},
        {"$set": {stock_key: data.quantity, "updated_at": datetime.utcnow()}},
        return_document=True,
    )
    if not result:
        raise ValueError("Machine not found.")
    logger.info(f"Stock updated: machine={machine_id} product={data.product_id} qty={data.quantity}")
    return _to_response(result)


async def deduct_stock(machine_id: str, items: list[dict]) -> None:
    """Decrement stock for each dispensed item. Called after successful dispense."""
    col = get_collection("machines")
    update_ops: dict = {}
    for item in items:
        product_id = item["product_id"]
        qty = item["quantity"]
        update_ops[f"stock.{product_id}"] = -qty

    await col.update_one(
        {"_id": ObjectId(machine_id)},
        {"$inc": update_ops, "$set": {"updated_at": datetime.utcnow()}},
    )
    logger.info(f"Stock deducted for machine {machine_id}: {items}")


async def get_nearest_machine(lat: float, lon: float) -> Optional[dict]:
    machines = await get_all_machines()
    return find_nearest_machine(lat, lon, machines)
