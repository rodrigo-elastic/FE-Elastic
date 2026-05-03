"""
filename: noisy_microservice.py
description: Story-driven demo dataset for Elastic Observability - "One Bad Apple".
A fictional payments platform (Stride Payments) runs 10 microservices behind an API
gateway. The recently-deployed checkout-service produces ~80% of all errors despite
handling only ~12% of traffic. Three deployment events in the last 7 days each cause
discrete error-rate jumps; the latest (T-12h, v1.7.3) introduced a NullPointerException
regression. Other 9 services hold steady at <2% error rate with one or two harmless
transient blips for realism.

The module is self-contained and exposes the public interface required by the
Demo Data Generator (SCENARIO_ID, INDICES, get_mappings, generate_documents,
get_dashboard_panels, seed). It DELETE+CREATEs three indices and a Kibana dashboard
saved object with seven panels (Vega-Lite for charts, markdown for narrative).
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
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


# ============================================================ Domain constants ======

_FICT_COMPANY = "Stride Payments"
_NAMESPACE = "stride-payments"
_REGIONS = ["us-east-1", "us-west-2", "eu-west-1"]
_NODES_PER_REGION = 3
_SLO_TARGET = 0.999

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


def _vega_errors_by_service_spec() -> Dict[str, Any]:
    """Vega-Lite bar chart: errors-by-service from Elasticsearch (terms agg)."""
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": {"text": "Errors by service (last 7d) - checkout-service dominates",
                  "fontSize": 14, "anchor": "start"},
        "data": {
            "url": {
                "%context%": True, "%timefield%": "@timestamp",
                "index": INDICES["traces"],
                "body": {
                    "size": 0,
                    "query": {"bool": {"filter": [{"term": {"event.outcome": "failure"}}]}},
                    "aggs": {"by_svc": {"terms": {"field": "service.name", "size": 20, "order": {"_count": "desc"}}}},
                },
            },
            "format": {"property": "aggregations.by_svc.buckets"},
        },
        "mark": {"type": "bar", "tooltip": True, "cornerRadiusEnd": 3},
        "encoding": {
            "y": {"field": "key", "type": "nominal", "sort": "-x", "title": "Service"},
            "x": {"field": "doc_count", "type": "quantitative", "title": "Error count"},
            "color": {
                "condition": {"test": "datum.key == 'checkout-service'", "value": "#e7664c"},
                "value": "#54b399",
            },
            "tooltip": [
                {"field": "key", "type": "nominal", "title": "service.name"},
                {"field": "doc_count", "type": "quantitative", "title": "errors"},
            ],
        },
    }


def _vega_error_rate_over_time_spec() -> Dict[str, Any]:
    """Vega-Lite line: error rate % per service over time (5-min buckets)."""
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": {"text": "Error rate % by service (5-min buckets) - three deploys land on checkout-service",
                  "fontSize": 14, "anchor": "start"},
        "data": {
            "url": {
                "%context%": True, "%timefield%": "@timestamp",
                "index": INDICES["traces"],
                "body": {
                    "size": 0,
                    "aggs": {
                        "by_time": {
                            "date_histogram": {"field": "@timestamp", "fixed_interval": "5m", "min_doc_count": 0},
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
                },
            },
            "format": {"property": "aggregations.by_time.buckets"},
        },
        "transform": [
            {"flatten": ["by_svc.buckets"], "as": ["svc_bucket"]},
            {"calculate": "datum.svc_bucket.key", "as": "service"},
            {"calculate": "datum.svc_bucket.doc_count > 0 ? datum.svc_bucket.fail.doc_count / datum.svc_bucket.doc_count : 0", "as": "error_rate"},
            {"calculate": "datum.error_rate * 100", "as": "error_rate_pct"},
        ],
        "mark": {"type": "line", "interpolate": "monotone", "point": False, "tooltip": True, "strokeWidth": 2},
        "encoding": {
            "x": {"field": "key_as_string", "type": "temporal", "title": None},
            "y": {"field": "error_rate_pct", "type": "quantitative", "title": "error rate (%)"},
            "color": {
                "field": "service", "type": "nominal",
                "scale": {
                    "domain": [
                        "checkout-service", "payments-gateway", "billing-service", "ledger-service",
                        "fraud-service", "notifications-service", "profile-service", "cart-service",
                        "inventory-service", "recs-service",
                    ],
                    "range": [
                        "#e7664c", "#54b399", "#9ab8d3", "#aaaaaa", "#d6bf57",
                        "#a987d1", "#7eaecf", "#7c8a99", "#c1a98c", "#7d9d7d",
                    ],
                },
            },
            "tooltip": [
                {"field": "key_as_string", "type": "temporal", "title": "time"},
                {"field": "service", "type": "nominal", "title": "service"},
                {"field": "error_rate_pct", "type": "quantitative", "title": "error %", "format": ".2f"},
            ],
        },
    }


def _vega_top_error_types_spec() -> Dict[str, Any]:
    """Vega-Lite horizontal bar: top error.type for checkout-service."""
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": {"text": "Top error.type - checkout-service (last 7d)", "fontSize": 14, "anchor": "start"},
        "data": {
            "url": {
                "%context%": True, "%timefield%": "@timestamp",
                "index": INDICES["traces"],
                "body": {
                    "size": 0,
                    "query": {"bool": {"filter": [
                        {"term": {"service.name": "checkout-service"}},
                        {"term": {"event.outcome": "failure"}},
                    ]}},
                    "aggs": {"by_err": {"terms": {"field": "error.type", "size": 5, "order": {"_count": "desc"}}}},
                },
            },
            "format": {"property": "aggregations.by_err.buckets"},
        },
        "mark": {"type": "bar", "tooltip": True, "cornerRadiusEnd": 3, "color": "#e7664c"},
        "encoding": {
            "y": {"field": "key", "type": "nominal", "sort": "-x", "title": "error.type"},
            "x": {"field": "doc_count", "type": "quantitative", "title": "count"},
            "tooltip": [
                {"field": "key", "type": "nominal", "title": "error.type"},
                {"field": "doc_count", "type": "quantitative", "title": "count"},
            ],
        },
    }


def _vega_deploy_timeline_spec(now: datetime) -> Dict[str, Any]:
    """Vega timeline: deployment vertical rules + checkout-service error-rate area chart."""
    deploy_times = []
    for dep in _CHECKOUT_DEPLOYS:
        ts = now - timedelta(hours=dep["hours_ago"])
        deploy_times.append({"ts": _iso(ts), "label": f"v{dep['version']} ({dep['commit_sha']})"})
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": {"text": "Deploys vs checkout-service error rate (5-min buckets)", "fontSize": 14, "anchor": "start"},
        "vconcat": [],  # placeholder so we use layer below at top level
        "layer": [
            {
                "data": {
                    "url": {
                        "%context%": True, "%timefield%": "@timestamp",
                        "index": INDICES["traces"],
                        "body": {
                            "size": 0,
                            "query": {"bool": {"filter": [{"term": {"service.name": "checkout-service"}}]}},
                            "aggs": {
                                "by_time": {
                                    "date_histogram": {"field": "@timestamp", "fixed_interval": "5m", "min_doc_count": 0},
                                    "aggs": {"fail": {"filter": {"term": {"event.outcome": "failure"}}}},
                                },
                            },
                        },
                    },
                    "format": {"property": "aggregations.by_time.buckets"},
                },
                "transform": [
                    {"calculate": "datum.doc_count > 0 ? datum.fail.doc_count / datum.doc_count : 0", "as": "rate"},
                    {"calculate": "datum.rate * 100", "as": "rate_pct"},
                ],
                "mark": {"type": "area", "color": "#e7664c", "opacity": 0.55, "interpolate": "monotone", "line": {"color": "#bd271e", "strokeWidth": 1.5}, "tooltip": True},
                "encoding": {
                    "x": {"field": "key_as_string", "type": "temporal", "title": None},
                    "y": {"field": "rate_pct", "type": "quantitative", "title": "checkout-service error %"},
                    "tooltip": [
                        {"field": "key_as_string", "type": "temporal", "title": "time"},
                        {"field": "doc_count", "type": "quantitative", "title": "txns"},
                        {"field": "rate_pct", "type": "quantitative", "title": "error %", "format": ".2f"},
                    ],
                },
            },
            {
                "data": {"values": deploy_times},
                "mark": {"type": "rule", "color": "#1d3c4f", "strokeWidth": 2, "strokeDash": [6, 4]},
                "encoding": {
                    "x": {"field": "ts", "type": "temporal"},
                    "tooltip": [{"field": "label", "type": "nominal", "title": "deploy"}, {"field": "ts", "type": "temporal", "title": "time"}],
                },
            },
            {
                "data": {"values": deploy_times},
                "mark": {"type": "text", "align": "left", "dx": 4, "dy": -6, "color": "#1d3c4f", "fontSize": 11, "fontWeight": "bold"},
                "encoding": {
                    "x": {"field": "ts", "type": "temporal"},
                    "y": {"datum": 0, "type": "quantitative"},
                    "text": {"field": "label", "type": "nominal"},
                },
            },
        ],
    }


def _md_header() -> str:
    return (
        "## One Bad Apple - Noisy Microservice\n"
        f"_{_FICT_COMPANY}_ runs **10 microservices** behind an API gateway. Over the last 7 days, "
        "the recently-deployed `checkout-service` (rolling **v1.7.0 → v1.7.3**) has produced **~80% of all "
        "errors** despite handling only **~12%** of traffic. Three deployment events land as discrete "
        "error-rate jumps; the **T-12h** rollout (v1.7.3) introduced a `NullPointerException` regression.\n\n"
        "**How Elastic catches this fast** - Service Map highlights the 80/20 split, "
        "**ML anomaly detection** flags the post-deploy regression in <5 minutes, "
        "**SLO burn-rate alerts** fire on the 0.999 availability target, and **Cases** auto-assigns the "
        "on-call (`@okafor`, the deploy author of `c6d2410`)."
    )


def _md_how_elastic_catches() -> str:
    return (
        "## How Elastic catches this - playbook\n"
        "| Step | Elastic capability | What it surfaces |\n"
        "| --- | --- | --- |\n"
        "| 1 | **Service Map** (Observability) | Auto-rendered topology - `checkout-service` lights red while peers stay green; click-through into APM |\n"
        "| 2 | **APM transaction breakdown** | p50 / p99 latency per `transaction.name` - `POST /checkout/confirm` regressed 4x at T-12h |\n"
        "| 3 | **ML anomaly job** (`high_error_rate` + `apm_tx_metrics`) | Pre-built detectors flag the 5-min bucket within 1-2 buckets of the deploy |\n"
        "| 4 | **SLO burn-rate alert** (target 0.999) | Fast-burn alert at 14.4x in 5 min - pages the checkout on-call |\n"
        "| 5 | **Cases** | Auto-attaches the failing trace + stack trace + the `release.commit_sha` of the bad deploy |\n"
        "| 6 | **Logs + APM correlation** | Single click pivot from anomaly to top stack-traces (NullPointerException dominates) |\n"
        "| 7 | **AIOps Log Rate Analysis** | Highlights `IdempotencyKeyExtractor.extract` as the regressing log signature |\n"
        "\n_Time-to-mitigation in the demo flow: deploy → alert → owner notified → rollback PR opened, all under 10 minutes._"
    )


def _md_stack_traces_table() -> str:
    """Five representative stack traces with commit SHAs ready to paste into Cases."""
    samples = [
        ("NullPointerException", "checkout-service", "c6d2410", "okafor",
         "Cannot invoke \"IdempotencyKey.value()\" because \"key\" is null",
         _STACKS["NullPointerException"][0]),
        ("DBConnectionTimeout", "checkout-service", "a4f9c21", "marquez",
         "HikariPool-1 - Connection is not available, request timed out after 30000ms",
         _STACKS["DBConnectionTimeout"][0]),
        ("JsonParseException", "checkout-service", "bd8e137", "patel",
         "Mismatched input: schema v2 requires 'cart_lines'; received legacy 'items'",
         _STACKS["JsonParseException"][1]),
        ("RateLimitExceeded", "checkout-service", "c6d2410", "okafor",
         "Rate limit exceeded for tenant t_3a8f: 200 rpm budget consumed",
         _STACKS["RateLimitExceeded"][0]),
        ("NullPointerException", "checkout-service", "c6d2410", "okafor",
         "null pointer dereference in CartTotalCalculator.totals - line items list returned null",
         _STACKS["NullPointerException"][2]),
    ]
    parts = [
        "## Representative stack traces - paste into a Case\n",
        "_Bug-bash starter pack. Each row has the deploy commit that introduced the regression._\n",
    ]
    for i, (etype, svc, sha, author, msg, stack) in enumerate(samples, 1):
        block = "\n".join(f"    at {line}" for line in stack)
        parts.append(
            f"**{i}. `{etype}` · service `{svc}` · commit `{sha}` (@{author})**\n\n"
            f"> {msg}\n\n"
            f"```\n{etype}: {msg}\n{block}\n```\n"
        )
    return "\n".join(parts)


def get_dashboard_panels() -> List[Dict[str, Any]]:
    """Seven panels in 48-wide grid."""
    now = _now()
    panels = []
    # 1. Header (full width, h=8)
    panels.append(_markdown_panel("p1", 0, 0, 48, 8, _md_header(),
                                  "Noisy microservice - story & talk track"))
    # 2. Vega errors-by-service bar (24x14)
    panels.append(_vega_panel("p2", 0, 8, 24, 14, "Errors by service", _vega_errors_by_service_spec()))
    # 3. Vega error-rate-over-time line (24x14)
    panels.append(_vega_panel("p3", 24, 8, 24, 14, "Error rate by service", _vega_error_rate_over_time_spec()))
    # 4. Vega top error.type for checkout (24x12)
    panels.append(_vega_panel("p4", 0, 22, 24, 12, "Top error types - checkout-service", _vega_top_error_types_spec()))
    # 5. Vega deploy timeline + checkout error rate (24x12)
    panels.append(_vega_panel("p5", 24, 22, 24, 12, "Deploys vs error rate", _vega_deploy_timeline_spec(now)))
    # 6. How Elastic catches this (full, h=10)
    panels.append(_markdown_panel("p6", 0, 34, 48, 10, _md_how_elastic_catches(),
                                  "How Elastic catches this earlier"))
    # 7. Stack traces table (full, h=12)
    panels.append(_markdown_panel("p7", 0, 44, 48, 12, _md_stack_traces_table(),
                                  "Top stack traces - checkout-service"))
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


def _create_dashboard() -> Dict[str, Any]:
    panels = get_dashboard_panels()
    panels_json = json.dumps(panels, ensure_ascii=False)
    options_json = json.dumps({"useMargins": True, "hidePanelTitles": False, "syncColors": False, "syncCursor": False, "syncTooltips": False})
    search_source_json = json.dumps({"query": {"language": "kuery", "query": ""}, "filter": []})
    title = "Demo · Noisy Microservice - One Bad Apple"
    description = (
        f"Story-driven demo dashboard for {_FICT_COMPANY}. checkout-service produces ~80% of "
        "errors with three deploy-correlated regressions in the last 7 days. Backed by "
        f"{INDICES['traces']}, {INDICES['logs']}, and {INDICES['deployments']}."
    )

    body = [{
        "id": DASHBOARD_ID,
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
        "dashboard_id": DASHBOARD_ID,
        "dashboard_url": settings.kibana_url.rstrip("/") + f"/app/dashboards#/view/{DASHBOARD_ID}",
        "status": resp.status_code,
        "panel_count": len(panels),
    }


# ============================================================ Public seed ==========


def seed() -> Dict[str, Any]:
    """Idempotent: DELETE indices, CREATE indices+mappings, generate, bulk-index, build dashboard."""
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

    dashboard = None
    dashboard_error = None
    if settings.kibana_api_key:
        try:
            dashboard = _create_dashboard()
        except httpx.HTTPStatusError as exc:
            dashboard_error = f"Kibana {exc.response.status_code}: {exc.response.text[:300]}"
        except Exception as exc:
            dashboard_error = f"Kibana request failed: {exc}"

    finished = datetime.now(timezone.utc)
    return {
        "scenario_id": SCENARIO_ID,
        "scenario_title": SCENARIO_TITLE,
        "indices": INDICES,
        "indexed_doc_counts": counts,
        "actual_doc_counts": refresh_counts,
        "deleted": deleted,
        "created": created,
        "dashboard": dashboard,
        "dashboard_error": dashboard_error,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "duration_seconds": (finished - started).total_seconds(),
    }
