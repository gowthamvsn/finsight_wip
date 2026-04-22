import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from auth.jwt_handler import get_admin_user, get_current_user
from db.connection import execute, fetch_all, fetch_one

logger = logging.getLogger("routers.alerts")

router = APIRouter()


class AlertPatch(BaseModel):
    status: str
    note: Optional[str] = None  # accepted but not stored (no column in schema)


@router.get("")
async def list_alerts(
    severity:    Optional[str] = Query(None),
    status_q:    Optional[str] = Query(None, alias="status"),
    customer_id: Optional[str] = Query(None),
    limit:       int           = Query(50, ge=1, le=500),
    current_user: dict = Depends(get_current_user),
):
    if current_user["role"] == "admin":
        rows = await fetch_all(
            """
            SELECT a.alert_id, a.customer_id, a.txn_id, a.alert_type,
                   a.severity, a.source, a.description, a.status,
                   a.email_sent, a.detected_at, a.updated_at, a.resolved_at,
                   c.first_name, c.last_name
            FROM alerts a
            JOIN customers c ON a.customer_id = c.customer_id
            WHERE ($1::text IS NULL OR a.severity    = $1)
              AND ($2::text IS NULL OR a.status      = $2)
              AND ($3::text IS NULL OR a.customer_id = $3)
            ORDER BY a.detected_at DESC
            LIMIT $4
            """,
            severity, status_q, customer_id, limit,
        )
    else:
        # Customers see only their own alerts — ignore customer_id filter
        cid = current_user["sub"]
        rows = await fetch_all(
            """
            SELECT alert_id, customer_id, txn_id, alert_type,
                   severity, source, description, status,
                   email_sent, detected_at, updated_at, resolved_at
            FROM alerts
            WHERE customer_id = $1
              AND ($2::text IS NULL OR severity = $2)
              AND ($3::text IS NULL OR status   = $3)
            ORDER BY detected_at DESC
            LIMIT $4
            """,
            cid, severity, status_q, limit,
        )

    return [dict(r) for r in rows]


@router.patch("/{alert_id}")
async def update_alert(
    alert_id: str,
    body: AlertPatch,
    current_user: dict = Depends(get_admin_user),
):
    allowed = {"open", "investigating", "resolved", "dismissed"}
    if body.status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"status must be one of: {', '.join(sorted(allowed))}",
        )

    row = await fetch_one(
        """
        UPDATE alerts
        SET status      = $1::VARCHAR,
            updated_at  = NOW(),
            resolved_at = CASE WHEN $1::VARCHAR = 'resolved' THEN NOW() ELSE resolved_at END
        WHERE alert_id  = $2::VARCHAR
        RETURNING alert_id, customer_id, alert_type, severity,
                  status, detected_at, updated_at, resolved_at
        """,
        body.status, alert_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Alert not found")

    logger.info(
        f"Alert {alert_id} updated to status={body.status} by {current_user['sub']}"
    )
    return dict(row)
