"""
Generate and insert 250-300 realistic transactions for the last 30 days
across all 50 customers.  Run: python seed_recent_txns.py
"""
import os, random, math
from datetime import datetime, timedelta, timezone
import psycopg2

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://menouser:WEHealth123@wehealthdb.postgres.database.azure.com:5432/wealth_manage"
)

# ── Ticker universe and approximate prices ──────────────────────────────────
PRICES = {
    "NVDA": 200, "TSLA": 390, "AAPL": 229, "MSFT": 415, "AMZN": 195,
    "GOOGL": 175, "META": 540, "VTSAX": 170, "SPY": 540, "QQQ": 470,
    "BTC": 75000, "ETH": 2300, "SOL": 85, "BNB": 630,
    "AMD": 165, "INTC": 22, "CRM": 280, "ORCL": 160, "ADBE": 370,
    "NFLX": 620, "DIS": 95, "BA": 175, "JPM": 235, "GS": 540,
    "BAC": 42, "WFC": 75, "V": 330, "MA": 530, "PYPL": 75,
    "AMGN": 310, "JNJ": 155, "PFE": 28, "MRK": 95, "UNH": 490,
    "CVS": 58, "ABBV": 195, "XOM": 115, "CVX": 155, "COP": 115,
    "SLB": 42, "WMT": 92, "TGT": 130, "COST": 920, "HD": 380,
    "LOW": 240, "T": 22, "VZ": 40, "TMUS": 240, "GE": 195,
    "CAT": 365, "MMM": 140, "HON": 230, "COIN": 195, "MARA": 18,
    "RIOT": 12, "MSTR": 340, "PLTR": 92, "SNOW": 155, "DDOG": 115,
    "NET": 115, "CRWD": 375, "ZS": 195, "LLY": 820, "TMO": 480,
    "DHR": 195, "ISRG": 520, "NEE": 72, "DUK": 115, "SO": 88,
    "AMT": 195, "PLD": 115, "EQIX": 790, "GLD": 295, "SLV": 32,
    "USO": 76, "ARKK": 52, "SOXX": 215, "XLF": 48, "XLE": 95,
    "XLK": 220, "XLV": 145,
}

CRYPTO = {"BTC", "ETH", "SOL", "BNB"}
ETFS   = {"SPY", "QQQ", "VTSAX", "ARKK", "SOXX", "XLF", "XLE", "XLK", "XLV",
           "GLD", "SLV", "USO"}

# Tickers per risk profile (soft guidance)
CONSERVATIVE_TICKERS = [
    "AAPL", "MSFT", "JNJ", "PG", "V", "MA", "JPM", "WMT", "HD",
    "SPY", "QQQ", "VTSAX", "XLF", "XLV", "GLD", "T", "VZ",
    "XOM", "CVX", "KO", "PEP", "MMM", "HON", "NEE", "DUK", "SO",
]
MODERATE_TICKERS = [
    "NVDA", "TSLA", "AMZN", "GOOGL", "META", "NFLX", "CRM", "ADBE",
    "AMD", "PLTR", "COIN", "MSFT", "AAPL", "BAC", "WFC", "UNH",
    "LLY", "TMO", "ISRG", "CRWD", "NET", "DDOG", "SNOW",
    "SPY", "QQQ", "SOXX", "XLK", "ETH", "BNB",
]
AGGRESSIVE_TICKERS = [
    "BTC", "ETH", "SOL", "BNB", "MARA", "RIOT", "MSTR", "COIN",
    "PLTR", "SNOW", "DDOG", "NET", "CRWD", "ZS", "NVDA", "TSLA",
    "AMD", "INTC", "META", "AMZN", "NFLX", "GS", "ARKK",
]

SUSPICIOUS_COUNTRIES = ["NG", "RU", "CN"]

# ── Helpers ─────────────────────────────────────────────────────────────────
def rand_price(ticker):
    base = PRICES[ticker]
    return round(base * random.uniform(0.95, 1.05), 2)

def rand_qty(ticker):
    if ticker in CRYPTO:
        return round(random.uniform(0.001, 2.0), 6)
    elif ticker in ETFS:
        return random.randint(1, 100)
    else:
        return random.randint(1, 50)

def rand_ip(country):
    # Approximate country IP blocks (rough, realistic-looking)
    blocks = {
        "US": (24, 104), "IN": (103, 49), "UK": (81, 5),
        "CA": (64, 26), "AU": (1, 120), "SG": (103, 6),
        "DE": (80, 91), "FR": (90, 195), "JP": (101, 211),
        "AE": (185, 46), "CH": (80, 74), "NL": (145, 220),
        "NG": (197, 210), "RU": (5, 101), "CN": (1, 123),
    }
    a, b = blocks.get(country, (10, 100))
    return f"{a}.{random.randint(0,255)}.{b}.{random.randint(1,254)}"

def rand_timestamp(days_back_max=30, flagged=False):
    now = datetime.now(timezone.utc)
    day_offset = random.randint(0, days_back_max - 1)
    dt = now - timedelta(days=day_offset)
    if flagged:
        # Late-night hour: 23:00–05:00
        hour = random.choice(list(range(23, 24)) + list(range(0, 6)))
    else:
        hour = random.randint(9, 21)
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    return dt.replace(hour=hour, minute=minute, second=second, microsecond=0)

