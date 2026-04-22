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


def _download_prices() -> dict:
    """Synchronous yfinance download — called via asyncio.to_thread."""
    try:
        import yfinance as yf
        symbols = list(TICKER_MAP.keys())
        data = yf.download(symbols, period="1d", interval="1m", progress=False, auto_adjust=True)
        if data.empty:
            logger.warning("yfinance returned empty data")
            return {}

        result = {}
        for yf_sym, db_ticker in TICKER_MAP.items():
            try:
                close_series = data["Close"][yf_sym].dropna()
                if len(close_series) < 1:
                    logger.warning(f"No close price for {yf_sym}")
                    continue

                price = float(close_series.iloc[-1])

                # Use day's first bar open as reference for intraday change %
                open_price = price
                change_pct = 0.0
                try:
                    open_series = data["Open"][yf_sym].dropna()
                    if not open_series.empty:
                        open_price = float(open_series.iloc[0])   # first bar = day open
                        if open_price > 0:
                            change_pct = round((price - open_price) / open_price * 100, 4)
                except Exception:
                    pass

                result[db_ticker] = (price, open_price, change_pct)
            except Exception as e:
                logger.warning(f"Price parse error for {yf_sym}: {e}")

        return result
    except Exception as e:
        logger.error(f"yfinance download failed: {e}")
        return {}


async def fetch_and_update_prices(pool) -> None:
    prices = await asyncio.to_thread(_download_prices)
    if not prices:
        logger.warning("Price update skipped — no data from yfinance")
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

        # Notify frontend WebSocket listeners
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
