"""Audit all transactions for CUS-0001 and compute correct holdings."""
import os, psycopg2
conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()

cur.execute("""
    SELECT txn_id, ticker, txn_type, quantity, price_at_txn, total_value,
           txn_timestamp, flagged, geo_country
    FROM transactions
    WHERE customer_id = 'CUS-0001'
    ORDER BY txn_timestamp ASC
""")
txns = cur.fetchall()
print(f"Total transactions: {len(txns)}\n")
for t in txns:
    flag = " [FLAGGED]" if t[7] else ""
    print(f"  {str(t[6])[:19]}  {t[2].upper():<8} {t[1]:<8} "
          f"qty={float(t[3]):<12.4f} @${float(t[4]):<12.2f} "
          f"total=${float(t[5]):>14,.2f}  {t[0]}{flag}")

# Compute correct net positions from transaction history
positions = {}
for txn_id, ticker, txn_type, qty, price, total, ts, flagged, geo in txns:
    if ticker == "CASH":
        continue
    qty   = float(qty)
    price = float(price)
    if ticker not in positions:
        positions[ticker] = {"qty": 0.0, "total_cost": 0.0}
    if txn_type == "buy":
        positions[ticker]["qty"]        += qty
        positions[ticker]["total_cost"] += qty * price
    elif txn_type == "sell":
        if positions[ticker]["qty"] > 0:
            avg = positions[ticker]["total_cost"] / positions[ticker]["qty"]
            positions[ticker]["total_cost"] -= qty * avg
            positions[ticker]["qty"]        = max(0, positions[ticker]["qty"] - qty)

cur.execute("SELECT ticker, price_usd FROM market_prices")
prices = {r[0]: float(r[1]) for r in cur.fetchall()}

print("\n=== Net positions derived from ALL transactions ===")
for ticker in sorted(positions):
    pos = positions[ticker]
    if pos["qty"] > 0:
        avg    = pos["total_cost"] / pos["qty"]
        cp     = prices.get(ticker, avg)
        val    = pos["qty"] * cp
        pl     = pos["qty"] * (cp - avg)
        pl_pct = (cp - avg) / avg * 100
        print(f"  {ticker:<8}  qty={pos['qty']:<12.4f}  avg_buy=${avg:>10.4f}  "
              f"curr=${cp:>9.2f}  value=${val:>12,.2f}  pl_pct={pl_pct:>+8.2f}%")

print("\n=== Current portfolio_holdings in DB ===")
cur.execute("""
    SELECT ticker, quantity, avg_buy_price, current_price,
           current_value, unrealized_pl, unrealized_pl_pct
    FROM portfolio_holdings WHERE customer_id = 'CUS-0001'
    ORDER BY current_value DESC
""")
for r in cur.fetchall():
    print(f"  {r[0]:<8}  qty={float(r[1]):<10}  avg_buy=${float(r[2]):>9.4f}  "
          f"curr=${float(r[3]):>9.2f}  value=${float(r[4]):>12,.2f}  "
          f"pl_pct={float(r[6] or 0):>+8.2f}%")

conn.close()
