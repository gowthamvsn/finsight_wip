import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from auth.jwt_handler import get_current_user, get_customer_or_admin
from db.connection import fetch_all, fetch_one, get_pool

logger = logging.getLogger("routers.banking")
router = APIRouter()


def _guard(current_user: dict, customer_id: str):
    if current_user["role"] == "customer" and current_user["sub"] != customer_id:
        raise HTTPException(status_code=403, detail="Access denied")


# ── GET accounts ─────────────────────────────────────────────────────────────

@router.get("/{customer_id}/accounts")
async def get_accounts(
    customer_id: str,
    current_user: dict = Depends(get_customer_or_admin),
):
    _guard(current_user, customer_id)
    rows = await fetch_all("""
        SELECT account_id, bank_name, account_type, account_number,
               balance, interest_rate, currency, last_synced
        FROM bank_accounts
        WHERE customer_id = $1 AND is_active = TRUE
        ORDER BY account_type
    """, customer_id)
    return [dict(r) for r in rows]


# ── GET transactions ──────────────────────────────────────────────────────────

@router.get("/{customer_id}/transactions")
async def get_transactions(
    customer_id: str,
    category: str  = Query(default=None),
    limit:    int  = Query(default=50, le=200),
    current_user: dict = Depends(get_customer_or_admin),
):
    _guard(current_user, customer_id)
    since = (datetime.now(timezone.utc) - timedelta(days=90)).date()
    if category:
        rows = await fetch_all("""
            SELECT txn_id, txn_date, description, category,
                   amount, txn_direction, merchant, location, balance_after
            FROM bank_transactions
            WHERE customer_id = $1 AND txn_date >= $2 AND category = $3
            ORDER BY txn_date DESC, created_at DESC
            LIMIT $4
        """, customer_id, since, category, limit)
    else:
        rows = await fetch_all("""
            SELECT txn_id, txn_date, description, category,
                   amount, txn_direction, merchant, location, balance_after
            FROM bank_transactions
            WHERE customer_id = $1 AND txn_date >= $2
            ORDER BY txn_date DESC, created_at DESC
            LIMIT $3
        """, customer_id, since, limit)
    return [dict(r) for r in rows]


# ── GET spending summary ──────────────────────────────────────────────────────

@router.get("/{customer_id}/spending-summary")
async def get_spending_summary(
    customer_id: str,
    current_user: dict = Depends(get_customer_or_admin),
):
    _guard(current_user, customer_id)

    rows = await fetch_all("""
        SELECT period, category, total_spent, total_earned, txn_count, avg_txn_amount
        FROM spending_summary
        WHERE customer_id = $1
          AND period >= TO_CHAR(NOW() - INTERVAL '3 months', 'YYYY-MM')
        ORDER BY period DESC, total_spent DESC
    """, customer_id)

    if not rows:
        return {"period": None, "total_income": 0, "total_spending": 0,
                "net_cashflow": 0, "savings_rate": 0, "by_category": [],
                "monthly_trend": [], "interest_earned_ytd": 0, "interest_paid_ytd": 0}

    # current month = latest period in data
    current_month = rows[0]["period"]

    cur_rows  = [r for r in rows if r["period"] == current_month]
    prev_rows = [r for r in rows if r["period"] != current_month]

    # group prev by period for trend
    periods: dict = {}
    for r in rows:
        p = r["period"]
        if p not in periods:
            periods[p] = {"income": 0.0, "spending": 0.0}
        periods[p]["income"]   += float(r["total_earned"])
        periods[p]["spending"] += float(r["total_spent"])

    total_income   = sum(float(r["total_earned"]) for r in cur_rows)
    total_spending = sum(float(r["total_spent"])  for r in cur_rows)
    net_cashflow   = round(total_income - total_spending, 2)
    savings_rate   = round((total_income - total_spending) / total_income * 100, 1) if total_income > 0 else 0

    # prev month spending by category for % change
    prev_month_cat: dict = {}
    if prev_rows:
        prev_period = sorted(set(r["period"] for r in prev_rows))[-1]
        for r in prev_rows:
            if r["period"] == prev_period:
                prev_month_cat[r["category"]] = float(r["total_spent"])

    # build by_category for current month
    cat_total = total_spending or 1
    by_category = []
    for r in cur_rows:
        if float(r["total_spent"]) == 0 and float(r["total_earned"]) == 0:
            continue
        prev_val = prev_month_cat.get(r["category"], 0)
        vs_last = round((float(r["total_spent"]) - prev_val) / prev_val * 100, 1) if prev_val else 0
        trend = "increasing" if vs_last > 5 else "decreasing" if vs_last < -5 else "stable"
        by_category.append({
            "category":        r["category"],
            "total_spent":     float(r["total_spent"]),
            "total_earned":    float(r["total_earned"]),
            "txn_count":       r["txn_count"],
            "avg_txn":         float(r["avg_txn_amount"]),
            "pct_of_spending": round(float(r["total_spent"]) / cat_total * 100, 1),
            "vs_last_month":   vs_last,
            "trend":           trend,
        })

    by_category.sort(key=lambda x: x["total_spent"], reverse=True)

    interest_earned_ytd = sum(
        float(r["total_earned"]) for r in rows if r["category"] == "interest_earned"
    )
    interest_paid_ytd = sum(
        float(r["total_spent"]) for r in rows if r["category"] == "interest_paid"
    )

    monthly_trend = [
        {"period": p, "income": round(v["income"], 2), "spending": round(v["spending"], 2)}
        for p, v in sorted(periods.items())
    ]

    return {
        "period":              current_month,
        "total_income":        round(total_income, 2),
        "total_spending":      round(total_spending, 2),
        "net_cashflow":        net_cashflow,
        "savings_rate":        savings_rate,
        "by_category":         by_category,
        "monthly_trend":       monthly_trend,
        "interest_earned_ytd": round(interest_earned_ytd, 2),
        "interest_paid_ytd":   round(interest_paid_ytd, 2),
    }


