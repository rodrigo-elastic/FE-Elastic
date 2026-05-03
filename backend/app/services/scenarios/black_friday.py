"""
filename: black_friday.py
description: FE Copilot · Demo Data Generator · Black Friday Outage scenario.

Story arc:
    Lumen Apparel — a fast-growing online apparel brand — runs their biggest sale
    of the year. Around 10am PT on Black Friday, sustained upstream load from
    catalog-svc drives checkout-db into IO contention. p99 latency on the
    checkout-db dependency jumps from a 180ms baseline to 4-8s; checkout-svc
    starts surfacing 5xx errors; payment-svc retries cascade. Cart abandonment
    doubles from ~28% to ~55%. By 11:30am PT the SRE team applies the fix
    (a hot config rollback for the catalog page-size change shipped on Tuesday)
    and the metrics snap back inside one bucket. Three smaller precursor
    incidents in the previous week, in retrospect, were warnings.

This module emits ~5,500 documents across three indices:
    - demo-blackfriday-checkout  (~3500 docs): web/transaction logs (ECS http).
    - demo-blackfriday-apm       (~1500 docs): APM transaction docs with span info.
    - demo-blackfriday-metrics   (~600  docs): per-service 5-min metric rollups.

Plus one Kibana dashboard with six story-driven panels, all Vega-Lite for
saved-object portability.

Public surface:
    SCENARIO_ID, SCENARIO_TITLE, SCENARIO_DESCRIPTION
    INDICES, DASHBOARD_ID
    get_mappings(), generate_documents(seed), get_dashboard_panels(), seed()

date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
import math
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


# ============================================================ Public constants ======

SCENARIO_ID: str = "black-friday-outage"
SCENARIO_TITLE: str = "Black Friday Outage"
SCENARIO_DESCRIPTION: str = (
    "Lumen Apparel — a growing fintech-backed e-commerce platform — runs its biggest "
    "sale of the year. At 10:00am PT, checkout-db hits IO contention: p99 latency jumps "
    "from 180ms to 4-8s, cart abandonment doubles, and 5xx errors cascade through "
    "payment-svc. Three precursor incidents in the prior week were the warning signs. "
    "Demo dataset shows the headliner outage plus the precursors and the snap-back "
    "recovery once SRE rolls back a hot config."
)

INDICES: Dict[str, str] = {
    "checkout": "demo-blackfriday-checkout",
    "apm": "demo-blackfriday-apm",
    "metrics": "demo-blackfriday-metrics",
}

DASHBOARD_ID: str = "demo-black-friday-outage-dashboard"

# The seed anchor — fixes "now" for reproducibility. Without this the timestamps
# walk every time you re-seed, which is fine for fresh demos but ugly for tests.
_DEFAULT_SEED: int = 20260503


# ============================================================ Topology =============

# Service catalogue. Each entry: name -> (baseline_p50_ms, baseline_p99_ms, role, version).
# checkout-db is the villain; checkout-svc and payment-svc are the collateral damage.
_SERVICES: Dict[str, Dict[str, Any]] = {
    "frontend": {"p50": 35, "p99": 80, "role": "edge", "version": "2026.11.4",
                 "language": "typescript", "runtime": "node-20"},
    "api-gateway": {"p50": 22, "p99": 95, "role": "edge", "version": "2026.11.2",
                    "language": "go", "runtime": "go-1.22"},
    "catalog-svc": {"p50": 45, "p99": 130, "role": "core", "version": "2026.11.3",
                    "language": "java", "runtime": "jvm-21"},
    "cart-svc": {"p50": 28, "p99": 110, "role": "core", "version": "2026.11.1",
                 "language": "java", "runtime": "jvm-21"},
    "recs-svc": {"p50": 55, "p99": 120, "role": "core", "version": "2026.10.7",
                 "language": "python", "runtime": "py-3.12"},
    "checkout-svc": {"p50": 70, "p99": 240, "role": "core", "version": "2026.11.2",
                     "language": "java", "runtime": "jvm-21"},
    "checkout-db": {"p50": 60, "p99": 180, "role": "datastore", "version": "PG-15.4",
                    "language": "postgres", "runtime": "rds-postgres-15"},
    "payment-svc": {"p50": 110, "p99": 320, "role": "core", "version": "2026.11.0",
                    "language": "go", "runtime": "go-1.22"},
    "inventory-svc": {"p50": 38, "p99": 140, "role": "core", "version": "2026.11.1",
                      "language": "go", "runtime": "go-1.22"},
    "notification-svc": {"p50": 18, "p99": 70, "role": "edge", "version": "2026.10.4",
                         "language": "typescript", "runtime": "node-20"},
}

# Service topology edges (caller -> callee). Used to walk realistic trace shapes.
_TOPOLOGY: Dict[str, List[str]] = {
    "frontend": ["api-gateway"],
    "api-gateway": ["catalog-svc", "cart-svc", "checkout-svc", "recs-svc"],
    "catalog-svc": ["inventory-svc"],
    "cart-svc": ["catalog-svc", "inventory-svc"],
    "recs-svc": ["catalog-svc"],
    "checkout-svc": ["checkout-db", "payment-svc", "inventory-svc", "notification-svc"],
    "payment-svc": [],
    "checkout-db": [],
    "inventory-svc": [],
    "notification-svc": [],
}

# Pods per service (k8s replica counts). Used to populate host.name and pod_name.
_POD_COUNTS: Dict[str, int] = {
    "frontend": 12, "api-gateway": 8, "catalog-svc": 10, "cart-svc": 8,
    "recs-svc": 4, "checkout-svc": 12, "checkout-db": 3, "payment-svc": 8,
    "inventory-svc": 6, "notification-svc": 4,
}

_REGIONS: List[Tuple[str, str, str]] = [
    ("us-west-2", "aws", "Oregon"),
    ("us-east-1", "aws", "N. Virginia"),
    ("eu-west-1", "aws", "Ireland"),
]

_COUNTRIES = [
    ("US", 0.55), ("CA", 0.07), ("GB", 0.09), ("DE", 0.06), ("FR", 0.05),
    ("AU", 0.04), ("JP", 0.04), ("BR", 0.03), ("MX", 0.03), ("NL", 0.02),
    ("SE", 0.01), ("ES", 0.01),
]

_USER_AGENTS = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.82 Mobile Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (iPad; CPU OS 17_4 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1",
]

_PAYMENT_METHODS: List[Tuple[str, float]] = [
    ("card", 0.62), ("paypal", 0.16), ("apple_pay", 0.11),
    ("google_pay", 0.06), ("klarna", 0.03), ("affirm", 0.02),
]

_RECS_VERSIONS = ["v4.2.1-prod", "v4.2.1-prod", "v4.2.1-prod", "v4.3.0-canary"]

_PATHS: List[Tuple[str, str, str]] = [
    ("GET", "/", "Home"),
    ("GET", "/c/womens-coats", "BrowseCategory"),
    ("GET", "/c/mens-knitwear", "BrowseCategory"),
    ("GET", "/p/{sku}", "ProductDetail"),
    ("POST", "/api/cart/add", "CartAdd"),
    ("DELETE", "/api/cart/{id}", "CartRemove"),
    ("GET", "/api/recs/home", "RecsHome"),
    ("GET", "/api/recs/cart", "RecsCart"),
    ("POST", "/checkout/begin", "CheckoutBegin"),
    ("POST", "/checkout/shipping", "CheckoutShipping"),
    ("POST", "/checkout/payment", "CheckoutPayment"),
    ("POST", "/checkout/place-order", "CheckoutPlaceOrder"),
    ("POST", "/api/payment/charge", "PaymentCharge"),
    ("POST", "/api/payment/retry", "PaymentRetry"),
]

# Lumen apparel SKUs — these get embedded in URLs, payloads.
_SKUS = [
    "LUM-AURA-COAT-NVY-M", "LUM-AURA-COAT-NVY-L", "LUM-AURA-COAT-CAM-S",
    "LUM-MERINO-CREW-OAT-M", "LUM-MERINO-CREW-CHA-L", "LUM-RIB-BEANIE-BLK-OS",
    "LUM-CASH-SCARF-RST-OS", "LUM-PEAK-DENIM-IND-32", "LUM-PEAK-DENIM-IND-34",
    "LUM-LINEN-SHIRT-WHT-M", "LUM-LINEN-SHIRT-WHT-L", "LUM-LOAFER-TAN-10",
    "LUM-TRENCH-KHA-S", "LUM-TRENCH-KHA-M", "LUM-CARGO-OLV-32",
]

_PROMO_CODES = ["BLACKFRIDAY", "BF30", "EARLYBIRD", "VIP15", "FREESHIP"]


# ============================================================ Anomaly windows ======


def _anomaly_windows(now: datetime) -> List[Dict[str, Any]]:
    """Return the four anomaly windows as datetime ranges plus severity multipliers.

    Severities are calibrated so the "headliner" dominates the visualization:
    severity is the latency multiplier applied on top of the baseline-with-tail.
    """
    return [
        {
            "label": "Precursor 1 — mild",
            "start": now - timedelta(days=6, hours=10),  # T-6d 14:00 UTC if 'now' is 00:00 UTC
            "end": now - timedelta(days=6, hours=10) + timedelta(minutes=25),
            "severity": 0.35,
            "tail_factor": 6.0,
        },
        {
            "label": "Precursor 2 — moderate",
            "start": now - timedelta(days=4, hours=6),
            "end": now - timedelta(days=4, hours=6) + timedelta(minutes=60),
            "severity": 0.55,
            "tail_factor": 11.0,
        },
        {
            "label": "Precursor 3 — dress rehearsal",
            "start": now - timedelta(days=2, hours=8),
            "end": now - timedelta(days=2, hours=8) + timedelta(minutes=90),
            "severity": 0.75,
            "tail_factor": 18.0,
        },
        {
            "label": "Headliner — Black Friday outage",
            "start": now - timedelta(hours=6),
            "end": now - timedelta(hours=6) + timedelta(minutes=90),
            "severity": 1.0,
            "tail_factor": 35.0,
        },
    ]


def _in_any_window(ts: datetime, windows: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for w in windows:
        if w["start"] <= ts <= w["end"]:
            return w
    return None


def _traffic_multiplier(ts: datetime, headliner_start: datetime) -> float:
    """Return a traffic-volume multiplier vs steady-state.

    Black Friday has a diurnal hump centred around the "10am PT" peak, plus a
    sustained-elevated baseline for the 24h surrounding the sale. This shapes
    the spread of timestamps so charts look like a real traffic curve, not
    uniform random.
    """
    hours_from_peak = abs((ts - headliner_start).total_seconds()) / 3600.0
    # Gaussian hump centred on the headliner, sigma = 6h.
    hump = math.exp(-(hours_from_peak ** 2) / (2 * (6.0 ** 2)))
    # Diurnal sin wave (24h cycle). Peak at the headliner hour.
    h = ts.hour + ts.minute / 60.0
    diurnal = 0.55 + 0.45 * math.sin(((h - 9) / 24.0) * 2 * math.pi)
    # 1.0 is steady; up to ~3.5 at peak.
    return 1.0 + 2.4 * hump + 0.2 * diurnal


# ============================================================ Stat helpers =========


def _heavy_tail_latency(rng: random.Random, p50: float, p99: float,
                        anomaly: Optional[Dict[str, Any]] = None,
                        is_db: bool = False) -> float:
    """Sample a request latency in milliseconds with a realistic heavy tail.

    Shape: 92% lognormal centred near p50; 8% extra-heavy tail for the natural
    long-tail (slow connections, DNS hiccups, GC pauses). When inside an anomaly
    window AND the service is the villain (checkout-db) or downstream collateral,
    the tail dominates: the long-tail mass jumps to 60-80% and the scale
    multiplies by the anomaly's tail_factor.

    This is what you actually see in real APM data: most requests still finish
    fast, but the p99 is held up by an aggressive minority of slow ones.
    """
    sigma = 0.55  # lognormal spread
    # mu calibrated so median ≈ p50.
    mu = math.log(max(p50, 1.0))

    base = math.exp(rng.gauss(mu, sigma))
    # Always-on background long tail
    tail_p = 0.08
    tail_scale = max(p99 / max(p50, 1.0), 1.4)

    if anomaly is not None and is_db:
        tail_p = 0.78  # the DB is in trouble; most requests are slow
        tail_scale = anomaly["tail_factor"] * (1.0 + 0.5 * rng.random())
    elif anomaly is not None:
        # Collateral damage: a slice of upstream calls inherit the slowness
        tail_p = 0.32
        tail_scale = max(2.0, anomaly["tail_factor"] * 0.35)

    if rng.random() < tail_p:
        # Pareto-ish tail (1 + exp scaled). Multiply baseline by a heavy multiplier.
        u = rng.random()
        # Inverse-CDF of a Pareto with alpha=1.4 → values in [1, 30+).
        pareto = (1.0 / max(u, 1e-3)) ** (1.0 / 1.4)
        return base * tail_scale * pareto
    return base


def _weighted_choice(rng: random.Random, items: List[Tuple[Any, float]]):
    r = rng.random()
    acc = 0.0
    for value, w in items:
        acc += w
        if r <= acc:
            return value
    return items[-1][0]


def _now_anchor() -> datetime:
    """Pin "now" so re-seeding produces a repeatable layout. We anchor on whole
    seconds so the dashboard's `now` filter still includes the headliner."""
    # Use real wall-clock (so the dashboard time picker covers the data) but
    # drop sub-second jitter. Re-seed will land timestamps in the same shape.
    n = datetime.now(timezone.utc).replace(microsecond=0)
    return n


