import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from db.connection import fetch_all

logger = logging.getLogger("routers.websocket")

router = APIRouter()


def _get_ws_clients() -> list:
    import main as m
    return m.connected_ws_clients


def _get_alert_clients() -> list:
    import main as m
    return m.connected_alert_clients


@router.websocket("/ws/dashboard")
async def ws_dashboard(websocket: WebSocket):
    await websocket.accept()
    clients = _get_ws_clients()
    clients.append(websocket)
    logger.info(f"Dashboard WS connected — {len(clients)} total")
    try:
        while True:
            await websocket.receive_text()
            # Reply with heartbeat so client knows the connection is alive
            await websocket.send_text(
                json.dumps({
                    "type": "heartbeat",
                    "ts": datetime.now(timezone.utc).isoformat(),
                })
            )
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning(f"Dashboard WS error: {e}")
    finally:
        try:
            clients.remove(websocket)
        except ValueError:
            pass
        logger.info(f"Dashboard WS disconnected — {len(clients)} remaining")


@router.websocket("/ws/alerts")
async def ws_alerts(websocket: WebSocket):
    await websocket.accept()
    clients = _get_alert_clients()
    clients.append(websocket)
    logger.info(f"Alerts WS connected — {len(clients)} total")

    # Push last 5 open alerts immediately on connect
    try:
        rows = await fetch_all(
            """
            SELECT alert_id, customer_id, alert_type, severity, description, detected_at
            FROM alerts
            WHERE status = 'open'
            ORDER BY detected_at DESC
            LIMIT 5
            """
        )
        for row in rows:
            await websocket.send_text(json.dumps({
                "type":        "alert",
                "alert_id":    row["alert_id"],
                "customer_id": row["customer_id"],
                "alert_type":  row["alert_type"],
                "severity":    row["severity"],
                "description": row["description"][:100],
            }))
    except Exception as e:
        logger.warning(f"Alerts WS initial push failed: {e}")

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning(f"Alerts WS error: {e}")
    finally:
        try:
            clients.remove(websocket)
        except ValueError:
            pass
        logger.info(f"Alerts WS disconnected — {len(clients)} remaining")
