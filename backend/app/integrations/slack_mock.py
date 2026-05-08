"""
filename: slack_mock.py
description: Slack client. Posts to a real Incoming Webhook when SLACK_WEBHOOK_URL is set;
falls back to appending to runtime/slack.log so the rest of the app always works.
date: 02-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
from datetime import datetime, timezone

import httpx

from app.config import settings
from app.utils.logging import get_logger

log = get_logger(__name__)


def post_message(channel: str, text: str, blocks: list | None = None) -> dict:
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "channel": channel,
        "text": text,
        "blocks": blocks or [],
    }
    # Always write to local log (audit trail regardless of webhook mode).
    log_path = settings.runtime_dir / "slack.log"
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")

    webhook_url = settings.slack_webhook_url
    if not webhook_url:
        return {"ok": True, "channel": channel, "mode": "dry-run"}

    payload: dict = {"text": text}
    if blocks:
        payload["blocks"] = blocks

    try:
        resp = httpx.post(webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
        log.info("slack.sent", channel=channel, status=resp.status_code)
        return {"ok": True, "channel": channel, "mode": "live"}
    except Exception as exc:
        log.warning("slack.send_failed", error=str(exc))
        return {"ok": False, "channel": channel, "error": str(exc)}
