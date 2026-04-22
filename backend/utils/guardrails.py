import re
from pydantic import BaseModel

BANNED_PHRASES = [
    'ignore previous',
    'system prompt',
    'forget instructions',
    'you are now',
    'disregard all',
    'jailbreak',
    'ignore all previous',
    'act as',
    'pretend you are',
    'override',
    'bypass',
    'sudo',
    'admin mode',
]


def sanitize_query(text: str) -> str:
    if not text:
        return text
    lower = text.lower()
    for phrase in BANNED_PHRASES:
        if phrase in lower:
            raise ValueError(f"Query contains disallowed content: {phrase}")
    text = re.sub(r'[\x00-\x1f\x7f]', '', text)
    if len(text) > 2000:
        raise ValueError("Query exceeds maximum length of 2000 characters")
    return text.strip()


def validate_customer_id(cid: str) -> bool:
    return bool(re.match(r'^CUS-\d{4}$', cid))


ALLOWED_TICKERS = [
    'NVDA', 'TSLA', 'AAPL', 'MSFT', 'AMZN', 'GOOGL',
    'META', 'VTSAX', 'SPY', 'QQQ', 'BTC', 'ETH', 'SOL',
    'BNB', 'CASH',
]


def validate_ticker(ticker: str) -> bool:
    return ticker.upper() in ALLOWED_TICKERS
