"""
Seed historical closed-position trades (buy then sell) for all 50 customers
covering 30-60 days ago.  The cash trigger fires on each INSERT, so cash
balances update automatically — no manual cash adjustment needed.

Each customer gets 2-4 trade pairs on their currently held tickers.
Mix of profitable and losing trades so cash balances shift realistically.
"""
import os, psycopg2, random, uuid
from datetime import datetime, timezone, timedelta
from collections import defaultdict

random.seed(42)   # reproducible

conn = psycopg2.connect(os.environ["DATABASE_URL"])
conn.autocommit = False
cur = conn.cursor()

# ── Load holdings ─────────────────────────────────────────────────────────────
cur.execute("""
    SELECT c.customer_id, c.risk_profile,
           ph.ticker, ph.asset_type, CAST(ph.current_price AS FLOAT)
    FROM customers c
    JOIN portfolio_holdings ph ON ph.customer_id = c.customer_id
    WHERE ph.asset_type != 'cash'
    ORDER BY c.customer_id, ph.current_value DESC
""")
holdings_by_cust = defaultdict(list)
risk_by_cust = {}
for cid, rp, ticker, atype, price in cur.fetchall():
    holdings_by_cust[cid].append((ticker, atype, price))
    risk_by_cust[cid] = rp

now = datetime.now(timezone.utc)

# ── How much to trade per asset type ─────────────────────────────────────────
def trade_quantity(ticker, asset_type, price):
    if asset_type == "crypto":
        if price > 10000:   # BTC
            return round(random.uniform(0.01, 0.05), 4)
        elif price > 1000:  # ETH, BNB
            return round(random.uniform(0.1, 0.8), 3)
        else:               # SOL, etc.
            return round(random.uniform(1, 10), 1)
    elif asset_type == "etf":
        return round(random.uniform(3, 20), 0)
    else:  # stock
        if price > 500:
            return round(random.uniform(1, 5), 0)
        elif price > 100:
            return round(random.uniform(2, 15), 0)
        else:
            return round(random.uniform(5, 30), 0)

# ── Profit/loss multipliers per risk profile ──────────────────────────────────
SELL_MULT = {
    "conservative": (0.94, 1.10),   # tight range
    "moderate":     (0.88, 1.18),
    "aggressive":   (0.80, 1.30),   # wide swings
}

# ── Force a realistic profit/loss mix: ~60% profitable ───────────────────────
def sell_multiplier(risk):
    lo, hi = SELL_MULT.get(risk, (0.88, 1.18))
    if random.random() < 0.60:
        # profitable trade
        return random.uniform(1.02, hi)
    else:
        # losing trade
        return random.uniform(lo, 0.98)

txn_rows = []

for cid, holdings in holdings_by_cust.items():
    risk = risk_by_cust[cid]
    n_pairs = random.randint(2, min(4, len(holdings)))
    chosen  = random.sample(holdings, n_pairs)

    for ticker, asset_type, curr_price in chosen:
        qty        = trade_quantity(ticker, asset_type, curr_price)
        # Historical buy price: current ±12%
        buy_price  = round(curr_price * random.uniform(0.88, 1.12), 2)
        buy_total  = round(qty * buy_price, 2)

        sell_mult  = sell_multiplier(risk)
        sell_price = round(buy_price * sell_mult, 2)
        sell_total = round(qty * sell_price, 2)
        realized   = round(sell_total - buy_total, 2)

        # Timestamps: buy 45-62 days ago, sell 18-40 days ago
        buy_days   = random.randint(45, 62)
        sell_days  = random.randint(18, 40)
        buy_ts     = now - timedelta(days=buy_days,  hours=random.randint(9, 16), minutes=random.randint(0,59))
        sell_ts    = now - timedelta(days=sell_days, hours=random.randint(9, 16), minutes=random.randint(0,59))

        buy_id  = f"TXN-{uuid.uuid4().hex[:8].upper()}"
        sell_id = f"TXN-{uuid.uuid4().hex[:8].upper()}"

        txn_rows.append((buy_id,  cid, ticker, "buy",  qty, buy_price,  buy_total,  0.0,      buy_ts))
        txn_rows.append((sell_id, cid, ticker, "sell", qty, sell_price, sell_total, realized, sell_ts))

# Sort chronologically so trigger sees buy before sell for each pair
txn_rows.sort(key=lambda r: r[8])

print(f"Inserting {len(txn_rows)} historical transactions ({len(txn_rows)//2} trade pairs)...")

for txn_id, cid, ticker, txn_type, qty, price, total, realized_pl, ts in txn_rows:
    cur.execute("""
        INSERT INTO transactions
            (txn_id, customer_id, ticker, txn_type, txn_category,
             quantity, price_at_txn, total_value, realized_pl,
             flagged, txn_timestamp, geo_country)
        VALUES (%s, %s, %s, %s, 'equity_trade',
                %s, %s, %s, %s,
                FALSE, %s, 'US')
    """, (txn_id, cid, ticker, txn_type, qty, price, total, realized_pl, ts))

conn.commit()
print("Committed.\n")

# ── Verify cash balances shifted ──────────────────────────────────────────────
cur.execute("""
    SELECT ph.customer_id,
           CAST(ph.current_value AS FLOAT) AS cash_now
    FROM portfolio_holdings ph
    WHERE ph.ticker = 'CASH'
    ORDER BY ph.customer_id
    LIMIT 10
""")
print(f"{'Customer':<12} {'Cash after'}")
print("-" * 30)
for cid, cash in cur.fetchall():
    print(f"{cid:<12} ${cash:>12,.2f}")

# ── Total realized P&L across all historical trades ───────────────────────────
cur.execute("""
    SELECT
        SUM(CASE WHEN realized_pl > 0 THEN realized_pl ELSE 0 END) AS total_gains,
        SUM(CASE WHEN realized_pl < 0 THEN realized_pl ELSE 0 END) AS total_losses,
        COUNT(*) FILTER (WHERE realized_pl > 0) AS profitable_trades,
        COUNT(*) FILTER (WHERE realized_pl < 0) AS losing_trades
    FROM transactions
    WHERE txn_type = 'sell' AND realized_pl IS NOT NULL
      AND txn_timestamp < NOW() - INTERVAL '17 days'
""")
r = cur.fetchone()
print(f"\nHistorical sell summary:")
print(f"  Profitable trades : {r[2]}  total gains  : ${float(r[0] or 0):>12,.2f}")
print(f"  Losing trades     : {r[3]}  total losses : ${float(r[1] or 0):>12,.2f}")
print(f"  Net realized P&L  : ${float((r[0] or 0) + (r[1] or 0)):>12,.2f}")

# ── Recent txn count still reasonable ────────────────────────────────────────
cur.execute("SELECT COUNT(*) FROM transactions WHERE txn_timestamp >= NOW() - INTERVAL '30 days'")
print(f"\nTransactions in last 30 days: {cur.fetchone()[0]}")
cur.execute("SELECT COUNT(*) FROM transactions")
print(f"Total transactions in DB    : {cur.fetchone()[0]}")

cur.close()
conn.close()
