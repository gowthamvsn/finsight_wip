import asyncio
import logging
import os
from datetime import datetime, timezone

import numpy as np
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(), override=True)

from db.connection import execute, fetch_all, fetch_one

logger = logging.getLogger("agents.market")

CRYPTO_MAP = {
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    "SOL": "SOL-USD",
    "BNB": "BNB-USD",
}

GEMINI_SYSTEM = (
    "You are a professional wealth advisor AI. Write clear advisory commentary "
    "based strictly on the ML prediction data provided. Do not invent numbers. "
    "Do not give specific price targets. End with one sentence risk disclaimer."
)

_INDICATOR_COLS = [
    "RSI", "MACD_diff", "ATR", "EMA50", "Stoch_K", "Stoch_D",
    "ADX", "ROC", "CCI", "OBV", "BB_Width", "DollarVolume",
    "GK_Volatility", "Log_Close", "Log_BB_Lower",
]
_FLAG_COLS = [
    "RSI_under_30", "MACD_positive", "Close_above_EMA50",
    "High_DollarVolume", "EPS_positive", "High_GK_Volatility",
    "ATR_above_avg", "Log_Close_above_BB_Lower", "Stoch_K_crossover",
    "ADX_above_20", "ROC_above_2", "CCI_extreme", "OBV_rising",
    "BB_width_expansion",
]
FEATURE_COLS = _FLAG_COLS  # 14 binary flags — matches RF training features

# ── Module-level singletons ────────────────────────────────────────────────

_rf_model = None
_CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "tickersdetails_US_master.csv")
_universe_df = None

# Universe flags cache — pre-computed indicator+flag last-row per ticker
_universe_flags_cache = None
_universe_cache_built_at = None
_CACHE_TTL_HOURS = 24   # refresh once per day — fresh yfinance data, not training CSV

# Disk cache path — survives hot-reloads and backend restarts within the same day
_CACHE_DISK_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "universe_cache.pkl")

try:
    import joblib
    _model_path = os.path.join(os.path.dirname(__file__), "..", "models", "rf_model.pkl")
    _rf_model = joblib.load(_model_path)
    logger.info(f"RF model loaded from {_model_path}")
except Exception as e:
    logger.warning(f"RF model not loaded — ML predictions disabled: {e}")

# Load disk cache on startup — avoids rebuild after hot-reload or same-day restart
try:
    import pickle
    if os.path.exists(_CACHE_DISK_PATH):
        with open(_CACHE_DISK_PATH, "rb") as _f:
            _cached = pickle.load(_f)
            _age_hours = (datetime.utcnow() - _cached["built_at"]).total_seconds() / 3600
            if _age_hours < _CACHE_TTL_HOURS:
                _universe_flags_cache = _cached["df"]
                _universe_cache_built_at = _cached["built_at"]
                logger.info(
                    f"Universe cache loaded from disk: {len(_universe_flags_cache)} tickers "
                    f"(age={_age_hours:.1f}h)"
                )
            else:
                logger.info("Disk cache found but stale — will rebuild on next request")
except Exception as _e:
    logger.warning(f"Could not load disk cache: {_e}")


def _get_universe_df():
    global _universe_df
    if _universe_df is None:
        try:
            import pandas as pd
            _universe_df = pd.read_csv(_CSV_PATH, parse_dates=["Date"])
            n_tickers = _universe_df["Ticker"].nunique()
            logger.info(f"Universe loaded: {n_tickers} tickers from {_CSV_PATH}")
        except Exception as e:
            logger.error(f"Failed to load universe CSV: {e}")
            _universe_df = None
    return _universe_df


# ── Technical indicator computation ───────────────────────────────────────

