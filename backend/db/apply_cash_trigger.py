"""
Create DB trigger that keeps the CASH holding in sync with every
buy/sell transaction.  Safe to re-run (uses CREATE OR REPLACE + DROP IF EXISTS).
"""
import os, psycopg2

conn = psycopg2.connect(os.environ["DATABASE_URL"])
conn.autocommit = True
cur = conn.cursor()

# ── Trigger function ──────────────────────────────────────────────────────────
cur.execute("""
CREATE OR REPLACE FUNCTION fn_update_cash_on_txn()
RETURNS TRIGGER AS $$
DECLARE
    v_avg_buy  NUMERIC;
    v_realized NUMERIC;
BEGIN
    -- Skip CASH ticker and transfers
    IF NEW.ticker = 'CASH' OR NEW.txn_type NOT IN ('buy', 'sell') THEN
        RETURN NEW;
    END IF;

    IF NEW.txn_type = 'buy' THEN
        -- Deduct purchase cost from cash balance
        UPDATE portfolio_holdings
        SET current_price = current_price - NEW.total_value,
            avg_buy_price = avg_buy_price - NEW.total_value,
            current_value = current_value - NEW.total_value,
            last_updated  = NOW()
        WHERE customer_id = NEW.customer_id AND ticker = 'CASH';

    ELSIF NEW.txn_type = 'sell' THEN
        -- Add sale proceeds to cash balance
        UPDATE portfolio_holdings
        SET current_price = current_price + NEW.total_value,
            avg_buy_price = avg_buy_price + NEW.total_value,
            current_value = current_value + NEW.total_value,
            last_updated  = NOW()
        WHERE customer_id = NEW.customer_id AND ticker = 'CASH';

        -- Backfill realized_pl on the transaction row if not already set
        -- (avg_buy_price BEFORE this insert is used; read it first)
        SELECT avg_buy_price INTO v_avg_buy
        FROM portfolio_holdings
        WHERE customer_id = NEW.customer_id AND ticker = NEW.ticker;

        IF v_avg_buy IS NOT NULL AND v_avg_buy > 0 THEN
            v_realized := ROUND((NEW.price_at_txn - v_avg_buy) * NEW.quantity, 2);
            UPDATE transactions
            SET realized_pl = v_realized
            WHERE txn_id = NEW.txn_id;
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
""")
print("fn_update_cash_on_txn created.")

# ── Trigger ───────────────────────────────────────────────────────────────────
cur.execute("DROP TRIGGER IF EXISTS trg_cash_on_txn ON transactions;")
cur.execute("""
CREATE TRIGGER trg_cash_on_txn
AFTER INSERT ON transactions
FOR EACH ROW
EXECUTE FUNCTION fn_update_cash_on_txn();
""")
print("trg_cash_on_txn created on transactions.")

# Verify
cur.execute("""
    SELECT trigger_name, event_manipulation, action_timing
    FROM information_schema.triggers
    WHERE event_object_table = 'transactions'
""")
for r in cur.fetchall():
    print(f"  trigger: {r}")

cur.close()
conn.close()
print("Done.")
