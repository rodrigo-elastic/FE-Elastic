"""
filename: black_friday.py
description: FE Copilot · Demo Data Generator · Black Friday Outage scenario.

Story arc:
    Lumen Apparel - a fast-growing online apparel brand - runs their biggest sale
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
    "Lumen Apparel - a growing fintech-backed e-commerce platform - runs its biggest "
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
CUSTOMER_DASHBOARD_ID: str = "demo-black-friday-outage-customer-dashboard"

# The seed anchor - fixes "now" for reproducibility. Without this the timestamps
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

# Lumen apparel SKUs - these get embedded in URLs, payloads.
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
            "label": "Precursor 1 - mild",
            "start": now - timedelta(days=6, hours=10),  # T-6d 14:00 UTC if 'now' is 00:00 UTC
            "end": now - timedelta(days=6, hours=10) + timedelta(minutes=25),
            "severity": 0.35,
            "tail_factor": 6.0,
        },
        {
            "label": "Precursor 2 - moderate",
            "start": now - timedelta(days=4, hours=6),
            "end": now - timedelta(days=4, hours=6) + timedelta(minutes=60),
            "severity": 0.55,
            "tail_factor": 11.0,
        },
        {
            "label": "Precursor 3 - dress rehearsal",
            "start": now - timedelta(days=2, hours=8),
            "end": now - timedelta(days=2, hours=8) + timedelta(minutes=90),
            "severity": 0.75,
            "tail_factor": 18.0,
        },
        {
            "label": "Headliner - Black Friday outage",
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

    # Path popularity weights - mostly browse + cart, then a smaller checkout funnel.
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

        # Outcome - db elevated failure rate during anomaly; checkout-svc cascades; others mostly fine.
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
    (288 buckets) or every 30 minutes for the prior 6 days (288 buckets) - but
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

            # Request count - diurnal+headliner shaped
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

            # checkout funnel KPIs - only on checkout-svc, the customer-facing measure.
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
    """Index mappings - keyword for high-cardinality strings, date for @timestamp,
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
    """Inline-data bar chart of peak p99 per service. Computed at seed time
    by querying ES; results embedded as data.values so the Vega plugin in
    Kibana never has to fetch anything (which is the failure mode that was
    breaking every URL-based panel in 9.3).

    Robustness: every ES call is wrapped in try/except. On failure the panel
    falls back to data.values: [] (a blank chart) plus a logged warning. The
    seed function must always succeed end-to-end even if individual aggs error.
    """
    values: List[Dict[str, Any]] = []
    try:
        es = get_client()
        r = es.search(index=INDICES["metrics"], body={
            "size": 0,
            "query": {"bool": {"filter": [
                {"range": {"@timestamp": {"gte": "now-7d", "lte": "now"}}},
            ]}},
            "aggs": {
                "by_service": {
                    "terms": {"field": "service.name", "size": 10,
                               "order": {"max_p99": "desc"}},
                    "aggs": {"max_p99": {"max": {"field": "latency.p99_ms"}}},
                },
            },
        })
        for b in r["aggregations"]["by_service"]["buckets"]:
            v = (b.get("max_p99") or {}).get("value")
            if v is not None:
                values.append({"service": b["key"], "peak_p99_ms": float(v)})
    except Exception as exc:
        log.warning("black_friday.spec_p99.compute.failed", error=str(exc))

    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": "Peak p99 latency by service (last 7d)",
        "data": {"values": values},
        "mark": "bar",
        "encoding": {
            "y": {"field": "service", "type": "nominal", "sort": "-x", "title": "service"},
            "x": {"field": "peak_p99_ms", "type": "quantitative", "title": "peak p99 (ms)"},
            "color": {"field": "service", "type": "nominal", "legend": None},
        },
    }


def _spec_errors_stacked() -> Dict[str, Any]:
    """Inline-data bar chart of total errors per service over last 7d.

    Robustness: ES query wrapped in try/except. On failure, falls back to an
    empty values array so the panel renders a blank chart and the seed keeps going.
    """
    values: List[Dict[str, Any]] = []
    try:
        es = get_client()
        r = es.search(index=INDICES["metrics"], body={
            "size": 0,
            "query": {"bool": {"filter": [
                {"range": {"@timestamp": {"gte": "now-7d", "lte": "now"}}},
            ]}},
            "aggs": {
                "by_service": {
                    "terms": {"field": "service.name", "size": 10,
                               "order": {"errs": "desc"}},
                    "aggs": {"errs": {"sum": {"field": "error.count"}}},
                },
            },
        })
        for b in r["aggregations"]["by_service"]["buckets"]:
            v = (b.get("errs") or {}).get("value")
            if v is not None:
                values.append({"service": b["key"], "errors": int(v)})
    except Exception as exc:
        log.warning("black_friday.spec_errors.compute.failed", error=str(exc))

    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": "Total errors by service (last 7d)",
        "data": {"values": values},
        "mark": "bar",
        "encoding": {
            "y": {"field": "service", "type": "nominal", "sort": "-x", "title": "service"},
            "x": {"field": "errors", "type": "quantitative", "title": "total errors"},
            "color": {"field": "service", "type": "nominal", "legend": None},
        },
    }


