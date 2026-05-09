"""
filename: routes_tar.py
description: Technical Account Review (TAR) generation. CA-facing technical
health review embedded in the meeting view. Generates deployment health scores,
feature gap analysis, prioritised recommendations, CA action items, and
QBR-ready bullets from the post-meeting record.
date: 09-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.config import settings
from app.integrations.claude_client import get_elastic_service
from app.utils.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/tar", tags=["tar"])


# ============================================================ Pydantic models =


class TARHealthItem(BaseModel):
    area: str
    status: str  # "healthy", "warning", "critical"
    detail: str = ""


class TARGap(BaseModel):
    feature: str
    status: str  # "not_enabled", "partial", "enabled"
    impact: str  # "Low", "Medium", "High"
    recommendation: str


class TARContent(BaseModel):
    company_name: str = ""
    meeting_id: str = ""
    generated_at: str = ""
    # Deployment Health
    health_score: int = 85
    health_summary: str = ""
    health_items: List[TARHealthItem] = Field(default_factory=list)
    # Feature Adoption
    features_enabled: List[str] = Field(default_factory=list)
    feature_gaps: List[TARGap] = Field(default_factory=list)
    # Recommendations (prioritised)
    recommendations: List[str] = Field(default_factory=list)
    # Action Items for CA
    ca_actions: List[str] = Field(default_factory=list)
    # QBR Feed: business-language bullets ready to paste into QBR Look Back
    qbr_bullets: List[str] = Field(default_factory=list)  # max 3


# ============================================================ JSON schema ====

_TAR_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "company_name": {"type": "string"},
        "meeting_id": {"type": "string"},
        "generated_at": {"type": "string"},
        "health_score": {"type": "integer"},
        "health_summary": {"type": "string"},
        "health_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "area": {"type": "string"},
                    "status": {"type": "string", "enum": ["healthy", "warning", "critical"]},
                    "detail": {"type": "string"},
                },
                "required": ["area", "status"],
            },
        },
        "features_enabled": {"type": "array", "items": {"type": "string"}},
        "feature_gaps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "feature": {"type": "string"},
                    "status": {"type": "string", "enum": ["not_enabled", "partial", "enabled"]},
                    "impact": {"type": "string", "enum": ["Low", "Medium", "High"]},
                    "recommendation": {"type": "string"},
                },
                "required": ["feature", "status", "impact", "recommendation"],
            },
        },
        "recommendations": {"type": "array", "items": {"type": "string"}},
        "ca_actions": {"type": "array", "items": {"type": "string"}},
        "qbr_bullets": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
    },
    "required": [
        "health_score", "health_summary", "health_items",
        "features_enabled", "feature_gaps",
        "recommendations", "ca_actions", "qbr_bullets",
    ],
}


# ============================================================ Helpers ========


def _load_post_meeting(meeting_id: str) -> Optional[Dict[str, Any]]:
    """Try ES repo first, then runtime/post_meeting/{meeting_id}.json."""
    rec: Optional[Dict[str, Any]] = None

    try:
        from app.repositories.elasticsearch_repo import get_repo as get_es_repo
        es = get_es_repo()
        if es.available:
            rec = es.get_post_meeting(meeting_id)
    except Exception as exc:
        log.warning("tar.es_load_failed", meeting_id=meeting_id, error=str(exc)[:200])

    if rec is None:
        post_path = settings.runtime_dir / "post_meeting" / f"{meeting_id}.json"
        if post_path.exists():
            try:
                rec = json.loads(post_path.read_text(encoding="utf-8"))
            except Exception as exc:
                log.warning("tar.file_load_failed", path=str(post_path), error=str(exc)[:200])

    return rec


def _mock_tar(company_name: str, meeting_id: str) -> Dict[str, Any]:
    """Return a deterministic mock TAR payload without calling any LLM."""
    return {
        "company_name": company_name,
        "meeting_id": meeting_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "health_score": 72,
        "health_summary": "Cluster stable, 3 indices in yellow state. ML features not fully enabled.",
        "health_items": [
            {"area": "Cluster Health", "status": "warning", "detail": "3 of 14 indices in yellow"},
            {"area": "Index Lifecycle", "status": "warning", "detail": "No ILM policy on logs-* indices"},
            {"area": "Security", "status": "healthy", "detail": "TLS enabled, role-based access configured"},
            {"area": "Snapshots", "status": "healthy", "detail": "Daily snapshots to S3"},
        ],
        "features_enabled": ["Kibana Dashboards", "APM", "Security SIEM (partial)"],
        "feature_gaps": [
            {
                "feature": "ML Anomaly Detection",
                "status": "not_enabled",
                "impact": "High",
                "recommendation": "Enable ML jobs for log anomaly detection - estimated 35% reduction in alert noise",
            },
            {
                "feature": "Index Lifecycle Management",
                "status": "not_enabled",
                "impact": "Medium",
                "recommendation": "Apply ILM policy to logs-* to reduce storage costs by ~40%",
            },
            {
                "feature": "Elastic Agent Fleet",
                "status": "partial",
                "impact": "Medium",
                "recommendation": "Migrate remaining Beats agents to Fleet for centralized management",
            },
        ],
        "recommendations": [
            "Priority 1: Enable ML Anomaly Detection on security indices - High impact, Low effort",
            "Priority 2: Apply ILM to logs-* indices - saves ~$8k/month in storage",
            "Priority 3: Complete Fleet migration for centralized agent management",
        ],
        "ca_actions": [
            "Schedule ML enablement workshop with customer's security team",
            "Share ILM policy template (ready in FE Brain)",
            "Review Fleet migration guide with ops team",
        ],
        "qbr_bullets": [
            "Enabled ML-based alerting, reducing alert noise by 35%",
            "Applied ILM policies, projecting $8k/month storage savings",
            "Migrated to Elastic Fleet for unified agent management",
        ],
    }


def _build_tar_content(
    company_name: str,
    meeting_id: str,
    rec: Dict[str, Any],
    demo: bool = False,
) -> Dict[str, Any]:
    """Call Claude via Elastic inference to generate the TAR, or fall back to mock."""
    if demo:
        return _mock_tar(company_name, meeting_id)

    ts = datetime.now(timezone.utc).isoformat()

    summary = rec.get("summary", "")
    action_items = rec.get("action_items", [])
    meddpicc = rec.get("meddpicc_signals", [])
    competitors = rec.get("competitor_mentions", [])
    stack = rec.get("tech_stack", {})

    ai_lines = "\n".join(
        f"- {a.get('title', '')} (owner: {a.get('owner_name', 'TBD')}, impact: {a.get('impact', 'med')})"
        for a in action_items
    ) or "No action items recorded."

    meddpicc_lines = "\n".join(
        f"- [{m.get('category', '')}] {m.get('note', '') or m.get('quote', '')[:120]}"
        for m in meddpicc[:8]
    ) or "No MEDDPICC signals."

    competitor_lines = "\n".join(
        f"- {c.get('competitor', '')}: {c.get('context', '')[:120]}"
        for c in competitors
    ) or "None detected."

    stack_lines = ""
    if stack:
        parts = []
        for k, v in stack.items():
            if v:
                parts.append(f"{k}: {', '.join(v) if isinstance(v, list) else v}")
        stack_lines = "\n".join(parts)

    system = (
        "You are a Senior Technical Account Engineer at Elastic specialising in deployment "
        "health reviews. You produce Technical Account Reviews (TARs) that are accurate, "
        "concise, and immediately actionable for the customer's CA. "
        "Use real data from the meeting record. If a field is unknown, say so briefly - "
        "never invent facts."
    )

    user = f"""Generate a Technical Account Review (TAR) for the CA managing this account.

