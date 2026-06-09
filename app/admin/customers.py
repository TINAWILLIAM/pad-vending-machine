"""
admin/customers.py – GET /admin/customers, GET /admin/customers/{id}

Tracks UPI (online) users only. Excludes anonymous coin users.
Supports search by name, email, or customer ID.
"""
from datetime import datetime, timedelta
from typing import Optional
from bson import ObjectId
from fastapi import APIRouter, Depends, Query, HTTPException

from app.database import get_collection
from app.admin.dependencies import require_admin_token
from app.admin.dashboard import _pct_change

router = APIRouter(prefix="/admin", tags=["Admin – Customers"])


async def _enrich_customer(user_doc: dict) -> dict:
    """Attach order stats to a user document."""
    user_id = str(user_doc["_id"])
    orders_col = get_collection("orders")

    pipeline = [
        {"$match": {"user_id": user_id, "status": "COMPLETED"}},
        {
            "$group": {
                "_id": None,
                "total_orders": {"$sum": 1},
                "total_spend": {"$sum": "$total_amount"},
                "last_purchase": {"$max": "$completed_at"},
            }
        },
    ]
    stats = await orders_col.aggregate(pipeline).to_list(1)
    s = stats[0] if stats else {}

    return {
        "customer_id": user_id,
        "name": user_doc.get("name", ""),
        "email": user_doc.get("email", ""),
        "is_active": user_doc.get("is_active", True),
        "created_at": user_doc.get("created_at", "").isoformat()
        if isinstance(user_doc.get("created_at"), datetime)
        else user_doc.get("created_at", ""),
        "last_login": user_doc.get("last_login", "").isoformat()
        if isinstance(user_doc.get("last_login"), datetime)
        else user_doc.get("last_login", ""),
        "total_orders": s.get("total_orders", 0),
        "total_spend": round(s.get("total_spend", 0.0), 2),
        "last_purchase": s.get("last_purchase", "").isoformat()
        if isinstance(s.get("last_purchase"), datetime)
        else s.get("last_purchase", None),
    }


@router.get("/customers", summary="List all UPI customers with stats + search")
async def list_customers(
    search: Optional[str] = Query(None, description="Search by name, email, or customer ID"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _: dict = Depends(require_admin_token),
):
    """
    Returns UPI customers only (from users collection).
    Optional ?search= supports: name, email, customer_id.
    """
    users_col = get_collection("users")
    now = datetime.utcnow()
    this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_end = this_month_start
    last_month_start = (this_month_start - timedelta(days=1)).replace(day=1)

    # Build query filter
    query: dict = {}
    if search:
        # Try ObjectId match for customer_id search
        try:
            oid = ObjectId(search)
            query = {"_id": oid}
        except Exception:
            query = {
                "$or": [
                    {"email": {"$regex": search, "$options": "i"}},
                    {"name": {"$regex": search, "$options": "i"}},
                ]
            }

    total_count = await users_col.count_documents(query)
    skip = (page - 1) * limit
    cursor = users_col.find(query).sort("created_at", -1).skip(skip).limit(limit)

    customers = []
    async for doc in cursor:
        customers.append(await _enrich_customer(doc))

    # Top card stats
    total_users_this_m = await users_col.count_documents(
        {"created_at": {"$gte": this_month_start}}
    )
    total_users_last_m = await users_col.count_documents(
        {"created_at": {"$gte": last_month_start, "$lt": last_month_end}}
    )

    # UPI-only revenue
    orders_col = get_collection("orders")
    rev_pipeline = [
        {
            "$match": {
                "status": "COMPLETED",
                "payment_method": {"$ne": "COIN"},
                "completed_at": {"$gte": this_month_start},
            }
        },
        {"$group": {"_id": None, "total": {"$sum": "$total_amount"}}},
    ]
    rev_result = await orders_col.aggregate(rev_pipeline).to_list(1)
    rev_this = rev_result[0]["total"] if rev_result else 0.0

    rev_pipeline_last = [
        {
            "$match": {
                "status": "COMPLETED",
                "payment_method": {"$ne": "COIN"},
                "completed_at": {"$gte": last_month_start, "$lt": last_month_end},
            }
        },
        {"$group": {"_id": None, "total": {"$sum": "$total_amount"}}},
    ]
    rev_last_result = await orders_col.aggregate(rev_pipeline_last).to_list(1)
    rev_last = rev_last_result[0]["total"] if rev_last_result else 0.0

    fallback = None
    if total_count == 0:
        fallback = "No customer profiles found matching search criteria."

    return {
        "summary": {
            "total_users": total_count,
            "new_this_month": total_users_this_m,
            "users_vs_last_month": _pct_change(total_users_this_m, total_users_last_m),
            "upi_revenue_this_month": round(rev_this, 2),
            "revenue_vs_last_month": _pct_change(rev_this, rev_last),
        },
        "pagination": {
            "total": total_count,
            "page": page,
            "limit": limit,
            "pages": -(-total_count // limit),
        },
        "customers": customers,
        "fallback_message": fallback,
    }


@router.get("/customers/{customer_id}", summary="Get single customer profile + order history")
async def get_customer(
    customer_id: str,
    _: dict = Depends(require_admin_token),
):
    users_col = get_collection("users")
    try:
        doc = await users_col.find_one({"_id": ObjectId(customer_id)})
    except Exception:
        doc = await users_col.find_one({"email": customer_id})

    if not doc:
        raise HTTPException(status_code=404, detail="Customer not found.")

    profile = await _enrich_customer(doc)

    # Full order history
    orders_col = get_collection("orders")
    cursor = orders_col.find({"user_id": customer_id}).sort("created_at", -1).limit(20)
    orders = []
    async for o in cursor:
        orders.append({
            "order_id": str(o["_id"]),
            "items": o.get("items", []),
            "total_amount": o["total_amount"],
            "status": o["status"],
            "payment_method": o.get("payment_method", "UPI"),
            "created_at": o["created_at"].isoformat(),
            "completed_at": o["completed_at"].isoformat() if o.get("completed_at") else None,
        })

    return {**profile, "order_history": orders}