def _spec_recovery_timeline() -> Dict[str, Any]:
    """Inline-data chart showing peak p99 (bar) per anomaly window plus the
    recovery duration in minutes. Each window is a labelled incident: three
    precursors plus the headliner. The customer view frames this as time-to-recover;
    the FE view frames it as the warning curve we ignored.

    Robustness: ES query wrapped in try/except. Falls back to empty values on error.
    """
    values: List[Dict[str, Any]] = []
    try:
        es = get_client()
        # Use the checkout index which maps lumen.anomaly_window as a proper
        # keyword field (the metrics index uses labels.* as a dynamic object,
        # which lands as text and blocks term aggregations).
        r = es.search(index=INDICES["checkout"], body={
            "size": 0,
            "query": {"bool": {"filter": [
                {"range": {"@timestamp": {"gte": "now-7d", "lte": "now"}}},
                {"exists": {"field": "lumen.anomaly_window"}},
            ]}},
            "aggs": {
                "by_window": {
                    "terms": {"field": "lumen.anomaly_window", "size": 8,
                              "order": {"peak_p99": "desc"}},
                    "aggs": {
                        "peak_p99": {"max": {"field": "transaction.duration.us"}},
                        "first_seen": {"min": {"field": "@timestamp"}},
                        "last_seen": {"max": {"field": "@timestamp"}},
                    },
                },
            },
        })
        for b in r["aggregations"]["by_window"]["buckets"]:
            label = b.get("key")
            peak_us = (b.get("peak_p99") or {}).get("value")
            first_ms = (b.get("first_seen") or {}).get("value")
            last_ms = (b.get("last_seen") or {}).get("value")
            if peak_us is None or first_ms is None or last_ms is None:
                continue
            duration_min = max(1.0, (float(last_ms) - float(first_ms)) / 60000.0)
            values.append({
                "window": label,
                "peak_p99_ms": round(float(peak_us) / 1000.0, 1),
                "duration_min": round(duration_min, 1),
            })
    except Exception as exc:
        log.warning("black_friday.spec_recovery.compute.failed", error=str(exc))

    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": "Recovery timeline: peak p99 and incident duration per window",
        "data": {"values": values},
        "layer": [
            {
                "mark": {"type": "bar", "color": "#c44"},
                "encoding": {
                    "y": {"field": "window", "type": "nominal", "sort": "-x",
                           "title": "anomaly window"},
                    "x": {"field": "peak_p99_ms", "type": "quantitative",
                           "title": "peak p99 (ms) on checkout-db"},
                    "tooltip": [
                        {"field": "window", "type": "nominal", "title": "incident"},
                        {"field": "peak_p99_ms", "type": "quantitative",
                         "title": "peak p99 (ms)"},
                        {"field": "duration_min", "type": "quantitative",
                         "title": "duration (min)"},
                    ],
                },
            },
            {
                "mark": {"type": "text", "align": "left", "dx": 6, "color": "#333"},
                "encoding": {
                    "y": {"field": "window", "type": "nominal", "sort": "-x"},
                    "x": {"field": "peak_p99_ms", "type": "quantitative"},
                    "text": {"field": "duration_min", "type": "quantitative",
                             "format": ".0f"},
                },
            },
        ],
    }


def _spec_cart_value_lost() -> Dict[str, Any]:
    """Inline-data bar chart: sum of cart.value_usd on checkout-svc 5xx events
    during the headliner window, bucketed by 10 minute slices. This is the
    customer-facing dollar figure: every bar is real cart abandonment that
    Lumen Apparel did not capture during the outage.

    Robustness: ES query wrapped in try/except. Falls back to empty values on error.
    """
    values: List[Dict[str, Any]] = []
    try:
        es = get_client()
        r = es.search(index=INDICES["checkout"], body={
            "size": 0,
            "query": {"bool": {"filter": [
                {"range": {"http.response.status_code": {"gte": 500, "lt": 600}}},
                {"range": {"@timestamp": {"gte": "now-12h", "lte": "now"}}},
                {"exists": {"field": "cart.value_usd"}},
            ]}},
            "aggs": {
                "time": {
                    "date_histogram": {"field": "@timestamp",
                                         "fixed_interval": "10m",
                                         "min_doc_count": 1},
                    "aggs": {
                        "lost_usd": {"sum": {"field": "cart.value_usd"}},
                        "carts": {"value_count": {"field": "cart.value_usd"}},
                    },
                },
            },
        })
        for b in r["aggregations"]["time"]["buckets"]:
            ts = b.get("key_as_string") or b.get("key")
            lost = (b.get("lost_usd") or {}).get("value") or 0.0
            carts = (b.get("carts") or {}).get("value") or 0
            if lost <= 0:
                continue
            values.append({
                "time": ts,
                "lost_usd": round(float(lost), 2),
                "carts": int(carts),
            })
    except Exception as exc:
        log.warning("black_friday.spec_cart_lost.compute.failed", error=str(exc))

    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": "Cart value lost during peak (sum USD per 10 min, checkout-svc 5xx)",
        "data": {"values": values},
        "mark": {"type": "bar", "color": "#a04"},
        "encoding": {
            "x": {"field": "time", "type": "temporal", "title": "time"},
            "y": {"field": "lost_usd", "type": "quantitative",
                   "title": "cart value lost (USD)"},
            "tooltip": [
                {"field": "time", "type": "temporal", "title": "bucket"},
                {"field": "lost_usd", "type": "quantitative",
                 "title": "lost USD", "format": ",.2f"},
                {"field": "carts", "type": "quantitative", "title": "abandoned carts"},
            ],
        },
    }


def _spec_outage_kpi() -> Dict[str, Any]:
    """Deprecated. Kept for backwards compatibility with any external caller.
    The dashboard now renders KPI tiles via a markdown panel populated by
    `_kpi_markdown()`, which queries ES once at seed time and embeds the
    values as static text. Markdown panels always render in Kibana 9.3,
    sidestepping the Vega-Lite text-mark rendering issues we hit with
    filters-agg + format.property."""
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "data": {"values": [{"x": 0}]},
        "mark": "text",
        "encoding": {"text": {"value": "see markdown panel"}},
    }


