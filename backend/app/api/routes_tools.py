"""
filename: routes_tools.py
description: Endpoints for the FE-specific technical tools panel (POC plan, SPL to ES|QL, compliance mapping, stack extraction, code samples, TCO calculator, capacity planner). Each Claude-backed tool is a single structured call; the calculators run in pure Python.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.prompts import language_instruction, language_preamble
from app.agents.prompts import tools as tool_prompts
from app.agents.schemas import (
    CodeSampleOut,
    ComplianceMappingsOut,
    OrchestratorInvocation,
    OrchestratorOut,
    OrchestratorPlanOut,
    OrchestratorSynthesisOut,
    POCPlanOut,
    SPLToESQLOut,
    StackExtractOut,
    TroubleshootOut,
)
from app.config import settings
from app.integrations.claude_client import MODEL_HAIKU, MODEL_OPUS, get_service
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


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=2000)
    top_k: int = Field(5, ge=1, le=20)
    model: Optional[str] = Field("", max_length=60)
    # Optional retrieval mode override. Defaults to the full hybrid + rerank
    # pipeline. Accepts: "semantic", "hybrid", "hybrid_rerank".
    mode: Optional[str] = Field("hybrid_rerank", max_length=24)


class KnowledgeCitation(BaseModel):
    n: int
    url: str
    title: str
    section_heading: str
    snippet: str


class KnowledgeSearchOut(BaseModel):
    answer: str
    citations: List[KnowledgeCitation]


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


# ============================================================ Knowledge search =======


_KNOWLEDGE_MOCK: Dict[str, Any] = {
    "answer": (
        "Mock fallback: the knowledge index is not yet populated. "
        "Once the corpus and embeddings are ready, this tool will return a grounded answer with citations. "
        "Visit https://www.elastic.co/docs/ for the official documentation in the meantime."
    ),
    "citations": [],
}


def _load_knowledge_repo():
    """Locate the KnowledgeRepo built by agent S3B. Tries a few known module paths."""
    last_err: Optional[Exception] = None
    for mod_path in (
        "app.repositories.knowledge_repo",
        "app.repositories.knowledge",
    ):
        try:
            mod = __import__(mod_path, fromlist=["KnowledgeRepo"])
            cls = getattr(mod, "KnowledgeRepo", None)
            if cls is not None:
                return cls
        except Exception as exc:
            last_err = exc
            continue
    if last_err:
        log.info("knowledge_repo.import_failed", reason=str(last_err))
    return None


def _normalize_hits(raw_hits: Any) -> List[Dict[str, Any]]:
    """Normalize whatever S3B's repo returns into the shape Mei's prompt expects."""
    if not raw_hits:
        return []
    out: List[Dict[str, Any]] = []
    for h in raw_hits:
        if not isinstance(h, dict):
            continue
        # Some repos nest payload in `_source`; flatten if needed.
        src = h.get("_source") if isinstance(h.get("_source"), dict) else h
        out.append(
            {
                "title": src.get("title") or src.get("page_title") or "",
                "url": src.get("url") or src.get("source_url") or "",
                "section_heading": (
                    src.get("section_heading")
                    or src.get("section")
                    or src.get("heading")
                    or ""
                ),
                "text": (
                    src.get("text")
                    or src.get("body")
                    or src.get("content")
                    or src.get("snippet")
                    or ""
                ),
            }
        )
    return out


def _safe_mode(value: Optional[str]) -> str:
    """Normalize the requested retrieval mode. Defaults to hybrid_rerank."""
    allowed = {"semantic", "hybrid", "hybrid_rerank"}
    v = (value or "hybrid_rerank").strip().lower()
    return v if v in allowed else "hybrid_rerank"


def _repo_search(repo: Any, query: str, top_k: int, mode: str) -> List[Any]:
    """Call repo.search with mode kwarg if supported, else fall back gracefully.

    Older repo signatures only accept (query, top_k); this keeps backward
    compatibility while letting the new modes drive retrieval when present.
    """
    try:
        return repo.search(query, top_k, mode=mode) or []
    except TypeError:
        # Repo predates the mode argument. Fall back to plain semantic.
        return repo.search(query, top_k) or []


async def run_knowledge_search(payload: KnowledgeSearchRequest) -> Dict[str, Any]:
    """Hybrid + rerank search over the Elastic public docs corpus, synthesized by Mei."""
    query = payload.query.strip()
    top_k = max(1, min(payload.top_k or 5, 20))
    mode = _safe_mode(payload.mode)
    log.info("tool.knowledge_search.start", query_len=len(query), top_k=top_k, mode=mode)

    cls = _load_knowledge_repo()
    repo = None
    raw_hits: List[Any] = []

    if cls is not None:
        try:
            repo = cls()
            raw_hits = _repo_search(repo, query, top_k, mode)
        except Exception as exc:
            log.info("knowledge_repo.init_failed", reason=str(exc))
            repo = None
            raw_hits = []

    # Per spec: if the repo is missing OR the corpus is empty, retry for up to 90s.
    if not raw_hits:
        deadline = time.monotonic() + 90.0
        while time.monotonic() < deadline:
            await asyncio.sleep(3.0)
            cls = _load_knowledge_repo() if cls is None else cls
            if cls is None:
                continue
            try:
                repo = cls()
                raw_hits = _repo_search(repo, query, top_k, mode)
                if raw_hits:
                    break
            except Exception as exc:
                log.info("knowledge_repo.retry_failed", reason=str(exc))

    if repo is None:
        return {
            "answer": (
                "The knowledge index is not yet ready. The corpus and embeddings are still being built; "
                "please retry in a minute. In the meantime, the Elastic public documentation lives at "
                "https://www.elastic.co/docs/ and is the canonical source for ILM, ES|QL, semantic_text, "
                "and detection-rule guidance."
            ),
            "citations": [],
            "warning": "knowledge_repo_unavailable",
        }

    hits = _normalize_hits(raw_hits)
    log.info("tool.knowledge_search.hits", count=len(hits))

    user_prompt = tool_prompts.render_knowledge_search_prompt(query, hits)

    result: KnowledgeSearchOut = get_service().call_structured(
        system=tool_prompts.KNOWLEDGE_SEARCH_SYSTEM,
        user=user_prompt,
        schema=tool_prompts.KNOWLEDGE_SEARCH_SCHEMA,
        output_model=KnowledgeSearchOut,
        model=_resolve_model(payload.model),
        max_tokens=4096,
        effort="high",
        mock_payload=_KNOWLEDGE_MOCK,
        audit_meta={
            "agent": "tool_knowledge_search",
            "tool": "knowledge_search",
            "query_len": len(query),
            "top_k": top_k,
            "hit_count": len(hits),
            "mode": mode,
        },
    )

    data = result.model_dump()
    log.info(
        "tool.knowledge_search.complete",
        answer_len=len(data.get("answer") or ""),
        citation_count=len(data.get("citations") or []),
    )
    return data


@router.post("/knowledge-search")
async def knowledge_search_endpoint(payload: KnowledgeSearchRequest) -> Dict[str, Any]:
    """Mei (ex-Elastic enablement docs lead) answers FE questions grounded in the public docs corpus."""
    return await run_knowledge_search(payload)


# ============================================================ Troubleshoot ===========


class TroubleshootRequest(BaseModel):
    error_text: str = Field(..., min_length=3, max_length=20000)
    context: Optional[str] = Field("", max_length=8000)
    language: Optional[str] = Field("English", max_length=40)
    model: Optional[str] = Field("", max_length=60)


_TROUBLESHOOT_MOCK: Dict[str, Any] = {
    "likely_causes": [
        {
            "cause": "Hot tier JVM heap is undersized for the current ingest + aggregation workload, so the parent circuit breaker trips before requests can complete.",
            "confidence": "medium",
            "evidence_in_input": "CircuitBreakingException with parent breaker [3.2gb/3gb]",
        }
    ],
    "diagnostic_queries": [
        {
            "title": "Mock fallback: recent error rate by service",
            "esql": "FROM logs-* | WHERE @timestamp > NOW() - 1 hour AND log.level == \"error\" | STATS errors = COUNT(*) BY service.name | SORT errors DESC | LIMIT 10",
            "expected_signal": "Top 10 services with the most error logs in the last hour. A single service dominating points at the upstream cause.",
        }
    ],
    "quick_remediations": [
        {
            "step": "Mock fallback: enable the bulk client retry policy with exponential backoff while you size the cluster.",
            "risk_level": "low",
            "reversible": True,
        }
    ],
    "escalation_path": "Mock fallback: engage Elastic Support if the breaker keeps tripping after you scale the hot tier or if shards become unassigned. Routine config tuning stays in-house.",
    "caveats": [
        "Mock mode active because no Anthropic API key is configured.",
        "Real responses include three diagnostic queries and a full cause-confidence-evidence breakdown.",
    ],
}


@router.post("/troubleshoot")
async def run_troubleshoot(payload: TroubleshootRequest) -> Dict[str, Any]:
    """Ravi (ex-Elastic Support, 1000+ tickets) diagnoses an Elastic stack error and emits 3 ES|QL diagnostic queries."""
    language = payload.language or "English"
    log.info("tool.troubleshoot.start", language=language, has_context=bool(payload.context))

    user_prompt = (
        language_preamble(language)
        + tool_prompts.render_troubleshoot_prompt(payload.error_text, payload.context or "")
        + language_instruction(language)
    )

    result: TroubleshootOut = get_service().call_structured(
        system=tool_prompts.TROUBLESHOOT_SYSTEM,
        user=user_prompt,
        schema=tool_prompts.TROUBLESHOOT_SCHEMA,
        output_model=TroubleshootOut,
        model=_resolve_model(payload.model),
        max_tokens=6144,
        effort="high",
        mock_payload=_TROUBLESHOOT_MOCK,
        audit_meta={"agent": "tool_troubleshoot", "tool": "troubleshoot"},
    )

    data = result.model_dump()

    # Persist a timestamped audit artifact for this diagnosis.
    try:
        out_dir = settings.runtime_dir / "troubleshoot"
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        record = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "language": language,
            "error_text": payload.error_text,
            "context": payload.context or "",
            **data,
        }
        (out_dir / f"{ts}.json").write_text(
            json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    except Exception as exc:
        log.warning("tool.troubleshoot.persist_failed", reason=str(exc))

    log.info(
        "tool.troubleshoot.complete",
        causes=len(data.get("likely_causes") or []),
        queries=len(data.get("diagnostic_queries") or []),
        remediations=len(data.get("quick_remediations") or []),
    )
    return data


# ============================================================ Orchestrator (Auro) ====


class OrchestratorRequest(BaseModel):
    query: str = Field(..., min_length=5, max_length=8000)
    language: Optional[str] = Field("English", max_length=40)
    model: Optional[str] = Field("", max_length=60, description="Synthesis model override; planning always uses Haiku for cost.")


# Mock fallback used when no Anthropic key is configured. Picks two tools
# (a cost calc and a capacity planner) and stitches a fake summary so the
# UI/MCP path stays demonstrable offline.
_ORCHESTRATOR_MOCK_PLAN: Dict[str, Any] = {
    "plan": (
        "Mock fallback: Auro picked fec_cost_calc and fec_capacity to handle the typical "
        "FE 'TCO + sizing' double-question. Configure ANTHROPIC_API_KEY to get a real plan."
    ),
    "picks": [
        {
            "tool": "fec_cost_calc",
            "rationale": "Mock pick: the query mentions ingest volume and retention, which is a TCO question.",
            "input_json": json.dumps({"ingest_gb_day": 500, "retention_months": 12}),
        },
        {
            "tool": "fec_capacity",
            "rationale": "Mock pick: pairing the TCO with a heuristic cluster topology so the FE can quote both numbers.",
            "input_json": json.dumps({"peak_indexing_eps": 6000, "hot_data_gb": 1500}),
        },
    ],
}

_ORCHESTRATOR_MOCK_SYNTHESIS: Dict[str, Any] = {
    "synthesis": (
        "Mock fallback synthesis: configure ANTHROPIC_API_KEY for the real Auro response. "
        "In a live run, Auro would weave the fec_cost_calc totals and the fec_capacity topology "
        "into one quote-ready paragraph, naming the savings versus the customer's current spend."
    ),
    "follow_ups": [
        "Do you want this priced against an existing Splunk or Datadog quote?",
        "Should we add a compliance mapping for the customer's regulated industry?",
        "Is there a meeting id we should anchor a POV plan to?",
    ],
}


def _summarize_tool_output(tool: str, payload: Any, max_chars: int = 1800) -> str:
    """Turn a tool's raw output into a compact JSON-ish string Auro can read.

    Keeps the synthesis prompt bounded; we never want to paste a 30 KB POV plan
    into the synthesis context. Truncation is marked explicitly so Auro knows.
    """
    if isinstance(payload, BaseModel):
        payload = payload.model_dump()
    try:
        text = json.dumps(payload, default=str, ensure_ascii=False, indent=2)
    except Exception:
        text = str(payload)
    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + f"\n... [truncated; full payload was {len(text)} chars]"
    return text


def _looks_like_meeting_id(text: str) -> bool:
    """Heuristic the spec calls for: only allow fec_poc_plan when the query names a synthetic meeting id."""
    import re

    if not text:
        return False
    return re.search(r"[a-z0-9_]+-mtg-[a-z0-9_-]+", text.lower()) is not None


async def _dispatch_pick(tool: str, args: Dict[str, Any]) -> Any:
    """Execute one Auro pick by routing into the existing FastAPI tool functions.

    Each branch validates inputs through the same Pydantic request model the
    public route uses, so bad inputs raise the same HTTPException 422 surface.
    """
    if tool == "fec_poc_plan":
        meeting_id = args.get("meeting_id")
        if not meeting_id:
            raise ValueError("fec_poc_plan requires a meeting_id")
        return await run_poc_plan(meeting_id, POCPlanRequest(language=args.get("language", "English")))
    if tool == "fec_spl_to_esql":
        return await run_spl_to_esql(SPLToESQLRequest(**args))
    if tool == "fec_compliance":
        return await run_compliance_mapping(ComplianceRequest(**args))
    if tool == "fec_stack_extract":
        return await run_stack_extract(StackExtractRequest(**args))
    if tool == "fec_code_sample":
        return await run_code_sample(CodeSampleRequest(**args))
    if tool == "fec_cost_calc":
        return await run_cost_calc(CostCalcRequest(**args))
    if tool == "fec_capacity":
        return await run_capacity(CapacityRequest(**args))
    if tool == "fec_knowledge_search":
        return await run_knowledge_search(KnowledgeSearchRequest(**args))
    if tool == "fec_troubleshoot":
        return await run_troubleshoot(TroubleshootRequest(**args))
    raise ValueError(f"unknown tool: {tool}")


async def run_orchestrator(payload: OrchestratorRequest) -> Dict[str, Any]:
    """Auro: plan -> parallel execute -> synthesize. Hard cap of 3 tools per run.

    Cost budget (live mode): planning ~500 input + ~400 output tokens on Haiku 4.5;
    each picked tool varies (Haiku/Opus per its existing config); synthesis ~2500 input
    + ~1500 output tokens on Sonnet/Opus.
    """
    language = payload.language or "English"
    query = payload.query.strip()
    log.info("tool.orchestrator.start", query_len=len(query), language=language)

    service = get_service()

    # ---- Step 1: planning. Forced Haiku for cost. -----------------------------------
    plan_prompt = (
        language_preamble(language)
        + tool_prompts.render_orchestrator_plan_prompt(query, language)
        + language_instruction(language)
    )
    plan_result: OrchestratorPlanOut = service.call_structured(
        system=tool_prompts.ORCHESTRATOR_SYSTEM,
        user=plan_prompt,
        schema=tool_prompts.ORCHESTRATOR_PLAN_SCHEMA,
        output_model=OrchestratorPlanOut,
        model=MODEL_HAIKU,
        max_tokens=1024,
        effort="medium",  # ignored on Haiku per claude_client._is_haiku
        mock_payload=_ORCHESTRATOR_MOCK_PLAN,
        audit_meta={"agent": "tool_orchestrator", "tool": "orchestrator", "stage": "plan"},
    )

    # Enforce the 3-tool cap and the meeting-id guard for fec_poc_plan.
    raw_picks = list(plan_result.picks or [])[:3]
    sanitized_picks = []
    for p in raw_picks:
        if p.tool == "fec_poc_plan" and not _looks_like_meeting_id(query):
            log.info("orchestrator.skip_pick", tool=p.tool, reason="no_meeting_id_in_query")
            continue
        sanitized_picks.append(p)

    if not sanitized_picks:
        # Auro picked nothing usable. Return the plan with an empty execution and a graceful synthesis.
        return OrchestratorOut(
            plan=plan_result.plan,
            tools_invoked=[],
            synthesis=(
                "Auro reviewed the query but did not find a clean tool match. "
                "The original plan is preserved for transparency. Try rephrasing with concrete inputs "
                "(an SPL block, an ingest GB/day figure, or a meeting id) so Auro can route the request."
            ),
            follow_ups=[
                "Can you share the exact SPL or EQL query you want translated?",
                "Do you have ingest volume and retention numbers for a TCO comparison?",
                "Is there a saved meeting id you want to anchor a POV plan to?",
            ],
        ).model_dump()

    # ---- Step 2: execute picks in parallel. -----------------------------------------
    async def _run_one(pick) -> OrchestratorInvocation:
        try:
            args = json.loads(pick.input_json) if pick.input_json else {}
            if not isinstance(args, dict):
                raise ValueError("input_json must decode to a JSON object")
        except Exception as exc:
            return OrchestratorInvocation(
                tool=pick.tool,
                rationale=pick.rationale,
                input={},
                output_summary=f"(input_json could not be parsed: {exc})",
                ok=False,
                error=f"bad input_json: {exc}",
            )
        try:
            result = await _dispatch_pick(pick.tool, args)
            summary = _summarize_tool_output(pick.tool, result)
            return OrchestratorInvocation(
                tool=pick.tool,
                rationale=pick.rationale,
                input=args,
                output_summary=summary,
                ok=True,
            )
        except Exception as exc:
            log.warning("orchestrator.tool_failed", tool=pick.tool, error=str(exc))
            return OrchestratorInvocation(
                tool=pick.tool,
                rationale=pick.rationale,
                input=args,
                output_summary=f"(tool call raised: {exc})",
                ok=False,
                error=str(exc),
            )

    invocations: List[OrchestratorInvocation] = await asyncio.gather(
        *[_run_one(p) for p in sanitized_picks]
    )

    # ---- Step 3: synthesis. Default to a stronger model for the unification step. ---
    synth_inputs = [
        {
            "tool": inv.tool,
            "ok": inv.ok,
            "rationale": inv.rationale,
            "output_summary": inv.output_summary,
        }
        for inv in invocations
    ]
    synth_prompt = (
        language_preamble(language)
        + tool_prompts.render_orchestrator_synthesis_prompt(
            query=query,
            plan=plan_result.plan,
            tool_outputs=synth_inputs,
            language=language,
        )
        + language_instruction(language)
    )
    synthesis_model = _resolve_model(payload.model)
    # If the caller did not override and the default is Haiku, bump to Opus for the unification step.
    if not (payload.model or "").strip() and "haiku" in synthesis_model:
        synthesis_model = MODEL_OPUS

    synth_result: OrchestratorSynthesisOut = service.call_structured(
        system=tool_prompts.ORCHESTRATOR_SYSTEM,
        user=synth_prompt,
        schema=tool_prompts.ORCHESTRATOR_SYNTHESIS_SCHEMA,
        output_model=OrchestratorSynthesisOut,
        model=synthesis_model,
        max_tokens=2048,
        effort="high",
        mock_payload=_ORCHESTRATOR_MOCK_SYNTHESIS,
        audit_meta={
            "agent": "tool_orchestrator",
            "tool": "orchestrator",
            "stage": "synthesis",
            "tools_picked": [inv.tool for inv in invocations],
        },
    )

    out = OrchestratorOut(
        plan=plan_result.plan,
        tools_invoked=invocations,
        synthesis=synth_result.synthesis,
        follow_ups=synth_result.follow_ups,
    )

    log.info(
        "tool.orchestrator.complete",
        picks=len(invocations),
        ok_count=sum(1 for inv in invocations if inv.ok),
    )
    return out.model_dump()


@router.post("/orchestrator")
async def orchestrator_endpoint(payload: OrchestratorRequest) -> Dict[str, Any]:
    """Auro (FE conductor) plans, fan-outs to 1-3 of the other 9 tools, and synthesizes a unified answer."""
    return await run_orchestrator(payload)
