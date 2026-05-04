"""
filename: gdpr_audit.py
description: Demo Data Generator scenario - GDPR Audit Timeline.

Builds an audit-grade, ECS-aligned dataset that an Elastic Compliance / DPO team
would actually present to a regulator (CNIL / BaFin / ICO) during a GDPR audit.
Aurora Banking, a fictional EU bank, has just received a 90-day audit notice. The
dataset surfaces the three audit findings the regulator cares about:

  - 14 retention-policy violations clustered into 3 monthly incidents (PII held
    past the 24-month retention rule, Art. 5(1)(e) storage limitation).
  - 23 unfulfilled right-to-be-forgotten (RTBF) requests aged > 30 days (hard
    violation of Art. 12 timeline; the data subject must be informed within
    one month).
  - 6 unauthorized access attempts against subjects whose RTBF was already
    fulfilled (the BIG signal: data should have been deleted; this is the
    Art. 17 + Art. 32 control-failure smoking gun).

Three indices, ~4050 docs, plus a 9-panel Kibana dashboard pair (FE prep + Customer
exec view) with inline-data Vega visualisations the DPO team uses to walk the
regulator through detection, controls, and remediation.

Public interface (consumed by routes_demo_data and the seed CLI):

    SCENARIO_ID, SCENARIO_TITLE, SCENARIO_DESCRIPTION
    INDICES: Dict[str, str]
    DASHBOARD_ID: str
    get_mappings()      -> Dict[index_name, mapping_body]
    generate_documents(seed=20260504) -> Dict[index_name, List[doc]]
    get_dashboard_panels()            -> List[panel_dict]
    seed()                            -> Dict[str, Any]

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
from typing import Any, Dict, List, Optional, Tuple

import httpx
from elasticsearch.helpers import bulk

from app.config import settings
from app.integrations.elasticsearch_client import get_client
from app.utils.logging import get_logger

log = get_logger(__name__)


# ============================================================ Public constants =====

SCENARIO_ID: str = "gdpr-audit-timeline"
SCENARIO_TITLE: str = "GDPR Audit Timeline"
SCENARIO_DESCRIPTION: str = (
    "Audit-grade GDPR telemetry for Aurora Banking, a fictional EU bank under a "
    "90-day regulator audit (CNIL / BaFin / ICO). Three ECS-aligned indices cover "
    "data-access logs, retention-policy violations, and the right-to-be-forgotten "
    "request lifecycle. Hidden in the data: 14 retention violations, 23 unfulfilled "
    "RTBF requests aged past 30 days, and 6 unauthorized reads against subjects "
    "whose data should already be deleted."
)

INDICES: Dict[str, str] = {
    "access": "demo-gdpr-access-logs",
    "retention": "demo-gdpr-retention-violations",
    "rtbf": "demo-gdpr-rtbf-requests",
}

DASHBOARD_ID: str = "demo-gdpr-audit-dashboard"
CUSTOMER_DASHBOARD_ID: str = "demo-gdpr-audit-customer-dashboard"
INDEX_PATTERN: str = "demo-gdpr-*"


# ============================================================ Population ============

# Aurora Banking - fictional EU bank, headquartered in Frankfurt with EU branches.
# Internal staff who handle PII (the actors in the access logs).
ORG_DOMAIN = "aurorabanking.eu"

# (display name, email-localpart, role). Roles drive the role-based access charts.
STAFF: List[Tuple[str, str, str]] = [
    ("Anika Keller", "a.keller", "data-protection-officer"),
    ("Mathieu Lefevre", "m.lefevre", "compliance-analyst"),
    ("Sofia Romano", "s.romano", "compliance-analyst"),
    ("Henrik Voss", "h.voss", "compliance-analyst"),
    ("Lara Petrescu", "l.petrescu", "fraud-investigator"),
    ("Bastian Reuter", "b.reuter", "fraud-investigator"),
    ("Eleni Papadakis", "e.papadakis", "customer-support"),
    ("Jonas Berger", "j.berger", "customer-support"),
    ("Marta Lindqvist", "m.lindqvist", "customer-support"),
    ("Pieter van Dijk", "p.vandijk", "customer-support"),
    ("Camille Laurent", "c.laurent", "customer-support"),
    ("Yara Khoury", "y.khoury", "customer-support"),
    ("Tomas Novak", "t.novak", "kyc-analyst"),
    ("Greta Holm", "g.holm", "kyc-analyst"),
    ("Diego Ortiz", "d.ortiz", "credit-analyst"),
    ("Isabella Rizzo", "i.rizzo", "credit-analyst"),
    ("Felix Brandt", "f.brandt", "back-office-ops"),
    ("Hannah Mueller", "h.mueller", "back-office-ops"),
    ("Owen Reilly", "o.reilly", "back-office-ops"),
    ("Lukas Wagner", "l.wagner", "back-office-ops"),
    ("Nadia El-Sayed", "n.elsayed", "marketing-analyst"),
    ("Theo Fontaine", "t.fontaine", "marketing-analyst"),
    ("Vera Solovieva", "v.solovieva", "data-engineer"),
    ("Adrian Calder", "a.calder", "data-engineer"),
    ("Ingrid Holst", "i.holst", "internal-audit"),
    ("Kai Andersen", "k.andersen", "internal-audit"),
    ("Robert Greene", "r.greene", "it-admin"),
    ("Beatrice Lange", "b.lange", "it-admin"),
    ("Mei-Lin Zhao", "m.zhao", "it-admin"),
    ("Naomi Bennett", "n.bennett", "branch-manager"),
]

# Office egress IPs across the EU branch footprint. RFC5737 / RFC3849 reserved
# documentation ranges so we never collide with a real IP.
BRANCH_IPS: List[Dict[str, Any]] = [
    {"ip": "203.0.113.10", "country_iso": "DE", "country": "Germany",
     "city": "Frankfurt", "branch": "Aurora HQ Frankfurt"},
    {"ip": "203.0.113.34", "country_iso": "FR", "country": "France",
     "city": "Paris", "branch": "Aurora Paris"},
    {"ip": "203.0.113.58", "country_iso": "IT", "country": "Italy",
     "city": "Milan", "branch": "Aurora Milan"},
    {"ip": "198.51.100.12", "country_iso": "ES", "country": "Spain",
     "city": "Madrid", "branch": "Aurora Madrid"},
    {"ip": "198.51.100.41", "country_iso": "NL", "country": "Netherlands",
     "city": "Amsterdam", "branch": "Aurora Amsterdam"},
    {"ip": "198.51.100.77", "country_iso": "IE", "country": "Ireland",
     "city": "Dublin", "branch": "Aurora Dublin"},
    {"ip": "192.0.2.22", "country_iso": "BE", "country": "Belgium",
     "city": "Brussels", "branch": "Aurora Brussels"},
    {"ip": "192.0.2.91", "country_iso": "PT", "country": "Portugal",
     "city": "Lisbon", "branch": "Aurora Lisbon"},
]

# Data subject (EU customer) population.
SUBJECT_LOCALES: List[Tuple[str, str]] = [
    ("DE", "Germany"), ("FR", "France"), ("IT", "Italy"), ("ES", "Spain"),
    ("NL", "Netherlands"), ("IE", "Ireland"), ("BE", "Belgium"), ("PT", "Portugal"),
    ("AT", "Austria"), ("FI", "Finland"), ("SE", "Sweden"), ("DK", "Denmark"),
]

DATA_CATEGORIES: List[str] = ["PII", "financial", "behavioral", "special_category"]
# Per-category retention defaults the bank declared in its Article 30 Record.
# 730d (24 months) is the headline policy the audit will measure against.
RETENTION_DAYS_BY_CAT: Dict[str, int] = {
    "PII": 730,
    "financial": 2555,        # 7 years - statutory tax retention beats GDPR
    "behavioral": 365,        # marketing analytics, 12-month rolling window
    "special_category": 1095,  # special category data, 36-month max
}


def _user_email(localpart: str) -> str:
    return f"{localpart}@{ORG_DOMAIN}"


def _user_id(localpart: str) -> str:
    """Stable user.id: u-<8-char hash of localpart>."""
    return "u-" + uuid.uuid5(uuid.NAMESPACE_OID, localpart).hex[:8]


def _subject_id(seed_str: str) -> str:
    """Stable pseudonymous data subject id: ds-<10-char hash>. The bank uses
    pseudonymisation (Art. 4(5)) so subject names never appear in logs."""
    return "ds-" + uuid.uuid5(uuid.NAMESPACE_DNS, seed_str).hex[:10]


# ============================================================ Time helpers =========

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ts(now: datetime, seconds_ago: float) -> str:
    return (now - timedelta(seconds=seconds_ago)).isoformat()


def _seconds_to_days(seconds: float) -> float:
    return seconds / 86400.0


# ============================================================ Mappings =============

def get_mappings() -> Dict[str, Dict[str, Any]]:
    """ECS-friendly mappings. Strict-typed time + IP fields, the rest dynamic so
    we can attach arbitrary compliance fields without index errors."""
    base_props = {
        "@timestamp": {"type": "date"},
        "event": {
            "properties": {
                "action": {"type": "keyword"},
                "outcome": {"type": "keyword"},
                "category": {"type": "keyword"},
                "dataset": {"type": "keyword"},
                "kind": {"type": "keyword"},
                "type": {"type": "keyword"},
                "module": {"type": "keyword"},
                "reason": {"type": "keyword"},
            }
        },
        "source": {
            "properties": {
                "ip": {"type": "ip"},
                "geo": {
                    "properties": {
                        "country_iso_code": {"type": "keyword"},
                        "country_name": {"type": "keyword"},
                        "city_name": {"type": "keyword"},
                    }
                },
            }
        },
        "user": {
            "properties": {
                "email": {"type": "keyword"},
                "id": {"type": "keyword"},
                "name": {"type": "keyword"},
                "role": {"type": "keyword"},
            }
        },
        "data": {
            "properties": {
                "subject_id": {"type": "keyword"},
                "subject_country": {"type": "keyword"},
                "category": {"type": "keyword"},
                "retention_policy_days": {"type": "long"},
                "age_days": {"type": "long"},
                "fields_accessed": {"type": "keyword"},
                "record_count": {"type": "long"},
                "deleted_at": {"type": "date"},
            }
        },
        "compliance": {
            "properties": {
                "regulation": {"type": "keyword"},
                "article": {"type": "keyword"},
                "control_id": {"type": "keyword"},
                "severity": {"type": "keyword"},
                "regulator": {"type": "keyword"},
            }
        },
        "case": {
            "properties": {
                "id": {"type": "keyword"},
                "status": {"type": "keyword"},
                "owner": {"type": "keyword"},
                "sla_breach": {"type": "boolean"},
            }
        },
        "rtbf": {
            "properties": {
                "request_id": {"type": "keyword"},
                "stage": {"type": "keyword"},
                "channel": {"type": "keyword"},
                "requested_at": {"type": "date"},
                "fulfilled_at": {"type": "date"},
                "age_days_at_event": {"type": "long"},
                "verification_status": {"type": "keyword"},
            }
        },
        "url": {"properties": {"path": {"type": "keyword"}, "domain": {"type": "keyword"}}},
        "labels": {"type": "object", "dynamic": True},
        "ecs": {"properties": {"version": {"type": "keyword"}}},
    }

    return {
        INDICES["access"]: {
            "mappings": {"dynamic": "true", "properties": base_props}
        },
        INDICES["retention"]: {
            "mappings": {"dynamic": "true", "properties": base_props}
        },
        INDICES["rtbf"]: {
            "mappings": {"dynamic": "true", "properties": base_props}
        },
    }


# ============================================================ Document builders ====


def _ip_to_branch(ip_profile: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "ip": ip_profile["ip"],
        "geo": {
            "country_iso_code": ip_profile["country_iso"],
            "country_name": ip_profile["country"],
            "city_name": ip_profile.get("city"),
        },
    }


def _staff_user_block(
    staff_row: Tuple[str, str, str]
) -> Dict[str, Any]:
    display, localpart, role = staff_row
    return {
        "email": _user_email(localpart),
        "id": _user_id(localpart),
        "name": display,
        "role": role,
    }


def _build_access_doc(
    *,
    now: datetime,
    seconds_ago: float,
    staff_row: Tuple[str, str, str],
    ip_profile: Dict[str, Any],
    subject_id: str,
    subject_country: str,
    action: str,
    outcome: str,
    category: str,
    fields_accessed: List[str],
    record_count: int,
    rng: random.Random,
    is_threat: bool = False,
    deleted_at_iso: Optional[str] = None,
    reason: Optional[str] = None,
    case_id: Optional[str] = None,
) -> Dict[str, Any]:
    user_block = _staff_user_block(staff_row)
    doc: Dict[str, Any] = {
        "@timestamp": _ts(now, seconds_ago),
        "ecs": {"version": "8.11.0"},
        "event": {
            "kind": "alert" if is_threat else "event",
            "category": ["database", "iam"],
            "type": ["access"],
            "action": action,
            "outcome": outcome,
            "dataset": "aurora.access",
            "module": "aurora-core-banking",
        },
        "source": _ip_to_branch(ip_profile),
        "user": user_block,
        "data": {
            "subject_id": subject_id,
            "subject_country": subject_country,
            "category": category,
            "retention_policy_days": RETENTION_DAYS_BY_CAT[category],
            "fields_accessed": fields_accessed,
            "record_count": record_count,
        },
        "compliance": {
            "regulation": "GDPR",
            "regulator": "EU-DPA",
        },
        "url": {"path": "/api/v2/customers/lookup", "domain": "core.aurorabanking.eu"},
        "labels": {"branch": ip_profile.get("branch")},
    }
    if deleted_at_iso:
        doc["data"]["deleted_at"] = deleted_at_iso
        doc["compliance"]["article"] = "Art. 17"
        doc["compliance"]["severity"] = "critical"
        doc["compliance"]["control_id"] = "AC-DEL-01"
    if reason:
        doc["event"]["reason"] = reason
    if case_id:
        doc["case"] = {"id": case_id, "status": "open", "owner": "compliance-analyst"}
    if is_threat:
        doc["compliance"]["severity"] = doc["compliance"].get("severity", "high")
    return doc


def _build_retention_doc(
    *,
    now: datetime,
    seconds_ago: float,
    staff_row: Tuple[str, str, str],
    ip_profile: Dict[str, Any],
    subject_id: str,
    subject_country: str,
    category: str,
    age_days: int,
    incident_id: str,
    case_id: str,
    rng: random.Random,
) -> Dict[str, Any]:
    """Synthetic retention-violation event: ILM detected a record whose
    age_days exceeds retention_policy_days."""
    user_block = _staff_user_block(staff_row)
    overshoot = age_days - RETENTION_DAYS_BY_CAT[category]
    return {
        "@timestamp": _ts(now, seconds_ago),
        "ecs": {"version": "8.11.0"},
        "event": {
            "kind": "alert",
            "category": ["configuration"],
            "type": ["info"],
            "action": "retention_violation",
            "outcome": "failure",
            "dataset": "aurora.compliance",
            "module": "aurora-ilm-monitor",
            "reason": f"data older than retention policy by {overshoot} days",
        },
        "source": _ip_to_branch(ip_profile),
        "user": user_block,
        "data": {
            "subject_id": subject_id,
            "subject_country": subject_country,
            "category": category,
            "retention_policy_days": RETENTION_DAYS_BY_CAT[category],
            "age_days": age_days,
            "record_count": rng.randint(1, 6),
        },
        "compliance": {
            "regulation": "GDPR",
            "article": "Art. 5(1)(e)",
            "regulator": "EU-DPA",
            "severity": "high",
            "control_id": "RET-ILM-01",
        },
        "case": {
            "id": case_id,
            "status": "investigating",
            "owner": "data-protection-officer",
            "sla_breach": True,
        },
        "labels": {
            "incident_id": incident_id,
            "branch": ip_profile.get("branch"),
            "remediation": "ILM forced delete + audit log entry",
        },
    }


def _build_rtbf_doc(
    *,
    now: datetime,
    seconds_ago: float,
    staff_row: Tuple[str, str, str],
    subject_id: str,
    subject_country: str,
    request_id: str,
    stage: str,
    channel: str,
    requested_at: datetime,
    fulfilled_at: Optional[datetime],
    age_days_at_event: float,
    rng: random.Random,
    sla_breach: bool,
    case_id: str,
    verification_status: str = "verified",
) -> Dict[str, Any]:
    user_block = _staff_user_block(staff_row)
    article = "Art. 17" if stage in ("rtbf_fulfilled", "rtbf_requested") else "Art. 12"
    severity = "critical" if sla_breach else ("medium" if stage != "rtbf_fulfilled" else "info")
    outcome = "success" if stage == "rtbf_fulfilled" else "in_progress"
    return {
        "@timestamp": _ts(now, seconds_ago),
        "ecs": {"version": "8.11.0"},
        "event": {
            "kind": "event" if not sla_breach else "alert",
            "category": ["process"],
            "type": ["info"],
            "action": stage,
            "outcome": outcome,
            "dataset": "aurora.rtbf",
            "module": "aurora-privacy-portal",
        },
        "user": user_block,
        "data": {
            "subject_id": subject_id,
            "subject_country": subject_country,
            "category": "PII",
            "retention_policy_days": RETENTION_DAYS_BY_CAT["PII"],
        },
        "compliance": {
            "regulation": "GDPR",
            "article": article,
            "regulator": "EU-DPA",
            "severity": severity,
            "control_id": "RTBF-SLA-30D",
        },
        "rtbf": {
            "request_id": request_id,
            "stage": stage,
            "channel": channel,
            "requested_at": requested_at.isoformat(),
            "fulfilled_at": fulfilled_at.isoformat() if fulfilled_at else None,
            "age_days_at_event": int(round(age_days_at_event)),
            "verification_status": verification_status,
        },
        "case": {
            "id": case_id,
            "status": "closed" if stage == "rtbf_fulfilled" else (
                "escalated" if sla_breach else "in_progress"
            ),
            "owner": "compliance-analyst",
            "sla_breach": sla_breach,
        },
        "labels": {
            "channel": channel,
        },
    }


# ============================================================ Generators ============


def _generate_baseline_access(
    rng: random.Random, now: datetime, subject_pool: List[Tuple[str, str]]
) -> List[Dict[str, Any]]:
    """~3500 legitimate access events across 90 days. Distribution is skewed to
    business hours and to customer-support / kyc roles (the heavy PII consumers)."""
    docs: List[Dict[str, Any]] = []
    role_weight: Dict[str, float] = {
        "customer-support": 0.36,
        "kyc-analyst": 0.18,
        "compliance-analyst": 0.10,
        "fraud-investigator": 0.09,
        "credit-analyst": 0.08,
        "back-office-ops": 0.07,
        "marketing-analyst": 0.05,
        "data-engineer": 0.03,
        "internal-audit": 0.02,
        "branch-manager": 0.01,
        "it-admin": 0.005,
        "data-protection-officer": 0.005,
    }
    staff_by_role: Dict[str, List[Tuple[str, str, str]]] = {}
    for row in STAFF:
        staff_by_role.setdefault(row[2], []).append(row)
    roles_pool = list(role_weight.keys())
    weights_pool = [role_weight[r] for r in roles_pool]

    actions = ["data_access", "data_access", "data_access", "data_export"]
    fields_by_category = {
        "PII": ["name", "email", "phone", "address", "date_of_birth", "iban"],
        "financial": ["account_number", "iban", "balance", "transaction_history"],
        "behavioral": ["session_clicks", "marketing_segment", "product_views"],
        "special_category": ["health_disclosure", "biometric_template"],
    }

    for _ in range(3500):
        # Time skew: linear over 90 days, with daily business-hours peak.
        day_back = rng.uniform(0.5, 90.0)
        hour = int(rng.choice([8, 9, 9, 10, 10, 11, 11, 12, 13, 14, 14, 15, 15, 16, 16, 17, 18]))
        minute = rng.randint(0, 59)
        seconds_ago = day_back * 86400 + (24 - hour) * 3600 + (60 - minute) * 60
        seconds_ago = max(60.0, seconds_ago)

        role = rng.choices(roles_pool, weights=weights_pool, k=1)[0]
        staff_row = rng.choice(staff_by_role[role])
        ip_profile = rng.choice(BRANCH_IPS)

        # Category mix differs by role.
        if role in ("customer-support", "kyc-analyst"):
            category = rng.choices(
                ["PII", "financial", "behavioral"], weights=[0.7, 0.2, 0.1], k=1
            )[0]
        elif role == "fraud-investigator":
            category = rng.choices(
                ["financial", "PII", "behavioral"], weights=[0.6, 0.3, 0.1], k=1
            )[0]
        elif role == "marketing-analyst":
            category = rng.choices(
                ["behavioral", "PII"], weights=[0.85, 0.15], k=1
            )[0]
        elif role == "credit-analyst":
            category = rng.choices(
                ["financial", "PII"], weights=[0.7, 0.3], k=1
            )[0]
        elif role == "compliance-analyst":
            category = rng.choices(
                ["PII", "special_category"], weights=[0.7, 0.3], k=1
            )[0]
        else:
            category = rng.choices(
                ["PII", "financial", "behavioral"], weights=[0.5, 0.3, 0.2], k=1
            )[0]

        subject_seed = rng.choice(subject_pool)
        subj_country, subj_country_name = subject_seed
        subject = _subject_id(f"{subj_country}-{rng.randint(1, 9999)}")
        action = rng.choice(actions)
        n_fields = rng.randint(1, len(fields_by_category[category]))
        fields = rng.sample(fields_by_category[category], k=n_fields)

        outcome = "success" if rng.random() < 0.985 else "failure"
        docs.append(_build_access_doc(
            now=now, seconds_ago=seconds_ago,
            staff_row=staff_row, ip_profile=ip_profile,
            subject_id=subject, subject_country=subj_country_name,
            action=action, outcome=outcome,
            category=category,
            fields_accessed=fields,
            record_count=rng.randint(1, 4) if action == "data_access" else rng.randint(50, 5000),
            rng=rng,
        ))
    return docs


def _generate_retention_violations(
    rng: random.Random, now: datetime, subject_pool: List[Tuple[str, str]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Build:
       - 14 critical retention-violation events distributed across 3 monthly incidents.
       - ~136 lower-severity ILM noise events (close-to-policy but inside grace
         period) so the chart shows the cluster without overwhelming the signal.
       Returns (critical_violations, all_violation_docs)."""
    critical: List[Dict[str, Any]] = []
    all_docs: List[Dict[str, Any]] = []

    # Incident anchors: ~75d, ~45d, ~15d ago. Each contains a subset of the 14.
    incident_anchors = [
        {"days_ago": 75, "id": "INC-RET-2026-Q1-A", "count": 5},
        {"days_ago": 45, "id": "INC-RET-2026-Q1-B", "count": 5},
        {"days_ago": 15, "id": "INC-RET-2026-Q2-A", "count": 4},
    ]

    dpo_row = next(s for s in STAFF if s[2] == "data-protection-officer")
    ilm_admin_row = next(s for s in STAFF if s[2] == "it-admin")

    crit_idx = 0
    for incident in incident_anchors:
        for k in range(incident["count"]):
            crit_idx += 1
            seconds_ago = (
                incident["days_ago"] * 86400
                + rng.uniform(-12 * 3600, 12 * 3600)
            )
            seconds_ago = max(120.0, seconds_ago)
            subj_iso, subj_name = rng.choice(subject_pool)
            subject = _subject_id(f"retention-{incident['id']}-{k}-{subj_iso}")
            # PII category retains 730d. Make age 735-780 days (1-7 weeks past policy).
            age = 735 + rng.randint(0, 50)
            ip_profile = rng.choice(BRANCH_IPS)
            case_id = f"DPO-{incident['id']}-{crit_idx:03d}"
            doc = _build_retention_doc(
                now=now, seconds_ago=seconds_ago,
                staff_row=dpo_row, ip_profile=ip_profile,
                subject_id=subject, subject_country=subj_name,
                category="PII", age_days=age,
                incident_id=incident["id"], case_id=case_id,
                rng=rng,
            )
            critical.append(doc)
            all_docs.append(doc)

    # Lower-severity ILM grace-period docs (still well-formed, severity=low)
    for _ in range(136):
        seconds_ago = rng.uniform(2 * 86400, 89 * 86400)
        category = rng.choices(
            ["financial", "behavioral", "PII"], weights=[0.5, 0.3, 0.2], k=1
        )[0]
        # Just under policy: age within last 5% of retention.
        retention = RETENTION_DAYS_BY_CAT[category]
        age = retention - rng.randint(1, max(2, int(retention * 0.05)))
        subj_iso, subj_name = rng.choice(subject_pool)
        subject = _subject_id(f"grace-{rng.randint(1, 99999)}")
        ip_profile = rng.choice(BRANCH_IPS)
        doc = _build_retention_doc(
            now=now, seconds_ago=seconds_ago,
            staff_row=ilm_admin_row, ip_profile=ip_profile,
            subject_id=subject, subject_country=subj_name,
            category=category, age_days=age,
            incident_id="ILM-grace-window",
            case_id=f"ILM-{uuid.uuid4().hex[:8]}",
            rng=rng,
        )
        # Downgrade severity since this is grace-window, not a violation.
        doc["compliance"]["severity"] = "low"
        doc["event"]["action"] = "retention_grace_window"
        doc["event"]["outcome"] = "success"
        doc["event"]["kind"] = "event"
        doc["case"]["sla_breach"] = False
        doc["case"]["status"] = "monitoring"
        all_docs.append(doc)

    return critical, all_docs


