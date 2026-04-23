import hashlib
import logging
import os
from datetime import datetime, timezone

import numpy as np
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(), override=True)

from db.connection import fetch_one, fetch_all, execute
from utils.email_sender import send_alert_email

logger = logging.getLogger("agents.fraud")

CRYPTO_TICKERS = {"BTC", "ETH", "SOL", "BNB"}
HIGH_RISK_COUNTRIES = {"NG", "RU", "CN", "IR", "KP"}


def _new_alert_id(customer_id: str, txn_id: str, alert_type: str) -> str:
    key = f"{customer_id}:{txn_id}:{alert_type}"
    return "ALT-" + hashlib.md5(key.encode()).hexdigest()[:6].upper()


def _get_alert_clients():
    try:
        import main as app_module
        return app_module.connected_alert_clients
    except Exception:
        return []


async def _insert_alert(
    pool,
    customer_id: str,
    txn_id: str,
    alert_type: str,
    severity: str,
    source: str,
    description: str,
) -> str:
    alert_id = _new_alert_id(customer_id, txn_id, alert_type)
    await execute(
        """
        INSERT INTO alerts
          (alert_id, customer_id, txn_id, alert_type, severity, source,
           description, status, email_sent, detected_at, updated_at)
        VALUES ($1,$2,$3,$4,$5,$6,$7,'open',FALSE,NOW(),NOW())
        ON CONFLICT (alert_id) DO NOTHING
        """,
        alert_id, customer_id, txn_id, alert_type, severity, source, description,
    )
    await execute(
        "UPDATE transactions SET flagged=TRUE WHERE txn_id=$1",
        txn_id,
    )

    if severity in ("high", "critical"):
        try:
            customer = await fetch_one(
                "SELECT email, first_name, last_name FROM customers WHERE customer_id=$1",
                customer_id,
            )
            if customer:
                full_name = f"{customer['first_name']} {customer['last_name']}"
                await send_alert_email(
                    customer["email"],
                    full_name,
                    alert_type,
                    description,
                )
        except Exception as e:
            logger.warning(f"Email send failed for alert {alert_id}: {e}")

    # Broadcast to alert WebSocket clients
    try:
        payload = (
            f'{{"alert_id":"{alert_id}","customer_id":"{customer_id}",'
            f'"alert_type":"{alert_type}","severity":"{severity}"}}'
        )
        dead = []
        for ws in list(_get_alert_clients()):
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        clients = _get_alert_clients()
        for ws in dead:
            try:
                clients.remove(ws)
            except ValueError:
                pass
    except Exception as e:
        logger.warning(f"WebSocket broadcast failed: {e}")

    logger.info(
        f"Fraud alert: id={alert_id} customer={customer_id} "
        f"type={alert_type} severity={severity} source={source}"
    )
    return alert_id