def rand_category(txn_type):
    if txn_type == "transfer":
        return "transfer"
    cats = ["investment", "investment", "investment", "rebalancing", "div_reinvest"]
    return random.choice(cats)

def pick_ticker(risk_profile):
    pool = {
        "conservative": CONSERVATIVE_TICKERS,
        "moderate":     MODERATE_TICKERS,
        "aggressive":   AGGRESSIVE_TICKERS,
    }.get(risk_profile, MODERATE_TICKERS)
    # Filter to only tickers we have prices for
    valid = [t for t in pool if t in PRICES]
    return random.choice(valid)

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor()

    # Fetch customers
    cur.execute("""
        SELECT customer_id, risk_profile,
               COALESCE(
                   (SELECT geo_country FROM transactions
                    WHERE customer_id = c.customer_id LIMIT 1),
                   'US'
               ) AS country
        FROM customers c
        ORDER BY customer_id
    """)
    customers = cur.fetchall()
    print(f"Loaded {len(customers)} customers")

    # Find current max numeric txn id
    cur.execute("SELECT MAX(CAST(REPLACE(txn_id,'TXN-','') AS INTEGER)) FROM transactions WHERE txn_id ~ '^TXN-[0-9]+$'")
    row = cur.fetchone()
    next_id = (row[0] or 9200) + 1
    print(f"Starting txn_id from TXN-{next_id:04d}")

    # Decide per-customer txn counts (3–10 each, total ~300)
    # Weight higher for some customers to create variance
    random.seed(42)
    per_customer = {}
    for cid, rp, country in customers:
        per_customer[cid] = random.randint(3, 10)

    total_planned = sum(per_customer.values())
    print(f"Planned transactions: {total_planned}")

    inserted = 0
    txn_rows = []

    for cid, risk_profile, base_country in customers:
        count = per_customer[cid]

        # Decide which of this customer's transactions are flagged (~8%)
        flagged_indices = set()
        num_flagged = max(0, round(count * 0.08))
        # At least one flagged per ~12-13 customers on average
        if random.random() < 0.08 * count:
            flagged_indices.add(random.randint(0, count - 1))

        for i in range(count):
            is_flagged = i in flagged_indices

            # txn_type: 60% buy, 30% sell, 10% transfer
            r = random.random()
            if r < 0.60:
                txn_type = "buy"
            elif r < 0.90:
                txn_type = "sell"
            else:
                txn_type = "transfer"

            ticker = pick_ticker(risk_profile)
            price  = rand_price(ticker)
            qty    = rand_qty(ticker)

            # Flagged overrides
            if is_flagged:
                # Must be large value
                min_value = 50001
                qty = max(qty, math.ceil(min_value / price) + random.randint(0, 10))
                country_for_txn = random.choice(SUSPICIOUS_COUNTRIES)
                ts = rand_timestamp(flagged=True)
            else:
                country_for_txn = base_country
                ts = rand_timestamp(flagged=False)

            total_val = round(qty * price, 2)

            realized_pl = 0.0
            if txn_type == "sell":
                if random.random() < 0.70:  # 70% profitable sells
                    realized_pl = round(total_val * random.uniform(0.02, 0.25), 2)
                else:
                    realized_pl = round(total_val * random.uniform(-0.15, -0.02), 2)

            txn_id   = f"TXN-{next_id:04d}"
            next_id += 1
            ip       = rand_ip(country_for_txn)
            category = rand_category(txn_type)

            txn_rows.append((
                txn_id, cid, ticker, txn_type, category,
                qty, price, total_val, realized_pl,
                is_flagged, ts, ip, country_for_txn, ts
            ))
            inserted += 1

    # Shuffle so timestamps are not grouped by customer
    random.shuffle(txn_rows)

    # Insert in one batch
    cur.executemany("""
        INSERT INTO transactions
            (txn_id, customer_id, ticker, txn_type, txn_category,
             quantity, price_at_txn, total_value, realized_pl,
             flagged, txn_timestamp, ip_address, geo_country, created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (txn_id) DO NOTHING
    """, txn_rows)

    conn.commit()
    print(f"Inserted {inserted} transactions")

    # ── Verification ─────────────────────────────────────────────────────────
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
    row = cur.fetchone()
    labels = ["total_txns","customers_with_txns","buy_volume","sell_volume",
              "flagged_count","earliest","latest"]
    print("\n-- 30-day summary --")
    for lbl, val in zip(labels, row):
        print(f"  {lbl:<25} {val}")

    cur.execute("""
        SELECT customer_id,
               COUNT(*)                                                    AS txn_count,
               SUM(CASE WHEN txn_type='buy'  THEN total_value ELSE 0 END) AS buy_vol,
               SUM(CASE WHEN txn_type='sell' THEN total_value ELSE 0 END) AS sell_vol
        FROM transactions
        WHERE txn_timestamp >= NOW() - INTERVAL '30 days'
        GROUP BY customer_id
        ORDER BY buy_vol DESC
        LIMIT 10
    """)
    rows = cur.fetchall()
    print("\n-- Top 10 customers by buy volume --")
    print(f"  {'customer_id':<12} {'txn_count':>9} {'buy_vol':>14} {'sell_vol':>14}")
    for r in rows:
        print(f"  {r[0]:<12} {r[1]:>9} {float(r[2] or 0):>14,.2f} {float(r[3] or 0):>14,.2f}")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
