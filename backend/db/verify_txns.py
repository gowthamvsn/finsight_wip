import os, psycopg2
conn = psycopg2.connect(os.environ["DATABASE_URL"])
cur = conn.cursor()

cur.execute("""
    SELECT
        COUNT(*)                                                       AS total_txns,
        COUNT(DISTINCT customer_id)                                    AS customers_with_txns,
        SUM(CASE WHEN txn_type='buy'  THEN total_value ELSE 0 END)    AS buy_volume,
        SUM(CASE WHEN txn_type='sell' THEN total_value ELSE 0 END)    AS sell_volume,
        SUM(CASE WHEN flagged=TRUE    THEN 1           ELSE 0 END)    AS flagged_count,
        MIN(txn_timestamp)                                             AS earliest,
        MAX(txn_timestamp)                                             AS latest
    FROM transactions
    WHERE txn_timestamp >= NOW() - INTERVAL '30 days'
""")
r = cur.fetchone()
print("total_txns           :", r[0])
print("customers_with_txns  :", r[1])
print("buy_volume           :", r[2])
print("sell_volume          :", r[3])
print("flagged_count        :", r[4])
print("earliest             :", r[5])
print("latest               :", r[6])

print()
cur.execute("""
    SELECT customer_id,
           COUNT(*)                                                       AS txn_count,
           SUM(CASE WHEN txn_type='buy'  THEN total_value ELSE 0 END)    AS buy_vol,
           SUM(CASE WHEN txn_type='sell' THEN total_value ELSE 0 END)    AS sell_vol
    FROM transactions
    WHERE txn_timestamp >= NOW() - INTERVAL '30 days'
    GROUP BY customer_id
    ORDER BY buy_vol DESC
    LIMIT 10
""")
print("customer_id    txn_count   buy_vol        sell_vol")
for row in cur.fetchall():
    print(f"{row[0]:<14} {row[1]:>9}   {float(row[2] or 0):>12,.2f}   {float(row[3] or 0):>12,.2f}")

cur.close()
conn.close()
