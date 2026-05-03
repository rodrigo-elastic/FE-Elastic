"""
filename: noisy_microservice.py
description: Story-driven demo dataset for Elastic Observability - "One Bad Apple".
A fictional payments platform (Stride Payments) runs 10 microservices behind an API
gateway. The recently-deployed checkout-service produces ~80% of all errors despite
handling only ~12% of traffic. Three deployment events in the last 7 days each cause
discrete error-rate jumps; the latest (T-12h, v1.7.3) introduced a NullPointerException
regression. Other 9 services hold steady at <2% error rate with one or two harmless
transient blips for realism.

The module ships TWO dashboards backed by the same inline-data Vega panels:
  * `[FE] Noisy Microservice` - Field-Engineer prep view with talk track + MEDDPICC
  * `[Customer] Noisy Microservice` - SRE / Engineering Manager service-health report

Both dashboards share the same Vega panels. Every Vega panel is rendered with
inline `data.values` populated at seed time (Kibana 9.3 rejects URL-based Vega
specs at render time even when saved objects validate). Every ES query is wrapped
in try/except; on failure the chart falls back to empty values plus a warning log
and the seed still succeeds.

Public surface (kept stable for the Demo Data Generator):
    SCENARIO_ID, SCENARIO_TITLE, SCENARIO_DESCRIPTION
    INDICES, DASHBOARD_ID, CUSTOMER_DASHBOARD_ID
    get_mappings(), generate_documents(seed), get_dashboard_panels(), seed()
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.2.0"
__status__ = "Development"

import json
import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

import httpx
from elasticsearch import helpers as es_helpers

from app.config import settings
from app.integrations.elasticsearch_client import get_client
from app.utils.logging import get_logger

log = get_logger(__name__)


# ============================================================ Public constants ======

SCENARIO_ID: str = "noisy-microservice"
SCENARIO_TITLE: str = "Noisy Microservice (One Bad Apple)"
SCENARIO_DESCRIPTION: str = (
    "Stride Payments runs 10 microservices behind an API gateway. The recently-deployed "
    "checkout-service produces 80% of all errors despite handling only 12% of traffic, "
    "with three deployment events visible as discrete error-rate jumps over the last 7 days. "
    "Demonstrates Elastic Service Map, ML deployment regression detection, SLO burn-rate "
    "alerts, and Cases-driven incident response."
)

INDICES: Dict[str, str] = {
    "traces": "demo-noisy-traces",
    "logs": "demo-noisy-logs",
    "deployments": "demo-noisy-deployments",
}

DASHBOARD_ID: str = "demo-noisy-microservice-dashboard"
CUSTOMER_DASHBOARD_ID: str = "demo-noisy-microservice-customer-dashboard"


# ============================================================ Domain constants ======

_FICT_COMPANY = "Stride Payments"
_NAMESPACE = "stride-payments"
_REGIONS = ["us-east-1", "us-west-2", "eu-west-1"]
_NODES_PER_REGION = 3
_SLO_TARGET = 0.999
_ERROR_BUDGET_WEEKLY = 1.0 - _SLO_TARGET  # 0.001 = 0.1% of weekly traffic

# The 10 services. The first is the bad apple - heavy error weighting + rolling deploys.
# Each entry: (name, base_p50_ms, base_err_rate, traffic_weight, transactions, version_stable)
_SERVICES: List[Dict[str, Any]] = [
    {
        "name": "checkout-service",
        "p50_ms": 95.0,
        "p99_jitter": 2.4,
        "base_err": 0.018,        # baseline before deploys
        "traffic_weight": 0.12,    # 12% of total traffic, but 80% of errors
        "txns": [
            ("POST /checkout", "request"),
            ("POST /checkout/confirm", "request"),
            ("GET /checkout/{id}", "request"),
            ("POST /checkout/refund", "request"),
        ],
        "version": None,           # rolling - picked from deploys
        "team": "checkout-platform",
    },
    {
        "name": "payments-gateway",
        "p50_ms": 42.0,
        "p99_jitter": 1.8,
        "base_err": 0.005,
        "traffic_weight": 0.18,
        "txns": [("POST /pay/charge", "request"), ("POST /pay/auth", "request"),
                  ("POST /pay/capture", "request"), ("GET /pay/{id}", "request")],
        "version": "3.4.2",
        "team": "payments-core",
    },
    {
        "name": "billing-service",
        "p50_ms": 70.0, "p99_jitter": 2.0, "base_err": 0.006, "traffic_weight": 0.10,
        "txns": [("POST /invoices", "request"), ("GET /invoices/{id}", "request"),
                  ("POST /credits/apply", "request")],
        "version": "2.11.0", "team": "billing",
    },
    {
        "name": "ledger-service",
        "p50_ms": 55.0, "p99_jitter": 1.6, "base_err": 0.004, "traffic_weight": 0.09,
        "txns": [("POST /ledger/post", "request"), ("GET /ledger/balance", "request")],
        "version": "1.22.4", "team": "ledger-core",
    },
    {
        "name": "fraud-service",
        "p50_ms": 130.0, "p99_jitter": 2.2, "base_err": 0.008, "traffic_weight": 0.08,
        "txns": [("POST /fraud/score", "request"), ("POST /fraud/decision", "request")],
        "version": "0.9.8", "team": "fraud-ml",
    },
    {
        "name": "notifications-service",
        "p50_ms": 35.0, "p99_jitter": 1.4, "base_err": 0.007, "traffic_weight": 0.10,
        "txns": [("POST /notify/email", "request"), ("POST /notify/sms", "request"),
                  ("POST /notify/push", "request")],
        "version": "4.0.1", "team": "messaging",
    },
    {
        "name": "profile-service",
        "p50_ms": 28.0, "p99_jitter": 1.3, "base_err": 0.003, "traffic_weight": 0.08,
        "txns": [("GET /profile/{id}", "request"), ("PATCH /profile/{id}", "request")],
        "version": "5.6.0", "team": "identity",
    },
    {
        "name": "cart-service",
        "p50_ms": 38.0, "p99_jitter": 1.4, "base_err": 0.005, "traffic_weight": 0.10,
        "txns": [("POST /cart", "request"), ("GET /cart/{id}", "request"),
                  ("POST /cart/items", "request"), ("DELETE /cart/items/{sku}", "request")],
        "version": "2.3.7", "team": "checkout-platform",
    },
    {
        "name": "inventory-service",
        "p50_ms": 60.0, "p99_jitter": 1.7, "base_err": 0.007, "traffic_weight": 0.08,
        "txns": [("GET /inventory/{sku}", "request"), ("POST /inventory/reserve", "request")],
        "version": "1.14.2", "team": "supply",
    },
    {
        "name": "recs-service",
        "p50_ms": 110.0, "p99_jitter": 2.0, "base_err": 0.008, "traffic_weight": 0.07,
        "txns": [("GET /recs/{user}", "request"), ("POST /recs/feedback", "request")],
        "version": "0.7.3", "team": "ml-platform",
    },
]
_SERVICE_BY_NAME: Dict[str, Dict[str, Any]] = {s["name"]: s for s in _SERVICES}

# Deployment plan. Each entry produces a deployment record AND a regression curve in
# checkout-service traces.
# (hours_ago, version, commit_sha, severity, primary_error_type, blast_radius_min)
_CHECKOUT_DEPLOYS: List[Dict[str, Any]] = [
    {
        "hours_ago": 5 * 24,        # T-5d
        "version": "1.7.1",
        "commit_sha": "a4f9c21",
        "author": "marquez",
        "severity": 0.55,
        "ramp_minutes": 35,
        "plateau_err_rate": 0.18,
        "primary_error": "DBConnectionTimeout",
        "release_notes": "Connection pool refactor + retry budget bump.",
    },
    {
        "hours_ago": 3 * 24,        # T-3d
        "version": "1.7.2",
        "commit_sha": "bd8e137",
        "author": "patel",
        "severity": 0.7,
        "ramp_minutes": 45,
        "plateau_err_rate": 0.27,
        "primary_error": "JsonParseException",
        "release_notes": "Migrated DTO to schema v2; payload contract change.",
    },
    {
        "hours_ago": 12,            # T-12h - the worst
        "version": "1.7.3",
        "commit_sha": "c6d2410",
        "author": "okafor",
        "severity": 1.0,
        "ramp_minutes": 55,
        "plateau_err_rate": 0.42,
        "primary_error": "NullPointerException",
        "release_notes": "Add idempotency key extraction in CheckoutOrchestrator.",
    },
]
# checkout-service version baseline before any deploys
_CHECKOUT_BASE_VERSION = "1.7.0"

# Error types and weights for checkout-service.
# Roughly: NullPointerException 40%, DBConnectionTimeout 25%, JsonParseException 18%, RateLimitExceeded 17%
_CHECKOUT_ERRORS: List[Tuple[str, float]] = [
    ("NullPointerException", 0.40),
    ("DBConnectionTimeout", 0.25),
    ("JsonParseException", 0.18),
    ("RateLimitExceeded", 0.17),
]

# Stack traces - realistic class.method paths.
_STACKS: Dict[str, List[List[str]]] = {
    "NullPointerException": [
        [
            "com.stride.checkout.service.CheckoutOrchestrator.processOrder(CheckoutOrchestrator.java:142)",
            "com.stride.checkout.service.CheckoutOrchestrator.handle(CheckoutOrchestrator.java:74)",
            "com.stride.checkout.web.CheckoutController.confirm(CheckoutController.java:108)",
            "jdk.internal.reflect.GeneratedMethodAccessor217.invoke(Unknown Source)",
            "org.springframework.web.method.support.InvocableHandlerMethod.invokeForRequest(InvocableHandlerMethod.java:179)",
        ],
        [
            "com.stride.checkout.idempotency.IdempotencyKeyExtractor.extract(IdempotencyKeyExtractor.java:58)",
            "com.stride.checkout.service.CheckoutOrchestrator.processOrder(CheckoutOrchestrator.java:135)",
            "com.stride.checkout.web.CheckoutController.confirm(CheckoutController.java:108)",
            "org.springframework.aop.framework.ReflectiveMethodInvocation.proceed(ReflectiveMethodInvocation.java:179)",
        ],
        [
            "com.stride.checkout.cart.CartTotalCalculator.totals(CartTotalCalculator.java:91)",
            "com.stride.checkout.service.CheckoutOrchestrator.computeTotals(CheckoutOrchestrator.java:223)",
            "com.stride.checkout.service.CheckoutOrchestrator.processOrder(CheckoutOrchestrator.java:148)",
            "com.stride.checkout.web.CheckoutController.confirm(CheckoutController.java:108)",
        ],
    ],
    "DBConnectionTimeout": [
        [
            "com.stride.checkout.persistence.OrderRepository.save(OrderRepository.java:204)",
            "com.stride.checkout.service.CheckoutOrchestrator.persist(CheckoutOrchestrator.java:312)",
            "com.stride.checkout.service.CheckoutOrchestrator.processOrder(CheckoutOrchestrator.java:151)",
            "com.zaxxer.hikari.pool.HikariPool.getConnection(HikariPool.java:182)",
            "com.zaxxer.hikari.pool.HikariPool.createTimeoutException(HikariPool.java:683)",
        ],
        [
            "com.stride.checkout.persistence.OrderRepository.findById(OrderRepository.java:88)",
            "com.stride.checkout.service.CheckoutOrchestrator.lookup(CheckoutOrchestrator.java:280)",
            "com.zaxxer.hikari.pool.HikariPool.getConnection(HikariPool.java:182)",
            "java.util.concurrent.locks.AbstractQueuedSynchronizer.tryAcquireSharedNanos(AbstractQueuedSynchronizer.java:1084)",
        ],
    ],
    "JsonParseException": [
        [
            "com.fasterxml.jackson.core.JsonParser._reportUnexpectedChar(JsonParser.java:712)",
            "com.fasterxml.jackson.databind.ObjectMapper.readValue(ObjectMapper.java:3585)",
            "com.stride.checkout.dto.CheckoutPayloadDeserializer.deserialize(CheckoutPayloadDeserializer.java:64)",
            "com.stride.checkout.web.CheckoutController.confirm(CheckoutController.java:101)",
        ],
        [
            "com.fasterxml.jackson.databind.exc.MismatchedInputException.from(MismatchedInputException.java:64)",
            "com.stride.checkout.dto.SchemaV2Mapper.fromV1(SchemaV2Mapper.java:117)",
            "com.stride.checkout.web.CheckoutController.confirm(CheckoutController.java:101)",
        ],
    ],
    "RateLimitExceeded": [
        [
            "com.stride.checkout.ratelimit.TokenBucketLimiter.consume(TokenBucketLimiter.java:48)",
            "com.stride.checkout.web.RateLimitFilter.doFilter(RateLimitFilter.java:73)",
            "org.springframework.web.filter.OncePerRequestFilter.doFilter(OncePerRequestFilter.java:117)",
        ],
        [
            "com.stride.checkout.ratelimit.RedisRateLimiter.acquire(RedisRateLimiter.java:88)",
            "com.stride.checkout.web.RateLimitFilter.doFilter(RateLimitFilter.java:73)",
            "io.lettuce.core.RedisCommandTimeoutException.create(RedisCommandTimeoutException.java:58)",
        ],
    ],
}

_CHECKOUT_ERROR_MESSAGES: Dict[str, List[str]] = {
    "NullPointerException": [
        "Cannot invoke \"IdempotencyKey.value()\" because \"key\" is null",
        "null pointer dereference in CartTotalCalculator.totals - line items list returned null",
        "Cannot read field \"customerId\" of null OrderContext returned by upstream",
    ],
    "DBConnectionTimeout": [
        "HikariPool-1 - Connection is not available, request timed out after 30000ms",
        "Could not acquire connection from pool 'checkout-primary' after 30s; active=20, idle=0",
        "DataAccessResourceFailureException: connect timeout to checkout-db.stride.internal:5432",
    ],
    "JsonParseException": [
        "Unexpected character ('}' (code 125)): expected a value at [Source: line 14 col 3]",
        "Cannot deserialize value of type CheckoutPayload from missing field 'idempotency_key'",
        "Mismatched input: schema v2 requires 'cart_lines'; received legacy 'items'",
    ],
    "RateLimitExceeded": [
        "Rate limit exceeded for tenant t_3a8f: 200 rpm budget consumed",
        "Token bucket exhausted on /checkout/confirm; retry after 4.5s",
        "Redis CLUSTERDOWN during rate-limit acquire - failing closed",
    ],
}

# Generic transient error pool for the OTHER 9 services (kept rare).
_OTHER_ERRORS: List[Tuple[str, str]] = [
    ("UpstreamTimeout", "downstream call to fraud-service exceeded 5s budget"),
    ("CacheMiss", "soft cache miss on key user_pref:%(uid)s - recovered from origin"),
    ("DeserializationError", "unexpected nullable field 'legacy_id' in incoming payload"),
    ("RetryableUpstream", "503 from external partner; retry scheduled"),
    ("S3PutFailure", "S3 PutObject failed for bucket stride-receipts; will retry"),
    ("KafkaProducerError", "broker disconnect on stride.events.v1; reconnecting"),
]


# ============================================================ Helpers ===============


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(ts: datetime) -> str:
    return ts.replace(microsecond=int(ts.microsecond)).isoformat()


def _hex(rng: random.Random, n: int) -> str:
    return "%0*x" % (n, rng.getrandbits(n * 4))


def _short_sha(rng: random.Random) -> str:
    return _hex(rng, 7)


def _trace_id(rng: random.Random) -> str:
    return _hex(rng, 32)


def _span_id(rng: random.Random) -> str:
    return _hex(rng, 16)


def _weighted_choice(rng: random.Random, items: List[Tuple[Any, float]]) -> Any:
    total = sum(w for _, w in items)
    r = rng.random() * total
    upto = 0.0
    for v, w in items:
        upto += w
        if upto >= r:
            return v
    return items[-1][0]


def _checkout_err_rate(seconds_ago: float) -> Tuple[float, Dict[str, Any]]:
    """Return (error_rate, active_deploy_or_None) at a given seconds_ago.

    The pattern: baseline error rate, then each deployment causes a ramp from baseline
    up to plateau_err_rate over ramp_minutes, plateau holds until next deploy.
    Severity multiplies the plateau height. seconds_ago is positive (older = larger).
    """
    base = _SERVICE_BY_NAME["checkout-service"]["base_err"]
    # Convert deploys to seconds_ago and sort newest-first (smallest seconds_ago first).
    deploys_sorted = sorted(_CHECKOUT_DEPLOYS, key=lambda d: d["hours_ago"])
    # Find which deploy is currently active for this seconds_ago. A deploy at H hours ago
    # is "in effect" for events with seconds_ago <= H*3600 (more recent than the deploy).
    active = None
    for dep in deploys_sorted:
        dep_secs = dep["hours_ago"] * 3600
        if seconds_ago <= dep_secs:
            active = dep
            break
    if active is None:
        return base, None
    dep_secs = active["hours_ago"] * 3600
    elapsed_since_deploy = dep_secs - seconds_ago  # how long after the deploy this event happened
    ramp_secs = active["ramp_minutes"] * 60
    plateau = active["plateau_err_rate"]
    if elapsed_since_deploy <= 0:
        rate = base
    elif elapsed_since_deploy < ramp_secs:
        # linear ramp from base to plateau
        frac = elapsed_since_deploy / ramp_secs
        rate = base + (plateau - base) * frac
    else:
        rate = plateau
    return rate, active


def _service_err_rate(svc_name: str, seconds_ago: float, rng: random.Random) -> float:
    """Error rate for a non-checkout service. Tiny transient blips at fixed times."""
    if svc_name == "checkout-service":
        rate, _ = _checkout_err_rate(seconds_ago)
        return rate
    base = _SERVICE_BY_NAME[svc_name]["base_err"]
    # Two minor non-regression blips: one ~80h ago on inventory-service, one ~40h ago on fraud-service.
    if svc_name == "inventory-service":
        if 80 * 3600 - 8 * 60 <= seconds_ago <= 80 * 3600 + 8 * 60:
            return min(0.06, base * 4.5)
    if svc_name == "fraud-service":
        if 40 * 3600 - 6 * 60 <= seconds_ago <= 40 * 3600 + 6 * 60:
            return min(0.06, base * 4.0)
    return base


def _pod_name(rng: random.Random, svc_name: str, version: str) -> str:
    rs = _hex(rng, 5)
    pod_suffix = _hex(rng, 5)
    safe_ver = version.replace(".", "-")
    return f"{svc_name}-{safe_ver}-{rs}-{pod_suffix}"


def _replica_set(svc_name: str, version: str) -> str:
    safe_ver = version.replace(".", "-")
    return f"{svc_name}-{safe_ver}"


def _node_name(rng: random.Random, region: str) -> str:
    return f"gke-{region}-node-{rng.randint(1, _NODES_PER_REGION):02d}"


def _latency_us(rng: random.Random, svc: Dict[str, Any], is_error: bool, deploy_active: bool) -> int:
    """Lognormal-ish latency tail. Errors and post-deploy events are slower."""
    p50 = svc["p50_ms"]
    sigma = 0.45 if not is_error else 0.85
    mu = (p50)
    # base lognormal-ish via gauss in log-space
    val_ms = max(1.0, mu * (1.0 + rng.lognormvariate(0.0, sigma) - 1.0))
    if deploy_active:
        val_ms *= 1.0 + rng.uniform(0.05, 0.45)
    if is_error:
        val_ms *= 1.0 + rng.uniform(0.2, 1.5)
    # Add an occasional p99 spike
    if rng.random() < svc["p99_jitter"] / 100:
        val_ms *= rng.uniform(3.0, 8.0)
    return int(max(1500, val_ms * 1000))  # microseconds, floor 1.5ms


def _checkout_active_version(seconds_ago: float) -> Tuple[str, str, str]:
    """Return (version, commit_sha, author) of checkout-service at the given seconds_ago."""
    deploys_sorted = sorted(_CHECKOUT_DEPLOYS, key=lambda d: d["hours_ago"])
    # Newest-first walk: find first deploy whose dep_secs >= seconds_ago (i.e. event happened after it).
    for dep in deploys_sorted:
        dep_secs = dep["hours_ago"] * 3600
        if seconds_ago <= dep_secs:
            return dep["version"], dep["commit_sha"], dep["author"]
    return _CHECKOUT_BASE_VERSION, "9b1e040", "marquez"


# ============================================================ Mappings ==============


def get_mappings() -> Dict[str, Dict[str, Any]]:
    common_props = {
        "@timestamp": {"type": "date"},
        "service": {
            "properties": {
                "name": {"type": "keyword"},
                "version": {"type": "keyword"},
                "environment": {"type": "keyword"},
                "team": {"type": "keyword"},
            }
        },
        "host": {"properties": {"name": {"type": "keyword"}, "id": {"type": "keyword"}}},
        "cloud": {
            "properties": {
                "provider": {"type": "keyword"},
                "region": {"type": "keyword"},
                "availability_zone": {"type": "keyword"},
            }
        },
        "kubernetes": {
            "properties": {
                "namespace": {"type": "keyword"},
                "deployment": {"properties": {"name": {"type": "keyword"}}},
                "replica_set": {"properties": {"name": {"type": "keyword"}}},
                "pod": {"properties": {"name": {"type": "keyword"}, "uid": {"type": "keyword"}}},
                "node": {"properties": {"name": {"type": "keyword"}}},
                "container": {"properties": {"name": {"type": "keyword"}}},
            }
        },
        "event": {
            "properties": {
                "outcome": {"type": "keyword"},
                "action": {"type": "keyword"},
                "category": {"type": "keyword"},
                "kind": {"type": "keyword"},
                "dataset": {"type": "keyword"},
            }
        },
        "release": {
            "properties": {
                "commit_sha": {"type": "keyword"},
                "author": {"type": "keyword"},
                "version": {"type": "keyword"},
                "notes": {"type": "text"},
            }
        },
        "slo": {"properties": {"target": {"type": "float"}, "name": {"type": "keyword"}}},
    }

    traces_props = dict(common_props)
    traces_props.update({
        "trace": {"properties": {"id": {"type": "keyword"}}},
        "transaction": {
            "properties": {
                "id": {"type": "keyword"},
                "name": {"type": "keyword"},
                "type": {"type": "keyword"},
                "result": {"type": "keyword"},
                "duration": {"properties": {"us": {"type": "long"}}},
                "sampled": {"type": "boolean"},
            }
        },
        "span": {
            "properties": {
                "id": {"type": "keyword"},
                "name": {"type": "keyword"},
                "type": {"type": "keyword"},
                "duration": {"properties": {"us": {"type": "long"}}},
            }
        },
        "http": {
            "properties": {
                "request": {"properties": {"method": {"type": "keyword"}}},
                "response": {"properties": {"status_code": {"type": "long"}}},
            }
        },
        "url": {"properties": {"path": {"type": "keyword"}}},
        "error": {
            "properties": {
                "id": {"type": "keyword"},
                "type": {"type": "keyword"},
                "message": {"type": "text"},
                "stack_trace": {"type": "text"},
                "grouping_key": {"type": "keyword"},
            }
        },
        "user": {"properties": {"id": {"type": "keyword"}}},
    })

    logs_props = dict(common_props)
    logs_props.update({
        "trace": {"properties": {"id": {"type": "keyword"}}},
        "transaction": {"properties": {"id": {"type": "keyword"}}},
        "log": {
            "properties": {
                "level": {"type": "keyword"},
                "logger": {"type": "keyword"},
            }
        },
        "message": {"type": "text"},
        "error": {
            "properties": {
                "type": {"type": "keyword"},
                "message": {"type": "text"},
                "stack_trace": {"type": "text"},
            }
        },
    })

    deployments_props = dict(common_props)
    deployments_props.update({
        "message": {"type": "text"},
        "deployment": {
            "properties": {
                "id": {"type": "keyword"},
                "name": {"type": "keyword"},
                "strategy": {"type": "keyword"},
                "previous_version": {"type": "keyword"},
                "next_version": {"type": "keyword"},
                "result": {"type": "keyword"},
                "duration_seconds": {"type": "long"},
                "rolled_back": {"type": "boolean"},
            }
        },
    })

    return {
        INDICES["traces"]: {
            "settings": {"number_of_shards": 1, "number_of_replicas": 0,
                          "index": {"refresh_interval": "1s"}},
            "mappings": {"dynamic": "true", "properties": traces_props},
        },
        INDICES["logs"]: {
            "settings": {"number_of_shards": 1, "number_of_replicas": 0,
                          "index": {"refresh_interval": "1s"}},
            "mappings": {"dynamic": "true", "properties": logs_props},
        },
        INDICES["deployments"]: {
            "settings": {"number_of_shards": 1, "number_of_replicas": 0,
                          "index": {"refresh_interval": "1s"}},
            "mappings": {"dynamic": "true", "properties": deployments_props},
        },
    }


# ============================================================ Generators ============


def generate_documents(seed: int = 20260503) -> Dict[str, List[Dict[str, Any]]]:
    """Generate the three datasets. Deterministic given the seed."""
    rng = random.Random(seed)
    now = _now()

    traces: List[Dict[str, Any]] = []
    logs: List[Dict[str, Any]] = []
    deployments: List[Dict[str, Any]] = []

    # ---- Deployment events (~30 docs) ----
    deployments.extend(_gen_deployments(rng, now))

    # ---- Traces (~5500 docs) ----
    # Aim: 12% checkout, 88% other; checkout dominates errors via err_rate curve.
    target_traces = 5500
    # Pre-compute traffic distribution
    weights = [(s["name"], s["traffic_weight"]) for s in _SERVICES]
    total_w = sum(w for _, w in weights)
    weights = [(n, w / total_w) for n, w in weights]

    for _ in range(target_traces):
        # Pick service by weight
        svc_name = _weighted_choice(rng, weights)
        # Pick a timestamp. For checkout-service oversample around deploys to make the
        # post-deploy ramp visible at 5-min granularity.
        seconds_ago = _pick_seconds_ago(rng, svc_name)
        traces.append(_make_trace_doc(rng, now, svc_name, seconds_ago))

    # Pod restart events stitched into traces (10 restarts, around the worst deploy).
    pod_restarts = _gen_pod_restart_logs(rng, now)
    logs.extend(pod_restarts)

    # ---- Logs (~3500 docs) - correlated app logs and stack traces ----
    target_logs = 3500 - len(pod_restarts)
    for _ in range(target_logs):
        svc_name = _weighted_choice(rng, weights)
        seconds_ago = _pick_seconds_ago(rng, svc_name)
        logs.append(_make_log_doc(rng, now, svc_name, seconds_ago))

    return {
        INDICES["traces"]: traces,
        INDICES["logs"]: logs,
        INDICES["deployments"]: deployments,
    }


def _pick_seconds_ago(rng: random.Random, svc_name: str) -> float:
    """Time picker. Most events in the last 7 days; for checkout-service slightly oversample
    the windows just after each deploy to reveal the regression at 5-min granularity."""
    week = 7 * 24 * 3600
    if svc_name == "checkout-service" and rng.random() < 0.55:
        # Bias around a deploy
        dep = rng.choice(_CHECKOUT_DEPLOYS)
        dep_secs = dep["hours_ago"] * 3600
        # window: from deploy time forward (smaller seconds_ago) for ramp_minutes*5
        w = max(60 * 60, dep["ramp_minutes"] * 60 * 5)
        return max(0.0, dep_secs - rng.uniform(0, w))
    return rng.uniform(0, week)


def _make_trace_doc(rng: random.Random, now: datetime, svc_name: str, seconds_ago: float) -> Dict[str, Any]:
    svc = _SERVICE_BY_NAME[svc_name]
    if svc_name == "checkout-service":
        version, commit_sha, author = _checkout_active_version(seconds_ago)
        err_rate, active_deploy = _checkout_err_rate(seconds_ago)
        deploy_active = active_deploy is not None
    else:
        version = svc["version"] or "0.1.0"
        commit_sha = _short_sha(random.Random(hash(svc_name) & 0xFFFFFFFF))  # stable per svc
        author = ""
        err_rate = _service_err_rate(svc_name, seconds_ago, rng)
        deploy_active = False

    is_error = rng.random() < err_rate
    txn_name, txn_type = rng.choice(svc["txns"])
    duration_us = _latency_us(rng, svc, is_error, deploy_active)

    region = rng.choice(_REGIONS)
    az = f"{region}{rng.choice(['a', 'b', 'c'])}"
    pod = _pod_name(rng, svc_name, version)
    node = _node_name(rng, region)

    ts = now - timedelta(seconds=seconds_ago)
    doc: Dict[str, Any] = {
        "@timestamp": _iso(ts),
        "service": {
            "name": svc_name,
            "version": version,
            "environment": "production",
            "team": svc["team"],
        },
        "host": {"name": pod, "id": _hex(rng, 16)},
        "cloud": {"provider": "gcp", "region": region, "availability_zone": az},
        "kubernetes": {
            "namespace": _NAMESPACE,
            "deployment": {"name": svc_name},
            "replica_set": {"name": _replica_set(svc_name, version)},
            "pod": {"name": pod, "uid": _hex(rng, 16)},
            "node": {"name": node},
            "container": {"name": svc_name},
        },
        "trace": {"id": _trace_id(rng)},
        "transaction": {
            "id": _span_id(rng),
            "name": txn_name,
            "type": txn_type,
            "duration": {"us": duration_us},
            "sampled": True,
        },
        "span": {"name": txn_name, "type": txn_type, "duration": {"us": duration_us}},
        "http": {
            "request": {"method": txn_name.split(" ")[0]},
            "response": {"status_code": 500 if is_error else 200},
        },
        "url": {"path": txn_name.split(" ", 1)[1] if " " in txn_name else "/"},
        "event": {
            "outcome": "failure" if is_error else "success",
            "action": "transaction",
            "category": ["application"],
            "kind": "event",
            "dataset": "apm.transaction",
        },
        "release": {"commit_sha": commit_sha, "author": author, "version": version},
        "slo": {"target": _SLO_TARGET, "name": f"{svc_name}-availability"},
        "user": {"id": f"u-{rng.randint(1, 99999):05d}"},
    }
    if is_error:
        if svc_name == "checkout-service":
            err_type = _weighted_choice(rng, _CHECKOUT_ERRORS)
            stack = rng.choice(_STACKS[err_type])
            msg = rng.choice(_CHECKOUT_ERROR_MESSAGES[err_type])
            doc["transaction"]["result"] = "HTTP 5xx"
            doc["error"] = {
                "id": _span_id(rng),
                "type": err_type,
                "message": msg,
                "stack_trace": "\n".join(f"\tat {f}" for f in stack),
                "grouping_key": _hex(rng, 16),
            }
        else:
            err_type, err_msg = rng.choice(_OTHER_ERRORS)
            err_msg = err_msg % {"uid": rng.randint(1, 99999)} if "%(uid)" in err_msg else err_msg
            doc["transaction"]["result"] = "HTTP 5xx"
            doc["error"] = {
                "id": _span_id(rng),
                "type": err_type,
                "message": err_msg,
                "grouping_key": _hex(rng, 16),
            }
    else:
        doc["transaction"]["result"] = "HTTP 2xx"
    return doc


def _make_log_doc(rng: random.Random, now: datetime, svc_name: str, seconds_ago: float) -> Dict[str, Any]:
    svc = _SERVICE_BY_NAME[svc_name]
    if svc_name == "checkout-service":
        version, commit_sha, author = _checkout_active_version(seconds_ago)
        err_rate, _ = _checkout_err_rate(seconds_ago)
    else:
        version = svc["version"] or "0.1.0"
        commit_sha = _short_sha(random.Random(hash(svc_name) & 0xFFFFFFFF))
        author = ""
        err_rate = _service_err_rate(svc_name, seconds_ago, rng)

    is_error = rng.random() < err_rate
    region = rng.choice(_REGIONS)
    pod = _pod_name(rng, svc_name, version)
    ts = now - timedelta(seconds=seconds_ago)

    if is_error and svc_name == "checkout-service":
        err_type = _weighted_choice(rng, _CHECKOUT_ERRORS)
        stack = rng.choice(_STACKS[err_type])
        msg = rng.choice(_CHECKOUT_ERROR_MESSAGES[err_type])
        level = "ERROR"
        message = f"{err_type}: {msg}"
        stack_text = "\n".join(f"\tat {f}" for f in stack)
        error_block = {"type": err_type, "message": msg, "stack_trace": stack_text}
    elif is_error:
        err_type, err_msg = rng.choice(_OTHER_ERRORS)
        err_msg = err_msg % {"uid": rng.randint(1, 99999)} if "%(uid)" in err_msg else err_msg
        level = rng.choice(["WARN", "ERROR"])
        message = f"{err_type}: {err_msg}"
        error_block = {"type": err_type, "message": err_msg}
    else:
        level = rng.choices(["DEBUG", "INFO", "INFO", "INFO", "WARN"], k=1)[0]
        message = rng.choice([
            "request handled in %dms" % rng.randint(8, 220),
            "cache hit for key user_pref",
            "downstream call ok",
            "background job complete",
            "metrics flushed to OTel collector",
            "warm pool replenished",
        ])
        error_block = None

    doc = {
        "@timestamp": _iso(ts),
        "service": {
            "name": svc_name, "version": version,
            "environment": "production", "team": svc["team"],
        },
        "host": {"name": pod, "id": _hex(rng, 16)},
        "cloud": {"provider": "gcp", "region": region},
        "kubernetes": {
            "namespace": _NAMESPACE,
            "deployment": {"name": svc_name},
            "replica_set": {"name": _replica_set(svc_name, version)},
            "pod": {"name": pod},
            "container": {"name": svc_name},
        },
        "log": {"level": level, "logger": f"com.stride.{svc_name.replace('-', '.')}"},
        "message": message,
        "trace": {"id": _trace_id(rng)},
        "transaction": {"id": _span_id(rng)},
        "event": {
            "outcome": "failure" if is_error else "success",
            "action": "log",
            "category": ["application"],
            "kind": "event",
            "dataset": "app.logs",
        },
        "release": {"commit_sha": commit_sha, "author": author, "version": version},
    }
    if error_block:
        doc["error"] = error_block
    return doc


def _gen_deployments(rng: random.Random, now: datetime) -> List[Dict[str, Any]]:
    """Deployment events (~30 docs). Three for checkout-service (the regressions),
    plus stable rollouts for the other 9 services scattered earlier in the week."""
    docs: List[Dict[str, Any]] = []

    # Checkout - three rolling deploys
    prev_version = _CHECKOUT_BASE_VERSION
    for dep in sorted(_CHECKOUT_DEPLOYS, key=lambda d: -d["hours_ago"]):
        ts = now - timedelta(hours=dep["hours_ago"])
        dur = rng.randint(180, 480)
        docs.append({
            "@timestamp": _iso(ts),
            "service": {"name": "checkout-service", "version": dep["version"],
                         "environment": "production", "team": "checkout-platform"},
            "kubernetes": {
                "namespace": _NAMESPACE,
                "deployment": {"name": "checkout-service"},
                "replica_set": {"name": _replica_set("checkout-service", dep["version"])},
            },
            "cloud": {"provider": "gcp", "region": rng.choice(_REGIONS)},
            "event": {
                "kind": "event", "category": ["configuration"],
                "action": "deployment", "outcome": "success",
                "dataset": "kubernetes.deployment",
            },
            "release": {
                "commit_sha": dep["commit_sha"], "author": dep["author"],
                "version": dep["version"], "notes": dep["release_notes"],
            },
            "deployment": {
                "id": f"dep-{dep['commit_sha']}",
                "name": f"checkout-service rollout {dep['version']}",
                "strategy": "RollingUpdate",
                "previous_version": prev_version,
                "next_version": dep["version"],
                "result": "succeeded",
                "duration_seconds": dur,
                "rolled_back": False,
            },
            "message": (
                f"checkout-service rolled from {prev_version} to {dep['version']} "
                f"by {dep['author']} (sha {dep['commit_sha']}): {dep['release_notes']}"
            ),
        })
        prev_version = dep["version"]

    # Other services: 2-4 stable deploys each, scattered in the past 7 days, no incidents.
    for svc in _SERVICES:
        if svc["name"] == "checkout-service":
            continue
        n = rng.choice([2, 3, 3, 4])
        for _ in range(n):
            hours_ago = rng.uniform(8, 7 * 24 - 4)
            ts = now - timedelta(hours=hours_ago)
            ver = svc["version"]
            sha = _short_sha(rng)
            author = rng.choice(["chen", "patel", "okafor", "marquez", "haddad", "schmidt", "iyer"])
            docs.append({
                "@timestamp": _iso(ts),
                "service": {"name": svc["name"], "version": ver,
                             "environment": "production", "team": svc["team"]},
                "kubernetes": {
                    "namespace": _NAMESPACE,
                    "deployment": {"name": svc["name"]},
                    "replica_set": {"name": _replica_set(svc["name"], ver)},
                },
                "cloud": {"provider": "gcp", "region": rng.choice(_REGIONS)},
                "event": {
                    "kind": "event", "category": ["configuration"],
                    "action": "deployment", "outcome": "success",
                    "dataset": "kubernetes.deployment",
                },
                "release": {"commit_sha": sha, "author": author, "version": ver,
                             "notes": "routine patch - dependency bump and metrics polish."},
                "deployment": {
                    "id": f"dep-{sha}",
                    "name": f"{svc['name']} rollout {ver}",
                    "strategy": "RollingUpdate",
                    "previous_version": ver,  # patch-level - same minor
                    "next_version": ver,
                    "result": "succeeded",
                    "duration_seconds": rng.randint(120, 360),
                    "rolled_back": False,
                },
                "message": f"{svc['name']} rolled out patch {ver} by {author} (sha {sha})",
            })
    return docs


def _gen_pod_restart_logs(rng: random.Random, now: datetime) -> List[Dict[str, Any]]:
    """10 pod restart events for checkout-service, clustered around deploy windows."""
    docs: List[Dict[str, Any]] = []
    # Distribute 10 restarts: 2 around T-5d, 3 around T-3d, 5 around T-12h (worst).
    plan = [(_CHECKOUT_DEPLOYS[0], 2), (_CHECKOUT_DEPLOYS[1], 3), (_CHECKOUT_DEPLOYS[2], 5)]
    for dep, n in plan:
        for _ in range(n):
            offset_min = rng.uniform(2, max(8, dep["ramp_minutes"]))
            seconds_ago = max(0.0, dep["hours_ago"] * 3600 - offset_min * 60)
            ts = now - timedelta(seconds=seconds_ago)
            ver = dep["version"]
            pod = _pod_name(rng, "checkout-service", ver)
            reason = rng.choice([
                "OOMKilled - memory cgroup exceeded 1.5Gi limit",
                "CrashLoopBackOff - exit code 137",
                "Liveness probe failed: HTTP 503 from /healthz",
                "Readiness probe failed for 90s - kubelet restarted container",
            ])
            docs.append({
                "@timestamp": _iso(ts),
                "service": {"name": "checkout-service", "version": ver,
                             "environment": "production", "team": "checkout-platform"},
                "kubernetes": {
                    "namespace": _NAMESPACE,
                    "deployment": {"name": "checkout-service"},
                    "replica_set": {"name": _replica_set("checkout-service", ver)},
                    "pod": {"name": pod},
                    "container": {"name": "checkout-service"},
                },
                "host": {"name": pod},
                "cloud": {"provider": "gcp", "region": rng.choice(_REGIONS)},
                "log": {"level": "ERROR", "logger": "kubelet"},
                "message": f"Pod {pod} restarted: {reason}",
                "event": {
                    "kind": "event", "category": ["process"],
                    "action": "pod-restart", "outcome": "failure",
                    "dataset": "kubernetes.events",
                },
                "release": {"commit_sha": dep["commit_sha"], "author": dep["author"], "version": ver},
                "error": {"type": "PodRestart", "message": reason},
            })
    return docs


# ============================================================ Vega specs (inline) ===
#
# Every chart embeds `data.values` populated at seed time. Kibana 9.3 rejects
# URL-based Vega specs at render time even though the saved object validates -
# inline data is the only reliable rendering path. Each helper wraps its ES
# query in try/except; on failure the chart degrades to an empty values list
# and a structured warning is emitted but seed() still completes.


def _spec_errors_by_service() -> Dict[str, Any]:
    """Horizontal bar - total errors per service over the last 7 days. The bad
    apple (`checkout-service`) is forced red; all others share a calm green."""
    values: List[Dict[str, Any]] = []
    try:
        es = get_client()
        r = es.search(index=INDICES["traces"], body={
            "size": 0,
            "query": {"bool": {"filter": [
                {"term": {"event.outcome": "failure"}},
                {"range": {"@timestamp": {"gte": "now-7d", "lte": "now"}}},
            ]}},
            "aggs": {
                "by_svc": {
                    "terms": {"field": "service.name", "size": 20,
                               "order": {"_count": "desc"}},
                },
            },
        })
        for b in r["aggregations"]["by_svc"]["buckets"]:
            values.append({"service": b["key"], "errors": int(b["doc_count"])})
    except Exception as exc:
        log.warning("noisy_microservice.spec_errors_by_service.failed", error=str(exc))

    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": {"text": "Errors by service (last 7d) - checkout-service dominates",
                  "fontSize": 14, "anchor": "start"},
        "data": {"values": values},
        "mark": {"type": "bar", "tooltip": True, "cornerRadiusEnd": 3},
        "encoding": {
            "y": {"field": "service", "type": "nominal", "sort": "-x", "title": "service"},
            "x": {"field": "errors", "type": "quantitative", "title": "error count"},
            "color": {
                "condition": {"test": "datum.service == 'checkout-service'", "value": "#e7664c"},
                "value": "#54b399",
            },
            "tooltip": [
                {"field": "service", "type": "nominal", "title": "service.name"},
                {"field": "errors", "type": "quantitative", "title": "errors"},
            ],
        },
    }


def _spec_error_rate_over_time() -> Dict[str, Any]:
    """Line chart - error rate % per service per 30-minute bucket over 7 days.
    Bucketing at 30m keeps the inline payload modest (~340 rows max)."""
    values: List[Dict[str, Any]] = []
    palette = {
        "checkout-service": "#e7664c",
        "payments-gateway": "#54b399",
        "billing-service": "#9ab8d3",
        "ledger-service": "#aaaaaa",
        "fraud-service": "#d6bf57",
        "notifications-service": "#a987d1",
        "profile-service": "#7eaecf",
        "cart-service": "#7c8a99",
        "inventory-service": "#c1a98c",
        "recs-service": "#7d9d7d",
    }
    try:
        es = get_client()
        r = es.search(index=INDICES["traces"], body={
            "size": 0,
            "query": {"bool": {"filter": [
                {"range": {"@timestamp": {"gte": "now-7d", "lte": "now"}}},
            ]}},
            "aggs": {
                "by_time": {
                    "date_histogram": {"field": "@timestamp",
                                         "fixed_interval": "30m",
                                         "min_doc_count": 1},
                    "aggs": {
                        "by_svc": {
                            "terms": {"field": "service.name", "size": 12},
                            "aggs": {
                                "fail": {"filter": {"term": {"event.outcome": "failure"}}},
                            },
                        },
                    },
                },
            },
        })
        for tb in r["aggregations"]["by_time"]["buckets"]:
            ts = tb.get("key_as_string") or tb.get("key")
            for sb in tb["by_svc"]["buckets"]:
                total = int(sb["doc_count"])
                if total <= 0:
                    continue
                fails = int((sb.get("fail") or {}).get("doc_count", 0))
                rate_pct = round((fails / total) * 100.0, 4)
                values.append({"time": ts, "service": sb["key"], "error_rate_pct": rate_pct})
    except Exception as exc:
        log.warning("noisy_microservice.spec_error_rate_over_time.failed", error=str(exc))

    domain = list(palette.keys())
    rng_colors = [palette[k] for k in domain]
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": {"text": "Error rate % by service (30-min buckets) - three deploys land on checkout-service",
                  "fontSize": 14, "anchor": "start"},
        "data": {"values": values},
        "mark": {"type": "line", "interpolate": "monotone", "point": False,
                  "tooltip": True, "strokeWidth": 2},
        "encoding": {
            "x": {"field": "time", "type": "temporal", "title": None},
            "y": {"field": "error_rate_pct", "type": "quantitative", "title": "error rate (%)"},
            "color": {
                "field": "service", "type": "nominal",
                "scale": {"domain": domain, "range": rng_colors},
                "legend": {"title": "service"},
            },
            "tooltip": [
                {"field": "time", "type": "temporal", "title": "time"},
                {"field": "service", "type": "nominal", "title": "service"},
                {"field": "error_rate_pct", "type": "quantitative", "title": "error %", "format": ".2f"},
            ],
        },
    }


def _spec_top_error_types() -> Dict[str, Any]:
    """Horizontal bar - top error.type buckets for checkout-service alone."""
    values: List[Dict[str, Any]] = []
    try:
        es = get_client()
        r = es.search(index=INDICES["traces"], body={
            "size": 0,
            "query": {"bool": {"filter": [
                {"term": {"service.name": "checkout-service"}},
                {"term": {"event.outcome": "failure"}},
                {"range": {"@timestamp": {"gte": "now-7d", "lte": "now"}}},
            ]}},
            "aggs": {
                "by_err": {"terms": {"field": "error.type", "size": 8,
                                       "order": {"_count": "desc"}}},
            },
        })
        for b in r["aggregations"]["by_err"]["buckets"]:
            values.append({"error_type": b["key"], "count": int(b["doc_count"])})
    except Exception as exc:
        log.warning("noisy_microservice.spec_top_error_types.failed", error=str(exc))

    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": {"text": "Top error.type - checkout-service (last 7d)",
                  "fontSize": 14, "anchor": "start"},
        "data": {"values": values},
        "mark": {"type": "bar", "tooltip": True, "cornerRadiusEnd": 3, "color": "#e7664c"},
        "encoding": {
            "y": {"field": "error_type", "type": "nominal", "sort": "-x", "title": "error.type"},
            "x": {"field": "count", "type": "quantitative", "title": "count"},
            "tooltip": [
                {"field": "error_type", "type": "nominal", "title": "error.type"},
                {"field": "count", "type": "quantitative", "title": "count"},
            ],
        },
    }


def _spec_deploy_timeline(now: datetime) -> Dict[str, Any]:
    """Layered chart - shaded area of checkout-service error rate plus vertical
    rules + labels for each of the three rolling deploys. New `value` chart for
    the FE narrative ("walk through the deploy correlation")."""
    rate_values: List[Dict[str, Any]] = []
    try:
        es = get_client()
        r = es.search(index=INDICES["traces"], body={
            "size": 0,
            "query": {"bool": {"filter": [
                {"term": {"service.name": "checkout-service"}},
                {"range": {"@timestamp": {"gte": "now-7d", "lte": "now"}}},
            ]}},
            "aggs": {
                "by_time": {
                    "date_histogram": {"field": "@timestamp",
                                         "fixed_interval": "30m",
                                         "min_doc_count": 1},
                    "aggs": {"fail": {"filter": {"term": {"event.outcome": "failure"}}}},
                },
            },
        })
        for b in r["aggregations"]["by_time"]["buckets"]:
            total = int(b["doc_count"])
            if total <= 0:
                continue
            fails = int((b.get("fail") or {}).get("doc_count", 0))
            rate_values.append({
                "time": b.get("key_as_string") or b.get("key"),
                "txns": total,
                "rate_pct": round((fails / total) * 100.0, 4),
            })
    except Exception as exc:
        log.warning("noisy_microservice.spec_deploy_timeline.failed", error=str(exc))

    deploy_values: List[Dict[str, Any]] = []
    for dep in _CHECKOUT_DEPLOYS:
        ts = now - timedelta(hours=dep["hours_ago"])
        deploy_values.append({
            "time": _iso(ts),
            "label": f"v{dep['version']} ({dep['commit_sha']})",
        })

    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": {"text": "Deployment regression timeline - deploys vs checkout-service error rate",
                  "fontSize": 14, "anchor": "start"},
        "layer": [
            {
                "data": {"values": rate_values},
                "mark": {"type": "area", "color": "#e7664c", "opacity": 0.55,
                          "interpolate": "monotone",
                          "line": {"color": "#bd271e", "strokeWidth": 1.5},
                          "tooltip": True},
                "encoding": {
                    "x": {"field": "time", "type": "temporal", "title": None},
                    "y": {"field": "rate_pct", "type": "quantitative", "title": "checkout-service error %"},
                    "tooltip": [
                        {"field": "time", "type": "temporal", "title": "time"},
                        {"field": "txns", "type": "quantitative", "title": "txns"},
                        {"field": "rate_pct", "type": "quantitative", "title": "error %", "format": ".2f"},
                    ],
                },
            },
            {
                "data": {"values": deploy_values},
                "mark": {"type": "rule", "color": "#1d3c4f", "strokeWidth": 2,
                          "strokeDash": [6, 4]},
                "encoding": {
                    "x": {"field": "time", "type": "temporal"},
                    "tooltip": [
                        {"field": "label", "type": "nominal", "title": "deploy"},
                        {"field": "time", "type": "temporal", "title": "time"},
                    ],
                },
            },
            {
                "data": {"values": deploy_values},
                "mark": {"type": "text", "align": "left", "dx": 4, "dy": -6,
                          "color": "#1d3c4f", "fontSize": 11, "fontWeight": "bold"},
                "encoding": {
                    "x": {"field": "time", "type": "temporal"},
                    "y": {"datum": 0, "type": "quantitative"},
                    "text": {"field": "label", "type": "nominal"},
                },
            },
        ],
    }


def _spec_error_budget_burn(now: datetime) -> Dict[str, Any]:
    """Cumulative checkout-service error budget consumed over the last 7 days,
    expressed as a percentage of the weekly budget. Budget = (1 - SLO target)
    multiplied by total checkout-service requests in the window. Each bucket
    contributes (errors / budget) to the running total."""
    values: List[Dict[str, Any]] = []
    try:
        es = get_client()
        r = es.search(index=INDICES["traces"], body={
            "size": 0,
            "query": {"bool": {"filter": [
                {"term": {"service.name": "checkout-service"}},
                {"range": {"@timestamp": {"gte": "now-7d", "lte": "now"}}},
            ]}},
            "aggs": {
                "total": {"value_count": {"field": "@timestamp"}},
                "by_time": {
                    "date_histogram": {"field": "@timestamp",
                                         "fixed_interval": "1h",
                                         "min_doc_count": 0},
                    "aggs": {"fail": {"filter": {"term": {"event.outcome": "failure"}}}},
                },
            },
        })
        total_reqs = int(r["aggregations"]["total"]["value"] or 0)
        budget = max(1.0, total_reqs * _ERROR_BUDGET_WEEKLY)
        consumed = 0
        for b in r["aggregations"]["by_time"]["buckets"]:
            fails = int((b.get("fail") or {}).get("doc_count", 0))
            consumed += fails
            consumed_pct = round((consumed / budget) * 100.0, 3)
            values.append({
                "time": b.get("key_as_string") or b.get("key"),
                "consumed_pct": consumed_pct,
                "remaining_pct": max(0.0, round(100.0 - consumed_pct, 3)),
            })
    except Exception as exc:
        log.warning("noisy_microservice.spec_error_budget_burn.failed", error=str(exc))

    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": {"text": "Error budget burn-down - checkout-service (SLO 99.9% / 7d window)",
                  "fontSize": 14, "anchor": "start"},
        "layer": [
            {
                "data": {"values": values},
                "mark": {"type": "area", "color": "#e7664c", "opacity": 0.7,
                          "interpolate": "monotone", "tooltip": True,
                          "line": {"color": "#bd271e", "strokeWidth": 2}},
                "encoding": {
                    "x": {"field": "time", "type": "temporal", "title": None},
                    "y": {"field": "consumed_pct", "type": "quantitative",
                          "title": "weekly error budget consumed (%)"},
                    "tooltip": [
                        {"field": "time", "type": "temporal", "title": "time"},
                        {"field": "consumed_pct", "type": "quantitative",
                         "title": "consumed %", "format": ".2f"},
                        {"field": "remaining_pct", "type": "quantitative",
                         "title": "remaining %", "format": ".2f"},
                    ],
                },
            },
            {
                "data": {"values": [{"y": 100}]},
                "mark": {"type": "rule", "color": "#1d3c4f", "strokeDash": [4, 4],
                          "strokeWidth": 2},
                "encoding": {"y": {"field": "y", "type": "quantitative"}},
            },
        ],
    }


# ============================================================ Markdown panels =======


def _md_switcher(this_view: str) -> str:
    """Top-of-dashboard view switcher. `this_view` is "fe" or "customer"."""
    fe_url = f"#/view/{DASHBOARD_ID}"
    customer_url = f"#/view/{CUSTOMER_DASHBOARD_ID}"
    fe_marker = " (current)" if this_view == "fe" else ""
    cust_marker = " (current)" if this_view == "customer" else ""
    return (
        "### Noisy Microservice - dual-view demo\n\n"
        f"Switch view: "
        f"**[ [FE] talk track + MEDDPICC]({fe_url})**{fe_marker}  ·  "
        f"**[ [Customer] service-health report]({customer_url})**{cust_marker}\n\n"
        "_Same charts, same data. Only the framing changes._"
    )


def _md_fe_intro() -> str:
    return (
        "## [FE] One Bad Apple - Field Engineer prep\n"
        f"_{_FICT_COMPANY}_ runs **10 microservices** behind an API gateway. Over the last 7 days, "
        "the recently-deployed `checkout-service` (rolling **v1.7.0 -> v1.7.3**) has produced **~80% of all "
        "errors** despite handling only **~12%** of traffic. Three deployment events land as discrete "
        "error-rate jumps; the **T-12h** rollout (v1.7.3) introduced a `NullPointerException` regression.\n\n"
        "### Demo talk track (5 minutes)\n"
        "1. **Open Service Map first** - the 80/20 split is visually obvious; `checkout-service` lights up red while peers stay green.\n"
        "2. **Click into checkout-service** - show the `error.type` breakdown chart on this dashboard. NullPointerException dominates after T-12h.\n"
        "3. **Walk through the deploy correlation** - point at the *Deployment regression timeline* panel; three vertical rules align with three error-rate steps.\n"
        "4. **Show the error budget burn-down** - one chart tells the SRE the budget is gone for the week; this is the SLO conversation.\n"
        "5. **Close with Cases** - drag the failing trace into a Case, auto-attach the `release.commit_sha` (`c6d2410`, @okafor), and show the rollback PR.\n\n"
        "### MEDDPICC angle\n"
        "- **Pain**: silent post-deploy regressions; today MTTR is 90+ minutes because logs and APM are in two tools.\n"
        "- **Metrics**: target MTTR <15 min; deploy-to-detect <5 min; one console for SRE + on-call + management.\n"
        "- **Decision Criteria**: observability consolidation (APM + Logs + ML + SLO + Cases on one license, ECS taxonomy across all services).\n"
        "- **Champion enablement**: this dashboard is the demo asset - clone it for the customer's services in the trial."
    )


def _md_fe_closing() -> str:
    return (
        "## [FE] How Elastic catches this - playbook\n"
        "| Step | Elastic capability | What it surfaces |\n"
        "| --- | --- | --- |\n"
        "| 1 | **Service Map** (Observability) | Auto-rendered topology - `checkout-service` lights red while peers stay green; click-through into APM |\n"
        "| 2 | **APM transaction breakdown** | p50 / p99 latency per `transaction.name` - `POST /checkout/confirm` regressed 4x at T-12h |\n"
        "| 3 | **ML anomaly job** (`high_error_rate` + `apm_tx_metrics`) | Pre-built detectors flag the 5-min bucket within 1-2 buckets of the deploy |\n"
        "| 4 | **SLO burn-rate alert** (target 0.999) | Fast-burn alert at 14.4x in 5 min - pages the checkout on-call |\n"
        "| 5 | **Cases** | Auto-attaches the failing trace + stack trace + the `release.commit_sha` of the bad deploy |\n"
        "| 6 | **Logs + APM correlation** | Single click pivot from anomaly to top stack-traces (NullPointerException dominates) |\n"
        "| 7 | **AIOps Log Rate Analysis** | Highlights `IdempotencyKeyExtractor.extract` as the regressing log signature |\n"
        "\n_Time-to-mitigation in the demo flow: deploy -> alert -> owner notified -> rollback PR opened, all under 10 minutes._\n\n"
        "### Representative stack traces - paste into a Case\n"
        "1. **NullPointerException** · checkout-service · commit `c6d2410` (@okafor) - `Cannot invoke \"IdempotencyKey.value()\" because \"key\" is null`\n"
        "2. **DBConnectionTimeout** · checkout-service · commit `a4f9c21` (@marquez) - `HikariPool-1 - Connection is not available, request timed out after 30000ms`\n"
        "3. **JsonParseException** · checkout-service · commit `bd8e137` (@patel) - `Mismatched input: schema v2 requires 'cart_lines'; received legacy 'items'`\n"
        "4. **RateLimitExceeded** · checkout-service · commit `c6d2410` (@okafor) - `Rate limit exceeded for tenant t_3a8f: 200 rpm budget consumed`\n"
        "5. **NullPointerException** · checkout-service · commit `c6d2410` (@okafor) - `null pointer dereference in CartTotalCalculator.totals`"
    )


def _md_customer_intro() -> str:
    return (
        "## [Customer] Service health report - last 7 days\n"
        f"_Audience: SRE leads, Engineering Manager, on-call rotation lead._\n\n"
        f"**Headline:** `checkout-service` is producing **~80% of all errors** across the platform "
        "despite handling only **~12%** of traffic. The error rate stepped up three times over the "
        "last week, each step landing within minutes of a `checkout-service` deployment. The most "
        "recent deploy (**v1.7.3**, T-12h) introduced a `NullPointerException` regression in the "
        "idempotency-key handling path that has become the dominant failure mode.\n\n"
        "### What this means for the team\n"
        "- **Error budget**: the weekly error budget for `checkout-service` (SLO 99.9%) is being burned down rapidly. The burn-down chart below shows when the budget runs out at the current pace.\n"
        "- **MTTR**: today the team detects deploy regressions only when customer-support tickets land. Target is **<15 min** detect-to-page; current actual hovers around **90 min**.\n"
        "- **Deploy regressions identified**: three `checkout-service` deploys in the last 7 days, all correlated with measurable error-rate jumps. The other 9 services shipped 24 stable rollouts in the same window with no incidents.\n"
        "- **Engineering impact**: `checkout-service` and `cart-service` (same team, `checkout-platform`) are absorbing the bulk of on-call pages. Other 8 services are quiet."
    )


def _md_customer_closing() -> str:
    return (
        "## [Customer] What we recommend next\n"
        "**Immediate (today):**\n"
        "- Roll back `checkout-service` to **v1.7.2** while the NullPointerException regression in `IdempotencyKeyExtractor.extract` is fixed and re-tested.\n"
        "- Acknowledge the current SLO burn and pause non-critical `checkout-service` rollouts until the error budget recovers.\n\n"
        "**This week:**\n"
        "- Add a **deploy-correlated error-rate alert** (fast-burn 14.4x in 5 min) so the next regression pages the deploy author within minutes, not hours.\n"
        "- Wire `release.commit_sha` and `release.author` into Cases templates so every incident auto-attaches the suspected deploy.\n"
        "- Add **ML anomaly detection** on `apm_tx_metrics` and `high_error_rate` for `checkout-service` - this dashboard would have surfaced the regression in the first 5-minute bucket after each deploy.\n\n"
        "**Quarterly:**\n"
        "- Adopt **shared SLOs** across `checkout-platform` (checkout-service + cart-service) so the team budget is visible at the squad level, not per-service.\n"
        "- Standardise on **Elastic Service Map** as the single starting point for incident triage. The 80/20 split visible here today should be the first thing on-call sees, not the last.\n\n"
        "### Engineering scoreboard (last 7 days)\n"
        "| Metric | Target | Actual | Status |\n"
        "| --- | --- | --- | --- |\n"
        "| Error rate (checkout-service) | < 1.0% | ~26% post-T-12h | breached |\n"
        "| Error rate (other 9 services) | < 1.0% | < 1.0% | on target |\n"
        "| Detect-to-page (deploy regressions) | < 5 min | ~90 min | breached |\n"
        "| Deploys with rollbacks | 0 | 0 (manual mitigation pending) | watch |\n"
        "| Weekly error budget consumed | < 100% | high (see chart) | watch |\n"
    )


# ============================================================ Dashboard panels ======


def _markdown_panel(panel_id: str, x: int, y: int, w: int, h: int, markdown: str,
                    title: str = "") -> Dict[str, Any]:
    """Markdown panel wrapped as a legacy `visualization` embeddable so Kibana 9.x renders it.

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
                "data": {"aggs": [], "searchSource": {"query": {"language": "kuery", "query": ""}, "filter": []}},
            },
        },
        "title": title,
    }