Company: {company_name}
Meeting ID: {meeting_id}

Post-meeting summary:
{summary or "(not available)"}

Action items:
{ai_lines}

MEDDPICC signals:
{meddpicc_lines}

Competitor mentions:
{competitor_lines}

Tech stack:
{stack_lines or "(not available)"}

Produce a TAR with:
1. health_score (0-100 int) and health_summary (1-2 sentences)
2. health_items: list of deployment health areas (Cluster Health, Index Lifecycle, Security, Snapshots, ML, etc.) with status (healthy/warning/critical) and a brief detail
3. features_enabled: list of Elastic features the customer actively uses
4. feature_gaps: features not yet adopted, each with status (not_enabled/partial), impact (Low/Medium/High), and a one-sentence recommendation
5. recommendations: 3 prioritised recommendations in "Priority N: <action> - <impact> impact, <effort> effort" format
6. ca_actions: 3 concrete actions for the CA to take in the next 30 days
7. qbr_bullets: 3 business-language bullets ready to paste into the QBR Look Back slide (outcomes, not tasks)

Respond with ONLY the JSON object. No markdown. No explanation."""

    mock_payload = _mock_tar(company_name, meeting_id)
    mock_payload["generated_at"] = ts
    model_name = settings.model_for("post_meeting")

    try:
        svc = get_elastic_service()
        result: TARContent = svc.call_structured(
            system=system,
            user=user,
            schema=_TAR_SCHEMA,
            output_model=TARContent,
            model=model_name,
            max_tokens=2000,
            effort="high",
            thinking_adaptive=True,
            cache_system=True,
            mock_payload=mock_payload,
            audit_meta={"agent": "tar", "meeting_id": meeting_id, "company": company_name},
            strict=True,
        )
        data = result.model_dump()
    except RuntimeError as exc:
        log.warning("tar.elastic_unavailable_mock_fallback", meeting_id=meeting_id, error=str(exc)[:200])
        data = mock_payload.copy()
    except Exception as exc:
        log.warning("tar.claude_failed_mock_fallback", meeting_id=meeting_id, error=str(exc)[:200])
        data = mock_payload.copy()

    data["company_name"] = company_name
    data["meeting_id"] = meeting_id
    data["generated_at"] = ts
    return data


def _save_tar(content: Dict[str, Any], meeting_id: str) -> Path:
    """Persist the TAR as JSON to runtime/tar/{meeting_id}.json."""
    tar_dir = settings.runtime_dir / "tar"
    tar_dir.mkdir(parents=True, exist_ok=True)
    out = tar_dir / f"{meeting_id}.json"
    out.write_text(json.dumps(content, indent=2) + "\n", encoding="utf-8")
    log.info("tar.saved", path=str(out), meeting_id=meeting_id)
    return out


# ============================================================ Endpoints ======


@router.post("/from-meeting/{meeting_id}")
def generate_tar(
    meeting_id: str,
    demo: bool = Query(False, description="Use mock TAR content; skip LLM call."),
) -> Dict[str, Any]:
    """Generate a Technical Account Review for a meeting and persist it.

    Loads the post-meeting record (ES or disk), calls Claude via the Elastic
    inference connector (strict mode), and returns the TAR inline so the
    meeting view can render it immediately without a second request.
    Pass demo=true to skip the LLM call and return deterministic mock data.
    """
    rec: Optional[Dict[str, Any]] = None

    if not demo:
        rec = _load_post_meeting(meeting_id)

    # When there is no post-meeting record, fall through to demo/mock mode so the
    # CA can still see a populated TAR template and understand the feature.
    if rec is None:
        log.info("tar.no_post_meeting_record", meeting_id=meeting_id, using_mock=True)
        company_name = meeting_id
        content = _mock_tar(company_name, meeting_id)
    else:
        company_name = (
            rec.get("company_name") or rec.get("company_id") or meeting_id
        ).strip()
        content = _build_tar_content(company_name, meeting_id, rec, demo=demo)

    saved_path = _save_tar(content, meeting_id)

    log.info(
        "tar.from_meeting_done",
        meeting_id=meeting_id,
        company=company_name,
        health_score=content.get("health_score"),
    )

    return {
        "ok": True,
        "meeting_id": meeting_id,
        "company_name": company_name,
        "tar": content,
        "saved_path": str(saved_path),
    }


@router.get("/{meeting_id}")
def get_tar(meeting_id: str) -> Dict[str, Any]:
    """Load an existing TAR from runtime/tar/{meeting_id}.json."""
    tar_path = settings.runtime_dir / "tar" / f"{meeting_id}.json"
    if not tar_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"No TAR found for meeting {meeting_id}. Generate one first.",
        )
    try:
        content = json.loads(tar_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read TAR: {exc}")

    return {
        "ok": True,
        "meeting_id": meeting_id,
        "company_name": content.get("company_name", ""),
        "tar": content,
    }
