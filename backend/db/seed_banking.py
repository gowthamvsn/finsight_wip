"""
Seed realistic bank accounts and 90 days of transactions for all 50 customers.
Patterns match customer risk profile and advisor tier.
"""
import os, random, uuid
from datetime import date, timedelta
from decimal import Decimal

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(), override=True)
DB_URL = os.getenv("DATABASE_URL")

random.seed(42)

# ── helpers ──────────────────────────────────────────────────────────────────

def acc_id(n):
    return f"ACC-{n:07d}"

def txn_id():
    return "BTX-" + uuid.uuid4().hex[:12].upper()

def masked(last4):
    return f"****{last4}"

GROCERY_MERCHANTS  = ["Whole Foods", "HEB", "Kroger", "Trader Joe's", "Walmart Grocery"]
DINING_MERCHANTS   = ["Chipotle", "Chili's", "Olive Garden", "Local Bistro", "Starbucks", "Subway", "Panda Express"]
TRANSPORT_MERCHANTS= ["Uber", "Shell Gas", "BP Gas", "City Parking", "Lyft", "EZ Tag Toll"]
UTILITY_MERCHANTS  = ["AT&T", "TXU Energy", "Spectrum", "T-Mobile", "Google Fi"]
ENTERTAINMENT_MERCH= ["Netflix", "AMC Theatres", "Spotify", "Hulu", "Disney+"]
HEALTH_MERCHANTS   = ["CVS Pharmacy", "Walgreens", "Dr. Patel Office", "LabCorp", "Urgent Care"]
SHOPPING_MERCHANTS = ["Amazon", "Target", "Best Buy", "Macy's", "H&M"]
TRAVEL_MERCHANTS   = ["Delta Airlines", "Marriott Hotels", "Airbnb", "United Airlines", "Expedia"]
INSURANCE_MERCHANTS= ["State Farm", "Geico", "Allstate", "Progressive"]
SUBS_MERCHANTS     = ["Adobe Creative", "Microsoft 365", "Apple iCloud", "Dropbox", "LinkedIn Premium"]

# salary ranges by tier
SALARY_BY_TIER = {
    "standard": (5000, 7000),
    "premium":  (7000, 12000),
    "elite":    (12000, 20000),
}

# spending scale by profile
SPEND_SCALE = {
    "conservative": 0.75,
    "moderate":     1.0,
    "aggressive":   1.35,
}

def rand_amount(lo, hi, scale=1.0):
    return round(random.uniform(lo * scale, hi * scale), 2)

def generate_accounts(customer_id, risk_profile, idx):
    accounts = []
    base = idx * 3 + 1
    # always: checking + savings
    accounts.append({
        "account_id":    acc_id(base),
        "customer_id":   customer_id,
        "bank_name":     "Chase",
        "account_type":  "checking",
        "account_number": masked(str(random.randint(1000, 9999))),
        "balance":       round(random.uniform(2000, 15000), 2),
        "interest_rate": None,
    })
    accounts.append({
        "account_id":    acc_id(base + 1),
        "customer_id":   customer_id,
        "bank_name":     "Chase",
        "account_type":  "savings",
        "account_number": masked(str(random.randint(1000, 9999))),
        "balance":       round(random.uniform(5000, 50000), 2),
        "interest_rate": 4.50,
    })
    # moderate & aggressive get a credit card
    if risk_profile in ("moderate", "aggressive"):
        accounts.append({
            "account_id":    acc_id(base + 2),
            "customer_id":   customer_id,
            "bank_name":     "Citi",
            "account_type":  "credit_card",
            "account_number": masked(str(random.randint(1000, 9999))),
            "balance":       round(random.uniform(-3000, -200), 2),
            "interest_rate": 19.99,
        })
    return accounts

