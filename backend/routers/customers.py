import logging

from fastapi import APIRouter, Depends, HTTPException, status

from auth.jwt_handler import get_admin_user, get_current_user
from db.connection import fetch_all, fetch_one

logger = logging.getLogger("routers.customers")

router = APIRouter()

_CUSTOMERS_QUERY = """
SELECT c.customer_id, c.first_name, c.last_name, c.email,
       c.risk_profile, c.advisor_tier, c.is_active, c.created_at,
       cs.portfolio_value, cs.net_worth, cs.cash_balance,
       cs.unrealized_pl, cs.realized_pl, cs.net_pl,
       cs.annualized_return_pct, cs.sp500_return_pct,
       cs.stock_pct, cs.crypto_pct, cs.etf_pct, cs.cash_pct,
       cs.loan_outstanding,
       (SELECT COUNT(*) FROM alerts a
        WHERE a.customer_id = c.customer_id
          AND a.status = 'open') AS open_alert_count
FROM customers c
LEFT JOIN customer_summary cs ON c.customer_id = cs.customer_id
"""


@router.get("")
async def list_customers(
    current_user: dict = Depends(get_admin_user),
):
    rows = await fetch_all(
        _CUSTOMERS_QUERY + "ORDER BY cs.portfolio_value DESC NULLS LAST"
    )
    return [dict(r) for r in rows]


@router.get("/{customer_id}")
async def get_customer(
    customer_id: str,
    current_user: dict = Depends(get_current_user),
):
    if current_user["role"] == "customer" and current_user["sub"] != customer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied — you can only view your own profile",
        )

    row = await fetch_one(
        _CUSTOMERS_QUERY + "WHERE c.customer_id = $1",
        customer_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Customer not found")
    return dict(row)
