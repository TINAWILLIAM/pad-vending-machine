"""
location_routes.py – User location submission and nearest machine lookup
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.services.machine_service import get_nearest_machine
from app.utils.logger import logger

router = APIRouter(prefix="/location", tags=["Location"])


class LocationUpdateRequest(BaseModel):
    user_id: str
    latitude: float
    longitude: float


@router.post("/update", summary="Submit user location and get nearest machine")
async def update_location(request: LocationUpdateRequest):
    """
    Called after OTP verification if the user grants location access.
    Returns the nearest vending machine.
    """
    machine = await get_nearest_machine(request.latitude, request.longitude)
    if not machine:
        return {"nearest_machine": None, "message": "No machines available near you."}

    logger.info(
        f"User {request.user_id} at ({request.latitude},{request.longitude}) → "
        f"nearest machine: {machine.get('machine_code')} ({machine.get('distance_km')} km)"
    )
    return {"nearest_machine": machine}


@router.get("/nearest-machine", summary="Get nearest machine by lat/lon query params")
async def nearest_machine(lat: float, lon: float):
    machine = await get_nearest_machine(lat, lon)
    if not machine:
        raise HTTPException(status_code=404, detail="No machines found near this location.")
    return machine
