import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from auth.jwt_handler import get_current_user
from db.connection import execute, fetch_one, fetch_all, get_pool
from utils.otp_store import create_otp, verify_otp
from utils.email_otp import send_otp_email

logger = logging.getLogger("routers.transactions")
router = APIRouter()

CRYPTO_TICKERS = {"BTC", "ETH", "SOL", "BNB"}
HIGH_RISK_COUNTRIES = {"NG", "RU", "CN", "IR", "KP"}
ASSET_TYPES = {
    "AAPL": "stock", "MSFT": "stock", "NVDA": "stock", "TSLA": "stock",
    "AMZN": "stock", "GOOGL": "stock", "META": "stock",
    "VTSAX": "etf", "SPY": "etf", "QQQ": "etf",
    "BTC": "crypto", "ETH": "crypto", "SOL": "crypto", "BNB": "crypto",
}


async def _update_holdings(customer_id: str, ticker: str, txn_type: str,
                           quantity: float, price_per_unit: float) -> None:
    """Update portfolio_holdings after a confirmed transaction."""
    holding = await fetch_one(
        "SELECT holding_id, quantity, avg_buy_price FROM portfolio_holdings WHERE customer_id=$1 AND ticker=$2",
        customer_id, ticker,
    )
    price_row = await fetch_one("SELECT price_usd FROM market_prices WHERE ticker=$1", ticker)
    current_price = float(price_row["price_usd"]) if price_row else price_per_unit

    if txn_type == "buy":
        if holding:
            old_qty = float(holding["quantity"])
            old_avg = float(holding["avg_buy_price"])
            new_qty = old_qty + quantity
            new_avg = (old_avg * old_qty + price_per_unit * quantity) / new_qty
            current_value = round(new_qty * current_price, 2)
            unreal_pl = round((current_price - new_avg) * new_qty, 2)
            unreal_pct = round((current_price - new_avg) / new_avg * 100, 2) if new_avg > 0 else 0
            await execute(
                """UPDATE portfolio_holdings
                   SET quantity=$1, avg_buy_price=$2, current_price=$3,
                       current_value=$4, unrealized_pl=$5, unrealized_pl_pct=$6, last_updated=NOW()
                   WHERE holding_id=$7""",
                new_qty, new_avg, current_price, current_value, unreal_pl, unreal_pct,
                holding["holding_id"],
            )
        else:
            asset_type = ASSET_TYPES.get(ticker, "stock")
            current_value = round(quantity * current_price, 2)
            unreal_pl = round((current_price - price_per_unit) * quantity, 2)
            unreal_pct = round((current_price - price_per_unit) / price_per_unit * 100, 2) if price_per_unit > 0 else 0
            holding_id = "HLD-" + uuid.uuid4().hex[:7].upper()
            await execute(
                """INSERT INTO portfolio_holdings
                     (holding_id, customer_id, ticker, asset_type, quantity, avg_buy_price,
                      current_price, current_value, unrealized_pl, unrealized_pl_pct, purchased_at, last_updated)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,NOW(),NOW())""",
                holding_id, customer_id, ticker, asset_type, quantity, price_per_unit,
                current_price, current_value, unreal_pl, unreal_pct,
            )
    elif txn_type == "sell" and holding:
        new_qty = float(holding["quantity"]) - quantity
        avg = float(holding["avg_buy_price"])
        if new_qty <= 0:
            await execute("DELETE FROM portfolio_holdings WHERE holding_id=$1", holding["holding_id"])
        else:
            current_value = round(new_qty * current_price, 2)
            unreal_pl = round((current_price - avg) * new_qty, 2)
            unreal_pct = round((current_price - avg) / avg * 100, 2) if avg > 0 else 0
            await execute(
                """UPDATE portfolio_holdings
                   SET quantity=$1, current_price=$2, current_value=$3,
                       unrealized_pl=$4, unrealized_pl_pct=$5, last_updated=NOW()
                   WHERE holding_id=$6""",
                new_qty, current_price, current_value, unreal_pl, unreal_pct,
                holding["holding_id"],
            )

class TransactionRequest(BaseModel):
    customer_id: str          # admin can specify any; customer must match their own
    ticker: str
    txn_type: str             # "buy" | "sell"
    quantity: float
    price_per_unit: float
    geo_country: str = "US"

class OTPConfirmRequest(BaseModel):
    challenge_id: str
    otp: str

def _fraud_precheck(ticker: str, txn_type: str, total_value: float, geo_country: str) -> list:
    """Fast rule-based check. Returns list of suspicious reasons (empty = clean)."""
    reasons = []
    t = ticker.upper()
    hour = datetime.now(timezone.utc).hour

    if total_value > 50000:
        reasons.append(f"Large transaction: ${total_value:,.2f}")
    if hour in range(0, 6) and t in CRYPTO_TICKERS:
        reasons.append(f"Crypto trade at unusual hour ({hour:02d}:00 UTC)")
    if geo_country.upper() in HIGH_RISK_COUNTRIES:
        reasons.append(f"High-risk country: {geo_country.upper()}")

    return reasons

