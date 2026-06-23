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


def _pct_change(current: float, previous: float) -> str | None:
    """Return a signed percentage string e.g. '+12.5%' or '-8.3%' or None if not applicable."""
    if previous == 0:
        return None
    change = ((current - previous) / previous) * 100
    sign = "+" if change >= 0 else ""
    return f"{sign}{change:.1f}%"



async def _revenue_for_period(start: datetime = None, end: datetime = None) -> float:
    col = get_collection("orders")
    match_q = {
        "status": {"$in": ["COMPLETED", "completed", "Dispensed", "dispensed"]},
        "payment_method": {"$ne": "COIN"}
    }
    if start or end:
        match_q["completed_at"] = {}
        if start:
            match_q["completed_at"]["$gte"] = start
        if end:
            match_q["completed_at"]["$lt"] = end

    pipeline = [
        {"$match": match_q},
        {"$group": {"_id": None, "total": {"$sum": "$total_amount"}}},
    ]
    result = await col.aggregate(pipeline).to_list(1)
    return result[0]["total"] if result else 0.0


async def _tx_count_for_period(start: datetime = None, end: datetime = None) -> int:
    col = get_collection("orders")
    match_q = {
        "status": {"$in": ["COMPLETED", "completed", "Dispensed", "dispensed"]},
        "payment_method": {"$ne": "COIN"}
    }
    if start or end:
        match_q["completed_at"] = {}
        if start:
            match_q["completed_at"]["$gte"] = start
        if end:
            match_q["completed_at"]["$lt"] = end

    return await col.count_documents(match_q)


async def _user_count_for_period(start: datetime = None, end: datetime = None) -> int:
    col = get_collection("users")
    match_q = {}
    if start or end:
        match_q["created_at"] = {}
        if start:
            match_q["created_at"]["$gte"] = start
        if end:
            match_q["created_at"]["$lt"] = end

    return await col.count_documents(match_q)


@router.get("/dashboard", summary="Admin dashboard – revenue, transactions, users, top products")
async def get_dashboard(_: dict = Depends(require_admin_token)):
    now = datetime.utcnow()
    this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_end = this_month_start
    last_month_start = (this_month_start - timedelta(days=1)).replace(day=1)

    # ── Revenue ──────────────────────────────────────────────────────────────
    all_time_revenue = await _revenue_for_period()
    revenue_this_m = await _revenue_for_period(this_month_start, now)
    revenue_last_m = await _revenue_for_period(last_month_start, last_month_end)

    # ── Transactions ─────────────────────────────────────────────────────────
    all_time_transactions = await _tx_count_for_period()
    tx_this_m = await _tx_count_for_period(this_month_start, now)
    tx_last_m = await _tx_count_for_period(last_month_start, last_month_end)

    # ── Users ────────────────────────────────────────────────────────────────
    all_time_users = await _user_count_for_period()
    users_this_m = await _user_count_for_period(this_month_start, now)
    users_last_m = await _user_count_for_period(last_month_start, last_month_end)

    # ── Recent transactions (latest 5 online orders) ───────────────────────────
    orders_col = get_collection("orders")
    recent_cursor = orders_col.find({"payment_method": {"$ne": "COIN"}}).sort("created_at", -1).limit(5)
    recent_transactions = []
    users_col = get_collection("users")
    async for doc in recent_cursor:
        user_id = doc.get("user_id", "")
        customer_email = "Anonymous"
        if user_id and not user_id.startswith("coin:"):
            try:
                user = await users_col.find_one({"_id": ObjectId(user_id)})
                if user:
                    customer_email = user.get("email", "Anonymous")
            except Exception:
                customer_email = user_id

        items_summary = ", ".join(
            f"{i['product_name']} x{i['quantity']}" for i in doc.get("items", [])
        )
        recent_transactions.append({
            "order_id": str(doc["_id"]),
            "customer": customer_email,
            "product": items_summary,
            "date": doc["created_at"].isoformat(),
            "amount": doc["total_amount"],
            "status": doc["status"],
            "payment_method": doc.get("payment_method", "UPI"),
        })

    top_products_pipeline = [
        {"$match": {"status": {"$in": ["COMPLETED", "completed", "Dispensed", "dispensed"]}, "payment_method": {"$ne": "COIN"}}},
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
    
    machines_col = get_collection("machines")
    top_products = []
    for d in top_docs:
        product_id = d["_id"]
        total_stock = 0
        async for m in machines_col.find({}):
            total_stock += m.get("stock", {}).get(product_id, 0)

        top_products.append({
            "product_id": product_id,
            "product_name": d["product_name"],
            "pad_type": d["pad_type"],
            "total_sold": d["total_sold"],
            "total_revenue": round(d["total_revenue"], 2),
            "stock": total_stock,
        })

    return {
        "revenue": {
            "total": round(all_time_revenue, 2),
            "vs_last_month": _pct_change(revenue_this_m, revenue_last_m),
        },
        "transactions": {
            "total": all_time_transactions,
            "vs_last_month": _pct_change(tx_this_m, tx_last_m),
        },
        "users": {
            "total": all_time_users,
            "new_this_month": users_this_m,
            "vs_last_month": _pct_change(users_this_m, users_last_m),
        },
        "recent_transactions": recent_transactions,
        "top_selling_products": top_products,
    }
