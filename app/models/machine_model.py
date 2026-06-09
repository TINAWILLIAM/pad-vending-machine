"""
machine_model.py – Pydantic schemas for Vending Machines
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict
from datetime import datetime
from enum import Enum


class MachineStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


class MachineLocation(BaseModel):
    latitude: float
    longitude: float
    address: Optional[str] = None
    landmark: Optional[str] = None


class StockItem(BaseModel):
    product_id: str
    quantity: int = 0


class MachineRegister(BaseModel):
    machine_code: str = Field(..., min_length=3, max_length=50)
    name: str = Field(..., min_length=1, max_length=100)
    location: MachineLocation
    esp32_ip: Optional[str] = None         # Local IP of ESP32 (dev)
    esp32_endpoint: Optional[str] = None   # Full URL override (prod)


class MachineUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[MachineLocation] = None
    esp32_ip: Optional[str] = None
    esp32_endpoint: Optional[str] = None
    status: Optional[MachineStatus] = None


class StockUpdate(BaseModel):
    product_id: str
    quantity: int = Field(..., ge=0)


class MachineInDB(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    machine_code: str
    name: str
    location: MachineLocation
    status: MachineStatus = MachineStatus.OFFLINE
    esp32_ip: Optional[str] = None
    esp32_endpoint: Optional[str] = None
    # stock: { product_id -> quantity }
    stock: Dict[str, int] = {}
    last_seen: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"populate_by_name": True}


class MachineResponse(BaseModel):
    id: str
    machine_code: str
    name: str
    location: MachineLocation
    status: MachineStatus
    stock: Dict[str, int]
    last_seen: Optional[datetime] = None
    distance_km: Optional[float] = None   # Present only in nearest-machine queries


class DispenseCommand(BaseModel):
    order_id: str
    machine_id: str
    items: list  # [{"product_id": ..., "quantity": ...}]
