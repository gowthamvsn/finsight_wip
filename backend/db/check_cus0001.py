import os, psycopg2
conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()

print("=== portfolio_holdings for CUS-0001 ===")
cur.execute("""
    SELECT ticker, asset_type, quantity, avg_buy_price,
           current_price, current_value, unrealized_pl, unrealized_pl_pct
    FROM portfolio_holdings
    WHERE customer_id = 'CUS-0001'
    ORDER BY current_value DESC
""")
rows = cur.fetchall()
print(f"rows found: {len(rows)}")
for r in rows:
    print(f"  {r}")

print()
print("=== customer_summary for CUS-0001 ===")
cur.execute("""
    SELECT portfolio_value, net_worth, cash_balance,
           unrealized_pl, crypto_pct, stock_pct, etf_pct, cash_pct
    FROM customer_summary WHERE customer_id = 'CUS-0001'
""")
r = cur.fetchone()
print(f"  {r}")

print()
print("=== transactions for CUS-0001 (first 10) ===")
cur.execute("""
    SELECT ticker, txn_type, quantity, price_at_txn, total_value, txn_timestamp
    FROM transactions
    WHERE customer_id = 'CUS-0001'
    ORDER BY txn_timestamp
    LIMIT 10
""")
for r in cur.fetchall():
    print(f"  {r}")

print()
print("=== current market prices ===")
cur.execute("SELECT ticker, price_usd FROM market_prices ORDER BY ticker")
for r in cur.fetchall():
    print(f"  {r[0]:<8} ${float(r[1]):>10.2f}")

conn.close()