# ── GET leaderboard (admin) ───────────────────────────────────────────────────

@router.get("/leaderboard")
async def get_leaderboard(
    current_user: dict = Depends(get_customer_or_admin),
):
    """Top 5 spenders, top 5 savers, top 5 portfolios — for admin dashboard."""
    from db.connection import fetch_all as fa

    period_expr = "TO_CHAR(NOW(), 'YYYY-MM')"

    top_spenders = await fa(f"""
        SELECT c.customer_id, c.first_name || ' ' || c.last_name AS name,
               c.advisor_tier,
               COALESCE(SUM(ss.total_spent), 0)  AS monthly_spending,
               COALESCE(SUM(ss.total_earned), 0) AS monthly_income
        FROM customers c
        LEFT JOIN spending_summary ss
               ON c.customer_id = ss.customer_id AND ss.period = {period_expr}
        GROUP BY c.customer_id, name, c.advisor_tier
        ORDER BY monthly_spending DESC
        LIMIT 5
    """)

    top_savers = await fa(f"""
        SELECT c.customer_id, c.first_name || ' ' || c.last_name AS name,
               c.advisor_tier,
               COALESCE(SUM(ss.total_earned), 0) AS monthly_income,
               COALESCE(SUM(ss.total_spent), 0)  AS monthly_spending,
               CASE WHEN COALESCE(SUM(ss.total_earned), 0) > 0
                    THEN ROUND(
                        (COALESCE(SUM(ss.total_earned), 0) - COALESCE(SUM(ss.total_spent), 0))
                        / SUM(ss.total_earned) * 100, 1)
                    ELSE 0 END AS savings_rate
        FROM customers c
        LEFT JOIN spending_summary ss
               ON c.customer_id = ss.customer_id AND ss.period = {period_expr}
        GROUP BY c.customer_id, name, c.advisor_tier
        HAVING COALESCE(SUM(ss.total_earned), 0) > 0
        ORDER BY savings_rate DESC
        LIMIT 5
    """)

    top_portfolios = await fa("""
        SELECT cs.customer_id, c.first_name || ' ' || c.last_name AS name,
               c.risk_profile, c.advisor_tier,
               COALESCE(cs.portfolio_value, 0) AS portfolio_value,
               COALESCE(cs.net_pl, 0) AS net_pl
        FROM customer_summary cs
        JOIN customers c ON cs.customer_id = c.customer_id
        ORDER BY cs.portfolio_value DESC
        LIMIT 5
    """)

    return {
        "top_spenders":   [dict(r) for r in top_spenders],
        "top_savers":     [dict(r) for r in top_savers],
        "top_portfolios": [dict(r) for r in top_portfolios],
    }


# ── POST analyze-spending ─────────────────────────────────────────────────────

@router.post("/{customer_id}/analyze-spending")
async def analyze_spending(
    customer_id: str,
    current_user: dict = Depends(get_customer_or_admin),
):
    _guard(current_user, customer_id)
    pool = get_pool()
    from agents.spending_analyst import run_spending_analyst
    return await run_spending_analyst(customer_id, pool)
