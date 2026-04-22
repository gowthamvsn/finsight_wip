import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth.jwt_handler import get_current_user, get_admin_user, get_customer_or_admin
from db.connection import get_pool, fetch_one, execute
from agents.orchestrator import get_customer_tickers

logger = logging.getLogger("routers.agents")

router = APIRouter()


class OrchestrateRequest(BaseModel):
    query: str
    customer_id: str


class SupportRequest(BaseModel):
    query: str
    customer_id: str


# ──────────────────────────────────────────────────────────────────────────────
# Portfolio agent
# ──────────────────────────────────────────────────────────────────────────────
@router.post("/agent/portfolio/{customer_id}")
async def portfolio_endpoint(
    customer_id: str,
    current_user: dict = Depends(get_customer_or_admin),
):
    pool = get_pool()
    from agents.portfolio import run_portfolio_agent
    return await run_portfolio_agent(customer_id, pool)


# ──────────────────────────────────────────────────────────────────────────────
# Market agent
# ──────────────────────────────────────────────────────────────────────────────
@router.post("/agent/market/{customer_id}")
async def market_endpoint(
    customer_id: str,
    current_user: dict = Depends(get_customer_or_admin),
):
    pool = get_pool()
    held = await get_customer_tickers(customer_id, pool)
    from agents.market import run_market_agent
    return await run_market_agent(customer_id, held, pool)


# ──────────────────────────────────────────────────────────────────────────────
# Orchestrator
# ──────────────────────────────────────────────────────────────────────────────
@router.post("/agent/orchestrate")
async def orchestrate_endpoint(
    body: OrchestrateRequest,
    current_user: dict = Depends(get_current_user),
):
    pool = get_pool()
    role = current_user.get("role", "customer")
    from agents.orchestrator import run_orchestrator
    return await run_orchestrator(body.query, body.customer_id, role, pool)


# ──────────────────────────────────────────────────────────────────────────────
# Report agent (admin only)
# ──────────────────────────────────────────────────────────────────────────────
@router.post("/agent/report/{customer_id}")
async def report_endpoint(
    customer_id: str,
    current_user: dict = Depends(get_admin_user),
):
    pool = get_pool()
    from agents.report import run_report_agent
    return await run_report_agent(customer_id, pool)


# ──────────────────────────────────────────────────────────────────────────────
# Support agent
# ──────────────────────────────────────────────────────────────────────────────
@router.post("/agent/support")
async def support_endpoint(
    body: SupportRequest,
    current_user: dict = Depends(get_current_user),
):
    pool = get_pool()
    from agents.support import run_support_agent
    return await run_support_agent(body.query, body.customer_id, pool)


# ──────────────────────────────────────────────────────────────────────────────
# Demo: trigger fraud scenario
# ──────────────────────────────────────────────────────────────────────────────
@router.post("/demo/trigger-fraud")
async def trigger_fraud_demo(
    current_user: dict = Depends(get_admin_user),
):
    pool = get_pool()

    # Get live BTC price from DB (populated by yfinance scheduler)
    price_row = await fetch_one(
        "SELECT price_usd FROM market_prices WHERE ticker='BTC'"
    )
    if not price_row:
        raise HTTPException(status_code=500, detail="BTC price not available in market_prices")

    btc_price = float(price_row["price_usd"])
    quantity = 1.4
    total_value = round(quantity * btc_price, 2)

    # Build txn_timestamp: today at 02:00 UTC
    now_utc = datetime.now(timezone.utc)
    txn_ts = now_utc.replace(hour=2, minute=0, second=0, microsecond=0)

    # Insert demo transaction (idempotent)
    await execute(
        """
        INSERT INTO transactions
          (txn_id, customer_id, ticker, txn_type, txn_category,
           quantity, price_at_txn, total_value, realized_pl, flagged,
           txn_timestamp, ip_address, geo_country, created_at)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,0,FALSE,$9,$10,$11,NOW())
        ON CONFLICT (txn_id) DO UPDATE
          SET price_at_txn=$7, total_value=$8, txn_timestamp=$9
        """,
        "TXN-DEMO-001",
        "CUS-0002",
        "BTC",
        "transfer",
        "investment",
        quantity,
        btc_price,
        total_value,
        txn_ts,
        "196.201.214.7",
        "NG",
    )

    # Run fraud agent on this transaction
    from agents.fraud import run_fraud_agent
    result = await run_fraud_agent("TXN-DEMO-001", "CUS-0002", pool)

    logger.info(
        f"Fraud demo triggered: BTC=${btc_price:,.2f} "
        f"total=${total_value:,.2f} alerts={result.get('alerts_created', 0)}"
    )

    return {
        "alert_created": result.get("alerts_created", 0) > 0,
        "btc_price_used": btc_price,
        "total_value": total_value,
        "txn_timestamp": txn_ts.isoformat(),
        "alert_details": result,
    }
