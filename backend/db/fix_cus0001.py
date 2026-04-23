"""
Restore CUS-0001 (Arjun Mehta) holdings to correct state.

Problem:
  9 garbage transactions were inserted today (2026-04-22) with
  nonsensical values (4,444 AAPL @ $4,444, flagged buys, GOOGL out of
  thin air, etc.).  These corrupt the net position computation and one
  of them has flagged=TRUE which would fire fraud alerts.

Fix:
  1. Delete the 9 bogus transactions.
  2. Recompute portfolio_holdings from the 11 legitimate transactions.
  3. Trigger customer_summary refresh by touching market_prices so the
     existing DB trigger cascade re-calculates everything cleanly.
"""
import os, psycopg2
from decimal import Decimal

DATABASE_URL = os.environ["DATABASE_URL"]
conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = False
cur = conn.cursor()

BOGUS_TXNS = [
    "TXN-64496F45",   # AAPL buy 345 @ $456     (garbage quantity/price)
    "TXN-D1189BDB",   # AAPL buy 4,444 @ $4,444  (obviously fabricated)
    "TXN-7EAE633D",   # AAPL buy 345 @ $345      (flagged=TRUE)
    "TXN-2E00B03C",   # AAPL buy 30  @ $45       (price way off market)
    "TXN-FA421AD6",   # AAPL sell 455 @ $100     (below-market disposal)
    "TXN-F683A975",   # AAPL buy 110 @ $289
    "TXN-CFCF8CE6",   # GOOGL buy 450 @ $337.67  (CUS-0001 never held GOOGL)
    "TXN-21F926C0",   # NVDA buy 1   @ $201.67
    "TXN-F5596374",   # BTC  buy 1   @ $79,279.61
]

print("Step 1 — removing alerts linked to garbage transactions...")
cur.execute(
    "DELETE FROM alerts WHERE txn_id = ANY(%s) AND customer_id = 'CUS-0001'",
    (BOGUS_TXNS,)
)
print(f"  deleted {cur.rowcount} linked alert(s)")

print("\nStep 1b — deleting garbage transactions...")
for txn_id in BOGUS_TXNS:
    cur.execute(
        "DELETE FROM transactions WHERE txn_id = %s AND customer_id = 'CUS-0001'",
        (txn_id,)
    )
    print(f"  deleted {txn_id}: {cur.rowcount} row(s)")

# Fetch current market prices
cur.execute("SELECT ticker, price_usd FROM market_prices")
prices = {r[0]: float(r[1]) for r in cur.fetchall()}

# Correct holdings derived from the 11 legitimate transactions
# NVDA: weighted avg from 100@421.50 + 20@650 = 55,150 / 120 = 459.5833
nvda_avg  = round((100 * 421.50 + 20 * 650.00) / 120, 4)   # 459.5833
aapl_avg  = 185.00    # single buy 25 @ 185
msft_avg  = 310.00    # single buy 50 @ 310
btc_avg   = 38200.00  # single buy 0.85 @ 38200
vtsax_avg = 98.40     # buy 310, then sell 50 — avg_buy unchanged

CORRECT_HOLDINGS = [
    # (ticker, asset_type, qty, avg_buy)
    ("BTC",   "crypto", 0.85,  btc_avg),
    ("VTSAX", "etf",    260.0, vtsax_avg),
    ("NVDA",  "stock",  120.0, nvda_avg),
    ("MSFT",  "stock",  50.0,  msft_avg),
    ("AAPL",  "stock",  25.0,  aapl_avg),
    ("CASH",  "cash",   1.0,   18500.00),
]

print("\nStep 2 — fetching existing holding_ids for CUS-0001...")
cur.execute("""
    SELECT holding_id, ticker FROM portfolio_holdings WHERE customer_id = 'CUS-0001'
""")
existing = {r[1]: r[0] for r in cur.fetchall()}
print(f"  existing rows: {dict(existing)}")

