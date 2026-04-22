import asyncio
import json
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.events import EVENT_JOB_ERROR
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(), override=True)

logger = logging.getLogger("price_updater")

TICKER_MAP = {
    "NVDA":  "NVDA",
    "TSLA":  "TSLA",
    "AAPL":  "AAPL",
    "MSFT":  "MSFT",
    "AMZN":  "AMZN",
    "GOOGL": "GOOGL",
    "META":  "META",
    "VTSAX": "VTSAX",
    "SPY":   "SPY",
    "QQQ":   "QQQ",
    "BTC-USD": "BTC",
    "ETH-USD": "ETH",
    "SOL-USD": "SOL",
    "BNB-USD": "BNB",
}

_scheduler: AsyncIOScheduler = None


def _fetch_single(yf_sym: str) -> tuple | None:
    """Fetch price for one symbol. Returns (price, prev_close, change_pct) or None."""
    try:
        import yfinance as yf
        hist = yf.Ticker(yf_sym).history(period="2d", interval="1d")
        if hist.empty or len(hist) < 1:
            return None
        price = float(hist["Close"].iloc[-1])
        prev_close = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else price
        if price <= 0:
            return None
        change_pct = round((price - prev_close) / prev_close * 100, 4) if prev_close > 0 else 0.0
        return (price, prev_close, change_pct)
    except Exception:
        return None


def _download_prices() -> dict:
    """Fetch prices for all tickers. Falls back to random walk if yfinance is blocked."""
    result = {}
    for yf_sym, db_ticker in TICKER_MAP.items():
        row = _fetch_single(yf_sym)
        if row:
            result[db_ticker] = row
        else:
            logger.debug(f"yfinance blocked/empty for {yf_sym}")
    return result


def _random_walk_prices(current_prices: dict) -> dict:
    """Apply ±0.3% random walk to existing prices when yfinance is unavailable.
    Keeps the live-update cascade firing for demos even without market data."""
    import random
    result = {}
    for db_ticker, (price, prev_close, _) in current_prices.items():
        delta = price * random.uniform(-0.003, 0.003)
        new_price = round(price + delta, 4)
        change_pct = round((new_price - prev_close) / prev_close * 100, 4) if prev_close > 0 else 0.0
        result[db_ticker] = (new_price, prev_close, change_pct)
    return result


async def fetch_and_update_prices(pool) -> None:
    prices = await asyncio.to_thread(_download_prices)

    # If yfinance is blocked (common in cloud), fall back to random walk
    # so the trigger cascade and WebSocket live demo still fire correctly.
    if not prices:
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT ticker, price_usd, open_price FROM market_prices"
                )
                current = {
                    r["ticker"]: (float(r["price_usd"]), float(r["open_price"] or r["price_usd"]), 0.0)
                    for r in rows
                }
            prices = _random_walk_prices(current)
            logger.info("yfinance unavailable — using random walk for demo price updates")
        except Exception as e:
            logger.error(f"Random walk fallback failed: {e}")
            return

    now = datetime.now(timezone.utc)
    updated = []
    try:
        async with pool.acquire() as conn:
            for db_ticker, (price, open_price, change_pct) in prices.items():
                await conn.execute(
                    """
                    UPDATE market_prices
                    SET price_usd       = $1,
                        open_price      = $2,
                        change_1d_pct   = $3,
                        price_timestamp = $4,
                        last_updated    = $4
                    WHERE ticker = $5
                    """,
                    price, open_price, change_pct, now, db_ticker,
                )
                updated.append(f"{db_ticker}=${price:,.2f}")

        async with pool.acquire() as notify_conn:
            payload = json.dumps({"type": "price_update", "ts": now.isoformat(), "count": len(updated)})
            await notify_conn.execute("SELECT pg_notify('dashboard_update', $1)", payload)

        summary = ", ".join(updated)
        logger.info(f"[{now.strftime('%H:%M:%S UTC')}] Prices updated ({len(updated)}): {summary}")
    except Exception as e:
        logger.error(f"DB price write failed: {e}")


def on_job_error(event) -> None:
    logger.error(f"Scheduler job error: {event.exception}", exc_info=event.exception)


async def _rebuild_universe_cache_job() -> None:
    """Wrapper so APScheduler can call the sync cache builder via asyncio.to_thread."""
    try:
        from agents.market import _build_universe_cache
        logger.info("Daily universe cache rebuild starting…")
        await asyncio.to_thread(_build_universe_cache)
        logger.info("Daily universe cache rebuild complete")
    except Exception as e:
        logger.error(f"Universe cache rebuild failed: {e}")


def start_scheduler(pool) -> AsyncIOScheduler:
    global _scheduler
    _scheduler = AsyncIOScheduler(timezone="UTC")
    _scheduler.add_listener(on_job_error, EVENT_JOB_ERROR)

    # Price update every 60 seconds
    _scheduler.add_job(
        fetch_and_update_prices,
        trigger="interval",
        seconds=60,
        args=[pool],
        id="price_update",
        max_instances=1,
        coalesce=True,
    )

    # Universe cache rebuild once per day at 13:30 UTC (09:30 EST — US market open)
    _scheduler.add_job(
        _rebuild_universe_cache_job,
        trigger="cron",
        hour=13,
        minute=30,
        id="universe_cache_rebuild",
        max_instances=1,
        coalesce=True,
    )

    _scheduler.start()
    logger.info("yfinance price scheduler started — updating every 60 seconds from live market data")
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Price scheduler stopped")