def _vega_panel(panel_id: str, x: int, y: int, w: int, h: int, title: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    """Vega/Vega-Lite visualization wrapped in a self-contained saved-vis."""
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
                "data": {"aggs": [], "searchSource": {"query": {"language": "kuery", "query": ""}, "filter": []}},
            },
        },
        "title": title,
    }


def _build_chart_panels(now: datetime, prefix: str) -> List[Dict[str, Any]]:
    """Return the shared Vega chart panels. Both dashboards use this exact set;
    only the surrounding markdown changes between FE and Customer views.

    Layout (48-wide grid, starting at y=12 to leave room for switcher + intro):
        row 1 (y=12): errors-by-service (24x14)  +  error-rate-over-time (24x14)
        row 2 (y=26): top-error-types (24x12)    +  deploy-timeline (24x12)
        row 3 (y=38): error-budget-burn (48x12)
    """
    panels: List[Dict[str, Any]] = []
    panels.append(_vega_panel(f"{prefix}-c1", 0, 12, 24, 14,
                              "Errors by service", _spec_errors_by_service()))
    panels.append(_vega_panel(f"{prefix}-c2", 24, 12, 24, 14,
                              "Error rate by service over time",
                              _spec_error_rate_over_time()))
    panels.append(_vega_panel(f"{prefix}-c3", 0, 26, 24, 12,
                              "Top error types - checkout-service",
                              _spec_top_error_types()))
    panels.append(_vega_panel(f"{prefix}-c4", 24, 26, 24, 12,
                              "Deployment regression timeline",
                              _spec_deploy_timeline(now)))
    panels.append(_vega_panel(f"{prefix}-c5", 0, 38, 48, 12,
                              "Error budget burn-down (SLO 99.9%)",
                              _spec_error_budget_burn(now)))
    return panels


