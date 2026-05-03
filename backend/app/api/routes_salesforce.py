"""
filename: routes_salesforce.py
description: Read endpoints for the Salesforce mock. Lets the dashboard show how many tasks the agent pushed and link to plausible Lightning URLs.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

from typing import Optional

from fastapi import APIRouter

from app.integrations import salesforce_mock
from app.repositories import synthetic

router = APIRouter(prefix="/salesforce", tags=["salesforce"])


@router.get("/tasks")
async def list_tasks(what_id: Optional[str] = None, limit: int = 100) -> dict:
    items = salesforce_mock.list_tasks(what_id=what_id, limit=limit)
    return {"count": len(items), "items": items}


@router.get("/account/{company_id}")
async def get_account(company_id: str) -> dict:
    company = synthetic.find_company(company_id) or {}
    return salesforce_mock.get_account(
        company_id=company_id,
        company_name=company.get("name", ""),
        industry=company.get("industry", ""),
        size=company.get("size", ""),
    )
