import logging
import os
from datetime import datetime

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(), override=True)

from db.connection import fetch_one, fetch_all

logger = logging.getLogger("agents.report")

SYSTEM_PROMPT = """You are the Report Generator Agent for \
FinSight wealth management platform.

Write professional client advisory reports based strictly \
on the data provided. Do not invent numbers. Do not make \
predictions beyond what the data supports. Always include \
a risk disclaimer section. Format with clear section headers."""


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


async def run_report_agent(customer_id: str, pool) -> dict:
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
            return {"error": "Customer not found", "duration_ms": 0}

        holdings = await fetch_all(
            """
            SELECT ph.ticker, ph.asset_type, ph.quantity, ph.avg_buy_price,
                   ph.current_price, ph.current_value, ph.unrealized_pl,
                   ph.unrealized_pl_pct,
                   mp.change_1d_pct, mp.predicted_5d_pct
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
                   emi_monthly, status
            FROM loans WHERE customer_id = $1 AND status != 'closed'
            ORDER BY outstanding_balance DESC
            """,
            customer_id,
        )

        alerts = await fetch_all(
            """
            SELECT alert_type, severity, description, status
            FROM alerts WHERE customer_id = $1 AND status = 'open'
            ORDER BY detected_at DESC LIMIT 5
            """,
            customer_id,
        )

        holdings_text = "\n".join([
            f"  {h['ticker']} ({h['asset_type']}): qty={h['quantity']}, "
            f"avg_buy=${h['avg_buy_price']}, current=${h['current_price']}, "
            f"value=${h['current_value']:,.2f}, P&L=${h['unrealized_pl']:,.2f} ({h['unrealized_pl_pct']}%)"
            for h in holdings if h["asset_type"] != "cash"
        ]) or "  None"

        loans_text = "\n".join([
            f"  {l['loan_type']}: ${l['outstanding_balance']:,.2f} @ {l['interest_rate_pct']}% — EMI ${l['emi_monthly']:,.2f} ({l['status']})"
            for l in loans
        ]) or "  None"

        alerts_text = "\n".join([
            f"  [{a['severity'].upper()}] {a['alert_type']}: {a['description'][:80]}"
            for a in alerts
        ]) or "  None"

        context = f"""CLIENT: {summary['first_name']} {summary['last_name']} ({customer_id}) | {summary['risk_profile']} risk | {summary['advisor_tier']} tier | {datetime.utcnow().strftime('%B %d, %Y')}

PORTFOLIO: Value=${summary['portfolio_value']:,.2f} | Net Worth=${summary['net_worth']:,.2f} | Cash=${summary['cash_balance']:,.2f} | Net P&L=${summary['net_pl']:,.2f}
Allocation: Stocks={summary['stock_pct']}% | Crypto={summary['crypto_pct']}% | ETFs={summary['etf_pct']}% | Cash={summary['cash_pct']}%
Returns: Annualized={summary['annualized_return_pct']}% vs S&P500={summary['sp500_return_pct']}%
Loans Outstanding: ${summary['loan_outstanding']:,.2f}

HOLDINGS:
{holdings_text}

LOANS:
{loans_text}

OPEN ALERTS:
{alerts_text}

Write a concise advisory report with EXACTLY these 6 sections (2-3 sentences each):
## 1. Executive Summary
## 2. Portfolio Performance
## 3. Risk Assessment (crypto limit: conservative=10%, moderate=25%, aggressive=50%)
## 4. Loan & Debt Summary
## 5. Recommendations (exactly 3 bullet points)
## 6. Risk Disclaimer (one sentence)

Total under 500 words. Complete every section."""

        client = _get_anthropic_client()
        if not client:
            return {
                "error": "Report generation unavailable — ANTHROPIC_API_KEY not configured.",
                "duration_ms": 0,
            }

        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1200,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": context}],
        )

        report_text = message.content[0].text
        ms = int((datetime.utcnow() - start).total_seconds() * 1000)
        tokens_used = message.usage.input_tokens + message.usage.output_tokens
        logger.info(f"Report agent: customer={customer_id} tokens={tokens_used} duration={ms}ms")

        return {
            "report_preview": report_text,
            "tokens_used": tokens_used,
            "duration_ms": ms,
        }

    except Exception as e:
        logger.error(f"Report agent error: customer={customer_id} error={e}")
        return {
            "error": "Report generation temporarily unavailable. Please try again.",
            "detail": str(e),
            "duration_ms": 0,
        }