def get_dashboard_panels() -> List[Dict[str, Any]]:
    """Backwards-compatible accessor used by the demo-data API. Returns the FE
    view panel set (the historical default for SCENARIO_ID -> DASHBOARD_ID)."""
    return _build_fe_panels(_now())


def _build_fe_panels(now: datetime) -> List[Dict[str, Any]]:
    panels: List[Dict[str, Any]] = []
    panels.append(_markdown_panel("fe-switch", 0, 0, 48, 4, _md_switcher("fe"),
                                  "View switcher"))
    panels.append(_markdown_panel("fe-intro", 0, 4, 48, 8, _md_fe_intro(),
                                  "Noisy microservice - FE prep & talk track"))
    panels.extend(_build_chart_panels(now, prefix="fe"))
    panels.append(_markdown_panel("fe-close", 0, 50, 48, 12, _md_fe_closing(),
                                  "How Elastic catches this earlier + stack traces"))
    return panels


def _build_customer_panels(now: datetime) -> List[Dict[str, Any]]:
    panels: List[Dict[str, Any]] = []
    panels.append(_markdown_panel("cu-switch", 0, 0, 48, 4, _md_switcher("customer"),
                                  "View switcher"))
    panels.append(_markdown_panel("cu-intro", 0, 4, 48, 8, _md_customer_intro(),
                                  "Service health report"))
    panels.extend(_build_chart_panels(now, prefix="cu"))
    panels.append(_markdown_panel("cu-close", 0, 50, 48, 12, _md_customer_closing(),
                                  "Recommendations & engineering scoreboard"))
    return panels