def compute_indicators(df):
    """Add 15 technical indicator columns to df. Modifies in-place."""
    import ta
    close = df["Close"]
    high  = df["High"]
    low   = df["Low"]
    vol   = df["Volume"]
    open_ = df["Open"]

    df["RSI"]      = ta.momentum.RSIIndicator(close, window=14).rsi()
    df["MACD_diff"] = ta.trend.MACD(close).macd_diff()
    df["ATR"]      = ta.volatility.AverageTrueRange(high, low, close, window=14).average_true_range()
    df["EMA50"]    = ta.trend.EMAIndicator(close, window=50).ema_indicator()

    stoch = ta.momentum.StochasticOscillator(high, low, close)
    df["Stoch_K"] = stoch.stoch()
    df["Stoch_D"] = stoch.stoch_signal()

    df["ADX"] = ta.trend.ADXIndicator(high, low, close, window=14).adx()
    df["ROC"] = ta.momentum.ROCIndicator(close, window=10).roc()
    df["CCI"] = ta.trend.CCIIndicator(high, low, close, window=20).cci()
    df["OBV"] = ta.volume.OnBalanceVolumeIndicator(close, vol).on_balance_volume()

    bb = ta.volatility.BollingerBands(close)
    df["BB_Width"]    = bb.bollinger_wband()
    df["Log_BB_Lower"] = np.log(bb.bollinger_lband().replace(0, np.nan))

    df["DollarVolume"] = close * vol

    log_hl = np.log(high / low.replace(0, np.nan))
    log_co = np.log(close / open_.replace(0, np.nan))
    df["GK_Volatility"] = 0.5 * log_hl ** 2 - (2 * np.log(2) - 1) * log_co ** 2
    df["Log_Close"]    = np.log(close.replace(0, np.nan))
    return df


def build_flags(df):
    """Add 14 binary flag columns. Skips EPS_positive if already set."""
    df["RSI_under_30"]           = (df["RSI"] < 30).astype(int)
    df["MACD_positive"]          = (df["MACD_diff"] > 0).astype(int)
    df["Close_above_EMA50"]      = (df["Close"] > df["EMA50"]).astype(int)
    df["High_DollarVolume"]      = (df["DollarVolume"] > df["DollarVolume"].rolling(20).mean()).astype(int)

    # EPS_positive: use real EPS if column present, else constant 1
    if "EPS_positive" not in df.columns:
        df["EPS_positive"] = 1

    df["High_GK_Volatility"]         = (df["GK_Volatility"] > df["GK_Volatility"].rolling(20).mean()).astype(int)
    df["ATR_above_avg"]               = (df["ATR"] > df["ATR"].rolling(20).mean()).astype(int)
    df["Log_Close_above_BB_Lower"]    = (df["Log_Close"] > df["Log_BB_Lower"]).astype(int)
    df["Stoch_K_crossover"]           = (
        (df["Stoch_K"] > df["Stoch_D"]) &
        (df["Stoch_K"].shift(1) <= df["Stoch_D"].shift(1))
    ).astype(int)
    df["ADX_above_20"]       = (df["ADX"] > 20).astype(int)
    df["ROC_above_2"]        = (df["ROC"] > 2).astype(int)
    df["CCI_extreme"]        = (df["CCI"].abs() > 100).astype(int)
    df["OBV_rising"]         = (df["OBV"] > df["OBV"].shift(1)).astype(int)
    df["BB_width_expansion"] = (df["BB_Width"] > df["BB_Width"].rolling(20).mean()).astype(int)
    return df


def _calibrate_prob(prob: float, temperature: float = 3.0) -> float:
    """
    Temperature scaling — compresses extreme probabilities toward 0.5.
    Fixes RF over-confidence caused by inference on training-set patterns.
    T=3.0 maps 0.99 → ~0.81, 0.90 → ~0.72, 0.70 → ~0.60, 0.50 → 0.50
    """
    import math
    p = max(0.001, min(0.999, prob))
    logit = math.log(p / (1 - p))
    return 1.0 / (1.0 + math.exp(-logit / temperature))


def _signal_label(prob: float) -> str:
    if prob > 0.75:
        return "strong buy"
    elif prob > 0.55:
        return "buy"
    elif prob > 0.40:
        return "neutral"
    return "caution"


# ── Universe flags cache builder (synchronous, run via to_thread) ──────────

_BATCH_SIZE = 150   # yfinance tickers per download call