def _kpi_markdown() -> str:
    """Compute peak checkout-db p99 + total errors over the last 7 days and
    render as a markdown KPI block. Falls back to a static narrative if ES
    is unreachable so the dashboard still has something to show."""
    try:
        es = get_client()
        r1 = es.search(index=INDICES["metrics"], body={
            "size": 0,
            "query": {"bool": {"filter": [
                {"term": {"service.name": "checkout-db"}},
                {"range": {"@timestamp": {"gte": "now-7d", "lte": "now"}}},
            ]}},
            "aggs": {"max_p99": {"max": {"field": "latency.p99_ms"}}},
        })
        peak_p99_ms = r1["aggregations"]["max_p99"]["value"] or 0
        r2 = es.search(index=INDICES["metrics"], body={
            "size": 0,
            "query": {"bool": {"filter": [
                {"range": {"@timestamp": {"gte": "now-7d", "lte": "now"}}},
            ]}},
            "aggs": {"total_errors": {"sum": {"field": "error.count"}}},
        })
        total_errors = int(r2["aggregations"]["total_errors"]["value"] or 0)
    except Exception as exc:
        log.warning("black_friday.kpi.compute.failed", error=str(exc))
        peak_p99_ms = 0
        total_errors = 0

    peak_p99_s = peak_p99_ms / 1000.0
    return (
        "## Outage KPIs (last 7d)\n\n"
        f"### checkout-db peak p99\n"
        f"# **{peak_p99_s:.2f} s**\n\n"
        f"_Baseline is ~180 ms. Peak is ~{int(peak_p99_s)}x baseline._\n\n"
        f"### Total errors (all services)\n"
        f"# **{total_errors:,}**\n\n"
        "_Concentrated in checkout-svc, payment-svc, checkout-db._\n"
    )