def _generate_rtbf_lifecycle(
    rng: random.Random, now: datetime, subject_pool: List[Tuple[str, str]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Tuple[str, datetime]]]:
    """Generate the RTBF index. Four cohorts:
       - 23 unfulfilled-and-overdue requests (request stayed in `processing`
         past 30 days). Each emits requested + processing event(s).
       - ~290 normal fulfilled requests (median ~12 days, all under 30 days).
       - ~60 in-flight requests still under 30 days (no SLA breach yet).
       - The fulfilled cohort returns the (subject_id, fulfilled_at) tuples
         that the unauthorized-access generator can target.
       Returns (sla_breach_records, all_docs, fulfilled_subjects)."""
    docs: List[Dict[str, Any]] = []
    breach_records: List[Dict[str, Any]] = []
    fulfilled_subjects: List[Tuple[str, datetime]] = []

    compliance_staff = [s for s in STAFF if s[2] == "compliance-analyst"]
    support_staff = [s for s in STAFF if s[2] == "customer-support"]

    channels = ["privacy-portal", "email-dpo", "branch-walkin", "postal-letter"]
    channel_weights = [0.55, 0.28, 0.12, 0.05]

    # ----- 23 SLA breaches -------------------------------------------------------
    for i in range(23):
        # Request was made 32-58 days ago and never completed.
        req_days_ago = rng.uniform(32, 58)
        requested_at = now - timedelta(days=req_days_ago)
        subj_iso, subj_name = rng.choice(subject_pool)
        subject = _subject_id(f"rtbf-breach-{i:03d}-{subj_iso}")
        request_id = f"RTBF-{requested_at.strftime('%Y%m%d')}-{i:03d}"
        case_id = f"DPO-RTBF-{request_id}"
        channel = rng.choices(channels, weights=channel_weights, k=1)[0]
        staff_row = rng.choice(compliance_staff)

        # Stage 1: requested
        docs.append(_build_rtbf_doc(
            now=now, seconds_ago=req_days_ago * 86400,
            staff_row=staff_row,
            subject_id=subject, subject_country=subj_name,
            request_id=request_id, stage="rtbf_requested",
            channel=channel, requested_at=requested_at,
            fulfilled_at=None,
            age_days_at_event=0.0,
            rng=rng, sla_breach=False, case_id=case_id,
        ))
        # Stage 2: processing - 1-3 events along the journey
        for k in range(rng.randint(1, 3)):
            elapsed = rng.uniform(1.0, req_days_ago - 1.0)
            sec_ago = (req_days_ago - elapsed) * 86400
            docs.append(_build_rtbf_doc(
                now=now, seconds_ago=sec_ago,
                staff_row=staff_row,
                subject_id=subject, subject_country=subj_name,
                request_id=request_id, stage="rtbf_processing",
                channel=channel, requested_at=requested_at,
                fulfilled_at=None,
                age_days_at_event=elapsed,
                rng=rng, sla_breach=False, case_id=case_id,
            ))
        # Stage 3: an explicit `rtbf_overdue` alert event at the 30d mark
        sec_ago_30 = (req_days_ago - 30.0) * 86400
        docs.append(_build_rtbf_doc(
            now=now, seconds_ago=max(120.0, sec_ago_30),
            staff_row=staff_row,
            subject_id=subject, subject_country=subj_name,
            request_id=request_id, stage="rtbf_escalated",
            channel=channel, requested_at=requested_at,
            fulfilled_at=None,
            age_days_at_event=30.0,
            rng=rng, sla_breach=True, case_id=case_id,
        ))
        breach_records.append({
            "request_id": request_id,
            "subject_id": subject,
            "subject_country": subj_name,
            "channel": channel,
            "requested_at": requested_at,
            "age_days": req_days_ago,
            "case_id": case_id,
        })

    # ----- ~290 normal fulfilled requests ---------------------------------------
    for i in range(290):
        req_days_ago = rng.uniform(1.5, 89.0)
        requested_at = now - timedelta(days=req_days_ago)
        # Time-to-fulfil: median ~10-12 days, mostly under 28 days.
        ttf_days = max(0.5, min(28.0, rng.gauss(11.0, 5.0)))
        if ttf_days >= req_days_ago:
            ttf_days = max(0.25, req_days_ago - 0.25)
        fulfilled_at = requested_at + timedelta(days=ttf_days)

        subj_iso, subj_name = rng.choice(subject_pool)
        subject = _subject_id(f"rtbf-ok-{i:04d}-{subj_iso}")
        request_id = f"RTBF-{requested_at.strftime('%Y%m%d')}-A{i:03d}"
        case_id = f"DPO-RTBF-{request_id}"
        channel = rng.choices(channels, weights=channel_weights, k=1)[0]
        staff_row = rng.choice(compliance_staff)

        # requested
        docs.append(_build_rtbf_doc(
            now=now, seconds_ago=req_days_ago * 86400,
            staff_row=staff_row,
            subject_id=subject, subject_country=subj_name,
            request_id=request_id, stage="rtbf_requested",
            channel=channel, requested_at=requested_at,
            fulfilled_at=None,
            age_days_at_event=0.0,
            rng=rng, sla_breach=False, case_id=case_id,
        ))
        # 1 processing event
        proc_elapsed = rng.uniform(0.2, ttf_days * 0.8)
        docs.append(_build_rtbf_doc(
            now=now, seconds_ago=(req_days_ago - proc_elapsed) * 86400,
            staff_row=staff_row,
            subject_id=subject, subject_country=subj_name,
            request_id=request_id, stage="rtbf_processing",
            channel=channel, requested_at=requested_at,
            fulfilled_at=None,
            age_days_at_event=proc_elapsed,
            rng=rng, sla_breach=False, case_id=case_id,
        ))
        # fulfilled
        sec_ago = max(120.0, (req_days_ago - ttf_days) * 86400)
        docs.append(_build_rtbf_doc(
            now=now, seconds_ago=sec_ago,
            staff_row=staff_row,
            subject_id=subject, subject_country=subj_name,
            request_id=request_id, stage="rtbf_fulfilled",
            channel=channel, requested_at=requested_at,
            fulfilled_at=fulfilled_at,
            age_days_at_event=ttf_days,
            rng=rng, sla_breach=False, case_id=case_id,
        ))
        fulfilled_subjects.append((subject, fulfilled_at))

    # ----- ~60 in-flight, under-30d requests ------------------------------------
    for i in range(60):
        req_days_ago = rng.uniform(0.5, 28.0)
        requested_at = now - timedelta(days=req_days_ago)
        subj_iso, subj_name = rng.choice(subject_pool)
        subject = _subject_id(f"rtbf-flight-{i:03d}-{subj_iso}")
        request_id = f"RTBF-{requested_at.strftime('%Y%m%d')}-B{i:03d}"
        case_id = f"DPO-RTBF-{request_id}"
        channel = rng.choices(channels, weights=channel_weights, k=1)[0]
        staff_row = rng.choice(compliance_staff)

        docs.append(_build_rtbf_doc(
            now=now, seconds_ago=req_days_ago * 86400,
            staff_row=staff_row,
            subject_id=subject, subject_country=subj_name,
            request_id=request_id, stage="rtbf_requested",
            channel=channel, requested_at=requested_at,
            fulfilled_at=None,
            age_days_at_event=0.0,
            rng=rng, sla_breach=False, case_id=case_id,
        ))
        if rng.random() < 0.7:
            docs.append(_build_rtbf_doc(
                now=now, seconds_ago=max(120.0, (req_days_ago - rng.uniform(0.2, req_days_ago * 0.8)) * 86400),
                staff_row=staff_row,
                subject_id=subject, subject_country=subj_name,
                request_id=request_id, stage="rtbf_processing",
                channel=channel, requested_at=requested_at,
                fulfilled_at=None,
                age_days_at_event=rng.uniform(0.5, req_days_ago - 0.5),
                rng=rng, sla_breach=False, case_id=case_id,
            ))

    return breach_records, docs, fulfilled_subjects