async def score_before_insert(
    customer_id: str,
    ticker: str,
    txn_type: str,
    total_value: float,
    geo_country: str,
    pool,
) -> tuple[list[str], float]:
    """
    Score a transaction BEFORE it is inserted into the DB.
    Returns (reasons, anomaly_score).
    reasons is a non-empty list if OTP should be triggered.
    Does NOT write to the DB.
    """
    reasons: list[str] = []
    anomaly_score = 0.0
    geo = geo_country.upper()
    hour = datetime.now(timezone.utc).hour
    t = ticker.upper()

    # Rule checks (same thresholds as run_fraud_agent)
    if total_value > 50000:
        reasons.append(f"Large transaction: ${total_value:,.2f}")
    if hour in list(range(23, 24)) + list(range(0, 6)) and t in CRYPTO_TICKERS:
        reasons.append(f"Crypto trade at unusual hour ({hour:02d}:00 UTC)")
    if geo in HIGH_RISK_COUNTRIES:
        reasons.append(f"High-risk country: {geo}")

    rapid = await fetch_one(
        "SELECT COUNT(*) AS cnt FROM transactions WHERE customer_id=$1 AND txn_timestamp >= NOW() - INTERVAL '10 minutes'",
        customer_id,
    )
    if rapid and rapid["cnt"] >= 3:
        reasons.append(f"Rapid transactions: {rapid['cnt']} in the last 10 minutes")

    customer = await fetch_one("SELECT risk_profile FROM customers WHERE customer_id=$1", customer_id)
    risk_profile = customer["risk_profile"] if customer else "moderate"
    if risk_profile == "conservative" and t in CRYPTO_TICKERS and txn_type == "buy" and total_value > 5000:
        reasons.append(f"Conservative profile buying ${total_value:,.2f} in crypto ({t})")

    overdue = await fetch_one("SELECT 1 FROM loans WHERE customer_id=$1 AND status='overdue' LIMIT 1", customer_id)
    if overdue and txn_type == "buy" and total_value > 10000:
        reasons.append(f"Overdue loan exists; buy order is ${total_value:,.2f}")

    # Isolation Forest — fit on history, score the candidate transaction
    history = await fetch_all(
        """SELECT total_value, txn_timestamp, ticker, geo_country
           FROM transactions
           WHERE customer_id=$1 AND txn_timestamp >= NOW() - INTERVAL '90 days'
           ORDER BY txn_timestamp DESC""",
        customer_id,
    )
    if len(history) >= 10:
        try:
            from sklearn.ensemble import IsolationForest

            countries = [r["geo_country"] for r in history if r["geo_country"]]
            common_country = max(set(countries), key=countries.count) if countries else None

            def _feats(rows):
                out = []
                for r in rows:
                    rg = (r["geo_country"] or "").upper()
                    out.append([
                        float(r["total_value"]),
                        float(r["txn_timestamp"].hour),
                        1.0 if r["ticker"] in CRYPTO_TICKERS else 0.0,
                        0.0 if (not common_country or rg == common_country) else 1.0,
                        float(sum(
                            1 for o in rows
                            if abs((o["txn_timestamp"] - r["txn_timestamp"]).total_seconds()) <= 3600
                        )),
                    ])
                return np.array(out)

            hist_feat = _feats(list(history))
            iso = IsolationForest(contamination=0.1, random_state=42)
            iso.fit(hist_feat)

            is_new_geo = 0.0 if (not common_country or geo == common_country) else 1.0
            now_ts = datetime.now(timezone.utc)
            hr_count = float(sum(
                1 for r in history
                if abs((r["txn_timestamp"] - now_ts).total_seconds()) <= 3600
            ) + 1)
            curr_feat = np.array([[
                total_value,
                float(hour),
                1.0 if t in CRYPTO_TICKERS else 0.0,
                is_new_geo,
                hr_count,
            ]])

            scores = iso.decision_function(hist_feat)
            mn, mx = scores.min(), scores.max()
            raw = iso.decision_function(curr_feat)[0]
            anomaly_score = float(max(0.0, min(1.0, 1.0 - (raw - mn) / (mx - mn) if mx > mn else 0.0)))

            if anomaly_score > 0.7:
                reasons.append(
                    f"ML anomaly score {anomaly_score:.2f} — pattern deviates from your transaction history"
                )
        except Exception as e:
            logger.warning(f"Isolation Forest (pre-insert) failed: {e}")

    return reasons, anomaly_score


