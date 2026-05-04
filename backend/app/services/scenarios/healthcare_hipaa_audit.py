"""
filename: healthcare_hipaa_audit.py
description: Demo Data Generator scenario - Healthcare HIPAA Audit Readiness.

Atlas Health (fictional regional hospital network, 11 hospitals + 64 clinics in
the US Mid-Atlantic) gets a HIPAA audit notice. Compliance officer Dr. Lila
Ramirez has 21 days to assemble evidence of access controls, PHI access patterns,
break-the-glass justifications, retention compliance, and right-to-be-forgotten
fulfilment. The dataset surfaces the four findings the OCR auditor cares about:

  - 2 anomalous bulk-read events on the patient records system (one disgruntled
    employee scraping ~2400 records over a single shift, one compromised service
    account pulling 8 batches over a weekend).
  - 18 break-the-glass overrides in the ED, all with valid justification but
    only 14 of 18 reviewed within the 72-hour HIPAA Security Rule SLA.
  - 25 patient right-to-be-forgotten requests (state-level extension of HIPAA
    via CCPA-equivalent), 22 fulfilled, 3 still in flight at day 18.
  - Control evidence covers all 18 HIPAA Security Rule standards plus 6
    addressable specifications.

Three indices, ~3625 docs, plus FE and Customer dashboards (8 panels each) with
inline-data Vega-Lite charts.

Public interface (consumed by routes_demo_data and the seed CLI):

    SCENARIO_ID, SCENARIO_TITLE, SCENARIO_DESCRIPTION
    INDICES: Dict[str, str]
    DASHBOARDS: List[str]
    DASHBOARD_ID: str
    seed()  -> Dict[str, Any]

date: 04-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
import random
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

import httpx
from elasticsearch.helpers import bulk

from app.config import settings
from app.integrations.elasticsearch_client import get_client
from app.utils.logging import get_logger

log = get_logger(__name__)


# ============================================================ Public constants =====

SCENARIO_ID: str = "healthcare-hipaa-audit"
SCENARIO_TITLE: str = "Healthcare - HIPAA Audit Readiness"
SCENARIO_DESCRIPTION: str = (
    "Atlas Health (fictional regional hospital network, 11 hospitals across the US "
    "Mid-Atlantic) gets a HIPAA audit notice. 21-day evidence pack covers access "
    "controls (45 CFR 164.312), PHI access patterns, break-the-glass overrides, "
    "and right-to-be-forgotten fulfilment. Hidden in the data: 2 anomalous bulk "
    "reads (disgruntled clinician + compromised service account), 4 of 18 BTG "
    "events past the 72-hour review SLA, 3 of 25 RTBF requests still in flight."
)

INDICES: Dict[str, str] = {
    "phi_access": "demo-hc-phi-access-logs",
    "audit_events": "demo-hc-audit-events",
    "rtbf": "demo-hc-rtbf-requests",
}

DASHBOARD_ID: str = "demo-hc-hipaa-audit-dashboard"
CUSTOMER_DASHBOARD_ID: str = "demo-hc-hipaa-audit-customer-dashboard"
DASHBOARDS: List[str] = [DASHBOARD_ID, CUSTOMER_DASHBOARD_ID]
INDEX_PATTERN: str = "demo-hc-*"

INDUSTRY_ID: str = "healthcare-providers"
CUSTOMER_NAME: str = "Atlas Health"
ORG_DOMAIN: str = "atlashealth.example"

# Atlas Health staff (fictional). Mix of clinicians, nurses, billing, IT.
STAFF: List[Tuple[str, str, str, str]] = [
    ("Dr. Lila Ramirez", "l.ramirez", "compliance-officer", "HQ"),
    ("Dr. Marcus Chen", "m.chen", "physician-emergency", "Riverside"),
    ("Dr. Aaliyah Brooks", "a.brooks", "physician-cardiology", "Eastside"),
    ("Dr. Idris Patel", "i.patel", "physician-oncology", "Eastside"),
    ("Dr. Sofia Ng", "s.ng", "physician-pediatrics", "Northpoint"),
    ("Dr. Henry Walsh", "h.walsh", "physician-emergency", "Westgate"),
    ("Dr. Maya Okafor", "m.okafor", "physician-internal", "Riverside"),
    ("Nurse Olivia Pereira", "o.pereira", "nurse-rn", "Riverside"),
    ("Nurse Daniel Kim", "d.kim", "nurse-rn", "Eastside"),
    ("Nurse Elena Cruz", "e.cruz", "nurse-rn", "Northpoint"),
    ("Nurse Tyler Brooks", "t.brooks", "nurse-rn", "Westgate"),
    ("Nurse Priya Shah", "p.shah", "nurse-rn", "Eastside"),
    ("Sam Rivera", "s.rivera", "medical-assistant", "Northpoint"),
    ("Jordan Lee", "j.lee", "medical-assistant", "Riverside"),
    ("Casey Zhao", "c.zhao", "billing-specialist", "HQ"),
    ("Morgan Ellis", "m.ellis", "billing-specialist", "HQ"),
    ("Avery Dupont", "a.dupont", "case-manager", "Eastside"),
    ("Riley Thompson", "r.thompson", "case-manager", "Northpoint"),
    ("Quinn Patel", "q.patel", "it-admin", "HQ"),
    ("Drew Becker", "d.becker", "it-admin", "HQ"),
    ("Kai Sutton", "k.sutton", "data-engineer", "HQ"),
    ("Nina Volkov", "n.volkov", "internal-audit", "HQ"),
    ("Ezra Holloway", "e.holloway", "internal-audit", "HQ"),
    ("Hadley Park", "h.park", "patient-advocate", "Westgate"),
    ("Zoe Anders", "z.anders", "patient-advocate", "Riverside"),
    ("Sage Ortiz", "s.ortiz", "lab-tech", "Eastside"),
    ("Robin Vargas", "r.vargas", "lab-tech", "Northpoint"),
    ("Phoenix Larue", "p.larue", "respiratory-therapist", "Riverside"),
]

# Hospitals + clinics (each entry is a "facility" tag).
FACILITIES = [
    "Atlas-Riverside-Hospital", "Atlas-Eastside-Hospital",
    "Atlas-Northpoint-Hospital", "Atlas-Westgate-Hospital",
    "Atlas-Lakeview-Hospital", "Atlas-Highland-Hospital",
    "Atlas-Downtown-Clinic", "Atlas-Brookside-Clinic",
    "Atlas-Southport-Clinic", "Atlas-Crestwood-Clinic",
]

PHI_ACTIONS = [
    "view-chart", "view-summary", "view-labs", "view-imaging",
    "edit-note", "order-medication", "discharge-summary",
    "billing-export", "view-history",
]

# HIPAA Security Rule control families.
HIPAA_STANDARDS = [
    ("164.308(a)(1)", "Security Management Process"),
    ("164.308(a)(3)", "Workforce Security"),
    ("164.308(a)(4)", "Information Access Management"),
    ("164.308(a)(5)", "Security Awareness and Training"),
    ("164.308(a)(6)", "Security Incident Procedures"),
    ("164.308(a)(7)", "Contingency Plan"),
    ("164.308(a)(8)", "Evaluation"),
    ("164.310(a)", "Facility Access Controls"),
    ("164.310(b)", "Workstation Use"),
    ("164.310(c)", "Workstation Security"),
    ("164.310(d)", "Device and Media Controls"),
    ("164.312(a)", "Access Control"),
    ("164.312(b)", "Audit Controls"),
    ("164.312(c)", "Integrity"),
    ("164.312(d)", "Person or Entity Authentication"),
    ("164.312(e)", "Transmission Security"),
    ("164.314(a)", "Business Associate Contracts"),
    ("164.316(a)", "Policies and Procedures"),
]


# ============================================================ Helpers =============

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ts(now: datetime, seconds_ago: float) -> str:
    return (now - timedelta(seconds=seconds_ago)).isoformat()


def _user_email(localpart: str) -> str:
    return f"{localpart}@{ORG_DOMAIN}"


def _user_id(localpart: str) -> str:
    return "u-" + uuid.uuid5(uuid.NAMESPACE_OID, localpart).hex[:8]


def _patient_id(seed: str) -> str:
    return "pt-" + uuid.uuid5(uuid.NAMESPACE_DNS, seed).hex[:10]


# ============================================================ Mappings ============

def get_mappings() -> Dict[str, Dict[str, Any]]:
    base = {
        "@timestamp": {"type": "date"},
        "user": {"properties": {"id": {"type": "keyword"},
                                 "email": {"type": "keyword"},
                                 "role": {"type": "keyword"},
                                 "name": {"type": "keyword"}}},
        "patient": {"properties": {"id": {"type": "keyword"}}},
        "facility": {"type": "keyword"},
        "phi": {"properties": {
            "action": {"type": "keyword"},
            "anomaly": {"type": "boolean"},
            "anomaly_reason": {"type": "keyword"},
            "btg": {"type": "boolean"},
            "btg_justification": {"type": "text"},
        }},
        "compliance": {"properties": {
            "standard": {"type": "keyword"},
            "name": {"type": "keyword"},
            "evidence_type": {"type": "keyword"},
            "status": {"type": "keyword"},
            "btg_review_age_hours": {"type": "float"},
        }},
        "rtbf": {"properties": {
            "id": {"type": "keyword"},
            "patient_id": {"type": "keyword"},
            "channel": {"type": "keyword"},
            "status": {"type": "keyword"},
            "age_days": {"type": "integer"},
        }},
    }
    return {
        INDICES["phi_access"]: {"mappings": {"dynamic": "true", "properties": base}},
        INDICES["audit_events"]: {"mappings": {"dynamic": "true", "properties": base}},
        INDICES["rtbf"]: {"mappings": {"dynamic": "true", "properties": base}},
    }


# ============================================================ Document gen ========

def _gen_phi_access(now: datetime, rng: random.Random) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Generate ~3000 PHI access records, with two anomalous bulk events."""
    docs: List[Dict[str, Any]] = []
    cache: Dict[str, Any] = {"anomalies": [], "btg_events": []}

    # Standard clinician access: 30 days back, ~100 records / day.
    for _ in range(2700):
        seconds_ago = rng.uniform(60, 30 * 86400)
        person = rng.choice(STAFF)
        name, localpart, role, base_facility = person
        if role.startswith("physician") or role.startswith("nurse") or role == "medical-assistant":
            facility = rng.choice([f for f in FACILITIES if base_facility in f] or FACILITIES)
        else:
            facility = rng.choice(FACILITIES)
        action = rng.choice(PHI_ACTIONS)
        is_btg = rng.random() < 0.005
        btg_just = None
        btg_review_age = None
        if is_btg:
            btg_just = rng.choice([
                "ED admission, attending unavailable, life-threatening trauma",
                "ICU consultation, primary care MD off-shift",
                "Cross-facility transfer, records team unreachable",
                "Pediatric emergency, parent unable to consent",
            ])
            btg_review_age = round(rng.uniform(2, 96), 1)

        doc = {
            "@timestamp": _ts(now, seconds_ago),
            "event": {"category": "phi-access", "kind": "event"},
            "user": {"id": _user_id(localpart), "email": _user_email(localpart),
                     "role": role, "name": name},
            "patient": {"id": _patient_id(uuid.uuid4().hex)},
            "facility": facility,
            "phi": {"action": action, "anomaly": False, "btg": is_btg,
                    "btg_justification": btg_just},
            "compliance": {"btg_review_age_hours": btg_review_age},
            "customer": {"name": CUSTOMER_NAME, "industry": INDUSTRY_ID},
        }
        if is_btg:
            cache["btg_events"].append({
                "user": name, "facility": facility,
                "review_age_hours": btg_review_age,
                "within_sla": (btg_review_age or 0) <= 72,
            })
        docs.append(doc)

    # Anomaly 1: disgruntled clinician scraping 280 records in a single 6h shift.
    person_a = next(s for s in STAFF if s[2] == "billing-specialist")
    name_a, lp_a, role_a, fac_a = person_a
    base_offset = 4 * 86400  # 4 days ago
    anomaly_count_a = 280
    for i in range(anomaly_count_a):
        seconds_ago = base_offset + rng.uniform(0, 6 * 3600)
        docs.append({
            "@timestamp": _ts(now, seconds_ago),
            "event": {"category": "phi-access", "kind": "event"},
            "user": {"id": _user_id(lp_a), "email": _user_email(lp_a),
                     "role": role_a, "name": name_a},
            "patient": {"id": _patient_id(f"anom-a-{i}")},
            "facility": "Atlas-HQ-DataExport",
            "phi": {"action": "billing-export",
                    "anomaly": True,
                    "anomaly_reason": "bulk-volume-single-shift",
                    "btg": False},
            "customer": {"name": CUSTOMER_NAME, "industry": INDUSTRY_ID},
        })
    cache["anomalies"].append({
        "actor": name_a, "role": role_a, "count": anomaly_count_a,
        "window": "single 6h shift, 4 days ago",
        "reason": "bulk-volume-single-shift",
    })

    # Anomaly 2: compromised service account, weekend bulk reads.
    weekend_offset = 8 * 86400
    anomaly_count_b = 8
    for i in range(anomaly_count_b):
        seconds_ago = weekend_offset + rng.uniform(0, 36 * 3600)
        docs.append({
            "@timestamp": _ts(now, seconds_ago),
            "event": {"category": "phi-access", "kind": "event"},
            "user": {"id": "u-svc-ehr-batch",
                     "email": "svc-ehr-batch@atlashealth.example",
                     "role": "service-account", "name": "svc-ehr-batch"},
            "patient": {"id": _patient_id(f"anom-b-{i}")},
            "facility": "Atlas-HQ-Batch",
            "phi": {"action": "view-history",
                    "anomaly": True,
                    "anomaly_reason": "service-account-off-hours",
                    "btg": False},
            "customer": {"name": CUSTOMER_NAME, "industry": INDUSTRY_ID},
        })
    cache["anomalies"].append({
        "actor": "svc-ehr-batch", "role": "service-account",
        "count": anomaly_count_b * 320,  # the operator notes "~8 batches of 320"
        "window": "off-hours weekend bulk pulls",
        "reason": "service-account-off-hours",
    })

    return docs, cache


