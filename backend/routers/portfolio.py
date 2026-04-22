import asyncio
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, status

from auth.jwt_handler import get_current_user
from db.connection import fetch_all, fetch_one

logger = logging.getLogger("routers.portfolio")

router = APIRouter()

# Human-readable company/asset names for better NewsAPI queries
_TICKER_NAMES = {
    "AAPL": "Apple stock", "MSFT": "Microsoft stock", "NVDA": "NVIDIA stock",
    "TSLA": "Tesla stock", "AMZN": "Amazon stock", "GOOGL": "Google Alphabet stock",
    "META": "Meta Platforms stock", "VTSAX": "Vanguard total stock market",
    "SPY": "S&P 500 ETF", "QQQ": "Nasdaq 100 ETF",
    "BTC": "Bitcoin", "ETH": "Ethereum", "SOL": "Solana", "BNB": "Binance coin",
}


async def _newsapi_article(ticker: str) -> dict | None:
    """Fetch the single most relevant recent article from NewsAPI.org."""
    api_key = os.getenv("NEWS_API_KEY", "")
    if not api_key:
        return None
    query = _TICKER_NAMES.get(ticker, ticker)
    url = (
        f"https://newsapi.org/v2/everything"
        f"?q={query.replace(' ', '+')}"
        f"&pageSize=3&sortBy=publishedAt&language=en"
        f"&apiKey={api_key}"
    )
    try:
        import httpx
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(url)
            if r.status_code != 200:
                return None
            articles = r.json().get("articles", [])
            if not articles:
                return None
            a = articles[0]
            return {
                "ticker": ticker,
                "title": a.get("title", ""),
                "publisher": a.get("source", {}).get("name", ""),
                "link": a.get("url", ""),
                "summary": a.get("description") or "",
                "published_at": a.get("publishedAt", ""),
                "source": "newsapi",
            }
    except Exception as e:
        logger.debug(f"NewsAPI failed for {ticker}: {e}")
        return None


async def _gemini_article(ticker: str) -> dict | None:
    """Generate a realistic news summary via Gemini when NewsAPI is unavailable."""
    try:
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GEMINI_API_KEY", ""))
        model = genai.GenerativeModel("gemini-2.0-flash")
        prompt = (
            f"Give me the single most important news story about {_TICKER_NAMES.get(ticker, ticker)} "
            f"right now. Reply with ONLY a JSON object with these keys: "
            f"title, publisher, summary (one sentence), sentiment (bullish/bearish/neutral). "
            f"No markdown, no extra text."
        )
        def _call():
            return model.generate_content(prompt)
        resp = await asyncio.to_thread(_call)
        import json, re
        raw = resp.text.strip()
        raw = re.sub(r"^```json\s*|^```\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()
        data = json.loads(raw)
        return {
            "ticker": ticker,
            "title": data.get("title", ""),
            "publisher": data.get("publisher", "Gemini AI"),
            "link": "",
            "summary": data.get("summary", ""),
            "sentiment": data.get("sentiment", "neutral"),
            "published_at": "",
            "source": "gemini",
        }
    except Exception as e:
        logger.debug(f"Gemini news fallback failed for {ticker}: {e}")
        return None


def _check_scope(current_user: dict, customer_id: str) -> None:
    if current_user["role"] == "customer" and current_user["sub"] != customer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied — you can only view your own portfolio",
        )


@router.get("/{customer_id}/news")
async def get_holding_news(
    customer_id: str,
    current_user: dict = Depends(get_current_user),
):
    _check_scope(current_user, customer_id)

    holdings = await fetch_all(
        "SELECT DISTINCT ticker FROM portfolio_holdings WHERE customer_id=$1 AND asset_type != 'cash'",
        customer_id,
    )
    tickers = [r["ticker"] for r in holdings]

    news_items = []
    for ticker in tickers[:8]:
        article = await _newsapi_article(ticker)
        if not article:
            article = await _gemini_article(ticker)
        if article:
            news_items.append(article)

    return {"news": news_items, "tickers": tickers}


@router.get("/prices")
async def get_market_prices(current_user: dict = Depends(get_current_user)):
    rows = await fetch_all("SELECT ticker, price_usd FROM market_prices ORDER BY ticker")
    return {r["ticker"]: float(r["price_usd"]) for r in rows}