def generate_transactions(customer_id, accounts, risk_profile, tier, today):
    """Generate ~90 days of bank transactions."""
    checking = accounts[0]
    savings  = accounts[1]
    has_cc   = len(accounts) > 2

    scale = SPEND_SCALE[risk_profile]
    sal_lo, sal_hi = SALARY_BY_TIER[tier]
    half_salary = round(random.uniform(sal_lo, sal_hi) / 2, 2)

    txns = []

    def add(acc_id, d, desc, cat, amount, direction, merchant=None, location=None):
        txns.append({
            "txn_id":       txn_id(),
            "account_id":   acc_id,
            "customer_id":  customer_id,
            "txn_date":     d,
            "description":  desc,
            "category":     cat,
            "amount":       amount,
            "txn_direction": direction,
            "merchant":     merchant,
            "location":     "Austin, TX",
        })

    start = today - timedelta(days=89)
    d = start
    while d <= today:
        day = d.day
        dow = d.weekday()  # 0=Mon … 6=Sun

        # ── SALARY: 1st and 15th ────────────────────────────────────────────
        if day in (1, 15):
            add(checking["account_id"], d,
                f"Payroll Direct Deposit", "salary",
                half_salary, "credit", "Employer Payroll")

        # ── RENT: 1st of month ──────────────────────────────────────────────
        if day == 1:
            rent = rand_amount(1500, 4000, scale)
            add(checking["account_id"], d,
                "Monthly Rent Payment", "rent",
                rent, "debit", "Apartment Management", "Austin, TX")

        # ── UTILITIES: mid-month ────────────────────────────────────────────
        if day == 14:
            add(checking["account_id"], d,
                "Electric Bill", "utilities",
                rand_amount(80, 220, scale), "debit",
                random.choice(UTILITY_MERCHANTS))
            add(checking["account_id"], d,
                "Internet / Phone", "utilities",
                rand_amount(60, 120, scale), "debit",
                random.choice(UTILITY_MERCHANTS))

        # ── INSURANCE: 5th of month ─────────────────────────────────────────
        if day == 5:
            add(checking["account_id"], d,
                "Insurance Premium", "insurance",
                rand_amount(200, 450, scale), "debit",
                random.choice(INSURANCE_MERCHANTS))

        # ── SUBSCRIPTIONS: 8th ──────────────────────────────────────────────
        if day == 8:
            add(checking["account_id"], d,
                "Streaming / Software Subscription", "subscription",
                rand_amount(10, 50, 1.0), "debit",
                random.choice(SUBS_MERCHANTS))

        # ── INTEREST EARNED: last day of month ──────────────────────────────
        next_d = d + timedelta(days=1)
        if next_d.month != d.month:
            rate = float(savings.get("interest_rate") or 4.5) / 100 / 12
            interest = round(float(savings["balance"]) * rate, 2)
            add(savings["account_id"], d,
                "Monthly Interest Credit", "interest_earned",
                max(interest, 0.01), "credit", "Chase Bank")

        # ── GROCERIES: Mon & Thu ────────────────────────────────────────────
        if dow in (0, 3):
            add(checking["account_id"], d,
                "Grocery Shopping", "groceries",
                rand_amount(60, 180, scale), "debit",
                random.choice(GROCERY_MERCHANTS))

        # ── DINING: Tue, Wed, Fri, Sat ──────────────────────────────────────
        if dow in (1, 2, 4, 5) and random.random() < 0.7:
            add(checking["account_id"], d,
                "Restaurant / Dining", "dining",
                rand_amount(20, 75, scale), "debit",
                random.choice(DINING_MERCHANTS))

        # ── TRANSPORT: weekdays ─────────────────────────────────────────────
        if dow < 5 and random.random() < 0.4:
            add(checking["account_id"], d,
                "Transport", "transport",
                rand_amount(10, 60, scale), "debit",
                random.choice(TRANSPORT_MERCHANTS))

        # ── ENTERTAINMENT: weekends ──────────────────────────────────────────
        if dow >= 5 and random.random() < 0.5:
            add(checking["account_id"], d,
                "Entertainment", "entertainment",
                rand_amount(15, 90, scale), "debit",
                random.choice(ENTERTAINMENT_MERCH))

        # ── HEALTHCARE: occasional ───────────────────────────────────────────
        if random.random() < 0.04:
            add(checking["account_id"], d,
                "Healthcare / Pharmacy", "healthcare",
                rand_amount(30, 300, scale), "debit",
                random.choice(HEALTH_MERCHANTS))

        # ── SHOPPING: occasional ────────────────────────────────────────────
        if random.random() < 0.06:
            acc = accounts[2]["account_id"] if has_cc else checking["account_id"]
            add(acc, d,
                "Online / Retail Shopping", "shopping",
                rand_amount(40, 350, scale), "debit",
                random.choice(SHOPPING_MERCHANTS))

        # ── TRAVEL: ~once per quarter ───────────────────────────────────────
        if random.random() < 0.007:
            add(checking["account_id"], d,
                "Travel Booking", "travel",
                rand_amount(200, 1800, scale), "debit",
                random.choice(TRAVEL_MERCHANTS))

        # ── INVESTMENT DIVIDEND: aggressive customers ────────────────────────
        if risk_profile == "aggressive" and random.random() < 0.008:
            add(savings["account_id"], d,
                "Dividend Payment", "investment",
                rand_amount(50, 500, 1.0), "credit",
                "Brokerage Account")

        # ── CREDIT CARD INTEREST PAID: if has CC ────────────────────────────
        if has_cc and day == 20:
            cc_bal = abs(float(accounts[2]["balance"]))
            monthly_interest = round(cc_bal * 19.99 / 100 / 12, 2)
            if monthly_interest > 0:
                add(accounts[2]["account_id"], d,
                    "Credit Card Interest Charge", "interest_paid",
                    monthly_interest, "debit", "Citi Bank")

        d += timedelta(days=1)

    return txns


