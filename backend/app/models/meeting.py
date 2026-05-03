"""
filename: meeting.py
description: Pydantic models for Meeting and Transcript.
date: 02-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class TranscriptTurn(BaseModel):
    speaker: str
    text: str
    ts_seconds: Optional[float] = None


class Transcript(BaseModel):
    meeting_id: str
    turns: List[TranscriptTurn]


class Meeting(BaseModel):
    id: str
    company_id: str
    title: str
    start_time: datetime
    end_time: datetime
    attendees: List[str]
    notes: Optional[str] = None