# ============================================================ Helpers ==============


def _trace_id() -> str:
    return uuid.uuid4().hex


def _span_id() -> str:
    return uuid.uuid4().hex[:16]


def _user(rng: random.Random) -> Dict[str, Any]:
    uid = rng.randint(10_000, 99_999)
    domains = ["gmail.com", "outlook.com", "yahoo.com", "icloud.com", "fastmail.com"]
    first = rng.choice([
        "alex", "morgan", "casey", "sam", "jordan", "taylor", "lee", "robin",
        "kai", "nico", "rin", "ezra", "june", "ari", "pat", "skye",
    ])
    last = rng.choice([
        "chen", "kumar", "weber", "perez", "singh", "alvarez", "lee",
        "mueller", "popov", "rossi", "tanaka", "smith", "dubois", "olsson",
    ])
    return {
        "id": f"u-{uid:06d}",
        "email": f"{first}.{last}{uid % 100:02d}@{rng.choice(domains)}",
        "name": f"{first.title()} {last.title()}",
        "geo": {"country_iso_code": _weighted_choice(rng, _COUNTRIES)},
    }


def _host_for(rng: random.Random, service: str) -> Dict[str, Any]:
    pod = rng.randint(1, _POD_COUNTS.get(service, 4))
    region, provider, region_label = rng.choice(_REGIONS)
    return {
        "name": f"k8s-{service}-{pod:02d}",
        "region": region_label,
        "pod_name": f"{service}-7c{rng.randrange(0xfff):03x}-x{rng.randrange(0xfff):03x}",
        "node": f"ip-10-{rng.randint(0, 255)}-{rng.randint(0, 255)}-{rng.randint(0, 255)}.{region}.compute.internal",
        "_provider": provider,
        "_region": region,
    }


# ============================================================ Document generators ==


