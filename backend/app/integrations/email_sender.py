"""
filename: email_sender.py
description: Email sender. Three delivery paths tried in order:
  1) Kibana built-in `.email` connector (Elastic Cloud, no SMTP creds needed)
  2) SMTP (TLS) when SMTP_USER + SMTP_PASSWORD are set
  3) Disk dry-run fallback so the rest of the app always works.
Every send writes a JSON record to runtime/emails/ for audit, regardless of mode.
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
from typing import Any, Dict, List, Optional

from app.config import settings
from app.utils.logging import get_logger

log = get_logger(__name__)


# Cache the discovered Kibana email connector id so we don't refetch on every
# email. Reset to None on connector failure so the next call re-discovers.
_email_connector_cache: Optional[str] = None


def _find_kibana_email_connector() -> Optional[str]:
    """Discover the first `.email` connector registered in Kibana. The Elastic
    Cloud built-in `elastic-cloud-email` is normally available with no SMTP
    setup. Returns the connector id or None if Kibana isn't live."""
    global _email_connector_cache
    if _email_connector_cache:
        return _email_connector_cache
    try:
        from app.integrations import agent_builder as ab  # local import avoids cycles
        if not ab.is_live():
            return None
        connectors = ab._request("GET", "/api/actions/connectors")
        if not isinstance(connectors, list):
            return None
        for c in connectors:
            if c.get("connector_type_id") == ".email" or c.get("actionTypeId") == ".email":
                cid = c.get("id")
                if cid:
                    _email_connector_cache = cid
                    log.info("email.kibana_connector_found", connector_id=cid, name=c.get("name"))
                    return cid
    except Exception as exc:
        log.warning("email.kibana_discover_failed", error=str(exc))
    return None


def _send_via_kibana(to: str, subject: str, body: str) -> Optional[Dict[str, Any]]:
    """Fire the Kibana `.email` connector via Actions API. Returns the
    `{ok, mode, to}` dict on success or None if Kibana isn't reachable so the
    caller can fall through to SMTP."""
    cid = _find_kibana_email_connector()
    if not cid:
        return None
    try:
        from app.integrations import agent_builder as ab
        body_req = {
            "params": {
                "to": [to],
                "subject": subject,
                "message": body,
            }
        }
        result = ab._request("POST", f"/api/actions/connector/{cid}/_execute", body_req)
        if isinstance(result, dict) and result.get("error"):
            log.warning("email.kibana_send_failed", to=to, error=str(result.get("body") or result)[:300])
            return None
        status = (result or {}).get("status") if isinstance(result, dict) else None
        if status and status != "ok":
            log.warning("email.kibana_send_non_ok", to=to, status=status, message=(result or {}).get("message"))
            return None
        log.info("email.sent_via_kibana", to=to, subject=subject, connector_id=cid)
        return {"ok": True, "mode": "kibana", "to": to, "connector_id": cid}
    except Exception as exc:
        log.warning("email.kibana_send_exception", to=to, error=str(exc))
        return None


def send(*, to: str, subject: str, body_markdown: str, meeting_id: str = "") -> dict:
    """Send an email. Tries Kibana .email connector first, then SMTP, then
    falls back to a disk-only dry-run. The disk record is always written so
    every send is auditable regardless of delivery mode."""
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

    if not to:
        return {"ok": True, "mode": "dry-run", "to": to, "reason": "no recipient"}

    # 1) Prefer the Kibana built-in .email connector when Kibana is wired up.
    #    This is the recommended path on Elastic Cloud because it does not need
    #    SMTP credentials or Gmail app passwords.
    kibana_result = _send_via_kibana(to, subject, body_markdown)
    if kibana_result:
        return kibana_result

    # 2) Fall back to direct SMTP when configured locally.
    if settings.smtp_user and settings.smtp_password:
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
            return {"ok": True, "mode": "smtp", "to": to}
        except Exception as exc:
            log.warning("email.smtp_send_failed", to=to, error=str(exc))
            return {"ok": False, "to": to, "mode": "smtp_failed", "error": str(exc)}

    # 3) No delivery channel; record was already written to disk.
    return {"ok": True, "mode": "dry-run", "to": to}