# Fixed holding_ids from the original seed
HOLDING_IDS = {
    "CASH":  "HOL-0001",
    "NVDA":  "HOL-0002",
    "BTC":   "HOL-0003",
    "VTSAX": "HOL-0004",
    "MSFT":  "HOL-0005",
    "AAPL":  existing.get("AAPL", "HOL-0005A"),  # may already exist
}

print("\nStep 2b — deleting and reinserting correct portfolio_holdings...")
for ticker, asset_type, qty, avg_buy in CORRECT_HOLDINGS:
    cp     = prices.get(ticker, avg_buy)
    val    = round(qty * cp, 2)
    pl     = round(qty * (cp - avg_buy), 2)
    pl_pct = round((cp - avg_buy) / avg_buy * 100, 2) if avg_buy > 0 else 0.0
    hid    = HOLDING_IDS.get(ticker, f"HOL-C1-{ticker[:4]}")

    # Delete existing row if any (by holding_id OR by customer+ticker)
    cur.execute(
        "DELETE FROM portfolio_holdings WHERE customer_id = 'CUS-0001' AND ticker = %s",
        (ticker,)
    )
    cur.execute("""
        INSERT INTO portfolio_holdings
            (holding_id, customer_id, ticker, asset_type, quantity, avg_buy_price,
             current_price, current_value, unrealized_pl, unrealized_pl_pct,
             last_updated)
        VALUES (%s, 'CUS-0001', %s, %s, %s, %s, %s, %s, %s, %s, NOW())
    """, (hid, ticker, asset_type, qty, avg_buy, cp, val, pl, pl_pct))
    print(f"  INSERT {ticker:<8} qty={qty:<8} avg=${avg_buy:<9.2f} "
          f"curr=${cp:<9.2f} value=${val:>10,.2f} pl={pl_pct:>+7.2f}%")

print("\nStep 3 — triggering customer_summary refresh via market_prices touch...")
cur.execute("""
    UPDATE market_prices
    SET last_updated = NOW()
    WHERE ticker IN ('AAPL','NVDA','BTC','MSFT','VTSAX')
""")
print(f"  touched {cur.rowcount} market_prices rows — trigger cascade will recalculate summary")

conn.commit()
print("\nAll done. Verifying final state...\n")

# Verification
cur.execute("""
    SELECT ticker, quantity, avg_buy_price, current_price,
           current_value, unrealized_pl, unrealized_pl_pct
    FROM portfolio_holdings
    WHERE customer_id = 'CUS-0001'
    ORDER BY current_value DESC
""")
print("portfolio_holdings:")
total_val = 0.0
for r in cur.fetchall():
    val = float(r[4])
    total_val += val
    print(f"  {r[0]:<8}  qty={float(r[1]):<10.4f}  avg_buy=${float(r[2]):>9.2f}  "
          f"curr=${float(r[3]):>9.2f}  value=${val:>10,.2f}  "
          f"pl_pct={float(r[6] or 0):>+8.2f}%")
print(f"  {'TOTAL':<8}  {'':10}  {'':>9}  {'':>9}  value=${total_val:>10,.2f}")

cur.execute("""
    SELECT COUNT(*) FROM transactions
    WHERE customer_id = 'CUS-0001'
      AND txn_id IN %s
""", (tuple(BOGUS_TXNS),))
remaining = cur.fetchone()[0]
print(f"\nbogus transactions remaining: {remaining} (should be 0)")

cur.execute("SELECT COUNT(*) FROM transactions WHERE customer_id = 'CUS-0001'")
print(f"total legitimate transactions: {cur.fetchone()[0]}")

cur.execute("""
    SELECT portfolio_value, net_worth, cash_balance,
           stock_pct, crypto_pct, etf_pct, cash_pct
    FROM customer_summary WHERE customer_id = 'CUS-0001'
""")
s = cur.fetchone()
print(f"\ncustomer_summary (may lag until trigger fires):")
print(f"  portfolio_value=${float(s[0] or 0):,.2f}  net_worth=${float(s[1] or 0):,.2f}")
print(f"  alloc: stock={s[2]}%  crypto={s[3]}%  etf={s[4]}%  cash={s[5]}%")

cur.close()
conn.close()