# ============================================================ Indexing =============


def _bulk_index(es, index: str, docs: List[Dict[str, Any]]) -> int:
    """Bulk-index in chunks of 500. Refresh wait_for only on the final batch."""
    if not docs:
        return 0
    chunk = 500
    total = len(docs)
    indexed = 0
    for i in range(0, total, chunk):
        batch = docs[i:i + chunk]
        actions = [{"_index": index, "_source": d} for d in batch]
        is_last = (i + chunk) >= total
        refresh = "wait_for" if is_last else False
        success, errors = es_helpers.bulk(es, actions, refresh=refresh, raise_on_error=False, request_timeout=60)
        indexed += success
    return indexed


def _delete_indices(es) -> Dict[str, bool]:
    out = {}
    for idx in INDICES.values():
        try:
            es.indices.delete(index=idx, ignore_unavailable=True)
            out[idx] = True
        except Exception:
            out[idx] = False
    return out


def _create_indices(es) -> Dict[str, bool]:
    mappings = get_mappings()
    out = {}
    for idx, body in mappings.items():
        es.indices.create(index=idx, settings=body["settings"], mappings=body["mappings"])
        out[idx] = True
    return out


# ============================================================ Kibana saved object ===


def _kbn_url(path: str) -> str:
    return settings.kibana_url.rstrip("/") + path


