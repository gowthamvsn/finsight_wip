import logging

from fastapi import APIRouter, Depends, HTTPException, status

from auth.jwt_handler import get_current_user
from db.connection import fetch_all

logger = logging.getLogger("routers.reports")

router = APIRouter()


@router.get("/{customer_id}")
async def list_reports(
    customer_id: str,
    current_user: dict = Depends(get_current_user),
):
    if current_user["role"] == "customer" and current_user["sub"] != customer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied — you can only view your own reports",
        )

    rows = await fetch_all(
        """
        SELECT report_id, report_type, generated_by_agent,
               llm_used, blob_url, tokens_used, generated_at, email_sent
        FROM reports
        WHERE customer_id = $1
        ORDER BY generated_at DESC
        """,
        customer_id,
    )
    return [dict(r) for r in rows]
