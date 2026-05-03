"""
filename: calendar_mock.py
description: Mock Google Calendar feed. Reads synthetic calendar events from JSON.
date: 02-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
from pathlib import Path

CALENDAR_PATH = Path(__file__).resolve().parents[2] / "data" / "synthetic" / "calendar.json"


def list_events() -> list:
    if not CALENDAR_PATH.exists():
        return []
    return json.loads(CALENDAR_PATH.read_text(encoding="utf-8"))