def _build_universe_cache() -> None:
    """
    Downloads fresh 90-day OHLCV from yfinance for every ticker in the universe CSV,
    computes indicators + flags on live market data (not training CSV rows), and
    stores the last-row flag vector per ticker in _universe_flags_cache.

    This gives true out-of-sample inference — the RF model never saw today's
    flag combinations during training, so predictions vary day-to-day with the market.

    Runs once at startup (after 15 s warm-up), then refreshes every 24 h.
    Batches yfinance downloads (_BATCH_SIZE tickers per call) to stay fast.
    """
    global _universe_flags_cache, _universe_cache_built_at

    if _rf_model is None:
        return
    raw = _get_universe_df()
    if raw is None:
        return

    import pandas as pd
    try:
        import yfinance as yf
    except ImportError:
        logger.error("yfinance not installed — cannot build live universe cache")
        return

    # Use CSV only for the ticker list (not for OHLCV data)
    all_db_tickers = [t for t in raw["Ticker"].unique().tolist()
                      if isinstance(t, str) and t.strip()]
    logger.info(f"Building live universe cache: {len(all_db_tickers)} tickers via yfinance")

    rows = []
    total_batches = (len(all_db_tickers) + _BATCH_SIZE - 1) // _BATCH_SIZE

    for batch_idx in range(total_batches):
        batch_db = all_db_tickers[batch_idx * _BATCH_SIZE : (batch_idx + 1) * _BATCH_SIZE]
        # Map DB ticker → yfinance symbol
        batch_yf  = [CRYPTO_MAP.get(t, t) for t in batch_db]
        yf_to_db  = {yf_sym: db_t for yf_sym, db_t in zip(batch_yf, batch_db)}

        try:
            if len(batch_yf) == 1:
                raw_dl = yf.download(
                    batch_yf[0], period="90d", interval="1d",
                    progress=False, auto_adjust=True,
                )
                if raw_dl.empty:
                    continue
                downloads = {batch_yf[0]: raw_dl}
            else:
                raw_dl = yf.download(
                    batch_yf, period="90d", interval="1d",
                    progress=False, auto_adjust=True,
                    group_by="ticker",
                )
                if raw_dl.empty:
                    continue
                downloads = {}
                for sym in batch_yf:
                    try:
                        if isinstance(raw_dl.columns, pd.MultiIndex):
                            df_sym = raw_dl[sym].dropna(how="all")
                        else:
                            df_sym = raw_dl  # single-ticker fallback
                        if not df_sym.empty:
                            downloads[sym] = df_sym
                    except Exception:
                        pass
        except Exception as e:
            logger.warning(f"Batch {batch_idx+1}/{total_batches} download failed: {e}")
            continue

        for yf_sym, df in downloads.items():
            db_ticker = yf_to_db.get(yf_sym, yf_sym)
            try:
                if len(df) < 60:
                    continue
                df = df.copy()
                # Ensure standard column names (yfinance sometimes returns MultiIndex)
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                required = {"Open", "High", "Low", "Close", "Volume"}
                if not required.issubset(df.columns):
                    continue
                df = compute_indicators(df)
                df = build_flags(df)
                available = [c for c in FEATURE_COLS if c in df.columns]
                if len(available) < len(FEATURE_COLS):
                    continue
                last = df[available].dropna()
                if last.empty:
                    continue
                row = last.iloc[-1].to_dict()
                row["Ticker"] = db_ticker
                rows.append(row)
            except Exception as e:
                logger.debug(f"Cache skip {db_ticker}: {e}")

        logger.info(
            f"Universe cache batch {batch_idx+1}/{total_batches} done "
            f"({len(rows)} tickers so far)"
        )

    if rows:
        _universe_flags_cache = pd.DataFrame(rows)
        _universe_cache_built_at = datetime.utcnow()
        # Persist to disk so hot-reloads and same-day restarts skip the rebuild
        try:
            import pickle
            cache_dir = os.path.dirname(_CACHE_DISK_PATH)
            os.makedirs(cache_dir, exist_ok=True)
            with open(_CACHE_DISK_PATH, "wb") as f:
                pickle.dump({"df": _universe_flags_cache, "built_at": _universe_cache_built_at}, f)
            logger.info(f"Universe cache saved to disk: {_CACHE_DISK_PATH}")
        except Exception as e:
            logger.warning(f"Could not save cache to disk: {e}")
        logger.info(
            f"Live universe cache ready: {len(_universe_flags_cache)} tickers "
            f"(built at {_universe_cache_built_at.strftime('%H:%M UTC')})"
        )
    else:
        logger.warning("Universe cache build produced no rows — yfinance may be rate-limited")


# ── Universe scan (synchronous, run via to_thread) ─────────────────────────