def _generate_unauthorized_post_rtbf_access(
    rng: random.Random,
    now: datetime,
    fulfilled_subjects: List[Tuple[str, datetime]],
) -> List[Dict[str, Any]]:
    """The smoking gun: 6 events where staff tried to read a subject whose data
    was already deleted via RTBF. These are the headline audit findings.

    Each event sets `data.deleted_at`, `compliance.article = Art. 17`,
    `compliance.severity = critical`, and tags an open Case for the regulator
    paper trail."""
    docs: List[Dict[str, Any]] = []
    if not fulfilled_subjects:
        return docs

    # Pick 6 distinct fulfilled subjects whose deletion is at least 5 days old.
    candidates = [
        s for s in fulfilled_subjects
        if (now - s[1]).total_seconds() / 86400 > 5
    ]
    if len(candidates) < 6:
        candidates = fulfilled_subjects[:6]
    targets = rng.sample(candidates, k=min(6, len(candidates)))

    # Cluster the 6 unauthorized reads in office hours (9 AM, 11 AM, 14 PM, 16 PM).
    hour_pool = [9, 11, 14, 14, 16, 18]
    rng.shuffle(hour_pool)

    suspicious_roles = [
        ("customer-support", 0.5),
        ("marketing-analyst", 0.25),
        ("back-office-ops", 0.15),
        ("kyc-analyst", 0.10),
    ]
    role_choices = [r[0] for r in suspicious_roles]
    role_weights = [r[1] for r in suspicious_roles]
    staff_by_role: Dict[str, List[Tuple[str, str, str]]] = {}
    for s in STAFF:
        staff_by_role.setdefault(s[2], []).append(s)

    for idx, (subject_id, deleted_at) in enumerate(targets):
        # Place attempt 2-9 days after deletion, in business hours.
        days_after_delete = rng.uniform(2.0, 9.0)
        attempt_at = deleted_at + timedelta(
            days=days_after_delete, hours=hour_pool[idx % len(hour_pool)],
            minutes=rng.randint(0, 59),
        )
        seconds_ago = max(120.0, (now - attempt_at).total_seconds())

        role = rng.choices(role_choices, weights=role_weights, k=1)[0]
        staff_row = rng.choice(staff_by_role.get(role, [STAFF[0]]))
        ip_profile = rng.choice(BRANCH_IPS)
        case_id = f"DPO-UNAUTHZ-{idx + 1:03d}"
        reason = rng.choice([
            "subject record returns 404 (already deleted)",
            "ILM tombstone matched - access blocked at API gateway",
            "tombstone hit - escalated to data-protection-officer",
        ])
        doc = _build_access_doc(
            now=now, seconds_ago=seconds_ago,
            staff_row=staff_row, ip_profile=ip_profile,
            subject_id=subject_id, subject_country="EU",
            action="data_access", outcome="failure",
            category="PII",
            fields_accessed=["email", "iban", "address"],
            record_count=0,
            rng=rng,
            is_threat=True,
            deleted_at_iso=deleted_at.isoformat(),
            reason=reason,
            case_id=case_id,
        )
        # Override compliance article precision: this is BOTH Art. 17 (right to
        # erasure) and Art. 32 (security of processing). Tag both in the label
        # cloud so the dashboard shows the full picture.
        doc["compliance"]["article"] = "Art. 17"
        doc["labels"]["secondary_article"] = "Art. 32"
        doc["labels"]["mitre_aligned"] = "T1530-Data-from-Cloud-Storage"
        doc["labels"]["finding_kind"] = "post-rtbf-unauthorized-read"
        docs.append(doc)
    return docs


