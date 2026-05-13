"""
filename: routes_customer_health.py
description: CA-first Customer Health endpoints. Aggregates signals across AutoOps,
POV Health, renewal signals, ticket trend, and last-contact into a single per-customer
view. Synthesises an adoption trajectory (90-day usage + feature recency) deterministically
from the seed data so the demo is stable. Emits proactive task suggestions from rule-based
detectors built on top of the existing repositories.
date: 05-13-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.repositories import synthetic
from app.utils.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/customer-health", tags=["customer-health"])

_SEED_DIR = Path(__file__).parent.parent.parent / "data" / "seed"


# ============================================================ Data sources

def _load_renewal_signals() -> List[Dict[str, Any]]:
    path = _SEED_DIR / "renewal_signals.json"
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def _signals_for(company_id: str, company_name: str) -> List[Dict[str, Any]]:
    """Match renewal signals to a company. The signals file uses hyphenated
    account ids ('northwind-pay') while synthetic uses bare ids ('northwind');
    fall back to a fuzzy name match so both shapes resolve."""
    name_lower = (company_name or "").lower()
    matches = []
    for sig in _load_renewal_signals():
        acc_id = sig.get("account_id", "").lower()
        acc_name = sig.get("account_name", "").lower()
        if company_id and company_id.lower() in acc_id:
            matches.append(sig)
        elif name_lower and (name_lower in acc_name or acc_name in name_lower):
            matches.append(sig)
    return matches


def _autoops_summary() -> Dict[str, Any]:
    """Best-effort AutoOps cluster snapshot. The autoops router serves the same
    data; we read the file directly to avoid an internal HTTP call."""
    candidates = [
        settings.runtime_dir / "autoops" / "events.json",
        Path(__file__).parent.parent.parent / "data" / "autoops_events.json",
    ]
    for p in candidates:
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
                if isinstance(data, list):
                    return {"events": data}
            except Exception:
                pass
    return {"events": []}


def _pov_health_for(company_id: str) -> Optional[Dict[str, Any]]:
    """If a POV Health report exists on disk for this company, surface its
    stage. Otherwise return None."""
    pov_dir = settings.runtime_dir / "pov_health"
    if not pov_dir.exists():
        return None
    for path in pov_dir.glob("*.json"):
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        cid = (d.get("company_id") or "").lower()
        cname = (d.get("company_name") or "").lower()
        if cid == company_id.lower() or company_id.lower() in cname:
            return {
                "stage_assessment": d.get("stage_assessment"),
                "confidence_score": d.get("confidence_score"),
                "days_to_decision_estimate": d.get("days_to_decision_estimate"),
            }
    return None


def _last_contact(company_id: str) -> Optional[Dict[str, Any]]:
    """Return the most recent meeting (past or upcoming) for the company.
    Falls back to None when synthetic data has no record."""
    relevant = [m for m in synthetic.meetings() if m.get("company_id") == company_id]
    if not relevant:
        return None
    def _ts(m):
        try:
            return datetime.fromisoformat(m.get("start_time", "").replace("Z", "+00:00"))
        except Exception:
            return datetime.min.replace(tzinfo=timezone.utc)
    relevant.sort(key=_ts, reverse=True)
    m = relevant[0]
    start = _ts(m)
    delta_days = (datetime.now(timezone.utc) - start).days
    return {
        "meeting_id": m.get("id") or m.get("meeting_id"),
        "title": m.get("title"),
        "date_iso": m.get("start_time"),
        "days_ago": delta_days,
        "is_future": delta_days < 0,
    }


# ============================================================ Adoption synthesis

def _seeded_int(seed: str, mod: int) -> int:
    """Stable pseudo-random int from a string seed so the demo is reproducible."""
    h = hashlib.sha1(seed.encode("utf-8")).hexdigest()
    return int(h[:8], 16) % mod


def _adoption_for(company_id: str, company: Dict[str, Any]) -> Dict[str, Any]:
    """Synthesise a 13-week (90-day) GB/day ingest trend + feature-recency chips.

    Deterministic from `company_id` so the same customer always shows the same
    trajectory across demo reloads. Trend direction is keyed off the dossier:
    customers flagged with usage_drop in renewal signals get a flat or
    declining line, others trend up.
    """
    signals = _signals_for(company_id, company.get("name", ""))
    has_drop = any(s.get("signal_type") == "usage_drop" for s in signals)
    has_growth = any(s.get("signal_type") in ("expansion", "new_workload") for s in signals)

    baseline = 150 + _seeded_int(company_id + ":baseline", 600)  # 150-750 GB/day starting point
    if has_drop:
        slope_pct = -0.04 - (_seeded_int(company_id + ":slope_d", 5) / 100.0)  # -4% to -9% / week
    elif has_growth:
        slope_pct = 0.04 + (_seeded_int(company_id + ":slope_g", 8) / 100.0)  # 4% to 12% / week
    else:
        slope_pct = (_seeded_int(company_id + ":slope_n", 6) - 3) / 100.0  # -3% to +3% / week

    series = []
    now = datetime.now(timezone.utc)
    val = float(baseline)
    for week in range(12, -1, -1):
        d = now - timedelta(days=week * 7)
        # Add a little weekly noise so the line is not a pure ramp.
        noise = (_seeded_int(company_id + f":w{week}", 11) - 5) / 100.0
        val_w = max(20.0, val * (1.0 + noise))
        series.append({"week": d.date().isoformat(), "value": round(val_w, 1)})
        val *= (1.0 + slope_pct)
    first, last = series[0]["value"], series[-1]["value"]
    trend_pct = round(((last - first) / first) * 100.0, 1) if first else 0.0

    # Feature usage: pick from a known catalogue, seed which are stale.
    catalogue = [
        ("ML jobs (anomaly detection)", "ml_jobs"),
        ("Cross-cluster search", "ccs"),
        ("ELSER semantic search", "elser"),
        ("Frozen tier (object storage)", "frozen"),
        ("APM service maps", "apm"),
        ("Security detection rules", "security"),
        ("Snapshot lifecycle (SLM)", "slm"),
        ("Index lifecycle (ILM)", "ilm"),
    ]
    features = []
    for label, key in catalogue:
        last_used = _seeded_int(company_id + ":" + key, 240)  # 0-240 days
        if last_used <= 14:
            status = "active"
        elif last_used <= 60:
            status = "warm"
        elif last_used <= 120:
            status = "cooling"
        else:
            status = "stale"
        features.append({"feature": label, "last_used_days": last_used, "status": status})

    return {
        "ingest_gb_day": {"series": series, "trend_pct": trend_pct},
        "feature_usage": features,
    }


# ============================================================ Proactive rules

def _proactive_tasks(
    company: Dict[str, Any],
    last_contact: Optional[Dict[str, Any]],
    signals: List[Dict[str, Any]],
    open_tickets: List[Dict[str, Any]],
    adoption: Dict[str, Any],
    autoops: Dict[str, Any],
    pov_health: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Deterministic rule pack. Each rule emits at most one task. The FE can
    extend this with their own rules without touching agent prompts."""
    tasks: List[Dict[str, Any]] = []
    cid = company.get("id", "")
    cname = company.get("name", cid)

    # Rule: no contact in 60+ days.
    if last_contact is not None and last_contact.get("days_ago", 0) >= 60 and not last_contact.get("is_future"):
        days = last_contact["days_ago"]
        tasks.append({
            "id": f"{cid}-no-contact",
            "title": f"Schedule a check-in with {cname}",
            "rationale": f"Last contact was {days} days ago ('{last_contact.get('title')}'). Re-engage before they go cold.",
            "trigger": ["no_recent_contact"],
            "severity": "medium" if days < 120 else "high",
            "suggested_owner": "CA",
            "suggested_action": "calendar_invite",
        })

    # Rule: renewal within 120 days + any open signal.
    soonest = None
    arr = None
    for s in signals:
        d = s.get("renewal_date")
        if not d:
            continue
        try:
            rd = datetime.fromisoformat(d).replace(tzinfo=timezone.utc) if "T" not in d else datetime.fromisoformat(d)
        except Exception:
            continue
        days_out = (rd - datetime.now(timezone.utc).replace(tzinfo=timezone.utc)).days
        if soonest is None or days_out < soonest:
            soonest = days_out
            arr = s.get("arr_usd")
    if soonest is not None and 0 < soonest <= 120:
        tasks.append({
            "id": f"{cid}-renewal-window",
            "title": f"Lock renewal motion for {cname}",
            "rationale": f"Renewal lands in {soonest} days at ${(arr or 0):,} ARR. Surface MEDDPICC champions + open signals on the next call.",
            "trigger": ["renewal_proximity"],
            "severity": "high" if soonest <= 60 else "medium",
            "suggested_owner": "AE+CA",
            "suggested_action": "renewal_plan",
        })

    # Rule: any usage_drop signal.
    drop = next((s for s in signals if s.get("signal_type") == "usage_drop"), None)
    if drop:
        tasks.append({
            "id": f"{cid}-usage-drop",
            "title": f"Investigate usage drop at {cname}",
            "rationale": drop.get("summary") or "Query volume trending down vs baseline.",
            "trigger": ["usage_drop"],
            "severity": drop.get("severity") or "medium",
            "suggested_owner": "CA",
            "suggested_action": "technical_review",
            "evidence": drop.get("evidence"),
        })

    # Rule: open P1 ticket.
    p1 = [t for t in open_tickets if (t.get("priority") or "").lower() in ("p1", "high", "urgent")]
    if p1:
        t = p1[0]
        tasks.append({
            "id": f"{cid}-p1-ticket",
            "title": f"Resolve P1 with {cname}",
            "rationale": f"{t.get('subject') or 'Open P1 ticket'}. Reactive distraction; clear before next strategic call.",
            "trigger": ["open_p1_ticket"],
            "severity": "high",
            "suggested_owner": "CA",
            "suggested_action": "escalate_support",
        })

    # Rule: ingest growth > +40%.
    trend = (adoption.get("ingest_gb_day") or {}).get("trend_pct", 0)
    if trend >= 40:
        tasks.append({
            "id": f"{cid}-expansion",
            "title": f"Position expansion at {cname}",
            "rationale": f"Ingest grew {trend:.0f}% in the last 90 days. Likely they're ready for the next workload or tier upgrade.",
            "trigger": ["growth_signal"],
            "severity": "medium",
            "suggested_owner": "AE+CA",
            "suggested_action": "expansion_pitch",
        })

    # Rule: AutoOps yellow/red status.
    aut = autoops or {}
    alerts = aut.get("events") or aut.get("alerts") or []
    high_alerts = [a for a in alerts if (a.get("severity") or "").lower() in ("warning", "critical", "high")]
    if len(high_alerts) >= 2:
        tasks.append({
            "id": f"{cid}-autoops",
            "title": f"Review AutoOps alerts before next {cname} call",
            "rationale": f"{len(high_alerts)} active AutoOps warnings on the demo cluster. Walk the customer through the diagnosis before they ask.",
            "trigger": ["autoops_degraded"],
            "severity": "medium",
            "suggested_owner": "CA",
            "suggested_action": "technical_review",
        })

    # Rule: POV at_risk or stalled.
    if pov_health and (pov_health.get("stage_assessment") in ("at_risk", "stalled")):
        tasks.append({
            "id": f"{cid}-pov-risk",
            "title": f"POV at-risk: rescue {cname}",
            "rationale": f"POV stage = {pov_health.get('stage_assessment')}, confidence {pov_health.get('confidence_score')}. Days to decision: {pov_health.get('days_to_decision_estimate')}.",
            "trigger": ["pov_risk"],
            "severity": "high" if pov_health.get("stage_assessment") == "stalled" else "medium",
            "suggested_owner": "FE+CSM",
            "suggested_action": "pov_intervention",
        })

    # Rule: stale ML / Security feature - expansion lever.
    features = adoption.get("feature_usage") or []
    stale_ml = next((f for f in features if "ML" in f["feature"] and f["status"] == "stale"), None)
    if stale_ml and not drop:
        tasks.append({
            "id": f"{cid}-stale-ml",
            "title": f"Re-engage on ML at {cname}",
            "rationale": f"{stale_ml['feature']} not used in {stale_ml['last_used_days']} days. Drop a use-case in the next QBR.",
            "trigger": ["stale_feature"],
            "severity": "low",
            "suggested_owner": "CA",
            "suggested_action": "use_case_pitch",
        })

    # De-dup by id, keep highest severity first.
    seen = set()
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    tasks.sort(key=lambda t: severity_order.get(t.get("severity"), 9))
    out = []
    for t in tasks:
        if t["id"] in seen:
            continue
        seen.add(t["id"])
        out.append(t)
    return out