def _scan_universe(held_set: set) -> tuple:
    """
    Score all tickers using cached flags + RF model.
    Returns (suggestions: list[dict], universe_size: int).
    On cache miss, builds cache first (slow). On cache hit, only runs predict_proba (fast).
    """
    if _rf_model is None:
        return [], 0

    raw = _get_universe_df()
    if raw is None:
        return [], 0

    universe_size = raw["Ticker"].nunique()

    # Rebuild cache if missing or stale
    cache_stale = (
        _universe_flags_cache is None or
        _universe_cache_built_at is None or
        (datetime.utcnow() - _universe_cache_built_at).total_seconds() > _CACHE_TTL_HOURS * 3600
    )
    if cache_stale:
        _build_universe_cache()

    if _universe_flags_cache is None or _universe_flags_cache.empty:
        return [], universe_size

    import pandas as pd
    batch_df = _universe_flags_cache.copy()
    for col in FEATURE_COLS:
        if col not in batch_df.columns:
            batch_df[col] = 0

    raw_probs = _rf_model.predict_proba(batch_df[FEATURE_COLS])[:, 1]
    import pandas as pd
    cal_probs = pd.Series(raw_probs).apply(_calibrate_prob)
    batch_df["raw_prob"]          = raw_probs
    batch_df["Predicted_Prob"]    = cal_probs
    batch_df["confidence"]        = (cal_probs * 100).round(1)
    # Centered return: (calibrated_prob - 0.5) * 12 → range ≈ -6% to +6%
    batch_df["predicted_5d_pct"]  = ((cal_probs - 0.5) * 12).round(2)
    batch_df["signal"]            = cal_probs.apply(_signal_label)
    batch_df["flags_fired"]       = batch_df[_FLAG_COLS].sum(axis=1).astype(int)

    top = (
        batch_df[
            (batch_df["confidence"] >= 55) &
            (~batch_df["Ticker"].isin(held_set))
        ]
        .sort_values("Predicted_Prob", ascending=False)
        .head(20)
    )

    suggestions = [
        {
            "ticker":           row["Ticker"],
            "confidence":       int(row["confidence"]),
            "signal":           row["signal"],
            "already_holds":    False,
            "predicted_5d_pct": float(row["predicted_5d_pct"]),
            "flags_fired":      int(row["flags_fired"]),
            "sector":           None,
        }
        for _, row in top.iterrows()
    ]

    logger.info(f"Universe scan (cached): {universe_size} tickers → {len(suggestions)} suggestions")
    return suggestions, universe_size


# ── yfinance download for held tickers ────────────────────────────────────

def _download_ohlcv(tickers: list) -> dict:
    """Synchronous yfinance OHLCV download. Returns {yf_symbol: DataFrame}."""
    try:
        import yfinance as yf
        import pandas as pd

        yf_symbols = [CRYPTO_MAP.get(t, t) for t in tickers]
        result = {}

        if len(yf_symbols) == 1:
            sym = yf_symbols[0]
            df = yf.download(sym, period="60d", interval="1d",
                             progress=False, auto_adjust=True)
            if not df.empty:
                result[sym] = df
        else:
            data = yf.download(yf_symbols, period="60d", interval="1d",
                               progress=False, auto_adjust=True)
            if not data.empty:
                for sym in yf_symbols:
                    try:
                        if isinstance(data.columns, pd.MultiIndex):
                            df = data.xs(sym, axis=1, level=1).dropna(how="all")
                        else:
                            df = data
                        if not df.empty:
                            result[sym] = df
                    except Exception:
                        pass
        return result
    except Exception as e:
        logger.error(f"OHLCV download failed: {e}")
        return {}


def _predict_single(yf_sym: str, df) -> float | None:
    """Run RF model on the latest row of a DataFrame. Returns prob or None."""
    if _rf_model is None:
        return None
    try:
        df = compute_indicators(df.copy())
        df = build_flags(df)
        avail = [c for c in FEATURE_COLS if c in df.columns]
        row = df[avail].dropna()
        if row.empty:
            return None
        return float(_rf_model.predict_proba(row.iloc[[-1]])[0][1])
    except Exception as e:
        logger.warning(f"Single predict failed for {yf_sym}: {e}")
        return None


# ── Market narrative: Gemini → Azure GPT-4o → hardcoded fallback ──────────

