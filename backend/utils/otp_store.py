import secrets, string
from datetime import datetime, timedelta

_store: dict = {}  # challenge_id -> {otp, txn_id, customer_id, ticker, txn_type, quantity, price, geo_country, txn_category, expires_at}

def create_otp(txn_id: str, customer_id: str, ttl_minutes: int = 5,
               ticker: str = "", txn_type: str = "", quantity: float = 0,
               price: float = 0, geo_country: str = "US",
               txn_category: str = "equity_trade") -> tuple:
    """Returns (challenge_id, otp_string)"""
    challenge_id = secrets.token_urlsafe(16)
    otp = ''.join(secrets.choice(string.digits) for _ in range(6))
    _store[challenge_id] = {
        "otp": otp,
        "txn_id": txn_id,
        "customer_id": customer_id,
        "ticker": ticker,
        "txn_type": txn_type,
        "quantity": quantity,
        "price": price,
        "geo_country": geo_country,
        "txn_category": txn_category,
        "expires_at": datetime.utcnow() + timedelta(minutes=ttl_minutes),
    }
    return challenge_id, otp

def verify_otp(challenge_id: str, otp: str) -> dict | None:
    """Returns stored entry if valid, None if invalid/expired. Single-use."""
    entry = _store.get(challenge_id)
    if not entry:
        return None
    if datetime.utcnow() > entry["expires_at"]:
        _store.pop(challenge_id, None)
        return None
    if entry["otp"] != otp:
        return None
    _store.pop(challenge_id)
    return entry