@router.post("")
async def submit_transaction(
    body: TransactionRequest,
    current_user: dict = Depends(get_current_user),
):
    # Authorization check
    if current_user["role"] == "customer" and current_user["sub"] != body.customer_id:
        raise HTTPException(status_code=403, detail="Cannot submit transaction for another customer")

    ticker = body.ticker.upper()
    total_value = round(body.quantity * body.price_per_unit, 2)
    txn_category = "crypto" if ticker in CRYPTO_TICKERS else "stock"
    txn_id = "TXN-" + uuid.uuid4().hex[:8].upper()

    # Validate sell: customer must hold enough
    if body.txn_type == "sell":
        holding = await fetch_one(
            "SELECT quantity FROM portfolio_holdings WHERE customer_id=$1 AND ticker=$2",
            body.customer_id, ticker,
        )
        if not holding or float(holding["quantity"]) < body.quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient holdings: you don't hold {body.quantity} of {ticker}")

    # Insert transaction (flagged=False initially)
    await execute(
        """
        INSERT INTO transactions
          (txn_id, customer_id, ticker, txn_type, txn_category,
           quantity, price_at_txn, total_value, realized_pl,
           flagged, txn_timestamp, ip_address, geo_country)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,0,FALSE,NOW(),'0.0.0.0',$9)
        """,
        txn_id, body.customer_id, ticker, body.txn_type, txn_category,
        body.quantity, body.price_per_unit, total_value, body.geo_country,
    )

    # Fraud pre-check
    reasons = _fraud_precheck(ticker, body.txn_type, total_value, body.geo_country)

    if reasons:
        # Generate OTP and send to customer email
        challenge_id, otp = create_otp(txn_id, body.customer_id,
                                        ticker=ticker, txn_type=body.txn_type,
                                        quantity=body.quantity, price=body.price_per_unit)
        customer = await fetch_one(
            "SELECT email, first_name, last_name FROM customers WHERE customer_id=$1",
            body.customer_id,
        )
        demo_otp = None
        if customer:
            sent = await send_otp_email(
                customer["email"],
                f"{customer['first_name']} {customer['last_name']}",
                otp,
                reasons,
            )
            if not sent:
                # Email not configured — return OTP in response for demo
                demo_otp = otp

        logger.info(f"Transaction {txn_id} flagged — OTP challenge created: {challenge_id}")
        return {
            "status": "requires_otp",
            "txn_id": txn_id,
            "challenge_id": challenge_id,
            "reasons": reasons,
            "total_value": total_value,
            "ticker": ticker,
            "txn_type": body.txn_type,
            "quantity": body.quantity,
            "message": "Suspicious activity detected. OTP sent to registered email.",
            "demo_otp": demo_otp,   # None in production, visible if email not configured
        }

    # Update holdings immediately for clean transactions
    await _update_holdings(body.customer_id, ticker, body.txn_type, body.quantity, body.price_per_unit)

    # Run fraud agent in background and return immediately
    import asyncio
    pool = get_pool()
    asyncio.create_task(_run_fraud_check(txn_id, body.customer_id, pool))

    logger.info(f"Transaction {txn_id} approved — no suspicious signals")
    return {
        "status": "approved",
        "txn_id": txn_id,
        "total_value": total_value,
        "ticker": ticker,
        "txn_type": body.txn_type,
        "quantity": body.quantity,
        "message": "Transaction submitted successfully.",
    }


@router.post("/confirm")
async def confirm_otp(
    body: OTPConfirmRequest,
    current_user: dict = Depends(get_current_user),
):
    entry = verify_otp(body.challenge_id, body.otp)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OTP. Please try again.",
        )

    txn_id = entry["txn_id"]
    customer_id = entry["customer_id"]

    # Update holdings now that OTP is verified
    await _update_holdings(
        customer_id, entry["ticker"], entry["txn_type"],
        entry["quantity"], entry["price"],
    )

    # Run full fraud agent in background
    import asyncio
    pool = get_pool()
    asyncio.create_task(_run_fraud_check(txn_id, customer_id, pool))

    logger.info(f"OTP confirmed for transaction {txn_id} — approved")
    return {
        "status": "approved",
        "txn_id": txn_id,
        "message": "OTP verified. Transaction approved and recorded.",
    }


async def _run_fraud_check(txn_id: str, customer_id: str, pool):
    try:
        from agents.fraud import run_fraud_agent
        await run_fraud_agent(txn_id, customer_id, pool)
    except Exception as e:
        logger.error(f"Background fraud check failed for {txn_id}: {e}")
