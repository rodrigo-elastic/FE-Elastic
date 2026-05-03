"""
filename: routes_tools.py
description: Endpoints for the FE-specific technical tools panel (POC plan, SPL to ES|QL, compliance mapping, stack extraction, code samples, TCO calculator, capacity planner). Each Claude-backed tool is a single structured call; the calculators run in pure Python.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.prompts import language_instruction, language_preamble
from app.agents.prompts import tools as tool_prompts
from app.agents.schemas import (
    CodeSampleOut,
    ComplianceMappingsOut,
    POCPlanOut,
    SPLToESQLOut,
    StackExtractOut,
)
from app.config import settings
from app.integrations.claude_client import get_service
from app.repositories import synthetic
from app.services import calculators
from app.utils.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/tools", tags=["tools"])


# ============================================================ Request models =========


class POCPlanRequest(BaseModel):
    language: Optional[str] = Field("English", max_length=40)
    model: Optional[str] = Field("", max_length=60)


class SPLToESQLRequest(BaseModel):
    spl: str = Field(..., min_length=3, max_length=20000)
    language: Optional[str] = Field("English", max_length=40)
    model: Optional[str] = Field("", max_length=60)


class ComplianceRequest(BaseModel):
    regulations: List[str] = Field(..., min_length=1, max_length=6)
    industry: Optional[str] = Field("", max_length=120)
    language: Optional[str] = Field("English", max_length=40)
    model: Optional[str] = Field("", max_length=60)


class StackExtractRequest(BaseModel):
    text: str = Field(..., min_length=20, max_length=200000)
    language: Optional[str] = Field("English", max_length=40)
    model: Optional[str] = Field("", max_length=60)


class CodeSampleRequest(BaseModel):
    language: str = Field(..., min_length=1, max_length=60, description="Programming language for the sample.")
    use_case: str = Field(..., min_length=3, max_length=400)
    response_language: Optional[str] = Field("English", max_length=40, description="Output prose language.")
    model: Optional[str] = Field("", max_length=60)


class CostCalcRequest(BaseModel):
    ingest_gb_day: float = Field(..., gt=0)
    retention_months: int = Field(..., gt=0, le=120)
    hot_pct: Optional[float] = Field(30.0, ge=0, le=100)
    warm_pct: Optional[float] = Field(30.0, ge=0, le=100)
    frozen_pct: Optional[float] = Field(40.0, ge=0, le=100)
    current_spend_annual_usd: Optional[float] = Field(None, ge=0)


class CapacityRequest(BaseModel):
    peak_indexing_eps: int = Field(..., gt=0)
    hot_data_gb: int = Field(..., gt=0)
    warm_data_gb: Optional[int] = Field(0, ge=0)
    replicas: Optional[int] = Field(1, ge=0, le=5)
    peak_qps: Optional[int] = Field(100, ge=0)


# ============================================================ Helpers ================


def _resolve_model(model: Optional[str]) -> str:
    return (model or "").strip() or settings.model_default


def _post_meeting_path(meeting_id: str):
    return settings.runtime_dir / "post_meeting" / f"{meeting_id}.json"


# ============================================================ Mock fixtures ==========


_POC_PLAN_MOCK: Dict[str, Any] = {
    "executive_summary": "Mock POC plan validating ingest, search, and SIEM use cases over 6 weeks.",
    "success_criteria": [
        {
            "metric": "Ingest throughput",
            "target": "Sustain 25k EPS for 30 minutes",
            "source_quote": "We need to prove we can keep up with our peak load.",
        }
    ],
    "phases": [
        {
            "name": "Phase 1 - Foundation",
            "weeks": "Week 1-2",
            "activities": ["Provision Elastic Cloud deployment", "Configure data ingestion pipelines"],
            "deliverables": ["Working dev cluster", "Initial dashboards"],
            "technical_owners": {
                "elastic": ["FE Lead"],
                "customer": ["Platform Engineer"],
            },
        }
    ],
    "resource_requests": {
        "fe_hours": "60 hours",
        "customer_hours": "40 hours",
        "infrastructure": "Elastic Cloud Standard tier dev cluster",
    },
    "risks": [
        {
            "description": "Schema mismatch between current pipeline and Elastic ECS",
            "mitigation": "Use ingest pipelines and runtime fields to bridge fields.",
        }
    ],
}

_SPL_ESQL_MOCK: Dict[str, Any] = {
    "esql": "FROM logs | WHERE message LIKE \"%error%\" | LIMIT 10",
    "explanation": "Mock fallback translation for offline mode.",
    "caveats": ["mock mode active"],
}

_COMPLIANCE_MOCK: Dict[str, Any] = {
    "mappings": [
        {
            "regulation": "Mock Regulation",
            "industry_note": "Demo mock; replace by configuring an Anthropic API key.",
            "requirements": [
                {
                    "requirement": "Audit log retention",
                    "elastic_control": "Frozen tier on object storage",
                    "native": True,
                }
            ],
        }
    ]
}

_STACK_EXTRACT_MOCK: Dict[str, Any] = {
    "observability": [{"name": "Splunk", "evidence": "mock evidence"}],
    "search": [],
    "cloud": [{"name": "AWS", "evidence": "mock evidence"}],
    "data": [],
    "languages": [],
    "frameworks": [],
}

_CODE_SAMPLE_MOCK: Dict[str, Any] = {
    "title": "Mock Elastic ingest sample",
    "code": "# mock fallback\nfrom elasticsearch import Elasticsearch\nes = Elasticsearch('https://example.es.io', api_key='YOUR_API_KEY')\nprint(es.info())\n",
    "explanation": "Mock fallback code sample served while offline.",
    "prerequisites": ["pip install elasticsearch", "set ELASTIC_API_KEY"],
}


# ============================================================ Routes =================


@router.post("/poc-plan/{meeting_id}")
async def run_poc_plan(meeting_id: str, payload: POCPlanRequest) -> Dict[str, Any]:
    """Generate a POC/POV plan grounded in the meeting + post-meeting record."""
    meeting = synthetic.find_meeting(meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail=f"meeting {meeting_id} not found")
    company = synthetic.find_company(meeting["company_id"])
    if company is None:
        raise HTTPException(status_code=404, detail=f"company {meeting['company_id']} not found")
    post_path = _post_meeting_path(meeting_id)
    if not post_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"post-meeting record missing for {meeting_id}; run the post-meeting agent first",
        )
    try:
        post = json.loads(post_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"could not load post-meeting record: {exc}")

    language = payload.language or "English"
    log.info("tool.poc_plan.start", meeting_id=meeting_id, language=language)

    user_prompt = (
        language_preamble(language)
        + tool_prompts.render_poc_plan_prompt(company, meeting, post)
        + language_instruction(language)
    )

    result: POCPlanOut = get_service().call_structured(
        system=tool_prompts.POC_PLAN_SYSTEM,
        user=user_prompt,
        schema=tool_prompts.POC_PLAN_SCHEMA,
        output_model=POCPlanOut,
        model=_resolve_model(payload.model),
        max_tokens=8192,
        effort="high",
        mock_payload=_POC_PLAN_MOCK,
        audit_meta={
            "agent": "tool_poc_plan",
            "tool": "poc_plan",
            "meeting_id": meeting_id,
            "company_id": company["id"],
        },
    )

    data = result.model_dump()
    record = {
        "meeting_id": meeting_id,
        "company_id": company["id"],
        "language": language,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **data,
    }

    out_dir = settings.runtime_dir / "poc_plans"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{meeting_id}.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    log.info("tool.poc_plan.complete", meeting_id=meeting_id, phases=len(data["phases"]))
    return record


@router.post("/spl-to-esql")
async def run_spl_to_esql(payload: SPLToESQLRequest) -> Dict[str, Any]:
    """Translate a Splunk SPL query into Elastic ES|QL."""
    language = payload.language or "English"
    user_prompt = (
        language_preamble(language)
        + tool_prompts.render_spl_prompt(payload.spl)
        + language_instruction(language)
    )

    result: SPLToESQLOut = get_service().call_structured(
        system=tool_prompts.SPL_ESQL_SYSTEM,
        user=user_prompt,
        schema=tool_prompts.SPL_ESQL_SCHEMA,
        output_model=SPLToESQLOut,
        model=_resolve_model(payload.model),
        max_tokens=4096,
        effort="medium",
        mock_payload=_SPL_ESQL_MOCK,
        audit_meta={"agent": "tool_spl_esql", "tool": "spl_to_esql"},
    )
    return result.model_dump()


@router.post("/compliance-mapping")
async def run_compliance_mapping(payload: ComplianceRequest) -> Dict[str, Any]:
    """Map regulations to native Elastic controls."""
    language = payload.language or "English"
    industry = (payload.industry or "").strip()
    user_prompt = (
        language_preamble(language)
        + tool_prompts.render_compliance_prompt(payload.regulations, industry)
        + language_instruction(language)
    )

    result: ComplianceMappingsOut = get_service().call_structured(
        system=tool_prompts.COMPLIANCE_SYSTEM,
        user=user_prompt,
        schema=tool_prompts.COMPLIANCE_SCHEMA,
        output_model=ComplianceMappingsOut,
        model=_resolve_model(payload.model),
        max_tokens=6144,
        effort="high",
        mock_payload=_COMPLIANCE_MOCK,
        audit_meta={
            "agent": "tool_compliance",
            "tool": "compliance_mapping",
            "regulations": payload.regulations,
            "industry": industry,
        },
    )
    return result.model_dump()


@router.post("/stack-extract")
async def run_stack_extract(payload: StackExtractRequest) -> Dict[str, Any]:
    """Extract a customer's tech stack from raw text."""
    language = payload.language or "English"
    user_prompt = (
        language_preamble(language)
        + tool_prompts.render_stack_prompt(payload.text)
        + language_instruction(language)
    )

    result: StackExtractOut = get_service().call_structured(
        system=tool_prompts.STACK_SYSTEM,
        user=user_prompt,
        schema=tool_prompts.STACK_SCHEMA,
        output_model=StackExtractOut,
        model=_resolve_model(payload.model),
        max_tokens=4096,
        effort="medium",
        mock_payload=_STACK_EXTRACT_MOCK,
        audit_meta={"agent": "tool_stack_extract", "tool": "stack_extract"},
    )
    return result.model_dump()


