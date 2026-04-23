"""
Audit: find transactions in the last 30 days whose ticker is not in
the customer's current portfolio_holdings.  Report only — no changes.
"""
import os, psycopg2
conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()

# Held tickers per customer (excluding CASH — cash is never a transaction ticker)
cur.execute("""
    SELECT customer_id, array_agg(ticker) AS held
    FROM portfolio_holdings
    WHERE asset_type != 'cash'
    GROUP BY customer_id
    ORDER BY customer_id
""")
holdings_map = {r[0]: set(r[1]) for r in cur.fetchall()}

# Recent transactions (last 30 days) that don't match any held ticker
cur.execute("""
    SELECT t.txn_id, t.customer_id, t.ticker, t.txn_type,
           t.quantity, t.total_value, t.txn_timestamp, t.flagged
    FROM transactions t
    WHERE t.txn_timestamp >= NOW() - INTERVAL '30 days'
      AND t.ticker != 'CASH'
    ORDER BY t.customer_id, t.txn_timestamp
""")
rows = cur.fetchall()

mismatch_ids = []
mismatch_by_cust = {}

for txn_id, cid, ticker, typ, qty, val, ts, flagged in rows:
    held = holdings_map.get(cid, set())
    if ticker not in held:
        mismatch_ids.append(txn_id)
        mismatch_by_cust.setdefault(cid, []).append(
            (txn_id, ticker, typ, float(qty), float(val), flagged)
        )

print(f"Total recent transactions checked : {len(rows)}")
print(f"Transactions to remove            : {len(mismatch_ids)}")
print(f"Customers affected                : {len(mismatch_by_cust)}")
print()

flagged_count = sum(1 for txn_id, ticker, typ, qty, val, f in
                    [item for sub in mismatch_by_cust.values() for item in sub] if f)
print(f"Flagged transactions in that set  : {flagged_count}")
print()

# Show per-customer breakdown (top 10 most affected)
sorted_custs = sorted(mismatch_by_cust.items(), key=lambda x: len(x[1]), reverse=True)
print(f"{'Customer':<12} {'Held tickers':<40} {'Orphan txns'}")
print("-" * 75)
for cid, items in sorted_custs[:15]:
    held_str = ",".join(sorted(holdings_map.get(cid, set())))
    orphan_tickers = sorted(set(t[1] for t in items))
    print(f"{cid:<12} {held_str:<40} {len(items):>3}  {orphan_tickers}")

conn.close()
