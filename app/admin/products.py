"""
admin/products.py – Admin product management.

GET  /admin/products           – All products across all machines with sales volume
POST /admin/products           – Create product in a specific machine block
PATCH /admin/products/{id}     – Update product details
DELETE /admin/products/{id}    – Soft-delete product
PATCH /admin/products/{id}/stock – Set stock level on a specific machine
"""
from datetime import datetime
from typing import Optional
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field

from app.database import get_collection
from app.admin.dependencies import require_admin_token

router = APIRouter(prefix="/admin", tags=["Admin – Products"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class AdminProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    pad_type: str                    # regular | medium | xl | xxl
    description: Optional[str] = None
    price: float = Field(..., gt=0)
    machine_id: str                  # Which machine block to assign stock
    initial_stock: int = Field(0, ge=0)
    image_url: Optional[str] = None
    category: Optional[str] = None


class AdminProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = Field(None, gt=0)
    image_url: Optional[str] = None
    is_active: Optional[bool] = None
    category: Optional[str] = None


class AdminStockUpdate(BaseModel):
    machine_id: str
    quantity: int = Field(..., ge=0)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_sales_volume(product_id: str) -> int:
    """Count total units sold for a product across all completed orders."""
    col = get_collection("orders")
    pipeline = [
        {"$match": {"status": "COMPLETED"}},
        {"$unwind": "$items"},
        {"$match": {"items.product_id": product_id}},
        {"$group": {"_id": None, "sold": {"$sum": "$items.quantity"}}},
    ]
    result = await col.aggregate(pipeline).to_list(1)
    return result[0]["sold"] if result else 0


async def _build_product_response(doc: dict, machine_filter: Optional[str] = None) -> dict:
    """Attach stock levels (per machine or aggregated) and sales volume."""
    product_id = str(doc["_id"])

    # Gather stock across all machines
    machines_col = get_collection("machines")
    stock_by_machine: dict = {}

    if machine_filter:
        try:
            m = await machines_col.find_one({"_id": ObjectId(machine_filter)})
        except Exception:
            m = await machines_col.find_one({"machine_code": machine_filter})
        if m:
            qty = m.get("stock", {}).get(product_id, 0)
            stock_by_machine[str(m["_id"])] = {
                "machine_name": m["name"],
                "quantity": qty,
            }
    else:
        cursor = machines_col.find({})
        async for m in cursor:
            qty = m.get("stock", {}).get(product_id, 0)
            stock_by_machine[str(m["_id"])] = {
                "machine_name": m["name"],
                "quantity": qty,
            }

    total_stock = sum(v["quantity"] for v in stock_by_machine.values())
    stock_status = "in_stock" if total_stock > 10 else ("low_stock" if total_stock > 0 else "out_of_stock")
    sales_volume = await _get_sales_volume(product_id)

    return {
        "product_id": product_id,
        "name": doc["name"],
        "pad_type": doc.get("pad_type", ""),
        "category": doc.get("category", doc.get("pad_type", "")),
        "description": doc.get("description", ""),
        "price": doc["price"],
        "image_url": doc.get("image_url"),
        "is_active": doc.get("is_active", True),
        "stock_by_machine": stock_by_machine,
        "total_stock": total_stock,
        "stock_status": stock_status,
        "sales_volume": sales_volume,
        "created_at": doc.get("created_at", "").isoformat()
        if isinstance(doc.get("created_at"), datetime)
        else "",
        "updated_at": doc.get("updated_at", "").isoformat()
        if isinstance(doc.get("updated_at"), datetime)
        else "",
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/products", summary="List all products with stock and sales analytics")
async def admin_list_products(
    machine_id: Optional[str] = Query(None),
    pad_type: Optional[str] = Query(None, description="Filter: regular | medium | xl | xxl"),
    sort_by: Optional[str] = Query(
        None, description="quantity_asc | quantity_desc | sales_desc"
    ),
    _: dict = Depends(require_admin_token),
):
    col = get_collection("products")
    query: dict = {}
    if pad_type:
        query["pad_type"] = pad_type.lower()

    cursor = col.find(query)
    products = []
    async for doc in cursor:
        products.append(await _build_product_response(doc, machine_filter=machine_id))

    # Sorting
    if sort_by == "quantity_asc":
        products.sort(key=lambda p: p["total_stock"])
    elif sort_by == "quantity_desc":
        products.sort(key=lambda p: p["total_stock"], reverse=True)
    elif sort_by == "sales_desc":
        products.sort(key=lambda p: p["sales_volume"], reverse=True)

    return {"count": len(products), "products": products}


@router.post(
    "/products",
    status_code=status.HTTP_201_CREATED,
    summary="Create product and assign initial stock to a machine block",
)
async def admin_create_product(
    data: AdminProductCreate,
    _: dict = Depends(require_admin_token),
):
    now = datetime.utcnow()
    doc = {
        "name": data.name,
        "pad_type": data.pad_type,
        "category": data.category or data.pad_type,
        "description": data.description,
        "price": data.price,
        "image_url": data.image_url,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    col = get_collection("products")
    result = await col.insert_one(doc)
    product_id = str(result.inserted_id)

    # Set initial stock on the specified machine
    if data.initial_stock > 0:
        machines_col = get_collection("machines")
        try:
            filt = {"_id": ObjectId(data.machine_id)}
        except Exception:
            filt = {"machine_code": data.machine_id}
        await machines_col.update_one(
            filt,
            {
                "$set": {
                    f"stock.{product_id}": data.initial_stock,
                    "updated_at": now,
                }
            },
        )

    doc["_id"] = result.inserted_id
    return await _build_product_response(doc)


@router.patch("/products/{product_id}", summary="Update product metadata")
async def admin_update_product(
    product_id: str,
    data: AdminProductUpdate,
    _: dict = Depends(require_admin_token),
):
    col = get_collection("products")
    update = {k: v for k, v in data.model_dump().items() if v is not None}
    update["updated_at"] = datetime.utcnow()

    result = await col.find_one_and_update(
        {"_id": ObjectId(product_id)},
        {"$set": update},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Product not found.")
    return await _build_product_response(result)


@router.delete("/products/{product_id}", summary="Soft-delete a product")
async def admin_delete_product(
    product_id: str,
    _: dict = Depends(require_admin_token),
):
    col = get_collection("products")
    result = await col.update_one(
        {"_id": ObjectId(product_id)},
        {"$set": {"is_active": False, "updated_at": datetime.utcnow()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Product not found.")
    return {"message": "Product deactivated.", "product_id": product_id}


@router.patch("/products/{product_id}/stock", summary="Update stock level for a product on a machine")
async def admin_update_stock(
    product_id: str,
    data: AdminStockUpdate,
    _: dict = Depends(require_admin_token),
):
    machines_col = get_collection("machines")
    try:
        filt = {"_id": ObjectId(data.machine_id)}
    except Exception:
        filt = {"machine_code": data.machine_id}

    result = await machines_col.find_one_and_update(
        filt,
        {
            "$set": {
                f"stock.{product_id}": data.quantity,
                "updated_at": datetime.utcnow(),
            }
        },
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Machine not found.")

    return {
        "message": "Stock updated.",
        "product_id": product_id,
        "machine_id": str(result["_id"]),
        "new_quantity": data.quantity,
    }
