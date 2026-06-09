#!/usr/bin/env python
"""
seed_data.py – Populate MongoDB with default products and a demo machine.
Run once after setting up the project:

    python scripts/seed_data.py
"""
import asyncio
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import datetime
from app.database import connect_db, get_collection


PRODUCTS = [
    {
        "name": "Regular Pad",
        "pad_type": "regular",
        "description": "Standard sanitary pad – suitable for light to moderate flow.",
        "price": 10.0,
        "is_active": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    },
    {
        "name": "Medium Pad",
        "pad_type": "medium",
        "description": "Medium-length sanitary pad – suitable for moderate flow.",
        "price": 15.0,
        "is_active": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    },
    {
        "name": "XL Pad",
        "pad_type": "xl",
        "description": "Extra-long sanitary pad – suitable for heavy flow and overnight use.",
        "price": 20.0,
        "is_active": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    },
]

DEMO_MACHINE = {
    "machine_code": "DEMO-001",
    "name": "Demo Machine – Main Building",
    "location": {
        "latitude": 12.9716,
        "longitude": 77.5946,
        "address": "Main Building, Ground Floor",
        "landmark": "Near Reception",
    },
    "status": "offline",
    "esp32_ip": "192.168.1.100",
    "esp32_endpoint": None,
    "stock": {},  # Will be updated after products are inserted
    "last_seen": None,
    "created_at": datetime.utcnow(),
    "updated_at": datetime.utcnow(),
}


async def seed():
    await connect_db()
    p_col = get_collection("products")
    m_col = get_collection("machines")

    # ── Products ───────────────────────────────────────────────
    inserted_ids = []
    for product in PRODUCTS:
        existing = await p_col.find_one({"name": product["name"]})
        if existing:
            print(f"  ↩  Product already exists: {product['name']}")
            inserted_ids.append(str(existing["_id"]))
        else:
            result = await p_col.insert_one(product)
            inserted_ids.append(str(result.inserted_id))
            print(f"  ✅ Product seeded: {product['name']} (id={result.inserted_id})")

    # ── Machine ────────────────────────────────────────────────
    stock = {pid: 50 for pid in inserted_ids}
    DEMO_MACHINE["stock"] = stock

    existing_m = await m_col.find_one({"machine_code": "DEMO-001"})
    if existing_m:
        print("  ↩  Demo machine already exists.")
    else:
        result = await m_col.insert_one(DEMO_MACHINE)
        print(f"  ✅ Demo machine seeded (id={result.inserted_id})")

    print("\n🎉 Seed complete!")
    print("   Product IDs:", inserted_ids)


if __name__ == "__main__":
    asyncio.run(seed())
