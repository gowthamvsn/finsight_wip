import asyncio
import logging
import os

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(), override=True)

logger = logging.getLogger("email_sender")


def get_client():
    conn_str = os.getenv("AZURE_EMAIL_CONNECTION_STRING")
    if not conn_str:
        logger.warning(
            "AZURE_EMAIL_CONNECTION_STRING not set — email sending disabled"
        )
        return None
    try:
        from azure.communication.email import EmailClient
        return EmailClient.from_connection_string(conn_str)
    except Exception as e:
        logger.error(f"Email client init failed: {e}")
        return None


def _send_message(client, message: dict) -> str:
    """Synchronous send — called via asyncio.to_thread."""
    poller = client.begin_send(message)
    result = poller.result()
    return result.get("id", "unknown")


async def send_alert_email(
    to_email: str,
    customer_name: str,
    alert_type: str,
    description: str,
    otp: str = None,
) -> bool:
    client = get_client()
    if not client:
        logger.info(f"[EMAIL SKIPPED] Alert to {to_email}: {description}")
        return False
    try:
        subject = f"FinSight Alert: {alert_type.replace('_', ' ').title()}"
        body = (
            f"Dear {customer_name},\n\n"
            f"{description}\n\n"
            + (f"Your OTP: {otp}\n\n" if otp else "")
            + "Please log in to FinSight to review this alert.\n\n"
            "FinSight Security Team"
        )
        message = {
            "senderAddress": os.getenv("AZURE_SENDER_EMAIL", "noreply@finsight.com"),
            "recipients": {"to": [{"address": to_email}]},
            "content": {"subject": subject, "plainText": body},
        }
        msg_id = await asyncio.to_thread(_send_message, client, message)
        logger.info(f"Alert email sent to {to_email}: {msg_id}")
        return True
    except Exception as e:
        logger.error(f"Email send failed: {e}")
        return False


async def send_report_email(
    to_email: str,
    customer_name: str,
    report_type: str,
    blob_url: str,
) -> bool:
    client = get_client()
    if not client:
        logger.info(f"[EMAIL SKIPPED] Report to {to_email}: {blob_url}")
        return False
    try:
        body = (
            f"Dear {customer_name},\n\n"
            f"Your {report_type.replace('_', ' ')} has been generated.\n\n"
            f"Download: {blob_url}\n\n"
            "FinSight Advisory Team"
        )
        message = {
            "senderAddress": os.getenv("AZURE_SENDER_EMAIL", "noreply@finsight.com"),
            "recipients": {"to": [{"address": to_email}]},
            "content": {
                "subject": f"Your FinSight {report_type.replace('_', ' ').title()} is Ready",
                "plainText": body,
            },
        }
        await asyncio.to_thread(_send_message, client, message)
        return True
    except Exception as e:
        logger.error(f"Report email failed: {e}")
        return False
