"""
filename: email_drafter.py
description: Persists the follow-up email draft produced by the Post-Meeting agent.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from app.config import settings


def save(*, meeting_id: str, email: Dict[str, Any], to: list[str]) -> Path:
    out_dir = settings.runtime_dir / "emails"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{meeting_id}.json"
    record = {
        "meeting_id": meeting_id,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "to": to,
        "subject": email["subject"],
        "body_markdown": email["body_markdown"],
    }
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
