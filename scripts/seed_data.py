#!/usr/bin/env python
"""
seed_data.py – Populate MongoDB with default products and the 5 requested blocks machines.
"""
import asyncio
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import datetime
from app.database import connect_db, get_collection

PRODUCTS = [
    {
        "name": "Whisper",
        "pad_type": "regular",
        "description": "Standard sanitary pad – suitable for light flow.",
        "price": 10.0,
        "is_active": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    },
    {
        "name": "Whisper",
        "pad_type": "xl",
        "description": "Extra-long sanitary pad – suitable for heavy flow.",
        "price": 15.0,
        "is_active": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    },
    {
        "name": "Whisper",
        "pad_type": "xxl",
        "description": "Maximum protection, long lasting.",
        "price": 20.0,
        "is_active": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    },
]

MACHINES = [
    {
        "machine_code": "UTIL-001",
        "name": "Utility Block Machine",
        "location": {
            "latitude": 12.9716,
            "longitude": 77.5946,
            "address": "Utility Block, Ground Floor",
        },
        "status": "online",
        "esp32_ip": "192.168.1.101",
        "esp32_endpoint": None,
        "last_seen": datetime.utcnow(),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    },
    {
        "machine_code": "MAIN-001",
        "name": "Main Block Machine",
        "location": {
            "latitude": 12.9720,
            "longitude": 77.5950,
            "address": "Main Block, Reception Area",
        },
        "status": "online",
        "esp32_ip": "192.168.1.102",
        "esp32_endpoint": None,
        "last_seen": datetime.utcnow(),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    },
    {
        "machine_code": "ADMIN-001",
        "name": "Admin Block Machine",
        "location": {
            "latitude": 12.9710,
            "longitude": 77.5940,
            "address": "Admin Block, First Floor Lobby",
        },
        "status": "online",
        "esp32_ip": "192.168.1.103",
        "esp32_endpoint": None,
        "last_seen": datetime.utcnow(),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    },
    {
        "machine_code": "PG-001",
        "name": "P.G Block Machine",
        "location": {
            "latitude": 12.9730,
            "longitude": 77.5960,
            "address": "P.G Block, Student Lounge",
        },
        "status": "online",
        "esp32_ip": "192.168.1.104",
        "esp32_endpoint": None,
        "last_seen": datetime.utcnow(),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    },
    {
        "machine_code": "HUM-FAIL",
        "name": "Humanities Block Machine",
        "location": {
            "latitude": 12.9740,
            "longitude": 77.5970,
            "address": "Humanities Block, Corridor",
        },
        "status": "online",
        "esp32_ip": "192.168.1.105",
        "esp32_endpoint": None,
        "last_seen": datetime.utcnow(),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    },
]

async def seed():
    await connect_db()
    p_col = get_collection("products")
    m_col = get_collection("machines")

    # Clear existing data to prevent duplicate keys
    print("Clearing existing products and machines...")
    await p_col.delete_many({})
    await m_col.delete_many({})

    # ── Products ───────────────────────────────────────────────
    inserted_ids = []
    for product in PRODUCTS:
        result = await p_col.insert_one(product)
        inserted_ids.append(str(result.inserted_id))
        print(f"  [SUCCESS] Product seeded: {product['name']} (id={result.inserted_id})")

    # ── Machines ───────────────────────────────────────────────
    stock = {pid: 50 for pid in inserted_ids}
    for machine in MACHINES:
        machine["stock"] = stock
        result = await m_col.insert_one(machine)
        print(f"  [SUCCESS] Vending Machine seeded: {machine['name']} (code={machine['machine_code']}, id={result.inserted_id})")

    print("\nSeed complete!")
    print("   Product IDs:", inserted_ids)

if __name__ == "__main__":
    asyncio.run(seed())