async def run_fraud_agent(txn_id: str, customer_id: str, pool) -> dict:
    start = datetime.utcnow()
    alerts_created = 0
    flagged_txn_ids = []
    alert_records = []

    try:
        txn = await fetch_one(
            """
            SELECT * FROM transactions WHERE txn_id=$1
            """,
            txn_id,
        )
        if not txn:
            return {"alerts_created": 0, "error": f"Transaction {txn_id} not found"}

        customer = await fetch_one(
            "SELECT risk_profile FROM customers WHERE customer_id=$1",
            customer_id,
        )
        risk_profile = customer["risk_profile"] if customer else "moderate"

        txn_hour = txn["txn_timestamp"].hour
        ticker = txn["ticker"]
        total_value = float(txn["total_value"])
        geo_country = (txn["geo_country"] or "").upper()

        async def _fire(alert_type, severity, source, description):
            nonlocal alerts_created
            aid = await _insert_alert(
                pool, customer_id, txn_id, alert_type, severity, source, description
            )
            alerts_created += 1
            if txn_id not in flagged_txn_ids:
                flagged_txn_ids.append(txn_id)
            alert_records.append({
                "alert_id": aid,
                "alert_type": alert_type,
                "severity": severity,
                "source": source,
                "description": description,
            })

        # Rule 1: large transaction
        if total_value > 50000:
            await _fire(
                "large_txn", "high", "rule",
                f"Large transaction detected: ${total_value:,.2f} for {ticker}.",
            )

        # Rule 2: night-time crypto
        if txn_hour in list(range(23, 24)) + list(range(0, 6)) and ticker in CRYPTO_TICKERS:
            await _fire(
                "geo_anomaly", "medium", "rule",
                f"Crypto transaction ({ticker}) at unusual hour {txn_hour:02d}:00 UTC.",
            )

        # Rule 3: high-risk country
        if geo_country in HIGH_RISK_COUNTRIES:
            await _fire(
                "geo_anomaly", "high", "rule",
                f"Transaction originating from high-risk country: {geo_country}.",
            )

        # Rule 4: rapid transactions (3+ in last 10 min)
        rapid_count = await fetch_one(
            """
            SELECT COUNT(*) AS cnt FROM transactions
            WHERE customer_id=$1
              AND txn_timestamp >= NOW() - INTERVAL '10 minutes'
            """,
            customer_id,
        )
        if rapid_count and rapid_count["cnt"] >= 3:
            await _fire(
                "rapid_txn", "high", "rule",
                f"Rapid transactions detected: {rapid_count['cnt']} transactions in the last 10 minutes.",
            )

        # Rule 5: conservative customer buying large crypto
        if (
            risk_profile == "conservative"
            and ticker in CRYPTO_TICKERS
            and txn["txn_type"] == "buy"
            and total_value > 5000
        ):
            await _fire(
                "risk_breach", "medium", "rule",
                f"Conservative risk profile purchasing ${total_value:,.2f} in crypto ({ticker}).",
            )

        # Rule 6: overdue loan + large buy
        overdue = await fetch_one(
            "SELECT 1 FROM loans WHERE customer_id=$1 AND status='overdue' LIMIT 1",
            customer_id,
        )
        if overdue and txn["txn_type"] == "buy" and total_value > 10000:
            await _fire(
                "large_txn", "low", "rule",
                f"Customer has overdue loan(s) but placed a ${total_value:,.2f} buy order.",
            )

        # Isolation Forest
        history = await fetch_all(
            """
            SELECT total_value, txn_timestamp, ticker, geo_country
            FROM transactions
            WHERE customer_id=$1
              AND txn_timestamp >= NOW() - INTERVAL '90 days'
            ORDER BY txn_timestamp DESC
            """,
            customer_id,
        )

        if len(history) >= 10:
            try:
                from sklearn.ensemble import IsolationForest

                # Determine customer's common geo
                countries = [r["geo_country"] for r in history if r["geo_country"]]
                common_country = max(set(countries), key=countries.count) if countries else None

                def _make_features(rows):
                    feats = []
                    for i, r in enumerate(rows):
                        hour = r["txn_timestamp"].hour
                        is_crypto = 1 if r["ticker"] in CRYPTO_TICKERS else 0
                        row_geo = (r["geo_country"] or "").upper()
                        is_new_geo = 0 if (not common_country or row_geo == common_country) else 1
                        # count txns within 1hr window of this txn
                        ts = r["txn_timestamp"]
                        txn_count_hr = sum(
                            1 for other in rows
                            if abs((other["txn_timestamp"] - ts).total_seconds()) <= 3600
                        )
                        feats.append([
                            float(r["total_value"]),
                            float(hour),
                            float(is_crypto),
                            float(is_new_geo),
                            float(txn_count_hr),
                        ])
                    return np.array(feats)

                hist_features = _make_features(list(history))
                iso = IsolationForest(contamination=0.1, random_state=42)
                iso.fit(hist_features)

                # Score current transaction
                curr_geo = geo_country
                is_new = 0 if (not common_country or curr_geo == common_country) else 1
                curr_hr_count = sum(
                    1 for r in history
                    if abs((r["txn_timestamp"] - txn["txn_timestamp"]).total_seconds()) <= 3600
                ) + 1
                curr_feat = np.array([[
                    total_value,
                    float(txn_hour),
                    float(1 if ticker in CRYPTO_TICKERS else 0),
                    float(is_new),
                    float(curr_hr_count),
                ]])

                scores = iso.decision_function(hist_features)
                min_s, max_s = scores.min(), scores.max()
                raw = iso.decision_function(curr_feat)[0]

                if max_s > min_s:
                    anomaly_score = 1.0 - (raw - min_s) / (max_s - min_s)
                else:
                    anomaly_score = 0.0
                anomaly_score = max(0.0, min(1.0, anomaly_score))

                if anomaly_score > 0.7:
                    await _fire(
                        "ml_anomaly", "high", "ml_model",
                        f"Isolation Forest anomaly score {anomaly_score:.2f} — "
                        f"transaction pattern deviates significantly from customer history.",
                    )

            except Exception as e:
                logger.warning(f"Isolation Forest failed: {e}")

        ms = int((datetime.utcnow() - start).total_seconds() * 1000)
        logger.info(
            f"Fraud agent: customer={customer_id} txn={txn_id} "
            f"alerts={alerts_created} duration={ms}ms"
        )

        return {
            "alerts_created": alerts_created,
            "flagged_txn_ids": flagged_txn_ids,
            "alerts": alert_records,
            "duration_ms": ms,
        }

    except Exception as e:
        logger.error(f"Fraud agent error: customer={customer_id} txn={txn_id} error={e}")
        return {
            "alerts_created": 0,
            "flagged_txn_ids": [],
            "alerts": [],
            "error": str(e),
            "duration_ms": 0,
        }
