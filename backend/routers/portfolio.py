import logging

from fastapi import APIRouter, Depends, HTTPException, status

from auth.jwt_handler import get_current_user
from db.connection import fetch_all, fetch_one

logger = logging.getLogger("routers.portfolio")

router = APIRouter()


def _check_scope(current_user: dict, customer_id: str) -> None:
    if current_user["role"] == "customer" and current_user["sub"] != customer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied — you can only view your own portfolio",
        )


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