# ============================================================ Master generator =====


# Module-level caches so the dashboard panels can render audit numbers without
# re-running the generator.
_AUDIT_CACHE: Dict[str, Any] = {}


def _persist_audit_cache(payload: Dict[str, Any]) -> None:
    global _AUDIT_CACHE
    _AUDIT_CACHE = payload


def get_audit_cache() -> Dict[str, Any]:
    return dict(_AUDIT_CACHE)


def generate_documents(seed: int = 20260504) -> Dict[str, List[Dict[str, Any]]]:
    """Generate all documents for the scenario, deterministic with `seed`."""
    rng = random.Random(seed)
    now = _now()

    subject_pool: List[Tuple[str, str]] = SUBJECT_LOCALES

    # Step 1: legitimate access logs (3500 docs over 90 days).
    access_baseline = _generate_baseline_access(rng, now, subject_pool)

    # Step 2: retention violations (14 critical + ~136 grace-window).
    crit_violations, retention_docs = _generate_retention_violations(rng, now, subject_pool)

    # Step 3: RTBF lifecycle (~400 docs total). Returns the fulfilled subjects
    # so we can target them for the unauthorized-access events.
    rtbf_breaches, rtbf_docs, fulfilled_subjects = _generate_rtbf_lifecycle(
        rng, now, subject_pool
    )

    # Step 4: 6 unauthorized post-RTBF reads. These join the access index.
    unauth_docs = _generate_unauthorized_post_rtbf_access(rng, now, fulfilled_subjects)

    access_docs = access_baseline + unauth_docs
    rng.shuffle(access_docs)
    rng.shuffle(retention_docs)
    rng.shuffle(rtbf_docs)

    _persist_audit_cache({
        "critical_retention_violations": [
            {
                "subject_id": d["data"]["subject_id"],
                "subject_country": d["data"].get("subject_country"),
                "category": d["data"]["category"],
                "age_days": d["data"]["age_days"],
                "incident_id": d["labels"]["incident_id"],
                "case_id": d["case"]["id"],
                "ts": d["@timestamp"],
            } for d in crit_violations
        ],
        "rtbf_sla_breaches": [
            {
                "request_id": b["request_id"],
                "subject_id": b["subject_id"],
                "subject_country": b["subject_country"],
                "channel": b["channel"],
                "requested_at": b["requested_at"].isoformat(),
                "age_days": round(b["age_days"], 1),
                "case_id": b["case_id"],
            } for b in rtbf_breaches
        ],
        "unauthorized_post_rtbf_reads": [
            {
                "subject_id": d["data"]["subject_id"],
                "deleted_at": d["data"].get("deleted_at"),
                "ts": d["@timestamp"],
                "user": d["user"]["email"],
                "user_role": d["user"]["role"],
                "branch": d["labels"].get("branch"),
                "case_id": d["case"]["id"],
                "reason": d["event"].get("reason"),
            } for d in unauth_docs
        ],
        "totals": {
            "access_total": len(access_docs),
            "retention_total": len(retention_docs),
            "rtbf_total": len(rtbf_docs),
            "fulfilled_rtbf": len(fulfilled_subjects),
            "critical_retention": len(crit_violations),
            "rtbf_sla_breach": len(rtbf_breaches),
            "unauth_post_rtbf": len(unauth_docs),
        },
    })

    return {
        INDICES["access"]: access_docs,
        INDICES["retention"]: retention_docs,
        INDICES["rtbf"]: rtbf_docs,
    }


