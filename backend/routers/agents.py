import asyncio
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
# Critic agent — runs Portfolio + Market in parallel then reconciles conflicts
# ──────────────────────────────────────────────────────────────────────────────
@router.post("/agent/critic/{customer_id}")
async def critic_endpoint(
    customer_id: str,
    current_user: dict = Depends(get_customer_or_admin),
):
    pool = get_pool()
    held = await get_customer_tickers(customer_id, pool)

    from agents.portfolio import run_portfolio_agent
    from agents.market import run_market_agent

    portfolio_result, market_result = await asyncio.gather(
        run_portfolio_agent(customer_id, pool),
        run_market_agent(customer_id, held, pool),
    )

    customer = await fetch_one(
        "SELECT risk_profile FROM customers WHERE customer_id=$1", customer_id
    )
    risk_profile = customer["risk_profile"] if customer else "moderate"

    from agents.critic import run_critic_agent
    critic_result = await run_critic_agent(
        portfolio_analysis=portfolio_result.get("analysis", ""),
        portfolio_holdings=portfolio_result.get("holdings", []),
        market_predictions=market_result.get("portfolio_predictions", []),
        customer_risk_profile=risk_profile,
        pool=pool,
    )

    return {
        "portfolio": portfolio_result,
        "market": market_result,
        "critic": critic_result,
    }


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
# Wealth snapshot — portfolio + banking in parallel, ~50 words each (customer only)
# ──────────────────────────────────────────────────────────────────────────────
@router.post("/agent/wealth-snapshot/{customer_id}")
async def wealth_snapshot_endpoint(
    customer_id: str,
    current_user: dict = Depends(get_customer_or_admin),
):
    caller_id = current_user.get("sub", current_user.get("user_id", ""))
    if current_user.get("role") == "customer" and customer_id != caller_id:
        raise HTTPException(status_code=403, detail="You can only request a snapshot for your own account")

    pool = get_pool()
    from agents.portfolio import run_portfolio_agent
    from agents.spending_analyst import run_spending_analyst

    portfolio_result, banking_result = await asyncio.gather(
        run_portfolio_agent(customer_id, pool, snapshot=True),
        run_spending_analyst(customer_id, pool, snapshot=True),
    )

    return {
        "portfolio": portfolio_result.get("analysis", ""),
        "banking":   banking_result.get("analysis", ""),
        "portfolio_duration_ms": portfolio_result.get("duration_ms", 0),
        "banking_duration_ms":   banking_result.get("duration_ms", 0),
    }


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
