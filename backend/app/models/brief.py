"""
filename: brief.py
description: Pydantic model for the Pre-Meeting Account Brief.
date: 02-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

from typing import List, Optional

from pydantic import BaseModel


class BriefSection(BaseModel):
    heading: str
    bullets: List[str]


class AccountBrief(BaseModel):
    meeting_id: str
    company_id: str
    headline: str
    sections: List[BriefSection]
    pdf_path: Optional[str] = None
    slack_channel: Optional[str] = None