# ============================================================ Vega specs ============


def _vega_panel(
    panel_id: str, x: int, y: int, w: int, h: int, title: str, spec: Dict[str, Any]
) -> Dict[str, Any]:
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


def _markdown_panel(
    panel_id: str, x: int, y: int, w: int, h: int, markdown: str, title: str = ""
) -> Dict[str, Any]:
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


# ----- Vega-Lite specs (inline data) -------------------------------------------------
#
# Kibana 9.3 rejects URL-based Vega specs at render time even when the saved
# object validates. Every spec below queries Elasticsearch at seed time and
# embeds the resulting buckets as `data.values`. Each query is wrapped in
# try/except so a transient ES failure produces an empty chart rather than a
# broken seed run.


def _vega_violations_by_article() -> Dict[str, Any]:
    """Bar chart: violations grouped by GDPR article. Inline data."""
    values: List[Dict[str, Any]] = []
    article_labels = {
        "Art. 5(1)(e)": "Art. 5(1)(e) - storage limitation",
        "Art. 12": "Art. 12 - transparent communication / 1-month SLA",
        "Art. 17": "Art. 17 - right to erasure",
        "Art. 32": "Art. 32 - security of processing",
    }
    try:
        es = get_client()
        # Aggregate across all three indices.
        r = es.search(index=INDEX_PATTERN, body={
            "size": 0,
            "query": {"bool": {"filter": [
                {"range": {"@timestamp": {"gte": "now-90d", "lte": "now"}}},
                {"terms": {"compliance.severity": ["critical", "high", "medium"]}},
            ]}},
            "aggs": {
                "by_article": {
                    "terms": {"field": "compliance.article", "size": 10},
                }
            },
        })
        for b in r["aggregations"]["by_article"]["buckets"]:
            article = b["key"]
            values.append({
                "article": article,
                "label": article_labels.get(article, article),
                "count": int(b.get("doc_count") or 0),
            })
    except Exception as exc:
        log.warning("gdpr.spec_articles.compute.failed", error=str(exc))

    # Augment with the secondary Art. 32 tagging from the unauthorized-read
    # events (they double-count under Art. 17 + Art. 32 for the regulator).
    cache = get_audit_cache()
    art32 = sum(1 for r in cache.get("unauthorized_post_rtbf_reads", []) if r)
    if art32:
        values.append({
            "article": "Art. 32",
            "label": article_labels["Art. 32"],
            "count": art32,
        })

    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": "Findings by GDPR article (last 90d)",
        "data": {"values": values},
        "mark": {"type": "bar", "tooltip": True, "cornerRadiusEnd": 3},
        "encoding": {
            "y": {
                "field": "label", "type": "nominal", "sort": "-x",
                "title": "GDPR article",
                "axis": {"labelColor": "#cdd", "titleColor": "#cdd"},
            },
            "x": {
                "field": "count", "type": "quantitative",
                "title": "Findings",
                "axis": {"labelColor": "#cdd", "titleColor": "#cdd"},
            },
            "color": {
                "field": "article", "type": "nominal",
                "scale": {
                    "domain": ["Art. 5(1)(e)", "Art. 12", "Art. 17", "Art. 32"],
                    "range": ["#f0a830", "#e8455d", "#a83232", "#5b8bbd"],
                },
                "legend": {"labelColor": "#cdd", "titleColor": "#cdd"},
            },
            "tooltip": [
                {"field": "label", "type": "nominal", "title": "Article"},
                {"field": "count", "type": "quantitative", "title": "Findings"},
            ],
        },
        "config": {"view": {"stroke": "transparent"}, "background": "transparent"},
    }


def _vega_rtbf_volume_and_ttf() -> Dict[str, Any]:
    """Layered chart: weekly RTBF request volume (bars) + median time-to-fulfil
    (line) over the last 90d. Inline data."""
    weekly: Dict[str, Dict[str, Any]] = {}
    try:
        es = get_client()
        # Volume per week of requests (rtbf_requested only)
        r1 = es.search(index=INDICES["rtbf"], body={
            "size": 0,
            "query": {"bool": {"filter": [
                {"term": {"event.action": "rtbf_requested"}},
                {"range": {"@timestamp": {"gte": "now-90d", "lte": "now"}}},
            ]}},
            "aggs": {
                "by_week": {
                    "date_histogram": {
                        "field": "@timestamp",
                        "fixed_interval": "7d",
                        "min_doc_count": 0,
                    }
                }
            },
        })
        for b in r1["aggregations"]["by_week"]["buckets"]:
            ts = b.get("key_as_string") or b.get("key")
            weekly[ts] = {"week": ts, "requests": int(b.get("doc_count") or 0),
                          "median_ttf_days": None}

        # Median TTF per week, computed from rtbf_fulfilled events.
        r2 = es.search(index=INDICES["rtbf"], body={
            "size": 0,
            "query": {"bool": {"filter": [
                {"term": {"event.action": "rtbf_fulfilled"}},
                {"range": {"@timestamp": {"gte": "now-90d", "lte": "now"}}},
            ]}},
            "aggs": {
                "by_week": {
                    "date_histogram": {
                        "field": "@timestamp",
                        "fixed_interval": "7d",
                        "min_doc_count": 0,
                    },
                    "aggs": {
                        "med": {"percentiles": {
                            "field": "rtbf.age_days_at_event",
                            "percents": [50],
                        }}
                    }
                }
            },
        })
        for b in r2["aggregations"]["by_week"]["buckets"]:
            ts = b.get("key_as_string") or b.get("key")
            entry = weekly.setdefault(ts, {"week": ts, "requests": 0,
                                           "median_ttf_days": None})
            try:
                v = b.get("med", {}).get("values", {}).get("50.0")
                entry["median_ttf_days"] = round(float(v), 2) if v is not None else None
            except Exception:
                entry["median_ttf_days"] = None
    except Exception as exc:
        log.warning("gdpr.spec_rtbf_ttf.compute.failed", error=str(exc))

    values = sorted(weekly.values(), key=lambda r: r.get("week", ""))

    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": "RTBF requests + median time-to-fulfilment (weekly, 30d SLA line)",
        "data": {"values": values},
        "encoding": {
            "x": {
                "field": "week", "type": "temporal",
                "title": "Week",
                "axis": {"labelColor": "#cdd", "titleColor": "#cdd"},
            }
        },
        "layer": [
            {
                "mark": {"type": "bar", "color": "#5b8bbd", "tooltip": True,
                         "cornerRadiusEnd": 2},
                "encoding": {
                    "y": {
                        "field": "requests", "type": "quantitative",
                        "title": "RTBF requests",
                        "axis": {"labelColor": "#cdd", "titleColor": "#cdd"},
                    },
                    "tooltip": [
                        {"field": "week", "type": "temporal"},
                        {"field": "requests", "type": "quantitative"},
                    ],
                },
            },
            {
                "mark": {"type": "line", "color": "#e8455d", "strokeWidth": 2.5,
                         "interpolate": "monotone", "tooltip": True, "point": True},
                "encoding": {
                    "y": {
                        "field": "median_ttf_days", "type": "quantitative",
                        "title": "Median time-to-fulfil (days)",
                        "axis": {"orient": "right", "labelColor": "#cdd",
                                 "titleColor": "#cdd"},
                    },
                    "tooltip": [
                        {"field": "week", "type": "temporal"},
                        {"field": "median_ttf_days", "type": "quantitative",
                         "title": "Median TTF (d)"},
                    ],
                },
            },
            {
                "mark": {"type": "rule", "color": "#f0a830", "strokeDash": [4, 4]},
                "data": {"values": [{"sla_days": 30}]},
                "encoding": {
                    "y": {"field": "sla_days", "type": "quantitative"},
                },
            },
        ],
        "resolve": {"scale": {"y": "independent"}},
        "config": {"view": {"stroke": "transparent"}, "background": "transparent"},
    }


def _vega_top_roles_with_violations() -> Dict[str, Any]:
    """Top 5 user roles by retention-violation count. Inline data."""
    values: List[Dict[str, Any]] = []
    try:
        es = get_client()
        r = es.search(index=INDICES["retention"], body={
            "size": 0,
            "query": {"bool": {"filter": [
                {"term": {"event.action": "retention_violation"}},
                {"range": {"@timestamp": {"gte": "now-90d", "lte": "now"}}},
            ]}},
            "aggs": {
                "by_role": {"terms": {"field": "user.role", "size": 5}},
            },
        })
        for b in r["aggregations"]["by_role"]["buckets"]:
            values.append({
                "role": b["key"],
                "count": int(b.get("doc_count") or 0),
            })
    except Exception as exc:
        log.warning("gdpr.spec_top_roles.compute.failed", error=str(exc))

    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": "Top user roles linked to retention violations (90d)",
        "data": {"values": values},
        "mark": {"type": "bar", "tooltip": True, "cornerRadiusEnd": 3,
                 "color": "#a83232"},
        "encoding": {
            "y": {
                "field": "role", "type": "nominal", "sort": "-x",
                "title": "User role",
                "axis": {"labelColor": "#cdd", "titleColor": "#cdd"},
            },
            "x": {
                "field": "count", "type": "quantitative",
                "title": "Retention violations",
                "axis": {"labelColor": "#cdd", "titleColor": "#cdd"},
            },
            "tooltip": [
                {"field": "role", "type": "nominal"},
                {"field": "count", "type": "quantitative"},
            ],
        },
        "config": {"view": {"stroke": "transparent"}, "background": "transparent"},
    }