def _gen_checkout_logs(rng: random.Random, now: datetime,
                       windows: List[Dict[str, Any]],
                       headliner: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate ECS-aligned web request logs (~3500 docs over the past 7 days).

    Each doc represents one HTTP request hitting the storefront. The mix of
    paths is realistic: heavy on browse, lighter on checkout, a few payment
    retries during the outage.
    """
    docs: List[Dict[str, Any]] = []
    target = 3500

    # Pre-generate timestamps weighted by the traffic curve (rejection sampling).
    horizon_seconds = 7 * 24 * 3600
    headliner_start = headliner["start"]

    # We want to bias mass toward the headliner window and the diurnal peaks.
    timestamps: List[datetime] = []
    while len(timestamps) < target:
        candidate = now - timedelta(seconds=rng.uniform(0, horizon_seconds))
        weight = _traffic_multiplier(candidate, headliner_start)
        if rng.random() * 4.0 < weight:  # accept proportional to weight (max ~3.6)
            timestamps.append(candidate)
    timestamps.sort()

    # Path popularity weights — mostly browse + cart, then a smaller checkout funnel.
    path_weights = [
        ("GET", "/", "Home", 0.10),
        ("GET", "/c/womens-coats", "BrowseCategory", 0.08),
        ("GET", "/c/mens-knitwear", "BrowseCategory", 0.07),
        ("GET", "/p/{sku}", "ProductDetail", 0.16),
        ("POST", "/api/cart/add", "CartAdd", 0.09),
        ("DELETE", "/api/cart/{id}", "CartRemove", 0.03),
        ("GET", "/api/recs/home", "RecsHome", 0.10),
        ("GET", "/api/recs/cart", "RecsCart", 0.06),
        ("POST", "/checkout/begin", "CheckoutBegin", 0.08),
        ("POST", "/checkout/shipping", "CheckoutShipping", 0.06),
        ("POST", "/checkout/payment", "CheckoutPayment", 0.06),
        ("POST", "/checkout/place-order", "CheckoutPlaceOrder", 0.05),
        ("POST", "/api/payment/charge", "PaymentCharge", 0.04),
        ("POST", "/api/payment/retry", "PaymentRetry", 0.02),
    ]
    pw_total = sum(w for _, _, _, w in path_weights)
    path_choices = [(method, path, txn, w / pw_total)
                    for method, path, txn, w in path_weights]

    for ts in timestamps:
        anomaly = _in_any_window(ts, windows)
        method, path, txn_name = _weighted_choice(
            rng, [((m, p, t), w) for m, p, t, w in path_choices])
        # Resolve URL placeholders.
        if "{sku}" in path:
            path = path.replace("{sku}", rng.choice(_SKUS).lower())
        if "{id}" in path:
            path = path.replace("{id}", uuid.uuid4().hex[:12])

        # Latency: which service is on the critical path for this URL?
        if path.startswith("/checkout") or path.startswith("/api/payment") or path.startswith("/api/cart"):
            # Checkout/payment/cart paths go through checkout-svc which depends on checkout-db
            base = _SERVICES["checkout-svc"]
            latency = _heavy_tail_latency(rng, base["p50"], base["p99"], anomaly, is_db=False)
            # Add an extra DB-dependent component if we're in the anomaly window
            if anomaly is not None:
                db = _SERVICES["checkout-db"]
                latency += _heavy_tail_latency(rng, db["p50"], db["p99"], anomaly, is_db=True)
        elif path.startswith("/api/recs"):
            base = _SERVICES["recs-svc"]
            latency = _heavy_tail_latency(rng, base["p50"], base["p99"], None, is_db=False)
        else:
            base = _SERVICES["frontend"]
            latency = _heavy_tail_latency(rng, base["p50"], base["p99"], None, is_db=False)

        # Outcome.
        is_checkout_path = path.startswith("/checkout") or path.startswith("/api/payment")
        in_outage = anomaly is not None
        if in_outage and is_checkout_path:
            # 5xx error rate ramps to 18-22% during the headliner; less for precursors.
            err_p = 0.005 + (0.20 * anomaly["severity"])
        elif in_outage and path.startswith("/api/cart"):
            err_p = 0.003 + (0.07 * anomaly["severity"])
        else:
            err_p = 0.005  # baseline 0.5%

        if rng.random() < err_p:
            status = rng.choice([500, 500, 502, 503, 503, 504])
            outcome = "failure"
            error_message = rng.choice([
                "upstream timeout: checkout-db connection acquire failed after 5000ms",
                "PaymentGatewayTimeout: stripe.api timed out after 15s; retry exhausted",
                "InventoryLockTimeout: redis lock contention on sku=" + rng.choice(_SKUS),
                "504 Gateway Timeout from checkout-svc",
                "checkout-db: deadlock detected on relation 'orders'",
            ])
            error_type = rng.choice([
                "DatabaseConnectionTimeout",
                "PaymentGatewayTimeout",
                "GatewayTimeout",
                "DownstreamUnavailable",
            ])
        elif rng.random() < 0.012:
            status = rng.choice([400, 404])
            outcome = "failure"
            error_message = "client error"
            error_type = "ClientError"
        else:
            status = rng.choice([200, 200, 200, 200, 200, 201, 204])
            outcome = "success"
            error_message = None
            error_type = None

        # Cart fields appear on cart and checkout paths.
        cart_value = None
        cart_items = None
        payment_method = None
        if path.startswith("/api/cart") or path.startswith("/checkout") or path.startswith("/api/payment"):
            cart_value = round(math.exp(rng.gauss(math.log(85.0), 0.7)), 2)
            cart_value = min(max(cart_value, 9.99), 1899.0)
            cart_items = max(1, min(12, int(rng.gauss(2.6, 1.5))))
            if path.startswith("/checkout/payment") or path.startswith("/api/payment"):
                payment_method = _weighted_choice(rng, _PAYMENT_METHODS)

        user = _user(rng)
        host = _host_for(rng, "frontend")
        recs_alg = _RECS_VERSIONS[rng.randrange(len(_RECS_VERSIONS))]

        doc: Dict[str, Any] = {
            "@timestamp": ts.isoformat(),
            "service": {"name": "frontend", "environment": "prod",
                        "version": _SERVICES["frontend"]["version"]},
            "event": {
                "dataset": "lumen.checkout.access",
                "category": ["web"],
                "kind": "event",
                "outcome": outcome,
                "duration": int(latency * 1_000_000),  # nanoseconds, ECS norm
            },
            "http": {
                "request": {"method": method,
                            "referrer": "https://www.google.com/" if rng.random() < 0.4
                                        else f"https://shop.lumenapparel.com/c/womens-coats"},
                "response": {
                    "status_code": status,
                    "bytes": int(rng.uniform(800, 22000)),
                },
                "version": "1.1",
            },
            "url": {
                "path": path,
                "domain": "shop.lumenapparel.com",
                "full": f"https://shop.lumenapparel.com{path}",
                "scheme": "https",
            },
            "user_agent": {"original": rng.choice(_USER_AGENTS)},
            "client": {"ip": f"{rng.randint(24, 223)}.{rng.randint(0, 255)}.{rng.randint(0, 255)}.{rng.randint(1, 254)}"},
            "user": user,
            "host": {"name": host["name"], "region": host["region"]},
            "cloud": {"provider": host["_provider"], "region": host["_region"]},
            "transaction": {
                "id": _span_id(),
                "name": f"{method} {path.split('?')[0]}",
                "type": "request",
                "duration": {"us": int(latency * 1000)},
            },
            "trace": {"id": _trace_id()},
            "recs": {"algorithm_version": recs_alg},
            "lumen": {
                "store": "shop.lumenapparel.com",
                "session_id": uuid.uuid4().hex[:16],
                "promo_applied": rng.choice(_PROMO_CODES) if rng.random() < 0.18 else None,
            },
        }
        if cart_value is not None:
            doc["cart"] = {"value_usd": cart_value, "item_count": cart_items}
        if payment_method:
            doc["payment"] = {"method": payment_method}
        if error_message:
            doc["error"] = {"message": error_message, "type": error_type}
            # On checkout outage, mark the offender for storytelling.
            if anomaly is not None and ("checkout-db" in error_message or "InventoryLock" in error_message):
                doc["error"]["stack_trace_excerpt"] = (
                    "at com.lumen.checkout.OrderRepo.acquire(OrderRepo.java:142)\n"
                    "at com.lumen.checkout.PlaceOrderHandler.run(PlaceOrderHandler.java:88)"
                )

        # Anomaly tag for filtering in the dashboard storytelling panel.
        if anomaly is not None:
            doc["lumen"]["anomaly_window"] = anomaly["label"]

        docs.append(doc)

    return docs


def _gen_apm_traces(rng: random.Random, now: datetime,
                    windows: List[Dict[str, Any]],
                    headliner: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate APM transaction documents per service (~1500 docs).

    Includes parent.id where this is a child span (downstream call), so the
    documents are coherent if a customer wants to drill into trace.id.
    """
    docs: List[Dict[str, Any]] = []
    target = 1500

    # Mass distribution: weight requests across services proportional to call volume.
    service_weights = {
        "frontend": 0.18, "api-gateway": 0.18, "catalog-svc": 0.14,
        "cart-svc": 0.08, "recs-svc": 0.07, "checkout-svc": 0.13,
        "checkout-db": 0.09, "payment-svc": 0.05, "inventory-svc": 0.05,
        "notification-svc": 0.03,
    }
    svc_choices = [(k, v) for k, v in service_weights.items()]

    horizon_seconds = 7 * 24 * 3600
    headliner_start = headliner["start"]

    timestamps: List[datetime] = []
    while len(timestamps) < target:
        candidate = now - timedelta(seconds=rng.uniform(0, horizon_seconds))
        weight = _traffic_multiplier(candidate, headliner_start)
        if rng.random() * 4.0 < weight:
            timestamps.append(candidate)
    timestamps.sort()

    transaction_names_by_service: Dict[str, List[str]] = {
        "frontend": ["GET /", "GET /c/{cat}", "GET /p/{sku}", "GET /cart"],
        "api-gateway": ["POST /api/cart/add", "GET /api/recs/home", "POST /checkout/begin",
                        "POST /checkout/place-order"],
        "catalog-svc": ["catalog.GetCategory", "catalog.GetProduct", "catalog.SearchByTag"],
        "cart-svc": ["cart.Add", "cart.Remove", "cart.GetTotals"],
        "recs-svc": ["recs.HomePage", "recs.PostCart", "recs.PDPSimilar"],
        "checkout-svc": ["POST /place-order", "POST /reserve-inventory",
                         "POST /apply-promo", "POST /confirm"],
        "checkout-db": ["SELECT orders", "INSERT orders", "UPDATE inventory_locks",
                        "SELECT cart_lines", "BEGIN tx"],
        "payment-svc": ["payment.Charge", "payment.Capture", "payment.Refund"],
        "inventory-svc": ["inventory.Reserve", "inventory.Release", "inventory.Get"],
        "notification-svc": ["notification.SendOrderConfirmation",
                             "notification.SendShipmentEmail"],
    }

    for ts in timestamps:
        anomaly = _in_any_window(ts, windows)
        svc = _weighted_choice(rng, svc_choices)
        cfg = _SERVICES[svc]
        is_db = (svc == "checkout-db")
        # Downstream services in the checkout chain see a fraction of the slowness.
        cascading = svc in ("checkout-svc", "payment-svc")
        eff_anomaly = anomaly if (is_db or cascading or svc in ("api-gateway", "cart-svc")) else None

        # Counterfactual: recs-svc, frontend, notification-svc remain healthy.
        if svc in ("recs-svc", "frontend", "notification-svc"):
            eff_anomaly = None

        latency_ms = _heavy_tail_latency(rng, cfg["p50"], cfg["p99"], eff_anomaly, is_db=is_db)

        # Outcome — db elevated failure rate during anomaly; checkout-svc cascades; others mostly fine.
        if is_db and anomaly is not None:
            err_p = 0.18 + 0.05 * anomaly["severity"]
        elif svc == "checkout-svc" and anomaly is not None:
            err_p = 0.10 + 0.10 * anomaly["severity"]
        elif svc == "payment-svc" and anomaly is not None:
            err_p = 0.04 + 0.06 * anomaly["severity"]
        else:
            err_p = 0.004

        is_failure = rng.random() < err_p
        outcome = "failure" if is_failure else "success"
        result = "HTTP 5xx" if is_failure else "HTTP 2xx"
        if is_db:
            result = "ERROR" if is_failure else "OK"

        txn_name = rng.choice(transaction_names_by_service[svc])
        host = _host_for(rng, svc)
        trace_id = _trace_id()
        span_id = _span_id()
        parent_id = _span_id() if svc not in ("frontend",) else None

        # Build the span/event structure. ECS APM has both transaction.* and span.*
        # for self-contained docs we use transaction.* as the canonical type.
        doc: Dict[str, Any] = {
            "@timestamp": ts.isoformat(),
            "service": {
                "name": svc,
                "environment": "prod",
                "version": cfg["version"],
                "language": {"name": cfg["language"]},
                "runtime": {"name": cfg["runtime"]},
                "node": {"name": host["pod_name"]},
            },
            "host": {"name": host["name"], "region": host["region"]},
            "cloud": {"provider": host["_provider"], "region": host["_region"]},
            "agent": {"name": "elastic-apm-node" if cfg["language"] == "typescript"
                              else f"elastic-apm-{cfg['language']}", "version": "4.4.1"},
            "processor": {"event": "transaction", "name": "transaction"},
            "transaction": {
                "id": span_id,
                "name": txn_name,
                "type": "db" if is_db else ("request" if svc in ("frontend", "api-gateway") else "messaging"
                                            if svc == "notification-svc" else "request"),
                "duration": {"us": int(latency_ms * 1000)},
                "result": result,
                "sampled": True,
            },
            "trace": {"id": trace_id},
            "event": {
                "outcome": outcome,
                "dataset": "apm.transaction",
                "duration": int(latency_ms * 1_000_000),
            },
        }
        if parent_id:
            doc["parent"] = {"id": parent_id}

        if is_db:
            doc["span"] = {
                "id": span_id,
                "type": "db",
                "subtype": "postgresql",
                "action": "query",
                "destination": {"service": {"resource": "postgresql/lumen_orders_writer"}},
                "db": {
                    "instance": "lumen_orders_writer",
                    "type": "postgresql",
                    "statement": rng.choice([
                        "SELECT id, total_cents, status FROM orders WHERE user_id = $1 AND status = 'pending'",
                        "INSERT INTO orders (id, user_id, total_cents, status) VALUES ($1, $2, $3, 'pending')",
                        "UPDATE inventory_locks SET held_until = NOW() + INTERVAL '5 min' WHERE sku = $1",
                        "SELECT line.id, line.sku, line.qty FROM cart_lines line WHERE cart_id = $1",
                        "BEGIN; SELECT pg_advisory_xact_lock($1)",
                    ]),
                },
            }
            if anomaly is not None:
                # IO contention indicators
                doc["postgres"] = {
                    "wait_event_type": rng.choice(["IO", "IO", "IO", "Lock", "BufferPin"]),
                    "wait_event": rng.choice(["DataFileRead", "DataFileWrite",
                                              "WALWriteLock", "BufferContent"]),
                    "io_read_blocks": int(rng.gauss(8500, 1800)),
                }

        if outcome == "failure":
            if is_db:
                doc["error"] = {
                    "type": rng.choice(["DeadlockDetected", "ConnectionTimeout",
                                        "WaitEventTimeout"]),
                    "message": rng.choice([
                        "could not obtain lock on relation 'orders' within 5000ms",
                        "deadlock detected (process 14732 waits for ShareLock on transaction 9912)",
                        "connection slot reservation timeout: max_connections=500",
                    ]),
                    "id": uuid.uuid4().hex[:12],
                }
            elif svc == "checkout-svc":
                doc["error"] = {
                    "type": "DownstreamUnavailable",
                    "message": "checkout-db pool exhausted; falling back failed after 3 retries",
                    "id": uuid.uuid4().hex[:12],
                }
            elif svc == "payment-svc":
                doc["error"] = {
                    "type": "PaymentGatewayTimeout",
                    "message": "stripe.api charge_intent timed out after 15s",
                    "id": uuid.uuid4().hex[:12],
                }
            else:
                doc["error"] = {
                    "type": "InternalError",
                    "message": "unexpected internal error during request",
                    "id": uuid.uuid4().hex[:12],
                }

        if anomaly is not None and (is_db or svc == "checkout-svc"):
            doc.setdefault("labels", {})["anomaly_window"] = anomaly["label"]

        docs.append(doc)

    return docs


def _gen_metrics_rollups(rng: random.Random, now: datetime,
                         windows: List[Dict[str, Any]],
                         headliner: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Per-service 5-minute metric rollups.

    For each service, emit a rollup every 5 minutes for the last 24 hours
    (288 buckets) or every 30 minutes for the prior 6 days (288 buckets) — but
    we cap the total at ~600 docs.

    Each rollup includes:
      - latency.p50_ms, p95_ms, p99_ms
      - error_rate (0..1)
      - cpu_utilization, mem_utilization
      - connection_pool.in_use, connection_pool.max
      - request_count
      - cart_abandonment_rate, payment_success_rate (only for checkout-svc)
    """
    docs: List[Dict[str, Any]] = []
    services = list(_SERVICES.keys())

    # Build a coarse + fine bucket grid that totals ~600 docs.
    fine_buckets = 30  # last ~5 hours, every 10 min, x 10 services = 300 docs
    coarse_buckets = 30  # prior 6.8 days, every ~5h, x 10 services = 300 docs

    now_floor = now.replace(second=0, microsecond=0)
    now_floor = now_floor - timedelta(minutes=now_floor.minute % 10)

    fine_starts = [now_floor - timedelta(minutes=10 * i) for i in range(fine_buckets)]
    horizon_start = now - timedelta(days=7)
    coarse_step = (now_floor - timedelta(hours=5) - horizon_start) / max(coarse_buckets - 1, 1)
    coarse_starts = [horizon_start + coarse_step * i for i in range(coarse_buckets)]

    bucket_starts = sorted(set(fine_starts + coarse_starts))

    for bstart in bucket_starts:
        anomaly = _in_any_window(bstart, windows)
        for svc in services:
            cfg = _SERVICES[svc]
            is_db = (svc == "checkout-db")
            cascading = svc in ("checkout-svc", "payment-svc")

            # Counterfactual healthy services
            healthy = svc in ("recs-svc", "frontend", "notification-svc")
            eff_anomaly = anomaly if (not healthy and (is_db or cascading or
                                       svc in ("api-gateway", "cart-svc"))) else None

            # Sample latency percentiles via repeated draws (cheap, realistic).
            samples = sorted([
                _heavy_tail_latency(rng, cfg["p50"], cfg["p99"], eff_anomaly, is_db=is_db)
                for _ in range(80)
            ])
            p50 = samples[40]
            p95 = samples[76]
            p99 = samples[78]

            # Request count — diurnal+headliner shaped
            mult = _traffic_multiplier(bstart, headliner["start"])
            base_rps = {
                "frontend": 320, "api-gateway": 320, "catalog-svc": 220,
                "cart-svc": 180, "recs-svc": 140, "checkout-svc": 110,
                "checkout-db": 260, "payment-svc": 60, "inventory-svc": 90,
                "notification-svc": 40,
            }[svc]
            req_count = int(base_rps * mult * (300 / 60))  # 5-min bucket
            # Add Poisson noise
            req_count = max(0, int(rng.gauss(req_count, req_count * 0.08)))

            # Error rate
            if eff_anomaly is not None and is_db:
                err_rate = 0.05 + 0.18 * eff_anomaly["severity"] + rng.uniform(-0.02, 0.04)
            elif eff_anomaly is not None and svc == "checkout-svc":
                err_rate = 0.04 + 0.18 * eff_anomaly["severity"] + rng.uniform(-0.01, 0.04)
            elif eff_anomaly is not None and svc == "payment-svc":
                err_rate = 0.02 + 0.10 * eff_anomaly["severity"] + rng.uniform(-0.01, 0.03)
            else:
                err_rate = 0.005 + abs(rng.gauss(0.0, 0.003))
            err_rate = max(0.0, min(0.5, err_rate))

            # Resource utilisation
            if is_db and anomaly is not None:
                cpu = 0.78 + 0.15 * anomaly["severity"] + rng.uniform(-0.04, 0.04)
                mem = 0.72 + 0.10 * anomaly["severity"] + rng.uniform(-0.03, 0.03)
                pool_in_use = int(490 + 8 * rng.random())
                pool_max = 500
                io_wait = 0.45 + 0.30 * anomaly["severity"] + rng.uniform(-0.05, 0.05)
            elif is_db:
                cpu = 0.32 + abs(rng.gauss(0.0, 0.06))
                mem = 0.55 + abs(rng.gauss(0.0, 0.04))
                pool_in_use = int(160 + rng.gauss(0, 30))
                pool_max = 500
                io_wait = 0.05 + abs(rng.gauss(0.0, 0.02))
            elif healthy:
                cpu = 0.38 + abs(rng.gauss(0.0, 0.08))
                mem = 0.45 + abs(rng.gauss(0.0, 0.05))
                pool_in_use = 0
                pool_max = 0
                io_wait = 0.0
            else:
                cpu = 0.42 + abs(rng.gauss(0.0, 0.08))
                if anomaly is not None and cascading:
                    cpu += 0.18 * anomaly["severity"]
                mem = 0.50 + abs(rng.gauss(0.0, 0.05))
                pool_in_use = 0
                pool_max = 0
                io_wait = 0.0

            doc: Dict[str, Any] = {
                "@timestamp": bstart.isoformat(),
                "service": {"name": svc, "environment": "prod",
                            "version": cfg["version"]},
                "event": {"dataset": "lumen.metrics.service",
                          "module": "service-rollup", "kind": "metric"},
                "metricset": {"name": "service_rollup",
                              "interval": "5m" if bstart in fine_starts else "5h"},
                "latency": {
                    "p50_ms": round(p50, 2),
                    "p95_ms": round(p95, 2),
                    "p99_ms": round(p99, 2),
                },
                "transaction": {
                    "duration": {"us": int(p50 * 1000)},
                    "p99": {"us": int(p99 * 1000)},
                },
                "request": {"count": req_count},
                "error": {"rate": round(err_rate, 4),
                          "count": int(req_count * err_rate)},
                "system": {
                    "cpu": {"utilization": round(min(0.99, cpu), 3)},
                    "memory": {"utilization": round(min(0.99, mem), 3)},
                },
                "io": {"wait_ratio": round(io_wait, 3)},
            }
            if pool_max:
                doc["connection_pool"] = {
                    "in_use": max(0, pool_in_use),
                    "max": pool_max,
                    "utilization": round(min(1.0, pool_in_use / pool_max), 3),
                }

            # checkout funnel KPIs — only on checkout-svc, the customer-facing measure.
            if svc == "checkout-svc":
                if anomaly is not None:
                    abandonment = 0.30 + 0.27 * anomaly["severity"] + rng.uniform(-0.03, 0.05)
                    payment_success = 0.74 - 0.20 * anomaly["severity"] + rng.uniform(-0.04, 0.03)
                else:
                    abandonment = 0.28 + abs(rng.gauss(0.0, 0.02))
                    payment_success = 0.96 + rng.uniform(-0.02, 0.01)
                doc["funnel"] = {
                    "cart_abandonment_rate": round(max(0.0, min(0.85, abandonment)), 4),
                    "payment_success_rate": round(max(0.0, min(1.0, payment_success)), 4),
                }

            if anomaly is not None and not healthy:
                doc.setdefault("labels", {})["anomaly_window"] = anomaly["label"]

            docs.append(doc)

    # Trim or extend roughly to target 600 docs.
    if len(docs) > 700:
        docs = docs[:700]
    return docs


# ============================================================ Public functions ====


def get_mappings() -> Dict[str, Dict[str, Any]]:
    """Index mappings — keyword for high-cardinality strings, date for @timestamp,
    long for counts, double for floats. Avoids dynamic mapping pitfalls (status_code
    being inferred as long+keyword inconsistently)."""
    common_props: Dict[str, Any] = {
        "@timestamp": {"type": "date"},
        "service": {
            "properties": {
                "name": {"type": "keyword"},
                "environment": {"type": "keyword"},
                "version": {"type": "keyword"},
                "language": {"properties": {"name": {"type": "keyword"}}},
                "runtime": {"properties": {"name": {"type": "keyword"}}},
                "node": {"properties": {"name": {"type": "keyword"}}},
            },
        },
        "host": {
            "properties": {
                "name": {"type": "keyword"},
                "region": {"type": "keyword"},
            },
        },
        "cloud": {
            "properties": {
                "provider": {"type": "keyword"},
                "region": {"type": "keyword"},
            },
        },
        "event": {
            "properties": {
                "outcome": {"type": "keyword"},
                "dataset": {"type": "keyword"},
                "category": {"type": "keyword"},
                "kind": {"type": "keyword"},
                "duration": {"type": "long"},
                "module": {"type": "keyword"},
            },
        },
        "labels": {"type": "object", "dynamic": True},
        "lumen": {
            "properties": {
                "store": {"type": "keyword"},
                "session_id": {"type": "keyword"},
                "promo_applied": {"type": "keyword"},
                "anomaly_window": {"type": "keyword"},
            },
        },
    }

    checkout_props = {
        **common_props,
        "http": {
            "properties": {
                "request": {
                    "properties": {
                        "method": {"type": "keyword"},
                        "referrer": {"type": "keyword"},
                    },
                },
                "response": {
                    "properties": {
                        "status_code": {"type": "long"},
                        "bytes": {"type": "long"},
                    },
                },
                "version": {"type": "keyword"},
            },
        },
        "url": {
            "properties": {
                "path": {"type": "keyword"},
                "domain": {"type": "keyword"},
                "full": {"type": "keyword"},
                "scheme": {"type": "keyword"},
            },
        },
        "user_agent": {
            "properties": {
                "original": {"type": "keyword"},
            },
        },
        "client": {
            "properties": {
                "ip": {"type": "ip"},
            },
        },
        "user": {
            "properties": {
                "id": {"type": "keyword"},
                "email": {"type": "keyword"},
                "name": {"type": "keyword"},
                "geo": {
                    "properties": {"country_iso_code": {"type": "keyword"}},
                },
            },
        },
        "transaction": {
            "properties": {
                "id": {"type": "keyword"},
                "name": {"type": "keyword"},
                "type": {"type": "keyword"},
                "duration": {"properties": {"us": {"type": "long"}}},
            },
        },
        "trace": {"properties": {"id": {"type": "keyword"}}},
        "recs": {"properties": {"algorithm_version": {"type": "keyword"}}},
        "cart": {
            "properties": {
                "value_usd": {"type": "double"},
                "item_count": {"type": "long"},
            },
        },
        "payment": {"properties": {"method": {"type": "keyword"}}},
        "error": {
            "properties": {
                "message": {"type": "text"},
                "type": {"type": "keyword"},
                "stack_trace_excerpt": {"type": "text"},
            },
        },
    }

    apm_props = {
        **common_props,
        "agent": {
            "properties": {
                "name": {"type": "keyword"},
                "version": {"type": "keyword"},
            },
        },
        "processor": {
            "properties": {
                "event": {"type": "keyword"},
                "name": {"type": "keyword"},
            },
        },
        "transaction": {
            "properties": {
                "id": {"type": "keyword"},
                "name": {"type": "keyword"},
                "type": {"type": "keyword"},
                "duration": {"properties": {"us": {"type": "long"}}},
                "result": {"type": "keyword"},
                "sampled": {"type": "boolean"},
            },
        },
        "span": {
            "properties": {
                "id": {"type": "keyword"},
                "type": {"type": "keyword"},
                "subtype": {"type": "keyword"},
                "action": {"type": "keyword"},
                "destination": {
                    "properties": {
                        "service": {
                            "properties": {"resource": {"type": "keyword"}},
                        },
                    },
                },
                "db": {
                    "properties": {
                        "instance": {"type": "keyword"},
                        "type": {"type": "keyword"},
                        "statement": {"type": "text"},
                    },
                },
            },
        },
        "trace": {"properties": {"id": {"type": "keyword"}}},
        "parent": {"properties": {"id": {"type": "keyword"}}},
        "postgres": {
            "properties": {
                "wait_event_type": {"type": "keyword"},
                "wait_event": {"type": "keyword"},
                "io_read_blocks": {"type": "long"},
            },
        },
        "error": {
            "properties": {
                "type": {"type": "keyword"},
                "message": {"type": "text"},
                "id": {"type": "keyword"},
            },
        },
    }

    metrics_props = {
        **common_props,
        "metricset": {
            "properties": {
                "name": {"type": "keyword"},
                "interval": {"type": "keyword"},
            },
        },
        "latency": {
            "properties": {
                "p50_ms": {"type": "double"},
                "p95_ms": {"type": "double"},
                "p99_ms": {"type": "double"},
            },
        },
        "transaction": {
            "properties": {
                "duration": {"properties": {"us": {"type": "long"}}},
                "p99": {"properties": {"us": {"type": "long"}}},
            },
        },
        "request": {"properties": {"count": {"type": "long"}}},
        "error": {
            "properties": {
                "rate": {"type": "double"},
                "count": {"type": "long"},
            },
        },
        "system": {
            "properties": {
                "cpu": {"properties": {"utilization": {"type": "double"}}},
                "memory": {"properties": {"utilization": {"type": "double"}}},
            },
        },
        "io": {"properties": {"wait_ratio": {"type": "double"}}},
        "connection_pool": {
            "properties": {
                "in_use": {"type": "long"},
                "max": {"type": "long"},
                "utilization": {"type": "double"},
            },
        },
        "funnel": {
            "properties": {
                "cart_abandonment_rate": {"type": "double"},
                "payment_success_rate": {"type": "double"},
            },
        },
    }

    return {
        INDICES["checkout"]: {"properties": checkout_props},
        INDICES["apm"]: {"properties": apm_props},
        INDICES["metrics"]: {"properties": metrics_props},
    }


def generate_documents(seed: int = _DEFAULT_SEED) -> Dict[str, List[Dict[str, Any]]]:
    """Generate the three index payloads. Deterministic for a given seed."""
    rng = random.Random(seed)
    random.seed(seed)
    now = _now_anchor()
    windows = _anomaly_windows(now)
    headliner = windows[-1]

    log.info("black_friday.generate.start",
             windows=[w["label"] for w in windows], anchor=now.isoformat())

    checkout_docs = _gen_checkout_logs(rng, now, windows, headliner)
    apm_docs = _gen_apm_traces(rng, now, windows, headliner)
    metrics_docs = _gen_metrics_rollups(rng, now, windows, headliner)

    log.info("black_friday.generate.done",
             checkout=len(checkout_docs), apm=len(apm_docs), metrics=len(metrics_docs))

    return {
        INDICES["checkout"]: checkout_docs,
        INDICES["apm"]: apm_docs,
        INDICES["metrics"]: metrics_docs,
    }


# ============================================================ Vega specs ==========


def _spec_p99_by_service() -> Dict[str, Any]:
    """Vega-Lite line chart of p99 latency per service over time, with a 1-second
    SLO threshold rule. Pulls the precomputed latency.p99_ms field from the
    metrics index, so we don't have to ask Kibana to compute percentiles
    client-side. Anomaly band overlay highlights the headliner window."""
    body = {
        "size": 0,
        "query": {
            "bool": {
                "must": [{"match_all": {}}],
                "filter": [{"match_all": {}}],
            },
        },
        "aggs": {
            "time": {
                "date_histogram": {
                    "field": "@timestamp",
                    "fixed_interval": "10m",
                    "min_doc_count": 0,
                    "extended_bounds": {"min": "{{timefilter.from}}",
                                        "max": "{{timefilter.to}}"},
                },
                "aggs": {
                    "by_service": {
                        "terms": {"field": "service.name", "size": 10},
                        "aggs": {
                            "p99": {"avg": {"field": "latency.p99_ms"}},
                        },
                    },
                },
            },
        },
    }

    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": {
            "text": "p99 latency by service — 10m buckets",
            "subtitle": "checkout-db is the villain. Healthy services (recs-svc, frontend) stay flat.",
            "color": "#e6e8eb",
            "subtitleColor": "#9aa0a6",
        },
        "data": {
            "url": {
                "%context%": True,
                "%timefield%": "@timestamp",
                "index": INDICES["metrics"],
                "body": body,
            },
            "format": {"property": "aggregations.time.buckets"},
        },
        "transform": [
            {"flatten": ["by_service.buckets"], "as": ["sub"]},
            {"calculate": "datum.key", "as": "ts"},
            {"calculate": "datum.sub.key", "as": "service"},
            {"calculate": "datum.sub.p99.value", "as": "p99_ms"},
            {"filter": "datum.p99_ms != null"},
        ],
        "layer": [
            {
                "mark": {"type": "line", "interpolate": "monotone", "strokeWidth": 2,
                         "point": {"filled": True, "size": 30}},
                "encoding": {
                    "x": {"field": "ts", "type": "temporal", "title": None,
                          "axis": {"labelColor": "#cfd2d6", "titleColor": "#cfd2d6",
                                   "format": "%a %H:%M"}},
                    "y": {"field": "p99_ms", "type": "quantitative",
                          "title": "p99 (ms)",
                          "scale": {"type": "log", "domainMin": 30},
                          "axis": {"labelColor": "#cfd2d6", "titleColor": "#cfd2d6"}},
                    "color": {
                        "field": "service",
                        "type": "nominal",
                        "title": "service",
                        "scale": {
                            "domain": [
                                "checkout-db", "checkout-svc", "payment-svc", "api-gateway",
                                "cart-svc", "catalog-svc", "inventory-svc",
                                "recs-svc", "frontend", "notification-svc",
                            ],
                            "range": [
                                "#e85b5b", "#f4a35a", "#f6cf60", "#7d8cf2",
                                "#7fc4ec", "#7ad6c1", "#9bd17f",
                                "#a5cb7d", "#9aa0a6", "#c8a4f0",
                            ],
                        },
                        "legend": {"labelColor": "#cfd2d6", "titleColor": "#cfd2d6",
                                   "orient": "right"},
                    },
                    "tooltip": [
                        {"field": "ts", "type": "temporal", "title": "time",
                         "format": "%a %H:%M"},
                        {"field": "service", "type": "nominal"},
                        {"field": "p99_ms", "type": "quantitative", "format": ".0f",
                         "title": "p99 (ms)"},
                    ],
                },
            },
            {
                "data": {"values": [{"slo": 1000}]},
                "mark": {"type": "rule", "color": "#ff5252", "strokeDash": [6, 4],
                         "strokeWidth": 2},
                "encoding": {
                    "y": {"field": "slo", "type": "quantitative"},
                },
            },
            {
                "data": {"values": [
                    {"label": "1s SLO", "y": 1000, "x": "{{timefilter.from}}"}]},
                "mark": {"type": "text", "align": "left", "dx": 4, "dy": -4,
                         "color": "#ff5252", "fontSize": 11},
                "encoding": {
                    "x": {"field": "x", "type": "temporal"},
                    "y": {"field": "y", "type": "quantitative"},
                    "text": {"field": "label", "type": "nominal"},
                },
            },
        ],
        "config": {
            "background": "transparent",
            "view": {"stroke": "transparent"},
            "axis": {"labelColor": "#cfd2d6", "titleColor": "#cfd2d6",
                     "gridColor": "#2a2d33"},
            "legend": {"labelColor": "#cfd2d6", "titleColor": "#cfd2d6"},
        },
    }


def _spec_errors_stacked() -> Dict[str, Any]:
    """Stacked bar of error count per service per 15-minute bucket, sourced
    from the APM index."""
    body = {
        "size": 0,
        "query": {
            "bool": {
                "must": [{"term": {"event.outcome": "failure"}}],
                "filter": [{"match_all": {}}],
            },
        },
        "aggs": {
            "time": {
                "date_histogram": {
                    "field": "@timestamp",
                    "fixed_interval": "30m",
                    "min_doc_count": 0,
                    "extended_bounds": {"min": "{{timefilter.from}}",
                                        "max": "{{timefilter.to}}"},
                },
                "aggs": {
                    "by_service": {
                        "terms": {"field": "service.name", "size": 10},
                    },
                },
            },
        },
    }

    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": {
            "text": "Errors by service over time — 30m buckets",
            "subtitle": "Stacked errors. Watch the headliner spike. checkout-svc, payment-svc and checkout-db light up together.",
            "color": "#e6e8eb",
            "subtitleColor": "#9aa0a6",
        },
        "data": {
            "url": {
                "%context%": True,
                "%timefield%": "@timestamp",
                "index": INDICES["apm"],
                "body": body,
            },
            "format": {"property": "aggregations.time.buckets"},
        },
        "transform": [
            {"flatten": ["by_service.buckets"], "as": ["sub"]},
            {"calculate": "datum.key", "as": "ts"},
            {"calculate": "datum.sub.key", "as": "service"},
            {"calculate": "datum.sub.doc_count", "as": "errors"},
        ],
        "mark": {"type": "bar", "tooltip": True},
        "encoding": {
            "x": {"field": "ts", "type": "temporal", "title": None,
                  "axis": {"format": "%a %H:%M", "labelColor": "#cfd2d6",
                           "titleColor": "#cfd2d6"}},
            "y": {"field": "errors", "type": "quantitative", "title": "errors",
                  "axis": {"labelColor": "#cfd2d6", "titleColor": "#cfd2d6"}},
            "color": {
                "field": "service",
                "type": "nominal",
                "scale": {
                    "domain": [
                        "checkout-db", "checkout-svc", "payment-svc",
                        "api-gateway", "cart-svc", "catalog-svc",
                        "inventory-svc", "recs-svc", "frontend",
                        "notification-svc",
                    ],
                    "range": [
                        "#e85b5b", "#f4a35a", "#f6cf60", "#7d8cf2",
                        "#7fc4ec", "#7ad6c1", "#9bd17f",
                        "#a5cb7d", "#9aa0a6", "#c8a4f0",
                    ],
                },
                "legend": {"labelColor": "#cfd2d6", "titleColor": "#cfd2d6"},
            },
            "tooltip": [
                {"field": "ts", "type": "temporal", "title": "time",
                 "format": "%a %H:%M"},
                {"field": "service", "type": "nominal"},
                {"field": "errors", "type": "quantitative"},
            ],
        },
        "config": {
            "background": "transparent",
            "view": {"stroke": "transparent"},
            "axis": {"gridColor": "#2a2d33"},
        },
    }


def _spec_outage_kpi() -> Dict[str, Any]:
    """Lightweight Vega text panel: peak p99 in seconds + total errors during
    the last 24h. We render it as a Vega-Lite text mark for portability —
    Lens metric saved-objects need a data view ID and are migration-fragile."""
    body_p99 = {
        "size": 0,
        "query": {"bool": {"filter": [
            {"term": {"service.name": "checkout-db"}},
            {"range": {"@timestamp": {"gte": "now-24h"}}},
        ]}},
        "aggs": {"max_p99": {"max": {"field": "latency.p99_ms"}}},
    }
    body_errors = {
        "size": 0,
        "query": {"bool": {"filter": [
            {"term": {"event.outcome": "failure"}},
            {"range": {"@timestamp": {"gte": "now-24h"}}},
        ]}},
    }
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": {"text": "Outage KPIs (last 24h)",
                  "color": "#e6e8eb"},
        "vconcat": [
            {
                "title": {"text": "checkout-db peak p99",
                          "color": "#9aa0a6", "fontSize": 11},
                "data": {
                    "url": {
                        "%context%": False,
                        "index": INDICES["metrics"],
                        "body": body_p99,
                    },
                    "format": {"property": "aggregations"},
                },
                "transform": [
                    {"calculate": "datum.max_p99.value / 1000.0", "as": "value_s"},
                    {"calculate": "format(datum.value_s, '.2f') + ' s'", "as": "label"},
                ],
                "mark": {"type": "text", "fontSize": 42, "fontWeight": "bold",
                         "color": "#e85b5b", "align": "center"},
                "encoding": {"text": {"field": "label", "type": "nominal"}},
            },
            {
                "title": {"text": "Errors (count)", "color": "#9aa0a6", "fontSize": 11},
                "data": {
                    "url": {
                        "%context%": False,
                        "index": INDICES["apm"],
                        "body": body_errors,
                    },
                    "format": {"property": "hits"},
                },
                "transform": [
                    {"calculate": "datum.total.value", "as": "value"},
                    {"calculate": "format(datum.value, ',') + ' failures'", "as": "label"},
                ],
                "mark": {"type": "text", "fontSize": 28, "fontWeight": "bold",
                         "color": "#f4a35a", "align": "center"},
                "encoding": {"text": {"field": "label", "type": "nominal"}},
            },
        ],
        "config": {"background": "transparent", "view": {"stroke": "transparent"}},
    }


def _spec_funnel() -> Dict[str, Any]:
    """Cart abandonment rate vs payment success rate over time, dual-line.
    Sourced from the metrics index, scoped to checkout-svc."""
    body = {
        "size": 0,
        "query": {"bool": {"filter": [
            {"term": {"service.name": "checkout-svc"}},
        ]}},
        "aggs": {
            "time": {
                "date_histogram": {
                    "field": "@timestamp",
                    "fixed_interval": "30m",
                    "min_doc_count": 0,
                    "extended_bounds": {"min": "{{timefilter.from}}",
                                        "max": "{{timefilter.to}}"},
                },
                "aggs": {
                    "abandon": {"avg": {"field": "funnel.cart_abandonment_rate"}},
                    "success": {"avg": {"field": "funnel.payment_success_rate"}},
                },
            },
        },
    }
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": {
            "text": "Customer-impact funnel: abandonment vs payment success",
            "subtitle": "Abandonment doubles from 28% to 55% during the headliner. Payment success collapses to 50%.",
            "color": "#e6e8eb",
            "subtitleColor": "#9aa0a6",
        },
        "data": {
            "url": {
                "%context%": True,
                "%timefield%": "@timestamp",
                "index": INDICES["metrics"],
                "body": body,
            },
            "format": {"property": "aggregations.time.buckets"},
        },
        "transform": [
            {"calculate": "datum.key", "as": "ts"},
            {"calculate": "datum.abandon.value", "as": "abandonment_rate"},
            {"calculate": "datum.success.value", "as": "payment_success_rate"},
            {"fold": ["abandonment_rate", "payment_success_rate"],
             "as": ["metric", "rate"]},
            {"filter": "datum.rate != null"},
        ],
        "mark": {"type": "line", "interpolate": "monotone", "strokeWidth": 2.5,
                 "point": {"filled": True, "size": 40}},
        "encoding": {
            "x": {"field": "ts", "type": "temporal", "title": None,
                  "axis": {"format": "%a %H:%M", "labelColor": "#cfd2d6",
                           "titleColor": "#cfd2d6"}},
            "y": {"field": "rate", "type": "quantitative", "title": "rate",
                  "axis": {"format": ".0%", "labelColor": "#cfd2d6",
                           "titleColor": "#cfd2d6"},
                  "scale": {"domain": [0, 1]}},
            "color": {
                "field": "metric",
                "type": "nominal",
                "scale": {
                    "domain": ["abandonment_rate", "payment_success_rate"],
                    "range": ["#e85b5b", "#7ad6c1"],
                },
                "legend": {"labelColor": "#cfd2d6", "titleColor": "#cfd2d6"},
            },
            "tooltip": [
                {"field": "ts", "type": "temporal", "title": "time",
                 "format": "%a %H:%M"},
                {"field": "metric", "type": "nominal"},
                {"field": "rate", "type": "quantitative", "format": ".1%"},
            ],
        },
        "config": {
            "background": "transparent",
            "view": {"stroke": "transparent"},
            "axis": {"gridColor": "#2a2d33"},
        },
    }


# ============================================================ Dashboard panels ====


def _markdown_panel(panel_id: str, x: int, y: int, w: int, h: int, markdown: str,
                    title: str = "") -> Dict[str, Any]:
    """Markdown panel wrapped as a legacy `visualization` embeddable so Kibana 9.x renders it."""
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
                "data": {"aggs": [],
                         "searchSource": {"query": {"language": "kuery", "query": ""},
                                          "filter": []}},
            },
        },
        "title": title,
    }


def get_dashboard_panels() -> List[Dict[str, Any]]:
    """Six panels in a 48-wide grid. All charts are Vega-Lite for portability."""
    md_header = (
        "## Black Friday Outage — Lumen Apparel\n\n"
        "**The story.** It is Black Friday at Lumen Apparel. Traffic is 3.4x normal. "
        "At **10:00am PT** the catalog page-size change shipped on Tuesday starts hammering "
        "`checkout-db` with a 12x query plan; the database falls into IO contention; p99 "
        "latency on the DB jumps from **180ms baseline to 4–8 seconds**; `checkout-svc` "
        "starts surfacing 5xx; `payment-svc` retries cascade. Cart abandonment doubles "
        "from 28% to 55%. **At 11:30am PT** SRE rolls back the catalog config and "
        "everything snaps back inside one bucket.\n\n"
        "**What this dashboard proves.**  This is *not* a system-wide outage. "
        "`recs-svc`, `frontend`, and `notification-svc` stay flat throughout — the failure "
        "is localised to the checkout writer DB and its dependents. That is the whole "
        "point of a service-aware observability platform.\n\n"
        "**Customer talk-track.**  *Three Elastic features would have caught this earlier:* "
        "(1) **APM service maps** — visualises that `catalog-svc` was driving load to "
        "`checkout-db` 48 hours before the outage; "
        "(2) **Elastic ML anomaly detection** — flags the p99 distribution shift in the "
        "first precursor window 6 days ago; "
        "(3) **SLO burn-rate alerts** — would page on the 4 hour burn-rate breach during "
        "the dress-rehearsal precursor at T-2d. Combined, the team would have seen "
        "the warning, pinpointed the change, and avoided **~$1.4M of lost GMV** during "
        "the headline window."
    )

    md_followup = (
        "## How this becomes a customer conversation\n\n"
        "**MEDDPICC pain & metrics surfaced by this scenario:**\n\n"
        "- **Metrics**  — Lost GMV per minute of checkout downtime; cart abandonment baseline vs peak; p99 SLO breach minutes\n"
        "- **Economic Buyer pain**  — \"We had four near-misses in the week before BF and didn't know.\" Detection time = 0 with anomaly ML\n"
        "- **Decision Criteria**  — APM + Logs + SIEM + ML in one license; no per-host gotcha; ECS taxonomy across services\n"
        "- **Champion enablement**  — Service maps, anomaly explorer, SLO burn rate dashboards out of the box; no Splunk SPL rewrite\n"
        "- **Identify pain**  — Today their tool was Datadog APM; logs were in Splunk; correlation across the two was manual\n"
        "- **Competition**  — Splunk ITSI ($$$, slow rollout), Datadog APM (no log/SIEM unification), New Relic (per-seat)\n\n"
        "**Call to action.**  *Schedule a 30-minute live APM walkthrough on the customer's "
        "own services next week.* We will set up an Elastic Cloud trial with "
        "their staging traffic mirrored in, and reproduce this exact dashboard in "
        "their environment within the trial.\n"
    )

    panels = [
        _markdown_panel("hdr", 0, 0, 48, 8, md_header,
                        "Black Friday outage — story & talk track"),
        _vega_panel("p99", 0, 8, 24, 14,
                    "p99 latency by service", _spec_p99_by_service()),
        _vega_panel("err", 24, 8, 24, 14,
                    "Errors by service over time", _spec_errors_stacked()),
        _vega_panel("kpi", 0, 22, 12, 10,
                    "Outage KPIs", _spec_outage_kpi()),
        _vega_panel("funnel", 12, 22, 36, 14,
                    "Funnel: abandonment vs payment success", _spec_funnel()),
        _markdown_panel("nar", 0, 36, 48, 10, md_followup,
                        "Customer conversation & MEDDPICC"),
    ]
    return panels


# ============================================================ Seeder ===============


def _kbn_url(path: str) -> str:
    return settings.kibana_url.rstrip("/") + path


def _kbn_headers() -> Dict[str, str]:
    return {
        "Authorization": f"ApiKey {settings.kibana_api_key}",
        "Content-Type": "application/json",
        "kbn-xsrf": "fe-copilot",
    }


def _delete_dashboard() -> bool:
    url = _kbn_url(f"/api/saved_objects/dashboard/{DASHBOARD_ID}")
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.delete(url, headers=_kbn_headers())
        return resp.status_code < 400 or resp.status_code == 404
    except Exception as exc:
        log.warning("black_friday.dashboard.delete.exception", error=str(exc))
        return False


def _create_dashboard() -> Tuple[str, str]:
    panels = get_dashboard_panels()
    panels_json = json.dumps(panels, ensure_ascii=False)
    options_json = json.dumps({
        "useMargins": True,
        "hidePanelTitles": False,
        "syncColors": True,
        "syncCursor": True,
        "syncTooltips": True,
    })
    search_source_json = json.dumps({"query": {"language": "kuery", "query": ""},
                                     "filter": []})
    body = [{
        "id": DASHBOARD_ID,
        "type": "dashboard",
        "attributes": {
            "title": f"FE Copilot Demo · {SCENARIO_TITLE}",
            "description": SCENARIO_DESCRIPTION,
            "panelsJSON": panels_json,
            "optionsJSON": options_json,
            "timeRestore": True,
            "timeFrom": "now-7d",
            "timeTo": "now",
            "refreshInterval": {"pause": True, "value": 0},
            "version": 1,
            "kibanaSavedObjectMeta": {"searchSourceJSON": search_source_json},
        },
    }]

    url = _kbn_url("/api/saved_objects/_bulk_create?overwrite=true")
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(url, headers=_kbn_headers(), json=body)
    if resp.status_code >= 400:
        raise RuntimeError(
            f"Kibana dashboard create failed: {resp.status_code} {resp.text[:400]}"
        )
    dashboard_url = settings.kibana_url.rstrip("/") + f"/app/dashboards#/view/{DASHBOARD_ID}"
    return DASHBOARD_ID, dashboard_url


def seed() -> Dict[str, Any]:
    """End-to-end. Deterministic. Deletes existing indices + dashboard, recreates
    with mappings, bulk-ingests, recreates dashboard. Returns counts + URL."""
    started = time.time()
    if not settings.elasticsearch_api_key and not settings.elasticsearch_password:
        raise RuntimeError("Elasticsearch credentials not configured")
    if not settings.kibana_api_key:
        raise RuntimeError("KIBANA_API_KEY not configured")

    es = get_client()
    mappings = get_mappings()
    docs_by_index = generate_documents()

    # Drop existing indices first (idempotent).
    counts: Dict[str, int] = {}
    index_names = list(INDICES.values())
    for index in index_names:
        if es.indices.exists(index=index):
            es.indices.delete(index=index)
            log.info("black_friday.index.deleted", index=index)
        es.indices.create(index=index, mappings=mappings[index])
        log.info("black_friday.index.created", index=index)

    # Bulk ingest with chunking, refresh on the last batch.
    for index, docs in docs_by_index.items():
        actions = ({"_index": index, "_source": doc} for doc in docs)
        success, errors = bulk(
            es, actions, chunk_size=500,
            refresh="wait_for", raise_on_error=False,
        )
        counts[index] = success
        n_errors = len(errors) if isinstance(errors, list) else 0
        log.info("black_friday.bulk.indexed", index=index,
                 count=success, errors=n_errors)

    # Force a final refresh per index to make docs visible immediately.
    for index in index_names:
        try:
            es.indices.refresh(index=index)
        except Exception as exc:
            log.warning("black_friday.refresh.failed", index=index, error=str(exc))

    # Dashboard: idempotent recreate.
    _delete_dashboard()
    dashboard_id, dashboard_url = _create_dashboard()

    elapsed = round(time.time() - started, 2)
    return {
        "ok": True,
        "scenario": SCENARIO_ID,
        "indices": counts,
        "doc_count": sum(counts.values()),
        "dashboard_id": dashboard_id,
        "dashboard_url": dashboard_url,
        "elapsed_seconds": elapsed,
        "anomaly_windows": [
            {"label": w["label"], "start": w["start"].isoformat(),
             "end": w["end"].isoformat(), "severity": w["severity"]}
            for w in _anomaly_windows(_now_anchor())
        ],
    }
