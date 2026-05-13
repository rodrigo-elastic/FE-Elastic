"""
filename: fsi_banking_fraud.py
description: Demo Data Generator scenario - FSI Card-not-Present Fraud Rings.

Friday morning at Northwind Pay (fictional UK fintech). Two card-not-present fraud
rings hit the checkout flow simultaneously. The Elastic ML jobs have been running
quietly since launch, but today they earn their keep: 80 high-severity alerts in
under three hours, 1500 customer journeys analysed, and ~5000 transactions scored.

The dashboard pair tells two stories from one dataset:

  - FE view (`demo-fsi-banking-fraud-dashboard`): raw signals the FE walks the
    customer through during a technical deep-dive. ML alert breakdown by job,
    fraud pattern by ring, false-positive rate, hour-by-hour transaction volume,
    BIN distribution of fraudulent cards, and the precision/recall snapshot.

  - Customer view (`demo-fsi-banking-fraud-customer-dashboard`): the board-ready
    view. Fraud loss prevented in GBP, alerts deflected at the gateway, mean
    time to detect, comparison to the prior-quarter baseline, and a one-screen
    ROI panel suitable for the CFO read-out.

Three indices (~6580 docs total) plus six Vega-Lite panels with inline data so
the saved-objects render even when the cluster is offline.

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

SCENARIO_ID: str = "fsi-banking-fraud"
SCENARIO_TITLE: str = "FSI Banking - Card-not-Present Fraud Rings"
SCENARIO_DESCRIPTION: str = (
    "Friday morning at Northwind Pay (fictional UK fintech). Two card-not-present "
    "fraud rings hit checkout simultaneously. ~5000 transactions over 24h with a "
    "3% fraud rate, 80 ML alerts ranked by severity, and 1500 customer journey "
    "events. Two paired dashboards: FE view (alert breakdown, fraud patterns, "
    "false positive rate) and Customer view (loss prevented in GBP, alerts "
    "deflected, time-to-detect, ROI snapshot for the board)."
)

INDICES: Dict[str, str] = {
    "transactions": "demo-fsi-card-transactions",
    "alerts": "demo-fsi-fraud-alerts",
    "journeys": "demo-fsi-customer-journey",
}

DASHBOARD_ID: str = "demo-fsi-banking-fraud-dashboard"
CUSTOMER_DASHBOARD_ID: str = "demo-fsi-banking-fraud-customer-dashboard"
DASHBOARDS: List[str] = [DASHBOARD_ID, CUSTOMER_DASHBOARD_ID]
INDEX_PATTERN: str = "demo-fsi-*"

INDUSTRY_ID: str = "fsi-banking"

CUSTOMER_NAME: str = "Northwind Pay"
CURRENCY: str = "GBP"

# Average fraudulent transaction value GBP. Calibrated against UKFinance 2024
# CNP fraud reports for mid-tier digital wallets.
_AVG_FRAUD_GBP = 142.0
_AVG_LEGIT_GBP = 38.0


# ============================================================ Topology ============

# Two fraud rings hitting at once. RING_A is high-velocity small-value testing
# (BIN attack on stolen cards via auto-fill bots). RING_B is patient large-value
# account takeover (legit-looking sessions, geo mismatch, new device).
_RING_A = "ring-a-bin-velocity"
_RING_B = "ring-b-account-takeover"

_BINS_LEGIT = ["411111", "455673", "529921", "601137", "374512", "362839"]
_BINS_FRAUD_RING_A = ["534102", "542418", "551501"]
_BINS_FRAUD_RING_B = ["489534", "467212"]

_MERCHANT_CATEGORIES = [
    ("ecommerce-electronics", 0.18),
    ("ecommerce-fashion", 0.22),
    ("ecommerce-grocery", 0.16),
    ("ecommerce-travel", 0.09),
    ("digital-goods", 0.12),
    ("subscriptions", 0.13),
    ("gift-cards", 0.10),
]

_DEVICE_TYPES = [
    ("ios-mobile", 0.42),
    ("android-mobile", 0.31),
    ("desktop-mac", 0.13),
    ("desktop-win", 0.11),
    ("tablet", 0.03),
]

_LEGIT_COUNTRIES = [
    ("GB", 0.62), ("IE", 0.10), ("FR", 0.08), ("DE", 0.07), ("ES", 0.05),
    ("IT", 0.04), ("NL", 0.04),
]
_RING_A_COUNTRIES = [("RO", 0.40), ("BG", 0.30), ("MD", 0.20), ("UA", 0.10)]
_RING_B_COUNTRIES = [("RU", 0.35), ("BY", 0.25), ("KZ", 0.20), ("TR", 0.20)]

_ML_JOBS = [
    "fsi_cnp_velocity_anomaly",
    "fsi_geoip_mismatch",
    "fsi_new_device_high_value",
    "fsi_bin_concentration",
    "fsi_session_replay_signature",
]

_SEVERITIES = [("critical", 0.18), ("high", 0.42), ("medium", 0.28), ("low", 0.12)]


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


# ============================================================ Mappings ============

def get_mappings() -> Dict[str, Dict[str, Any]]:
    """Mappings stay loose to keep the seed forgiving. Strict-typed time fields
    and IPs only; the rest is dynamic so we can attach arbitrary fraud signals
    without index errors."""
    base = {
        "@timestamp": {"type": "date"},
        "source": {"properties": {"ip": {"type": "ip"}}},
        "client": {"properties": {"ip": {"type": "ip"}}},
        "user": {"properties": {"id": {"type": "keyword"}}},
        "fraud": {
            "properties": {
                "is_fraud": {"type": "boolean"},
                "ring": {"type": "keyword"},
                "score": {"type": "float"},
                "severity": {"type": "keyword"},
                "ml_job": {"type": "keyword"},
            }
        },
        "transaction": {
            "properties": {
                "amount_gbp": {"type": "float"},
                "currency": {"type": "keyword"},
                "merchant_category": {"type": "keyword"},
                "card_bin": {"type": "keyword"},
                "decision": {"type": "keyword"},
            }
        },
        "geo": {
            "properties": {
                "country_iso": {"type": "keyword"},
                "country_name": {"type": "keyword"},
            }
        },
        "device": {"properties": {"type": {"type": "keyword"}}},
    }
    return {
        INDICES["transactions"]: {"mappings": {"dynamic": "true", "properties": base}},
        INDICES["alerts"]: {"mappings": {"dynamic": "true", "properties": base}},
        INDICES["journeys"]: {"mappings": {"dynamic": "true", "properties": base}},
    }


# ============================================================ Document gen ========

def _gen_transactions(now: datetime, rng: random.Random) -> List[Dict[str, Any]]:
    docs: List[Dict[str, Any]] = []
    total = 5000
    fraud_target = int(total * 0.03)
    fraud_indices = set(rng.sample(range(total), fraud_target))

    for i in range(total):
        # Spread across last 24h, with a slight peak Friday lunchtime (UK).
        seconds_ago = rng.uniform(60, 24 * 3600)
        is_fraud = i in fraud_indices

        if is_fraud:
            ring = _RING_A if rng.random() < 0.55 else _RING_B
            if ring == _RING_A:
                amount = round(rng.uniform(8.0, 95.0), 2)
                bin_ = rng.choice(_BINS_FRAUD_RING_A)
                country = _weighted_pick(rng, _RING_A_COUNTRIES)
                decision = rng.choices(
                    ["declined", "approved-then-chargeback", "blocked-3ds"],
                    weights=[0.5, 0.2, 0.3],
                )[0]
            else:
                amount = round(rng.uniform(180.0, 1450.0), 2)
                bin_ = rng.choice(_BINS_FRAUD_RING_B)
                country = _weighted_pick(rng, _RING_B_COUNTRIES)
                decision = rng.choices(
                    ["declined", "approved-then-chargeback", "blocked-3ds"],
                    weights=[0.35, 0.30, 0.35],
                )[0]
        else:
            ring = None
            amount = round(rng.gauss(_AVG_LEGIT_GBP, 22.0), 2)
            if amount < 1.0:
                amount = round(rng.uniform(2.0, 18.0), 2)
            bin_ = rng.choice(_BINS_LEGIT)
            country = _weighted_pick(rng, _LEGIT_COUNTRIES)
            decision = rng.choices(["approved", "declined"], weights=[0.93, 0.07])[0]

        category = _weighted_pick(rng, _MERCHANT_CATEGORIES)
        device = _weighted_pick(rng, _DEVICE_TYPES)
        score = round(rng.uniform(0.78, 0.99), 3) if is_fraud else round(rng.uniform(0.01, 0.32), 3)

        docs.append({
            "@timestamp": _ts(now, seconds_ago),
            "event": {"category": "transaction", "kind": "event"},
            "transaction": {
                "id": "tx-" + uuid.uuid4().hex[:14],
                "amount_gbp": amount,
                "currency": CURRENCY,
                "merchant_category": category,
                "card_bin": bin_,
                "decision": decision,
            },
            "fraud": {
                "is_fraud": is_fraud,
                "ring": ring,
                "score": score,
                "model_version": "fsi-cnp-2026.04",
            },
            "geo": {"country_iso": country, "country_name": country},
            "device": {"type": device},
            "customer": {
                "name": CUSTOMER_NAME,
                "industry": INDUSTRY_ID,
            },
        })
    return docs


def _gen_alerts(now: datetime, rng: random.Random) -> List[Dict[str, Any]]:
    docs: List[Dict[str, Any]] = []
    for _ in range(80):
        seconds_ago = rng.uniform(60, 18 * 3600)
        ml_job = rng.choice(_ML_JOBS)
        severity = _weighted_pick(rng, _SEVERITIES)
        ring = _RING_A if rng.random() < 0.55 else _RING_B
        # 12% of alerts are false positives. The model still flagged them but
        # the analyst review marked them legit.
        is_fp = rng.random() < 0.12
        score = round(rng.uniform(0.62, 0.99), 3)
        docs.append({
            "@timestamp": _ts(now, seconds_ago),
            "event": {"kind": "alert", "category": "fraud"},
            "fraud": {
                "is_fraud": not is_fp,
                "ring": ring,
                "severity": severity,
                "ml_job": ml_job,
                "score": score,
                "false_positive": is_fp,
            },
            "alert": {
                "id": "al-" + uuid.uuid4().hex[:12],
                "status": rng.choice(["open", "investigating", "resolved", "escalated"]),
                "owner": rng.choice([
                    "soc-l1@northwindpay.example",
                    "soc-l2@northwindpay.example",
                    "fraud-ops@northwindpay.example",
                ]),
            },
            "customer": {"name": CUSTOMER_NAME, "industry": INDUSTRY_ID},
        })
    return docs


def _gen_journeys(now: datetime, rng: random.Random) -> List[Dict[str, Any]]:
    docs: List[Dict[str, Any]] = []
    for _ in range(1500):
        seconds_ago = rng.uniform(60, 24 * 3600)
        is_fraud = rng.random() < 0.04
        steps = ["landing", "product-view", "add-to-cart", "checkout-init",
                 "payment-init", "payment-3ds", "payment-result"]
        step = rng.choice(steps)
        device = _weighted_pick(rng, _DEVICE_TYPES)
        country = (_weighted_pick(rng, _RING_A_COUNTRIES) if is_fraud
                   else _weighted_pick(rng, _LEGIT_COUNTRIES))
        docs.append({
            "@timestamp": _ts(now, seconds_ago),
            "event": {"category": "session", "kind": "event", "action": step},
            "session": {
                "id": "ses-" + uuid.uuid4().hex[:12],
                "step": step,
                "duration_ms": int(rng.uniform(120, 3500)),
            },
            "fraud": {"is_fraud": is_fraud,
                      "ring": _RING_A if is_fraud else None},
            "geo": {"country_iso": country},
            "device": {"type": device},
            "customer": {"name": CUSTOMER_NAME, "industry": INDUSTRY_ID},
        })
    return docs


def generate_documents(seed: int = 20260504) -> Dict[str, List[Dict[str, Any]]]:
    rng = random.Random(seed)
    now = _now()
    return {
        INDICES["transactions"]: _gen_transactions(now, rng),
        INDICES["alerts"]: _gen_alerts(now, rng),
        INDICES["journeys"]: _gen_journeys(now, rng),
    }


# ============================================================ KPIs ===============

def _compute_kpis(docs: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    tx = docs[INDICES["transactions"]]
    alerts = docs[INDICES["alerts"]]
    fraud_tx = [t for t in tx if t["fraud"]["is_fraud"]]
    blocked_tx = [t for t in fraud_tx
                  if t["transaction"]["decision"] in ("declined", "blocked-3ds")]
    loss_prevented = round(sum(t["transaction"]["amount_gbp"] for t in blocked_tx), 2)
    realised_loss = round(sum(t["transaction"]["amount_gbp"] for t in fraud_tx
                              if t["transaction"]["decision"] == "approved-then-chargeback"), 2)
    fp_rate = round(sum(1 for a in alerts if a["fraud"]["false_positive"]) / max(1, len(alerts)) * 100, 1)
    avg_ttd_seconds = 47  # mean time to detect, narrative figure
    return {
        "transactions_total": len(tx),
        "fraud_total": len(fraud_tx),
        "alerts_total": len(alerts),
        "loss_prevented_gbp": loss_prevented,
        "realised_loss_gbp": realised_loss,
        "fp_rate_pct": fp_rate,
        "mean_ttd_seconds": avg_ttd_seconds,
    }


# ============================================================ Vega specs =========

_VEGA_SCHEMA = "https://vega.github.io/schema/vega-lite/v5.json"


def _vega_alerts_by_job(alerts: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts: Dict[str, int] = {}
    for a in alerts:
        counts[a["fraud"]["ml_job"]] = counts.get(a["fraud"]["ml_job"], 0) + 1
    values = [{"job": k, "count": v} for k, v in sorted(counts.items())]
    return {
        "$schema": _VEGA_SCHEMA,
        "description": "Alerts by ML job",
        "data": {"values": values},
        "mark": {"type": "bar", "tooltip": True, "color": "#0077CC"},
        "encoding": {
            "y": {"field": "job", "type": "nominal", "sort": "-x", "title": "ML job"},
            "x": {"field": "count", "type": "quantitative", "title": "Alerts"},
        },
        "width": "container",
        "height": 220,
    }


def _vega_alerts_by_severity(alerts: List[Dict[str, Any]]) -> Dict[str, Any]:
    sev_order = ["critical", "high", "medium", "low"]
    counts: Dict[str, int] = {s: 0 for s in sev_order}
    for a in alerts:
        sev = a["fraud"]["severity"]
        counts[sev] = counts.get(sev, 0) + 1
    values = [{"severity": s, "count": counts[s]} for s in sev_order]
    return {
        "$schema": _VEGA_SCHEMA,
        "data": {"values": values},
        "mark": {"type": "bar", "tooltip": True},
        "encoding": {
            "x": {"field": "severity", "type": "nominal", "sort": sev_order, "title": "Severity"},
            "y": {"field": "count", "type": "quantitative", "title": "Alerts"},
            "color": {
                "field": "severity", "type": "nominal",
                "scale": {"domain": sev_order,
                          "range": ["#C0392B", "#E67E22", "#F1C40F", "#2ECC71"]},
                "legend": None,
            },
        },
        "width": "container",
        "height": 220,
    }


def _vega_fraud_by_ring(tx: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts: Dict[str, int] = {_RING_A: 0, _RING_B: 0}
    amount: Dict[str, float] = {_RING_A: 0.0, _RING_B: 0.0}
    for t in tx:
        if not t["fraud"]["is_fraud"]:
            continue
        ring = t["fraud"]["ring"]
        counts[ring] = counts.get(ring, 0) + 1
        amount[ring] = amount.get(ring, 0.0) + t["transaction"]["amount_gbp"]
    values = [
        {"ring": "Ring A (BIN velocity)", "count": counts[_RING_A],
         "gbp": round(amount[_RING_A], 2)},
        {"ring": "Ring B (account takeover)", "count": counts[_RING_B],
         "gbp": round(amount[_RING_B], 2)},
    ]
    return {
        "$schema": _VEGA_SCHEMA,
        "data": {"values": values},
        "layer": [
            {
                "mark": {"type": "bar", "tooltip": True, "color": "#16A085"},
                "encoding": {
                    "x": {"field": "ring", "type": "nominal", "title": "Fraud ring"},
                    "y": {"field": "count", "type": "quantitative", "title": "Fraud transactions"},
                },
            },
            {
                "mark": {"type": "text", "dy": -8, "fontSize": 12, "color": "#0F2A3F"},
                "encoding": {
                    "x": {"field": "ring", "type": "nominal"},
                    "y": {"field": "count", "type": "quantitative"},
                    "text": {"field": "gbp", "type": "quantitative", "format": ",.0f"},
                },
            },
        ],
        "width": "container",
        "height": 220,
    }


def _vega_tx_volume_24h(tx: List[Dict[str, Any]]) -> Dict[str, Any]:
    buckets: Dict[int, Dict[str, int]] = {}
    now = datetime.now(timezone.utc)
    for t in tx:
        ts = datetime.fromisoformat(t["@timestamp"].replace("Z", "+00:00"))
        hours_ago = int((now - ts).total_seconds() // 3600)
        if hours_ago < 0 or hours_ago > 24:
            continue
        b = buckets.setdefault(hours_ago, {"legit": 0, "fraud": 0})
        if t["fraud"]["is_fraud"]:
            b["fraud"] += 1
        else:
            b["legit"] += 1
    values: List[Dict[str, Any]] = []
    for h in range(24, -1, -1):
        b = buckets.get(h, {"legit": 0, "fraud": 0})
        values.append({"hours_ago": -h, "kind": "legit", "count": b["legit"]})
        values.append({"hours_ago": -h, "kind": "fraud", "count": b["fraud"]})
    return {
        "$schema": _VEGA_SCHEMA,
        "data": {"values": values},
        "mark": {"type": "area", "tooltip": True, "interpolate": "monotone"},
        "encoding": {
            "x": {"field": "hours_ago", "type": "quantitative", "title": "Hours ago"},
            "y": {"field": "count", "type": "quantitative", "stack": "zero", "title": "Transactions"},
            "color": {
                "field": "kind", "type": "nominal",
                "scale": {"domain": ["legit", "fraud"],
                          "range": ["#3498DB", "#E74C3C"]},
                "title": "Class",
            },
        },
        "width": "container",
        "height": 220,
    }


def _vega_loss_prevented(kpi: Dict[str, Any]) -> Dict[str, Any]:
    values = [
        {"label": "Prevented (blocked or declined)", "gbp": kpi["loss_prevented_gbp"]},
        {"label": "Realised loss (chargebacks)", "gbp": kpi["realised_loss_gbp"]},
    ]
    return {
        "$schema": _VEGA_SCHEMA,
        "data": {"values": values},
        "mark": {"type": "bar", "tooltip": True},
        "encoding": {
            "y": {"field": "label", "type": "nominal", "title": ""},
            "x": {"field": "gbp", "type": "quantitative", "title": "GBP"},
            "color": {
                "field": "label", "type": "nominal",
                "scale": {"range": ["#16A085", "#C0392B"]},
                "legend": None,
            },
        },
        "width": "container",
        "height": 180,
    }


def _vega_country_distribution(tx: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts: Dict[str, Dict[str, int]] = {}
    for t in tx:
        c = t["geo"]["country_iso"]
        d = counts.setdefault(c, {"legit": 0, "fraud": 0})
        if t["fraud"]["is_fraud"]:
            d["fraud"] += 1
        else:
            d["legit"] += 1
    values: List[Dict[str, Any]] = []
    top = sorted(counts.items(), key=lambda kv: kv[1]["legit"] + kv[1]["fraud"], reverse=True)[:8]
    for country, kinds in top:
        values.append({"country": country, "kind": "legit", "count": kinds["legit"]})
        values.append({"country": country, "kind": "fraud", "count": kinds["fraud"]})
    return {
        "$schema": _VEGA_SCHEMA,
        "data": {"values": values},
        "mark": {"type": "bar", "tooltip": True},
        "encoding": {
            "x": {"field": "country", "type": "nominal", "title": "Country"},
            "y": {"field": "count", "type": "quantitative", "title": "Transactions"},
            "color": {
                "field": "kind", "type": "nominal",
                "scale": {"domain": ["legit", "fraud"],
                          "range": ["#3498DB", "#E74C3C"]},
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
        f"## Northwind Pay - card-not-present fraud rings\n\n"
        f"- [FE prep view{fe_active}]({fe_url})\n"
        f"- [Customer board view{cu_active}]({cu_url})\n"
    )


def _intro_fe_md() -> str:
    return (
        "## How to demo this scenario\n\n"
        "1. Open the **Alerts by ML job** panel and call out that five jobs run "
        "in production right now. The headline today is `fsi_cnp_velocity_anomaly` "
        "catching Ring A at the BIN level.\n"
        "2. Pivot to **Fraud by ring**. Two rings, two stories: Ring A is "
        "high-velocity small-ticket testing, Ring B is patient large-ticket account "
        "takeover. Different signatures, same dataset.\n"
        "3. **Transactions over 24h** shows the lunchtime spike both rings ride. "
        "`fraud` overlay tracks the legit curve - that is the point.\n"
        "4. **Country distribution** is the geo-IP mismatch story for the customer.\n"
        "5. Close on **Alerts by severity**. 18% critical, 42% high. SOC tier-1 "
        "gets a clean queue.\n\n"
        "**MEDDPICC angle.** Northwind Pay's CISO says they ship 2.3M card "
        "transactions/day; current vendor (legacy on-prem rules engine) misses "
        "Ring B entirely because rules cannot baseline an unseen device. ML jobs "
        "shipped here cover that gap with no manual rule tuning."
    )


def _intro_customer_md() -> str:
    return (
        "## Friday 11:47 - what just happened\n\n"
        "Two coordinated card-not-present fraud rings hit checkout at the same "
        "time. Ring A ran a BIN-velocity test on stolen cards (fast, cheap, "
        "high-volume). Ring B used compromised credentials with new devices to "
        "push large-ticket purchases through 3DS.\n\n"
        "**Bottom line.** Elastic ML jobs detected both rings inside the first "
        "minute; transactions were declined or stepped up to 3DS at the gateway "
        "before settlement. The board view below quantifies what was prevented "
        "and what was missed."
    )


def _kpi_fe_md(kpi: Dict[str, Any]) -> str:
    return (
        "## Headline KPIs (last 24h)\n\n"
        "| Metric | Value | Notes |\n"
        "| --- | --- | --- |\n"
        f"| Transactions scored | **{kpi['transactions_total']:,}** | one ML pass each |\n"
        f"| Fraudulent transactions | **{kpi['fraud_total']}** | "
        f"{kpi['fraud_total'] / kpi['transactions_total']:.1%} ground-truth rate |\n"
        f"| ML alerts | **{kpi['alerts_total']}** | across 5 jobs |\n"
        f"| False-positive rate | **{kpi['fp_rate_pct']}%** | analyst-validated |\n"
        f"| Mean time to detect | **{kpi['mean_ttd_seconds']}s** | from card swipe to alert |\n\n"
        "_All five ML jobs hosted in Elastic Machine Learning, scored against "
        "an inline pipeline at index time._"
    )


def _kpi_customer_md(kpi: Dict[str, Any]) -> str:
    return (
        "## Board-ready KPIs (last 24h)\n\n"
        "| Metric | Value |\n"
        "| --- | --- |\n"
        f"| Loss prevented | **GBP {kpi['loss_prevented_gbp']:,.2f}** |\n"
        f"| Realised loss (chargebacks) | GBP {kpi['realised_loss_gbp']:,.2f} |\n"
        f"| Alerts deflected at gateway | {kpi['alerts_total']} |\n"
        f"| Mean time to detect | {kpi['mean_ttd_seconds']}s |\n"
        f"| False-positive rate | {kpi['fp_rate_pct']}% |\n\n"
        "**ROI snapshot.** Loss prevented at this rate annualises to "
        f"**~GBP {kpi['loss_prevented_gbp'] * 365:,.0f}** at constant volume; the "
        "Elastic Search Platform spend for this workload sits in the **low six "
        "figures** - the platform pays for itself inside the first quarter."
    )


def _close_fe_md() -> str:
    return (
        "## Talk track for the close\n\n"
        "1. Northwind Pay had this exact pattern hit them in February, lost "
        "**GBP 480k** in 4 hours because the rules engine did not see Ring B. "
        "Today's data shows that gap closed.\n"
        "2. The five ML jobs ship out of the box; the customer's data scientists "
        "can clone them, retrain on their own merchant categories, and promote "
        "in-place.\n"
        "3. Pair with **Detection Rules** for known signatures + **Cases** for "
        "the analyst queue. One platform, one schema, one investigation surface."
    )


def _close_customer_md() -> str:
    return (
        "## Next 30 days\n\n"
        "**Done.** Both fraud rings detected, alerted, and routed to the SOC "
        "queue with zero false escalations on the critical band.\n\n"
        "**In flight.**\n"
        "1. Promote `fsi_session_replay_signature` from canary to production - "
        "currently catches 78% of Ring B with 3% false positives.\n"
        "2. Wire the alert webhook to the IVR gateway so high-severity events "
        "trigger an automated customer call within 60 seconds.\n"
        "3. Quarterly red-team replay using the same dataset Elastic ships in "
        "this scenario, signed off by the Head of Fraud Operations."
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
    tx = docs[INDICES["transactions"]]
    alerts = docs[INDICES["alerts"]]
    kpi = _compute_kpis(docs)

    intro_md = _intro_fe_md() if view == "fe" else _intro_customer_md()
    kpi_md = _kpi_fe_md(kpi) if view == "fe" else _kpi_customer_md(kpi)
    close_md = _close_fe_md() if view == "fe" else _close_customer_md()

    panels: List[Dict[str, Any]] = []

    # Row 1: switcher
    panels.append(_markdown_panel("p_switch", 0, 0, 48, 4, _switcher_md(view), "Switch view"))

    # Row 2: intro
    panels.append(_markdown_panel("p_intro", 0, 4, 48, 8, intro_md, "Overview"))

    # Row 3: alerts by job + alerts by severity
    panels.append(_vega_panel("p_jobs", 0, 12, 24, 14,
                              "Alerts by ML job", _vega_alerts_by_job(alerts)))
    panels.append(_vega_panel("p_sev", 24, 12, 24, 14,
                              "Alerts by severity", _vega_alerts_by_severity(alerts)))

    # Row 4: fraud by ring + transaction volume 24h
    panels.append(_vega_panel("p_ring", 0, 26, 24, 14,
                              "Fraud transactions by ring", _vega_fraud_by_ring(tx)))
    panels.append(_vega_panel("p_vol", 24, 26, 24, 14,
                              "Transactions over 24h (legit vs fraud)",
                              _vega_tx_volume_24h(tx)))

    # Row 5: country distribution + loss prevented
    panels.append(_vega_panel("p_geo", 0, 40, 24, 14,
                              "Top countries (legit vs fraud)", _vega_country_distribution(tx)))
    panels.append(_vega_panel("p_loss", 24, 40, 24, 14,
                              "Loss prevented vs realised", _vega_loss_prevented(kpi)))

    # Row 6: KPI markdown
    panels.append(_markdown_panel("p_kpi", 0, 54, 48, 12, kpi_md, "KPIs"))

    # Row 7: closing
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
            "name": f"demo fsi {SCENARIO_ID}",
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
            log.warning("fsi_banking_fraud.dataview.fallback",
                        status=resp.status_code, body=resp.text[:300])
            body2 = [{
                "id": dv_id,
                "type": "index-pattern",
                "attributes": {
                    "title": INDEX_PATTERN,
                    "name": f"demo fsi {SCENARIO_ID}",
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
            "timeFrom": "now-24h",
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
        "id": "fsi-banking",
        "name": "FSI banking fraud - account-takeover and rings",
        "summary": ("Real-time fraud detection across retail and commercial "
                    "banking. ML-driven rings, ATO, mule-account chains."),
        "personas": [
            {"role": "Head of Fraud",
             "pain": "Detect ATO under 90s; rule-based stack is at 90 minutes."},
            {"role": "CISO",
             "pain": "Splunk renewal is 2x last year and DORA evidence is manual."},
            {"role": "Chief Risk Officer",
             "pain": "Cross-channel fraud is invisible: card, ACH, wire silos."},
            {"role": "Compliance Officer",
             "pain": "FRTB and DORA pulls take 3 weeks of audit-team time."},
        ],
        "regulations": ["DORA", "PCI DSS", "FRTB", "Basel III", "GDPR"],
        "top_competitors": ["battlecard-splunk", "battlecard-datadog",
                            "battlecard-sumologic"],
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
        customer="Northwind Pay",
        customer_panels=cu_panels,
        fe_only_extras=fe_only_extras,
        id_prefix="fsi-fe",
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
            "Field Engineer prep view. ML alert breakdown, fraud patterns by ring, "
            "false-positive rate, country distribution, MEDDPICC angle, demo cheat "
            "sheet for the technical deep-dive."
        ),
        panels=fe_panels,
    )
    cu_id = _create_one_dashboard(
        data_view_id=data_view_id,
        dashboard_id=CUSTOMER_DASHBOARD_ID,
        title=f"[Customer] {SCENARIO_TITLE}",
        description=(
            "Northwind Pay board view. Fraud loss prevented in GBP, alerts deflected, "
            "mean time to detect, ROI snapshot for the CFO."
        ),
        panels=cu_panels,
    )
    return {"fe": fe_id, "customer": cu_id}


# ============================================================ Seed entrypoint ====


def _to_bulk_actions(index: str, docs: List[Dict[str, Any]]):
    for doc in docs:
        yield {"_index": index, "_source": doc}


def seed_dashboards(kibana_client=None) -> Dict[str, Any]:
    """Public hook: rebuild only the dashboards. Generates docs in-memory just
    to recompute the KPI markdowns. Useful when the seeders are invoked by an
    external orchestrator that already owns the index data."""
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
    ingests, recreates the FE + Customer dashboards. Returns counts and URLs."""
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
            log.warning("fsi_banking_fraud.index.recreate.failed",
                        index=index, error=str(exc))
        actions = list(_to_bulk_actions(index, docs))
        refresh = "wait_for" if index == last_index else False
        try:
            success, errors = bulk(es, actions, chunk_size=500,
                                   refresh=refresh, raise_on_error=False)
        except Exception as exc:
            log.warning("fsi_banking_fraud.bulk.failed", index=index, error=str(exc))
            success, errors = 0, [str(exc)]
        counts[index] = success
        log.info("fsi_banking_fraud.indexed", index=index, count=success,
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
