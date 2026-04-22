"""
Gap runner: fills Phase 1 minimum row counts.
Inserts additional transactions, loans, alerts, and reports.
"""
import psycopg2
import os

DB_URL = "postgresql://menouser:WEHealth123@wehealthdb.postgres.database.azure.com:5432/wealth_manage"
BASE = os.path.dirname(__file__)

def read_sql(filename):
    with open(os.path.join(BASE, filename)) as f:
        return f.read()

def run():
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = False
    cur = conn.cursor()

    print("Inserting gap transactions...")
    cur.execute(read_sql("gap_transactions.sql"))
    conn.commit()
    print("  Transactions done.")

    print("Inserting gap loans...")
    cur.execute(read_sql("gap_loans.sql"))
    conn.commit()
    print("  Loans done.")

    print("Inserting gap alerts...")
    cur.execute(read_sql("gap_alerts.sql"))
    conn.commit()
    print("  Alerts done.")

    print("Inserting gap reports...")
    cur.execute(read_sql("gap_reports.sql"))
    conn.commit()
    print("  Reports done.")

    print("Refreshing customer_summary via trigger...")
    cur.execute("UPDATE portfolio_holdings SET current_value = current_value WHERE asset_type != 'cash'")
    conn.commit()
    print("  customer_summary refreshed.")

    # Verification
    print("\n=== FINAL COUNTS ===")
    cur.execute("""
        SELECT 'transactions' as tbl, COUNT(*) FROM transactions
        UNION ALL SELECT 'loans', COUNT(*) FROM loans
        UNION ALL SELECT 'alerts', COUNT(*) FROM alerts
        UNION ALL SELECT 'reports', COUNT(*) FROM reports
        UNION ALL SELECT 'loans_overdue', COUNT(*) FROM loans WHERE status='overdue'
        UNION ALL SELECT 'txns_flagged', COUNT(*) FROM transactions WHERE flagged=TRUE
        ORDER BY tbl
    """)
    for row in cur.fetchall():
        print(f"  {row[0]:<20} {row[1]}")

    cur.close()
    conn.close()
    print("\nPhase 1 gap fill complete!")

if __name__ == "__main__":
    run()
