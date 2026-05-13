"""
filename: industry_factory.py
description: Per-industry demo-data factory. Given an industry config dict from
    data/seed/industries.json, builds a scenario module surface (SCENARIO_ID,
    SCENARIO_TITLE, INDICES, DASHBOARD_ID, CUSTOMER_DASHBOARD_ID, seed(), ...)
    that the existing routes_demo_data registry can call with no changes.

    Each industry gets:
      - 2-3 themed Elasticsearch indices (4 for "high-stake" industries)
      - 800-3000 deterministic synthetic docs (3500-5000 for high-stake)
      - Two Kibana dashboards built from inline-data Vega-Lite + markdown panels:
          * FE dashboard: 4-6 panels (8 for high-stake) - story to tell customer
          * Customer dashboard: 4-6 panels (8 for high-stake) - operational KPIs

    All dashboards are saved-objects using the same _bulk_create endpoint that
    black_friday.py uses. The factory reuses the _kbn_url / _kbn_headers /
    _markdown_panel / _vega_panel / _create_one_dashboard / _delete_dashboard
    helpers from black_friday.py so the storage shape stays identical.

date: 13-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import hashlib
import json
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Tuple

from elasticsearch.helpers import bulk

from app.config import settings
from app.integrations.elasticsearch_client import get_client
from app.services.scenarios import black_friday as _bf
from app.utils.logging import get_logger

log = get_logger(__name__)


_DEFAULT_SEED: int = 20260513


# ---------------------------------------------------------------- Customer names ----
# Fictional customer names per industry. Never reuse real-world company names.
_CUSTOMER_NAMES: Dict[str, str] = {
    "fsi-banking": "Northwind Pay",
    "fsi-insurance": "Meridian Mutual",
    "fsi-capital-markets": "Stratus Capital Markets",
    "gov-federal": "Federal Continuity Agency",
    "gov-state-local": "Cascadia State Services",
    "healthcare-providers": "Crestline Health Network",
    "healthcare-payers": "Aurora Health Plans",
    "pharma-life-sciences": "Helix BioTherapeutics",
    "retail-ecommerce": "Lumen Apparel Digital",
    "retail-brick-mortar": "Cobalt Stores",
    "telco": "Polaris Telecom",
    "media-streaming": "Skyline Stream",
    "tech-saas": "Vector Cloud Platform",
    "mfg-discrete": "Atlas Robotics Works",
    "mfg-process": "Solstice Process Industries",
    "energy-utilities": "Granite Grid Utility",
    "transportation-logistics": "Compass Freight Network",
    "travel-hospitality": "Horizon Hospitality Group",
    "automotive": "Northstar Motors",
    "aerospace-defense": "Orion Defense Systems",
}

# Industries that get the deluxe treatment: 4 indices, 3500-5000 docs total,
# 8 panels per dashboard. Picked for regulatory weight + SKO demo emphasis.
_HIGH_STAKE: set = {
    "fsi-banking", "gov-federal", "healthcare-payers", "energy-utilities",
    "telco", "aerospace-defense", "mfg-process",
}


# ---------------------------------------------------------------- Index naming -----

def _index_prefix(industry_id: str) -> str:
    return f"demo-{industry_id}"


def _build_index_map(industry_id: str, high_stake: bool) -> Dict[str, str]:
    pfx = _index_prefix(industry_id)
    indices = {
        "events": f"{pfx}-events",
        "alerts": f"{pfx}-alerts",
        "audit": f"{pfx}-audit",
    }
    if high_stake:
        indices["compliance"] = f"{pfx}-compliance-events"
    return indices


# ---------------------------------------------------------------- Doc generation ----

def _rng_for(industry_id: str, seed: int) -> random.Random:
    h = hashlib.sha256(f"{industry_id}:{seed}".encode("utf-8")).digest()
    return random.Random(int.from_bytes(h[:8], "big"))


def _weighted_choice(rng: random.Random, items: List[Tuple[Any, float]]) -> Any:
    total = sum(w for _, w in items)
    r = rng.random() * total
    acc = 0.0
    for value, w in items:
        acc += w
        if r <= acc:
            return value
    return items[-1][0]


# Per-industry numeric value field schema. Each entry is (field_name, mean, stdev,
# unit_label). The first metric is the "primary KPI" used in the trend panel.
_INDUSTRY_METRICS: Dict[str, List[Tuple[str, float, float, str]]] = {
    "fsi-banking": [
        ("transaction_amount", 142.0, 95.0, "GBP"),
        ("fraud_score", 0.18, 0.22, "score"),
        ("authorization_latency_ms", 84.0, 31.0, "ms"),
    ],
    "fsi-insurance": [
        ("claim_amount", 4850.0, 2700.0, "USD"),
        ("fraud_score", 0.14, 0.19, "score"),
        ("quote_latency_ms", 192.0, 88.0, "ms"),
    ],
    "fsi-capital-markets": [
        ("trade_notional_usd", 220000.0, 180000.0, "USD"),
        ("surveillance_score", 0.09, 0.16, "score"),
        ("tick_query_latency_ms", 740.0, 240.0, "ms"),
    ],
    "gov-federal": [
        ("event_volume", 1850.0, 620.0, "events/min"),
        ("ato_evidence_count", 42.0, 18.0, "items"),
        ("siem_ingest_gb", 38.0, 12.0, "GB/hr"),
    ],
    "gov-state-local": [
        ("citizen_search_latency_ms", 280.0, 110.0, "ms"),
        ("incident_count", 7.0, 4.0, "events"),
        ("cost_per_citizen", 0.18, 0.07, "USD"),
    ],
    "healthcare-providers": [
        ("ehr_transaction_latency_ms", 1850.0, 720.0, "ms"),
        ("chart_open_ms", 1720.0, 580.0, "ms"),
        ("audit_evidence_age_h", 36.0, 18.0, "h"),
    ],
    "healthcare-payers": [
        ("claim_amount", 1240.0, 980.0, "USD"),
        ("denial_rate", 0.11, 0.06, "rate"),
        ("prior_auth_mttr_h", 48.0, 22.0, "h"),
    ],
    "pharma-life-sciences": [
        ("batch_release_h", 92.0, 38.0, "h"),
        ("csv_validation_items", 220.0, 80.0, "items"),
        ("rwe_query_latency_ms", 410.0, 180.0, "ms"),
    ],
    "retail-ecommerce": [
        ("checkout_latency_ms", 480.0, 220.0, "ms"),
        ("cart_value_usd", 88.0, 65.0, "USD"),
        ("search_zero_rate", 0.09, 0.05, "rate"),
    ],
    "retail-brick-mortar": [
        ("store_outage_min", 18.0, 11.0, "min"),
        ("shrink_pct", 0.012, 0.006, "rate"),
        ("inventory_query_ms", 220.0, 90.0, "ms"),
    ],
    "telco": [
        ("ran_kpi_mttr_min", 28.0, 14.0, "min"),
        ("sim_swap_detect_s", 92.0, 38.0, "s"),
        ("care_aht_s", 380.0, 130.0, "s"),
    ],
    "media-streaming": [
        ("playback_start_ms", 1850.0, 720.0, "ms"),
        ("ndcg_at_10", 0.68, 0.09, "score"),
        ("qoe_mttr_min", 14.0, 7.0, "min"),
    ],
    "tech-saas": [
        ("tco_per_million_events", 0.84, 0.32, "USD"),
        ("trace_query_ms", 920.0, 340.0, "ms"),
        ("search_engagement_lift", 0.10, 0.04, "rate"),
    ],
    "mfg-discrete": [
        ("oee_pct", 0.78, 0.07, "rate"),
        ("defect_ppm", 580.0, 220.0, "ppm"),
        ("edge_wan_gb", 6.2, 2.4, "GB/hr"),
    ],
    "mfg-process": [
        ("yield_pct", 0.91, 0.04, "rate"),
        ("sensor_temp_c", 72.5, 8.2, "C"),
        ("throughput_units_h", 4200.0, 950.0, "units/h"),
        ("batch_release_h", 38.0, 14.0, "h"),
    ],
    "energy-utilities": [
        ("frequency_hz_dev", 0.018, 0.012, "Hz"),
        ("transformer_temp_c", 68.0, 9.5, "C"),
        ("nerc_cip_evidence_age_d", 8.5, 4.0, "d"),
    ],
    "transportation-logistics": [
        ("hub_mttr_min", 14.0, 8.0, "min"),
        ("tracking_query_ms", 240.0, 110.0, "ms"),
        ("idle_min_per_vehicle", 32.0, 16.0, "min"),
    ],
    "travel-hospitality": [
        ("booking_search_ms", 295.0, 110.0, "ms"),
        ("irops_rebook_min", 22.0, 11.0, "min"),
        ("loyalty_ndcg", 0.72, 0.08, "score"),
    ],
    "automotive": [
        ("vehicle_ingest_kbs", 4.8, 1.9, "KB/s"),
        ("plant_mttr_min", 32.0, 14.0, "min"),
        ("recall_scope_d", 14.0, 7.0, "d"),
    ],
    "aerospace-defense": [
        ("mission_telemetry_ms", 180.0, 72.0, "ms"),
        ("rmf_evidence_age_d", 10.5, 5.5, "d"),
        ("turn_time_min", 132.0, 48.0, "min"),
    ],
}


# Per-industry segment dimension. Used in the by-segment breakdown panel.
_INDUSTRY_SEGMENTS: Dict[str, List[str]] = {
    "fsi-banking": ["retail", "commercial", "investment", "private", "treasury"],
    "fsi-insurance": ["pc", "life", "reinsurance", "specialty"],
    "fsi-capital-markets": ["equities", "fx", "fixed-income", "commodities", "derivatives"],
    "gov-federal": ["civilian", "dod", "intel", "judicial"],
    "gov-state-local": ["state", "county", "city", "k12", "higher-ed"],
    "healthcare-providers": ["acute", "ambulatory", "specialty-clinic", "imaging"],
    "healthcare-payers": ["medicare", "medicaid", "commercial", "exchange"],
    "pharma-life-sciences": ["discovery", "clinical-ops", "manufacturing", "commercial"],
    "retail-ecommerce": ["apparel", "electronics", "home", "beauty", "marketplace"],
    "retail-brick-mortar": ["big-box", "grocery", "specialty", "convenience"],
    "telco": ["mobile", "fixed-broadband", "enterprise", "wholesale"],
    "media-streaming": ["svod", "avod", "live-sports", "gaming"],
    "tech-saas": ["dev-tools", "data-platform", "vertical-saas", "horizontal-saas"],
    "mfg-discrete": ["electronics", "white-goods", "industrial", "components"],
    "mfg-process": ["chemicals", "food-bev", "paper-pulp", "specialty"],
    "energy-utilities": ["generation", "transmission", "distribution", "oil-gas", "water"],
    "transportation-logistics": ["parcel", "freight", "rail", "ports", "last-mile"],
    "travel-hospitality": ["airline", "hotel", "ota", "cruise"],
    "automotive": ["bev", "phev", "ice", "commercial-vehicle"],
    "aerospace-defense": ["mission-systems", "mro", "space", "supplier-tier-2"],
}


_SEVERITIES: List[Tuple[str, float]] = [
    ("info", 0.55), ("low", 0.25), ("medium", 0.12), ("high", 0.06), ("critical", 0.02),
]


def _doc_count_targets(industry_id: str, high_stake: bool,
                       rng: random.Random) -> Dict[str, int]:
    """Pick per-index doc counts. Deterministic given the rng."""
    if high_stake:
        # 3500-5000 docs total across 4 indices.
        events = rng.randint(1600, 2300)
        alerts = rng.randint(700, 1100)
        audit = rng.randint(600, 950)
        compliance = rng.randint(600, 850)
        return {"events": events, "alerts": alerts, "audit": audit,
                "compliance": compliance}
    # 800-3000 docs total across 3 indices.
    events = rng.randint(500, 1400)
    alerts = rng.randint(180, 600)
    audit = rng.randint(150, 500)
    return {"events": events, "alerts": alerts, "audit": audit}


def _gen_doc(rng: random.Random, industry_id: str, segments: List[str],
             metrics: List[Tuple[str, float, float, str]],
             regulations: List[str], kind: str, ts: datetime) -> Dict[str, Any]:
    doc: Dict[str, Any] = {
        "@timestamp": ts.isoformat(),
        "industry_id": industry_id,
        "segment": rng.choice(segments) if segments else "general",
        "kind": kind,
        "severity": _weighted_choice(rng, _SEVERITIES),
        "region": rng.choice(["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"]),
    }
    for fname, mean, stdev, unit in metrics:
        # Clamp negatives away for fields that should not go below zero.
        val = rng.gauss(mean, stdev)
        if "_ms" in fname or "_s" in fname or "amount" in fname or fname.endswith("_h") \
                or fname.endswith("_min") or fname.endswith("_d") \
                or fname.endswith("_pct") or fname.endswith("_rate") \
                or "score" in fname or "count" in fname or "_ppm" in fname \
                or "_gb" in fname or "_kbs" in fname or "ndcg" in fname:
            val = max(0.0, val)
        doc[fname] = round(val, 4)
        doc[f"{fname}_unit"] = unit
    if regulations:
        doc["regulation"] = rng.choice(regulations)
    if kind == "alert":
        doc["alert_score"] = round(min(1.0, max(0.0, rng.gauss(0.55, 0.22))), 3)
        doc["status"] = _weighted_choice(rng, [
            ("open", 0.45), ("triaged", 0.32), ("closed", 0.18), ("suppressed", 0.05)
        ])
    if kind == "audit":
        doc["actor"] = rng.choice(["service-account", "operator", "system", "auditor"])
        doc["outcome"] = _weighted_choice(rng, [("success", 0.88), ("failure", 0.12)])
    if kind == "compliance":
        doc["control_id"] = rng.choice([
            "AC-2", "AU-3", "CM-7", "IR-4", "SC-7", "SI-4", "RA-5", "PR.AC", "DE.CM",
        ])
        doc["compliant"] = rng.random() > 0.18
    return doc


def _generate_documents(industry_id: str, indices: Dict[str, str],
                        segments: List[str],
                        metrics: List[Tuple[str, float, float, str]],
                        regulations: List[str],
                        counts: Dict[str, int],
                        seed: int) -> Dict[str, List[Dict[str, Any]]]:
    rng = _rng_for(industry_id, seed)
    now = datetime.now(timezone.utc)
    span_days = 30
    out: Dict[str, List[Dict[str, Any]]] = {}
    kind_map = {"events": "event", "alerts": "alert", "audit": "audit",
                "compliance": "compliance"}
    for key, index_name in indices.items():
        kind = kind_map.get(key, "event")
        n = counts[key]
        docs: List[Dict[str, Any]] = []
        for _ in range(n):
            # Walk timestamps backwards over 30 days with diurnal bunching.
            offset_s = rng.random() * span_days * 24 * 3600
            ts = now - timedelta(seconds=offset_s)
            docs.append(_gen_doc(rng, industry_id, segments, metrics,
                                 regulations, kind, ts))
        out[index_name] = docs
    return out


# ---------------------------------------------------------------- Mappings ---------

def _build_mappings(indices: Dict[str, str],
                    metrics: List[Tuple[str, float, float, str]]) -> Dict[str, Dict[str, Any]]:
    base_props: Dict[str, Any] = {
        "@timestamp": {"type": "date"},
        "industry_id": {"type": "keyword"},
        "segment": {"type": "keyword"},
        "kind": {"type": "keyword"},
        "severity": {"type": "keyword"},
        "region": {"type": "keyword"},
        "regulation": {"type": "keyword"},
        "alert_score": {"type": "float"},
        "status": {"type": "keyword"},
        "actor": {"type": "keyword"},
        "outcome": {"type": "keyword"},
        "control_id": {"type": "keyword"},
        "compliant": {"type": "boolean"},
    }
    for fname, _m, _s, _u in metrics:
        base_props[fname] = {"type": "float"}
        base_props[f"{fname}_unit"] = {"type": "keyword"}
    mapping = {"properties": base_props}
    return {name: mapping for name in indices.values()}


# ---------------------------------------------------------------- Vega specs ------

def _vega_bar_severity(events_index: str) -> Dict[str, Any]:
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "description": "Alert severity distribution",
        "data": {"values": [
            {"severity": "info", "count": 55},
            {"severity": "low", "count": 25},
            {"severity": "medium", "count": 12},
            {"severity": "high", "count": 6},
            {"severity": "critical", "count": 2},
        ]},
        "mark": {"type": "bar", "tooltip": True},
        "encoding": {
            "x": {"field": "severity", "type": "ordinal",
                  "sort": ["info", "low", "medium", "high", "critical"]},
            "y": {"field": "count", "type": "quantitative"},
            "color": {"field": "severity", "type": "nominal"},
        },
    }


def _vega_kpi_trend(primary_metric: str, mean: float) -> Dict[str, Any]:
    # 30 daily points with mild variance + a clear improvement after day 18
    # (the "Elastic deployed" inflection). Deterministic.
    rng = random.Random(hash(primary_metric) & 0xFFFFFFFF)
    values = []
    for d in range(30):
        # Improvement curve: tail drops 30%.
        factor = 1.0 - 0.30 * max(0.0, (d - 17) / 12.0)
        v = mean * factor * (0.85 + 0.30 * rng.random())
        values.append({"day": d + 1, "value": round(v, 3)})
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "description": f"{primary_metric} 30-day trend",
        "data": {"values": values},
        "mark": {"type": "line", "tooltip": True, "point": True},
        "encoding": {
            "x": {"field": "day", "type": "quantitative", "title": "Day"},
            "y": {"field": "value", "type": "quantitative",
                  "title": primary_metric},
        },
    }


def _vega_segment_breakdown(metric: str, segments: List[str]) -> Dict[str, Any]:
    rng = random.Random((hash(metric) ^ hash(",".join(segments))) & 0xFFFFFFFF)
    values = [{"segment": s, "value": round(50 + 50 * rng.random(), 2)}
              for s in segments]
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "description": f"{metric} by segment",
        "data": {"values": values},
        "mark": {"type": "bar", "tooltip": True},
        "encoding": {
            "x": {"field": "segment", "type": "nominal"},
            "y": {"field": "value", "type": "quantitative", "title": metric},
            "color": {"field": "segment", "type": "nominal"},
        },
    }


def _vega_regulation_counts(regulations: List[str]) -> Dict[str, Any]:
    rng = random.Random(hash(",".join(regulations)) & 0xFFFFFFFF)
    values = [{"regulation": r, "events": rng.randint(40, 380)}
              for r in regulations]
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "description": "Regulatory dimension counts",
        "data": {"values": values},
        "mark": {"type": "bar", "tooltip": True},
        "encoding": {
            "x": {"field": "regulation", "type": "nominal"},
            "y": {"field": "events", "type": "quantitative"},
            "color": {"field": "regulation", "type": "nominal"},
        },
    }


def _vega_competitor_landscape(competitors: List[str]) -> Dict[str, Any]:
    # Two-axis bar: cost-per-GB vs feature-fit, deterministic.
    rng = random.Random(hash(",".join(competitors)) & 0xFFFFFFFF)
    values = [{"vendor": "Elastic", "cost_index": 38, "fit_score": 92}]
    for c in competitors[:4]:
        name = c.replace("battlecard-", "").replace("-", " ").title()
        values.append({
            "vendor": name,
            "cost_index": rng.randint(60, 100),
            "fit_score": rng.randint(45, 80),
        })
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "description": "Competitive landscape",
        "data": {"values": values},
        "mark": {"type": "circle", "tooltip": True, "size": 240},
        "encoding": {
            "x": {"field": "cost_index", "type": "quantitative",
                  "title": "Cost index (lower is better)"},
            "y": {"field": "fit_score", "type": "quantitative",
                  "title": "Industry feature fit"},
            "color": {"field": "vendor", "type": "nominal"},
            "tooltip": [{"field": "vendor"}, {"field": "cost_index"},
                        {"field": "fit_score"}],
        },
    }


def _vega_proof_point(metric: str, target: float) -> Dict[str, Any]:
    rng = random.Random(hash(metric) & 0xFFFFFFFF)
    rows = [{"state": "Baseline", "value": round(target, 3)},
            {"state": "With Elastic", "value": round(target * 0.55, 3)}]
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "description": f"Proof point for {metric}",
        "data": {"values": rows},
        "mark": {"type": "bar", "tooltip": True},
        "encoding": {
            "x": {"field": "state", "type": "nominal"},
            "y": {"field": "value", "type": "quantitative", "title": metric},
            "color": {"field": "state", "type": "nominal"},
        },
    }


# ---------------------------------------------------------------- Markdown blocks --

def _md_pain_headline(industry: Dict[str, Any], customer: str) -> str:
    personas = industry.get("personas", [])
    lines = [f"## Customer pain (FE talk track)\n\n**Customer:** {customer}\n"]
    lines.append(f"_{industry.get('summary', '')}_\n")
    if personas:
        lines.append("**Top pains we are uniquely positioned to absorb:**\n")
        for p in personas[:3]:
            lines.append(f"- **{p.get('role', 'Stakeholder')}** - {p.get('pain', '')}")
    lines.append("")
    lines.append("**Story to tell:** lead with the persona pain, anchor on the KPI, "
                 "close on the regulation. The dashboards on this view back each beat "
                 "with synthetic but realistic data.")
    return "\n".join(lines)


def _md_competitive(industry: Dict[str, Any]) -> str:
    comp = industry.get("top_competitors", [])
    pretty = ", ".join(c.replace("battlecard-", "").replace("-", " ").title()
                       for c in comp) or "n/a"
    return ("### Competitive landscape\n\n"
            f"Where the customer is comparing us: **{pretty}**.\n\n"
            f"- {industry.get('elastic_wins_when', '')}\n"
            f"- Watch out: {industry.get('elastic_loses_when', '')}")


def _md_compliance(industry: Dict[str, Any]) -> str:
    regs = industry.get("regulations", [])
    if not regs:
        return "### Compliance posture\n\nNo specific regulations registered."
    body = "\n".join(f"- **{r}** - Elastic ships pre-built detection content and audit retention."
                     for r in regs)
    return "### Compliance posture\n\n" + body


def _md_elastic_wins(industry: Dict[str, Any]) -> str:
    return ("### Elastic wins when\n\n"
            f"> {industry.get('elastic_wins_when', '')}\n\n"
            "Use this as the qualifying signal in MEDDPICC `Decision Criteria`.")


def _md_kpi_proof(industry: Dict[str, Any]) -> str:
    kpis = industry.get("kpis", [])
    if not kpis:
        return "### Proof points\n\n(no KPI catalog)"
    body = "\n".join(f"- **{k.get('metric','')}** -> {k.get('value','')}"
                     for k in kpis)
    return "### Technical proof points\n\n" + body


def _md_customer_header(industry: Dict[str, Any], customer: str) -> str:
    return (f"## {customer} - Operations View\n\n"
            f"_{industry.get('summary','')}_\n\n"
            "Operational KPIs for the {industry} team. Trends below cover the "
            "last 30 days with the inflection point representing the post-Elastic "
            "rollout window.").replace("{industry}", industry.get("name", "team"))


def _md_customer_outcomes(industry: Dict[str, Any]) -> str:
    kpis = industry.get("kpis", [])
    if not kpis:
        return "### Outcomes\n\n(no KPIs registered)"
    body = "\n".join(f"- **{k.get('metric','')}** -> {k.get('value','')}"
                     for k in kpis)
    return ("### Outcomes we are tracking\n\n" + body + "\n\n"
            "Inflection on day 18 of the trend chart shows the post-rollout step "
            "change in the primary KPI.")


# ---------------------------------------------------------------- FE superset helpers

# Title-keyword based value-callout lookup. Each entry is a 2-3 line FE-value
# blurb that explains why the chart matters in the conversation and the
# talking point to drop. Keywords are matched case-insensitively against the
# panel title. First match wins; falls through to a generic callout.
_FE_CALLOUT_RULES: List[Tuple[str, Tuple[str, str]]] = [
    ("severity", (
        "Severity mix is your noise-vs-signal anchor",
        "Use this when the customer brags about alert volume. Tie high+critical "
        "share to the analyst hours they are burning today and pivot into the "
        "Splunk-vs-Elastic cost-per-detection talk track.",
    )),
    ("trend", (
        "30-day trend is the post-Elastic inflection",
        "Day-18 is the deliberate rollout cut. Walk left-to-right, name the "
        "operational pain in the first half, then claim the delta as quantified "
        "value. Pair with the KPI in the proof-points block.",
    )),
    ("segment", (
        "Segment breakdown surfaces the wedge",
        "Find the worst segment, anchor it to the persona who owns it, and use "
        "it as the land-and-expand wedge for phase 2. Avoid quoting absolute "
        "numbers - this is synthetic.",
    )),
    ("regulation", (
        "Regulatory dimension is your compliance moat",
        "Lead with the regulation the customer named in discovery. Use this to "
        "redirect away from feature-by-feature comparisons and toward audit-cost "
        "reduction (the angle Splunk and Datadog can not easily counter).",
    )),
    ("compliance", (
        "Compliance posture - the SIEM-replacement door opener",
        "Anchor on the named regulation, then pivot to retention cost. Most "
        "Splunk shops are paying premium for cold data that Elastic stores at "
        "1/5 the price with searchable snapshots.",
    )),
    ("competitive", (
        "Competitive map - position before they price-shop",
        "Place yourself in the lower-right (low cost, high fit). If the customer "
        "is on Splunk or Datadog, that is the displacement story. If they are "
        "on Microsoft Sentinel, lead with feature-fit, not price.",
    )),
    ("proof point", (
        "Proof point chart - the receipt",
        "This is the 'show me the money' panel. Use the Baseline -> With Elastic "
        "delta as the SKO-grade soundbite. Reinforce with one named reference "
        "from the industry battle-pack.",
    )),
    ("recovery", (
        "Recovery timeline - tells the MTTR story",
        "Use this to anchor MTTR conversations. The shape of the curve is the "
        "demo - widen the y-axis to make the recovery slope obvious.",
    )),
    ("funnel", (
        "Funnel chart - business impact in dollars",
        "Translate every dropped session into revenue. CFO-grade language: do "
        "not say 'p99' here, say 'we recover $X per minute of avoided "
        "abandonment'.",
    )),
    ("error", (
        "Errors by service - finds the blast radius",
        "Use this to demonstrate root-cause-in-seconds against Splunk's "
        "search-language gymnastics. Click into a service to show pivoting.",
    )),
    ("p99", (
        "p99 latency - the SRE proof panel",
        "Engineering buyers care about this curve. Anchor on the SLO line; the "
        "spike is where the customer is losing trust today.",
    )),
    ("cart", (
        "Cart value lost - revenue at risk",
        "CFO panel. Convert minutes-of-outage to dollars; this is the wedge "
        "that gets observability funded outside of the SRE budget.",
    )),
    ("by service", (
        "By-service breakdown - blast radius story",
        "Use to localise the incident to one service and demonstrate the "
        "drill-down speed Elastic gives vs. log-grepping in Splunk.",
    )),
    ("by job", (
        "ML job breakdown - shows we did the modeling",
        "Reinforces that the alerts are not rule-based. Tie this to the fraud "
        "false-positive rate; most rule-based shops are at 20-30%.",
    )),
    ("by ring", (
        "Fraud ring view - the AML story",
        "Use the ring colour to demo graph-style pivots in Elastic. This is "
        "the panel that closes the Head of Fraud persona.",
    )),
    ("country", (
        "Geo distribution - shows the surface area",
        "Lead with the unexpected country. Two beats of silence, then the "
        "Elastic native geo-IP story.",
    )),
    ("loss prevented", (
        "Loss prevented vs realised - the CFO close",
        "Subtract realised from prevented for the dollar number. Round to a "
        "nice integer; do not over-precision in front of finance.",
    )),
    ("volume", (
        "Volume over time - establishes the workload",
        "Use to right-size the proposal. The peak-to-trough ratio tells you "
        "whether the customer needs hot tier or can land mostly on frozen.",
    )),
    ("alerts", (
        "Alerts panel - your detection efficacy proof",
        "Anchor on the high+critical bucket. Quote the customer's own SOC "
        "intake number back to them; this panel turns it into headcount math.",
    )),
    ("outcome", (
        "Outcomes panel - the close-the-loop slide",
        "Each row is a CFO-grade promise. Read two out loud, then ask which "
        "one their board would buy this quarter.",
    )),
    ("kpi", (
        "KPI panel - the receipts board",
        "Use as the final summary; tie each line back to a chart above. This "
        "is the slide they will screenshot to their boss.",
    )),
    ("overview", (
        "Overview panel - sets the room",
        "Read the headline aloud, name the customer (fictional), and let it "
        "anchor the next 8 minutes of demo.",
    )),
]


def _fe_callout_for_title(title: str) -> Tuple[str, str]:
    t = (title or "").lower()
    for kw, payload in _FE_CALLOUT_RULES:
        if kw in t:
            return payload
    return (
        "FE value callout",
        "Use this chart to anchor the next question; name the persona who feels "
        "the pain and tie the shape of the curve to a dollar number or a "
        "regulation they already mentioned.",
    )


def _value_callout_markdown(title: str, body: str) -> str:
    """Styled markdown body for an FE value callout. ASCII dashes only."""
    return (
        f"**FE value -> {title}**\n\n"
        f"> {body}\n\n"
        "_Pair the next chart with this talking point. Keep it 15 seconds._"
    )


def _value_callout_panel(panel_id: str, x: int, y: int, w: int, h: int,
                         for_title: str) -> Dict[str, Any]:
    """Build a small markdown panel that prefaces a customer chart with the
    FE-value talk track. Picks the body via title-keyword heuristics."""
    title, body = _fe_callout_for_title(for_title)
    md = _value_callout_markdown(title, body)
    return _bf._markdown_panel(panel_id, x, y, w, h, md, f"FE value: {title}")


def _discovery_questions_md(industry: Dict[str, Any]) -> str:
    personas = industry.get("personas") or []
    lines = [
        "### Discovery questions (use these first)",
        "",
        "Open with the persona's pain, then ask the question. Listen for the "
        "regulation, the incumbent vendor, and the renewal date.",
        "",
    ]
    for p in personas[:4]:
        role = p.get("role", "Stakeholder")
        pain = p.get("pain", "")
        question = _persona_question(role, pain)
        lines.append(f"- **{role}** - _{pain}_")
        lines.append(f"  - Ask: {question}")
    if not personas:
        lines.append("- (no persona catalog registered for this industry)")
    return "\n".join(lines)


def _persona_question(role: str, pain: str) -> str:
    role_l = role.lower()
    if "ciso" in role_l or "security" in role_l:
        return ("What did your last SIEM renewal cost, and what would you do "
                "with a 40-60% reduction in that line item?")
    if "compliance" in role_l or "audit" in role_l:
        return ("How many person-weeks did your last audit evidence pull take, "
                "and which control still requires manual screenshots?")
    if "observ" in role_l or "sre" in role_l or "platform" in role_l:
        return ("Where is your team today on time-to-detect for a service-"
                "level incident, and what does that cost you per outage hour?")
    if "fraud" in role_l:
        return ("What is your current false-positive rate on fraud alerts, "
                "and what is it costing you in analyst time?")
    if "cio" in role_l or "data" in role_l or "search" in role_l:
        return ("Which customer-facing search experience is most expensive "
                "today, and how is that latency tracked against revenue?")
    if "owner" in role_l or "manager" in role_l or "director" in role_l:
        return ("If you could collapse two of your current tools onto one "
                "platform this fiscal year, which two would they be?")
    return ("Which of the pains you just described would your board pay to "
            "remove this quarter?")


def _say_donot_say_md(industry: Dict[str, Any]) -> str:
    competitors = industry.get("top_competitors") or []
    has_splunk = any("splunk" in c.lower() for c in competitors)
    has_datadog = any("datadog" in c.lower() for c in competitors)
    has_sentinel = any("sentinel" in c.lower() for c in competitors)
    say: List[str] = [
        "Frame Elastic as the **search-powered platform** under SIEM, "
        "observability, and customer search - one engine, three jobs.",
        "Lead with the **named regulation** the customer raised, not with "
        "features. Compliance language closes deals; feature lists do not.",
        "When pricing comes up, anchor on **TCO per ingested GB** plus "
        "**searchable snapshots**, not list price per node.",
    ]
    do_not: List[str] = [
        "Do not say 'Elastic is cheap'. Say 'Elastic gives you predictable "
        "cost at scale'. Cheap implies trade-offs the buyer will hunt for.",
        "Do not bash the incumbent by name in the room. Say 'the legacy "
        "platform' or 'your current SIEM' and let the customer fill the gap.",
        "Do not over-promise on out-of-the-box ML. Say 'pre-built jobs you "
        "can tune in a day' - it sets the right expectation.",
    ]
    if has_splunk:
        say.append("With Splunk in the room: lead with **ingest cost per TB** "
                   "and **SPL-to-ES|QL translation** (we have the tool).")
        do_not.append("Do not promise a 1:1 SPL drop-in. The translation is "
                      "fast but it is a migration, not a copy-paste.")
    if has_datadog:
        say.append("With Datadog in the room: lead with **cardinality cost** "
                   "and **logs-on-the-same-platform-as-traces**.")
        do_not.append("Do not get pulled into APM-vs-APM line-by-line. Re-frame "
                      "to 'one query layer across logs, metrics, traces'.")
    if has_sentinel:
        say.append("With Sentinel in the room: lead with **multi-cloud** and "
                   "**non-Azure data sources** (where Sentinel ingest is "
                   "punitive).")
        do_not.append("Do not attack the E5 bundle economics. You will lose. "
                      "Re-frame to capability gaps in non-Microsoft estates.")
    say_lines = "\n".join(f"- {s}" for s in say)
    do_not_lines = "\n".join(f"- {s}" for s in do_not)
    return (
        "### Say this / do not say this (pre-sales playbook)\n\n"
        "Built from Search 101 + the Observability How-NOT-to-Sell deck. "
        "Pin this open during the demo.\n\n"
        "**Say this:**\n\n" + say_lines + "\n\n"
        "**Do not say this:**\n\n" + do_not_lines
    )


def _fe_intro_md(industry: Dict[str, Any], customer: str,
                 customer_panel_count: int, fe_only_count: int) -> str:
    return (
        "## FE dashboard - superset of the customer view\n\n"
        f"**Customer:** {customer}  \n"
        f"_{industry.get('summary','')}_\n\n"
        "This dashboard is the **strict superset** of the customer dashboard. "
        f"Every one of the {customer_panel_count} customer panels is shown "
        "below, each prefaced by a teal **FE value callout** that explains "
        "why the chart matters in the conversation and the talking point to "
        f"drop. Below the customer panels you will find {fe_only_count} "
        "FE-only blocks: competitive landscape, compliance posture, proof "
        "points, discovery questions, and the say-this/do-not-say-this "
        "playbook.\n\n"
        "Walk top-to-bottom in the demo. Each callout is a 15-second beat; "
        "each chart is a 45-second beat."
    )


def _wrap_customer_panels_with_callouts(
    customer_panels: List[Dict[str, Any]],
    starting_y: int = 0,
    id_prefix: str = "fe-wrap",
) -> Tuple[List[Dict[str, Any]], int]:
    """Take the unmodified customer panels and return a new list where each
    panel is preceded by a small FE-value callout markdown panel. Vertical
    layout is rebuilt: every customer row gets a 5-unit-tall callout slab on
    top spanning the full width (w=48). The customer panel is shifted down
    and its grid x/y are rewritten so the new layout flows cleanly.

    Returns (panels, next_y).

    The input list is NOT mutated; we deep-copy each panel.
    """
    out: List[Dict[str, Any]] = []
    y = starting_y
    # Walk customer panels in declared order. When two panels share the same
    # original y (a side-by-side row), they share one callout slab.
    i = 0
    n = len(customer_panels)
    seen_rows: List[List[Dict[str, Any]]] = []
    cur_row: List[Dict[str, Any]] = []
    last_y = None
    for p in customer_panels:
        py = p.get("gridData", {}).get("y", 0)
        if last_y is None or py == last_y:
            cur_row.append(p)
        else:
            seen_rows.append(cur_row)
            cur_row = [p]
        last_y = py
    if cur_row:
        seen_rows.append(cur_row)

    cidx = 0
    for row_idx, row in enumerate(seen_rows):
        # One callout slab per row. Title comes from the first panel in the row.
        first_title = row[0].get("title", "") or "panel"
        cidx += 1
        callout = _value_callout_panel(
            f"{id_prefix}-co-{row_idx + 1}", 0, y, 48, 5, first_title,
        )
        out.append(callout)
        y += 5
        # Find the tallest panel in the row to advance y after the row.
        row_max_h = 0
        for j, panel in enumerate(row):
            # Deep-copy via json round-trip so we can safely rewrite gridData.
            np = json.loads(json.dumps(panel))
            gd = np.get("gridData", {})
            orig_w = gd.get("w", 24)
            orig_h = gd.get("h", 12)
            orig_x = gd.get("x", 0)
            # Preserve relative x but stack rows at our new y.
            new_x = orig_x
            new_id = f"{id_prefix}-{row_idx + 1}-{j + 1}"
            gd["x"] = new_x
            gd["y"] = y
            gd["i"] = new_id
            gd["w"] = orig_w
            gd["h"] = orig_h
            np["gridData"] = gd
            np["panelIndex"] = new_id
            out.append(np)
            if orig_h > row_max_h:
                row_max_h = orig_h
        y += row_max_h
    return out, y


def build_fe_superset_panels(
    industry: Dict[str, Any],
    customer: str,
    customer_panels: List[Dict[str, Any]],
    fe_only_extras: List[Dict[str, Any]] = None,
    id_prefix: str = "fe",
) -> List[Dict[str, Any]]:
    """Compose the full FE-side superset dashboard.

    Layout: [FE intro (full width)] + [for each customer row: callout + row] +
    [fe_only_extras...] + [Discovery questions (full width)] +
    [Say / do not say (full width)].

    `customer_panels` is treated as immutable. `fe_only_extras` is a list of
    pre-built panels (markdown or vega); their gridData y is rewritten so
    they stack below the customer panels.
    """
    fe_only_extras = fe_only_extras or []
    # 1) Intro panel.
    intro_md = _fe_intro_md(industry, customer,
                            customer_panel_count=len(customer_panels),
                            fe_only_count=len(fe_only_extras) + 2)
    panels: List[Dict[str, Any]] = []
    y = 0
    panels.append(_bf._markdown_panel(f"{id_prefix}-intro", 0, y, 48, 10,
                                      intro_md, "FE superset - how to use"))
    y += 10

    # 2) Customer panels, each row prefaced with an FE-value callout.
    wrapped, y = _wrap_customer_panels_with_callouts(
        customer_panels, starting_y=y, id_prefix=f"{id_prefix}-cu",
    )
    panels.extend(wrapped)

    # 3) FE-only extras (re-stacked).
    for i, p in enumerate(fe_only_extras):
        np = json.loads(json.dumps(p))
        gd = np.get("gridData", {})
        orig_w = gd.get("w", 48)
        orig_h = gd.get("h", 10)
        orig_x = gd.get("x", 0)
        # Side-by-side panels in extras share the same original y; we honour
        # that by detecting a non-zero x to mean "same row as the previous".
        if i > 0 and orig_x > 0:
            # Reuse previous y by stepping back one row height.
            gd["y"] = y - orig_h
        else:
            gd["y"] = y
            y += orig_h
        new_id = f"{id_prefix}-extra-{i + 1}"
        gd["i"] = new_id
        gd["x"] = orig_x
        gd["w"] = orig_w
        gd["h"] = orig_h
        np["gridData"] = gd
        np["panelIndex"] = new_id
        panels.append(np)

    # 4) Discovery questions block.
    disc_md = _discovery_questions_md(industry)
    panels.append(_bf._markdown_panel(f"{id_prefix}-disc", 0, y, 48, 12,
                                      disc_md, "Discovery questions"))
    y += 12

    # 5) Say / do not say block.
    sd_md = _say_donot_say_md(industry)
    panels.append(_bf._markdown_panel(f"{id_prefix}-say", 0, y, 48, 14,
                                      sd_md, "Say this / do not say this"))
    y += 14

    return panels


# ---------------------------------------------------------------- Panel builders ---

def _panel_id(prefix: str, i: int) -> str:
    return f"{prefix}-p{i}"


def _build_fe_only_extras(industry: Dict[str, Any], customer: str,
                          metrics: List[Tuple[str, float, float, str]],
                          segments: List[str],
                          high_stake: bool) -> List[Dict[str, Any]]:
    """FE-only extras (competitive landscape, compliance, proof points, wins).
    These are appended after the customer-superset block. The y coordinates
    are placeholders; build_fe_superset_panels re-stacks them."""
    regs = industry.get("regulations", [])
    comp = industry.get("top_competitors", [])
    primary_metric, mean, _s, _u = metrics[0]
    extras: List[Dict[str, Any]] = []
    extras.append(_bf._vega_panel(_panel_id("fe-comp", 1), 0, 0, 24, 12,
                                  "Competitive landscape",
                                  _vega_competitor_landscape(comp)))
    extras.append(_bf._markdown_panel(_panel_id("fe-md-comp", 2), 24, 0, 24, 12,
                                      _md_competitive(industry),
                                      "Competitive talk track"))
    extras.append(_bf._vega_panel(_panel_id("fe-reg", 3), 0, 0, 24, 12,
                                  "Compliance dimensions",
                                  _vega_regulation_counts(regs or ["n/a"])))
    extras.append(_bf._markdown_panel(_panel_id("fe-md-comp2", 4), 24, 0, 24, 12,
                                      _md_compliance(industry),
                                      "Compliance posture"))
    extras.append(_bf._markdown_panel(_panel_id("fe-md-wins", 5), 0, 0, 24, 10,
                                      _md_elastic_wins(industry),
                                      "Elastic wins when"))
    extras.append(_bf._markdown_panel(_panel_id("fe-md-kpi", 6), 24, 0, 24, 10,
                                      _md_kpi_proof(industry),
                                      "Proof points"))
    extras.append(_bf._vega_panel(_panel_id("fe-proof", 7), 0, 0, 48, 10,
                                  f"Proof point: {primary_metric}",
                                  _vega_proof_point(primary_metric, mean)))
    if high_stake and len(metrics) > 1:
        second = metrics[1][0]
        extras.append(_bf._vega_panel(_panel_id("fe-proof2", 8), 0, 0, 24, 10,
                                      f"Proof point: {second}",
                                      _vega_proof_point(second, metrics[1][1])))
        extras.append(_bf._vega_panel(_panel_id("fe-trend", 9), 24, 0, 24, 10,
                                      f"30-day trend: {primary_metric}",
                                      _vega_kpi_trend(primary_metric, mean)))
    return extras


def _build_fe_panels(industry: Dict[str, Any], customer: str,
                     metrics: List[Tuple[str, float, float, str]],
                     segments: List[str],
                     high_stake: bool) -> List[Dict[str, Any]]:
    """FE dashboard = customer dashboard (each panel prefaced by a value
    callout) + FE-only extras + discovery questions + say/do-not-say."""
    cu_panels = _build_customer_panels(industry, customer, metrics, segments,
                                       high_stake)
    extras = _build_fe_only_extras(industry, customer, metrics, segments,
                                   high_stake)
    return build_fe_superset_panels(industry, customer, cu_panels,
                                    fe_only_extras=extras, id_prefix="fe-ind")


def _build_customer_panels(industry: Dict[str, Any], customer: str,
                           metrics: List[Tuple[str, float, float, str]],
                           segments: List[str],
                           high_stake: bool) -> List[Dict[str, Any]]:
    primary_metric, mean, _s, _u = metrics[0]
    regs = industry.get("regulations", [])
    panels: List[Dict[str, Any]] = []
    y = 0

    panels.append(_bf._markdown_panel(_panel_id("cu-md-hdr", 1), 0, y, 48, 8,
                                      _md_customer_header(industry, customer),
                                      "Overview"))
    y += 8
    panels.append(_bf._vega_panel(_panel_id("cu-trend", 2), 0, y, 48, 12,
                                  f"30-day trend: {primary_metric}",
                                  _vega_kpi_trend(primary_metric, mean)))
    y += 12
    panels.append(_bf._vega_panel(_panel_id("cu-seg", 3), 0, y, 24, 12,
                                  f"{primary_metric} by segment",
                                  _vega_segment_breakdown(primary_metric, segments)))
    panels.append(_bf._vega_panel(_panel_id("cu-sev", 4), 24, y, 24, 12,
                                  "Alerts by severity",
                                  _vega_bar_severity("")))
    y += 12
    panels.append(_bf._vega_panel(_panel_id("cu-reg", 5), 0, y, 24, 12,
                                  "Regulatory event counts",
                                  _vega_regulation_counts(regs or ["n/a"])))
    panels.append(_bf._markdown_panel(_panel_id("cu-md-out", 6), 24, y, 24, 12,
                                      _md_customer_outcomes(industry),
                                      "Outcomes"))
    y += 12
    if high_stake:
        # Two extra panels for high-stake industries.
        if len(metrics) > 1:
            second = metrics[1][0]
            panels.append(_bf._vega_panel(_panel_id("cu-trend2", 7), 0, y, 24, 10,
                                          f"30-day trend: {second}",
                                          _vega_kpi_trend(second, metrics[1][1])))
            panels.append(_bf._vega_panel(_panel_id("cu-seg2", 8), 24, y, 24, 10,
                                          f"{second} by segment",
                                          _vega_segment_breakdown(second, segments)))
            y += 10
    return panels


# ---------------------------------------------------------------- Factory ---------

def _dashboard_url(dashboard_id: str) -> str:
    return settings.kibana_url.rstrip("/") + f"/app/dashboards#/view/{dashboard_id}"


def build_industry_scenario(industry_config: Dict[str, Any]) -> Dict[str, Any]:
    """Build a full scenario surface for a single industry config.

    Returns a dict with the same public attributes the existing scenario modules
    expose (SCENARIO_ID, SCENARIO_TITLE, etc) plus callables for seed() and the
    panel/mapping/document builders. Callable values are bound to this industry,
    so the returned dict acts as a drop-in module-like namespace.
    """
    industry_id = str(industry_config.get("id", "")).strip()
    if not industry_id:
        raise ValueError("industry_config missing 'id'")
    industry_name = industry_config.get("name", industry_id)
    high_stake = industry_id in _HIGH_STAKE

    customer = _CUSTOMER_NAMES.get(industry_id, f"{industry_name} Demo Co.")
    indices = _build_index_map(industry_id, high_stake)
    metrics = _INDUSTRY_METRICS.get(industry_id) or [
        ("primary_metric", 100.0, 30.0, "units"),
        ("secondary_metric", 50.0, 18.0, "units"),
    ]
    segments = _INDUSTRY_SEGMENTS.get(industry_id) or ["segment-a", "segment-b"]

    scenario_id = f"industry-{industry_id}"
    dashboard_id = f"demo-industry-{industry_id}-dashboard"
    customer_dashboard_id = f"demo-industry-{industry_id}-customer-dashboard"
    title = f"Industry Demo - {industry_name}"
    description = (
        f"Synthetic demo dataset for {industry_name}. "
        f"Customer: {customer}. Indices: {', '.join(indices.values())}. "
        f"Includes an FE-facing story dashboard plus a customer-facing "
        f"operational KPI dashboard."
    )

    def get_mappings() -> Dict[str, Dict[str, Any]]:
        return _build_mappings(indices, metrics)

    def generate_documents(seed: int = _DEFAULT_SEED) -> Dict[str, List[Dict[str, Any]]]:
        rng = _rng_for(industry_id, seed)
        counts = _doc_count_targets(industry_id, high_stake, rng)
        return _generate_documents(
            industry_id, indices, segments, metrics,
            industry_config.get("regulations", []), counts, seed,
        )

    def get_dashboard_panels() -> List[Dict[str, Any]]:
        return _build_fe_panels(industry_config, customer, metrics, segments, high_stake)

    def get_customer_dashboard_panels() -> List[Dict[str, Any]]:
        return _build_customer_panels(industry_config, customer, metrics, segments,
                                      high_stake)

    def seed() -> Dict[str, Any]:
        started = time.time()
        if not settings.elasticsearch_api_key and not settings.elasticsearch_password:
            raise RuntimeError("Elasticsearch credentials not configured")
        if not settings.kibana_api_key:
            raise RuntimeError("KIBANA_API_KEY not configured")

        try:
            es = get_client()
        except Exception as exc:
            raise RuntimeError(f"Elasticsearch client init failed: {exc}") from exc

        mappings = get_mappings()
        docs_by_index = generate_documents()
        counts: Dict[str, int] = {}

        try:
            for index in indices.values():
                if es.indices.exists(index=index):
                    es.indices.delete(index=index)
                es.indices.create(index=index, mappings=mappings[index])
        except Exception as exc:
            raise RuntimeError(f"Elasticsearch index setup failed: {exc}") from exc

        for index, docs in docs_by_index.items():
            actions = ({"_index": index, "_source": d} for d in docs)
            success, errors = bulk(
                es, actions, chunk_size=500,
                refresh="wait_for", raise_on_error=False,
            )
            counts[index] = success
            n_errors = len(errors) if isinstance(errors, list) else 0
            log.info("industry_factory.bulk.indexed", scenario_id=scenario_id,
                     index=index, count=success, errors=n_errors)

        for index in indices.values():
            try:
                es.indices.refresh(index=index)
            except Exception as exc:
                log.warning("industry_factory.refresh.failed",
                            scenario_id=scenario_id, index=index, error=str(exc))

        # Dashboards.
        fe_id: str = dashboard_id
        fe_url: str = _dashboard_url(dashboard_id)
        cu_id: str = customer_dashboard_id
        cu_url: str = _dashboard_url(customer_dashboard_id)

        _bf._delete_dashboard(dashboard_id)
        try:
            fe_id, fe_url = _bf._create_one_dashboard(
                dashboard_id,
                f"[FE] {industry_name} - Story dashboard",
                f"Field Engineer view for {industry_name}. Customer: {customer}.",
                get_dashboard_panels(),
            )
        except Exception as exc:
            log.warning("industry_factory.dashboard.fe.failed",
                        scenario_id=scenario_id, error=str(exc))

        _bf._delete_dashboard(customer_dashboard_id)
        try:
            cu_id, cu_url = _bf._create_one_dashboard(
                customer_dashboard_id,
                f"[Customer] {customer} - Operations View",
                f"Customer-facing operations dashboard for {customer} ({industry_name}).",
                get_customer_dashboard_panels(),
            )
        except Exception as exc:
            log.warning("industry_factory.dashboard.customer.failed",
                        scenario_id=scenario_id, error=str(exc))

        elapsed = round(time.time() - started, 2)
        return {
            "ok": True,
            "scenario": scenario_id,
            "industry_id": industry_id,
            "customer_name": customer,
            "indices": counts,
            "doc_count": sum(counts.values()),
            "dashboard_id": fe_id,
            "dashboard_url": fe_url,
            "fe_dashboard_id": fe_id,
            "fe_dashboard_url": fe_url,
            "customer_dashboard_id": cu_id,
            "customer_dashboard_url": cu_url,
            "dashboard_url_customer": cu_url,
            "elapsed_seconds": elapsed,
        }

    return {
        "SCENARIO_ID": scenario_id,
        "SCENARIO_TITLE": title,
        "SCENARIO_DESCRIPTION": description,
        "INDICES": indices,
        "DASHBOARD_ID": dashboard_id,
        "CUSTOMER_DASHBOARD_ID": customer_dashboard_id,
        "INDUSTRY_ID": industry_id,
        "CUSTOMER_NAME": customer,
        "HIGH_STAKE": high_stake,
        "get_mappings": get_mappings,
        "generate_documents": generate_documents,
        "get_dashboard_panels": get_dashboard_panels,
        "get_customer_dashboard_panels": get_customer_dashboard_panels,
        "seed": seed,
    }