def _get_narrative(prompt_content: str, suggestions: list, risk_profile: str) -> str:
    # 1. Try Gemini
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel("gemini-2.0-flash", system_instruction=GEMINI_SYSTEM)
            resp = model.generate_content(prompt_content)
            if resp.text:
                logger.info("Narrative: Gemini")
                return resp.text
        except Exception as e:
            logger.warning(f"Gemini narrative failed: {e}")

    # 2. Azure OpenAI GPT-4o fallback
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key  = os.getenv("AZURE_OPENAI_KEY")
    if endpoint and api_key:
        try:
            from openai import AzureOpenAI
            client = AzureOpenAI(
                azure_endpoint=endpoint,
                api_key=api_key,
                api_version="2024-02-01",
            )
            resp = client.chat.completions.create(
                model=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"),
                messages=[
                    {"role": "system", "content": GEMINI_SYSTEM},
                    {"role": "user",   "content": prompt_content},
                ],
                max_tokens=300,
            )
            text = resp.choices[0].message.content
            if text:
                logger.info("Narrative: Azure GPT-4o fallback")
                return text
        except Exception as e:
            logger.warning(f"GPT-4o narrative fallback failed: {e}")

    # 3. Hardcoded fallback — always returns non-empty text
    logger.info("Narrative: hardcoded fallback")
    if suggestions:
        tickers = ", ".join(s["ticker"] for s in suggestions[:3])
        return (
            f"Our model identified {tickers} as top opportunities from a universe of {len(suggestions) + 800} US stocks. "
            f"These signals are derived from 14 technical indicators including RSI, MACD, ADX, and Bollinger Bands. "
            f"Past model performance does not guarantee future returns — "
            f"please consult your advisor before acting on these signals."
        )
    return (
        "Market analysis complete. No strong new opportunities identified at this time. "
        "Past model performance does not guarantee future returns — consult your advisor before acting."
    )


# ── Main agent function ────────────────────────────────────────────────────

