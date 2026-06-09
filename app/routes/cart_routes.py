"""
cart_routes.py – Cart management (per-user, per-machine)
"""
from datetime import datetime
from bson import ObjectId
from fastapi import APIRouter, HTTPException, status

from app.database import get_collection
from app.models.cart_model import CartAddRequest, CartRemoveRequest, CartResponse, CartItem
from app.utils.logger import logger

router = APIRouter(prefix="/cart", tags=["Cart"])


async def _get_cart(user_id: str, machine_id: str) -> dict | None:
    col = get_collection("carts")
    return await col.find_one({"user_id": user_id, "machine_id": machine_id})


def _calc_total(items: list[dict]) -> float:
    return round(sum(i["price"] * i["quantity"] for i in items), 2)


def _doc_to_response(doc: dict) -> CartResponse:
    return CartResponse(
        id=str(doc["_id"]) if doc.get("_id") else None,
        user_id=doc["user_id"],
        machine_id=doc["machine_id"],
        items=[CartItem(**i) for i in doc.get("items", [])],
        total_amount=doc.get("total_amount", 0.0),
        item_count=sum(i["quantity"] for i in doc.get("items", [])),
    )


@router.get("/{user_id}", response_model=CartResponse, summary="Get user's cart")
async def get_cart(user_id: str, machine_id: str):
    cart = await _get_cart(user_id, machine_id)
    if not cart:
        return CartResponse(user_id=user_id, machine_id=machine_id, items=[], total_amount=0.0, item_count=0)
    return _doc_to_response(cart)


@router.post("/add", response_model=CartResponse, summary="Add item to cart")
async def add_to_cart(request: CartAddRequest):
    # Validate product exists
    p_col = get_collection("products")
    product = await p_col.find_one({"_id": ObjectId(request.product_id), "is_active": True})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    # Validate machine stock
    m_col = get_collection("machines")
    machine = await m_col.find_one({"_id": ObjectId(request.machine_id)})
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found.")

    available = machine.get("stock", {}).get(request.product_id, 0)
    if available < request.quantity:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Insufficient stock. Available: {available}",
        )

    cart_col = get_collection("carts")
    cart = await _get_cart(request.user_id, request.machine_id)
    now = datetime.utcnow()

    new_item = {
        "product_id": request.product_id,
        "product_name": product["name"],
        "pad_type": product["pad_type"],
        "price": product["price"],
        "quantity": request.quantity,
    }

    if cart:
        items: list = cart.get("items", [])
        # Update quantity if product already in cart
        found = False
        for item in items:
            if item["product_id"] == request.product_id:
                item["quantity"] += request.quantity
                found = True
                break
        if not found:
            items.append(new_item)

        total = _calc_total(items)
        await cart_col.update_one(
            {"_id": cart["_id"]},
            {"$set": {"items": items, "total_amount": total, "updated_at": now}},
        )
        cart["items"] = items
        cart["total_amount"] = total
        return _doc_to_response(cart)
    else:
        doc = {
            "user_id": request.user_id,
            "machine_id": request.machine_id,
            "items": [new_item],
            "total_amount": new_item["price"] * new_item["quantity"],
            "created_at": now,
            "updated_at": now,
        }
        result = await cart_col.insert_one(doc)
        doc["_id"] = result.inserted_id
        return _doc_to_response(doc)


@router.post("/remove", response_model=CartResponse, summary="Remove item from cart")
async def remove_from_cart(request: CartRemoveRequest):
    cart_col = get_collection("carts")
    # We need machine_id – caller provides it via query or body.
    # Simplified: find any cart for this user + product_id
    cart = await cart_col.find_one({"user_id": request.user_id, "items.product_id": request.product_id})
    if not cart:
        raise HTTPException(status_code=404, detail="Cart item not found.")

    items = [i for i in cart.get("items", []) if i["product_id"] != request.product_id]
    total = _calc_total(items)
    now = datetime.utcnow()

    await cart_col.update_one(
        {"_id": cart["_id"]},
        {"$set": {"items": items, "total_amount": total, "updated_at": now}},
    )
    cart["items"] = items
    cart["total_amount"] = total
    return _doc_to_response(cart)


@router.delete("/{user_id}", summary="Clear entire cart")
async def clear_cart(user_id: str, machine_id: str):
    col = get_collection("carts")
    await col.delete_many({"user_id": user_id, "machine_id": machine_id})
    return {"message": "Cart cleared."}
