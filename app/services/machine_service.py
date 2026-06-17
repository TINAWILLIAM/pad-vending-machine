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
    try:
        filt = {"_id": ObjectId(machine_id)}
    except Exception:
        filt = {"machine_code": machine_id}

    machine = await col.find_one(filt)
    if not machine:
        logger.error(f"[STOCK DEDUCTION ERROR] Machine not found for ID/code: {machine_id}")
        return

    current_stock = machine.get("stock", {})
    update_ops: dict = {}
    
    logger.info(f"[STOCK DEDUCTION] Starting deduction for machine: {machine.get('name')} (id/code: {machine_id})")
    
    for item in items:
        product_id = item["product_id"]
        qty = item["quantity"]
        stock_before = current_stock.get(product_id, 0)
        
        logger.info(f"  - Product {product_id}: Stock Before = {stock_before}, Quantity Dispensed = {qty}")
        
        new_qty = max(0, stock_before - qty)
        update_ops[f"stock.{product_id}"] = new_qty
        
        logger.info(f"  - Product {product_id}: Stock After (calculated) = {new_qty}")

    await col.update_one(
        {"_id": machine["_id"]},
        {"$set": {**update_ops, "updated_at": datetime.utcnow()}}
    )
    logger.info(f"[STOCK DEDUCTION SUCCESS] Stock updated successfully for machine {machine_id}")


async def get_nearest_machine(lat: float, lon: float) -> Optional[dict]:
    machines = await get_all_machines()
    return find_nearest_machine(lat, lon, machines)
