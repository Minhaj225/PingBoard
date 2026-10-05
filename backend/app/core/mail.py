"""Outbound email.

With no SMTP host configured the message is written to the log instead of
sent, which keeps local development free of external dependencies. Phase 4
swaps the transport for a real provider without touching call sites.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger(__name__)


async def send_email(*, to: str, subject: str, body: str) -> None:
    settings = get_settings()

    if not settings.SMTP_HOST:
        logger.info(
            "email suppressed (no SMTP_HOST configured)",
            extra={"mail_to": to, "mail_subject": subject, "mail_body": body},
        )
        return

    message = EmailMessage()
    message["From"] = settings.SMTP_FROM
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)

    # smtplib is blocking; keep it off the event loop.
    await asyncio.to_thread(_send_sync, message)


def _send_sync(message: EmailMessage) -> None:
    settings = get_settings()
    assert settings.SMTP_HOST is not None  # guarded by the caller

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
        if settings.SMTP_TLS:
            smtp.starttls()
        if settings.SMTP_USER and settings.SMTP_PASSWORD:
            smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        smtp.send_message(message)
