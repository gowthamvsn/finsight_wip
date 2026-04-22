import asyncio
import logging
import os

logger = logging.getLogger("email_otp")


def _get_azure_client():
    conn_str = os.getenv("AZURE_EMAIL_CONNECTION_STRING")
    if not conn_str:
        return None
    try:
        from azure.communication.email import EmailClient
        return EmailClient.from_connection_string(conn_str)
    except Exception as e:
        logger.error(f"Azure email client init failed: {e}")
        return None


ALERT_EMAIL = "koolestue@gmail.com"

async def send_otp_email(to_email: str, customer_name: str, otp: str, reasons: list) -> bool:
    to_email = ALERT_EMAIL  # always route OTP alerts to the ops mailbox
    reasons_text = "\n".join(f"  • {r}" for r in reasons)
    body_text = f"""Dear {customer_name},

A transaction on your FinSight account requires verification due to:
{reasons_text}

Your One-Time Password (OTP): {otp}

This OTP expires in 5 minutes. Do not share it with anyone.

If you did not initiate this transaction, please contact support immediately.

FinSight Security Team"""

    # Always log OTP to backend console for debugging/demo
    logger.info(f"[OTP] To: {to_email} | OTP: {otp} | Reasons: {reasons}")

    client = _get_azure_client()
    if not client:
        logger.warning(f"[EMAIL DEMO MODE] Azure not configured — OTP {otp} would be sent to {to_email}")
        return False

    sender = os.getenv("AZURE_SENDER_EMAIL", "DoNotReply@finsight.com")
    message = {
        "senderAddress": sender,
        "recipients": {"to": [{"address": to_email}]},
        "content": {
            "subject": "FinSight — Transaction Verification OTP",
            "plainText": body_text,
        },
    }

    try:
        def _send():
            poller = client.begin_send(message)
            result = poller.result()
            if result.get("status", "").lower() != "succeeded":
                raise RuntimeError(f"Azure email status: {result.get('status')}")
            return result

        await asyncio.to_thread(_send)
        logger.info(f"OTP email sent via Azure to {to_email}")
        return True
    except Exception as e:
        logger.error(f"OTP email failed: {e}")
        return False
