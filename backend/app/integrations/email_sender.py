"""
filename: email_sender.py
description: Email sender. Uses SMTP (TLS) when SMTP_USER + SMTP_PASSWORD are set;
falls back to writing the message to runtime/emails/ so the rest of the app always works.
date: 08-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings
from app.utils.logging import get_logger

log = get_logger(__name__)


def send(*, to: str, subject: str, body_markdown: str, meeting_id: str = "") -> dict:
    """Send an email. Falls back to disk if SMTP is not configured."""
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "to": to,
        "subject": subject,
        "body": body_markdown,
        "meeting_id": meeting_id,
    }
    out_dir = settings.runtime_dir / "emails"
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{meeting_id or datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}.json"
    (out_dir / fname).write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")

    if not (settings.smtp_user and settings.smtp_password and to):
        return {"ok": True, "mode": "dry-run", "to": to}

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = settings.smtp_user
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body_markdown, "plain", "utf-8"))

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.smtp_user, [to], msg.as_string())

        log.info("email.sent", to=to, subject=subject)
        return {"ok": True, "mode": "live", "to": to}
    except Exception as exc:
        log.warning("email.send_failed", to=to, error=str(exc))
        return {"ok": False, "to": to, "error": str(exc)}
