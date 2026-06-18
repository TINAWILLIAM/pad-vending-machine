from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config import settings
from app.utils.logger import logger

# ── Module-level client ────────────────────────────────────────────────────────
_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None

PRODUCTS_TO_SEED = [
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


async def _seed_if_empty() -> None:
    db = get_db()
    machine_count = await db["machines"].count_documents({})
    if machine_count > 0:
        logger.info(f"Machines collection is not empty ({machine_count} records found). Skipping auto-seeding.")
        return

    logger.info("Machines collection is empty. Starting auto-seeding for Kristu Jayanti campus...")
    
    p_col = db["products"]
    product_count = await p_col.count_documents({})
    product_ids = []
    
    if product_count == 0:
        logger.info("Products collection is empty. Seeding default products...")
        for p in PRODUCTS_TO_SEED:
            res = await p_col.insert_one(p.copy())
            product_ids.append(str(res.inserted_id))
    else:
        async for doc in p_col.find({}):
            product_ids.append(str(doc["_id"]))
            
    if not product_ids:
        product_ids = ["regular_id", "xl_id", "xxl_id"]
        
    m_col = db["machines"]
    
    seeded_machines = [
        {
            "machine_code": "UTIL-001",
            "name": "Utility Block Machine",
            "machine_name": "Utility Block Machine",
            "block_name": "Utility Block",
            "latitude": 13.0581,
            "longitude": 77.6426,
            "location": {
                "latitude": 13.0581,
                "longitude": 77.6426,
                "address": "Utility Block, Ground Floor",
            },
            "is_active": True,
            "is_online": True,
            "status": "online",
            "stock": {pid: 25 for pid in product_ids},
            "esp32_ip": "192.168.1.101",
            "esp32_endpoint": None,
            "last_seen": datetime.utcnow(),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        },
        {
            "machine_code": "MAIN-001",
            "name": "Main Block Machine",
            "machine_name": "Main Block Machine",
            "block_name": "Main Block",
            "latitude": 13.0585,
            "longitude": 77.6424,
            "location": {
                "latitude": 13.0585,
                "longitude": 77.6424,
                "address": "Main Block, Reception Area",
            },
            "is_active": True,
            "is_online": True,
            "status": "online",
            "stock": {pid: 25 for pid in product_ids},
            "esp32_ip": "192.168.1.102",
            "esp32_endpoint": None,
            "last_seen": datetime.utcnow(),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        },
        {
            "machine_code": "PG-001",
            "name": "PG Block Machine",
            "machine_name": "PG Block Machine",
            "block_name": "PG Block",
            "latitude": 13.0590,
            "longitude": 77.6428,
            "location": {
                "latitude": 13.0590,
                "longitude": 77.6428,
                "address": "PG Block, Ground Floor Lounge",
            },
            "is_active": True,
            "is_online": True,
            "status": "online",
            "stock": {pid: 25 for pid in product_ids},
            "esp32_ip": "192.168.1.103",
            "esp32_endpoint": None,
            "last_seen": datetime.utcnow(),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        },
        {
            "machine_code": "ADMIN-001",
            "name": "Admin Block Machine",
            "machine_name": "Admin Block Machine",
            "block_name": "Admin Block",
            "latitude": 13.0583,
            "longitude": 77.6427,
            "location": {
                "latitude": 13.0583,
                "longitude": 77.6427,
                "address": "Admin Block, Ground Floor Lobby",
            },
            "is_active": True,
            "is_online": True,
            "status": "online",
            "stock": {pid: 25 for pid in product_ids},
            "esp32_ip": "192.168.1.104",
            "esp32_endpoint": None,
            "last_seen": datetime.utcnow(),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        },
        {
            "machine_code": "HUM-001",
            "name": "Humanities Block Machine",
            "machine_name": "Humanities Block Machine",
            "block_name": "Humanities Block",
            "latitude": 13.0594,
            "longitude": 77.6431,
            "location": {
                "latitude": 13.0594,
                "longitude": 77.6431,
                "address": "Humanities Block, Corridor",
            },
            "is_active": True,
            "is_online": True,
            "status": "online",
            "stock": {pid: 25 for pid in product_ids},
            "esp32_ip": "192.168.1.105",
            "esp32_endpoint": None,
            "last_seen": datetime.utcnow(),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        },
    ]
    
    for m in seeded_machines:
        await m_col.insert_one(m)
        logger.info(f"Seeded machine: {m['machine_name']}")
    
    logger.info("Auto-seeding complete.")


async def _initialize_stock_to_25() -> None:
    """Ensure all machines in MongoDB have a stock of 25 for each active product."""
    db = get_db()
    p_col = db["products"]
    m_col = db["machines"]
    
    product_ids = []
    async for p in p_col.find({"is_active": True}):
        product_ids.append(str(p["_id"]))
        
    if not product_ids:
        logger.info("No active products found during stock init. Seeding default products...")
        for p in PRODUCTS_TO_SEED:
            res = await p_col.insert_one(p.copy())
            product_ids.append(str(res.inserted_id))
            
    stock_dict = {pid: 25 for pid in product_ids}
    result = await m_col.update_many(
        {},
        {"$set": {"stock": stock_dict, "updated_at": datetime.utcnow()}}
    )
    logger.info(f"Initialized stock of 25 for {len(product_ids)} products on {result.modified_count} machines in MongoDB.")


async def _normalize_seeded_products() -> None:
    """Normalize seeded product names to 'Whisper' to avoid duplication with category names."""
    db = get_db()
    p_col = db["products"]
    cursor = p_col.find({})
    async for doc in cursor:
        name = doc.get("name", "")
        if name in ("Regular Pad", "XL Pad", "XXL Pad") or name.lower().endswith("pad"):
            await p_col.update_one({"_id": doc["_id"]}, {"$set": {"name": "Whisper"}})
            logger.info(f"Normalized product name to Whisper for category {doc.get('pad_type')}")


async def connect_db() -> None:
    """Called once on application startup."""
    global _client, _db
    logger.info("Connecting to MongoDB …")
    _client = AsyncIOMotorClient(settings.MONGO_URI)
    _db = _client[settings.DB_NAME]

    # Verify the connection
    await _client.admin.command("ping")
    logger.info(f"Connected to MongoDB database: {settings.DB_NAME}")

    await _create_indexes()
    await _normalize_seeded_products()
    await _seed_if_empty()
    await _initialize_stock_to_25()


async def close_db() -> None:
    """Called once on application shutdown."""
    global _client
    if _client:
        _client.close()
        logger.info("MongoDB connection closed.")


def get_db() -> AsyncIOMotorDatabase:
    """Return the live database instance."""
    if _db is None:
        raise RuntimeError("Database not initialised. Call connect_db() first.")
    return _db


# ── Collection helpers ─────────────────────────────────────────────────────────
def get_collection(name: str):
    return get_db()[name]


# ── Index creation ─────────────────────────────────────────────────────────────
async def _create_indexes() -> None:
    db = get_db()

    # Users
    await db["users"].create_index("email", unique=True)

    # OTPs
    await db["otps"].create_index("email")
    await db["otps"].create_index("expires_at", expireAfterSeconds=0)

    # Orders
    await db["orders"].create_index("user_id")
    await db["orders"].create_index("razorpay_order_id")
    await db["orders"].create_index("payment_method")
    await db["orders"].create_index("status")
    await db["orders"].create_index("created_at")

    # Machines
    await db["machines"].create_index("machine_code", unique=True)

    # Payments
    await db["payments"].create_index("razorpay_order_id", unique=True)
    await db["payments"].create_index("razorpay_payment_id", unique=True, sparse=True)

    # Coin transactions
    await db["coin_transactions"].create_index("machine_id")
    await db["coin_transactions"].create_index("created_at")
    await db["coin_transactions"].create_index("status")

    # Support Tickets
    await db["issue_reports"].create_index("user_id")
    await db["issue_reports"].create_index("created_at")

    logger.info("MongoDB indexes verified / created.")