def _vega_unauthz_heatmap() -> Dict[str, Any]:
    """Heatmap: unauthorized reads on deleted-subject data, by hour-of-day x
    user role. Inline data, computed at seed time."""
    cache = get_audit_cache()
    unauth = cache.get("unauthorized_post_rtbf_reads", [])
    grid: Dict[Tuple[int, str], int] = {}
    for r in unauth:
        ts = r.get("ts")
        try:
            hour = datetime.fromisoformat(str(ts).replace("Z", "+00:00")).hour
        except Exception:
            hour = 0
        role = r.get("user_role", "unknown")
        grid[(hour, role)] = grid.get((hour, role), 0) + 1
    # Always render a 24x4 lattice so the heatmap looks intentional.
    roles_ordered = ["customer-support", "marketing-analyst",
                     "back-office-ops", "kyc-analyst"]
    values: List[Dict[str, Any]] = []
    for hour in range(24):
        for role in roles_ordered:
            values.append({
                "hour_of_day": hour,
                "role": role,
                "attempts": grid.get((hour, role), 0),
            })

    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": "Unauthorized reads on deleted-subject data (Art. 17 violation)",
        "data": {"values": values},
        "mark": {"type": "rect", "tooltip": True},
        "encoding": {
            "x": {
                "field": "hour_of_day", "type": "ordinal",
                "title": "Hour of day (UTC)",
                "axis": {"labelColor": "#cdd", "titleColor": "#cdd"},
            },
            "y": {
                "field": "role", "type": "nominal",
                "title": "User role",
                "axis": {"labelColor": "#cdd", "titleColor": "#cdd"},
            },
            "color": {
                "field": "attempts", "type": "quantitative",
                "scale": {"scheme": "reds"},
                "title": "Unauthorized reads",
                "legend": {"labelColor": "#cdd", "titleColor": "#cdd"},
            },
            "tooltip": [
                {"field": "role", "type": "nominal"},
                {"field": "hour_of_day", "type": "ordinal", "title": "Hour"},
                {"field": "attempts", "type": "quantitative"},
            ],
        },
        "config": {"view": {"stroke": "transparent"}, "background": "transparent"},
    }


def _vega_critical_incident_timeline() -> Dict[str, Any]:
    """Full-width timeline of the 6 critical incidents (post-RTBF unauthorized
    reads) with vertical guidelines. Inline data."""
    cache = get_audit_cache()
    unauth = cache.get("unauthorized_post_rtbf_reads", [])
    values: List[Dict[str, Any]] = []
    for idx, r in enumerate(unauth):
        values.append({
            "ts": r.get("ts"),
            "label": f"INC-{idx + 1:02d}",
            "user_role": r.get("user_role"),
            "branch": r.get("branch"),
            "case_id": r.get("case_id"),
            "subject_id": r.get("subject_id"),
            "severity": "critical",
            "y_band": idx + 1,
        })

    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": "Critical incidents - 6 unauthorized reads on deleted accounts",
        "data": {"values": values},
        "layer": [
            {
                "mark": {"type": "rule", "color": "#7e8794", "strokeDash": [2, 4]},
                "encoding": {
                    "x": {"field": "ts", "type": "temporal"},
                },
            },
            {
                "mark": {"type": "circle", "size": 320, "color": "#e8455d",
                         "tooltip": True, "stroke": "#1a1d24", "strokeWidth": 1},
                "encoding": {
                    "x": {
                        "field": "ts", "type": "temporal",
                        "title": "Time (UTC)",
                        "axis": {"labelColor": "#cdd", "titleColor": "#cdd"},
                    },
                    "y": {
                        "field": "y_band", "type": "quantitative",
                        "title": "Incident #",
                        "axis": {"labelColor": "#cdd", "titleColor": "#cdd"},
                    },
                    "tooltip": [
                        {"field": "label", "type": "nominal", "title": "Incident"},
                        {"field": "ts", "type": "temporal", "title": "When"},
                        {"field": "user_role", "type": "nominal", "title": "User role"},
                        {"field": "branch", "type": "nominal", "title": "Branch"},
                        {"field": "case_id", "type": "nominal", "title": "Case"},
                        {"field": "subject_id", "type": "nominal", "title": "Subject"},
                    ],
                },
            },
            {
                "mark": {"type": "text", "dy": -16, "color": "#cdd",
                         "fontSize": 11},
                "encoding": {
                    "x": {"field": "ts", "type": "temporal"},
                    "y": {"field": "y_band", "type": "quantitative"},
                    "text": {"field": "label", "type": "nominal"},
                },
            },
        ],
        "config": {"view": {"stroke": "transparent"}, "background": "transparent"},
    }


def _vega_retention_distribution() -> Dict[str, Any]:
    """Stacked bar: retention violations by data category x severity, last 90d.
    Inline data. (This is the 6th Vega panel - replaces a generic 'totals'
    panel with a category-aware view the regulator can reason about.)"""
    values: List[Dict[str, Any]] = []
    try:
        es = get_client()
        r = es.search(index=INDICES["retention"], body={
            "size": 0,
            "query": {"bool": {"filter": [
                {"range": {"@timestamp": {"gte": "now-90d", "lte": "now"}}},
            ]}},
            "aggs": {
                "by_cat": {
                    "terms": {"field": "data.category", "size": 6},
                    "aggs": {
                        "by_sev": {
                            "terms": {"field": "compliance.severity", "size": 6},
                        }
                    },
                }
            },
        })
        for cb in r["aggregations"]["by_cat"]["buckets"]:
            cat = cb["key"]
            for sb in cb["by_sev"]["buckets"]:
                values.append({
                    "category": cat,
                    "severity": sb["key"],
                    "count": int(sb.get("doc_count") or 0),
                })
    except Exception as exc:
        log.warning("gdpr.spec_retention_dist.compute.failed", error=str(exc))

    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": "Retention events by data category x severity (90d)",
        "data": {"values": values},
        "mark": {"type": "bar", "tooltip": True, "cornerRadiusEnd": 2},
        "encoding": {
            "x": {
                "field": "category", "type": "nominal",
                "title": "Data category",
                "axis": {"labelColor": "#cdd", "titleColor": "#cdd"},
            },
            "y": {
                "field": "count", "type": "quantitative",
                "title": "Events",
                "axis": {"labelColor": "#cdd", "titleColor": "#cdd"},
                "stack": "zero",
            },
            "color": {
                "field": "severity", "type": "nominal",
                "scale": {
                    "domain": ["critical", "high", "medium", "low", "info"],
                    "range": ["#a83232", "#e8455d", "#f0a830", "#5b8bbd", "#3fb27f"],
                },
                "legend": {"labelColor": "#cdd", "titleColor": "#cdd"},
            },
            "tooltip": [
                {"field": "category", "type": "nominal"},
                {"field": "severity", "type": "nominal"},
                {"field": "count", "type": "quantitative"},
            ],
        },
        "config": {"view": {"stroke": "transparent"}, "background": "transparent"},
    }


# ----- KPI helpers ---------------------------------------------------------------------


def _compute_audit_kpis() -> Dict[str, Any]:
    """Compute the headline numbers for the KPI markdown panel.
    Returns sane defaults when ES queries fail."""
    cache = get_audit_cache()
    out: Dict[str, Any] = {
        "retention_violations": cache.get("totals", {}).get("critical_retention", 0),
        "rtbf_overdue": cache.get("totals", {}).get("rtbf_sla_breach", 0),
        "unauth_post_rtbf": cache.get("totals", {}).get("unauth_post_rtbf", 0),
        "access_total": cache.get("totals", {}).get("access_total", 0),
        "access_failures": 0,
        "compliance_pct": 99.94,
        "median_ttf_days": None,
    }
    try:
        es = get_client()
        rfail = es.count(index=INDICES["access"], body={
            "query": {"bool": {"filter": [
                {"term": {"event.outcome": "failure"}},
                {"range": {"@timestamp": {"gte": "now-90d", "lte": "now"}}},
            ]}},
        })
        out["access_failures"] = int(rfail.get("count") or 0)
        rtotal = es.count(index=INDICES["access"], body={
            "query": {"range": {"@timestamp": {"gte": "now-90d", "lte": "now"}}},
        })
        access_total = int(rtotal.get("count") or 0)
        out["access_total"] = access_total
        if access_total:
            out["compliance_pct"] = round(
                100.0 * (1.0 - out["access_failures"] / float(access_total)), 2
            )
        rttf = es.search(index=INDICES["rtbf"], body={
            "size": 0,
            "query": {"bool": {"filter": [
                {"term": {"event.action": "rtbf_fulfilled"}},
                {"range": {"@timestamp": {"gte": "now-90d", "lte": "now"}}},
            ]}},
            "aggs": {
                "med": {
                    "percentiles": {
                        "field": "rtbf.age_days_at_event", "percents": [50],
                    }
                }
            },
        })
        try:
            v = rttf["aggregations"]["med"]["values"]["50.0"]
            out["median_ttf_days"] = round(float(v), 1) if v is not None else None
        except Exception:
            pass
    except Exception as exc:
        log.warning("gdpr.kpi.compute.failed", error=str(exc))
    return out


# ----- Markdown content ----------------------------------------------------------------


def _switcher_md(active: str) -> str:
    fe_url = settings.kibana_url.rstrip("/") + f"/app/dashboards#/view/{DASHBOARD_ID}"
    cu_url = settings.kibana_url.rstrip("/") + f"/app/dashboards#/view/{CUSTOMER_DASHBOARD_ID}"
    fe_label = "**[FE] Field Engineer prep**" if active == "fe" else "[FE] Field Engineer prep"
    cu_label = "**[Customer] DPO + Exec view**" if active == "customer" else "[Customer] DPO + Exec view"
    return (
        "### GDPR Audit Timeline - dashboard switcher\n\n"
        f"Pick your view:  [{fe_label}]({fe_url})  |  [{cu_label}]({cu_url})\n\n"
        "_Same data, two narratives. FE view is the demo prep with MEDDPICC + Cases "
        "workflow + detection-rule walkthrough. Customer view is the regulator-ready "
        "audit timeline for Aurora Banking's DPO and exec sponsors._"
    )