def main():
    conn = psycopg2.connect(DB_URL)
    cur  = conn.cursor()

    # wipe existing data
    cur.execute("DELETE FROM spending_summary")
    cur.execute("DELETE FROM bank_transactions")
    cur.execute("DELETE FROM bank_accounts")
    conn.commit()
    print("Cleared existing banking data.")

    cur.execute("""
        SELECT customer_id, risk_profile, advisor_tier
        FROM customers ORDER BY customer_id
    """)
    customers = cur.fetchall()

    today = date.today()
    all_accounts = []
    all_txns     = []

    for idx, (cid, risk, tier) in enumerate(customers):
        accs  = generate_accounts(cid, risk, idx)
        txns  = generate_transactions(cid, accs, risk, tier, today)
        all_accounts.extend(accs)
        all_txns.extend(txns)

    # insert accounts
    psycopg2.extras.execute_values(cur, """
        INSERT INTO bank_accounts
          (account_id, customer_id, bank_name, account_type,
           account_number, balance, interest_rate)
        VALUES %s ON CONFLICT DO NOTHING
    """, [(
        a["account_id"], a["customer_id"], a["bank_name"],
        a["account_type"], a["account_number"], a["balance"],
        a.get("interest_rate"),
    ) for a in all_accounts])
    print(f"Inserted {len(all_accounts)} bank accounts.")

    # insert transactions in batches of 500
    batch = 500
    total_inserted = 0
    for i in range(0, len(all_txns), batch):
        chunk = all_txns[i:i+batch]
        psycopg2.extras.execute_values(cur, """
            INSERT INTO bank_transactions
              (txn_id, account_id, customer_id, txn_date, description,
               category, amount, txn_direction, merchant, location)
            VALUES %s ON CONFLICT DO NOTHING
        """, [(
            t["txn_id"], t["account_id"], t["customer_id"],
            t["txn_date"], t["description"], t["category"],
            t["amount"], t["txn_direction"], t["merchant"], t["location"],
        ) for t in chunk])
        total_inserted += len(chunk)
    conn.commit()
    print(f"Inserted {total_inserted} bank transactions.")

    # rebuild spending_summary
    cur.execute("""
        INSERT INTO spending_summary
          (customer_id, period, category, total_spent, total_earned, txn_count, avg_txn_amount)
        SELECT
          customer_id,
          TO_CHAR(txn_date, 'YYYY-MM'),
          category,
          SUM(CASE WHEN txn_direction='debit'  THEN amount ELSE 0 END),
          SUM(CASE WHEN txn_direction='credit' THEN amount ELSE 0 END),
          COUNT(*),
          ROUND(AVG(amount)::NUMERIC, 2)
        FROM bank_transactions
        GROUP BY customer_id, TO_CHAR(txn_date, 'YYYY-MM'), category
        ON CONFLICT (customer_id, period, category) DO UPDATE SET
          total_spent    = EXCLUDED.total_spent,
          total_earned   = EXCLUDED.total_earned,
          txn_count      = EXCLUDED.txn_count,
          avg_txn_amount = EXCLUDED.avg_txn_amount
    """)
    conn.commit()
    print("spending_summary rebuilt.")

    # verify
    cur.execute("""
        SELECT COUNT(*) as bank_txns,
               COUNT(DISTINCT customer_id) as customers,
               SUM(CASE WHEN txn_direction='debit'  THEN amount ELSE 0 END) as total_spent,
               SUM(CASE WHEN txn_direction='credit' THEN amount ELSE 0 END) as total_earned
        FROM bank_transactions
    """)
    row = cur.fetchone()
    print(f"\nVerification:")
    print(f"  bank_txns : {row[0]}")
    print(f"  customers : {row[1]}")
    print(f"  total_spent : ${float(row[2]):,.0f}")
    print(f"  total_earned: ${float(row[3]):,.0f}")

    # top 5 spenders
    cur.execute("""
        SELECT c.first_name,
               COUNT(bt.txn_id) as txn_count,
               SUM(CASE WHEN bt.txn_direction='credit' THEN bt.amount ELSE 0 END) as income,
               SUM(CASE WHEN bt.txn_direction='debit'  THEN bt.amount ELSE 0 END) as spending
        FROM customers c
        JOIN bank_transactions bt ON c.customer_id = bt.customer_id
        GROUP BY c.customer_id, c.first_name
        ORDER BY spending DESC
        LIMIT 5
    """)
    print("\nTop 5 spenders:")
    for r in cur.fetchall():
        print(f"  {r[0]:<15} txns={r[1]:3d}  income=${float(r[2]):>10,.0f}  spending=${float(r[3]):>10,.0f}")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
