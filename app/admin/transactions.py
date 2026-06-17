"""
admin/transactions.py – GET /admin/transactions, GET /admin/transactions/search, PATCH /admin/transactions/{order_id}/status

Manages online transactions, search filters, and status updates.
"""
from datetime import datetime
from typing import Optional
from bson import ObjectId
from fastapi import APIRouter, Depends, Query, HTTPException

from app.database import get_collection
from app.admin.dependencies import require_admin_token

router = APIRouter(prefix="/admin", tags=["Admin – Transactions"])


def _map_status(db_status: str) -> str:
    db_status = (db_status or "").upper()
    if db_status == "PENDING_PAYMENT":
        return "Pending"
    elif db_status in ("PAYMENT_VERIFIED", "DISPENSING"):
        return "Paid"
    elif db_status == "COMPLETED":
        return "Dispensed"
    elif db_status == "FAILED_DISPENSE":
        return "Failed"
    elif db_status in ("CANCELLED", "REFUNDED"):
        return "Cancelled"
    return db_status


async def _format_tx(doc: dict) -> dict:
    user_id = doc.get("user_id", "")
    customer_email = "Anonymous"
    
    if user_id and not user_id.startswith("coin:"):
        try:
            users_col = get_collection("users")
            user = await users_col.find_one({"_id": ObjectId(user_id)})
            if user:
                customer_email = user.get("email", "Anonymous")
        except Exception:
            customer_email = user_id
            
    items = doc.get("items", [])
    product_names = list(set(item.get("product_name", "") for item in items))
    product_str = ", ".join(product_names) if product_names else "N/A"
    
    items_summary = ", ".join(f"{item.get('pad_type', '').upper()} (x{item.get('quantity', 0)})" for item in items)
    
    return {
        "order_id": str(doc["_id"]),
        "customer_email": customer_email,
        "machine_name": doc.get("machine_name", "Unknown Machine"),
        "product": product_str,
        "items": items_summary,
        "amount": doc.get("total_amount", 0.0),
        "payment_method": doc.get("payment_method", "UPI"),
        "status": _map_status(doc.get("status", "")),
        "date_time": doc["created_at"].isoformat() if isinstance(doc.get("created_at"), datetime) else doc.get("created_at", ""),
    }


@router.get("/transactions", summary="List all online transactions with search & filter")
async def list_transactions(
    payment_method: Optional[str] = Query(None, description="Filter: UPI or COIN or ALL"),
    status: Optional[str] = Query(None, description="Filter by status (Pending, Paid, Dispensed, Failed, Cancelled)"),
    q: Optional[str] = Query(None, description="Search term for order ID, customer email, machine name, product, method, amount, date"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _: dict = Depends(require_admin_token),
):
    col = get_collection("orders")
    
    # 1. Base query filter
    query: dict = {}
    if payment_method:
        if payment_method.upper() != "ALL":
            query["payment_method"] = payment_method.upper()
    else:
        # Default: Exclude coin transactions for now to only show online transactions
        query["payment_method"] = {"$ne": "COIN"}
        
    # 2. Status filter mapping
    if status:
        db_statuses = []
        if status == "Pending":
            db_statuses = ["PENDING_PAYMENT"]
        elif status == "Paid":
            db_statuses = ["PAYMENT_VERIFIED", "DISPENSING"]
        elif status == "Dispensed":
            db_statuses = ["COMPLETED"]
        elif status == "Failed":
            db_statuses = ["FAILED_DISPENSE"]
        elif status == "Cancelled":
            db_statuses = ["CANCELLED", "REFUNDED"]
        else:
            db_statuses = [status.upper()]
        query["status"] = {"$in": db_statuses}
        
    # 3. Search parameters
    if q:
        q_clean = q.strip()
        search_terms = []
        
        # Order ID exact match
        try:
            search_terms.append({"_id": ObjectId(q_clean)})
        except Exception:
            pass
            
        # Regex matches
        search_terms.append({"machine_name": {"$regex": q_clean, "$options": "i"}})
        search_terms.append({"items.product_name": {"$regex": q_clean, "$options": "i"}})
        search_terms.append({"items.pad_type": {"$regex": q_clean, "$options": "i"}})
        search_terms.append({"payment_method": {"$regex": q_clean, "$options": "i"}})
        
        # Amount match
        try:
            val = float(q_clean)
            search_terms.append({"total_amount": val})
        except ValueError:
            pass
            
        # Customer Email search
        users_col = get_collection("users")
        matching_users = await users_col.find({"email": {"$regex": q_clean, "$options": "i"}}).to_list(100)
        user_ids = [str(u["_id"]) for u in matching_users]
        if user_ids:
            search_terms.append({"user_id": {"$in": user_ids}})
        search_terms.append({"user_id": {"$regex": q_clean, "$options": "i"}})
        
        query["$or"] = search_terms

    total_count = await col.count_documents(query)
    skip = (page - 1) * limit
    cursor = col.find(query).sort("created_at", -1).skip(skip).limit(limit)
    
    transactions = []
    async for doc in cursor:
        transactions.append(await _format_tx(doc))

    # Summary metrics for header cards (excl. COIN for total transactions count)
    total_successful_query = {
        "status": {"$in": ["COMPLETED", "completed", "Dispensed", "dispensed"]},
        "payment_method": {"$ne": "COIN"}
    }
    total_successful_count = await col.count_documents(total_successful_query)
    
    # Coin revenue calculation (successful coin orders)
    coin_query = {"status": "COMPLETED", "payment_method": "COIN"}
    coin_rev_pipeline = [
        {"$match": coin_query},
        {"$group": {"_id": None, "total": {"$sum": "$total_amount"}}}
    ]
    coin_rev_res = await col.aggregate(coin_rev_pipeline).to_list(1)
    coin_revenue = coin_rev_res[0]["total"] if coin_rev_res else 0.0

    fallback = None
    if total_count == 0:
        fallback = "No orders found matching the filter selection."

    return {
        "metrics": {
            "total_transactions": total_successful_count,
            "coin_revenue": round(coin_revenue, 2),
        },
        "pagination": {
            "total": total_count,
            "page": page,
            "limit": limit,
            "pages": -(-total_count // limit),
        },
        "transactions": transactions,
        "fallback_message": fallback,
    }


@router.patch("/transactions/{order_id}/status", summary="Update transaction status")
async def update_transaction_status(
    order_id: str,
    status_update: dict,
    _: dict = Depends(require_admin_token),
):
    col = get_collection("orders")
    disp_status = status_update.get("status")
    
    db_status = None
    if disp_status == "Pending":
        db_status = "PENDING_PAYMENT"
    elif disp_status == "Paid":
        db_status = "PAYMENT_VERIFIED"
    elif disp_status == "Dispensed":
        db_status = "COMPLETED"
    elif disp_status == "Failed":
        db_status = "FAILED_DISPENSE"
    elif disp_status == "Cancelled":
        db_status = "CANCELLED"
        
    if not db_status:
        raise HTTPException(status_code=400, detail="Invalid status value.")
        
    result = await col.find_one_and_update(
        {"_id": ObjectId(order_id)},
        {"$set": {"status": db_status, "updated_at": datetime.utcnow()}},
        return_document=True
    )
    if not result:
        raise HTTPException(status_code=404, detail="Order not found.")
        
    return await _format_tx(result)
