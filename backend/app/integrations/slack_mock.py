"""
filename: slack_mock.py
description: Mock Slack client. Appends posted messages to runtime/slack.log.
date: 02-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
from datetime import datetime, timezone

from app.config import settings


def post_message(channel: str, text: str, blocks: list | None = None) -> dict:
    log_path = settings.runtime_dir / "slack.log"
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "channel": channel,
        "text": text,
        "blocks": blocks or [],
    }
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
    return {"ok": True, "channel": channel}
