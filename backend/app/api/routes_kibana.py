"""
filename: routes_kibana.py
description: Build and create a customer-fit dashboard inside Elastic Kibana from a meeting record. Pulls the company profile, the pre-meeting brief, the post-meeting record, and runs the pure-Python TCO + capacity calculators to populate eight markdown panels (profile, what they care about, pains, compliance, TCO, capacity, competitive landscape, action items). POSTs a single dashboard saved object via /api/saved_objects/_bulk_create and returns the Kibana view URL.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException

from app.config import settings
from app.repositories import synthetic
from app.services import calculators
from app.utils.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/kibana", tags=["kibana"])


# ============================================================ Helpers ===============


def _kbn_url(path: str) -> str:
    return settings.kibana_url.rstrip("/") + path


def _kbn_headers() -> Dict[str, str]:
    return {
        "Authorization": f"ApiKey {settings.kibana_api_key}",
        "Content-Type": "application/json",
        "kbn-xsrf": "fe-copilot",
    }


def _slug(text: str) -> str:
    """Lowercase + dasherized id, safe to use as a Kibana saved-object id."""
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s or "fec"


def _scale_defaults(company: Dict[str, Any]) -> Dict[str, Any]:
    """Best-effort scale estimate from company size for cost / capacity panels."""
    size = (company.get("size") or "").lower()
    if any(k in size for k in ["10000", "10k", "8000", "8k", "5000+"]):
        return {"ingest_gb_day": 250.0, "retention_months": 12, "current_spend": 2_500_000.0,
                "peak_eps": 60_000, "hot_gb": 6_000}
    if any(k in size for k in ["1000", "1k", "2000", "3000"]):
        return {"ingest_gb_day": 150.0, "retention_months": 12, "current_spend": 1_200_000.0,
                "peak_eps": 30_000, "hot_gb": 3_000}
    return {"ingest_gb_day": 80.0, "retention_months": 9, "current_spend": 600_000.0,
            "peak_eps": 15_000, "hot_gb": 1_500}


def _parse_stack_notes(notes: str) -> Dict[str, List[str]]:
    """Split a free-form stack-notes string from Quick Research into the canonical
    bucket shape the markdown panels expect. Heuristic only - we just sort tokens
    by keyword match into a few buckets and dump everything else into 'data'."""
    if not notes:
        return {}
    tokens = [t.strip() for t in notes.replace(";", ",").replace("/", ",").split(",") if t.strip()]
    buckets: Dict[str, List[str]] = {"observability": [], "search": [], "siem": [], "cloud": [], "data": []}
    OBS = {"splunk", "datadog", "newrelic", "new relic", "dynatrace", "grafana", "appdynamics", "sumologic", "sumo logic"}
    SRCH = {"elasticsearch", "elastic", "solr", "algolia", "opensearch"}
    SIEM = {"splunk siem", "qradar", "sentinel", "chronicle", "exabeam"}
    CLOUD = {"aws", "gcp", "azure", "alibaba", "oracle cloud"}
    for t in tokens:
        low = t.lower()
        if any(k in low for k in OBS):
            buckets["observability"].append(t)
        elif any(k in low for k in SIEM):
            buckets["siem"].append(t)
        elif any(k in low for k in SRCH):
            buckets["search"].append(t)
        elif any(k in low for k in CLOUD):
            buckets["cloud"].append(t)
        else:
            buckets["data"].append(t)
    return {k: v for k, v in buckets.items() if v}


def _industry_regulations(industry: str) -> List[str]:
    s = (industry or "").lower()
    if any(k in s for k in ["bank", "financ", "fintech", "fs", "insurance", "card"]):
        return ["DORA", "PCI DSS", "GDPR", "SOX", "FCA SYSC"]
    if any(k in s for k in ["health", "pharma", "hospital"]):
        return ["HIPAA", "GDPR", "HITRUST"]
    if any(k in s for k in ["e-comm", "retail", "marketplace"]):
        return ["PCI DSS", "GDPR", "SOC 2"]
    if any(k in s for k in ["public", "gov", "federal"]):
        return ["FedRAMP", "NIST 800-53"]
    return ["ISO 27001", "SOC 2", "GDPR"]


# ============================================================ Markdown builders =====


def _md_customer_profile(company: Dict[str, Any], meeting: Dict[str, Any]) -> str:
    parts = [f"## Customer Profile · {company.get('name', 'Unknown')}\n"]
    if company.get("industry"):
        parts.append(f"**Industry:** {company['industry']}{' · ' + company['size'] if company.get('size') else ''}")
    if company.get("description"):
        parts.append(f"\n{company['description']}\n")
    stack = company.get("tech_stack") or {}
    chips = []
    for k in ("observability", "search", "siem", "cloud", "data"):
        v = stack.get(k)
        if v:
            chips.append(f"**{k}:** {', '.join(v[:5])}")
    if chips:
        parts.append("\n" + " · ".join(chips))
    if meeting.get("title"):
        parts.append(f"\n\n*Meeting: {meeting['title']}*")
    return "\n".join(parts)


def _md_what_they_care_about(post: Optional[Dict[str, Any]], brief: Optional[Dict[str, Any]]) -> str:
    if post and post.get("meddpicc_signals"):
        # Prefer post-meeting MEDDPICC signals where category is Pain / Metrics / Decision Criteria.
        prio = ["Pain", "Metrics", "Decision Criteria", "Champion", "Economic Buyer"]
        signals = sorted(
            post["meddpicc_signals"],
            key=lambda s: prio.index(s.get("category")) if s.get("category") in prio else 99,
        )[:6]
        lines = ["## What They Care About\n", "_Top MEDDPICC signals captured in this conversation._\n"]
        for s in signals:
            lines.append(f"- **{s.get('category', '')}** - \"{s.get('quote', '').strip()}\"")
            if s.get("note"):
                lines.append(f"  - _{s['note']}_")
        return "\n".join(lines)
    if brief and brief.get("sections"):
        # Use brief signals as fallback.
        target = next((s for s in brief["sections"] if "signal" in (s.get("heading", "")).lower()), None) or brief["sections"][0]
        lines = [f"## What They Care About\n", f"_From the pre-meeting brief: {target.get('heading', '')}._\n"]
        for b in target.get("bullets", [])[:6]:
            lines.append(f"- {b}")
        return "\n".join(lines)
    return "## What They Care About\n\n_Run the Pre-Meeting agent first to populate this panel._"


def _md_pain_points(brief: Optional[Dict[str, Any]]) -> str:
    if not brief or not brief.get("sections"):
        return "## Pain Points & Concerns\n\n_No brief on file._"
    pain = next((s for s in brief["sections"] if "pain" in (s.get("heading", "")).lower()), None)
    if not pain:
        return "## Pain Points & Concerns\n\n_No pain section in the brief._"
    lines = [f"## Pain Points & Concerns\n", f"_{pain.get('heading', '')}_\n"]
    for b in pain.get("bullets", [])[:6]:
        lines.append(f"- {b}")
    return "\n".join(lines)


def _md_compliance(industry: str) -> str:
    regs = _industry_regulations(industry)
    rows = [
        "| Regulation | Elastic native control |",
        "| --- | --- |",
    ]
    mapping = {
        "DORA": "ICT incident detection (Elastic Security), 24h reporting via Cases + Elastic Workflows",
        "PCI DSS": "ECS-aligned audit logs, frozen tier for 12-month retention, RBAC + IP filters",
        "GDPR": "Field-level security, data masking, retention policies via ILM",
        "SOX": "Audit-trail indices on hot+frozen, immutability via lifecycle policies",
        "FCA SYSC": "Operational resilience dashboards, regulatory metrics in Lens",
        "HIPAA": "PHI-aware ingest pipelines + audit log capture per event",
        "HITRUST": "ECS audit fields + Cases for documented evidence trail",
        "PCI DSS (e-comm)": "Card-data tokenization in pipelines, audit retention",
        "FedRAMP": "Encrypted at rest + in transit, IL5-ready GovCloud deployment",
        "NIST 800-53": "Per-control mapping in Elastic Security detection rules",
        "ISO 27001": "Asset inventory via Fleet, access logs via Elastic Auth",
        "SOC 2": "Continuous monitoring dashboards + change tracking",
    }
    for r in regs:
        rows.append(f"| **{r}** | {mapping.get(r, 'Custom mapping; see Elastic compliance reference architectures')} |")
    return "## Compliance Fit\n\n_Mapped from the customer's industry signal._\n\n" + "\n".join(rows)


def _md_tco(scale: Dict[str, Any]) -> str:
    out = calculators.estimate_tco(
        ingest_gb_day=scale["ingest_gb_day"],
        retention_months=scale["retention_months"],
        current_spend_annual_usd=scale["current_spend"],
    )
    el = out["elastic"]["total_annual_usd"]
    sp = out["splunk"]["total_annual_usd"]
    dd = out["datadog"]["total_annual_usd"]
    save = out.get("savings_vs_current") or 0
    pct = out.get("savings_pct_vs_current") or 0
    rows = [
        f"## TCO Comparison · {int(scale['ingest_gb_day'])} GB/day · {scale['retention_months']}-month retention\n",
        f"_Defaults inferred from the customer's company size; tweak in the FE Copilot tools page for a precise number._\n",
        "| Platform | Annual cost (USD) |",
        "| --- | ---: |",
        f"| **Elastic Cloud** | ${el:,.0f} |",
        f"| Splunk | ${sp:,.0f} |",
        f"| Datadog Logs (directional) | ${dd:,.0f} |",
        "",
        f"**Savings vs current spend (${scale['current_spend']:,.0f}/yr): ${save:,.0f} ({pct:.1f}%)**",
    ]
    return "\n".join(rows)


def _md_capacity(scale: Dict[str, Any]) -> str:
    out = calculators.plan_cluster(
        peak_indexing_eps=scale["peak_eps"],
        hot_data_gb=scale["hot_gb"],
        warm_data_gb=scale["hot_gb"] // 2,
        replicas=1,
        peak_qps=200,
    )
    rec = out.get("recommendation") or out
    nodes = rec.get("hot_nodes") or rec.get("nodes_required") or "?"
    masters = rec.get("master_nodes") or 3
    kibana = rec.get("kibana_nodes") or 2
    return (
        f"## Capacity Sizing · {scale['peak_eps']:,} EPS · {scale['hot_gb']:,} GB hot data\n\n"
        f"_Heuristic from the cluster planner._\n\n"
        f"- **Hot tier:** {nodes} nodes, NVMe SSD\n"
        f"- **Warm tier:** {scale['hot_gb'] // 2:,} GB cost-optimized storage\n"
        f"- **Master nodes:** {masters} (HA quorum)\n"
        f"- **Kibana nodes:** {kibana} (HA dashboards)\n"
        f"- **Frozen tier:** searchable snapshots on object storage (S3/GCS/Azure Blob)\n"
    )


def _md_competitive(post: Optional[Dict[str, Any]], company: Dict[str, Any]) -> str:
    competitors = []
    if post and post.get("competitor_mentions"):
        competitors = [c.get("competitor") for c in post["competitor_mentions"] if c.get("competitor")]
    # Fall back to obs/siem stack
    if not competitors:
        stack = company.get("tech_stack") or {}
        competitors = list(set((stack.get("observability") or []) + (stack.get("siem") or [])))[:3]
    if not competitors:
        return "## Competitive Landscape\n\n_No competitors on file yet._"
    lines = [
        "## Competitive Landscape\n",
        "_Counter-positioning to use during follow-up._\n",
        "| Competitor | Elastic counter |",
        "| --- | --- |",
    ]
    counters = {
        "Splunk": "Open architecture + ES|QL + frozen tier object-store; up to 60% lower TCO at scale",
        "Datadog": "Honest unit economics, no per-host gotchas; logs + APM + SIEM in one license",
        "Sumo Logic": "Self-hosted option, ECS taxonomy, Kibana + Lens for ad-hoc analysis",
        "New Relic": "Vendor-neutral OpenTelemetry + Elastic SIEM; pay for ingest, not seats",
        "Grafana": "First-class observability + native log analytics + SIEM, single pane of glass",
        "Graylog": "Searchable snapshots + ML-driven anomaly detection out of the box",
    }
    for c in competitors[:5]:
        lines.append(f"| **{c}** | {counters.get(c, 'See FE Copilot battlecard.')} |")
    return "\n".join(lines)


def _md_action_items(post: Optional[Dict[str, Any]]) -> str:
    if not post or not post.get("action_items"):
        return "## Action Items\n\n_Run the Post-Meeting agent to populate this panel._"
    lines = ["## Action Items & Next Steps\n", "| Action | Owner | Due | Impact |", "| --- | --- | --- | --- |"]
    for a in post["action_items"][:10]:
        lines.append(
            f"| {a.get('title', '')} | {a.get('owner_name', '?')} | {a.get('due_date') or '-'} | {a.get('impact') or '-'} |"
        )
    return "\n".join(lines)


# ============================================================ Panels ==============


def _markdown_panel(panel_id: str, x: int, y: int, w: int, h: int, markdown: str,
                    title: str = "") -> Dict[str, Any]:
    """Build a by-value markdown panel using the legacy visualization embeddable wrapper.

    Kibana 9.x does not register a top-level "markdown" embeddable factory; markdown panels
    must be wrapped as type "visualization" with savedVis.type "markdown" so the visualization
    embeddable picks them up.
    """
    return {
        "type": "visualization",
        "panelIndex": panel_id,
        "gridData": {"x": x, "y": y, "w": w, "h": h, "i": panel_id},
        "version": "9.3.4",
        "embeddableConfig": {
            "enhancements": {},
            "savedVis": {
                "type": "markdown",
                "title": title,
                "description": "",
                "params": {"fontSize": 12, "openLinksInNewTab": True, "markdown": markdown},
                "uiState": {},
                "data": {
                    "aggs": [],
                    "searchSource": {"query": {"language": "kuery", "query": ""}, "filter": []},
                },
            },
        },
        "title": title,
    }


def build_panels(company: Dict[str, Any], meeting: Dict[str, Any], brief: Optional[Dict[str, Any]],
                  post: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Two-column 48-wide grid; each row is h=14, paired panels share the row."""
    scale = _scale_defaults(company)
    industry = company.get("industry") or ""
    layout = [
        ("p1", 0, 0, 24, 14, _md_customer_profile(company, meeting), "Customer profile"),
        ("p2", 24, 0, 24, 14, _md_what_they_care_about(post, brief), "What they care about"),
        ("p3", 0, 14, 24, 14, _md_pain_points(brief), "Pain points & concerns"),
        ("p4", 24, 14, 24, 14, _md_compliance(industry), "Compliance fit"),
        ("p5", 0, 28, 24, 14, _md_tco(scale), "TCO comparison"),
        ("p6", 24, 28, 24, 14, _md_capacity(scale), "Capacity sizing"),
        ("p7", 0, 42, 24, 14, _md_competitive(post, company), "Competitive landscape"),
        ("p8", 24, 42, 24, 14, _md_action_items(post), "Action items & next steps"),
    ]
    return [_markdown_panel(*args) for args in layout]


