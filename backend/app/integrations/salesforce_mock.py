"""
filename: salesforce_mock.py
description: Salesforce REST mock. The function signatures mirror SFDC's Task / Account / Opportunity shapes so swapping for the real client is a one-file change.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.config import settings


def _log_path() -> "object":
    return settings.runtime_dir / "salesforce.log"


# --------------------------------------------------------------- task creation

def create_task(
    *,
    subject: str,
    owner: str,
    due_date: str,
    description: str = "",
    what_id: Optional[str] = None,
    account_id: Optional[str] = None,
    priority: str = "Normal",
    status: str = "Not Started",
    activity_type: str = "Other",
    impact: Optional[str] = None,
) -> Dict[str, Any]:
    """Mirror of `POST /services/data/v60.0/sobjects/Task`.

    Returns SFDC-shaped {ok, task_id, url, attributes} so the dashboard footer
    can render plausible Salesforce links.
    """
    task_id = "00T" + uuid.uuid4().hex[:15].upper()
    record = {
        "Id": task_id,
        "Subject": subject,
        "OwnerName": owner,
        "ActivityDate": due_date,
        "Description": description,
        "WhatId": what_id,
        "AccountId": account_id,
        "Priority": priority,
        "Status": status,
        "Type": activity_type,
        "TaskSubtype": "Task",
        # Custom field naming in our pretend org.
        "Impact__c": impact,
        "CreatedDate": datetime.now(timezone.utc).isoformat(),
        "Url": f"https://example.lightning.force.com/lightning/r/Task/{task_id}/view",
    }
    log_path = _log_path()
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
    return {
        "ok": True,
        "task_id": task_id,
        "url": record["Url"],
        "attributes": {"type": "Task"},
    }


# ----------------------------------------------------------------------- read

def list_tasks(*, what_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    log_path = _log_path()
    if not log_path.exists():
        return []
    out: List[Dict[str, Any]] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if what_id and rec.get("WhatId") != what_id:
            continue
        out.append(rec)
    out.reverse()
    return out[:limit]


def get_account(company_id: str, company_name: str = "", industry: str = "", size: str = "") -> Dict[str, Any]:
    """Synthesise an Account record from the synthetic catalog. Stand-in for `GET /sobjects/Account/{id}`."""
    account_id = "001" + (company_id.replace("-", "")[:15].upper().ljust(15, "0"))
    return {
        "Id": account_id,
        "Name": company_name or company_id,
        "Industry": industry or "Unknown",
        "NumberOfEmployees": _employees_from_size(size),
        "OwnerName": "Field Engineering",
        "Type": "Customer",
        "Url": f"https://example.lightning.force.com/lightning/r/Account/{account_id}/view",
    }


def _employees_from_size(size: str) -> str:
    if not size:
        return "n/a"
    s = size.lower()
    if "1k-5k" in s or "mid" in s:
        return "1,000-5,000"
    if "5k+" in s or "enterprise" in s:
        return "5,000+"
    if "smb" in s or "100-1k" in s:
        return "100-1,000"
    return size


# ---------------------------------------------------- Opportunity + extended writes

def get_opportunity(account_id: str, company_name: str = "") -> Dict[str, Any]:
    """Synthesise an Opportunity record. Stand-in for `GET /sobjects/Opportunity/{id}`."""
    opp_id = "006" + (account_id.replace("-", "")[3:18].upper().ljust(15, "0"))
    return {
        "Id": opp_id,
        "AccountId": account_id,
        "Name": f"{company_name or 'Account'} - Observability Consolidation FY27",
        "StageName": "Proposal/Price Quote",
        "Amount": 1_200_000,
        "Probability": 35,
        "CloseDate": "2026-09-30",
        "OwnerName": "Field Engineering",
        "Type": "New Business",
        "Url": f"https://example.lightning.force.com/lightning/r/Opportunity/{opp_id}/view",
    }


def create_content_note(*, opportunity_id: str, account_id: str, title: str, body: str) -> Dict[str, Any]:
    """SFDC ContentNote (`POST /sobjects/ContentNote`). Linked to the Opportunity via ContentDocumentLink."""
    note_id = "069" + uuid.uuid4().hex[:15].upper()
    record = {
        "_action": "ContentNote.create",
        "Id": note_id,
        "Title": title,
        "Content": body,
        "OwnerName": "Field Engineering",
        "LinkedEntityId": opportunity_id,
        "AccountId": account_id,
        "CreatedDate": datetime.now(timezone.utc).isoformat(),
        "Url": f"https://example.lightning.force.com/lightning/r/ContentNote/{note_id}/view",
    }
    with _log_path().open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
    return {"ok": True, "note_id": note_id, "url": record["Url"]}


# Maps our MEDDPICC schema enums → typical custom field API names you'd see on
# SFDC orgs that have one of the popular MEDDPICC managed packages installed.
MEDDPICC_FIELD_MAP = {
    "Metrics": "Metrics__c",
    "Economic Buyer": "Economic_Buyer__c",
    "Decision Criteria": "Decision_Criteria__c",
    "Decision Process": "Decision_Process__c",
    "Identify Pain": "Identify_Pain__c",
    "Champion": "Champion__c",
    "Competition": "Competition__c",
}


def update_opp_meddpicc(*, opportunity_id: str, signals: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compose a MEDDPICC field-update PATCH against the Opportunity.

    Picks the strongest signal per category (longest quote) and writes it to the
    matching custom field. Also writes a long-text 'evidence' field with the
    verbatim quote so reviewers can audit the update.
    """
    by_cat: Dict[str, Dict[str, Any]] = {}
    for s in signals or []:
        cat = (s.get("category") or "").strip()
        if cat not in MEDDPICC_FIELD_MAP:
            continue
        existing = by_cat.get(cat)
        if not existing or len(s.get("quote") or "") > len(existing.get("quote") or ""):
            by_cat[cat] = s

    fields_updated: Dict[str, str] = {}
    evidence_lines: List[str] = []
    for cat, s in by_cat.items():
        quote = (s.get("quote") or "").strip()
        note = (s.get("note") or "").strip() or quote[:160]
        api_name = MEDDPICC_FIELD_MAP[cat]
        # The field value is the curated note; full quote goes into the evidence trail.
        fields_updated[api_name] = note[:255]
        evidence_lines.append(f"[{cat}] \"{quote}\"")

    record = {
        "_action": "Opportunity.update.meddpicc",
        "OpportunityId": opportunity_id,
        "Fields": fields_updated,
        "MEDDPICC_Evidence__c": "\n\n".join(evidence_lines)[:32000],
        "UpdatedAt": datetime.now(timezone.utc).isoformat(),
        "Url": f"https://example.lightning.force.com/lightning/r/Opportunity/{opportunity_id}/view",
    }
    with _log_path().open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
    return {
        "ok": True,
        "opportunity_id": opportunity_id,
        "fields_updated": list(fields_updated.keys()),
        "evidence_chars": sum(len(v) for v in fields_updated.values()),
        "url": record["Url"],
    }


