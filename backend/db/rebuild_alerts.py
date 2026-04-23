"""
Delete all existing alerts and rebuild from real data only.

Three legitimate sources:
  1. Flagged transactions  — suspicious geo + large amount + odd hours
  2. Risk limit breaches   — crypto_pct currently exceeds profile limit
  3. Overdue loans         — loans.status = 'overdue'

No fabrication. Every alert row points back to a real transaction,
real portfolio state, or real loan record.
"""
import os, psycopg2
from datetime import timezone

conn = psycopg2.connect(os.environ["DATABASE_URL"])
conn.autocommit = False
cur = conn.cursor()

# ── 1. Wipe existing alerts ───────────────────────────────────────────────────
cur.execute("DELETE FROM alerts")
print(f"Deleted {cur.rowcount} existing alerts.")

alerts = []   # (alert_id, customer_id, txn_id, alert_type, severity, source, description, status, detected_at)
seq = 1

def aid():
    global seq
    v = f"ALT-{seq:04d}"
    seq += 1
    return v

# ── 2. Flagged transactions ───────────────────────────────────────────────────
HIGH_RISK_GEO = {"CN", "RU", "NG", "IR", "KP"}

cur.execute("""
    SELECT txn_id, customer_id, ticker, txn_type, total_value,
           geo_country, txn_timestamp
    FROM transactions
    WHERE flagged = TRUE
    ORDER BY txn_timestamp DESC
""")
for txn_id, cid, ticker, typ, amount, geo, ts in cur.fetchall():
    amount = float(amount)
    hour   = ts.astimezone(timezone.utc).hour

    # All 8 are high-risk geo + >$50k + between midnight and 6am → CRITICAL
    if geo in HIGH_RISK_GEO and amount > 50000 and hour < 6:
        severity = "critical"
    elif geo in HIGH_RISK_GEO and amount > 20000:
        severity = "high"
    else:
        severity = "medium"

    desc = (
        f"{typ.upper()} {ticker} ${amount:,.0f} from {geo} "
        f"at {ts.strftime('%H:%M')} UTC — flagged by fraud model"
    )
    alerts.append((aid(), cid, txn_id, "suspicious_activity", severity,
                   "ml_model", desc, "open", ts))
    print(f"  FLAGGED  {cid} {txn_id}  {severity:<8}  {desc[:70]}")

# ── 3. Current risk-limit breaches ───────────────────────────────────────────
CRYPTO_LIMITS = {"conservative": 10.0, "moderate": 25.0, "aggressive": 50.0}

cur.execute("""
    SELECT c.customer_id, c.first_name, c.risk_profile,
           cs.crypto_pct, NOW()
    FROM customers c
    JOIN customer_summary cs ON cs.customer_id = c.customer_id
    WHERE
        (c.risk_profile = 'conservative' AND cs.crypto_pct > 10) OR
        (c.risk_profile = 'moderate'     AND cs.crypto_pct > 25) OR
        (c.risk_profile = 'aggressive'   AND cs.crypto_pct > 50)
    ORDER BY c.customer_id
""")
for cid, fname, profile, crypto_pct, now in cur.fetchall():
    limit    = CRYPTO_LIMITS[profile]
    pct      = float(crypto_pct)
    overage  = pct - limit

    if overage > 30:
        severity = "high"
    elif overage > 10:
        severity = "medium"
    else:
        severity = "low"

    desc = (
        f"Crypto allocation {pct:.1f}% exceeds {profile} profile "
        f"limit of {limit:.0f}% (over by {overage:.1f}%)"
    )
    alerts.append((aid(), cid, None, "risk_breach", severity,
                   "rule", desc, "open", now))
    print(f"  RISK     {cid}  {severity:<8}  {desc}")

# ── 4. Overdue loans ─────────────────────────────────────────────────────────
cur.execute("""
    SELECT loan_id, customer_id, loan_type, outstanding_balance,
           next_due_date, NOW()
    FROM loans
    WHERE status = 'overdue'
    ORDER BY customer_id
""")
for loan_id, cid, ltype, balance, due_date, now in cur.fetchall():
    balance = float(balance)
    desc = (
        f"{ltype.capitalize()} loan ${balance:,.0f} overdue "
        f"(due {due_date.strftime('%Y-%m-%d') if due_date else 'N/A'})"
    )
    alerts.append((aid(), cid, None, "loan_overdue", "high",
                   "rule", desc, "open", now))
    print(f"  LOAN     {cid}  high      {desc}")

# ── 5. Insert all alerts ──────────────────────────────────────────────────────
print(f"\nInserting {len(alerts)} alerts...")
for row in alerts:
    cur.execute("""
        INSERT INTO alerts
            (alert_id, customer_id, txn_id, alert_type, severity,
             source, description, status, email_sent, detected_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, FALSE, %s)
    """, row)

conn.commit()
print("Committed.\n")

# ── Verification ──────────────────────────────────────────────────────────────
cur.execute("SELECT COUNT(*) FROM alerts")
print(f"Total alerts now         : {cur.fetchone()[0]}")

cur.execute("SELECT severity, COUNT(*) FROM alerts GROUP BY severity ORDER BY severity")
print("By severity:")
for r in cur.fetchall(): print(f"  {r[0]:<10} {r[1]}")

cur.execute("SELECT alert_type, COUNT(*) FROM alerts GROUP BY alert_type ORDER BY alert_type")
print("By type:")
for r in cur.fetchall(): print(f"  {r[0]:<25} {r[1]}")

cur.execute("""
    SELECT COUNT(*) FROM alerts WHERE status = 'open'
""")
print(f"Open alerts              : {cur.fetchone()[0]}")

cur.close()
conn.close()