def _kbn_headers() -> Dict[str, str]:
    return {
        "Authorization": f"ApiKey {settings.kibana_api_key}",
        "Content-Type": "application/json",
        "kbn-xsrf": "fe-copilot",
    }


def _post_dashboard(dashboard_id: str, title: str, description: str,
                    panels: List[Dict[str, Any]]) -> Dict[str, Any]:
    panels_json = json.dumps(panels, ensure_ascii=False)
    options_json = json.dumps({
        "useMargins": True, "hidePanelTitles": False,
        "syncColors": False, "syncCursor": False, "syncTooltips": False,
    })
    search_source_json = json.dumps({"query": {"language": "kuery", "query": ""}, "filter": []})
    body = [{
        "id": dashboard_id,
        "type": "dashboard",
        "attributes": {
            "title": title,
            "description": description,
            "panelsJSON": panels_json,
            "optionsJSON": options_json,
            "timeRestore": True,
            "timeFrom": "now-7d/d",
            "timeTo": "now",
            "version": 1,
            "kibanaSavedObjectMeta": {"searchSourceJSON": search_source_json},
        },
    }]
    url = _kbn_url("/api/saved_objects/_bulk_create?overwrite=true")
    with httpx.Client(timeout=45.0) as client:
        resp = client.post(url, headers=_kbn_headers(), json=body)
    resp.raise_for_status()
    return {
        "dashboard_id": dashboard_id,
        "dashboard_url": settings.kibana_url.rstrip("/") + f"/app/dashboards#/view/{dashboard_id}",
        "status": resp.status_code,
        "panel_count": len(panels),
    }


