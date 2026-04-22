import logging
import os
from datetime import datetime

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(), override=True)

from db.connection import fetch_one, fetch_all

logger = logging.getLogger("agents.portfolio")

SYSTEM_PROMPT = """You are the Portfolio Agent for FinSight wealth management platform.
Analyze the customer's portfolio data and give concise professional financial analysis.
Use only the data provided. Do not invent numbers. Be direct and actionable."""

_RISK_LIMITS = {
    "conservative": 10.0,
    "moderate": 25.0,
    "aggressive": 50.0,
}


def _get_anthropic_client():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import anthropic
        return anthropic.Anthropic(api_key=api_key)
    except Exception as e:
        logger.error(f"Anthropic client init failed: {e}")
        return None


async def run_portfolio_agent(customer_id: str, pool) -> dict:
    start = datetime.utcnow()
    try:
        summary = await fetch_one(
            """
            SELECT cs.*, c.risk_profile, c.advisor_tier,
                   c.first_name, c.last_name
            FROM customer_summary cs
            JOIN customers c ON cs.customer_id = c.customer_id
            WHERE cs.customer_id = $1
            """,
            customer_id,
        )

        if not summary:
            return {"analysis": "Customer not found.", "error": "not_found", "duration_ms": 0}

        holdings = await fetch_all(
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

        loans = await fetch_all(
            """
            SELECT loan_type, outstanding_balance, interest_rate_pct,
                   emi_monthly, status, next_due_date
            FROM loans WHERE customer_id = $1 AND status != 'closed'
            ORDER BY outstanding_balance DESC
            """,
            customer_id,
        )

        risk_profile = summary["risk_profile"]
        crypto_limit = _RISK_LIMITS.get(risk_profile, 25.0)
        crypto_pct = float(summary["crypto_pct"] or 0)
        risk_breached = crypto_pct > crypto_limit

        holdings_text = "\n".join([
            f"  {h['ticker']} ({h['asset_type']}): "
            f"qty={h['quantity']}, avg_buy=${h['avg_buy_price']}, "
            f"current=${h['current_price']}, value=${h['current_value']:,.2f}, "
            f"P&L=${h['unrealized_pl']:,.2f} ({h['unrealized_pl_pct']}%)"
            + (f", 1d={h['change_1d_pct']}%" if h['change_1d_pct'] is not None else "")
            for h in holdings if h["asset_type"] != "cash"
        ]) or "  No holdings"

        loans_text = "\n".join([
            f"  {l['loan_type']}: outstanding=${l['outstanding_balance']:,.2f}, "
            f"rate={l['interest_rate_pct']}%, EMI=${l['emi_monthly']:,.2f}, status={l['status']}"
            for l in loans
        ]) or "  No active loans"

        context = f"""Customer: {summary['first_name']} {summary['last_name']} ({customer_id})
Risk Profile: {risk_profile} (crypto limit {crypto_limit}%) | Tier: {summary['advisor_tier']}

PORTFOLIO: Value=${summary['portfolio_value']:,.2f} | Net Worth=${summary['net_worth']:,.2f} | Cash=${summary['cash_balance']:,.2f}
P&L: Unrealized=${summary['unrealized_pl']:,.2f} | Realized=${summary['realized_pl']:,.2f} | Net=${summary['net_pl']:,.2f}
Allocation: Stocks={summary['stock_pct']}% | Crypto={summary['crypto_pct']}% | ETFs={summary['etf_pct']}% | Cash={summary['cash_pct']}%
Risk: {'BREACH — crypto {crypto_pct}% exceeds {crypto_limit}% limit' if risk_breached else 'Within limits'}

HOLDINGS:
{holdings_text}

LOANS:
{loans_text}

Write exactly 3 sections, 2-3 sentences each. Complete every sentence. Total under 300 words.
## Performance Overview
## Allocation & Risk
## 3 Recommendations (bullet points)"""

        client = _get_anthropic_client()
        if not client:
            return {
                "analysis": "Portfolio analysis unavailable — ANTHROPIC_API_KEY not configured.",
                "duration_ms": 0,
            }

        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=700,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": context}],
        )

        analysis = message.content[0].text
        ms = int((datetime.utcnow() - start).total_seconds() * 1000)
        logger.info(f"Portfolio agent: customer={customer_id} duration={ms}ms tokens={message.usage.input_tokens+message.usage.output_tokens}")

        return {
            "analysis": analysis,
            "summary": dict(summary),
            "holdings": [dict(h) for h in holdings],
            "loans": [dict(l) for l in loans],
            "duration_ms": ms,
        }

    except Exception as e:
        logger.error(f"Portfolio agent error: customer={customer_id} error={e}")
        return {
            "analysis": "Portfolio analysis temporarily unavailable. Please try again.",
            "error": str(e),
            "duration_ms": 0,
        }
