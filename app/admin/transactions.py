"""
admin/transactions.py – GET /admin/transactions, GET /admin/transactions/search

Shows both UPI and COIN orders.
Coin revenue card = COIN-method totals only.
"""
from datetime import datetime, timedelta
from typing import Optional
from bson import ObjectId
from fastapi import APIRouter, Depends, Query

from app.database import get_collection
from app.admin.dependencies import require_admin_token

router = APIRouter(prefix="/admin", tags=["Admin – Transactions"])


def _format_tx(doc: dict) -> dict:
    return {
        "order_id": str(doc["_id"]),
        "customer_id": doc.get("user_id", "anonymous"),
        "date_placed": doc["created_at"].isoformat(),
        "items": doc.get("items", []),
        "payment_method": doc.get("payment_method", "UPI"),
        "total_price": doc["total_amount"],
        "status": doc["status"],
        "machine_name": doc.get("machine_name", ""),
    }


@router.get("/transactions", summary="List all transactions with coin revenue card")
async def list_transactions(
    payment_method: Optional[str] = Query(None, description="UPI or COIN"),
    status: Optional[str] = Query(None, description="Filter by order status"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _: dict = Depends(require_admin_token),
):
    col = get_collection("orders")
    now = datetime.utcnow()
    this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_end = this_month_start
    last_month_start = (this_month_start - timedelta(days=1)).replace(day=1)

    # ── Coin revenue card ─────────────────────────────────────────────────────
    coin_pipeline = [
        {
            "$match": {
                "payment_method": "COIN",
                "status": "COMPLETED",
                "completed_at": {"$gte": this_month_start},
            }
        },
        {"$group": {"_id": None, "total": {"$sum": "$total_amount"}, "count": {"$sum": 1}}},
    ]
    coin_result = await col.aggregate(coin_pipeline).to_list(1)
    coin_revenue = coin_result[0]["total"] if coin_result else 0.0
    coin_tx_count = coin_result[0]["count"] if coin_result else 0

    coin_last_pipeline = [
        {
            "$match": {
                "payment_method": "COIN",
                "status": "COMPLETED",
                "completed_at": {"$gte": last_month_start, "$lt": last_month_end},
            }
        },
        {"$group": {"_id": None, "total": {"$sum": "$total_amount"}}},
    ]
    coin_last = await col.aggregate(coin_last_pipeline).to_list(1)
    coin_revenue_last = coin_last[0]["total"] if coin_last else 0.0

    def _pct(cur, prev):
        if prev == 0:
            return "+100.0%" if cur > 0 else "0.0%"
        c = ((cur - prev) / prev) * 100
        return f"{'+'if c>=0 else ''}{c:.1f}%"

    # ── Query filter ──────────────────────────────────────────────────────────
    query: dict = {}
    if payment_method:
        query["payment_method"] = payment_method.upper()
    if status:
        query["status"] = status.upper()

    total_count = await col.count_documents(query)
    skip = (page - 1) * limit
    cursor = col.find(query).sort("created_at", -1).skip(skip).limit(limit)

    transactions = []
    async for doc in cursor:
        transactions.append(_format_tx(doc))

    fallback = None
    if total_count == 0:
        fallback = "No orders found matching the filter selection."

    return {
        "coin_revenue_card": {
            "coin_revenue_this_month": round(coin_revenue, 2),
            "coin_transactions_this_month": coin_tx_count,
            "vs_last_month": _pct(coin_revenue, coin_revenue_last),
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


@router.get("/transactions/search", summary="Search transactions by order ID or customer ID")
async def search_transactions(
    q: str = Query(..., min_length=1, description="Order ID or Customer ID"),
    _: dict = Depends(require_admin_token),
):
    col = get_collection("orders")
    results = []

    # Try exact order_id match (ObjectId)
    try:
        doc = await col.find_one({"_id": ObjectId(q)})
        if doc:
            results.append(_format_tx(doc))
    except Exception:
        pass

    # Customer ID match
    if not results:
        cursor = col.find({"user_id": q}).sort("created_at", -1).limit(20)
        async for doc in cursor:
            results.append(_format_tx(doc))

    fallback = "No orders found matching the filter selection." if not results else None
    return {"transactions": results, "count": len(results), "fallback_message": fallback}
