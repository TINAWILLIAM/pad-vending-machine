"""
admin/dashboard.py – GET /admin/dashboard

Aggregates data from orders, users, payments collections into a single
response consumed by the Admin Dashboard page.

Tracks BOTH UPI (Razorpay) and COIN payment methods.
"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends

from app.database import get_collection
from app.admin.dependencies import require_admin_token

router = APIRouter(prefix="/admin", tags=["Admin – Dashboard"])


def _pct_change(current: float, previous: float) -> str:
    """Return a signed percentage string e.g. '+12.5%' or '-8.3%'."""
    if previous == 0:
        return "+100.0%" if current > 0 else "0.0%"
    change = ((current - previous) / previous) * 100
    sign = "+" if change >= 0 else ""
    return f"{sign}{change:.1f}%"


async def _revenue_for_period(start: datetime, end: datetime) -> float:
    col = get_collection("orders")
    pipeline = [
        {
            "$match": {
                "status": "COMPLETED",
                "completed_at": {"$gte": start, "$lt": end},
            }
        },
        {"$group": {"_id": None, "total": {"$sum": "$total_amount"}}},
    ]
    result = await col.aggregate(pipeline).to_list(1)
    return result[0]["total"] if result else 0.0


async def _tx_count_for_period(start: datetime, end: datetime) -> dict:
    col = get_collection("orders")
    pipeline = [
        {"$match": {"created_at": {"$gte": start, "$lt": end}}},
        {
            "$group": {
                "_id": "$status",
                "count": {"$sum": 1},
            }
        },
    ]
    rows = await col.aggregate(pipeline).to_list(20)
    successful = sum(r["count"] for r in rows if r["_id"] == "COMPLETED")
    failed = sum(r["count"] for r in rows if r["_id"] in ("FAILED_DISPENSE", "CANCELLED"))
    return {"successful": successful, "failed": failed, "total": successful + failed}


async def _user_count_for_period(start: datetime, end: datetime) -> int:
    col = get_collection("users")
    return await col.count_documents({"created_at": {"$gte": start, "$lt": end}})


@router.get("/dashboard", summary="Admin dashboard – revenue, transactions, users, top products")
async def get_dashboard(_: dict = Depends(require_admin_token)):
    now = datetime.utcnow()
    this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_end = this_month_start
    last_month_start = (this_month_start - timedelta(days=1)).replace(day=1)

    # ── Revenue ──────────────────────────────────────────────────────────────
    upi_revenue_this = await _revenue_for_period(this_month_start, now)
    upi_revenue_last = await _revenue_for_period(last_month_start, last_month_end)

    # Coin revenue from coin_transactions collection (separate payment method)
    coin_col = get_collection("coin_transactions")
    coin_pipeline = [
        {"$match": {"status": "completed", "created_at": {"$gte": this_month_start}}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
    ]
    coin_result = await coin_col.aggregate(coin_pipeline).to_list(1)
    coin_revenue_this = coin_result[0]["total"] if coin_result else 0.0

    coin_pipeline_last = [
        {"$match": {"status": "completed",
                    "created_at": {"$gte": last_month_start, "$lt": last_month_end}}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
    ]
    coin_result_last = await coin_col.aggregate(coin_pipeline_last).to_list(1)
    coin_revenue_last = coin_result_last[0]["total"] if coin_result_last else 0.0

    total_revenue_this = upi_revenue_this + coin_revenue_this
    total_revenue_last = upi_revenue_last + coin_revenue_last

    # ── Transactions ─────────────────────────────────────────────────────────
    tx_this = await _tx_count_for_period(this_month_start, now)
    tx_last = await _tx_count_for_period(last_month_start, last_month_end)

    # ── Users ────────────────────────────────────────────────────────────────
    upi_users_total = await get_collection("users").count_documents({})
    upi_users_last_m = await _user_count_for_period(last_month_start, last_month_end)
    upi_users_this_m = await _user_count_for_period(this_month_start, now)

    coin_users_total = await get_collection("coin_transactions").distinct("session_id")
    coin_users_count = len(coin_users_total)

    # ── Recent transactions (latest 5) ───────────────────────────────────────
    orders_col = get_collection("orders")
    recent_cursor = orders_col.find({}).sort("created_at", -1).limit(5)
    recent_transactions = []
    async for doc in recent_cursor:
        items_summary = ", ".join(
            f"{i['product_name']} x{i['quantity']}" for i in doc.get("items", [])
        )
        recent_transactions.append({
            "order_id": str(doc["_id"]),
            "customer": doc.get("user_id", "Anonymous"),
            "product": items_summary,
            "date": doc["created_at"].isoformat(),
            "amount": doc["total_amount"],
            "status": doc["status"],
            "payment_method": doc.get("payment_method", "UPI"),
        })

    # ── Top selling products ─────────────────────────────────────────────────
    top_products_pipeline = [
        {"$match": {"status": "COMPLETED"}},
        {"$unwind": "$items"},
        {
            "$group": {
                "_id": "$items.product_id",
                "product_name": {"$first": "$items.product_name"},
                "pad_type": {"$first": "$items.pad_type"},
                "total_sold": {"$sum": "$items.quantity"},
                "total_revenue": {"$sum": {"$multiply": ["$items.price", "$items.quantity"]}},
            }
        },
        {"$sort": {"total_sold": -1}},
        {"$limit": 5},
    ]
    top_docs = await orders_col.aggregate(top_products_pipeline).to_list(5)
    top_products = [
        {
            "product_id": d["_id"],
            "product_name": d["product_name"],
            "pad_type": d["pad_type"],
            "total_sold": d["total_sold"],
            "total_revenue": round(d["total_revenue"], 2),
        }
        for d in top_docs
    ]

    return {
        "revenue": {
            "total": round(total_revenue_this, 2),
            "upi": round(upi_revenue_this, 2),
            "coin": round(coin_revenue_this, 2),
            "vs_last_month": _pct_change(total_revenue_this, total_revenue_last),
        },
        "transactions": {
            "total": tx_this["total"],
            "successful": tx_this["successful"],
            "failed": tx_this["failed"],
            "vs_last_month": _pct_change(tx_this["total"], tx_last["total"]),
        },
        "users": {
            "upi_users": upi_users_total,
            "coin_users": coin_users_count,
            "total": upi_users_total + coin_users_count,
            "new_this_month": upi_users_this_m,
            "vs_last_month": _pct_change(upi_users_this_m, upi_users_last_m),
        },
        "recent_transactions": recent_transactions,
        "top_selling_products": top_products,
    }
