"""
database.py – Motor (async MongoDB) client and collection helpers
"""
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config import settings
from app.utils.logger import logger

# ── Module-level client ────────────────────────────────────────────────────────
_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


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
    await db["support_tickets"].create_index("user_id")
    await db["support_tickets"].create_index("created_at")

    logger.info("MongoDB indexes verified / created.")