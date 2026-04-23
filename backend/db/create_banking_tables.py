"""Create bank_accounts, bank_transactions, spending_summary tables."""
import os
import psycopg2
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(), override=True)
DB_URL = os.getenv("DATABASE_URL")

DDL = """
CREATE TABLE IF NOT EXISTS bank_accounts (
    account_id      VARCHAR(12) PRIMARY KEY,
    customer_id     VARCHAR(10) NOT NULL REFERENCES customers(customer_id),
    bank_name       VARCHAR(50) NOT NULL,
    account_type    VARCHAR(20) NOT NULL
                    CHECK (account_type IN ('checking','savings','credit_card','mortgage','investment')),
    account_number  VARCHAR(20) NOT NULL,
    balance         NUMERIC(15,2) NOT NULL DEFAULT 0,
    interest_rate   NUMERIC(6,2),
    currency        CHAR(3) DEFAULT 'USD',
    is_active       BOOLEAN DEFAULT TRUE,
    linked_at       TIMESTAMPTZ DEFAULT NOW(),
    last_synced     TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS bank_transactions (
    txn_id          VARCHAR(16) PRIMARY KEY,
    account_id      VARCHAR(12) REFERENCES bank_accounts(account_id),
    customer_id     VARCHAR(10) REFERENCES customers(customer_id),
    txn_date        DATE NOT NULL,
    description     VARCHAR(200) NOT NULL,
    category        VARCHAR(30) NOT NULL
                    CHECK (category IN (
                        'groceries','dining','transport','utilities','entertainment',
                        'healthcare','shopping','travel','salary','investment',
                        'interest_earned','interest_paid','rent','insurance',
                        'subscription','transfer','other'
                    )),
    amount          NUMERIC(12,2) NOT NULL,
    txn_direction   VARCHAR(10) NOT NULL CHECK (txn_direction IN ('credit','debit')),
    balance_after   NUMERIC(15,2),
    merchant        VARCHAR(100),
    location        VARCHAR(100),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bank_txn_customer  ON bank_transactions(customer_id);
CREATE INDEX IF NOT EXISTS idx_bank_txn_date      ON bank_transactions(txn_date);
CREATE INDEX IF NOT EXISTS idx_bank_txn_category  ON bank_transactions(category);

CREATE TABLE IF NOT EXISTS spending_summary (
    customer_id     VARCHAR(10) REFERENCES customers(customer_id),
    period          VARCHAR(7) NOT NULL,
    category        VARCHAR(30) NOT NULL,
    total_spent     NUMERIC(12,2) DEFAULT 0,
    total_earned    NUMERIC(12,2) DEFAULT 0,
    txn_count       INTEGER DEFAULT 0,
    avg_txn_amount  NUMERIC(10,2) DEFAULT 0,
    PRIMARY KEY (customer_id, period, category)
);
"""

conn = psycopg2.connect(DB_URL)
cur = conn.cursor()
cur.execute(DDL)
conn.commit()
print("Tables created: bank_accounts, bank_transactions, spending_summary")
cur.close()
conn.close()