@router.get("/{customer_id}")
async def get_portfolio(
    customer_id: str,
    current_user: dict = Depends(get_current_user),
):
    _check_scope(current_user, customer_id)

    summary, holdings, transactions, loans, alerts = await _fetch_all_portfolio(customer_id)

    if not summary:
        raise HTTPException(status_code=404, detail="Customer not found")

    return {
        "summary":      dict(summary),
        "holdings":     [dict(r) for r in holdings],
        "transactions": [dict(r) for r in transactions],
        "loans":        [dict(r) for r in loans],
        "alerts":       [dict(r) for r in alerts],
    }


@router.get("/{customer_id}/pl")
async def get_pl_breakdown(
    customer_id: str,
    current_user: dict = Depends(get_current_user),
):
    _check_scope(current_user, customer_id)

    summary = await fetch_one(
        """
        SELECT cs.unrealized_pl, cs.realized_pl, cs.interest_paid_ytd,
               cs.net_pl, cs.annualized_return_pct, cs.sp500_return_pct
        FROM customer_summary cs
        WHERE cs.customer_id = $1
        """,
        customer_id,
    )
    if not summary:
        raise HTTPException(status_code=404, detail="Customer not found")

    by_asset = await fetch_all(
        """
        SELECT asset_type,
               SUM(unrealized_pl)   AS unrealized_pl,
               SUM(current_value)   AS current_value
        FROM portfolio_holdings
        WHERE customer_id = $1 AND asset_type != 'cash'
        GROUP BY asset_type
        """,
        customer_id,
    )

    ann = float(summary["annualized_return_pct"] or 0)
    sp5 = float(summary["sp500_return_pct"] or 0)

    return {
        "by_asset_type":         [dict(r) for r in by_asset],
        "realized_pl":           float(summary["realized_pl"] or 0),
        "interest_paid_ytd":     float(summary["interest_paid_ytd"] or 0),
        "net_pl":                float(summary["net_pl"] or 0),
        "annualized_return_pct": ann,
        "sp500_return_pct":      sp5,
        "beating_market":        ann > sp5,
    }


async def _fetch_all_portfolio(customer_id: str):
    import asyncio

    summary_task = fetch_one(
        """
        SELECT cs.*, c.first_name, c.last_name, c.email,
               c.risk_profile, c.advisor_tier
        FROM customer_summary cs
        JOIN customers c ON cs.customer_id = c.customer_id
        WHERE cs.customer_id = $1
        """,
        customer_id,
    )
    holdings_task = fetch_all(
        """
        SELECT ph.ticker, ph.asset_type, ph.quantity, ph.avg_buy_price,
               ph.current_price, ph.current_value, ph.unrealized_pl,
               ph.unrealized_pl_pct,
               mp.change_1d_pct, mp.predicted_5d_pct, mp.prediction_confidence
        FROM portfolio_holdings ph
        LEFT JOIN market_prices mp ON ph.ticker = mp.ticker
        WHERE ph.customer_id = $1
        ORDER BY ph.current_value DESC
        """,
        customer_id,
    )
    txns_task = fetch_all(
        """
        SELECT ticker, txn_type, txn_category, quantity, price_at_txn,
               total_value, realized_pl, flagged, txn_timestamp,
               ip_address, geo_country
        FROM transactions
        WHERE customer_id = $1
        ORDER BY txn_timestamp DESC
        LIMIT 20
        """,
        customer_id,
    )
    loans_task = fetch_all(
        """
        SELECT loan_type, outstanding_balance, interest_rate_pct,
               emi_monthly, status, next_due_date
        FROM loans
        WHERE customer_id = $1 AND status != 'closed'
        ORDER BY outstanding_balance DESC
        """,
        customer_id,
    )
    alerts_task = fetch_all(
        """
        SELECT alert_id, alert_type, severity, source,
               description, status, detected_at
        FROM alerts
        WHERE customer_id = $1 AND status = 'open'
        ORDER BY detected_at DESC
        LIMIT 10
        """,
        customer_id,
    )

    return await asyncio.gather(
        summary_task, holdings_task, txns_task, loans_task, alerts_task
    )