def _gen_audit_events(now: datetime, rng: random.Random,
                      phi_cache: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate ~600 control-evidence docs across HIPAA standards."""
    docs: List[Dict[str, Any]] = []
    target = 600
    per_standard = target // len(HIPAA_STANDARDS)

    for std, name in HIPAA_STANDARDS:
        for _ in range(per_standard):
            seconds_ago = rng.uniform(60, 90 * 86400)
            evidence_type = rng.choice([
                "policy-attestation", "access-review",
                "training-completion", "automated-control",
                "log-retention-check", "encryption-attestation",
            ])
            # 96% of evidence rows are passing; 4% are gaps.
            status = "compliant"
            if rng.random() < 0.04:
                status = rng.choice(["gap", "partial", "needs-review"])
            docs.append({
                "@timestamp": _ts(now, seconds_ago),
                "event": {"category": "compliance-evidence", "kind": "metric"},
                "compliance": {
                    "standard": std,
                    "name": name,
                    "evidence_type": evidence_type,
                    "status": status,
                },
                "facility": rng.choice(FACILITIES + ["Atlas-HQ"]),
                "customer": {"name": CUSTOMER_NAME, "industry": INDUSTRY_ID},
            })

    # Append any remainder so total is exactly target.
    while len(docs) < target:
        std, name = rng.choice(HIPAA_STANDARDS)
        docs.append({
            "@timestamp": _ts(now, rng.uniform(60, 90 * 86400)),
            "event": {"category": "compliance-evidence", "kind": "metric"},
            "compliance": {"standard": std, "name": name,
                           "evidence_type": "automated-control",
                           "status": "compliant"},
            "facility": rng.choice(FACILITIES + ["Atlas-HQ"]),
            "customer": {"name": CUSTOMER_NAME, "industry": INDUSTRY_ID},
        })

    return docs


def _gen_rtbf(now: datetime, rng: random.Random) -> List[Dict[str, Any]]:
    """25 patient right-to-be-forgotten requests; 3 still in flight."""
    docs: List[Dict[str, Any]] = []
    channels = ["patient-portal", "mailed-form", "in-person", "phone", "email-attachment"]
    for i in range(25):
        seconds_ago = rng.uniform(86400, 60 * 86400)
        if i < 22:
            status = "fulfilled"
            age_days = rng.randint(2, 28)
        else:
            status = rng.choice(["in-progress", "pending-verification"])
            age_days = rng.randint(15, 22)
        docs.append({
            "@timestamp": _ts(now, seconds_ago),
            "event": {"category": "rtbf-request", "kind": "event"},
            "rtbf": {
                "id": f"rtbf-{i + 1:03d}",
                "patient_id": _patient_id(f"rtbf-{i}"),
                "channel": rng.choice(channels),
                "status": status,
                "age_days": age_days,
            },
            "customer": {"name": CUSTOMER_NAME, "industry": INDUSTRY_ID},
        })
    return docs


def generate_documents(seed: int = 20260504) -> Dict[str, List[Dict[str, Any]]]:
    rng = random.Random(seed)
    now = _now()
    phi_docs, phi_cache = _gen_phi_access(now, rng)
    audit_docs = _gen_audit_events(now, rng, phi_cache)
    rtbf_docs = _gen_rtbf(now, rng)
    # Stash the cache on a module-level for KPI computation later.
    global _LAST_PHI_CACHE
    _LAST_PHI_CACHE = phi_cache
    return {
        INDICES["phi_access"]: phi_docs,
        INDICES["audit_events"]: audit_docs,
        INDICES["rtbf"]: rtbf_docs,
    }


_LAST_PHI_CACHE: Dict[str, Any] = {}


# ============================================================ KPIs ===============

def _compute_kpis(docs: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    audit_docs = docs[INDICES["audit_events"]]
    rtbf_docs = docs[INDICES["rtbf"]]
    phi_docs = docs[INDICES["phi_access"]]

    by_status: Dict[str, int] = {}
    for d in audit_docs:
        s = d["compliance"]["status"]
        by_status[s] = by_status.get(s, 0) + 1
    total_evidence = len(audit_docs)
    compliant = by_status.get("compliant", 0)
    coverage_pct = round(compliant / total_evidence * 100, 1) if total_evidence else 0.0

    rtbf_open = sum(1 for r in rtbf_docs if r["rtbf"]["status"] != "fulfilled")
    btg_total = sum(1 for d in phi_docs if d["phi"].get("btg"))
    btg_within = sum(1 for d in phi_docs
                     if d["phi"].get("btg")
                     and (d["compliance"].get("btg_review_age_hours") or 0) <= 72)
    btg_breached = btg_total - btg_within

    anomaly_actors = len(_LAST_PHI_CACHE.get("anomalies", []))

    standards_with_gap = {d["compliance"]["standard"] for d in audit_docs
                          if d["compliance"]["status"] != "compliant"}

    # Audit readiness score: weighted blend of evidence coverage, RTBF closure,
    # BTG SLA compliance, anomaly remediation status.
    rtbf_closure = (len(rtbf_docs) - rtbf_open) / max(1, len(rtbf_docs))
    btg_compliance = btg_within / max(1, btg_total) if btg_total else 1.0
    anomaly_factor = max(0, 1 - (anomaly_actors * 0.05))
    score = (coverage_pct / 100) * 0.4 + rtbf_closure * 0.2 + btg_compliance * 0.3 + anomaly_factor * 0.1
    readiness_pct = round(score * 100, 1)

    return {
        "total_evidence": total_evidence,
        "compliant_evidence": compliant,
        "coverage_pct": coverage_pct,
        "btg_total": btg_total,
        "btg_within_sla": btg_within,
        "btg_breached": btg_breached,
        "rtbf_total": len(rtbf_docs),
        "rtbf_open": rtbf_open,
        "anomaly_actors": anomaly_actors,
        "standards_total": len(HIPAA_STANDARDS),
        "standards_with_gap": len(standards_with_gap),
        "readiness_pct": readiness_pct,
    }


# ============================================================ Vega specs =========

_VEGA_SCHEMA = "https://vega.github.io/schema/vega-lite/v5.json"


def _vega_control_coverage(audit_docs: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_std: Dict[str, Dict[str, int]] = {}
    for d in audit_docs:
        std = d["compliance"]["standard"]
        st = d["compliance"]["status"]
        by_std.setdefault(std, {"compliant": 0, "gap": 0,
                                 "partial": 0, "needs-review": 0})
        by_std[std][st] = by_std[std].get(st, 0) + 1
    values: List[Dict[str, Any]] = []
    for std, kinds in by_std.items():
        for kind, n in kinds.items():
            values.append({"standard": std, "status": kind, "count": n})
    return {
        "$schema": _VEGA_SCHEMA,
        "data": {"values": values},
        "mark": {"type": "bar", "tooltip": True},
        "encoding": {
            "x": {"field": "standard", "type": "nominal", "title": "HIPAA standard"},
            "y": {"field": "count", "type": "quantitative", "stack": "normalize",
                  "title": "Coverage (%)"},
            "color": {
                "field": "status", "type": "nominal",
                "scale": {"domain": ["compliant", "partial", "needs-review", "gap"],
                          "range": ["#16A085", "#F1C40F", "#3498DB", "#C0392B"]},
            },
        },
        "width": "container",
        "height": 240,
    }


def _vega_anomaly_timeline(phi_docs: List[Dict[str, Any]]) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    buckets: Dict[int, Dict[str, int]] = {}
    for d in phi_docs:
        ts = datetime.fromisoformat(d["@timestamp"].replace("Z", "+00:00"))
        days_ago = int((now - ts).total_seconds() // 86400)
        if days_ago > 30:
            continue
        b = buckets.setdefault(days_ago, {"normal": 0, "anomaly": 0})
        if d["phi"].get("anomaly"):
            b["anomaly"] += 1
        else:
            b["normal"] += 1
    values: List[Dict[str, Any]] = []
    for d in range(30, -1, -1):
        b = buckets.get(d, {"normal": 0, "anomaly": 0})
        values.append({"days_ago": -d, "kind": "normal", "count": b["normal"]})
        values.append({"days_ago": -d, "kind": "anomaly", "count": b["anomaly"]})
    return {
        "$schema": _VEGA_SCHEMA,
        "data": {"values": values},
        "mark": {"type": "bar", "tooltip": True},
        "encoding": {
            "x": {"field": "days_ago", "type": "quantitative", "title": "Days ago"},
            "y": {"field": "count", "type": "quantitative", "title": "PHI access events"},
            "color": {
                "field": "kind", "type": "nominal",
                "scale": {"domain": ["normal", "anomaly"],
                          "range": ["#3498DB", "#C0392B"]},
            },
        },
        "width": "container",
        "height": 220,
    }


def _vega_access_by_role(phi_docs: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts: Dict[str, int] = {}
    for d in phi_docs:
        r = d["user"]["role"]
        counts[r] = counts.get(r, 0) + 1
    items = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:10]
    values = [{"role": r, "count": c} for r, c in items]
    return {
        "$schema": _VEGA_SCHEMA,
        "data": {"values": values},
        "mark": {"type": "bar", "tooltip": True, "color": "#16A085"},
        "encoding": {
            "y": {"field": "role", "type": "nominal", "sort": "-x", "title": "User role"},
            "x": {"field": "count", "type": "quantitative", "title": "PHI accesses (90d)"},
        },
        "width": "container",
        "height": 220,
    }


def _vega_btg_sla(phi_docs: List[Dict[str, Any]]) -> Dict[str, Any]:
    within = sum(1 for d in phi_docs
                 if d["phi"].get("btg")
                 and (d["compliance"].get("btg_review_age_hours") or 0) <= 72)
    breached = sum(1 for d in phi_docs
                   if d["phi"].get("btg")
                   and (d["compliance"].get("btg_review_age_hours") or 0) > 72)
    values = [
        {"label": "Within 72h SLA", "count": within},
        {"label": "Past 72h SLA", "count": breached},
    ]
    return {
        "$schema": _VEGA_SCHEMA,
        "data": {"values": values},
        "mark": {"type": "arc", "tooltip": True, "innerRadius": 50},
        "encoding": {
            "theta": {"field": "count", "type": "quantitative"},
            "color": {
                "field": "label", "type": "nominal",
                "scale": {"range": ["#16A085", "#C0392B"]},
            },
        },
        "width": "container",
        "height": 220,
    }


def _vega_rtbf_status(rtbf_docs: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts: Dict[str, int] = {}
    for d in rtbf_docs:
        s = d["rtbf"]["status"]
        counts[s] = counts.get(s, 0) + 1
    values = [{"status": s, "count": c} for s, c in counts.items()]
    return {
        "$schema": _VEGA_SCHEMA,
        "data": {"values": values},
        "mark": {"type": "bar", "tooltip": True},
        "encoding": {
            "x": {"field": "status", "type": "nominal", "title": "RTBF status"},
            "y": {"field": "count", "type": "quantitative", "title": "Requests"},
            "color": {
                "field": "status", "type": "nominal",
                "scale": {"range": ["#16A085", "#F1C40F", "#3498DB"]},
                "legend": None,
            },
        },
        "width": "container",
        "height": 220,
    }


def _vega_facility_heatmap(phi_docs: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts: Dict[Tuple[str, str], int] = {}
    for d in phi_docs:
        fac = d.get("facility") or "Atlas-HQ"
        action = d["phi"].get("action", "unknown")
        counts[(fac, action)] = counts.get((fac, action), 0) + 1
    values: List[Dict[str, Any]] = []
    for (fac, action), n in counts.items():
        values.append({"facility": fac, "action": action, "count": n})
    return {
        "$schema": _VEGA_SCHEMA,
        "data": {"values": values},
        "mark": {"type": "rect", "tooltip": True},
        "encoding": {
            "x": {"field": "action", "type": "nominal", "title": "PHI action"},
            "y": {"field": "facility", "type": "nominal", "title": "Facility"},
            "color": {"field": "count", "type": "quantitative",
                      "scale": {"scheme": "blues"}, "title": "Events"},
        },
        "width": "container",
        "height": 240,
    }


# ============================================================ Markdown panels ====


def _switcher_md(view: str) -> str:
    fe_url = _dashboard_url(DASHBOARD_ID)
    cu_url = _dashboard_url(CUSTOMER_DASHBOARD_ID)
    fe_active = " (active)" if view == "fe" else ""
    cu_active = " (active)" if view == "customer" else ""
    return (
        f"## Atlas Health - HIPAA audit readiness\n\n"
        f"- [FE prep view{fe_active}]({fe_url})\n"
        f"- [Customer compliance view{cu_active}]({cu_url})\n"
    )


def _intro_fe_md() -> str:
    return (
        "## How to demo this scenario\n\n"
        "1. Open **Control coverage map**. 18 HIPAA Security Rule standards "
        "stacked, normalised. Green = compliant evidence, red = gap, yellow = "
        "partial. The CISO will linger on the few standards with red.\n"
        "2. Pivot to **Anomaly timeline**. Two spikes: 4 days ago (~280 events "
        "in 6h, billing-specialist role) and 8 days ago (~8 service-account "
        "batch pulls). The Elastic anomaly detection job flagged both inside "
        "the same hour.\n"
        "3. **Access by role** sets the baseline. Clinicians and nurses "
        "dominate, exactly as expected. Service-accounts should be near zero - "
        "the spike is the tell.\n"
        "4. **BTG SLA** doughnut: 14 of 18 within the 72-hour review SLA. The "
        "4 breaches are the customer's nudge to wire the auto-Case rule.\n"
        "5. **RTBF status**: 22 fulfilled, 3 in flight. State-level extension "
        "of HIPAA via CCPA-equivalent.\n\n"
        "**MEDDPICC angle.** Atlas Health's Compliance Officer pays a "
        "consultant USD 350k/year to assemble the audit pack manually. "
        "Elastic regenerates the same pack in 60 seconds, refreshes live "
        "during the OCR audit visit."
    )


def _intro_customer_md() -> str:
    return (
        "## OCR audit notice received - day 1 of 21\n\n"
        "Atlas Health's Compliance team has 21 days to assemble evidence of "
        "HIPAA Security Rule compliance across 11 hospitals and 64 clinics. "
        "This dashboard is the live evidence layer the auditor will see.\n\n"
        "**Bottom line.** Audit readiness score is **above 95%** with two "
        "live anomalies caught and remediated. Three RTBF requests are still "
        "in flight; all are within the state-level 30-day SLA. Four "
        "break-the-glass overrides need post-hoc review (the auto-Case rule "
        "is being wired this week)."
    )


def _kpi_fe_md(kpi: Dict[str, Any]) -> str:
    return (
        "## Headline metrics (last 90 days)\n\n"
        "| Metric | Value | Where |\n"
        "| --- | --- | --- |\n"
        f"| Audit readiness score | **{kpi['readiness_pct']}%** | weighted blend |\n"
        f"| Control evidence rows | **{kpi['total_evidence']:,}** | 18 standards |\n"
        f"| Coverage (compliant) | **{kpi['coverage_pct']}%** | "
        f"{kpi['standards_with_gap']} standards with at least one gap |\n"
        f"| BTG events | **{kpi['btg_total']}** | "
        f"{kpi['btg_within_sla']} within 72h, {kpi['btg_breached']} past SLA |\n"
        f"| RTBF requests | **{kpi['rtbf_total']}** | "
        f"{kpi['rtbf_total'] - kpi['rtbf_open']} fulfilled, {kpi['rtbf_open']} in flight |\n"
        f"| Anomalous actors | **{kpi['anomaly_actors']}** | "
        "1 disgruntled clinician + 1 compromised service account |\n\n"
        "_All evidence stored in `demo-hc-*` indices, queryable as ECS-aligned "
        "documents from any Kibana surface or by the OCR auditor's read-only token._"
    )


def _kpi_customer_md(kpi: Dict[str, Any]) -> str:
    return (
        "## Compliance summary for the OCR audit pack\n\n"
        "| Metric | Status |\n"
        "| --- | --- |\n"
        f"| Audit readiness score | **{kpi['readiness_pct']}%** |\n"
        f"| HIPAA standards with full coverage | "
        f"**{kpi['standards_total'] - kpi['standards_with_gap']} of {kpi['standards_total']}** |\n"
        f"| Control evidence collected | **{kpi['total_evidence']:,}** rows |\n"
        f"| RTBF closure | **{kpi['rtbf_total'] - kpi['rtbf_open']} of {kpi['rtbf_total']}** |\n"
        f"| BTG within 72h review SLA | **{kpi['btg_within_sla']} of {kpi['btg_total']}** |\n"
        f"| Active anomalies under remediation | **{kpi['anomaly_actors']}** |\n\n"
        "**Audit pack delivery.** This dashboard URL is the evidence pack. The "
        "OCR auditor receives a read-only Kibana token, scoped to "
        "`demo-hc-*`, valid for the 21-day audit window."
    )


def _close_fe_md() -> str:
    return (
        "## Talk track for the close\n\n"
        "1. Atlas Health's last audit response took **6 weeks** of consultant "
        "billable time. Today's evidence pack regenerates in **60 seconds**.\n"
        "2. Three Detection Rules ship with this scenario:\n"
        "   - *Anomalous PHI Bulk Read* - ML rate anomaly job on user/role.\n"
        "   - *BTG Review Past SLA* - threshold rule on `btg_review_age_hours > 72`.\n"
        "   - *Service Account Off-Hours* - rule on principal type + time.\n"
        "3. Pair with **Elastic Cases** for the audit response queue. Each "
        "anomaly auto-creates a Case with the patient list redacted via field "
        "level security.\n"
        "4. **Champion:** Compliance Officer. **EB:** General Counsel.\n"
        "5. **Competition:** Symplr (compliance-only, no live telemetry), "
        "Splunk Enterprise Security (no native PHI lifecycle controls)."
    )


def _close_customer_md() -> str:
    return (
        "## 21-day audit response plan\n\n"
        "**Day 1-7 (now):** Evidence pack frozen as a Kibana saved object. "
        "OCR auditor receives a read-only token. Two live anomalies have "
        "Cases assigned to General Counsel + CISO with named owners.\n\n"
        "**Day 8-14:** BTG auto-Case rule shipped to production. The 4 BTG "
        "events past SLA are reviewed and signed off by the on-call attending. "
        "RTBF backlog cleared.\n\n"
        "**Day 15-21:** Final evidence pack handed to OCR. Atlas Health's "
        "internal audit committee signs off. CISO presents to the board.\n\n"
        "**Why Elastic.** One ECS schema served three teams (Compliance, "
        "Security, IT). The OCR auditor and the CISO read the same events in "
        "real time. No spreadsheets, no PDF exports, no version skew."
    )


# ============================================================ Panel helpers ======


def _vega_panel(panel_id: str, x: int, y: int, w: int, h: int,
                title: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    spec_str = json.dumps(spec, ensure_ascii=False)
    return {
        "type": "visualization",
        "panelIndex": panel_id,
        "gridData": {"x": x, "y": y, "w": w, "h": h, "i": panel_id},
        "version": "9.3.4",
        "embeddableConfig": {
            "enhancements": {},
            "savedVis": {
                "title": title,
                "description": "",
                "type": "vega",
                "params": {"spec": spec_str},
                "uiState": {},
                "data": {
                    "aggs": [],
                    "searchSource": {"query": {"language": "kuery", "query": ""}, "filter": []},
                },
            },
        },
        "title": title,
    }


def _markdown_panel(panel_id: str, x: int, y: int, w: int, h: int,
                    markdown: str, title: str = "") -> Dict[str, Any]:
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


def _build_panels(view: str, docs: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    audit_docs = docs[INDICES["audit_events"]]
    phi_docs = docs[INDICES["phi_access"]]
    rtbf_docs = docs[INDICES["rtbf"]]
    kpi = _compute_kpis(docs)

    intro_md = _intro_fe_md() if view == "fe" else _intro_customer_md()
    kpi_md = _kpi_fe_md(kpi) if view == "fe" else _kpi_customer_md(kpi)
    close_md = _close_fe_md() if view == "fe" else _close_customer_md()

    panels: List[Dict[str, Any]] = []
    panels.append(_markdown_panel("p_switch", 0, 0, 48, 4, _switcher_md(view), "Switch view"))
    panels.append(_markdown_panel("p_intro", 0, 4, 48, 8, intro_md, "Overview"))
    panels.append(_vega_panel("p_cov", 0, 12, 48, 14,
                              "Control coverage map (HIPAA Security Rule)",
                              _vega_control_coverage(audit_docs)))
    panels.append(_vega_panel("p_anom", 0, 26, 24, 14,
                              "PHI access anomaly timeline",
                              _vega_anomaly_timeline(phi_docs)))
    panels.append(_vega_panel("p_role", 24, 26, 24, 14,
                              "PHI access by role", _vega_access_by_role(phi_docs)))
    panels.append(_vega_panel("p_btg", 0, 40, 24, 14,
                              "BTG 72h review SLA", _vega_btg_sla(phi_docs)))
    panels.append(_vega_panel("p_rtbf", 24, 40, 24, 14,
                              "RTBF status", _vega_rtbf_status(rtbf_docs)))
    panels.append(_vega_panel("p_heat", 0, 54, 48, 14,
                              "PHI action by facility", _vega_facility_heatmap(phi_docs)))
    panels.append(_markdown_panel("p_kpi", 0, 68, 48, 12, kpi_md, "KPIs"))
    panels.append(_markdown_panel("p_close", 0, 80, 48, 12, close_md, "Closing"))
    return panels


# ============================================================ Kibana helpers =====


def _kbn_url(path: str) -> str:
    return settings.kibana_url.rstrip("/") + path


def _kbn_headers() -> Dict[str, str]:
    return {
        "Authorization": f"ApiKey {settings.kibana_api_key}",
        "Content-Type": "application/json",
        "kbn-xsrf": "fe-copilot",
    }


def _data_view_id() -> str:
    return f"demo-{SCENARIO_ID}-dataview"


def _dashboard_url(dashboard_id: str = DASHBOARD_ID) -> str:
    return settings.kibana_url.rstrip("/") + f"/app/dashboards#/view/{dashboard_id}"


def _create_data_view() -> str:
    dv_id = _data_view_id()
    body = {
        "data_view": {
            "id": dv_id,
            "title": INDEX_PATTERN,
            "name": f"demo hc {SCENARIO_ID}",
            "timeFieldName": "@timestamp",
        },
        "override": True,
    }
    with httpx.Client(timeout=30.0) as client:
        try:
            client.delete(_kbn_url(f"/api/data_views/data_view/{dv_id}"),
                          headers=_kbn_headers())
        except Exception:
            pass
        resp = client.post(_kbn_url("/api/data_views/data_view"),
                           headers=_kbn_headers(), json=body)
        if resp.status_code >= 400:
            log.warning("hc_hipaa.dataview.fallback",
                        status=resp.status_code, body=resp.text[:300])
            body2 = [{
                "id": dv_id,
                "type": "index-pattern",
                "attributes": {
                    "title": INDEX_PATTERN,
                    "name": f"demo hc {SCENARIO_ID}",
                    "timeFieldName": "@timestamp",
                },
            }]
            resp2 = client.post(_kbn_url("/api/saved_objects/_bulk_create?overwrite=true"),
                                headers=_kbn_headers(), json=body2)
            if resp2.status_code >= 400:
                raise RuntimeError(
                    f"Kibana data view create failed: {resp2.status_code} "
                    f"{resp2.text[:300]}"
                )
    return dv_id


def _create_one_dashboard(*, data_view_id: str, dashboard_id: str, title: str,
                          description: str, panels: List[Dict[str, Any]]) -> str:
    panels_json = json.dumps(panels, ensure_ascii=False)
    options_json = json.dumps({
        "useMargins": True,
        "hidePanelTitles": False,
        "syncColors": True,
        "syncCursor": True,
        "syncTooltips": True,
    })
    search_source_json = json.dumps(
        {"query": {"language": "kuery", "query": ""}, "filter": []}
    )
    body = [{
        "id": dashboard_id,
        "type": "dashboard",
        "attributes": {
            "title": title,
            "description": description,
            "panelsJSON": panels_json,
            "optionsJSON": options_json,
            "timeRestore": True,
            "timeFrom": "now-90d",
            "timeTo": "now",
            "refreshInterval": {"pause": True, "value": 0},
            "version": 1,
            "kibanaSavedObjectMeta": {"searchSourceJSON": search_source_json},
        },
        "references": [
            {"id": data_view_id, "type": "index-pattern",
             "name": "kibanaSavedObjectMeta.searchSourceJSON.index"},
        ],
    }]
    with httpx.Client(timeout=30.0) as client:
        try:
            client.delete(_kbn_url(f"/api/saved_objects/dashboard/{dashboard_id}"),
                          headers=_kbn_headers())
        except Exception:
            pass
        resp = client.post(
            _kbn_url("/api/saved_objects/_bulk_create?overwrite=true"),
            headers=_kbn_headers(), json=body,
        )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Kibana dashboard create failed ({dashboard_id}): "
                f"{resp.status_code} {resp.text[:400]}"
            )
    return dashboard_id


def _create_dashboards(data_view_id: str,
                       docs: Dict[str, List[Dict[str, Any]]]) -> Dict[str, str]:
    fe_panels = _build_panels("fe", docs)
    cu_panels = _build_panels("customer", docs)
    fe_id = _create_one_dashboard(
        data_view_id=data_view_id,
        dashboard_id=DASHBOARD_ID,
        title=f"[FE] {SCENARIO_TITLE}",
        description=(
            "Field Engineer prep view. HIPAA Security Rule control coverage, PHI "
            "anomaly timeline, BTG SLA, RTBF lifecycle, MEDDPICC angle, demo "
            "cheat sheet."
        ),
        panels=fe_panels,
    )
    cu_id = _create_one_dashboard(
        data_view_id=data_view_id,
        dashboard_id=CUSTOMER_DASHBOARD_ID,
        title=f"[Customer] {SCENARIO_TITLE}",
        description=(
            "Atlas Health Compliance + executive view. Audit readiness score, "
            "evidence collected, gaps remaining, 21-day audit response plan."
        ),
        panels=cu_panels,
    )
    return {"fe": fe_id, "customer": cu_id}


# ============================================================ Seed entrypoint ====


def _to_bulk_actions(index: str, docs: List[Dict[str, Any]]):
    for doc in docs:
        yield {"_index": index, "_source": doc}


def seed_dashboards(kibana_client=None) -> Dict[str, Any]:
    docs = generate_documents()
    data_view_id = _create_data_view()
    ids = _create_dashboards(data_view_id, docs)
    return {
        "ok": True,
        "data_view_id": data_view_id,
        "fe_dashboard_id": ids["fe"],
        "fe_dashboard_url": _dashboard_url(ids["fe"]),
        "customer_dashboard_id": ids["customer"],
        "customer_dashboard_url": _dashboard_url(ids["customer"]),
    }


def seed(client=None) -> Dict[str, Any]:
    """End-to-end. Idempotent. Drops indices, recreates with mappings, bulk
    ingests, recreates the FE + Customer dashboards."""
    started = time.time()
    if not settings.elasticsearch_api_key and not settings.elasticsearch_password:
        raise RuntimeError("Elasticsearch credentials not configured")
    if not settings.kibana_api_key:
        raise RuntimeError("KIBANA_API_KEY not configured")

    docs_by_index = generate_documents()
    es = client or get_client()
    mappings = get_mappings()

    counts: Dict[str, int] = {}
    last_index = list(docs_by_index.keys())[-1]
    for index, docs in docs_by_index.items():
        try:
            if es.indices.exists(index=index):
                es.indices.delete(index=index)
            es.indices.create(index=index, body=mappings[index])
        except Exception as exc:
            log.warning("hc_hipaa.index.recreate.failed",
                        index=index, error=str(exc))
        actions = list(_to_bulk_actions(index, docs))
        refresh = "wait_for" if index == last_index else False
        try:
            success, errors = bulk(es, actions, chunk_size=500,
                                   refresh=refresh, raise_on_error=False)
        except Exception as exc:
            log.warning("hc_hipaa.bulk.failed", index=index, error=str(exc))
            success, errors = 0, [str(exc)]
        counts[index] = success
        log.info("hc_hipaa.indexed", index=index, count=success,
                 errors=len(errors) if isinstance(errors, list) else 0)

    for index in counts:
        try:
            es.indices.refresh(index=index)
        except Exception:
            pass

    data_view_id = _create_data_view()
    ids = _create_dashboards(data_view_id, docs_by_index)
    fe_id = ids.get("fe", DASHBOARD_ID)
    cu_id = ids.get("customer", CUSTOMER_DASHBOARD_ID)

    return {
        "ok": True,
        "scenario": SCENARIO_ID,
        "indices": counts,
        "doc_count": sum(counts.values()),
        "data_view_id": data_view_id,
        "dashboard_id": fe_id,
        "dashboard_url": _dashboard_url(fe_id),
        "fe_dashboard_id": fe_id,
        "fe_dashboard_url": _dashboard_url(fe_id),
        "customer_dashboard_id": cu_id,
        "customer_dashboard_url": _dashboard_url(cu_id),
        "dashboard_url_customer": _dashboard_url(cu_id),
        "elapsed_seconds": round(time.time() - started, 2),
        "kpi": _compute_kpis(docs_by_index),
    }
