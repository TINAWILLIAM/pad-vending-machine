"""
cart_model.py – Pydantic schemas for Cart
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class CartItem(BaseModel):
    product_id: str
    product_name: str
    pad_type: str
    price: float
    quantity: int = Field(..., ge=1)


class CartAddRequest(BaseModel):
    user_id: str
    product_id: str
    quantity: int = Field(1, ge=1)
    machine_id: str   # Cart is always tied to a specific machine


class CartRemoveRequest(BaseModel):
    user_id: str
    product_id: str


class CartInDB(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    user_id: str
    machine_id: str
    items: List[CartItem] = []
    total_amount: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"populate_by_name": True}


class CartResponse(BaseModel):
    id: Optional[str] = None
    user_id: str
    machine_id: str
    items: List[CartItem]
    total_amount: float
    item_count: int