def _create_fe_dashboard() -> Dict[str, Any]:
    now = _now()
    panels = _build_fe_panels(now)
    title = "[FE] Noisy Microservice - One Bad Apple"
    description = (
        f"Field-Engineer prep view for the {_FICT_COMPANY} noisy-microservice scenario. "
        "Talk track, MEDDPICC framing, and 'how Elastic catches this earlier' playbook. "
        f"Backed by {INDICES['traces']}, {INDICES['logs']}, and {INDICES['deployments']}."
    )
    return _post_dashboard(DASHBOARD_ID, title, description, panels)


def _create_customer_dashboard() -> Dict[str, Any]:
    now = _now()
    panels = _build_customer_panels(now)
    title = "[Customer] Noisy Microservice - Service Health Report"
    description = (
        f"Customer-facing service-health report for the {_FICT_COMPANY} noisy-microservice "
        "scenario. SRE / Engineering Manager view: error budget burn, MTTR vs target, "
        "deploy regressions identified, and recommended next steps."
    )
    return _post_dashboard(CUSTOMER_DASHBOARD_ID, title, description, panels)


# Legacy alias so any external caller that imports `_create_dashboard` keeps working.
def _create_dashboard() -> Dict[str, Any]:
    return _create_fe_dashboard()


# ============================================================ Public seed ==========