# ============================================================ Endpoint ============


@router.post("/dashboard/{meeting_id}")
def create_dashboard(meeting_id: str) -> Dict[str, Any]:
    if not settings.kibana_api_key:
        raise HTTPException(status_code=409, detail="KIBANA_API_KEY not configured")

    # Best-effort: load brief + post if they exist on disk.
    brief = None
    post = None
    brief_path = settings.runtime_dir / "briefs" / f"{meeting_id}.json"
    if brief_path.exists():
        try:
            brief = json.loads(brief_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    post_path = settings.runtime_dir / "post_meeting" / f"{meeting_id}.json"
    if post_path.exists():
        try:
            post = json.loads(post_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Resolve meeting + company. Synthetic meetings live in the JSON fixtures;
    # ad-hoc meetings (Quick Research) only exist as a brief on disk, so we
    # reconstruct the lightweight context from the brief itself.
    meeting = synthetic.find_meeting(meeting_id)
    company: Optional[Dict[str, Any]] = None
    if meeting is not None:
        company = synthetic.find_company(meeting["company_id"])
    if company is None and brief is not None:
        ui = (brief.get("sources_used") or {}).get("user_input") or {}
        company = {
            "id": brief.get("company_id") or meeting_id,
            "name": brief.get("company_name") or ui.get("company_name") or "Customer",
            "industry": ui.get("industry", ""),
            "size": ui.get("size", ""),
            "description": ui.get("notes", ""),
            "tech_stack": _parse_stack_notes(ui.get("tech_stack_notes", "")),
        }
        meeting = meeting or {
            "id": meeting_id,
            "company_id": company["id"],
            "title": ui.get("meeting_title") or brief.get("headline", "")[:80] or meeting_id,
            "start_time": brief.get("generated_at"),
        }
    if company is None or meeting is None:
        raise HTTPException(
            status_code=404,
            detail=f"meeting {meeting_id} not found - run the Pre-Meeting agent first so the brief lands on disk.",
        )

    panels = build_panels(company, meeting, brief, post)
    panels_json = json.dumps(panels, ensure_ascii=False)
    options_json = json.dumps({"useMargins": True, "hidePanelTitles": False, "syncColors": False, "syncCursor": False, "syncTooltips": False})
    search_source_json = json.dumps({"query": {"language": "kuery", "query": ""}, "filter": []})

    dashboard_id = f"fec-{_slug(meeting_id)}"
    title = f"FE Copilot · {company.get('name', 'Customer')} · {meeting.get('title', '')[:60]}"
    description = (
        f"Customer-fit briefing built from the FE Copilot pre-meeting brief and post-meeting record. "
        f"Generated {datetime.now(timezone.utc).isoformat()}."
    )

    body = [{
        "id": dashboard_id,
        "type": "dashboard",
        "attributes": {
            "title": title,
            "description": description,
            "panelsJSON": panels_json,
            "optionsJSON": options_json,
            "timeRestore": False,
            "version": 1,
            "kibanaSavedObjectMeta": {"searchSourceJSON": search_source_json},
        },
    }]

    url = _kbn_url("/api/saved_objects/_bulk_create?overwrite=true")
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, headers=_kbn_headers(), json=body)
    except Exception as exc:
        log.warning("kibana.dashboard.exception", error=str(exc))
        raise HTTPException(status_code=502, detail=f"Kibana request failed: {exc}")

    if resp.status_code >= 400:
        log.warning("kibana.dashboard.http_error", status=resp.status_code, body=resp.text[:500])
        raise HTTPException(status_code=502, detail=f"Kibana {resp.status_code}: {resp.text[:300]}")

    dashboard_url = settings.kibana_url.rstrip("/") + f"/app/dashboards#/view/{dashboard_id}"
    log.info("kibana.dashboard.created", id=dashboard_id, meeting_id=meeting_id)
    return {
        "ok": True,
        "dashboard_id": dashboard_id,
        "dashboard_url": dashboard_url,
        "panels": len(panels),
    }
