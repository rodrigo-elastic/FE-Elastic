"""
filename: government_cdm.py
description: Demo Data Generator scenario - Federal CDM (Continuous Diagnostics & Mitigation).

Federal Demonstration Agency (FDA, fictional civilian agency, 12k employees, 4
data centres + 1 cloud region) reports its CDM AWARE score to CISA every month.
Today is the Monday after a federal holiday weekend; the asset inventory is
refreshing, three new CVEs landed Friday with one tagged Exploit-in-the-Wild,
and 11 production hosts have drifted from the FedRAMP baseline overnight.

The dashboard pair walks two audiences through the same dataset:

  - FE view (`demo-gov-cdm-dashboard`): operator surface. AWARE score breakdown
    (Manage Trust, Manage Behaviours, Manage Events), top CVEs by exposure
    weight, drift events bucketed by control family, 30-day trend.

  - Customer view (`demo-gov-cdm-customer-dashboard`): the CISO + agency-head
    surface. CDM scorecard, percentage of assets compliant, mean time to
    remediate, comparison to the federal civilian average.

Three indices, ~2650 docs total, plus FE and Customer dashboards (8 panels each)
with inline-data Vega-Lite.

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

SCENARIO_ID: str = "gov-cdm-compliance"
SCENARIO_TITLE: str = "Government Federal - CDM Continuous Diagnostics"
SCENARIO_DESCRIPTION: str = (
    "Federal Demonstration Agency (FDA, fictional federal civilian agency) reports "
    "its CDM AWARE score to CISA monthly. ~2000 host assets across 4 data centres, "
    "400 CVE findings tagged by criticality and Exploit-in-the-Wild status, 250 "
    "configuration drift events against the FedRAMP baseline. Dashboards: FE view "
    "(AWARE-score breakdown, top CVEs by exposure, drift by control family) plus "
    "Customer view (CDM scorecard, percent compliant, mean time to remediate)."
)

INDICES: Dict[str, str] = {
    "assets": "demo-gov-asset-inventory",
    "cves": "demo-gov-cve-findings",
    "drift": "demo-gov-config-drift",
}

DASHBOARD_ID: str = "demo-gov-cdm-dashboard"
CUSTOMER_DASHBOARD_ID: str = "demo-gov-cdm-customer-dashboard"
DASHBOARDS: List[str] = [DASHBOARD_ID, CUSTOMER_DASHBOARD_ID]
INDEX_PATTERN: str = "demo-gov-*"

INDUSTRY_ID: str = "gov-federal"
CUSTOMER_NAME: str = "Federal Demonstration Agency"

# Locations: 4 federal data centres + 1 FedRAMP High cloud tenant.
LOCATIONS: List[Tuple[str, str]] = [
    ("DC-East-VA", "data-center"),
    ("DC-Central-MO", "data-center"),
    ("DC-West-CO", "data-center"),
    ("DC-South-TX", "data-center"),
    ("Cloud-FedRAMP-High-AWS", "cloud-region"),
]

ASSET_KINDS: List[Tuple[str, float]] = [
    ("linux-server", 0.42),
    ("windows-server", 0.28),
    ("network-appliance", 0.10),
    ("database-host", 0.08),
    ("vmware-esxi", 0.07),
    ("kubernetes-node", 0.05),
]

CONTROL_FAMILIES: List[Tuple[str, str]] = [
    ("AC", "Access Control"),
    ("AU", "Audit and Accountability"),
    ("CM", "Configuration Management"),
    ("CP", "Contingency Planning"),
    ("IA", "Identification and Authentication"),
    ("IR", "Incident Response"),
    ("RA", "Risk Assessment"),
    ("SC", "System and Communications Protection"),
    ("SI", "System and Information Integrity"),
]

# CDM AWARE pillars.
AWARE_PILLARS = [
    ("manage-trust", "Manage Trust (HWAM/SWAM)"),
    ("manage-behaviours", "Manage Behaviours (CSM)"),
    ("manage-events", "Manage Events (BOUND/EVENT)"),
]


# ============================================================ Helpers =============

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ts(now: datetime, seconds_ago: float) -> str:
    return (now - timedelta(seconds=seconds_ago)).isoformat()


def _weighted_pick(rng: random.Random, items: List[Tuple[Any, float]]) -> Any:
    total = sum(w for _, w in items)
    pick = rng.uniform(0, total)
    cum = 0.0
    for v, w in items:
        cum += w
        if pick <= cum:
            return v
    return items[-1][0]


def _asset_id(seed: str) -> str:
    return "ast-" + uuid.uuid5(uuid.NAMESPACE_OID, seed).hex[:10]


# ============================================================ Mappings ============

def get_mappings() -> Dict[str, Dict[str, Any]]:
    base = {
        "@timestamp": {"type": "date"},
        "asset": {
            "properties": {
                "id": {"type": "keyword"},
                "hostname": {"type": "keyword"},
                "kind": {"type": "keyword"},
                "location": {"type": "keyword"},
                "site_kind": {"type": "keyword"},
                "owner": {"type": "keyword"},
                "criticality": {"type": "keyword"},
                "hardening_status": {"type": "keyword"},
                "patched_within_30d": {"type": "boolean"},
            }
        },
        "cve": {
            "properties": {
                "id": {"type": "keyword"},
                "cvss_score": {"type": "float"},
                "criticality": {"type": "keyword"},
                "exploit_in_the_wild": {"type": "boolean"},
                "kev_listed": {"type": "boolean"},
                "remediation_status": {"type": "keyword"},
                "exposure_weight": {"type": "float"},
                "age_days": {"type": "integer"},
            }
        },
        "drift": {
            "properties": {
                "control_family": {"type": "keyword"},
                "control_id": {"type": "keyword"},
                "severity": {"type": "keyword"},
                "fixed": {"type": "boolean"},
                "detected_age_minutes": {"type": "float"},
            }
        },
        "compliance": {
            "properties": {
                "aware_pillar": {"type": "keyword"},
                "fedramp_baseline": {"type": "keyword"},
            }
        },
    }
    return {
        INDICES["assets"]: {"mappings": {"dynamic": "true", "properties": base}},
        INDICES["cves"]: {"mappings": {"dynamic": "true", "properties": base}},
        INDICES["drift"]: {"mappings": {"dynamic": "true", "properties": base}},
    }


# ============================================================ Document gen ========

def _gen_assets(now: datetime, rng: random.Random) -> List[Dict[str, Any]]:
    docs: List[Dict[str, Any]] = []
    for i in range(2000):
        seconds_ago = rng.uniform(60, 24 * 3600)
        kind = _weighted_pick(rng, ASSET_KINDS)
        loc, site_kind = rng.choice(LOCATIONS)
        criticality = rng.choices(
            ["high", "moderate", "low"],
            weights=[0.22, 0.55, 0.23],
        )[0]
        # 91% hardened, 6% partial, 3% open.
        hardening = rng.choices(
            ["hardened", "partial", "open"],
            weights=[0.91, 0.06, 0.03],
        )[0]
        patched = rng.random() < 0.93
        owner = rng.choice([
            "iam-ops", "platform-ops", "data-ops", "soc",
            "network-eng", "endpoint-mgmt", "cloud-platform",
        ])
        hostname = f"fda-{kind.split('-')[0]}-{i:04d}"
        docs.append({
            "@timestamp": _ts(now, seconds_ago),
            "event": {"category": "asset-inventory", "kind": "metric"},
            "asset": {
                "id": _asset_id(hostname),
                "hostname": hostname,
                "kind": kind,
                "location": loc,
                "site_kind": site_kind,
                "owner": owner,
                "criticality": criticality,
                "hardening_status": hardening,
                "patched_within_30d": patched,
            },
            "compliance": {
                "aware_pillar": "manage-trust",
                "fedramp_baseline": rng.choice(["High", "Moderate"]),
            },
            "customer": {"name": CUSTOMER_NAME, "industry": INDUSTRY_ID},
        })
    return docs


def _gen_cves(now: datetime, rng: random.Random) -> List[Dict[str, Any]]:
    docs: List[Dict[str, Any]] = []
    cve_ids = [f"CVE-2026-{rng.randint(10000, 49999)}" for _ in range(400)]
    for i, cve_id in enumerate(cve_ids):
        age = rng.randint(1, 120)
        seconds_ago = rng.uniform(60, age * 86400)
        cvss = round(rng.triangular(2.0, 9.8, 7.2), 1)
        if cvss >= 9.0:
            crit = "critical"
        elif cvss >= 7.0:
            crit = "high"
        elif cvss >= 4.0:
            crit = "medium"
        else:
            crit = "low"
        eitw = rng.random() < 0.06  # 6% Exploit-in-the-Wild
        kev = eitw or rng.random() < 0.04
        remediation = rng.choices(
            ["remediated", "in-progress", "accepted-risk", "open"],
            weights=[0.65, 0.18, 0.05, 0.12],
        )[0]
        exposure = round((cvss / 10) * (1.5 if eitw else 1.0)
                         * (1.2 if kev else 1.0), 3)
        affected = rng.randint(1, 25)
        docs.append({
            "@timestamp": _ts(now, seconds_ago),
            "event": {"category": "vulnerability", "kind": "alert"},
            "cve": {
                "id": cve_id,
                "cvss_score": cvss,
                "criticality": crit,
                "exploit_in_the_wild": eitw,
                "kev_listed": kev,
                "remediation_status": remediation,
                "exposure_weight": exposure,
                "age_days": age,
                "affected_assets": affected,
            },
            "compliance": {"aware_pillar": "manage-behaviours"},
            "customer": {"name": CUSTOMER_NAME, "industry": INDUSTRY_ID},
        })
    return docs


def _gen_drift(now: datetime, rng: random.Random) -> List[Dict[str, Any]]:
    docs: List[Dict[str, Any]] = []
    for i in range(250):
        seconds_ago = rng.uniform(60, 30 * 86400)
        family, family_name = rng.choice(CONTROL_FAMILIES)
        control_id = f"{family}-{rng.randint(1, 24)}"
        severity = rng.choices(
            ["critical", "high", "medium", "low"],
            weights=[0.08, 0.30, 0.42, 0.20],
        )[0]
        fixed = rng.random() < 0.78
        det_age = round(rng.uniform(5, 1440), 1)
        loc, site_kind = rng.choice(LOCATIONS)
        kind = _weighted_pick(rng, ASSET_KINDS)
        host = f"fda-{kind.split('-')[0]}-{rng.randint(1, 1999):04d}"
        docs.append({
            "@timestamp": _ts(now, seconds_ago),
            "event": {"category": "config-drift", "kind": "alert"},
            "drift": {
                "control_family": family,
                "control_family_name": family_name,
                "control_id": control_id,
                "severity": severity,
                "fixed": fixed,
                "detected_age_minutes": det_age,
                "drift_type": rng.choice([
                    "kernel-param-mismatch",
                    "service-enabled-not-baseline",
                    "firewall-rule-added",
                    "user-account-out-of-baseline",
                    "tls-version-downgraded",
                    "logging-disabled",
                    "encryption-key-rotation-overdue",
                ]),
            },
            "asset": {
                "hostname": host,
                "kind": kind,
                "location": loc,
            },
            "compliance": {"aware_pillar": "manage-events"},
            "customer": {"name": CUSTOMER_NAME, "industry": INDUSTRY_ID},
        })
    return docs


def generate_documents(seed: int = 20260504) -> Dict[str, List[Dict[str, Any]]]:
    rng = random.Random(seed)
    now = _now()
    return {
        INDICES["assets"]: _gen_assets(now, rng),
        INDICES["cves"]: _gen_cves(now, rng),
        INDICES["drift"]: _gen_drift(now, rng),
    }


# ============================================================ KPIs ===============

def _compute_kpis(docs: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    assets = docs[INDICES["assets"]]
    cves = docs[INDICES["cves"]]
    drift = docs[INDICES["drift"]]

    total_assets = len(assets)
    hardened = sum(1 for a in assets if a["asset"]["hardening_status"] == "hardened")
    patched = sum(1 for a in assets if a["asset"]["patched_within_30d"])
    pct_hardened = round(hardened / total_assets * 100, 1) if total_assets else 0.0
    pct_patched = round(patched / total_assets * 100, 1) if total_assets else 0.0

    open_cves = sum(1 for c in cves if c["cve"]["remediation_status"] != "remediated")
    eitw = sum(1 for c in cves if c["cve"]["exploit_in_the_wild"])
    kev_open = sum(1 for c in cves
                   if c["cve"]["kev_listed"]
                   and c["cve"]["remediation_status"] != "remediated")

    drift_open = sum(1 for d in drift if not d["drift"]["fixed"])
    mttr_minutes = round(
        sum(d["drift"]["detected_age_minutes"] for d in drift if d["drift"]["fixed"])
        / max(1, sum(1 for d in drift if d["drift"]["fixed"])),
        1,
    )

    # AWARE score: weighted blend of pillars (Manage Trust 0.45, Manage
    # Behaviours 0.30, Manage Events 0.25). Federal civilian average per CISA
    # 2025 transparency report: 78. Our target is to beat that.
    pillar_trust = pct_hardened
    # Behaviours pillar penalises EITW exposure most heavily, KEV-listed less,
    # and the long tail of routine open CVEs only mildly. Calibrated so a clean
    # week (zero EITW, low backlog) sits in the high 80s and matches FedRAMP
    # baseline expectations.
    pillar_behave = max(0, 100 - eitw * 0.6 - kev_open * 0.4 - max(0, open_cves - 80) * 0.05)
    pillar_events = round((1 - drift_open / max(1, len(drift))) * 100, 1)

    aware = round(
        pillar_trust * 0.45 + pillar_behave * 0.30 + pillar_events * 0.25, 1
    )

    return {
        "total_assets": total_assets,
        "hardened_assets": hardened,
        "pct_hardened": pct_hardened,
        "pct_patched": pct_patched,
        "open_cves": open_cves,
        "eitw_count": eitw,
        "kev_open": kev_open,
        "drift_total": len(drift),
        "drift_open": drift_open,
        "mttr_minutes": mttr_minutes,
        "aware_score": aware,
        "pillar_trust": round(pillar_trust, 1),
        "pillar_behave": round(pillar_behave, 1),
        "pillar_events": pillar_events,
        "federal_average_aware": 78.0,
    }


# ============================================================ Vega specs =========

_VEGA_SCHEMA = "https://vega.github.io/schema/vega-lite/v5.json"


def _vega_aware_breakdown(kpi: Dict[str, Any]) -> Dict[str, Any]:
    values = [
        {"pillar": "Manage Trust", "score": kpi["pillar_trust"]},
        {"pillar": "Manage Behaviours", "score": kpi["pillar_behave"]},
        {"pillar": "Manage Events", "score": kpi["pillar_events"]},
        {"pillar": "Federal civilian avg", "score": kpi["federal_average_aware"]},
    ]
    return {
        "$schema": _VEGA_SCHEMA,
        "data": {"values": values},
        "mark": {"type": "bar", "tooltip": True},
        "encoding": {
            "y": {"field": "pillar", "type": "nominal", "sort": "-x", "title": "AWARE pillar"},
            "x": {"field": "score", "type": "quantitative",
                  "scale": {"domain": [0, 100]}, "title": "Score"},
            "color": {
                "field": "pillar", "type": "nominal",
                "scale": {"range": ["#0077CC", "#16A085", "#8E44AD", "#7F8C8D"]},
                "legend": None,
            },
        },
        "width": "container",
        "height": 220,
    }


def _vega_top_cves(cves: List[Dict[str, Any]]) -> Dict[str, Any]:
    open_cves = [c for c in cves if c["cve"]["remediation_status"] != "remediated"]
    open_cves.sort(key=lambda c: c["cve"]["exposure_weight"], reverse=True)
    top = open_cves[:10]
    values: List[Dict[str, Any]] = []
    for c in top:
        values.append({
            "cve": c["cve"]["id"],
            "exposure": c["cve"]["exposure_weight"],
            "eitw": "Exploit-in-the-Wild" if c["cve"]["exploit_in_the_wild"] else "No",
            "cvss": c["cve"]["cvss_score"],
            "affected": c["cve"]["affected_assets"],
        })
    return {
        "$schema": _VEGA_SCHEMA,
        "data": {"values": values},
        "mark": {"type": "bar", "tooltip": True},
        "encoding": {
            "y": {"field": "cve", "type": "nominal", "sort": "-x", "title": "CVE"},
            "x": {"field": "exposure", "type": "quantitative", "title": "Exposure weight"},
            "color": {
                "field": "eitw", "type": "nominal",
                "scale": {"domain": ["Exploit-in-the-Wild", "No"],
                          "range": ["#C0392B", "#3498DB"]},
            },
        },
        "width": "container",
        "height": 240,
    }


def _vega_drift_by_family(drift: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts: Dict[str, Dict[str, int]] = {}
    for d in drift:
        fam = d["drift"]["control_family"]
        sev = d["drift"]["severity"]
        counts.setdefault(fam, {"critical": 0, "high": 0, "medium": 0, "low": 0})
        counts[fam][sev] = counts[fam].get(sev, 0) + 1
    values: List[Dict[str, Any]] = []
    for fam, kinds in counts.items():
        for sev, n in kinds.items():
            values.append({"family": fam, "severity": sev, "count": n})
    return {
        "$schema": _VEGA_SCHEMA,
        "data": {"values": values},
        "mark": {"type": "bar", "tooltip": True},
        "encoding": {
            "x": {"field": "family", "type": "nominal", "title": "Control family"},
            "y": {"field": "count", "type": "quantitative", "title": "Drift events"},
            "color": {
                "field": "severity", "type": "nominal",
                "scale": {"domain": ["critical", "high", "medium", "low"],
                          "range": ["#C0392B", "#E67E22", "#F1C40F", "#3498DB"]},
            },
        },
        "width": "container",
        "height": 220,
    }


def _vega_assets_hardening(assets: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts: Dict[str, Dict[str, int]] = {}
    for a in assets:
        loc = a["asset"]["location"]
        st = a["asset"]["hardening_status"]
        counts.setdefault(loc, {"hardened": 0, "partial": 0, "open": 0})
        counts[loc][st] = counts[loc].get(st, 0) + 1
    values: List[Dict[str, Any]] = []
    for loc, kinds in counts.items():
        for st, n in kinds.items():
            values.append({"location": loc, "status": st, "count": n})
    return {
        "$schema": _VEGA_SCHEMA,
        "data": {"values": values},
        "mark": {"type": "bar", "tooltip": True},
        "encoding": {
            "y": {"field": "location", "type": "nominal", "title": "Location"},
            "x": {"field": "count", "type": "quantitative", "stack": "normalize",
                  "title": "Hardening (%)"},
            "color": {
                "field": "status", "type": "nominal",
                "scale": {"domain": ["hardened", "partial", "open"],
                          "range": ["#16A085", "#F1C40F", "#C0392B"]},
            },
        },
        "width": "container",
        "height": 220,
    }


def _vega_cve_age(cves: List[Dict[str, Any]]) -> Dict[str, Any]:
    open_cves = [c for c in cves if c["cve"]["remediation_status"] != "remediated"]
    buckets = {"0-7d": 0, "8-30d": 0, "31-60d": 0, "60d+": 0}
    for c in open_cves:
        a = c["cve"]["age_days"]
        if a <= 7:
            buckets["0-7d"] += 1
        elif a <= 30:
            buckets["8-30d"] += 1
        elif a <= 60:
            buckets["31-60d"] += 1
        else:
            buckets["60d+"] += 1
    values = [{"bucket": k, "count": v} for k, v in buckets.items()]
    return {
        "$schema": _VEGA_SCHEMA,
        "data": {"values": values},
        "mark": {"type": "bar", "tooltip": True},
        "encoding": {
            "x": {"field": "bucket", "type": "nominal",
                  "sort": ["0-7d", "8-30d", "31-60d", "60d+"], "title": "Age"},
            "y": {"field": "count", "type": "quantitative", "title": "Open CVEs"},
            "color": {
                "field": "bucket", "type": "nominal",
                "scale": {"range": ["#16A085", "#3498DB", "#E67E22", "#C0392B"]},
                "legend": None,
            },
        },
        "width": "container",
        "height": 220,
    }


def _vega_remediation_trend(drift: List[Dict[str, Any]]) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    buckets: Dict[int, Dict[str, int]] = {}
    for d in drift:
        ts = datetime.fromisoformat(d["@timestamp"].replace("Z", "+00:00"))
        days_ago = int((now - ts).total_seconds() // 86400)
        if days_ago > 30:
            continue
        b = buckets.setdefault(days_ago, {"new": 0, "fixed": 0})
        if d["drift"]["fixed"]:
            b["fixed"] += 1
        else:
            b["new"] += 1
    values: List[Dict[str, Any]] = []
    for d in range(30, -1, -1):
        b = buckets.get(d, {"new": 0, "fixed": 0})
        values.append({"days_ago": -d, "kind": "new", "count": b["new"]})
        values.append({"days_ago": -d, "kind": "fixed", "count": b["fixed"]})
    return {
        "$schema": _VEGA_SCHEMA,
        "data": {"values": values},
        "mark": {"type": "line", "tooltip": True, "interpolate": "monotone"},
        "encoding": {
            "x": {"field": "days_ago", "type": "quantitative", "title": "Days ago"},
            "y": {"field": "count", "type": "quantitative", "title": "Drift events"},
            "color": {
                "field": "kind", "type": "nominal",
                "scale": {"domain": ["new", "fixed"],
                          "range": ["#C0392B", "#16A085"]},
            },
        },
        "width": "container",
        "height": 220,
    }


# ============================================================ Markdown panels ====


def _switcher_md(view: str) -> str:
    fe_url = _dashboard_url(DASHBOARD_ID)
    cu_url = _dashboard_url(CUSTOMER_DASHBOARD_ID)
    fe_active = " (active)" if view == "fe" else ""
    cu_active = " (active)" if view == "customer" else ""
    return (
        f"## FDA - CDM continuous diagnostics\n\n"
        f"- [FE prep view{fe_active}]({fe_url})\n"
        f"- [Customer scorecard{cu_active}]({cu_url})\n"
    )


def _intro_fe_md() -> str:
    return (
        "## How to demo this scenario\n\n"
        "1. Open **AWARE-score breakdown**. The three CDM pillars (Manage "
        "Trust, Behaviours, Events) plotted alongside the federal civilian "
        "average. The customer's CIO knows their AWARE figure to the decimal "
        "point - this is how Elastic shows up in the conversation.\n"
        "2. Pivot to **Top CVEs by exposure**. Red bars = Exploit-in-the-Wild. "
        "These are the ones CISA will ask about by name.\n"
        "3. **Drift by control family** stacks severity per NIST 800-53 family. "
        "Configuration Management (CM) and System and Information Integrity (SI) "
        "always dominate after a long weekend.\n"
        "4. **Asset hardening by location** shows the cloud tenant hardening "
        "rate is now ahead of three of the four data centres - a quotable "
        "win for the FedRAMP migration sponsor.\n"
        "5. **Open-CVE age distribution** is the audit-ready trend.\n\n"
        "**MEDDPICC angle.** FDA's current CDM stack is BigFix + Splunk + "
        "Tenable, three vendors, three indices, no live AWARE score. Elastic "
        "unifies the three feeds, computes AWARE in ESQL on every refresh, "
        "and ships the score to CISA via a saved-search export."
    )


def _intro_customer_md() -> str:
    return (
        "## CDM scorecard - week ending today\n\n"
        "Federal Demonstration Agency reports its AWARE score to CISA "
        "monthly. This dashboard is the live production view: the next "
        "submission to CISA reads the same numbers shown below.\n\n"
        "**Bottom line.** AWARE score is **above the federal civilian "
        "average**, asset hardening is at 91%, and the open Exploit-in-the-"
        "Wild CVE count is in single digits. Drift events from the holiday "
        "weekend are 78% remediated; the remaining 22% have named owners "
        "with sub-24-hour SLAs."
    )


def _kpi_fe_md(kpi: Dict[str, Any]) -> str:
    return (
        "## Headline metrics (live)\n\n"
        "| Metric | Value | Notes |\n"
        "| --- | --- | --- |\n"
        f"| AWARE score | **{kpi['aware_score']}** | "
        f"federal avg {kpi['federal_average_aware']} |\n"
        f"| Asset count | **{kpi['total_assets']:,}** | hardened "
        f"{kpi['pct_hardened']}%, patched {kpi['pct_patched']}% |\n"
        f"| Open CVEs | **{kpi['open_cves']}** | "
        f"{kpi['eitw_count']} Exploit-in-the-Wild, {kpi['kev_open']} KEV-listed open |\n"
        f"| Drift events | **{kpi['drift_total']}** | "
        f"{kpi['drift_total'] - kpi['drift_open']} fixed, "
        f"{kpi['drift_open']} open |\n"
        f"| Mean time to remediate (drift) | **{kpi['mttr_minutes']}m** | "
        "wall-clock |\n\n"
        "_All figures recomputed at index time via Elastic Transforms; the "
        "CISA submission read-only token reuses the same Kibana saved search._"
    )


def _kpi_customer_md(kpi: Dict[str, Any]) -> str:
    return (
        "## CDM scorecard\n\n"
        "| Metric | Status |\n"
        "| --- | --- |\n"
        f"| AWARE score | **{kpi['aware_score']}** "
        f"({'above' if kpi['aware_score'] >= kpi['federal_average_aware'] else 'below'} federal civilian average of {kpi['federal_average_aware']}) |\n"
        f"| Assets compliant (hardened) | **{kpi['pct_hardened']}%** |\n"
        f"| Open Exploit-in-the-Wild CVEs | **{kpi['eitw_count']}** |\n"
        f"| Mean time to remediate drift | **{kpi['mttr_minutes']} minutes** |\n"
        f"| Drift events open | **{kpi['drift_open']} of {kpi['drift_total']}** |\n\n"
        "**For the CISA submission.** This dashboard URL is the FDA's "
        "monthly CDM evidence pack. CISA's auditor receives a read-only "
        "Kibana token, scoped to `demo-gov-*`, valid for the duration of the "
        "review window."
    )


def _close_fe_md() -> str:
    return (
        "## Talk track for the close\n\n"
        "1. FDA's last CDM submission cycle took **9 days** of analyst time "
        "to assemble. Today's pack regenerates in **45 seconds**.\n"
        "2. Three Detection Rules ship with this scenario:\n"
        "   - *Drift Past 24h SLA* - threshold rule on `detected_age_minutes > 1440`.\n"
        "   - *EITW CVE Open* - rule on `exploit_in_the_wild=true AND remediation_status!=remediated`.\n"
        "   - *Hardening Regression* - ML rate change job on `hardening_status` per location.\n"
        "3. Pair with **Elastic Cases** for the CDM remediation queue, "
        "**Maps** for asset geo-distribution, and **ESQL Transforms** for "
        "the live AWARE rollup.\n"
        "4. **Champion:** Agency CISO. **EB:** CIO + Authorising Official.\n"
        "5. **Competition:** Splunk for FedRAMP (no native CDM rollup), "
        "Tenable.sc (vuln-only)."
    )


def _close_customer_md() -> str:
    return (
        "## Next 30 days - operational plan\n\n"
        "**Done.**\n"
        "- AWARE score above federal civilian average.\n"
        "- Cloud-FedRAMP-High tenant hardening ahead of three data centres.\n"
        "- Drift auto-Case rule live; mean time to remediate inside the SLA.\n\n"
        "**In flight.**\n"
        "1. Promote the *Hardening Regression* ML job to production - it "
        "currently catches 92% of regressions in canary.\n"
        "2. Wire the EITW Detection Rule to the CIO's executive paging "
        "channel for sub-15-minute response on net-new EITW CVEs.\n"
        "3. Quarterly tabletop exercise replaying the holiday-weekend drift "
        "spike. Sign-off by the CISO.\n\n"
        "**Why Elastic.** One ECS schema served three teams (CDM operators, "
        "vulnerability management, FedRAMP compliance). The CISA auditor and "
        "the FDA SOC read the same events in real time. No spreadsheets, no "
        "PDF exports, no lag between assessment and submission."
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
    assets = docs[INDICES["assets"]]
    cves = docs[INDICES["cves"]]
    drift = docs[INDICES["drift"]]
    kpi = _compute_kpis(docs)

    intro_md = _intro_fe_md() if view == "fe" else _intro_customer_md()
    kpi_md = _kpi_fe_md(kpi) if view == "fe" else _kpi_customer_md(kpi)
    close_md = _close_fe_md() if view == "fe" else _close_customer_md()

    panels: List[Dict[str, Any]] = []
    panels.append(_markdown_panel("p_switch", 0, 0, 48, 4, _switcher_md(view), "Switch view"))
    panels.append(_markdown_panel("p_intro", 0, 4, 48, 8, intro_md, "Overview"))
    panels.append(_vega_panel("p_aware", 0, 12, 24, 14,
                              "AWARE-score breakdown", _vega_aware_breakdown(kpi)))
    panels.append(_vega_panel("p_top_cve", 24, 12, 24, 14,
                              "Top open CVEs by exposure", _vega_top_cves(cves)))
    panels.append(_vega_panel("p_drift", 0, 26, 24, 14,
                              "Drift events by control family",
                              _vega_drift_by_family(drift)))
    panels.append(_vega_panel("p_assets", 24, 26, 24, 14,
                              "Asset hardening by location",
                              _vega_assets_hardening(assets)))
    panels.append(_vega_panel("p_cve_age", 0, 40, 24, 14,
                              "Open-CVE age distribution", _vega_cve_age(cves)))
    panels.append(_vega_panel("p_trend", 24, 40, 24, 14,
                              "Drift remediation trend (30d)",
                              _vega_remediation_trend(drift)))
    panels.append(_markdown_panel("p_kpi", 0, 54, 48, 12, kpi_md, "KPIs"))
    panels.append(_markdown_panel("p_close", 0, 66, 48, 12, close_md, "Closing"))
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
            "name": f"demo gov {SCENARIO_ID}",
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
            log.warning("gov_cdm.dataview.fallback",
                        status=resp.status_code, body=resp.text[:300])
            body2 = [{
                "id": dv_id,
                "type": "index-pattern",
                "attributes": {
                    "title": INDEX_PATTERN,
                    "name": f"demo gov {SCENARIO_ID}",
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
            "timeFrom": "now-30d",
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


def _fe_industry_context() -> Dict[str, Any]:
    return {
        "id": "gov-cdm",
        "name": "Government CDM - federal continuous monitoring",
        "summary": ("CISA CDM Dashboard requirement: asset, account, and "
                    "config inventory with continuous drift detection."),
        "personas": [
            {"role": "Agency CISO",
             "pain": "BOD 23-01 asset inventory across 12 sub-agencies is incomplete."},
            {"role": "Mission Owner",
             "pain": "Continuous ATO is still slide-deck driven, not telemetry-driven."},
            {"role": "Compliance Officer",
             "pain": "FISMA quarterly reports take 4 person-weeks."},
            {"role": "CISA Liaison",
             "pain": "Dashboard data is stale by the time it reaches CISA."},
        ],
        "regulations": ["FedRAMP High", "FISMA", "M-21-31", "NIST 800-53",
                        "BOD 23-01", "CDM"],
        "top_competitors": ["battlecard-splunk", "battlecard-microsoft-sentinel",
                            "battlecard-chronicle", "battlecard-qradar"],
    }


def _fe_superset_panels(docs: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    from app.services.scenarios.industry_factory import build_fe_superset_panels

    cu_panels = _build_panels("customer", docs)
    legacy_fe = _build_panels("fe", docs)
    fe_only_extras = [p for p in legacy_fe
                      if p.get("embeddableConfig", {}).get("savedVis", {})
                          .get("type") == "markdown"
                      and p.get("panelIndex") not in ("p_switch",)]
    return build_fe_superset_panels(
        _fe_industry_context(),
        customer="Federal Continuity Agency",
        customer_panels=cu_panels,
        fe_only_extras=fe_only_extras,
        id_prefix="gov-fe",
    )


def _create_dashboards(data_view_id: str,
                       docs: Dict[str, List[Dict[str, Any]]]) -> Dict[str, str]:
    fe_panels = _fe_superset_panels(docs)
    cu_panels = _build_panels("customer", docs)
    fe_id = _create_one_dashboard(
        data_view_id=data_view_id,
        dashboard_id=DASHBOARD_ID,
        title=f"[FE] {SCENARIO_TITLE}",
        description=(
            "Field Engineer prep view. CDM AWARE-score breakdown, top open CVEs "
            "by exposure, drift events by control family, asset hardening, MEDDPICC "
            "angle, demo cheat sheet."
        ),
        panels=fe_panels,
    )
    cu_id = _create_one_dashboard(
        data_view_id=data_view_id,
        dashboard_id=CUSTOMER_DASHBOARD_ID,
        title=f"[Customer] {SCENARIO_TITLE}",
        description=(
            "Federal Demonstration Agency CISO + CIO scorecard. AWARE score, "
            "percent compliant, Exploit-in-the-Wild posture, mean time to remediate."
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
            log.warning("gov_cdm.index.recreate.failed",
                        index=index, error=str(exc))
        actions = list(_to_bulk_actions(index, docs))
        refresh = "wait_for" if index == last_index else False
        try:
            success, errors = bulk(es, actions, chunk_size=500,
                                   refresh=refresh, raise_on_error=False)
        except Exception as exc:
            log.warning("gov_cdm.bulk.failed", index=index, error=str(exc))
            success, errors = 0, [str(exc)]
        counts[index] = success
        log.info("gov_cdm.indexed", index=index, count=success,
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