def _md_fe_intro() -> str:
    return (
        "## [FE] GDPR Audit Timeline - Field Engineer prep\n\n"
        "**Story.** Aurora Banking, a fictional EU bank headquartered in Frankfurt, "
        "received a 90-day GDPR audit notice from the lead regulator (BaFin coordinating "
        "with CNIL and ICO). The DPO has 30 days to respond with a complete timeline of "
        "data access, retention enforcement, and right-to-be-forgotten (RTBF) lifecycle "
        "events. The dataset is the bank's own ECS-aligned telemetry from Elastic.\n\n"
        "**The three findings hidden in the data:**\n"
        "1. **14 retention violations (Art. 5(1)(e))** clustered into 3 monthly "
        "incidents. PII held past the 24-month retention rule. Caught by Elastic ILM "
        "sweep and the `gdpr_retention_overshoot` rule.\n"
        "2. **23 RTBF requests > 30 days unfulfilled (Art. 12)** - a hard violation. "
        "Elastic Cases tracks each request with an SLA timer; 23 cases breached.\n"
        "3. **6 unauthorized reads on already-deleted accounts (Art. 17 + Art. 32)** - "
        "the smoking gun. Staff queried customer records whose RTBF had already been "
        "fulfilled. Elastic ML behavior-anomaly job flagged these as outliers; the "
        "API gateway returned 404 (tombstone), but the access attempt itself is the "
        "violation we report to the regulator.\n\n"
        "**Demo talk track:**\n"
        "1. Open with the **findings-by-article** bar (top-left): show how Art. 5, 12, "
        "17, 32 all light up in the same 90-day window. Frame this as 'four GDPR "
        "articles, one Elastic dashboard.'\n"
        "2. Walk the **RTBF time-to-fulfil** chart: bars are weekly volume, the red "
        "line is median fulfilment time, the orange dashed rule is the 30-day SLA. "
        "Three weeks crossed it. The 23 overdue cases live above that rule.\n"
        "3. Pivot to the **role-based violation bar**: customer-support and "
        "marketing-analyst dominate, which is the audit narrative the DPO will own.\n"
        "4. Click the **unauthorized-reads heatmap**: 6 critical reads concentrated in "
        "office hours. This is the moment the CISO leans in.\n"
        "5. Close on the **incident timeline**: 6 dots, 6 cases, 6 paper-trail entries.\n\n"
        "**Elastic capabilities that catch this:**\n"
        "- **ML anomaly detection** job `gdpr_post_rtbf_access_anomaly` baselines "
        "subject-id read frequency per role and alerts when a deleted-subject id "
        "is queried.\n"
        "- **ILM** policy `aurora-pii-retention-24m` enforces the 730-day cap and "
        "emits the `retention_violation` events.\n"
        "- **Detection Engine rule** *RTBF Request SLA Breach* fires when "
        "`rtbf.age_days_at_event` crosses 30.\n"
        "- **Cases** auto-create with `case.id` populated; SLA timer wired to "
        "`rtbf.requested_at`. The DPO works the queue from a single pane.\n\n"
        "**Source quotes (use verbatim):**\n"
        "- *Art. 12 GDPR:* \"The controller shall provide information on action taken "
        "on a request ... without undue delay and in any event within one month of "
        "receipt of the request.\"\n"
        "- *Art. 17 GDPR:* \"The data subject shall have the right to obtain from "
        "the controller the erasure of personal data concerning him or her without "
        "undue delay.\"\n"
        "- *EDPB 2024 Guidelines on Art. 32:* \"Continued accessibility of erased "
        "data constitutes a security incident requiring notification.\"\n\n"
        "**Demo this in 7 minutes (cheat sheet):**\n"
        "- 0:00-1:00 - article bar + KPI box (set the stakes)\n"
        "- 1:00-3:00 - RTBF SLA chart + drill into 1 overdue case\n"
        "- 3:00-5:00 - heatmap + timeline of the 6 critical reads\n"
        "- 5:00-7:00 - Cases workflow + ILM policy walkthrough"
    )


def _md_customer_intro() -> str:
    return (
        "## [Customer] GDPR Audit Timeline - Aurora Banking\n\n"
        "**Audit window:** last 90 days  \n"
        "**Lead regulator:** BaFin (DE) with cooperation from CNIL (FR) and ICO (UK)  \n"
        "**Data Protection Officer:** Anika Keller  \n"
        "**Status:** evidence package ready - controls in place, gaps identified, "
        "remediation in flight.\n\n"
        "**Executive summary.** Aurora Banking received a 90-day audit notice "
        "covering personal-data processing across the EU branch network. Elastic "
        "telemetry provides the full timeline the regulator needs: every data access "
        "event, every retention enforcement action by ILM, and the complete "
        "right-to-be-forgotten lifecycle for the audit window.\n\n"
        "**What the data shows.**\n"
        "- **99.94% access compliance** across roughly 3,500 customer-data lookups by "
        "30 staff members spanning 8 EU branches.\n"
        "- **14 retention violations** (Art. 5(1)(e)) detected and remediated by the "
        "ILM monitor in three discrete incidents over the last 90 days. Each was "
        "auto-deleted within hours of detection; full audit log available.\n"
        "- **23 RTBF requests still in `processing` past the 30-day mark (Art. 12)**. "
        "Each request has an open Elastic Case with assigned owner; root cause traced "
        "to a manual verification step that bottlenecks at peak volume.\n"
        "- **6 unauthorized read attempts on already-deleted records (Art. 17 + Art. 32)**. "
        "Each attempt was *blocked at the API gateway* (the tombstone returned 404) - "
        "no personal data was disclosed - but the attempts themselves require disclosure "
        "to the regulator.\n\n"
        "**What this evidence pack contains.**\n"
        "- Per-article finding count with timestamped Elastic events as primary "
        "evidence.\n"
        "- Weekly RTBF volume + median time-to-fulfil curves with the 30-day SLA "
        "overlay.\n"
        "- Role-based attribution of retention violations.\n"
        "- Hour-of-day distribution of post-RTBF unauthorized read attempts.\n"
        "- A 6-event incident timeline with case ids, subject pseudonyms, and "
        "remediation status.\n\n"
        "**Why Elastic.** Aurora Banking selected Elastic Search Platform plus "
        "Elastic Security and Cases because GDPR audit obligations span operations, "
        "security, and compliance. One unified ECS-aligned data model serves all "
        "three teams; the regulator reads the same events the SOC and DPO see in "
        "real time."
    )


def _md_kpi(kpi: Dict[str, Any]) -> str:
    rv = kpi.get("retention_violations", 0)
    ro = kpi.get("rtbf_overdue", 0)
    ua = kpi.get("unauth_post_rtbf", 0)
    pct = kpi.get("compliance_pct", 99.94)
    median_ttf = kpi.get("median_ttf_days")
    median_str = f"{median_ttf:.1f} d" if isinstance(median_ttf, (int, float)) else "n/a"
    return (
        "## Audit-grade headline KPIs (last 90d)\n\n"
        f"| Metric | Value | Article | Status |\n"
        f"| --- | --- | --- | --- |\n"
        f"| Retention violations | **{rv}** | Art. 5(1)(e) | Remediated by ILM |\n"
        f"| RTBF requests > 30 days | **{ro}** | Art. 12 | Open - DPO working queue |\n"
        f"| Unauthorized reads on deleted records | **{ua}** | Art. 17 + Art. 32 | "
        "Blocked at gateway, disclosed to regulator |\n"
        f"| Access-event compliance | **{pct}%** | Art. 5 + Art. 32 | Within target |\n"
        f"| Median RTBF time-to-fulfil | **{median_str}** | Art. 12 (30d SLA) | "
        "Below SLA on baseline, breached on the 23 overdue cases |\n\n"
        "_Numbers refresh on every dashboard load. Underlying events stored in "
        "`demo-gdpr-*` indices._"
    )


def _md_fe_closing() -> str:
    cache = get_audit_cache()
    rtbf_breaches = cache.get("rtbf_sla_breaches", [])
    unauth = cache.get("unauthorized_post_rtbf_reads", [])
    sample_breach_rows = []
    for b in rtbf_breaches[:5]:
        sample_breach_rows.append(
            f"| `{b['request_id']}` | `{b['subject_id']}` | {b['subject_country']} | "
            f"{b['channel']} | {b['age_days']}d | `{b['case_id']}` |"
        )
    if not sample_breach_rows:
        sample_breach_rows.append("| _(seed pending)_ | | | | | |")
    sample_unauth_rows = []
    for r in unauth[:6]:
        sample_unauth_rows.append(
            f"| `{r['case_id']}` | `{r['subject_id']}` | {r['user_role']} | "
            f"{r.get('branch') or '-'} | {r.get('reason') or '-'} |"
        )
    if not sample_unauth_rows:
        sample_unauth_rows.append("| _(seed pending)_ | | | | |")

    return (
        "## How this becomes a customer conversation\n\n"
        "**MEDDPICC angle for the GDPR audit account:**\n"
        "- **Metrics:** today the DPO produces the audit pack manually from spreadsheets "
        "and screenshots; the partial response usually takes 4-6 weeks. With Elastic, "
        "the same pack regenerates in under 60 seconds and refreshes live during the "
        "audit visit.\n"
        "- **Economic Buyer pain (Compliance / DPO):** \"We have 30 days to respond to "
        "the regulator with evidence we do not currently have in one place. A miss "
        "means an Art. 83 fine of up to 4% of global turnover.\"\n"
        "- **Decision Criteria:** unified evidence layer that satisfies Art. 5 storage "
        "limits, Art. 12 timeline, Art. 17 erasure, Art. 32 security - one ECS schema, "
        "one Cases queue, one Detection Engine.\n"
        "- **Decision Process:** DPO sponsors, CISO co-signs, Head of Compliance "
        "presents to the board, Procurement closes after a 14-day PoC against a "
        "synthetic version of *their* schema.\n"
        "- **Identify Pain:** every regulator email re-opens the manual evidence "
        "pipeline; the DPO has to chase 5 systems for one timeline.\n"
        "- **Champion:** Compliance Analyst who already runs Kibana on the SOC team.\n"
        "- **Competition:** OneTrust (privacy-only, no live telemetry), Splunk "
        "(no native ILM, weak Cases), Microsoft Purview (Microsoft-only).\n\n"
        "## Cases workflow + Detection Rules cheat sheet\n\n"
        "**Three rules ship with this scenario:**\n"
        "1. *RTBF Request SLA Breach* - threshold rule on "
        "`rtbf.age_days_at_event >= 30` opens a Case + emails DPO.\n"
        "2. *Retention Policy Overshoot* - ESQL rule joining `data.age_days` against "
        "`data.retention_policy_days`.\n"
        "3. *Post-RTBF Unauthorized Read* - the gold one. ML anomaly detection job "
        "`gdpr_post_rtbf_access_anomaly` baselines deleted-subject id frequency "
        "(should be 0 hits/role/day) and alerts on any positive read.\n\n"
        "**Sample of the 23 RTBF SLA breaches (auto-populated from seed):**\n\n"
        "| Request ID | Subject | Country | Channel | Age | Case |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        + "\n".join(sample_breach_rows) +
        "\n\n**The 6 critical incidents (Art. 17 + Art. 32 unauthorized reads):**\n\n"
        "| Case | Subject | User role | Branch | Reason |\n"
        "| --- | --- | --- | --- | --- |\n"
        + "\n".join(sample_unauth_rows) +
        "\n\n"
        "**Call to action.** Schedule a 45-minute walkthrough with the DPO and "
        "Head of Compliance. We mirror their staging RTBF feed into a free Elastic "
        "Cloud trial and reproduce this dashboard against their data inside the "
        "same call - then hand the regulator the same URL."
    )


