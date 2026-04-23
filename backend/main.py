import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from dotenv import load_dotenv, find_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

load_dotenv(find_dotenv(), override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")

from db.connection import create_pool, get_pool
from scheduler.price_updater import start_scheduler, stop_scheduler, fetch_and_update_prices
from routers.auth import router as auth_router
from routers.agents import router as agents_router
from routers.customers import router as customers_router
from routers.portfolio import router as portfolio_router
from routers.alerts import router as alerts_router
from routers.reports import router as reports_router
from routers.websocket import router as websocket_router
from routers.transactions import router as transactions_router
from routers.banking import router as banking_router

# WebSocket client lists — populated by Phase 3 routers
connected_ws_clients: list = []
connected_alert_clients: list = []


async def _warm_market_cache() -> None:
    """Pre-build universe flags cache ~15s after startup."""
    await asyncio.sleep(15)
    try:
        from agents.market import _build_universe_cache
        await asyncio.to_thread(_build_universe_cache)
        logger.info("Market universe cache warm-up complete")
    except Exception as e:
        logger.warning(f"Market cache warm-up failed: {e}")


async def listen_to_postgres(pool) -> None:
    """Dedicated connection that listens for dashboard_update NOTIFY signals."""
    try:
        async with pool.acquire() as conn:
            async def _broadcast(connection, pid, channel, payload):
                dead = []
                for ws in connected_ws_clients:
                    try:
                        await ws.send_text(payload)
                    except Exception:
                        dead.append(ws)
                for ws in dead:
                    try:
                        connected_ws_clients.remove(ws)
                    except ValueError:
                        pass

            await conn.add_listener("dashboard_update", _broadcast)
            logger.info("PostgreSQL LISTEN active on channel: dashboard_update")
            while True:
                await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"pg_notify listener crashed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────────
    pool = await create_pool()
    logger.info("Database connection pool created")

    # Kick off first price update immediately (non-blocking)
    asyncio.create_task(fetch_and_update_prices(pool))

    # Start APScheduler (60-second interval)
    start_scheduler(pool)

    # Pre-warm universe flags cache in background (fires after 15s)
    asyncio.create_task(_warm_market_cache())

    # Start pg_notify listener as background task
    listener_task = asyncio.create_task(listen_to_postgres(pool))

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────────
    listener_task.cancel()
    try:
        await listener_task
    except asyncio.CancelledError:
        pass

    stop_scheduler()
    await pool.close()
    logger.info("Shutdown complete")


app = FastAPI(title="FinSight API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router,      prefix="/api/auth",      tags=["auth"])
app.include_router(agents_router,    prefix="/api",           tags=["agents"])
app.include_router(customers_router, prefix="/api/customers", tags=["customers"])
app.include_router(portfolio_router, prefix="/api/portfolio", tags=["portfolio"])
app.include_router(alerts_router,    prefix="/api/alerts",    tags=["alerts"])
app.include_router(reports_router,   prefix="/api/reports",   tags=["reports"])
app.include_router(websocket_router,                          tags=["websocket"])
app.include_router(transactions_router, prefix="/api/transactions", tags=["transactions"])
app.include_router(banking_router,      prefix="/api/banking",      tags=["banking"])


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)},
    )


@app.get("/health")
async def health():
    pool = get_pool()
    db_status = "disconnected"
    if pool:
        try:
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            db_status = "connected"
        except Exception as e:
            db_status = f"error: {e}"

    from scheduler.price_updater import _scheduler
    scheduler_status = "running" if (_scheduler and _scheduler.running) else "stopped"

    return {
        "status": "ok",
        "database": db_status,
        "scheduler": scheduler_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
    }
