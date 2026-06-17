"""
main.py – FastAPI application entry point.
Registers all routers, configures CORS, and manages DB lifecycle.
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import connect_db, close_db
from app.utils.logger import logger

# ── Route imports ──────────────────────────────────────────────────────────────
from app.routes.auth_routes     import router as auth_router
from app.routes.product_routes  import router as product_router
from app.routes.cart_routes     import router as cart_router
from app.routes.order_routes    import router as order_router
from app.routes.payment_routes  import router as payment_router
from app.routes.webhook_routes  import router as webhook_router
from app.routes.machine_routes  import router as machine_router
from app.routes.iot_routes      import router as iot_router
from app.routes.location_routes import router as location_router
from app.routes.support_routes  import router as support_router
from app.admin.auth import router as admin_auth_router
from app.admin.dashboard import router as admin_dashboard_router
from app.admin.customers import router as admin_customers_router
from app.admin.transactions import router as admin_transactions_router
from app.admin.products import router as admin_products_router
from app.admin.coin_routes import router as admin_coin_router


# ── Create logs directory ──────────────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)
os.makedirs("qr_codes", exist_ok=True)


# ── Lifespan (startup / shutdown) ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION} …")
    await connect_db()
    yield
    logger.info("Shutting down …")
    await close_db()


# ── App factory ────────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Backend API for the IoT-enabled Sanitary Pad Vending Machine System. "
        "Handles authentication, payments, ESP32 communication, and order management."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(location_router)
app.include_router(product_router)
app.include_router(cart_router)
app.include_router(order_router)
app.include_router(payment_router)
app.include_router(webhook_router)
app.include_router(machine_router)
app.include_router(iot_router)
app.include_router(support_router)
app.include_router(admin_auth_router)
app.include_router(admin_dashboard_router)
app.include_router(admin_customers_router)
app.include_router(admin_transactions_router)
app.include_router(admin_products_router)
app.include_router(admin_coin_router)


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


@app.get("/", tags=["Health"])
async def root():
    return JSONResponse(
        content={
            "message": f"Welcome to {settings.APP_NAME}",
            "docs": "/docs",
            "health": "/health",
        }
    )

# Force reload triggers after .env modification - CORS updated

