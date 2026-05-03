"""
filename: company.py
description: Pydantic models for Company and TechStack.
date: 02-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

from typing import List, Optional

from pydantic import BaseModel, Field


class TechStack(BaseModel):
    observability: List[str] = Field(default_factory=list)
    search: List[str] = Field(default_factory=list)
    cloud: List[str] = Field(default_factory=list)
    other: List[str] = Field(default_factory=list)


class Company(BaseModel):
    id: str
    name: str
    industry: str
    size: str
    headquarters: Optional[str] = None
    website: Optional[str] = None
    tech_stack: TechStack = Field(default_factory=TechStack)
    description: Optional[str] = None
