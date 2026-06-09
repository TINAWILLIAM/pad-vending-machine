"""
product_model.py – Pydantic schemas for Products
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class PadType(str, Enum):
    REGULAR = "regular"
    MEDIUM = "medium"
    XL = "xl"
    XXL = "xxl"


class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    pad_type: PadType
    description: Optional[str] = None
    price: float = Field(..., gt=0)
    image_url: Optional[str] = None


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = Field(None, gt=0)
    image_url: Optional[str] = None
    is_active: Optional[bool] = None


class ProductInDB(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    name: str
    pad_type: PadType
    description: Optional[str] = None
    price: float
    image_url: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = {"populate_by_name": True}


class ProductResponse(BaseModel):
    id: str
    name: str
    pad_type: PadType
    description: Optional[str] = None
    price: float
    image_url: Optional[str] = None
    is_active: bool
    available_stock: int = 0  # Injected from machine stock at query time