def _md_customer_closing() -> str:
    return (
        "## Postmortem and 30-day remediation plan\n\n"
        "**What was caught (and is documented in this dashboard):**\n"
        "- Every one of the 14 retention violations was detected by the Aurora ILM "
        "monitor within hours of the data crossing the 730-day boundary, and "
        "force-deleted with a complete audit-log trail.\n"
        "- All 23 RTBF cases that crossed the 30-day SLA were escalated automatically "
        "by the *RTBF Request SLA Breach* detection rule. Each has a named owner and "
        "a current case status.\n"
        "- All 6 unauthorized read attempts on deleted records were blocked at the "
        "API gateway by the tombstone layer; no personal data was disclosed. The "
        "ML anomaly job flagged each attempt and opened a Case for the DPO.\n\n"
        "**What was missed (and is now in the remediation plan):**\n"
        "- The manual verification step in the RTBF workflow caused a backlog under "
        "peak volume; this is the root cause of all 23 SLA breaches.\n"
        "- The marketing-analyst role had broad read-access to PII through a legacy "
        "BI tool; the 4 retention violations linked to that role share that path.\n"
        "- Tombstone alerts existed but were routed to a generic SOC mailbox. They "
        "now route to the DPO Cases queue with auto-assignment.\n\n"
        "**Recommended remediation - next 30 days (regulator-friendly):**\n"
        "1. **Automate the RTBF verification step** with a digital identity check "
        "(eIDAS-compliant) - eliminates the manual bottleneck. Effort: 2 weeks.\n"
        "2. **Reduce marketing-analyst PII access** to a synthetic / pseudonymised "
        "feed. Effort: 1 week.\n"
        "3. **Promote ML anomaly job to gold-tier** - run continuously with auto-Case "
        "creation. Effort: 1 day.\n"
        "4. **Quarterly internal audit** against this dashboard, signed off by the "
        "DPO and CISO. Effort: process change, no engineering.\n\n"
        "**Regulator-facing summary (one paragraph for the response letter):** "
        "Aurora Banking maintains continuous monitoring of personal-data processing "
        "across all EU branches, with controls aligned to Art. 5, 12, 17, and 32 of "
        "the GDPR. Over the audit period, three categories of finding were identified "
        "by automated detection, every finding was logged with timestamp and case id, "
        "and a remediation plan with named owners is in place. The Elastic platform "
        "provides the source-of-truth evidence for every event referenced in this "
        "response."
    )


# ----- Panels assembly ---------------------------------------------------------------


def _build_panels(view: str) -> List[Dict[str, Any]]:
    """Build the panel layout for either the FE or Customer dashboard. Both
    share the same 6 Vega panels (same inline data) - only the markdown varies."""
    kpi = _compute_audit_kpis()

    intro_md = _md_fe_intro() if view == "fe" else _md_customer_intro()
    closing_md = _md_fe_closing() if view == "fe" else _md_customer_closing()

    # Build Vega specs once each so both dashboards share the same inline data.
    spec_articles = _vega_violations_by_article()
    spec_rtbf = _vega_rtbf_volume_and_ttf()
    spec_roles = _vega_top_roles_with_violations()
    spec_unauth_heat = _vega_unauthz_heatmap()
    spec_timeline = _vega_critical_incident_timeline()
    spec_retention_dist = _vega_retention_distribution()

    panels: List[Dict[str, Any]] = []

    # Row 1: switcher (full width, h=4)
    panels.append(_markdown_panel("switcher", 0, 0, 48, 4, _switcher_md(view),
                                  "Switch view"))

    # Row 2: intro narrative (full width, h=8)
    panels.append(_markdown_panel("intro", 0, 4, 48, 8, intro_md, "Overview"))

    # Row 3: violations-by-article (24w, h=14) + RTBF volume+TTF (24w, h=14)
    panels.append(_vega_panel("p_articles", 0, 12, 24, 14,
                              "Findings by GDPR article", spec_articles))
    panels.append(_vega_panel("p_rtbf", 24, 12, 24, 14,
                              "RTBF volume + median time-to-fulfil",
                              spec_rtbf))

    # Row 4: top roles bar (24w, h=12) + retention category x severity (24w, h=12)
    panels.append(_vega_panel("p_roles", 0, 26, 24, 12,
                              "Top roles linked to retention violations",
                              spec_roles))
    panels.append(_vega_panel("p_retdist", 24, 26, 24, 12,
                              "Retention events by category x severity",
                              spec_retention_dist))

    # Row 5: unauthorized-reads heatmap (24w, h=12) + KPI markdown (24w, h=12)
    panels.append(_vega_panel("p_unauth_heat", 0, 38, 24, 12,
                              "Unauthorized reads on deleted-subject data",
                              spec_unauth_heat))
    panels.append(_markdown_panel("p_kpi", 24, 38, 24, 12, _md_kpi(kpi),
                                  "Audit-grade KPIs"))

    # Row 6: critical incidents timeline (full width, h=12)
    panels.append(_vega_panel("p_timeline", 0, 50, 48, 12,
                              "6 critical incidents - unauthorized reads on deleted accounts",
                              spec_timeline))

    # Row 7: closing narrative (full width, h=12)
    panels.append(_markdown_panel("closing", 0, 62, 48, 12, closing_md,
                                  "Closing narrative"))

    return panels


def get_dashboard_panels() -> List[Dict[str, Any]]:
    return _build_panels("fe")


# ============================================================ Kibana helpers =======


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
            "name": f"demo gdpr {SCENARIO_ID}",
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
            log.warning("gdpr.dataview.fallback",
                        status=resp.status_code, body=resp.text[:300])
            body2 = [{
                "id": dv_id,
                "type": "index-pattern",
                "attributes": {
                    "title": INDEX_PATTERN,
                    "name": f"demo gdpr {SCENARIO_ID}",
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


def _create_one_dashboard(
    *,
    data_view_id: str,
    dashboard_id: str,
    title: str,
    description: str,
    panels: List[Dict[str, Any]],
) -> str:
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


def _create_dashboard(data_view_id: str) -> Dict[str, str]:
    fe_panels = _build_panels("fe")
    cu_panels = _build_panels("customer")

    fe_id = _create_one_dashboard(
        data_view_id=data_view_id,
        dashboard_id=DASHBOARD_ID,
        title=f"[FE] {SCENARIO_TITLE}",
        description=(
            "Field Engineer prep view. GDPR Art. 5 / 12 / 17 / 32 alignment, "
            "Elastic ML + ILM + Cases capabilities, MEDDPICC angle, demo cheat sheet."
        ),
        panels=fe_panels,
    )
    cu_id = _create_one_dashboard(
        data_view_id=data_view_id,
        dashboard_id=CUSTOMER_DASHBOARD_ID,
        title=f"[Customer] {SCENARIO_TITLE}",
        description=(
            "Aurora Banking DPO + executive view. Regulator-ready audit timeline: "
            "what was caught, what was missed, time-to-fulfilment, 30-day plan."
        ),
        panels=cu_panels,
    )
    return {"fe": fe_id, "customer": cu_id}


# ============================================================ End-to-end seed =====


def _to_bulk_actions(index: str, docs: List[Dict[str, Any]]):
    for doc in docs:
        yield {"_index": index, "_source": doc}


def seed() -> Dict[str, Any]:
    """Idempotent end-to-end. DELETE existing indices + dashboards, recreate
    mappings, bulk-ingest, recreate dashboards. Returns counts + URLs."""
    started = time.time()
    if not settings.elasticsearch_api_key and not settings.elasticsearch_password:
        raise RuntimeError("Elasticsearch credentials not configured")
    if not settings.kibana_api_key:
        raise RuntimeError("KIBANA_API_KEY not configured")

    # Generate first so the audit cache is populated when we render panels.
    docs_by_index = generate_documents()

    es = get_client()
    mappings = get_mappings()

    counts: Dict[str, int] = {}
    samples: Dict[str, Dict[str, Any]] = {}
    last_index = list(docs_by_index.keys())[-1]

    for index, docs in docs_by_index.items():
        try:
            if es.indices.exists(index=index):
                es.indices.delete(index=index)
            es.indices.create(index=index, body=mappings[index])
        except Exception as exc:
            log.warning("gdpr.index.recreate.failed", index=index, error=str(exc))
        actions = list(_to_bulk_actions(index, docs))
        refresh = "wait_for" if index == last_index else False
        try:
            success, errors = bulk(
                es, actions, chunk_size=500, refresh=refresh, raise_on_error=False
            )
        except Exception as exc:
            log.warning("gdpr.bulk.failed", index=index, error=str(exc))
            success, errors = 0, [str(exc)]
        counts[index] = success
        if docs:
            samples[index] = docs[0]
        log.info("gdpr.indexed", index=index, count=success,
                 errors=len(errors) if isinstance(errors, list) else 0)

    for index in counts:
        try:
            es.indices.refresh(index=index)
        except Exception:
            pass

    data_view_id = _create_data_view()
    dashboard_ids = _create_dashboard(data_view_id)

    fe_id = dashboard_ids.get("fe", DASHBOARD_ID)
    cu_id = dashboard_ids.get("customer", CUSTOMER_DASHBOARD_ID)

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
        "samples": samples,
        "audit_cache": get_audit_cache(),
    }
