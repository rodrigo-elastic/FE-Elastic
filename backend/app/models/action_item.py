"""
filename: action_item.py
description: Pydantic models for ActionItem and Owner.
date: 02-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

from datetime import date
from typing import Optional

from pydantic import BaseModel


class Owner(BaseModel):
    name: str
    email: Optional[str] = None
    role: Optional[str] = None


class ActionItem(BaseModel):
    title: str
    owner: Owner
    due_date: Optional[date] = None
    description: Optional[str] = None
    source_quote: Optional[str] = None
