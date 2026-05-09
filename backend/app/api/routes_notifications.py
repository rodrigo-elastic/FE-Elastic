"""
filename: routes_notifications.py
description: Notification relay endpoints. Receives webhook calls from Kibana alerting rules
and logs/forwards email notifications. Kibana cannot call SMTP directly from a .webhook
connector, so we receive the fire here and handle delivery.
date: 09-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Request

from app.config import settings
from app.utils.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _append_notification(record: Dict[str, Any]) -> None:
    try:
        path = settings.runtime_dir / "notification_log.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except Exception as exc:
        log.warning("notifications.log_failed", error=str(exc))


@router.post("/email")
async def receive_email_notification(request: Request) -> Dict[str, Any]:
    """Relay endpoint called by the Kibana email-webhook connector when a rule fires.

    Kibana resolves Mustache templates in the body before POSTing here.
    We log the notification and optionally deliver it via SMTP when configured.
    """
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    received_at = datetime.now(timezone.utc).isoformat()
    to = (payload or {}).get("to") or ""
    rule_name = (payload or {}).get("rule_name") or "FE Copilot Rule"
    subject = (payload or {}).get("subject") or f"FE Copilot: {rule_name}"
    message = (payload or {}).get("message") or ""

    log.info("notifications.email.received", to=to, rule=rule_name)

    record = {
        "received_at": received_at,
        "channel": "email",
        "to": to,
        "subject": subject,
        "message": message,
        "rule_name": rule_name,
        "payload": payload,
        "delivered": False,
    }

    # Best-effort SMTP delivery when credentials are present.
    smtp_host = getattr(settings, "smtp_host", "")
    smtp_user = getattr(settings, "smtp_user", "")
    smtp_pass = getattr(settings, "smtp_password", "")
    notify_from = getattr(settings, "notify_from", smtp_user)
    if smtp_host and smtp_user and smtp_pass and to:
        try:
            import smtplib
            from email.mime.text import MIMEText

            msg = MIMEText(message, "plain")
            msg["Subject"] = subject
            msg["From"] = notify_from
            msg["To"] = to
            smtp_port = int(getattr(settings, "smtp_port", 587))
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.sendmail(notify_from, [to], msg.as_string())
            record["delivered"] = True
            record["delivery_mode"] = "smtp"
            log.info("notifications.email.sent", to=to)
        except Exception as exc:
            log.warning("notifications.email.smtp_failed", error=str(exc)[:200])
            record["delivery_error"] = str(exc)[:200]
    else:
        record["delivery_mode"] = "logged-only"

    _append_notification(record)
    return {"ok": True, "received_at": received_at, "to": to, "delivered": record["delivered"]}


@router.get("/log")
def get_notification_log(limit: int = 20) -> Dict[str, Any]:
    """Return recent notification deliveries."""
    bounded = max(1, min(200, limit))
    path = settings.runtime_dir / "notification_log.jsonl"
    if not path.exists():
        return {"ok": True, "notifications": []}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return {"ok": True, "notifications": []}
    out = []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
        if len(out) >= bounded:
            break
    return {"ok": True, "notifications": out}