async def run_market_agent(customer_id: str, held_tickers: list, pool) -> dict:
    start = datetime.utcnow()
    try:
        held_set = set(held_tickers)

        # Fetch customer risk profile
        customer = await fetch_one(
            "SELECT risk_profile FROM customers WHERE customer_id=$1",
            customer_id,
        )
        risk_profile = customer["risk_profile"] if customer else "moderate"

        # Fetch current holdings data (value + P&L)
        holdings_data = {}
        if held_tickers:
            rows = await fetch_all(
                """
                SELECT ticker, current_value, unrealized_pl
                FROM portfolio_holdings
                WHERE customer_id=$1 AND asset_type != 'cash'
                """,
                customer_id,
            )
            holdings_data = {r["ticker"]: r for r in rows}

        # Part A: universe scan (uses cache if warm, builds on miss)
        suggestions, universe_size = await asyncio.to_thread(_scan_universe, held_set)

        # Part B: yfinance download for held tickers
        portfolio_predictions = []
        db_updates = []

        if held_tickers:
            ohlcv = await asyncio.to_thread(_download_ohlcv, held_tickers)

            for db_ticker in held_tickers:
                yf_sym = CRYPTO_MAP.get(db_ticker, db_ticker)
                df = ohlcv.get(yf_sym)

                if df is None or df.empty:
                    logger.warning(f"No yfinance data for {db_ticker} ({yf_sym})")
                    prob = 0.50
                else:
                    prob = await asyncio.to_thread(_predict_single, yf_sym, df)
                    if prob is None:
                        prob = 0.50
                    else:
                        prob = _calibrate_prob(prob)

                signal     = _signal_label(prob)
                confidence = round(prob * 100, 1)
                pred_5d    = round((prob - 0.5) * 12, 2)

                flags_fired = 0
                if df is not None and not df.empty:
                    try:
                        tmp = compute_indicators(df.copy())
                        tmp = build_flags(tmp)
                        last = tmp[_FLAG_COLS].dropna()
                        if not last.empty:
                            flags_fired = int(last.iloc[-1].sum())
                    except Exception:
                        pass

                h_data = holdings_data.get(db_ticker, {})
                portfolio_predictions.append({
                    "ticker":           db_ticker,
                    "confidence":       confidence,
                    "signal":           signal,
                    "already_holds":    True,
                    "current_value":    float(h_data.get("current_value") or 0),
                    "unrealized_pl":    float(h_data.get("unrealized_pl") or 0),
                    "predicted_5d_pct": pred_5d,
                    "flags_fired":      flags_fired,
                })
                db_updates.append((pred_5d, confidence, db_ticker))

        portfolio_predictions.sort(key=lambda x: x["confidence"], reverse=True)

        # Part D: update market_prices table
        for p5d, conf, ticker in db_updates:
            try:
                await execute(
                    """
                    UPDATE market_prices
                    SET predicted_5d_pct=$1, prediction_confidence=$2
                    WHERE ticker=$3
                    """,
                    p5d, conf, ticker,
                )
            except Exception as e:
                logger.warning(f"DB update failed for {ticker}: {e}")

        # Part E: narrative — guaranteed non-empty via 3-tier fallback
        top5_suggestions = suggestions[:5]
        top3_held = portfolio_predictions[:3]

        sugg_text = "\n".join([
            f"  {s['ticker']}: signal={s['signal']}, "
            f"confidence={s['confidence']}%, predicted_5d={s['predicted_5d_pct']}%"
            for s in top5_suggestions
        ]) or "  None"

        held_text = "\n".join([
            f"  {h['ticker']}: signal={h['signal']}, "
            f"confidence={h['confidence']}%, predicted_5d={h['predicted_5d_pct']}%, "
            f"current_value=${h['current_value']:,.2f}, P&L=${h['unrealized_pl']:,.2f}"
            for h in top3_held
        ]) or "  None"

        prompt = (
            f"Customer risk profile: {risk_profile}\n\n"
            f"TOP NEW MARKET SUGGESTIONS (not currently held):\n{sugg_text}\n\n"
            f"CURRENT PORTFOLIO SIGNALS (held positions):\n{held_text}\n\n"
            "Please write:\n"
            "- 2 sentences on the top new market suggestions\n"
            "- 2 sentences on the held ticker signals\n"
            "- 1 sentence risk disclaimer"
        )
        narrative = await asyncio.to_thread(_get_narrative, prompt, top5_suggestions, risk_profile)

        ms = int((datetime.utcnow() - start).total_seconds() * 1000)
        logger.info(
            f"Market agent: customer={customer_id} "
            f"held={len(held_tickers)} universe={universe_size} "
            f"suggestions={len(suggestions)} duration={ms}ms"
        )

        # Raw RF debug info — top 10 universe scores
        raw_rf_scores = []
        if _universe_flags_cache is not None and not _universe_flags_cache.empty:
            import pandas as pd
            debug_df = _universe_flags_cache.copy()
            for col in FEATURE_COLS:
                if col not in debug_df.columns:
                    debug_df[col] = 0
            probs_debug = _rf_model.predict_proba(debug_df[FEATURE_COLS])[:, 1]
            debug_df["prob"] = probs_debug
            debug_df["flags_fired"] = debug_df[_FLAG_COLS].sum(axis=1).astype(int)
            probs_cal = pd.Series(probs_debug).apply(_calibrate_prob)
            debug_df["cal_prob"] = probs_cal.values
            top10 = debug_df.nlargest(10, "prob")[["Ticker", "prob", "cal_prob", "flags_fired"] + _FLAG_COLS]
            for _, r in top10.iterrows():
                raw_rf_scores.append({
                    "ticker": r["Ticker"],
                    "raw_prob": round(float(r["prob"]), 4),
                    "cal_prob": round(float(r["cal_prob"]), 4),
                    "flags_fired": int(r["flags_fired"]),
                    "flags": {f: int(r[f]) for f in _FLAG_COLS},
                })

        return {
            "portfolio_predictions": portfolio_predictions,
            "market_suggestions":    suggestions,
            "narrative":             narrative,
            "universe_scanned":      universe_size,
            "raw_rf_top10":          raw_rf_scores,
            "analyzed_at":           datetime.now(timezone.utc).isoformat(),
            "duration_ms":           ms,
        }

    except Exception as e:
        logger.error(f"Market agent error: customer={customer_id} error={e}")
        return {
            "portfolio_predictions": [],
            "market_suggestions":    [],
            "narrative":             "Market analysis temporarily unavailable. Please try again.",
            "error":                 str(e),
            "universe_scanned":      0,
            "analyzed_at":           datetime.now(timezone.utc).isoformat(),
            "duration_ms":           0,
        }