def attach_content_document(*, opportunity_id: str, file_path: str, title: str) -> Dict[str, Any]:
    """SFDC ContentVersion + ContentDocumentLink (`POST /sobjects/ContentVersion`).

    Mock only: records the link without uploading binary content.
    """
    doc_id = "068" + uuid.uuid4().hex[:15].upper()
    record = {
        "_action": "ContentDocument.attach",
        "Id": doc_id,
        "Title": title,
        "PathOnClient": file_path,
        "LinkedEntityId": opportunity_id,
        "CreatedDate": datetime.now(timezone.utc).isoformat(),
        "Url": f"https://example.lightning.force.com/lightning/r/ContentDocument/{doc_id}/view",
    }
    with _log_path().open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
    return {"ok": True, "content_document_id": doc_id, "url": record["Url"]}


def update_competitor(*, opportunity_id: str, primary: str, others: Optional[List[str]] = None) -> Dict[str, Any]:
    """Updates the `Primary_Competitor__c` field plus a long-text history."""
    record = {
        "_action": "Opportunity.update.competitor",
        "OpportunityId": opportunity_id,
        "Primary_Competitor__c": primary,
        "Competitor_History__c": ", ".join((others or [])[:5]),
        "UpdatedAt": datetime.now(timezone.utc).isoformat(),
    }
    with _log_path().open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
    return {"ok": True, "opportunity_id": opportunity_id, "primary": primary, "others": others or []}


def update_deal_health(*, opportunity_id: str, score: int, max_score: int = 7) -> Dict[str, Any]:
    """Updates a custom Deal_Health_Score__c (0..100) derived from MEDDPICC completeness."""
    pct = int(round((score / max(1, max_score)) * 100))
    record = {
        "_action": "Opportunity.update.deal_health",
        "OpportunityId": opportunity_id,
        "Deal_Health_Score__c": pct,
        "MEDDPICC_Categories_Captured__c": score,
        "UpdatedAt": datetime.now(timezone.utc).isoformat(),
    }
    with _log_path().open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
    return {"ok": True, "opportunity_id": opportunity_id, "deal_health_pct": pct, "score": score}


def post_to_slack(*, channel: str, opportunity_id: str, text: str, brief_url: Optional[str] = None) -> Dict[str, Any]:
    """SF-Slack connector: post a deal-channel message."""
    record = {
        "_action": "Slack.post",
        "Channel": channel,
        "OpportunityId": opportunity_id,
        "Text": text[:4000],
        "BriefUrl": brief_url,
        "PostedAt": datetime.now(timezone.utc).isoformat(),
    }
    with _log_path().open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
    return {"ok": True, "channel": channel, "opportunity_id": opportunity_id}