@router.post("/code-sample")
async def run_code_sample(payload: CodeSampleRequest) -> Dict[str, Any]:
    """Generate a runnable code sample for a target programming language and use case."""
    response_language = payload.response_language or "English"
    user_prompt = (
        language_preamble(response_language)
        + tool_prompts.render_code_sample_prompt(payload.language, payload.use_case)
        + language_instruction(response_language)
    )

    result: CodeSampleOut = get_service().call_structured(
        system=tool_prompts.CODE_SAMPLE_SYSTEM,
        user=user_prompt,
        schema=tool_prompts.CODE_SAMPLE_SCHEMA,
        output_model=CodeSampleOut,
        model=_resolve_model(payload.model),
        max_tokens=4096,
        effort="medium",
        mock_payload=_CODE_SAMPLE_MOCK,
        audit_meta={
            "agent": "tool_code_sample",
            "tool": "code_sample",
            "programming_language": payload.language,
        },
    )
    return result.model_dump()


@router.post("/cost-calc")
async def run_cost_calc(payload: CostCalcRequest) -> Dict[str, Any]:
    """Pure-Python TCO comparison: Elastic vs Splunk vs Datadog."""
    try:
        return calculators.estimate_tco(
            ingest_gb_day=payload.ingest_gb_day,
            retention_months=payload.retention_months,
            hot_pct=payload.hot_pct if payload.hot_pct is not None else 30.0,
            warm_pct=payload.warm_pct if payload.warm_pct is not None else 30.0,
            frozen_pct=payload.frozen_pct if payload.frozen_pct is not None else 40.0,
            current_spend_annual_usd=payload.current_spend_annual_usd,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/capacity")
async def run_capacity(payload: CapacityRequest) -> Dict[str, Any]:
    """Pure-Python heuristic Elastic Cloud cluster sizing."""
    try:
        return calculators.plan_cluster(
            peak_indexing_eps=payload.peak_indexing_eps,
            hot_data_gb=payload.hot_data_gb,
            warm_data_gb=payload.warm_data_gb if payload.warm_data_gb is not None else 0,
            replicas=payload.replicas if payload.replicas is not None else 1,
            peak_qps=payload.peak_qps if payload.peak_qps is not None else 100,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