def _spec_funnel() -> Dict[str, Any]:
    """Inline-data dual-line of cart abandonment vs payment success. Buckets
    pre-computed via ES at seed time, embedded as data.values pre-folded into
    long format so Vega-Lite needs no transforms."""
    values: List[Dict[str, Any]] = []
    try:
        es = get_client()
        r = es.search(index=INDICES["metrics"], body={
            "size": 0,
            "query": {"bool": {"filter": [
                {"term": {"service.name": "checkout-svc"}},
                {"range": {"@timestamp": {"gte": "now-7d", "lte": "now"}}},
            ]}},
            "aggs": {
                "time": {
                    "date_histogram": {"field": "@timestamp",
                                         "fixed_interval": "30m",
                                         "min_doc_count": 1},
                    "aggs": {
                        "abandon": {"avg": {"field": "funnel.cart_abandonment_rate"}},
                        "success": {"avg": {"field": "funnel.payment_success_rate"}},
                    },
                },
            },
        })
        for b in r["aggregations"]["time"]["buckets"]:
            ts = b.get("key_as_string") or b.get("key")
            ab = (b.get("abandon") or {}).get("value")
            su = (b.get("success") or {}).get("value")
            if ab is not None:
                values.append({"time": ts, "metric": "abandonment_rate", "rate": float(ab)})
            if su is not None:
                values.append({"time": ts, "metric": "payment_success_rate", "rate": float(su)})
    except Exception as exc:
        log.warning("black_friday.spec_funnel.compute.failed", error=str(exc))

    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": "Funnel: abandonment vs payment success",
        "data": {"values": values},
        "mark": "line",
        "encoding": {
            "x": {"field": "time", "type": "temporal", "title": "time"},
            "y": {"field": "rate", "type": "quantitative", "title": "rate",
                  "axis": {"format": ".0%"}},
            "color": {"field": "metric", "type": "nominal", "title": "metric"},
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


# ============================================================ Lens helpers ========


def _ensure_data_view(index: str, dv_id: str) -> Optional[str]:
    """Idempotently ensure a Kibana data view (index pattern) exists for `index`.

    Returns the data view id on success, or None if Kibana rejected the request
    (in which case callers should fall back to the inline-data Vega version).

    Strategy:
      1. GET /api/data_views/data_view/<dv_id>. If 200, done.
      2. Otherwise POST /api/data_views/data_view with the desired id. The
         response code is 200 on success, 409 if it already exists (race), or
         4xx/5xx on real failure.
    """
    get_url = _kbn_url(f"/api/data_views/data_view/{dv_id}")
    post_url = _kbn_url("/api/data_views/data_view")
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(get_url, headers=_kbn_headers())
            if resp.status_code == 200:
                return dv_id
            body = {
                "data_view": {
                    "id": dv_id,
                    "name": index,
                    "title": index,
                    "timeFieldName": "@timestamp",
                },
                "override": True,
            }
            resp = client.post(post_url, headers=_kbn_headers(), json=body)
            if resp.status_code in (200, 201):
                return dv_id
            if resp.status_code == 409:
                return dv_id
            log.warning("black_friday.data_view.create.failed",
                        dv_id=dv_id, status=resp.status_code,
                        body=resp.text[:300])
            return None
    except Exception as exc:
        log.warning("black_friday.data_view.create.exception",
                    dv_id=dv_id, error=str(exc))
        return None


def _lens_p99_panel(panel_id: str, x: int, y: int, w: int, h: int,
                    title: str, dv_id: str) -> Dict[str, Any]:
    """Lens line chart: avg(latency.p99_ms) over @timestamp, broken down by
    service.name. Live, time-picker aware, filterable, drilldown-friendly.

    Schema validated against Kibana 9.3.4 Lens saved-object format. The same
    `attributes` blob is what Kibana returns when you export a Lens by-value
    panel from a dashboard, so this is round-trip safe.
    """
    attributes = {
        "title": title,
        "description": "",
        "visualizationType": "lnsXY",
        "type": "lens",
        "references": [
            {
                "name": "indexpattern-datasource-layer-layer1",
                "type": "index-pattern",
                "id": dv_id,
            },
        ],
        "state": {
            "datasourceStates": {
                "formBased": {
                    "layers": {
                        "layer1": {
                            "columnOrder": ["x_col", "split_col", "metric_col"],
                            "columns": {
                                "x_col": {
                                    "label": "@timestamp",
                                    "dataType": "date",
                                    "operationType": "date_histogram",
                                    "sourceField": "@timestamp",
                                    "isBucketed": True,
                                    "scale": "interval",
                                    "params": {"interval": "auto",
                                               "includeEmptyRows": True,
                                               "dropPartials": False},
                                },
                                "split_col": {
                                    "label": "Top values of service.name",
                                    "dataType": "string",
                                    "operationType": "terms",
                                    "sourceField": "service.name",
                                    "isBucketed": True,
                                    "scale": "ordinal",
                                    "params": {
                                        "size": 10,
                                        "orderBy": {"type": "column",
                                                     "columnId": "metric_col"},
                                        "orderDirection": "desc",
                                        "otherBucket": False,
                                        "missingBucket": False,
                                        "parentFormat": {"id": "terms"},
                                    },
                                },
                                "metric_col": {
                                    "label": "Average of latency.p99_ms",
                                    "dataType": "number",
                                    "operationType": "average",
                                    "sourceField": "latency.p99_ms",
                                    "isBucketed": False,
                                    "scale": "ratio",
                                    "params": {"format": {"id": "number",
                                                           "params": {"decimals": 0,
                                                                       "suffix": " ms"}}},
                                },
                            },
                            "incompleteColumns": {},
                        },
                    },
                },
            },
            "visualization": {
                "preferredSeriesType": "line",
                "layers": [
                    {
                        "layerId": "layer1",
                        "accessors": ["metric_col"],
                        "position": "top",
                        "seriesType": "line",
                        "showGridlines": False,
                        "layerType": "data",
                        "xAccessor": "x_col",
                        "splitAccessor": "split_col",
                    },
                ],
                "title": title,
                "legend": {"isVisible": True, "position": "right"},
                "valueLabels": "hide",
                "fittingFunction": "None",
                "axisTitlesVisibilitySettings": {"x": True, "yLeft": True,
                                                  "yRight": True},
                "tickLabelsVisibilitySettings": {"x": True, "yLeft": True,
                                                  "yRight": True},
                "labelsOrientation": {"x": 0, "yLeft": 0, "yRight": 0},
                "gridlinesVisibilitySettings": {"x": True, "yLeft": True,
                                                "yRight": True},
            },
            "filters": [],
            "query": {"language": "kuery", "query": ""},
        },
    }

    return {
        "type": "lens",
        "panelIndex": panel_id,
        "gridData": {"x": x, "y": y, "w": w, "h": h, "i": panel_id},
        "version": "9.3.4",
        "embeddableConfig": {
            "enhancements": {},
            "attributes": attributes,
        },
        "title": title,
    }


def _lens_funnel_panel(panel_id: str, x: int, y: int, w: int, h: int,
                       title: str, dv_id: str) -> Dict[str, Any]:
    """Lens dual-line chart on the funnel metrics from checkout-svc rollups.

    x=@timestamp (date_histogram auto), two y series:
      - avg(funnel.cart_abandonment_rate)
      - avg(funnel.payment_success_rate)
    Filter pinned to service.name = checkout-svc so only the funnel bucket
    contributes (other services do not emit the funnel.* fields).
    """
    attributes = {
        "title": title,
        "description": "",
        "visualizationType": "lnsXY",
        "type": "lens",
        "references": [
            {
                "name": "indexpattern-datasource-layer-layer1",
                "type": "index-pattern",
                "id": dv_id,
            },
        ],
        "state": {
            "datasourceStates": {
                "formBased": {
                    "layers": {
                        "layer1": {
                            "columnOrder": ["x_col", "abandon_col", "success_col"],
                            "columns": {
                                "x_col": {
                                    "label": "@timestamp",
                                    "dataType": "date",
                                    "operationType": "date_histogram",
                                    "sourceField": "@timestamp",
                                    "isBucketed": True,
                                    "scale": "interval",
                                    "params": {"interval": "auto",
                                               "includeEmptyRows": True,
                                               "dropPartials": False},
                                },
                                "abandon_col": {
                                    "label": "Cart abandonment rate",
                                    "dataType": "number",
                                    "operationType": "average",
                                    "sourceField": "funnel.cart_abandonment_rate",
                                    "isBucketed": False,
                                    "scale": "ratio",
                                    "params": {"format": {"id": "percent",
                                                           "params": {"decimals": 0}}},
                                },
                                "success_col": {
                                    "label": "Payment success rate",
                                    "dataType": "number",
                                    "operationType": "average",
                                    "sourceField": "funnel.payment_success_rate",
                                    "isBucketed": False,
                                    "scale": "ratio",
                                    "params": {"format": {"id": "percent",
                                                           "params": {"decimals": 0}}},
                                },
                            },
                            "incompleteColumns": {},
                        },
                    },
                },
            },
            "visualization": {
                "preferredSeriesType": "line",
                "layers": [
                    {
                        "layerId": "layer1",
                        "accessors": ["abandon_col", "success_col"],
                        "position": "top",
                        "seriesType": "line",
                        "showGridlines": False,
                        "layerType": "data",
                        "xAccessor": "x_col",
                        "yConfig": [
                            {"forAccessor": "abandon_col", "color": "#c44"},
                            {"forAccessor": "success_col", "color": "#0a6e3f"},
                        ],
                    },
                ],
                "title": title,
                "legend": {"isVisible": True, "position": "right"},
                "valueLabels": "hide",
                "fittingFunction": "Linear",
                "axisTitlesVisibilitySettings": {"x": True, "yLeft": True,
                                                  "yRight": True},
                "tickLabelsVisibilitySettings": {"x": True, "yLeft": True,
                                                  "yRight": True},
                "labelsOrientation": {"x": 0, "yLeft": 0, "yRight": 0},
                "gridlinesVisibilitySettings": {"x": True, "yLeft": True,
                                                "yRight": True},
            },
            "filters": [],
            "query": {"language": "kuery",
                      "query": "service.name : \"checkout-svc\""},
        },
    }

    return {
        "type": "lens",
        "panelIndex": panel_id,
        "gridData": {"x": x, "y": y, "w": w, "h": h, "i": panel_id},
        "version": "9.3.4",
        "embeddableConfig": {
            "enhancements": {},
            "attributes": attributes,
        },
        "title": title,
    }


def _switcher_markdown(active: str, fe_url: str, customer_url: str) -> str:
    """Build a markdown switcher with two anchor-tag buttons. Kibana 9 markdown
    panels render inline anchor tags and basic inline styles, so we can give the
    active view a highlighted look. `active` is either "fe" or "customer".
    """
    fe_active = (active == "fe")
    cu_active = (active == "customer")
    fe_style = (
        "display:inline-block;padding:8px 16px;margin-right:8px;border-radius:6px;"
        + ("background:#1a4480;color:#fff;font-weight:600;" if fe_active
           else "background:#eef2f7;color:#1a4480;font-weight:500;border:1px solid #1a4480;")
        + "text-decoration:none;"
    )
    cu_style = (
        "display:inline-block;padding:8px 16px;border-radius:6px;"
        + ("background:#0a6e3f;color:#fff;font-weight:600;" if cu_active
           else "background:#eef7f1;color:#0a6e3f;font-weight:500;border:1px solid #0a6e3f;")
        + "text-decoration:none;"
    )
    return (
        "**View:** "
        f"<a href=\"{fe_url}\" style=\"{fe_style}\">[FE] Field Engineer view</a>"
        f"<a href=\"{customer_url}\" style=\"{cu_style}\">[Customer] Postmortem view</a>"
        "\n\n"
        "_Same data. Same charts. Different audience. Use the FE view to prep "
        "the narrative and the Customer view to walk the customer through it._"
    )


def _fe_header_markdown() -> str:
    return (
        "## [FE] Black Friday Outage - Lumen Apparel - Field Engineer view\n\n"
        "**The story.** It is Black Friday at Lumen Apparel. Traffic is 3.4x normal. "
        "At **10:00am PT** the catalog page-size change shipped on Tuesday starts hammering "
        "`checkout-db` with a 12x query plan; the database falls into IO contention; p99 "
        "latency on the DB jumps from **180ms baseline to 4-8 seconds**; `checkout-svc` "
        "starts surfacing 5xx; `payment-svc` retries cascade. Cart abandonment doubles "
        "from 28% to 55%. **At 11:30am PT** SRE rolls back the catalog config and "
        "everything snaps back inside one bucket.\n\n"
        "**What this dashboard proves.**  This is *not* a system-wide outage. "
        "`recs-svc`, `frontend`, and `notification-svc` stay flat throughout - the failure "
        "is localised to the checkout writer DB and its dependents. That is the whole "
        "point of a service-aware observability platform.\n\n"
        "**How to demo this.**\n\n"
        "1. Start at the recovery timeline: point out the three precursor incidents "
        "and ask the customer how their current tool would have surfaced them.\n"
        "2. Move to the p99 by service chart: only `checkout-db`, `checkout-svc`, "
        "and `payment-svc` move. Everything else is flat.\n"
        "3. Land on the cart-value-lost chart: convert the outage into hard dollars.\n"
        "4. Close on the funnel: abandonment doubles, payment success collapses, "
        "both snap back when SRE rolls back.\n\n"
        "**Customer source quotes (use as you see fit):**\n\n"
        "> \"We had four near-misses in the week before Black Friday and we didn't "
        "know.\" - VP Engineering, Lumen Apparel\n\n"
        "> \"Our APM told us latency was up. It did not tell us which deploy caused it.\" "
        "- Director of SRE\n\n"
        "**Three Elastic capabilities that would have caught this earlier:** "
        "(1) **APM service maps** show `catalog-svc` driving load to `checkout-db` 48 hours "
        "before the outage; "
        "(2) **Elastic ML anomaly detection** flags the p99 distribution shift in the "
        "first precursor 6 days ago; "
        "(3) **SLO burn-rate alerts** page on the 4 hour burn-rate breach during the "
        "dress-rehearsal precursor at T-2d. Combined, the team would have caught the "
        "warning, pinpointed the deploy, and avoided **~$1.4M of lost GMV** during the "
        "headline window."
    )


def _fe_followup_markdown() -> str:
    return (
        "## How this becomes a customer conversation\n\n"
        "**MEDDPICC pain and metrics surfaced by this scenario:**\n\n"
        "- **Metrics**  - Lost GMV per minute of checkout downtime; cart abandonment "
        "baseline vs peak; p99 SLO breach minutes; mean time to detect.\n"
        "- **Economic Buyer pain**  - \"We had four near-misses in the week before BF "
        "and didn't know.\" Detection time approaches 0 with Elastic anomaly ML.\n"
        "- **Decision Criteria**  - APM + Logs + SIEM + ML in one license; no per-host "
        "gotcha; ECS taxonomy across services; one query language.\n"
        "- **Decision Process**  - Three precursor incidents make the case for a "
        "60-day pilot before the next peak event.\n"
        "- **Paper Process**  - Procurement is friendly to consolidating tools, "
        "especially when it lets them retire two contracts.\n"
        "- **Identify pain**  - Today the customer runs Datadog APM and Splunk for "
        "logs; correlation across the two is manual and slow.\n"
        "- **Champion enablement**  - Service maps, anomaly explorer, SLO burn rate "
        "dashboards out of the box; no Splunk SPL rewrite required.\n"
        "- **Competition**  - Splunk ITSI (expensive, slow rollout), Datadog APM "
        "(no log and SIEM unification), New Relic (per-seat pricing).\n\n"
        "**Annotations for the live demo.**\n\n"
        "- The recovery timeline is the highest-impact slide: walk the customer "
        "left-to-right across the three precursors and pause on each one.\n"
        "- Use the cart-value-lost chart to translate the outage from engineering "
        "language into the CFO's language.\n"
        "- The funnel chart is the cleanest visual proof of business impact: "
        "abandonment up, payment success down, both recovering inside one bucket.\n\n"
        "**Call to action.**  Schedule a 30-minute live APM walkthrough on the "
        "customer's own services next week. Set up an Elastic Cloud trial with their "
        "staging traffic mirrored in, and reproduce this exact dashboard in their "
        "environment within the trial.\n"
    )


def _customer_header_markdown() -> str:
    return (
        "## [Customer] Black Friday Outage - Postmortem and Business Briefing\n\n"
        "**Executive summary.** On Black Friday, Lumen Apparel experienced a "
        "90 minute checkout outage starting at 10:00am PT. Root cause was a "
        "configuration change on the product catalog service that drove the "
        "checkout database into IO contention. The shopper-facing impact was a "
        "doubling of cart abandonment, a collapse in payment success, and an "
        "estimated **$1.4M of lost GMV** during the headline window.\n\n"
        "**What you will see in this briefing.**\n\n"
        "- **Recovery timeline:** four incidents in the prior week, with the "
        "headliner on Black Friday at 10:00am PT. Three precursor events were "
        "early warnings.\n"
        "- **Service-level latency:** the failure was localised. Storefront, "
        "recommendations, and notifications stayed healthy throughout.\n"
        "- **Customer impact in dollars:** abandoned cart value, summed in 10 minute "
        "buckets, during the peak window.\n"
        "- **Funnel impact:** cart abandonment vs payment success across the "
        "headliner window, including the snap-back after the rollback.\n\n"
        "**What would have been different with Elastic Observability.**\n\n"
        "- **Time to detect:** 6 days earlier. Elastic ML anomaly detection would "
        "have flagged the first precursor incident in the week leading up to the "
        "sale.\n"
        "- **Time to localise:** minutes, not hours. APM service maps would have "
        "shown the catalog service driving load into the checkout database 48 hours "
        "before the outage.\n"
        "- **Time to recover:** the rollback would have started before peak hour, "
        "preventing the cart abandonment spike entirely.\n"
    )


def _customer_followup_markdown() -> str:
    return (
        "## Recommended next steps\n\n"
        "**Business outcomes Elastic Observability would have unlocked on this incident.**\n\n"
        "- **GMV protected.** Catching the precursor incidents would have prevented "
        "the headliner. Estimated value: **$1.4M of recovered Black Friday GMV.**\n"
        "- **Customer-minutes protected.** The 90 minute outage affected tens of "
        "thousands of shoppers at peak. Faster detection and rollback compresses "
        "this window dramatically.\n"
        "- **One platform.** APM, logs, infrastructure metrics, and SIEM in one "
        "license, with one query language. Retire two existing tooling contracts.\n"
        "- **No more manual correlation.** Today the team manually pivots from "
        "APM dashboards to log search to identify a noisy deploy. Elastic "
        "correlates this in the same view.\n\n"
        "**Proposed pilot.**\n\n"
        "- **Week 1.** Mirror staging traffic into an Elastic Cloud deployment. "
        "Reproduce this dashboard in the customer's environment.\n"
        "- **Weeks 2 to 4.** Onboard production telemetry from checkout, payment, "
        "and catalog services. Configure SLO burn-rate alerts on the checkout funnel.\n"
        "- **Week 5.** Run a tabletop exercise replaying this incident and measure "
        "time to detect, time to localise, and time to recover.\n"
        "- **Week 6.** Executive readout with quantified before-and-after metrics.\n\n"
        "**Success criteria for the pilot.**\n\n"
        "- Detect a synthetic precursor inside 5 minutes.\n"
        "- Localise to the offending service inside 10 minutes.\n"
        "- Single dashboard view that combines APM, logs, and infrastructure metrics "
        "for the checkout flow.\n"
    )


def _dashboard_url(dashboard_id: str) -> str:
    return settings.kibana_url.rstrip("/") + f"/app/dashboards#/view/{dashboard_id}"


def _shared_vega_specs() -> Dict[str, Dict[str, Any]]:
    """Compute the shared Vega specs once. Both dashboards reuse the exact same
    inline-data Vega panels - only the markdown panels differ. Each spec
    function already wraps its ES query in try/except, so this call is safe
    even if individual aggs fail.
    """
    return {
        "p99": _spec_p99_by_service(),
        "errors": _spec_errors_stacked(),
        "funnel": _spec_funnel(),
        "recovery": _spec_recovery_timeline(),
        "cart_lost": _spec_cart_value_lost(),
    }


def _build_panels(view: str, specs: Dict[str, Dict[str, Any]],
                  kpi_md: str, fe_url: str, customer_url: str,
                  lens_dv_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Assemble the panel list for one dashboard.

    Layout (48 wide grid):
      row 0  - h=4   - switcher (full width)
      row 4  - h=8   - title + intro markdown (full width)
      row 12 - h=14  - p99 by service (24w) + errors by service (24w)
      row 26 - h=10  - KPI markdown (12w) + funnel (36w)            [funnel h=14]
      row 40 - h=14  - recovery timeline (24w) + cart lost (24w)
      row 54 - h=12  - closing narrative (full width)

    When `lens_dv_id` is provided, the p99 and funnel panels are upgraded to
    Lens visualizations backed by the live demo-blackfriday-metrics index.
    Lens panels respond to the dashboard time picker and global filters,
    where inline-data Vega panels are frozen at seed time. If `lens_dv_id`
    is None (data view creation failed), the panels fall back to the
    inline-data Vega versions, which are visually identical and always render.
    """
    if view == "fe":
        intro_md = _fe_header_markdown()
        followup_md = _fe_followup_markdown()
        intro_title = "[FE] Story and talk track"
        followup_title = "[FE] Customer conversation and MEDDPICC"
    else:
        intro_md = _customer_header_markdown()
        followup_md = _customer_followup_markdown()
        intro_title = "[Customer] Executive summary"
        followup_title = "[Customer] Recommended next steps"

    switcher_md = _switcher_markdown(view, fe_url, customer_url)

    if lens_dv_id:
        p99_panel = _lens_p99_panel(
            "p99", 0, 12, 24, 14,
            "p99 latency by service (live)", lens_dv_id,
        )
        funnel_panel = _lens_funnel_panel(
            "funnel", 12, 26, 36, 14,
            "Funnel: abandonment vs payment success (live)", lens_dv_id,
        )
    else:
        p99_panel = _vega_panel(
            "p99", 0, 12, 24, 14,
            "p99 latency by service", specs["p99"],
        )
        funnel_panel = _vega_panel(
            "funnel", 12, 26, 36, 14,
            "Funnel: abandonment vs payment success", specs["funnel"],
        )

    panels = [
        _markdown_panel("switcher", 0, 0, 48, 4, switcher_md, "View switcher"),
        _markdown_panel("hdr", 0, 4, 48, 8, intro_md, intro_title),
        p99_panel,
        _vega_panel("err", 24, 12, 24, 14,
                    "Errors by service over time", specs["errors"]),
        _markdown_panel("kpi", 0, 26, 12, 14, kpi_md, "Outage KPIs"),
        funnel_panel,
        _vega_panel("recovery", 0, 40, 24, 14,
                    "Recovery timeline by anomaly window", specs["recovery"]),
        _vega_panel("cart_lost", 24, 40, 24, 14,
                    "Cart value lost during peak", specs["cart_lost"]),
        _markdown_panel("nar", 0, 54, 48, 12, followup_md, followup_title),
    ]
    return panels


def _flagship_industry_context() -> Dict[str, Any]:
    """Stand-in industry config for the FE superset helpers. Black Friday is
    a retail-ecommerce flagship; we hand-roll a context that drives the
    discovery-questions and say/do-not-say blocks correctly."""
    return {
        "id": "retail-ecommerce",
        "name": "Retail e-commerce - Black Friday",
        "summary": ("Peak-traffic outage on the busiest shopping day. "
                    "Observability + revenue-protection story."),
        "personas": [
            {"role": "VP Engineering",
             "pain": "Cart abandonment during peak is costing us seven figures per minute."},
            {"role": "SRE Lead",
             "pain": "p99 spikes hidden behind aggregate dashboards in Datadog."},
            {"role": "CFO",
             "pain": "Outage MTTR maps directly to lost revenue and we cannot quantify it."},
            {"role": "CISO",
             "pain": "PCI-DSS evidence retention is expensive on the legacy SIEM."},
        ],
        "regulations": ["PCI DSS", "SOC 2", "GDPR"],
        "top_competitors": ["battlecard-datadog", "battlecard-splunk",
                            "battlecard-new-relic"],
    }


def get_dashboard_panels(lens_dv_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """FE-view dashboard panels.

    FE = strict superset of the customer view: every customer panel is shown,
    each prefaced by an FE value-callout markdown panel, followed by the
    existing FE-only talk-track and the two new FE-only blocks (discovery
    questions, say/do-not-say). Built by composing the customer panel list
    via `get_customer_panels()` and the existing `_build_panels("fe", ...)`
    output (which carries the FE-specific markdown framing)."""
    from app.services.scenarios.industry_factory import build_fe_superset_panels

    specs = _shared_vega_specs()
    kpi_md = _kpi_markdown()
    fe_url = _dashboard_url(DASHBOARD_ID)
    customer_url = _dashboard_url(CUSTOMER_DASHBOARD_ID)
    # Customer panels are the canonical inner block (do not mutate).
    cu_panels = _build_panels("customer", specs, kpi_md, fe_url, customer_url,
                              lens_dv_id=lens_dv_id)
    # FE-only extras: take the existing FE panel set and keep only the
    # markdown panels (talk track, MEDDPICC) - drop charts that are already
    # in the customer view to avoid duplication.
    legacy_fe = _build_panels("fe", specs, kpi_md, fe_url, customer_url,
                              lens_dv_id=lens_dv_id)
    fe_only_extras = [p for p in legacy_fe
                      if p.get("embeddableConfig", {}).get("savedVis", {})
                          .get("type") == "markdown"
                      and p.get("panelIndex") not in ("switcher",)]
    return build_fe_superset_panels(
        _flagship_industry_context(),
        customer="Lumen Apparel Digital",
        customer_panels=cu_panels,
        fe_only_extras=fe_only_extras,
        id_prefix="bf-fe",
    )


def get_customer_panels(lens_dv_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Customer-view dashboard panels. Same Vega specs as the FE view; the only
    differences are the markdown panels framing the charts as a postmortem."""
    specs = _shared_vega_specs()
    kpi_md = _kpi_markdown()
    fe_url = _dashboard_url(DASHBOARD_ID)
    customer_url = _dashboard_url(CUSTOMER_DASHBOARD_ID)
    return _build_panels("customer", specs, kpi_md, fe_url, customer_url,
                         lens_dv_id=lens_dv_id)


# ============================================================ Seeder ===============


def _kbn_url(path: str) -> str:
    return settings.kibana_url.rstrip("/") + path


def _kbn_headers() -> Dict[str, str]:
    return {
        "Authorization": f"ApiKey {settings.kibana_api_key}",
        "Content-Type": "application/json",
        "kbn-xsrf": "fe-copilot",
    }


def _delete_dashboard(dashboard_id: str = DASHBOARD_ID) -> bool:
    url = _kbn_url(f"/api/saved_objects/dashboard/{dashboard_id}")
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.delete(url, headers=_kbn_headers())
        return resp.status_code < 400 or resp.status_code == 404
    except Exception as exc:
        log.warning("black_friday.dashboard.delete.exception",
                    dashboard_id=dashboard_id, error=str(exc))
        return False


def _create_one_dashboard(dashboard_id: str, title: str, description: str,
                          panels: List[Dict[str, Any]]) -> Tuple[str, str]:
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
        "id": dashboard_id,
        "type": "dashboard",
        "attributes": {
            "title": title,
            "description": description,
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
            f"Kibana dashboard create failed for {dashboard_id}: "
            f"{resp.status_code} {resp.text[:400]}"
        )
    return dashboard_id, _dashboard_url(dashboard_id)


def _create_dashboard(lens_dv_id: Optional[str] = None) -> Tuple[str, str]:
    """Create the FE-view dashboard. Title prefixed with [FE] so the user can
    spot it in Kibana's dashboard list. Reuses the shared Vega specs."""
    panels = get_dashboard_panels(lens_dv_id=lens_dv_id)
    title = f"[FE] {SCENARIO_TITLE} - Field Engineer view"
    description = (
        "Field Engineer view of the Black Friday outage. Includes MEDDPICC "
        "framing, source quotes, and how-to-demo annotations alongside the "
        "shared chart set."
    )
    return _create_one_dashboard(DASHBOARD_ID, title, description, panels)


def _create_customer_dashboard(lens_dv_id: Optional[str] = None) -> Tuple[str, str]:
    """Create the customer-facing postmortem dashboard. Same Vega panels as the
    FE view (literally the same inline values), wrapped in clean executive
    language. Idempotent: delete-then-create."""
    panels = get_customer_panels(lens_dv_id=lens_dv_id)
    title = f"[Customer] {SCENARIO_TITLE} - Postmortem"
    description = (
        "Customer-facing postmortem of the Black Friday outage. Same data and "
        "same charts as the FE view, framed as an executive briefing on "
        "business impact, recovery time, and outcomes Elastic would unlock."
    )
    return _create_one_dashboard(CUSTOMER_DASHBOARD_ID, title, description, panels)


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

    # Ensure the Lens data view exists before building the dashboard. If this
    # fails we fall back to the inline-data Vega panels (lens_dv_id stays None),
    # so the dashboard still renders correctly.
    metrics_index = INDICES["metrics"]
    lens_dv_id = _ensure_data_view(metrics_index, f"{metrics_index}-dv")
    if lens_dv_id:
        log.info("black_friday.data_view.ready", dv_id=lens_dv_id,
                 index=metrics_index)
    else:
        log.warning("black_friday.data_view.fallback",
                    index=metrics_index,
                    note="Lens upgrade skipped, using inline-data Vega panels.")

    # Dashboards: idempotent recreate of BOTH the FE and Customer views.
    # Each create is wrapped so a failure on one does not block the other.
    fe_id: Optional[str] = None
    fe_url: Optional[str] = None
    customer_id: Optional[str] = None
    customer_url: Optional[str] = None

    _delete_dashboard(DASHBOARD_ID)
    try:
        fe_id, fe_url = _create_dashboard(lens_dv_id=lens_dv_id)
        log.info("black_friday.dashboard.fe.created", id=fe_id, url=fe_url,
                 lens=bool(lens_dv_id))
    except Exception as exc:
        log.warning("black_friday.dashboard.fe.failed", error=str(exc))
        # If Lens upgrade caused the failure, retry once with inline-Vega only
        # so we never leave the user with a broken dashboard.
        if lens_dv_id is not None:
            try:
                fe_id, fe_url = _create_dashboard(lens_dv_id=None)
                log.info("black_friday.dashboard.fe.created.fallback",
                         id=fe_id, url=fe_url)
                lens_dv_id = None  # downgrade for the customer view too
            except Exception as exc2:
                log.warning("black_friday.dashboard.fe.fallback.failed",
                            error=str(exc2))

    _delete_dashboard(CUSTOMER_DASHBOARD_ID)
    try:
        customer_id, customer_url = _create_customer_dashboard(lens_dv_id=lens_dv_id)
        log.info("black_friday.dashboard.customer.created",
                 id=customer_id, url=customer_url, lens=bool(lens_dv_id))
    except Exception as exc:
        log.warning("black_friday.dashboard.customer.failed", error=str(exc))
        if lens_dv_id is not None:
            try:
                customer_id, customer_url = _create_customer_dashboard(lens_dv_id=None)
                log.info("black_friday.dashboard.customer.created.fallback",
                         id=customer_id, url=customer_url)
            except Exception as exc2:
                log.warning("black_friday.dashboard.customer.fallback.failed",
                            error=str(exc2))

    elapsed = round(time.time() - started, 2)
    return {
        "ok": True,
        "scenario": SCENARIO_ID,
        "indices": counts,
        "doc_count": sum(counts.values()),
        "dashboard_id": fe_id or DASHBOARD_ID,
        "dashboard_url": fe_url or _dashboard_url(DASHBOARD_ID),
        "fe_dashboard_id": fe_id,
        "fe_dashboard_url": fe_url,
        "customer_dashboard_id": customer_id,
        "customer_dashboard_url": customer_url,
        "lens_data_view_id": lens_dv_id,
        "lens_panels_enabled": bool(lens_dv_id),
        "elapsed_seconds": elapsed,
        "anomaly_windows": [
            {"label": w["label"], "start": w["start"].isoformat(),
             "end": w["end"].isoformat(), "severity": w["severity"]}
            for w in _anomaly_windows(_now_anchor())
        ],
    }
