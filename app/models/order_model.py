"""
order_model.py – Pydantic schemas for Orders and Payments
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class OrderStatus(str, Enum):
    PENDING_PAYMENT = "PENDING_PAYMENT"
    PAYMENT_VERIFIED = "PAYMENT_VERIFIED"
    DISPENSING = "DISPENSING"
    COMPLETED = "COMPLETED"
    FAILED_DISPENSE = "FAILED_DISPENSE"
    REFUNDED = "REFUNDED"
    CANCELLED = "CANCELLED"


class PaymentStatus(str, Enum):
    CREATED = "created"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"


class OrderItem(BaseModel):
    product_id: str
    product_name: str
    pad_type: str
    price: float
    quantity: int


class OrderCreate(BaseModel):
    user_id: str
    machine_id: str
    items: List[OrderItem]


class OrderInDB(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    user_id: str
    machine_id: str
    machine_name: str
    items: List[OrderItem]
    total_amount: float
    status: OrderStatus = OrderStatus.PENDING_PAYMENT
    razorpay_order_id: Optional[str] = None
    razorpay_payment_id: Optional[str] = None
    razorpay_signature: Optional[str] = None
    dispense_attempts: int = 0
    dispense_error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None

    model_config = {"populate_by_name": True}


class OrderResponse(BaseModel):
    id: str
    user_id: str
    machine_id: str
    machine_name: str
    items: List[OrderItem]
    total_amount: float
    status: OrderStatus
    razorpay_order_id: Optional[str] = None
    dispense_attempts: int
    created_at: datetime
    completed_at: Optional[datetime] = None


class RazorpayOrderResponse(BaseModel):
    order_id: str               # Internal order id
    razorpay_order_id: str
    razorpay_key_id: str
    amount: int                 # In paise
    currency: str
    total_amount_inr: float


class VendNowRequest(BaseModel):
    order_id: str
    user_id: str


class PaymentWebhookEvent(BaseModel):
    """Minimal shape of the Razorpay webhook payload we care about."""
    event: str
    payload: Dict[str, Any]
