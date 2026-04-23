"""
Fix: delete recent transactions whose ticker is not in the customer's
current portfolio_holdings.  Handles FK constraint on alerts.txn_id.
"""
import os, psycopg2

conn = psycopg2.connect(os.environ["DATABASE_URL"])
conn.autocommit = False
cur = conn.cursor()

# Step 1 — build held-ticker map per customer (cash excluded)
cur.execute("""
    SELECT customer_id, array_agg(ticker) AS held
    FROM portfolio_holdings
    WHERE asset_type != 'cash'
    GROUP BY customer_id
""")
holdings_map = {r[0]: set(r[1]) for r in cur.fetchall()}

# Step 2 — collect all orphan txn_ids from the last 30 days
cur.execute("""
    SELECT t.txn_id, t.customer_id, t.ticker
    FROM transactions t
    WHERE t.txn_timestamp >= NOW() - INTERVAL '30 days'
      AND t.ticker != 'CASH'
    ORDER BY t.customer_id, t.txn_timestamp
""")
rows = cur.fetchall()

orphan_ids = [
    txn_id
    for txn_id, cid, ticker in rows
    if ticker not in holdings_map.get(cid, set())
]

print(f"Total recent non-CASH transactions : {len(rows)}")
print(f"Orphan transactions to delete      : {len(orphan_ids)}")

if not orphan_ids:
    print("Nothing to do.")
    conn.close()
    exit(0)

# Step 3 — delete linked alerts first (FK constraint)
cur.execute("DELETE FROM alerts WHERE txn_id = ANY(%s)", (orphan_ids,))
alerts_deleted = cur.rowcount
print(f"Linked alerts deleted              : {alerts_deleted}")

# Step 4 — delete the orphan transactions
cur.execute("DELETE FROM transactions WHERE txn_id = ANY(%s)", (orphan_ids,))
txns_deleted = cur.rowcount
print(f"Orphan transactions deleted        : {txns_deleted}")

conn.commit()
print("\nCommitted.\n")

# Verification
cur.execute("""
    SELECT COUNT(*) FROM transactions
    WHERE txn_timestamp >= NOW() - INTERVAL '30 days'
      AND ticker != 'CASH'
""")
remaining = cur.fetchone()[0]
print(f"Remaining recent non-CASH transactions: {remaining}")

cur.execute("SELECT COUNT(*) FROM transactions")
total = cur.fetchone()[0]
print(f"Total transactions in DB              : {total}")

# Sanity-check: any orphans still remaining?
cur.execute("""
    SELECT t.txn_id, t.customer_id, t.ticker
    FROM transactions t
    WHERE t.txn_timestamp >= NOW() - INTERVAL '30 days'
      AND t.ticker != 'CASH'
      AND NOT EXISTS (
          SELECT 1 FROM portfolio_holdings ph
          WHERE ph.customer_id = t.customer_id
            AND ph.ticker = t.ticker
      )
""")
leftover = cur.fetchall()
print(f"Orphan transactions remaining (should be 0): {len(leftover)}")
if leftover:
    for row in leftover[:10]:
        print(f"  {row}")

# Buy/sell volume per customer check (top 10)
cur.execute("""
    SELECT customer_id,
           SUM(CASE WHEN txn_type='buy'  THEN 1 ELSE 0 END) AS buys,
           SUM(CASE WHEN txn_type='sell' THEN 1 ELSE 0 END) AS sells,
           COUNT(*) AS total
    FROM transactions
    WHERE txn_timestamp >= NOW() - INTERVAL '30 days'
      AND ticker != 'CASH'
    GROUP BY customer_id
    ORDER BY total DESC
    LIMIT 10
""")
print("\nTop 10 customers by recent transaction count (post-cleanup):")
print(f"{'Customer':<12} {'Buys':>6} {'Sells':>6} {'Total':>6}")
print("-" * 32)
for cid, buys, sells, total in cur.fetchall():
    print(f"{cid:<12} {buys:>6} {sells:>6} {total:>6}")

cur.close()
conn.close()