# ============================================================ Scoring

def _health_score(
    signals: List[Dict[str, Any]],
    last_contact: Optional[Dict[str, Any]],
    open_tickets: List[Dict[str, Any]],
    adoption: Dict[str, Any],
    pov_health: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """0-100 health score, with status bucket. Higher is healthier."""
    score = 100

    # Renewal proximity + signal severity
    for s in signals:
        sev = (s.get("severity") or "low").lower()
        if sev == "critical":
            score -= 30
        elif sev == "high":
            score -= 20
        elif sev == "medium":
            score -= 10
        else:
            score -= 5

    # Last contact recency
    if last_contact is None or last_contact.get("days_ago", 999) > 120:
        score -= 15
    elif last_contact.get("days_ago", 0) > 60:
        score -= 8

    # Open tickets
    p1 = sum(1 for t in open_tickets if (t.get("priority") or "").lower() in ("p1", "high", "urgent"))
    score -= min(20, p1 * 10)

    # Adoption trend
    trend = (adoption.get("ingest_gb_day") or {}).get("trend_pct", 0)
    if trend <= -20:
        score -= 15
    elif trend <= -5:
        score -= 5
    elif trend >= 25:
        score += 5

    # POV risk
    if pov_health:
        st = pov_health.get("stage_assessment")
        if st == "stalled":
            score -= 20
        elif st == "at_risk":
            score -= 10

    score = max(0, min(100, score))
    if score >= 80:
        status = "healthy"
    elif score >= 60:
        status = "watch"
    elif score >= 40:
        status = "at_risk"
    else:
        status = "critical"
    return {"score": score, "status": status}


# ============================================================ Endpoints

def _customer_summary(company: Dict[str, Any]) -> Dict[str, Any]:
    cid = company.get("id", "")
    cname = company.get("name", cid)
    signals = _signals_for(cid, cname)
    last_contact = _last_contact(cid)
    open_tickets = [t for t in synthetic.tickets_for(cid) if (t.get("status") or "").lower() in ("open", "in_progress", "new")]
    adoption = _adoption_for(cid, company)
    pov = _pov_health_for(cid)
    health = _health_score(signals, last_contact, open_tickets, adoption, pov)
    proactive = _proactive_tasks(company, last_contact, signals, open_tickets, adoption, _autoops_summary(), pov)

    days_to_renewal = None
    arr = None
    for s in signals:
        d = s.get("renewal_date")
        if not d:
            continue
        try:
            rd = datetime.fromisoformat(d).replace(tzinfo=timezone.utc) if "T" not in d else datetime.fromisoformat(d)
            days = (rd - datetime.now(timezone.utc).replace(tzinfo=timezone.utc)).days
            if days_to_renewal is None or days < days_to_renewal:
                days_to_renewal = days
                arr = s.get("arr_usd") or arr
        except Exception:
            continue

    headline = None
    if proactive:
        headline = proactive[0]["title"] + " - " + proactive[0]["rationale"][:120]

    return {
        "id": cid,
        "name": cname,
        "industry": company.get("industry"),
        "size": company.get("size"),
        "health_score": health["score"],
        "health_status": health["status"],
        "headline_signal": headline,
        "days_to_renewal": days_to_renewal,
        "arr_usd": arr,
        "open_tickets": len(open_tickets),
        "open_p1_tickets": sum(1 for t in open_tickets if (t.get("priority") or "").lower() in ("p1", "high", "urgent")),
        "last_contact_days": (last_contact or {}).get("days_ago"),
        "adoption_trend_pct": (adoption.get("ingest_gb_day") or {}).get("trend_pct"),
        "proactive_count": len(proactive),
    }


@router.get("")
def list_customer_health() -> Dict[str, Any]:
    """List every customer with a rolled-up health summary. Sorted by health
    ascending so the most-at-risk accounts surface at the top of the CA view."""
    summaries = [_customer_summary(c) for c in synthetic.companies()]
    summaries.sort(key=lambda s: s["health_score"])
    return {"customers": summaries, "count": len(summaries)}


@router.get("/{customer_id}")
def get_customer_health(customer_id: str) -> Dict[str, Any]:
    """Full per-customer view: aggregate signals + adoption trajectory +
    proactive tasks. Powers the customer-health.html detail pane."""
    company = synthetic.find_company(customer_id)
    if not company:
        raise HTTPException(status_code=404, detail=f"customer {customer_id} not found")

    cid = company["id"]
    cname = company.get("name", cid)
    signals = _signals_for(cid, cname)
    last_contact = _last_contact(cid)
    open_tickets = [t for t in synthetic.tickets_for(cid) if (t.get("status") or "").lower() in ("open", "in_progress", "new")]
    adoption = _adoption_for(cid, company)
    pov = _pov_health_for(cid)
    autoops = _autoops_summary()
    health = _health_score(signals, last_contact, open_tickets, adoption, pov)
    proactive = _proactive_tasks(company, last_contact, signals, open_tickets, adoption, autoops, pov)

    # Ticket trend: synthetic 30-day count vs prior 30 days. Deterministic.
    open_count = len(open_tickets)
    prior_count = max(0, open_count - (_seeded_int(cid + ":tick_prior", 4) - 1))
    trend_30d = open_count - prior_count

    days_to_renewal = None
    arr = None
    renewal_date = None
    for s in signals:
        d = s.get("renewal_date")
        if not d:
            continue
        try:
            rd = datetime.fromisoformat(d).replace(tzinfo=timezone.utc) if "T" not in d else datetime.fromisoformat(d)
            days = (rd - datetime.now(timezone.utc).replace(tzinfo=timezone.utc)).days
            if days_to_renewal is None or days < days_to_renewal:
                days_to_renewal = days
                arr = s.get("arr_usd") or arr
                renewal_date = s.get("renewal_date")
        except Exception:
            continue

    autoops_alerts = autoops.get("events") or autoops.get("alerts") or []
    autoops_high = [a for a in autoops_alerts if (a.get("severity") or "").lower() in ("warning", "critical", "high")]

    return {
        "customer": {
            "id": cid,
            "name": cname,
            "industry": company.get("industry"),
            "size": company.get("size"),
            "headquarters": company.get("headquarters"),
            "website": company.get("website"),
            "tech_stack": company.get("tech_stack"),
        },
        "health_score": health["score"],
        "health_status": health["status"],
        "signals": {
            "autoops": {
                "alert_count": len(autoops_alerts),
                "high_severity_count": len(autoops_high),
                "status": "red" if len(autoops_high) >= 3 else ("yellow" if autoops_high else "green"),
            },
            "pov_health": pov,
            "renewal": {
                "date": renewal_date,
                "days_remaining": days_to_renewal,
                "arr_usd": arr,
                "signal_count": len(signals),
                "signals": signals,
            },
            "tickets": {
                "open": open_count,
                "p1": sum(1 for t in open_tickets if (t.get("priority") or "").lower() in ("p1", "high", "urgent")),
                "trend_30d": trend_30d,
                "items": open_tickets[:8],
            },
            "last_contact": last_contact,
        },
        "adoption": adoption,
        "proactive_tasks": proactive,
    }