def seed() -> Dict[str, Any]:
    """Idempotent: DELETE indices, CREATE indices+mappings, generate, bulk-index,
    build BOTH dashboards (FE + Customer). Vega specs are computed AFTER bulk-index
    so their inline `data.values` reflect the freshly-loaded data. Every Vega
    helper wraps its ES call in try/except, so even if Elasticsearch hiccups the
    seed completes and the dashboards still render."""
    random.seed(20260503)
    es = get_client()
    started = datetime.now(timezone.utc)

    deleted = _delete_indices(es)
    created = _create_indices(es)

    docs = generate_documents(seed=20260503)
    counts: Dict[str, int] = {}
    for index, batch in docs.items():
        counts[index] = _bulk_index(es, index, batch)

    # Confirm via _count.
    refresh_counts = {}
    for idx in INDICES.values():
        try:
            es.indices.refresh(index=idx)
            refresh_counts[idx] = es.count(index=idx).get("count", 0)
        except Exception:
            refresh_counts[idx] = -1

    fe_dashboard: Dict[str, Any] = None
    customer_dashboard: Dict[str, Any] = None
    dashboard_error = None
    if settings.kibana_api_key:
        try:
            fe_dashboard = _create_fe_dashboard()
        except httpx.HTTPStatusError as exc:
            dashboard_error = f"FE Kibana {exc.response.status_code}: {exc.response.text[:300]}"
            log.warning("noisy_microservice.fe_dashboard.failed", error=dashboard_error)
        except Exception as exc:
            dashboard_error = f"FE Kibana request failed: {exc}"
            log.warning("noisy_microservice.fe_dashboard.failed", error=str(exc))
        try:
            customer_dashboard = _create_customer_dashboard()
        except httpx.HTTPStatusError as exc:
            err = f"Customer Kibana {exc.response.status_code}: {exc.response.text[:300]}"
            dashboard_error = (dashboard_error + " | " + err) if dashboard_error else err
            log.warning("noisy_microservice.customer_dashboard.failed", error=err)
        except Exception as exc:
            err = f"Customer Kibana request failed: {exc}"
            dashboard_error = (dashboard_error + " | " + err) if dashboard_error else err
            log.warning("noisy_microservice.customer_dashboard.failed", error=str(exc))

    finished = datetime.now(timezone.utc)
    return {
        "scenario_id": SCENARIO_ID,
        "scenario_title": SCENARIO_TITLE,
        "indices": INDICES,
        "indexed_doc_counts": counts,
        "actual_doc_counts": refresh_counts,
        "deleted": deleted,
        "created": created,
        "dashboard": fe_dashboard,                  # legacy key - FE view
        "fe_dashboard": fe_dashboard,
        "customer_dashboard": customer_dashboard,
        "dashboard_error": dashboard_error,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "duration_seconds": (finished - started).total_seconds(),
    }
