"""
product_routes.py – CRUD for sanitary pad products
"""
from datetime import datetime
from bson import ObjectId
from fastapi import APIRouter, HTTPException, status, Query
from typing import Optional

from app.database import get_collection
from app.models.product_model import ProductCreate, ProductUpdate, ProductResponse
from app.utils.logger import logger

router = APIRouter(prefix="/products", tags=["Products"])


def _to_response(doc: dict, stock: int = 0, stock_by_machine: Optional[dict] = None) -> ProductResponse:
    return ProductResponse(
        id=str(doc["_id"]),
        name=doc["name"],
        pad_type=str(doc["pad_type"]).lower(),
        description=doc.get("description"),
        price=doc["price"],
        image_url=doc.get("image_url"),
        is_active=doc.get("is_active", True),
        available_stock=stock,
        stock_by_machine=stock_by_machine,
    )


@router.get("", response_model=list[ProductResponse], summary="List all active products")
async def list_products(machine_id: Optional[str] = Query(None, description="Filter stock for this machine")):
    """
    Return all active products. If machine_id is provided, attach that
    machine's stock quantities to each product.
    """
    col = get_collection("products")
    cursor = col.find({"is_active": True})
    products = []

    m_col = get_collection("machines")
    # Fetch all active machines to build stock_by_machine dictionary
    all_machines = []
    async for m in m_col.find({"is_active": {"$ne": False}}):
        all_machines.append(m)

    machine_stock: dict = {}
    if machine_id:
        m_doc = next((m for m in all_machines if str(m["_id"]) == machine_id or m["machine_code"] == machine_id), None)
        if m_doc:
            machine_stock = m_doc.get("stock", {})

    async for doc in cursor:
        pid = str(doc["_id"])
        stock = machine_stock.get(pid, 0)
        
        # Build stock_by_machine map for all machines
        stock_by_mach = {}
        for m in all_machines:
            qty = m.get("stock", {}).get(pid, 0)
            stock_by_mach[str(m["_id"])] = {
                "machine_name": m["name"],
                "quantity": qty,
            }
            
        products.append(_to_response(doc, stock, stock_by_mach))

    return products


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED, summary="Create a product")
async def create_product(data: ProductCreate):
    col = get_collection("products")
    now = datetime.utcnow()
    doc = {**data.model_dump(), "is_active": True, "created_at": now, "updated_at": now}
    result = await col.insert_one(doc)
    doc["_id"] = result.inserted_id
    logger.info(f"Product created: {data.name}")
    return _to_response(doc)


@router.get("/{product_id}", response_model=ProductResponse, summary="Get a single product")
async def get_product(product_id: str, machine_id: Optional[str] = None):
    col = get_collection("products")
    doc = await col.find_one({"_id": ObjectId(product_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Product not found.")

    m_col = get_collection("machines")
    all_machines = []
    async for m in m_col.find({"is_active": {"$ne": False}}):
        all_machines.append(m)

    stock = 0
    if machine_id:
        m_doc = next((m for m in all_machines if str(m["_id"]) == machine_id or m["machine_code"] == machine_id), None)
        if m_doc:
            stock = m_doc.get("stock", {}).get(product_id, 0)

    stock_by_mach = {}
    for m in all_machines:
        qty = m.get("stock", {}).get(product_id, 0)
        stock_by_mach[str(m["_id"])] = {
            "machine_name": m["name"],
            "quantity": qty,
        }

    return _to_response(doc, stock, stock_by_mach)


@router.patch("/{product_id}", response_model=ProductResponse, summary="Update a product")
async def update_product(product_id: str, data: ProductUpdate):
    col = get_collection("products")
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow()

    result = await col.find_one_and_update(
        {"_id": ObjectId(product_id)},
        {"$set": update_data},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Product not found.")
    return _to_response(result)


@router.delete("/{product_id}", summary="Soft-delete a product")
async def delete_product(product_id: str):
    col = get_collection("products")
    result = await col.update_one(
        {"_id": ObjectId(product_id)},
        {"$set": {"is_active": False, "updated_at": datetime.utcnow()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Product not found.")
    return {"message": "Product deactivated."}
