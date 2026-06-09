"""
machine_routes.py – Machine CRUD, stock management, and location APIs
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Optional

from app.models.machine_model import (
    MachineRegister,
    MachineUpdate,
    MachineResponse,
    StockUpdate,
    MachineStatus,
)
from app.services.machine_service import (
    register_machine,
    get_machine_by_id,
    get_all_machines,
    update_machine,
    update_machine_status,
    update_stock,
    get_nearest_machine,
)
from app.utils.logger import logger

router = APIRouter(prefix="/machine", tags=["Machines"])


# ── Location / nearest machine ─────────────────────────────────────────────────

class LocationRequest(BaseModel):
    latitude: float
    longitude: float
    user_id: Optional[str] = None


@router.post("/nearest", summary="Find the nearest vending machine for a given location")
async def nearest_machine(loc: LocationRequest):
    machine = await get_nearest_machine(loc.latitude, loc.longitude)
    if not machine:
        raise HTTPException(status_code=404, detail="No machines found.")
    return machine


# ── CRUD ───────────────────────────────────────────────────────────────────────

@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    summary="Register a new vending machine",
)
async def register(data: MachineRegister):
    try:
        machine = await register_machine(data)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return machine


@router.get("", summary="List all machines")
async def list_machines():
    return await get_all_machines()


@router.get("/{machine_id}", summary="Get machine details by ID or machine_code")
async def get_machine(machine_id: str):
    machine = await get_machine_by_id(machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found.")
    return machine


@router.patch("/{machine_id}", summary="Update machine details")
async def update(machine_id: str, data: MachineUpdate):
    machine = await update_machine(machine_id, data)
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found.")
    return machine


# ── Stock management ──────────────────────────────────────────────────────────

@router.put("/{machine_id}/stock", summary="Set stock quantity for a product on a machine")
async def set_stock(machine_id: str, data: StockUpdate):
    try:
        machine = await update_stock(machine_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"message": "Stock updated.", "machine": machine}


@router.get("/{machine_id}/stock", summary="Get current stock for a machine")
async def get_stock(machine_id: str):
    machine = await get_machine_by_id(machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found.")
    return {"machine_id": machine_id, "stock": machine.get("stock", {})}


# ── Dispense (admin / direct trigger) ─────────────────────────────────────────

@router.post("/dispense", summary="Admin: directly trigger dispense on a machine")
async def admin_dispense(order_id: str, machine_id: str):
    """Admin endpoint to manually re-trigger dispensing for a given order."""
    from app.services.order_service import execute_vend
    try:
        result = await execute_vend(order_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return result
