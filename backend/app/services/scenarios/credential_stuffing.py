"""
filename: credential_stuffing.py
description: Demo Data Generator scenario - Credential Stuffing Attack.

Builds a story-driven, ECS-aligned dataset that an Elastic SOC analyst would actually
investigate during an attack triage. Two attack waves (low-and-slow recon + aggressive
spike), 8 attacker IPs across 4 datacenter ASNs, ~0.4% breach rate, mixed with realistic
corporate background traffic. Three indices, ~4100 docs total, plus a 7-panel Kibana
dashboard with Vega-Lite visualisations the SOC team uses to identify, scope, and
respond to the attack.

Public interface (consumed by routes_demo_data and the seed CLI):

    SCENARIO_ID, SCENARIO_TITLE, SCENARIO_DESCRIPTION
    INDICES: Dict[str, str]
    DASHBOARD_ID: str
    get_mappings()      -> Dict[index_name, mapping_body]
    generate_documents(seed=20260503) -> Dict[index_name, List[doc]]
    get_dashboard_panels()            -> List[panel_dict]
    seed()                            -> Dict[str, Any]

date: 03-05-2026
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

SCENARIO_ID: str = "credential-stuffing"
SCENARIO_TITLE: str = "Credential Stuffing Attack"
SCENARIO_DESCRIPTION: str = (
    "Authenticated attack telemetry showing a credential-stuffing campaign against the "
    "corporate webapp. A reused-password dump from a 2024 third-party SaaS breach is "
    "being burned through over two waves: a low-and-slow recon phase 2 days ago "
    "followed by an aggressive datacenter spike six hours ago. ECS-aligned auth, "
    "session, and IP-enrichment events for SOC triage and Elastic Security ML jobs."
)

INDICES: Dict[str, str] = {
    "auth": "demo-credstuff-auth",
    "sessions": "demo-credstuff-sessions",
    "iplookup": "demo-credstuff-iplookup",
}

DASHBOARD_ID: str = "demo-credential-stuffing-dashboard"
CUSTOMER_DASHBOARD_ID: str = "demo-credential-stuffing-customer-dashboard"
INDEX_PATTERN: str = "demo-credstuff-*"


# ============================================================ Threat model =========

# 8 attacker source IPs, 4 ASNs, deliberately chosen so the dashboards reveal the
# datacenter footprint when filtered by failure rate. Each IP carries a believable
# geo / TLS / user-agent profile.

ATTACKER_IPS: List[Dict[str, Any]] = [
    # DigitalOcean LLC (AS14061) - NYC + AMS pops
    {"ip": "165.227.45.118", "asn": 14061, "as_org": "DigitalOcean LLC",
     "country_iso": "US", "country": "United States", "city": "New York",
     "kind": "datacenter", "ua_pool": "headless_chrome"},
    {"ip": "143.198.72.204", "asn": 14061, "as_org": "DigitalOcean LLC",
     "country_iso": "NL", "country": "Netherlands", "city": "Amsterdam",
     "kind": "datacenter", "ua_pool": "python_requests"},
    # Hetzner Online GmbH (AS24940) - Falkenstein + Helsinki
    {"ip": "78.46.151.92", "asn": 24940, "as_org": "Hetzner Online GmbH",
     "country_iso": "DE", "country": "Germany", "city": "Falkenstein",
     "kind": "datacenter", "ua_pool": "headless_chrome"},
    {"ip": "95.216.213.44", "asn": 24940, "as_org": "Hetzner Online GmbH",
     "country_iso": "FI", "country": "Finland", "city": "Helsinki",
     "kind": "datacenter", "ua_pool": "go_http"},
    # OVH SAS (AS16276) - Roubaix + Singapore POP
    {"ip": "51.158.94.213", "asn": 16276, "as_org": "OVH SAS",
     "country_iso": "FR", "country": "France", "city": "Roubaix",
     "kind": "datacenter", "ua_pool": "python_requests"},
    {"ip": "139.99.122.18", "asn": 16276, "as_org": "OVH SAS",
     "country_iso": "SG", "country": "Singapore", "city": "Singapore",
     "kind": "datacenter", "ua_pool": "curl"},
    # Anonymized / unknown VPN provider (residential-looking masks)
    {"ip": "185.220.101.42", "asn": 4224, "as_org": "ANONYMIZED VPN PROVIDER",
     "country_iso": "RU", "country": "Russia", "city": "Saint Petersburg",
     "kind": "vpn", "ua_pool": "spoofed_safari"},
    {"ip": "194.26.135.88", "asn": 4224, "as_org": "ANONYMIZED VPN PROVIDER",
     "country_iso": "RO", "country": "Romania", "city": "Bucharest",
     "kind": "vpn", "ua_pool": "spoofed_safari"},
]

# Subset used for the aggressive wave (6 of 8). The other 2 only appear in recon
# phase, which is itself a tell: an analyst pivoting on "IPs in BOTH waves" would see
# the persistent operators.
WAVE2_IP_SUBSET = [ATTACKER_IPS[i] for i in (0, 2, 3, 4, 5, 6)]

USER_AGENT_POOLS: Dict[str, List[str]] = {
    "headless_chrome": [
        # Version drift across 4 minor releases - real attacker infra often runs slightly
        # outdated or non-uniform Chrome builds because they're Dockerized.
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/119.0.6045.105 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/120.0.6099.71 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/121.0.6167.85 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/122.0.6261.39 Safari/537.36",
    ],
    "python_requests": [
        "python-requests/2.31.0",
        "python-requests/2.32.3",
    ],
    "curl": [
        "curl/7.85.0",
        "curl/8.4.0",
    ],
    "go_http": [
        "Go-http-client/1.1",
        "Go-http-client/2.0",
    ],
    "spoofed_safari": [
        # Spoofed but obvious - real Safari ships consistent versions; mismatched OS
        # build numbers are a classic tell for SOC analysts.
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
    ],
}


def _parse_ua(ua: str) -> Tuple[str, str]:
    """Best-effort name + version extraction from a UA string for ECS user_agent.name/version."""
    if "HeadlessChrome" in ua:
        v = ua.split("HeadlessChrome/")[1].split(" ")[0]
        return ("HeadlessChrome", v)
    if ua.startswith("python-requests/"):
        return ("python-requests", ua.split("/", 1)[1])
    if ua.startswith("curl/"):
        return ("curl", ua.split("/", 1)[1])
    if ua.startswith("Go-http-client/"):
        return ("Go-http-client", ua.split("/", 1)[1])
    if "Safari/" in ua and "Version/" in ua:
        v = ua.split("Version/")[1].split(" ")[0]
        return ("Safari", v)
    if "Chrome/" in ua:
        v = ua.split("Chrome/")[1].split(" ")[0]
        return ("Chrome", v)
    if "Firefox/" in ua:
        v = ua.split("Firefox/")[1].split(" ")[0]
        return ("Firefox", v)
    return ("unknown", "0.0")


# ============================================================ Population ===========

# Realistic corporate user pool. Names span English / Japanese / Spanish / etc to
# reflect a globally distributed knowledge-worker org.

CORP_DOMAIN = "bigcorp.com"

CORP_USERS: List[Tuple[str, str]] = [
    # (display name, email-localpart) - 60 representative employees
    ("Jane Dougherty", "jane.dougherty"),
    ("Kenji Shimizu", "k.shimizu"),
    ("Marco Bellini", "m.bellini"),
    ("Aisha Okonkwo", "a.okonkwo"),
    ("Lucas Almeida", "l.almeida"),
    ("Priya Venkatesh", "p.venkatesh"),
    ("Owen Reilly", "o.reilly"),
    ("Sofia Marchetti", "s.marchetti"),
    ("David Park", "d.park"),
    ("Hannah Mueller", "h.mueller"),
    ("Tomas Novak", "t.novak"),
    ("Rachel Goldstein", "r.goldstein"),
    ("Carlos Mendoza", "c.mendoza"),
    ("Yuki Tanaka", "y.tanaka"),
    ("Nadia El-Sayed", "n.elsayed"),
    ("Ben Whitfield", "b.whitfield"),
    ("Olivia Lindberg", "o.lindberg"),
    ("Sanjay Patel", "s.patel"),
    ("Greta Holm", "g.holm"),
    ("Ethan Rosenbaum", "e.rosenbaum"),
    ("Mei-Lin Zhao", "m.zhao"),
    ("Jonas Berger", "j.berger"),
    ("Liam Donnelly", "l.donnelly"),
    ("Isabella Rizzo", "i.rizzo"),
    ("Felix Brandt", "f.brandt"),
    ("Anika Sharma", "a.sharma"),
    ("Ryan Nakamura", "r.nakamura"),
    ("Eva Klein", "e.klein"),
    ("Daniel Cohen", "d.cohen"),
    ("Chloe Beaumont", "c.beaumont"),
    ("Hiroshi Sato", "h.sato"),
    ("Lena Vogel", "l.vogel"),
    ("Mikhail Ivanov", "m.ivanov"),
    ("Sara Lindqvist", "s.lindqvist"),
    ("Pablo Hernandez", "p.hernandez"),
    ("Naomi Bennett", "n.bennett"),
    ("Tariq Hassan", "t.hassan"),
    ("Camille Laurent", "c.laurent"),
    ("Alex Petrov", "a.petrov"),
    ("Wendy Cho", "w.cho"),
    ("Jamal Roberts", "j.roberts"),
    ("Karina Voss", "k.voss"),
    ("Diego Ortiz", "d.ortiz"),
    ("Eleni Papadakis", "e.papadakis"),
    ("Robert Greene", "r.greene"),
    ("Yara Khoury", "y.khoury"),
    ("Henry Atkinson", "h.atkinson"),
    ("Vera Solovieva", "v.solovieva"),
    ("Kai Andersen", "k.andersen"),
    ("Beatrice Lange", "b.lange"),
    ("Samuel Park", "sam.park"),
    ("Ingrid Holst", "i.holst"),
    ("Theo Fontaine", "t.fontaine"),
    ("Maya Krishnan", "m.krishnan"),
    ("Adrian Calder", "a.calder"),
    ("Lara Petrescu", "l.petrescu"),
    ("Simon Vasquez", "s.vasquez"),
    ("Esther Mwangi", "e.mwangi"),
    ("Nikolai Ivashov", "n.ivashov"),
    ("Tamara Webb", "t.webb"),
]


def _user_email(localpart: str) -> str:
    return f"{localpart}@{CORP_DOMAIN}"


def _user_id(localpart: str) -> str:
    """Stable user.id: u-<8-char hash of localpart>."""
    return "u-" + uuid.uuid5(uuid.NAMESPACE_OID, localpart).hex[:8]


# Legitimate user telemetry: corporate egress IPs (3 offices) + WFH residential ranges.
# The mix matters - SOC analysts looking at totals see this normal long tail and
# wouldn't immediately notice the attack.

CORP_OFFICE_IPS: List[Dict[str, Any]] = [
    {"ip": "203.0.113.41", "asn": 65001, "as_org": "BigCorp HQ Egress",
     "country_iso": "US", "country": "United States", "city": "San Francisco"},
    {"ip": "198.51.100.22", "asn": 65001, "as_org": "BigCorp HQ Egress",
     "country_iso": "US", "country": "United States", "city": "Boston"},
    {"ip": "192.0.2.158", "asn": 65002, "as_org": "BigCorp EMEA Egress",
     "country_iso": "GB", "country": "United Kingdom", "city": "London"},
]

# Pool of residential-looking ISPs for WFH employees.
RESIDENTIAL_ISPS: List[Tuple[int, str, str, str]] = [
    (7922, "Comcast Cable Communications", "US", "Seattle"),
    (7018, "AT&T Internet Services", "US", "Atlanta"),
    (701, "Verizon Business", "US", "Boston"),
    (3320, "Deutsche Telekom AG", "DE", "Berlin"),
    (5089, "Virgin Media Limited", "GB", "Manchester"),
    (12876, "Free SAS", "FR", "Paris"),
    (4713, "NTT Communications", "JP", "Tokyo"),
    (4837, "China Unicom", "CN", "Shanghai"),
    (8708, "RCS & RDS", "RO", "Bucharest"),
    (3215, "Orange S.A.", "FR", "Lyon"),
]

REAL_BROWSER_UAS: List[str] = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]


# ============================================================ Time helpers =========

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ts(now: datetime, seconds_ago: float) -> str:
    return (now - timedelta(seconds=seconds_ago)).isoformat()


# ============================================================ Mappings =============

def get_mappings() -> Dict[str, Dict[str, Any]]:
    """ECS-friendly mappings. Strict-typed time + IP fields; everything else dynamic
    so we can attach any custom field without errors."""
    base_dynamic_props = {
        "@timestamp": {"type": "date"},
        "event": {
            "properties": {
                "action": {"type": "keyword"},
                "outcome": {"type": "keyword"},
                "category": {"type": "keyword"},
                "dataset": {"type": "keyword"},
                "kind": {"type": "keyword"},
                "type": {"type": "keyword"},
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
                        "location": {"type": "geo_point"},
                    }
                },
                "as": {
                    "properties": {
                        "number": {"type": "long"},
                        "organization": {
                            "properties": {"name": {"type": "keyword"}}
                        },
                    }
                },
            }
        },
        "user": {
            "properties": {
                "email": {"type": "keyword"},
                "id": {"type": "keyword"},
                "name": {"type": "keyword"},
            }
        },
        "user_agent": {
            "properties": {
                "original": {
                    "type": "keyword",
                    "fields": {"text": {"type": "text"}},
                },
                "name": {"type": "keyword"},
                "version": {"type": "keyword"},
            }
        },
        "related": {
            "properties": {
                "ip": {"type": "ip"},
                "user": {"type": "keyword"},
            }
        },
        "tls": {
            "properties": {
                "version": {"type": "keyword"},
                "cipher": {"type": "keyword"},
            }
        },
        "http": {
            "properties": {
                "request": {"properties": {"method": {"type": "keyword"}}},
                "response": {"properties": {"status_code": {"type": "long"}}},
            }
        },
        "auth": {
            "properties": {
                "attempt_number": {"type": "long"},
                "failure_reason": {"type": "keyword"},
                "method": {"type": "keyword"},
            }
        },
        "threat": {
            "properties": {
                "tactic": {
                    "properties": {
                        "id": {"type": "keyword"},
                        "name": {"type": "keyword"},
                    }
                },
                "technique": {
                    "properties": {
                        "id": {"type": "keyword"},
                        "name": {"type": "keyword"},
                    }
                },
            }
        },
        "url": {"properties": {"path": {"type": "keyword"}, "domain": {"type": "keyword"}}},
        "labels": {"type": "object", "dynamic": True},
        "session": {
            "properties": {
                "id": {"type": "keyword"},
                "ttl_seconds": {"type": "long"},
            }
        },
    }

    return {
        INDICES["auth"]: {
            "mappings": {
                "dynamic": "true",
                "properties": base_dynamic_props,
            }
        },
        INDICES["sessions"]: {
            "mappings": {
                "dynamic": "true",
                "properties": base_dynamic_props,
            }
        },
        INDICES["iplookup"]: {
            "mappings": {
                "dynamic": "true",
                "properties": {
                    "@timestamp": {"type": "date"},
                    "ip": {"type": "ip"},
                    "asn": {"type": "long"},
                    "as_org": {"type": "keyword"},
                    "country_iso_code": {"type": "keyword"},
                    "country_name": {"type": "keyword"},
                    "city_name": {"type": "keyword"},
                    "kind": {"type": "keyword"},
                    "risk_score": {"type": "long"},
                    "first_seen_ms_ago": {"type": "long"},
                    "last_seen_ms_ago": {"type": "long"},
                    "tags": {"type": "keyword"},
                    "location": {"type": "geo_point"},
                },
            }
        },
    }


# ============================================================ Generators ===========

def _build_auth_doc(
    *,
    now: datetime,
    seconds_ago: float,
    ip_profile: Dict[str, Any],
    ua: str,
    user_email: str,
    user_id_: str,
    user_display: str,
    outcome: str,
    action: str,
    failure_reason: Optional[str],
    attempt_number: int,
    is_threat: bool,
    rng: random.Random,
) -> Dict[str, Any]:
    ua_name, ua_version = _parse_ua(ua)
    status = 200 if outcome == "success" else (
        401 if failure_reason in (None, "invalid_password", "invalid_email") else
        429 if failure_reason == "rate_limited" else
        423 if failure_reason == "account_locked" else
        401
    )
    if action == "user-mfa-challenge":
        status = 401 if outcome == "failure" else 200
    if action == "user-password-reset":
        status = 200 if outcome == "success" else 400

    doc: Dict[str, Any] = {
        "@timestamp": _ts(now, seconds_ago),
        "ecs": {"version": "8.11.0"},
        "event": {
            "kind": "alert" if is_threat and outcome == "failure" else "event",
            "category": ["authentication"],
            "type": ["start"] if action != "user-session-created" else ["start", "creation"],
            "action": action,
            "outcome": outcome,
            "dataset": "webapp.auth",
            "module": "webapp",
        },
        "source": {
            "ip": ip_profile["ip"],
            "geo": {
                "country_iso_code": ip_profile["country_iso"],
                "country_name": ip_profile["country"],
                "city_name": ip_profile.get("city"),
            },
            "as": {
                "number": ip_profile["asn"],
                "organization": {"name": ip_profile["as_org"]},
            },
        },
        "user": {
            "email": user_email,
            "id": user_id_,
            "name": user_display,
        },
        "user_agent": {
            "original": ua,
            "name": ua_name,
            "version": ua_version,
        },
        "http": {
            "request": {"method": "POST"},
            "response": {"status_code": status},
        },
        "url": {"path": "/auth/login", "domain": "app.bigcorp.com"},
        "tls": {
            "version": rng.choice(["1.3", "1.3", "1.3", "1.2"]),
            "cipher": rng.choice([
                "TLS_AES_128_GCM_SHA256",
                "TLS_AES_256_GCM_SHA384",
                "TLS_CHACHA20_POLY1305_SHA256",
            ]),
        },
        "auth": {
            "attempt_number": attempt_number,
            "method": "password",
        },
        "related": {
            "ip": [ip_profile["ip"]],
            "user": [user_display],
        },
    }
    if failure_reason:
        doc["auth"]["failure_reason"] = failure_reason
    if is_threat:
        doc["threat"] = {
            "tactic": {"id": "TA0006", "name": "Credential Access"},
            "technique": {"id": "T1110.004", "name": "Brute Force: Credential Stuffing"},
        }
        doc["labels"] = {"attack_wave": "wave1" if seconds_ago > 24 * 3600 else "wave2"}
    return doc


def _generate_legitimate_auth(
    rng: random.Random, now: datetime
) -> List[Dict[str, Any]]:
    """~600 legitimate logins over the last 7 days. ~95% success, ~5% normal mistakes."""
    docs: List[Dict[str, Any]] = []
    user_attempt_counts: Dict[str, int] = {}

    for _ in range(600):
        # Skew weight: more recent = more activity. 60% in last 24h, 30% prior 3 days,
        # 10% earlier in the 7-day window.
        roll = rng.random()
        if roll < 0.60:
            seconds_ago = rng.uniform(0, 24 * 3600)
        elif roll < 0.90:
            seconds_ago = rng.uniform(24 * 3600, 4 * 24 * 3600)
        else:
            seconds_ago = rng.uniform(4 * 24 * 3600, 7 * 24 * 3600)

        # 70% from corporate office, 30% from residential WFH IPs.
        if rng.random() < 0.70:
            ip_profile = dict(rng.choice(CORP_OFFICE_IPS))
        else:
            asn, org, ctry, city = rng.choice(RESIDENTIAL_ISPS)
            # Synthesize a residential-looking IP within the ISP.
            octets = [rng.randint(8, 254) for _ in range(4)]
            ip_profile = {
                "ip": ".".join(str(o) for o in octets),
                "asn": asn,
                "as_org": org,
                "country_iso": ctry,
                "country": _country_name(ctry),
                "city": city,
            }

        display, localpart = rng.choice(CORP_USERS)
        user_email = _user_email(localpart)
        user_id_ = _user_id(localpart)
        ua = rng.choice(REAL_BROWSER_UAS)

        attempt = user_attempt_counts.get(user_email, 0) + 1
        user_attempt_counts[user_email] = attempt

        # 95% success. Of failures: 70% invalid_password (typo), 25% mfa_required,
        # 5% account_locked.
        if rng.random() < 0.95:
            outcome = "success"
            failure = None
        else:
            outcome = "failure"
            r2 = rng.random()
            if r2 < 0.70:
                failure = "invalid_password"
            elif r2 < 0.95:
                failure = "mfa_required"
            else:
                failure = "account_locked"

        action = "user-login" if outcome == "success" else "user-login-failed"
        docs.append(_build_auth_doc(
            now=now, seconds_ago=seconds_ago,
            ip_profile=ip_profile, ua=ua,
            user_email=user_email, user_id_=user_id_, user_display=display,
            outcome=outcome, action=action, failure_reason=failure,
            attempt_number=attempt, is_threat=False, rng=rng,
        ))
    return docs


def _country_name(iso: str) -> str:
    return {
        "US": "United States", "GB": "United Kingdom", "DE": "Germany",
        "FR": "France", "JP": "Japan", "CN": "China", "RO": "Romania",
        "RU": "Russia", "NL": "Netherlands", "BR": "Brazil", "VN": "Vietnam",
        "FI": "Finland", "SG": "Singapore",
    }.get(iso, iso)


def _pick_failure_reason(rng: random.Random) -> str:
    """Attacker failure-reason distribution: 65% invalid_password, 22% invalid_email,
    10% rate_limited, 3% account_locked."""
    r = rng.random()
    if r < 0.65:
        return "invalid_password"
    if r < 0.87:
        return "invalid_email"
    if r < 0.97:
        return "rate_limited"
    return "account_locked"


def _generate_attack_wave(
    rng: random.Random,
    now: datetime,
    *,
    start_seconds_ago: float,
    duration_seconds: float,
    ips: List[Dict[str, Any]],
    total_attempts: int,
    breach_targets: List[Tuple[str, str]],
    success_rate: float,
    label: str,
    thunder_herd: bool = False,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Returns (auth_docs, breached_user_records).
    breached_user_records = [{ip_profile, user_display, user_email, user_id, when}]"""
    auth_docs: List[Dict[str, Any]] = []
    breaches: List[Dict[str, Any]] = []
    user_attempts: Dict[str, int] = {}

    # Build a list of timestamps within the wave window. Thunder herd front-loads.
    times: List[float] = []
    for _ in range(total_attempts):
        if thunder_herd:
            # Beta(1.7, 4) skews toward the beginning (the spike).
            frac = min(1.0, max(0.0, rng.betavariate(1.7, 4.0)))
        else:
            # Mostly uniform with light Gaussian jitter to look bot-like-but-jittered.
            frac = rng.uniform(0, 1)
        offset = frac * duration_seconds
        # Small per-event jitter (+/- 0.4 s) so timestamps don't perfectly bucket.
        offset += rng.gauss(0, 0.4)
        offset = max(0.0, min(duration_seconds, offset))
        times.append(start_seconds_ago - offset)

    times.sort(reverse=True)  # earliest first in chronological order

    # Track which (user_email, ip) pairs we've already breached so a single victim
    # only flips to success once.
    already_breached: Dict[str, Dict[str, Any]] = {}

    breach_target_idx = 0

    for sec_ago in times:
        ip_profile = rng.choice(ips)
        ua = rng.choice(USER_AGENT_POOLS[ip_profile["ua_pool"]])

        # Decide if this attempt is a planned successful breach.
        is_planned_breach = (
            breach_target_idx < len(breach_targets)
            and rng.random() < success_rate * 8  # rare; ensures we hit ~all targets across wave
            and (breach_targets[breach_target_idx][1] not in already_breached)
        )

        if is_planned_breach:
            display, localpart = breach_targets[breach_target_idx]
            user_email = _user_email(localpart)
            user_id_ = _user_id(localpart)
            outcome = "success"
            failure = None
            action = "user-login"
            attempt = user_attempts.get(user_email, 0) + 1
            user_attempts[user_email] = attempt
            already_breached[user_email] = {
                "ip_profile": ip_profile,
                "ua": ua,
                "user_display": display,
                "user_email": user_email,
                "user_id": user_id_,
                "seconds_ago": sec_ago,
                "attempt_number": attempt,
            }
            breaches.append(already_breached[user_email])
            breach_target_idx += 1
        else:
            # Attacker is iterating through the leaked dump - mostly hits unknown
            # users (invalid_email) or known users with wrong password (invalid_password).
            if rng.random() < 0.55:
                # Attempt against a real corp user (the dump partially overlaps the
                # corp population - that's what makes credential stuffing dangerous).
                display, localpart = rng.choice(CORP_USERS)
                user_email = _user_email(localpart)
                user_id_ = _user_id(localpart)
                failure = _pick_failure_reason(rng)
                if failure == "invalid_email":
                    # Promote to a "noise" user since we said it's invalid_email.
                    fake_local = f"{localpart}.{rng.randint(1, 99)}"
                    user_email = _user_email(fake_local)
                    user_id_ = _user_id(fake_local)
                    display = f"{display} (unknown)"
            else:
                # Pure dump-noise user - email exists in the leaked dump but not in
                # the corp directory.
                fake = rng.choice([
                    "j.smith", "info", "admin", "support", "k.brown", "test",
                    "m.davis", "p.wilson", "noreply", "billing", "hr",
                ])
                tag = rng.randint(1, 999)
                user_email = f"{fake}{tag}@{CORP_DOMAIN}"
                user_id_ = _user_id(f"{fake}{tag}")
                display = f"{fake}{tag}"
                failure = "invalid_email"
            outcome = "failure"
            action = "user-login-failed"
            attempt = user_attempts.get(user_email, 0) + 1
            user_attempts[user_email] = attempt

        sec_ago = max(60.0, sec_ago)  # never future-dated
        auth_docs.append(_build_auth_doc(
            now=now, seconds_ago=sec_ago,
            ip_profile=ip_profile, ua=ua,
            user_email=user_email, user_id_=user_id_, user_display=display,
            outcome=outcome, action=action, failure_reason=failure,
            attempt_number=attempt, is_threat=True, rng=rng,
        ))
        # Tag the wave label on every attack doc.
        auth_docs[-1].setdefault("labels", {})["attack_wave"] = label

    return auth_docs, breaches


def _generate_session_and_followups(
    rng: random.Random, now: datetime, breaches: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """For each breach, create a session-created doc + 1-3 follow-on suspicious actions.
    Returns (session_docs, extra_auth_docs)."""
    session_docs: List[Dict[str, Any]] = []
    follow_auth_docs: List[Dict[str, Any]] = []

    for b in breaches:
        ipp = b["ip_profile"]
        # Session created within seconds of the successful auth.
        sess_seconds_ago = max(30.0, b["seconds_ago"] - rng.uniform(2, 8))
        session_id = "sess-" + uuid.uuid4().hex[:18]
        ttl = rng.choice([3600, 7200, 28800])

        ua_name, ua_version = _parse_ua(b["ua"])
        session_docs.append({
            "@timestamp": _ts(now, sess_seconds_ago),
            "ecs": {"version": "8.11.0"},
            "event": {
                "kind": "event",
                "category": ["authentication", "session"],
                "type": ["creation"],
                "action": "user-session-created",
                "outcome": "success",
                "dataset": "webapp.auth",
                "module": "webapp",
            },
            "source": {
                "ip": ipp["ip"],
                "geo": {
                    "country_iso_code": ipp["country_iso"],
                    "country_name": ipp["country"],
                    "city_name": ipp.get("city"),
                },
                "as": {"number": ipp["asn"], "organization": {"name": ipp["as_org"]}},
            },
            "user": {"email": b["user_email"], "id": b["user_id"], "name": b["user_display"]},
            "user_agent": {"original": b["ua"], "name": ua_name, "version": ua_version},
            "session": {"id": session_id, "ttl_seconds": ttl},
            "http": {"request": {"method": "POST"}, "response": {"status_code": 201}},
            "url": {"path": "/auth/session", "domain": "app.bigcorp.com"},
            "tls": {"version": "1.3", "cipher": "TLS_AES_256_GCM_SHA384"},
            "related": {"ip": [ipp["ip"]], "user": [b["user_display"]]},
            "labels": {"breach": "confirmed", "attack_wave": "wave2" if b["seconds_ago"] < 24 * 3600 else "wave1"},
            "threat": {
                "tactic": {"id": "TA0001", "name": "Initial Access"},
                "technique": {"id": "T1078", "name": "Valid Accounts"},
            },
        })

        # Generate 1-3 follow-on attacker actions (password reset, MFA challenge spam,
        # second login from same IP).
        n_followups = rng.randint(1, 3)
        for k in range(n_followups):
            sec = max(20.0, sess_seconds_ago - rng.uniform(60, 600))
            choice = rng.choice([
                ("user-password-reset", "success", None),
                ("user-mfa-challenge", "failure", "mfa_required"),
                ("user-mfa-challenge", "failure", "mfa_required"),
                ("user-login", "success", None),
            ])
            action, outcome, failure = choice
            attempt = 1
            doc = _build_auth_doc(
                now=now, seconds_ago=sec,
                ip_profile=ipp, ua=b["ua"],
                user_email=b["user_email"], user_id_=b["user_id"],
                user_display=b["user_display"],
                outcome=outcome, action=action, failure_reason=failure,
                attempt_number=attempt, is_threat=True, rng=rng,
            )
            doc["labels"]["follow_up"] = True
            doc["threat"] = {
                "tactic": {"id": "TA0001", "name": "Initial Access"},
                "technique": {"id": "T1556", "name": "Modify Authentication Process"},
            }
            follow_auth_docs.append(doc)

    return session_docs, follow_auth_docs


def _generate_iplookup(
    rng: random.Random, now: datetime, observed_ips: Dict[str, Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Precomputed IP enrichment docs - what an analyst pivot-table would join against.
    Includes attacker IPs (high risk_score) + a sample of corp + residential IPs."""
    docs: List[Dict[str, Any]] = []
    # Approx geo coordinates for a handful of well-known cities; the rest fall back
    # to country-level centroids so geo_point still indexes cleanly.
    coords = {
        ("US", "New York"): {"lat": 40.7128, "lon": -74.0060},
        ("NL", "Amsterdam"): {"lat": 52.3676, "lon": 4.9041},
        ("DE", "Falkenstein"): {"lat": 50.4779, "lon": 12.3713},
        ("FI", "Helsinki"): {"lat": 60.1699, "lon": 24.9384},
        ("FR", "Roubaix"): {"lat": 50.6927, "lon": 3.1746},
        ("SG", "Singapore"): {"lat": 1.3521, "lon": 103.8198},
        ("RU", "Saint Petersburg"): {"lat": 59.9311, "lon": 30.3609},
        ("RO", "Bucharest"): {"lat": 44.4268, "lon": 26.1025},
        ("US", "San Francisco"): {"lat": 37.7749, "lon": -122.4194},
        ("US", "Boston"): {"lat": 42.3601, "lon": -71.0589},
        ("GB", "London"): {"lat": 51.5074, "lon": -0.1278},
        ("US", "Seattle"): {"lat": 47.6062, "lon": -122.3321},
        ("US", "Atlanta"): {"lat": 33.7490, "lon": -84.3880},
        ("DE", "Berlin"): {"lat": 52.5200, "lon": 13.4050},
        ("GB", "Manchester"): {"lat": 53.4808, "lon": -2.2426},
        ("FR", "Paris"): {"lat": 48.8566, "lon": 2.3522},
        ("JP", "Tokyo"): {"lat": 35.6762, "lon": 139.6503},
        ("CN", "Shanghai"): {"lat": 31.2304, "lon": 121.4737},
        ("FR", "Lyon"): {"lat": 45.7640, "lon": 4.8357},
    }

    for ip, info in observed_ips.items():
        kind = info.get("kind", "residential")
        if kind == "datacenter":
            risk = rng.randint(85, 99)
            tags = ["datacenter", "credential-stuffing-suspect", info["as_org"].split()[0].lower()]
        elif kind == "vpn":
            risk = rng.randint(75, 92)
            tags = ["anonymizer", "vpn", "credential-stuffing-suspect"]
        elif kind == "corporate":
            risk = rng.randint(0, 5)
            tags = ["corp-egress", "trusted"]
        else:
            risk = rng.randint(5, 30)
            tags = ["residential", "isp"]

        loc = coords.get((info["country_iso"], info.get("city", "")))
        doc: Dict[str, Any] = {
            "@timestamp": _ts(now, rng.uniform(60, 600)),
            "ip": ip,
            "asn": info["asn"],
            "as_org": info["as_org"],
            "country_iso_code": info["country_iso"],
            "country_name": info["country"],
            "city_name": info.get("city"),
            "kind": kind,
            "risk_score": risk,
            "first_seen_ms_ago": int(rng.uniform(2, 6) * 24 * 3600 * 1000),
            "last_seen_ms_ago": int(rng.uniform(0.1, 12) * 3600 * 1000),
            "tags": tags,
        }
        if loc:
            doc["location"] = loc
        docs.append(doc)
    return docs


# ============================================================ Master generator =====

def generate_documents(seed: int = 20260503) -> Dict[str, List[Dict[str, Any]]]:
    """Generate all documents for the scenario, deterministic with `seed`."""
    rng = random.Random(seed)
    now = _now()

    # ============== Wave 1: low-and-slow recon, 2 days ago, 30-min window ============
    # ~50 attempts/min aggregate × 30 min ≈ 1500 attempts spread across all 8 IPs.
    wave1_start = 2 * 24 * 3600 + 30 * 60   # 2 days, 30 min ago
    wave1_duration = 30 * 60                # 30 min
    wave1_attempts = 1500

    # Wave 1 breaches: 2 (recon-phase tells - the attacker confirmed the dump partially
    # works against corp accounts).
    wave1_breach_targets = [
        ("Jane Dougherty", "jane.dougherty"),
        ("Kenji Shimizu", "k.shimizu"),
    ]
    wave1_auth, wave1_breaches = _generate_attack_wave(
        rng, now,
        start_seconds_ago=wave1_start,
        duration_seconds=wave1_duration,
        ips=ATTACKER_IPS,
        total_attempts=wave1_attempts,
        breach_targets=wave1_breach_targets,
        success_rate=0.004,
        label="wave1-recon",
        thunder_herd=False,
    )

    # ============== Wave 2: aggressive datacenter spike, 6h ago, 25-min window =======
    # ~60 attempts/min/IP × 6 IPs × 25 min ≈ 9000 raw, but we compress to ~1500 attempts
    # in storage to keep the index tight. The visualization still shows the spike vs
    # baseline because the rate is concentrated.
    wave2_start = 6 * 3600 + 25 * 60        # 6h 25min ago
    wave2_duration = 25 * 60                # 25 min
    wave2_attempts = 1500
    wave2_breach_targets = [
        ("Sofia Marchetti", "s.marchetti"),
        ("David Park", "d.park"),
        ("Marco Bellini", "m.bellini"),
        ("Aisha Okonkwo", "a.okonkwo"),
    ]
    wave2_auth, wave2_breaches = _generate_attack_wave(
        rng, now,
        start_seconds_ago=wave2_start,
        duration_seconds=wave2_duration,
        ips=WAVE2_IP_SUBSET,
        total_attempts=wave2_attempts,
        breach_targets=wave2_breach_targets,
        success_rate=0.005,
        label="wave2-spike",
        thunder_herd=True,
    )

    # ============== Sessions + post-breach follow-ups ===============================
    all_breaches = wave1_breaches + wave2_breaches
    session_docs, followup_auth = _generate_session_and_followups(rng, now, all_breaches)

    # ============== Legitimate background traffic ==================================
    legit_docs = _generate_legitimate_auth(rng, now)

    # ============== Combine auth docs ==============================================
    auth_docs = legit_docs + wave1_auth + wave2_auth + followup_auth
    rng.shuffle(auth_docs)

    # ============== IP enrichment table ============================================
    observed: Dict[str, Dict[str, Any]] = {}
    for ipp in ATTACKER_IPS:
        observed[ipp["ip"]] = {**ipp}
    for ipp in CORP_OFFICE_IPS:
        observed[ipp["ip"]] = {**ipp, "kind": "corporate"}
    # Sample residential IPs from legit traffic (cap to ~30 to hit ~50 total).
    seen_residential: Dict[str, Dict[str, Any]] = {}
    for d in legit_docs:
        ip = d["source"]["ip"]
        if ip in observed or ip in seen_residential:
            continue
        seen_residential[ip] = {
            "ip": ip,
            "asn": d["source"]["as"]["number"],
            "as_org": d["source"]["as"]["organization"]["name"],
            "country_iso": d["source"]["geo"]["country_iso_code"],
            "country": d["source"]["geo"]["country_name"],
            "city": d["source"]["geo"].get("city_name"),
            "kind": "residential",
        }
        if len(seen_residential) >= 39:
            break
    observed.update(seen_residential)
    iplookup_docs = _generate_iplookup(rng, now, observed)

    # Track breach metadata on the module for downstream panel rendering.
    _persist_breach_table(all_breaches)

    return {
        INDICES["auth"]: auth_docs,
        INDICES["sessions"]: session_docs,
        INDICES["iplookup"]: iplookup_docs,
    }


# Module-level cache so panel builders can render the breach table without
# re-running the generator. Populated by the most recent generate_documents() call.
_BREACH_CACHE: List[Dict[str, Any]] = []


def _persist_breach_table(breaches: List[Dict[str, Any]]) -> None:
    global _BREACH_CACHE
    _BREACH_CACHE = [
        {
            "user_email": b["user_email"],
            "user_display": b["user_display"],
            "ip": b["ip_profile"]["ip"],
            "asn": b["ip_profile"]["asn"],
            "as_org": b["ip_profile"]["as_org"],
            "country_iso": b["ip_profile"]["country_iso"],
            "country": b["ip_profile"]["country"],
            "city": b["ip_profile"].get("city"),
            "seconds_ago": b["seconds_ago"],
        }
        for b in breaches
    ]


def get_breach_table() -> List[Dict[str, Any]]:
    return list(_BREACH_CACHE)


# ============================================================ Dashboard panels =====


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


# ----- Vega-Lite specs (inline data) -------------------------------------------------
#
# Kibana 9.3 rejects URL-based Vega specs at render time even when the saved
# object validates. Every spec below queries Elasticsearch at seed time and
# embeds the resulting buckets as `data.values`. Each query is wrapped in
# try/except so a transient ES failure produces an empty chart rather than a
# broken seed run.


def _vega_heatmap_country_hour() -> Dict[str, Any]:
    """Heatmap: failure count by hour-of-day x source country. Inline data."""
    values: List[Dict[str, Any]] = []
    try:
        es = get_client()
        r = es.search(index=INDEX_PATTERN, body={
            "size": 0,
            "query": {"bool": {"filter": [
                {"term": {"event.outcome": "failure"}},
                {"range": {"@timestamp": {"gte": "now-3d", "lte": "now"}}},
            ]}},
            "aggs": {
                "by_country": {
                    "terms": {"field": "source.geo.country_iso_code", "size": 20},
                    "aggs": {
                        "by_hour": {
                            "date_histogram": {
                                "field": "@timestamp",
                                "fixed_interval": "1h",
                                "min_doc_count": 1,
                            }
                        }
                    },
                }
            },
        })
        for cb in r["aggregations"]["by_country"]["buckets"]:
            country = cb["key"]
            for hb in cb["by_hour"]["buckets"]:
                ts_ms = hb.get("key")
                hour_of_day = None
                try:
                    if ts_ms is not None:
                        hour_of_day = datetime.fromtimestamp(
                            int(ts_ms) / 1000, tz=timezone.utc
                        ).hour
                except Exception:
                    hour_of_day = None
                values.append({
                    "country": country,
                    "hour_of_day": hour_of_day if hour_of_day is not None else 0,
                    "failures": int(hb.get("doc_count") or 0),
                })
    except Exception as exc:
        log.warning("credstuff.spec_heatmap.compute.failed", error=str(exc))

    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": "Failed logins by hour x source country (attack windows light up)",
        "data": {"values": values},
        "mark": {"type": "rect", "tooltip": True},
        "encoding": {
            "x": {
                "field": "hour_of_day", "type": "ordinal", "title": "Hour of day (UTC)",
                "axis": {"labelColor": "#cdd", "titleColor": "#cdd"},
            },
            "y": {
                "field": "country", "type": "nominal", "title": "Source country",
                "axis": {"labelColor": "#cdd", "titleColor": "#cdd"},
            },
            "color": {
                "field": "failures", "type": "quantitative",
                "scale": {"scheme": "reds"},
                "title": "Failures",
                "legend": {"labelColor": "#cdd", "titleColor": "#cdd"},
            },
            "tooltip": [
                {"field": "country", "type": "nominal"},
                {"field": "hour_of_day", "type": "ordinal", "title": "Hour"},
                {"field": "failures", "type": "quantitative"},
            ],
        },
        "config": {"view": {"stroke": "transparent"}, "background": "transparent"},
    }


def _vega_top_source_ips() -> Dict[str, Any]:
    """Top 10 source IPs by failure count, color-coded attacker vs baseline. Inline data."""
    attacker_orgs = {
        "DigitalOcean LLC", "Hetzner Online GmbH", "OVH SAS",
        "ANONYMIZED VPN PROVIDER",
    }
    values: List[Dict[str, Any]] = []
    try:
        es = get_client()
        r = es.search(index=INDEX_PATTERN, body={
            "size": 0,
            "query": {"bool": {"filter": [
                {"term": {"event.outcome": "failure"}},
                {"range": {"@timestamp": {"gte": "now-3d", "lte": "now"}}},
            ]}},
            "aggs": {
                "by_ip": {
                    "terms": {"field": "source.ip", "size": 10},
                    "aggs": {
                        "by_org": {"terms": {"field": "source.as.organization.name", "size": 1}},
                    },
                }
            },
        })
        for b in r["aggregations"]["by_ip"]["buckets"]:
            org_buckets = b.get("by_org", {}).get("buckets") or []
            as_org = org_buckets[0]["key"] if org_buckets else "unknown"
            classification = "attacker" if as_org in attacker_orgs else "baseline"
            values.append({
                "ip": b["key"],
                "failures": int(b.get("doc_count") or 0),
                "as_org": as_org,
                "classification": classification,
            })
    except Exception as exc:
        log.warning("credstuff.spec_top_ips.compute.failed", error=str(exc))

    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": "Top 10 source IPs by failed-login count",
        "data": {"values": values},
        "mark": {"type": "bar", "tooltip": True, "cornerRadiusEnd": 3},
        "encoding": {
            "y": {
                "field": "ip", "type": "nominal", "sort": "-x", "title": "Source IP",
                "axis": {"labelColor": "#cdd", "titleColor": "#cdd"},
            },
            "x": {
                "field": "failures", "type": "quantitative", "title": "Failures",
                "axis": {"labelColor": "#cdd", "titleColor": "#cdd"},
            },
            "color": {
                "field": "classification", "type": "nominal",
                "scale": {
                    "domain": ["attacker", "baseline"],
                    "range": ["#e8455d", "#5b8bbd"],
                },
                "title": "Classification",
                "legend": {"labelColor": "#cdd", "titleColor": "#cdd"},
            },
            "tooltip": [
                {"field": "ip", "type": "nominal"},
                {"field": "as_org", "type": "nominal", "title": "ASN"},
                {"field": "failures", "type": "quantitative"},
                {"field": "classification", "type": "nominal"},
            ],
        },
        "config": {"view": {"stroke": "transparent"}, "background": "transparent"},
    }


def _vega_logins_per_minute() -> Dict[str, Any]:
    """Two-line time series: success vs failure with shaded attack-wave bands.
    Inline data: per-minute buckets are computed at seed time."""
    now = _now()
    wave1_end = now - timedelta(seconds=2 * 24 * 3600)
    wave1_start = wave1_end - timedelta(minutes=30)
    wave2_end = now - timedelta(hours=6)
    wave2_start = wave2_end - timedelta(minutes=25)

    series_values: List[Dict[str, Any]] = []
    try:
        es = get_client()
        r = es.search(index=INDEX_PATTERN, body={
            "size": 0,
            "query": {"bool": {"filter": [
                {"range": {"@timestamp": {"gte": "now-3d", "lte": "now"}}},
            ]}},
            "aggs": {
                "by_outcome": {
                    "terms": {"field": "event.outcome", "size": 4},
                    "aggs": {
                        "by_minute": {
                            "date_histogram": {
                                "field": "@timestamp",
                                "fixed_interval": "5m",
                                "min_doc_count": 0,
                            }
                        }
                    },
                }
            },
        })
        for ob in r["aggregations"]["by_outcome"]["buckets"]:
            outcome = ob["key"]
            for mb in ob["by_minute"]["buckets"]:
                series_values.append({
                    "ts": mb.get("key_as_string") or mb.get("key"),
                    "outcome": outcome,
                    "count": int(mb.get("doc_count") or 0),
                })
    except Exception as exc:
        log.warning("credstuff.spec_logins_per_minute.compute.failed", error=str(exc))

    band_values = [
        {
            "wave_start": wave1_start.isoformat(),
            "wave_end": wave1_end.isoformat(),
            "label": "Wave 1 - low and slow recon",
        },
        {
            "wave_start": wave2_start.isoformat(),
            "wave_end": wave2_end.isoformat(),
            "label": "Wave 2 - aggressive spike",
        },
    ]
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": "Logins per 5-min bucket - success vs failure (attack waves shaded)",
        "layer": [
            {
                "data": {"values": band_values},
                "mark": {"type": "rect", "opacity": 0.18, "color": "#7e8794"},
                "encoding": {
                    "x": {"field": "wave_start", "type": "temporal"},
                    "x2": {"field": "wave_end"},
                    "tooltip": [{"field": "label", "type": "nominal"}],
                },
            },
            {
                "data": {"values": series_values},
                "mark": {"type": "line", "interpolate": "monotone", "strokeWidth": 2},
                "encoding": {
                    "x": {
                        "field": "ts", "type": "temporal", "title": "Time (UTC)",
                        "axis": {"labelColor": "#cdd", "titleColor": "#cdd"},
                    },
                    "y": {
                        "field": "count", "type": "quantitative", "title": "Logins / 5 min",
                        "axis": {"labelColor": "#cdd", "titleColor": "#cdd"},
                    },
                    "color": {
                        "field": "outcome", "type": "nominal",
                        "scale": {"domain": ["success", "failure"],
                                  "range": ["#3fb27f", "#e8455d"]},
                        "title": "Outcome",
                        "legend": {"labelColor": "#cdd", "titleColor": "#cdd"},
                    },
                    "tooltip": [
                        {"field": "ts", "type": "temporal", "title": "Bucket"},
                        {"field": "outcome", "type": "nominal"},
                        {"field": "count", "type": "quantitative"},
                    ],
                },
            },
        ],
        "config": {"view": {"stroke": "transparent"}, "background": "transparent"},
    }


def _vega_asn_treemap() -> Dict[str, Any]:
    """Donut of failed-login source ASNs - the datacenter footprint pops. Inline data."""
    datacenter_orgs = {"DigitalOcean LLC", "Hetzner Online GmbH", "OVH SAS"}
    values: List[Dict[str, Any]] = []
    try:
        es = get_client()
        r = es.search(index=INDEX_PATTERN, body={
            "size": 0,
            "query": {"bool": {"filter": [
                {"term": {"event.outcome": "failure"}},
                {"range": {"@timestamp": {"gte": "now-3d", "lte": "now"}}},
            ]}},
            "aggs": {
                "by_org": {"terms": {"field": "source.as.organization.name", "size": 12}},
            },
        })
        for b in r["aggregations"]["by_org"]["buckets"]:
            org = b["key"]
            if org in datacenter_orgs:
                kind = "datacenter"
            elif org == "ANONYMIZED VPN PROVIDER":
                kind = "anonymizer"
            else:
                kind = "legitimate"
            values.append({
                "as_org": org,
                "failures": int(b.get("doc_count") or 0),
                "kind": kind,
            })
    except Exception as exc:
        log.warning("credstuff.spec_asn_donut.compute.failed", error=str(exc))

    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": "Source ASN distribution (failures only)",
        "data": {"values": values},
        "mark": {"type": "arc", "innerRadius": 60, "tooltip": True, "stroke": "#1a1d24"},
        "encoding": {
            "theta": {"field": "failures", "type": "quantitative"},
            "color": {
                "field": "kind", "type": "nominal",
                "scale": {
                    "domain": ["datacenter", "anonymizer", "legitimate"],
                    "range": ["#e8455d", "#f0a830", "#5b8bbd"],
                },
                "title": "ASN type",
                "legend": {"labelColor": "#cdd", "titleColor": "#cdd"},
            },
            "tooltip": [
                {"field": "as_org", "type": "nominal", "title": "ASN"},
                {"field": "failures", "type": "quantitative"},
                {"field": "kind", "type": "nominal"},
            ],
        },
        "config": {"view": {"stroke": "transparent"}, "background": "transparent"},
    }


def _vega_failure_reasons() -> Dict[str, Any]:
    """Bar chart of `auth.failure_reason` distribution. Inline data.
    Tells the SOC analyst whether the attacker was burning known emails
    (invalid_password) or scanning for valid usernames (invalid_email)."""
    values: List[Dict[str, Any]] = []
    try:
        es = get_client()
        r = es.search(index=INDEX_PATTERN, body={
            "size": 0,
            "query": {"bool": {"filter": [
                {"term": {"event.outcome": "failure"}},
                {"range": {"@timestamp": {"gte": "now-3d", "lte": "now"}}},
                {"exists": {"field": "auth.failure_reason"}},
            ]}},
            "aggs": {
                "by_reason": {
                    "terms": {"field": "auth.failure_reason", "size": 10},
                },
            },
        })
        for b in r["aggregations"]["by_reason"]["buckets"]:
            values.append({
                "reason": b["key"],
                "count": int(b.get("doc_count") or 0),
            })
    except Exception as exc:
        log.warning("credstuff.spec_failure_reasons.compute.failed", error=str(exc))

    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": "Auth failure reason distribution (last 3d)",
        "data": {"values": values},
        "mark": {"type": "bar", "tooltip": True, "cornerRadiusEnd": 3},
        "encoding": {
            "y": {
                "field": "reason", "type": "nominal", "sort": "-x",
                "title": "Failure reason",
                "axis": {"labelColor": "#cdd", "titleColor": "#cdd"},
            },
            "x": {
                "field": "count", "type": "quantitative", "title": "Count",
                "axis": {"labelColor": "#cdd", "titleColor": "#cdd"},
            },
            "color": {
                "field": "reason", "type": "nominal",
                "scale": {
                    "domain": [
                        "invalid_password", "invalid_email", "rate_limited",
                        "account_locked", "mfa_required",
                    ],
                    "range": ["#e8455d", "#f0a830", "#7e8794", "#5b8bbd", "#3fb27f"],
                },
                "legend": {"labelColor": "#cdd", "titleColor": "#cdd"},
            },
            "tooltip": [
                {"field": "reason", "type": "nominal"},
                {"field": "count", "type": "quantitative"},
            ],
        },
        "config": {"view": {"stroke": "transparent"}, "background": "transparent"},
    }


def _vega_targeted_users() -> Dict[str, Any]:
    """Top 10 most-targeted usernames with attempt counts and a flag for
    confirmed breach. Shows attacker targeting strategy. Inline data."""
    breached_emails = {b["user_email"] for b in get_breach_table()}
    values: List[Dict[str, Any]] = []
    try:
        es = get_client()
        r = es.search(index=INDICES["auth"], body={
            "size": 0,
            "query": {"bool": {"filter": [
                {"term": {"event.outcome": "failure"}},
                {"range": {"@timestamp": {"gte": "now-3d", "lte": "now"}}},
                {"bool": {"must_not": [
                    {"term": {"auth.failure_reason": "invalid_email"}},
                ]}},
                {"exists": {"field": "user.email"}},
            ]}},
            "aggs": {
                "by_user": {
                    "terms": {"field": "user.email", "size": 10},
                },
            },
        })
        for b in r["aggregations"]["by_user"]["buckets"]:
            email = b["key"]
            values.append({
                "user": email,
                "attempts": int(b.get("doc_count") or 0),
                "status": "BREACHED" if email in breached_emails else "blocked",
            })
    except Exception as exc:
        log.warning("credstuff.spec_targeted_users.compute.failed", error=str(exc))

    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": "Top targeted users - attempts vs breach outcome",
        "data": {"values": values},
        "mark": {"type": "bar", "tooltip": True, "cornerRadiusEnd": 3},
        "encoding": {
            "y": {
                "field": "user", "type": "nominal", "sort": "-x", "title": "User email",
                "axis": {"labelColor": "#cdd", "titleColor": "#cdd"},
            },
            "x": {
                "field": "attempts", "type": "quantitative", "title": "Failed attempts",
                "axis": {"labelColor": "#cdd", "titleColor": "#cdd"},
            },
            "color": {
                "field": "status", "type": "nominal",
                "scale": {
                    "domain": ["BREACHED", "blocked"],
                    "range": ["#e8455d", "#5b8bbd"],
                },
                "title": "Outcome",
                "legend": {"labelColor": "#cdd", "titleColor": "#cdd"},
            },
            "tooltip": [
                {"field": "user", "type": "nominal"},
                {"field": "attempts", "type": "quantitative"},
                {"field": "status", "type": "nominal"},
            ],
        },
        "config": {"view": {"stroke": "transparent"}, "background": "transparent"},
    }


# ----- KPI helpers (queried at seed time, rendered as markdown) ----------------------


def _compute_time_to_first_breach() -> Dict[str, Any]:
    """Returns dict with first_failure_iso, first_breach_iso, ttd_minutes, total_failures.
    All ES queries wrapped in try/except - returns sane defaults on failure."""
    out: Dict[str, Any] = {
        "first_failure_iso": None,
        "first_breach_iso": None,
        "ttd_minutes": None,
        "total_failures": 0,
        "total_breaches": len(get_breach_table()),
    }
    try:
        es = get_client()
        r1 = es.search(index=INDICES["auth"], body={
            "size": 1,
            "_source": ["@timestamp"],
            "query": {"bool": {"filter": [
                {"term": {"event.outcome": "failure"}},
                {"exists": {"field": "threat.technique.id"}},
                {"range": {"@timestamp": {"gte": "now-3d", "lte": "now"}}},
            ]}},
            "sort": [{"@timestamp": {"order": "asc"}}],
        })
        hits1 = r1.get("hits", {}).get("hits", [])
        if hits1:
            out["first_failure_iso"] = hits1[0]["_source"]["@timestamp"]
        r2 = es.search(index=INDICES["sessions"], body={
            "size": 1,
            "_source": ["@timestamp"],
            "query": {"bool": {"filter": [
                {"term": {"labels.breach": "confirmed"}},
                {"range": {"@timestamp": {"gte": "now-3d", "lte": "now"}}},
            ]}},
            "sort": [{"@timestamp": {"order": "asc"}}],
        })
        hits2 = r2.get("hits", {}).get("hits", [])
        if hits2:
            out["first_breach_iso"] = hits2[0]["_source"]["@timestamp"]
        r3 = es.count(index=INDICES["auth"], body={
            "query": {"bool": {"filter": [
                {"term": {"event.outcome": "failure"}},
                {"range": {"@timestamp": {"gte": "now-3d", "lte": "now"}}},
            ]}},
        })
        out["total_failures"] = int(r3.get("count") or 0)
    except Exception as exc:
        log.warning("credstuff.kpi.ttd.compute.failed", error=str(exc))

    if out["first_failure_iso"] and out["first_breach_iso"]:
        try:
            t1 = datetime.fromisoformat(out["first_failure_iso"].replace("Z", "+00:00"))
            t2 = datetime.fromisoformat(out["first_breach_iso"].replace("Z", "+00:00"))
            out["ttd_minutes"] = round((t2 - t1).total_seconds() / 60.0, 1)
        except Exception:
            pass
    return out


# ----- Markdown content --------------------------------------------------------------


def _switcher_md(active: str) -> str:
    """Header switcher with anchor links to the other view. `active` is "fe" or
    "customer". Same content on both dashboards, only the highlighted link differs."""
    fe_url = settings.kibana_url.rstrip("/") + f"/app/dashboards#/view/{DASHBOARD_ID}"
    cu_url = settings.kibana_url.rstrip("/") + f"/app/dashboards#/view/{CUSTOMER_DASHBOARD_ID}"
    fe_label = "**[FE] Field Engineer prep**" if active == "fe" else "[FE] Field Engineer prep"
    cu_label = "**[Customer] SOC / CISO view**" if active == "customer" else "[Customer] SOC / CISO view"
    return (
        "### Credential Stuffing Attack - dashboard switcher\n\n"
        f"Pick your view:  [{fe_label}]({fe_url})  |  [{cu_label}]({cu_url})\n\n"
        "_Same data, two narratives. FE view is the demo prep with MITRE + MEDDPICC + "
        "talk track. Customer view is the executive incident report._"
    )


def _md_fe_intro() -> str:
    return (
        "## [FE] Credential Stuffing Attack - Field Engineer prep\n\n"
        "**MITRE: T1110.004 Credential Stuffing | TA0006 Credential Access**\n\n"
        "An attacker is burning a leaked credential dump (~10k emails from a 2024 third-party "
        "SaaS breach) against `app.bigcorp.com`. Two waves observed:\n\n"
        "1. **Wave 1 - low and slow recon (~2 days ago, 30 min):** ~50 attempts/min from 8 "
        "datacenter / VPN IPs. Pattern testing for valid usernames.\n"
        "2. **Wave 2 - aggressive spike (~6 hours ago, 25 min):** thunder-herd from 6 "
        "datacenter IPs. Peak ~60 attempts/min/IP; 4 confirmed account compromises with "
        "follow-on session creation + password reset attempts.\n\n"
        "**Demo talk track:**\n"
        "1. Open with the heatmap (top-left): show how datacenter-country cells light up "
        "during the two waves while baseline geos stay dark.\n"
        "2. Click into the breach table: 4 confirmed account takeovers, all from attacker "
        "ASNs. This is the moment that lands with the CISO.\n"
        "3. Pivot to the auth-failure-reason chart: the attacker is mostly hitting "
        "`invalid_password` against real users, which is exactly the credential-stuffing "
        "fingerprint.\n"
        "4. Close with the EQL hunt example in the closing panel - show how this scales to "
        "thousands of services without rewriting Splunk SPL.\n\n"
        "**Elastic Security capabilities that catch this:**\n"
        "- ML auth jobs: `auth_high_count_logon_fails`, `auth_rare_source_ip_for_a_user`\n"
        "- Prebuilt detection rule: *Multiple Logon Failures from the Same Source*\n"
        "- Behavior Analytics: anomalous geo + ASN for known users\n"
        "- EQL hunt: `sequence by source.ip [authentication where event.outcome=='failure'] "
        "with maxspan=10m`\n\n"
        "**Source quotes (use verbatim):**\n"
        "- *Verizon DBIR 2024:* \"Stolen credentials remain the top initial-access vector, "
        "implicated in 38% of breaches.\"\n"
        "- *Elastic Security docs:* \"`auth_high_count_logon_fails` flags source IPs "
        "exceeding their 14-day baseline at p99.5.\""
    )


def _md_customer_intro() -> str:
    return (
        "## [Customer] Credential Stuffing Attack - Security Incident Report\n\n"
        "**Incident class:** Attempted account takeover via credential stuffing  \n"
        "**MITRE technique:** T1110.004  \n"
        "**Status:** Contained - active response in progress\n\n"
        "**What happened.** Between two days ago and six hours ago, an external attacker "
        "operating from datacenter and anonymizer infrastructure attempted to gain access "
        "to `app.bigcorp.com` employee accounts using a leaked credential dump from an "
        "unrelated 2024 SaaS breach. The campaign played out in two waves: a low and slow "
        "reconnaissance phase, followed by an aggressive datacenter spike six hours ago.\n\n"
        "**Headline numbers:**\n"
        "- **4** confirmed account takeovers (sessions revoked, passwords rotated, MFA "
        "re-enrolled)\n"
        "- **1500+** failed logins blocked or rate-limited at the auth layer\n"
        "- **8** distinct attacker source IPs across **4** datacenter / VPN ASNs\n"
        "- Detection time: under 10 minutes from first anomalous failure cluster\n\n"
        "**What was caught:** every successful breach was correlated with its session "
        "creation + follow-on suspicious actions inside Elastic Security. Cases were "
        "auto-bundled and escalated to Tier-2.\n\n"
        "**What was missed (and is now backlog):** the wave-1 recon phase from two days ago "
        "did not page Tier-2 because the threshold was tuned for a single-IP burst. Wave 1 "
        "was distributed across 8 IPs at sub-threshold rate. The new ML job baselines "
        "failure rates per ASN as well as per IP."
    )


def _md_breach_table(breaches: List[Dict[str, Any]]) -> str:
    if not breaches:
        return (
            "## Confirmed Breaches\n\n_Run the seeder; the table will populate from "
            "the generated breach records._"
        )
    rows = [
        "## Confirmed Account Compromises\n",
        "Cross-referenced from `event.outcome:success` joined to `source.as.organization.name` "
        "matching known attacker ASNs. Each requires immediate password reset + session revoke.\n\n",
        "| User | Email | Source IP | ASN | Geo | When | MITRE |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    now = _now()
    for b in breaches:
        when = (now - timedelta(seconds=b["seconds_ago"])).strftime("%Y-%m-%d %H:%M UTC")
        geo = f"{b['country_iso']} / {b.get('city') or '-'}"
        rows.append(
            f"| **{b['user_display']}** | `{b['user_email']}` | `{b['ip']}` | "
            f"AS{b['asn']} {b['as_org']} | {geo} | {when} | "
            f"[T1110.004](https://attack.mitre.org/techniques/T1110/004/) |"
        )
    return "\n".join(rows)


def _md_ttd_kpi(kpi: Dict[str, Any]) -> str:
    """Renders the time-to-first-breach KPI block as markdown.
    Falls back to a placeholder when ES did not return data."""
    ttd = kpi.get("ttd_minutes")
    total_failures = kpi.get("total_failures") or 0
    total_breaches = kpi.get("total_breaches") or 0
    ttd_str = f"{ttd:.1f} min" if isinstance(ttd, (int, float)) else "n/a"
    first_fail = kpi.get("first_failure_iso") or "n/a"
    first_breach = kpi.get("first_breach_iso") or "n/a"
    return (
        "## Time-to-first-breach\n\n"
        f"### Detection window\n"
        f"# **{ttd_str}**\n\n"
        f"_From first attacker failure to first confirmed session takeover._\n\n"
        f"- **First attacker failure:** `{first_fail}`\n"
        f"- **First confirmed breach session:** `{first_breach}`\n"
        f"- **Total failed logins (3d):** **{total_failures:,}**\n"
        f"- **Confirmed compromises:** **{total_breaches}**\n"
    )


def _md_fe_closing() -> str:
    return (
        "## How this becomes a customer conversation\n\n"
        "**MEDDPICC angle for the next call:**\n"
        "- **Metrics:** time-to-detection (today: hours via SIEM correlation; with Elastic "
        "ML auth jobs: under 10 minutes per the chart above). 4 confirmed breaches translates "
        "to 4 forced password rotations, 4 incident reports, and N hours of SOC analyst time.\n"
        "- **Economic Buyer pain:** \"We had 4 confirmed account breaches this week and the "
        "first sign was a help-desk ticket from the affected employee.\"\n"
        "- **Decision Criteria:** SIEM consolidation. Today the customer runs Splunk for "
        "logs + a separate IDP analytics tool + manual VirusTotal pivots. Elastic Security "
        "unifies all three under one ECS-compliant index.\n"
        "- **Champion enablement:** the EQL hunt syntax, the Behavior Analytics geo-anomaly "
        "rule, and the auto-Case workflow are all out of the box. Champion does not have to "
        "rewrite SPL queries.\n"
        "- **Competition:** Splunk ES (slow detection rules, no native ML for auth), "
        "CrowdStrike Identity (no log unification), Microsoft Sentinel (Azure-only ML).\n\n"
        "## MITRE ATT&CK mapping and Elastic countermeasures\n\n"
        "| MITRE | Stage | Elastic Security capability |\n"
        "| --- | --- | --- |\n"
        "| **[T1110.004](https://attack.mitre.org/techniques/T1110/004/) Credential Stuffing** "
        "| Initial pre-auth probing | ML job `auth_high_count_logon_fails` (anomaly detection "
        "on failure-rate per source.ip); prebuilt rule *Multiple Logon Failures From the "
        "Same Source* |\n"
        "| **[T1078](https://attack.mitre.org/techniques/T1078/) Valid Accounts** "
        "| Post-breach session creation | Behavior Analytics anomalous-geo rule (mismatch vs "
        "user's 30-day baseline); auto-create Case with affected user + IOC pivot |\n"
        "| **[T1556](https://attack.mitre.org/techniques/T1556/) Modify Authentication Process** "
        "| Attacker password-reset / MFA bypass | EQL rule chains successful login + "
        "`event.action:user-password-reset` from a non-trusted ASN within 10 min; Endpoint "
        "Integration auto-revokes session |\n\n"
        "**Call to action.** Schedule a 30-minute live walkthrough on the customer's own "
        "auth telemetry next week. We mirror their staging IDP feed into a free Elastic "
        "Cloud trial and reproduce this dashboard against their data inside the same call."
    )


def _md_customer_closing() -> str:
    return (
        "## What was caught, what was missed, and what is next\n\n"
        "**Caught:**\n"
        "- All 4 successful logins from attacker ASNs were correlated with their session "
        "creation events and tagged `labels.breach: confirmed`.\n"
        "- Wave 2 (the aggressive spike) tripped the `auth_high_count_logon_fails` ML job "
        "within minutes; Tier-2 was paged automatically.\n"
        "- Geo-anomaly detection caught the post-breach session activity from "
        "non-baseline countries.\n\n"
        "**Missed (and now in scope):**\n"
        "- Wave 1 (the low-and-slow recon two days ago) was distributed across 8 IPs at "
        "sub-threshold rate per IP. Today's threshold detection did not page. Going "
        "forward, the per-ASN ML baseline closes that gap.\n"
        "- Two of the breached users had only single-factor authentication. MFA enrolment "
        "is now mandatory for the affected access tier.\n\n"
        "**Recommended controls (priority order):**\n"
        "1. **Per-ASN failure rate ML job** - catches distributed credential-stuffing the "
        "single-IP rule misses. Effort: 1 day.\n"
        "2. **Mandatory MFA on the affected access tier** - blocks credential reuse even "
        "when the dump is valid. Effort: policy change + 2 weeks rollout.\n"
        "3. **Threat intel feed for known datacenter ASN ranges** - default-deny on auth "
        "endpoints from DigitalOcean / Hetzner / OVH unless the user has previously "
        "logged in from that ASN. Effort: 3 days + change-control review.\n"
        "4. **Auto-revoke on geo-anomaly** - Endpoint integration response action revokes "
        "the session within seconds of the Behavior Analytics rule firing.\n\n"
        "**Executive summary one-liner:** Elastic Security detected and contained an active "
        "credential-stuffing campaign against 4 corporate accounts before the attacker could "
        "pivot inside the environment. Controls are being tuned to close the wave-1 gap."
    )


# ----- Lens helpers (live time-picker drama) -----------------------------------------
#
# The two highest-value SOC-analyst panels (logins-per-minute time series and
# top-IPs by failure count) are rendered as Lens visualisations so the time
# picker, drag-zoom, and breakdown legends all work natively. The remaining
# panels stay as inline-data Vega-Lite for resilience. If the Lens saved-object
# spec is rejected by this Kibana version, `_build_panels` falls back to the
# pre-existing Vega panel for that slot so the dashboard never breaks.

CREDSTUFF_AUTH_DATA_VIEW_ID: str = "demo-credstuff-auth-dv"
CREDSTUFF_AUTH_INDEX_PATTERN: str = "demo-credstuff-auth"


def _ensure_data_view(
    *,
    dv_id: str = CREDSTUFF_AUTH_DATA_VIEW_ID,
    title: str = CREDSTUFF_AUTH_INDEX_PATTERN,
    name: str = "demo credstuff auth",
) -> Optional[str]:
    """Idempotently create a dedicated auth-only data view used by the Lens
    panels. Returns the data view id, or None if creation failed (caller should
    fall back to Vega)."""
    body = {
        "data_view": {
            "id": dv_id,
            "title": title,
            "name": name,
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
        try:
            resp = client.post(_kbn_url("/api/data_views/data_view"),
                               headers=_kbn_headers(), json=body)
            if resp.status_code < 400:
                return dv_id
            log.warning("credstuff.lens_dv.fallback",
                        status=resp.status_code, body=resp.text[:300])
            body2 = [{
                "id": dv_id,
                "type": "index-pattern",
                "attributes": {
                    "title": title,
                    "name": name,
                    "timeFieldName": "@timestamp",
                },
            }]
            resp2 = client.post(_kbn_url("/api/saved_objects/_bulk_create?overwrite=true"),
                                headers=_kbn_headers(), json=body2)
            if resp2.status_code < 400:
                return dv_id
            log.warning("credstuff.lens_dv.create_failed",
                        status=resp2.status_code, body=resp2.text[:300])
        except Exception as exc:
            log.warning("credstuff.lens_dv.exception", error=str(exc))
    return None


def _lens_logins_timeseries_attrs(data_view_id: str, title: str) -> Dict[str, Any]:
    """Lens XY two-line time series (success vs failure) broken down by event.outcome.

    Layout: x = @timestamp date_histogram (auto interval), y = count of records,
    breakdown = terms on event.outcome. SOC analysts get native drag-zoom and
    follow the global time picker."""
    layer_id = "layer_logins_ts"
    col_x = "col_x_ts"
    col_y = "col_y_count"
    col_split = "col_split_outcome"
    return {
        "title": title,
        "description": "",
        "visualizationType": "lnsXY",
        "state": {
            "datasourceStates": {
                "formBased": {
                    "layers": {
                        layer_id: {
                            "columnOrder": [col_x, col_split, col_y],
                            "columns": {
                                col_x: {
                                    "label": "@timestamp",
                                    "dataType": "date",
                                    "operationType": "date_histogram",
                                    "sourceField": "@timestamp",
                                    "isBucketed": True,
                                    "scale": "interval",
                                    "params": {"interval": "auto", "includeEmptyRows": True},
                                },
                                col_split: {
                                    "label": "Top values of event.outcome",
                                    "dataType": "string",
                                    "operationType": "terms",
                                    "sourceField": "event.outcome",
                                    "isBucketed": True,
                                    "scale": "ordinal",
                                    "params": {
                                        "size": 4,
                                        "orderBy": {"type": "column", "columnId": col_y},
                                        "orderDirection": "desc",
                                        "otherBucket": False,
                                        "missingBucket": False,
                                        "parentFormat": {"id": "terms"},
                                    },
                                },
                                col_y: {
                                    "label": "Count of records",
                                    "dataType": "number",
                                    "operationType": "count",
                                    "sourceField": "___records___",
                                    "isBucketed": False,
                                    "scale": "ratio",
                                },
                            },
                            "incompleteColumns": {},
                        }
                    }
                }
            },
            "visualization": {
                "legend": {"isVisible": True, "position": "right"},
                "valueLabels": "hide",
                "fittingFunction": "None",
                "axisTitlesVisibilitySettings": {"x": True, "yLeft": True, "yRight": True},
                "tickLabelsVisibilitySettings": {"x": True, "yLeft": True, "yRight": True},
                "labelsOrientation": {"x": 0, "yLeft": 0, "yRight": 0},
                "gridlinesVisibilitySettings": {"x": True, "yLeft": True, "yRight": True},
                "preferredSeriesType": "line",
                "layers": [
                    {
                        "layerId": layer_id,
                        "accessors": [col_y],
                        "position": "top",
                        "seriesType": "line",
                        "showGridlines": False,
                        "layerType": "data",
                        "xAccessor": col_x,
                        "splitAccessor": col_split,
                    }
                ],
            },
            "query": {"query": "", "language": "kuery"},
            "filters": [],
        },
        "references": [
            {
                "type": "index-pattern",
                "id": data_view_id,
                "name": f"indexpattern-datasource-layer-{layer_id}",
            }
        ],
    }


def _lens_top_ips_failures_attrs(data_view_id: str, title: str) -> Dict[str, Any]:
    """Lens horizontal bar chart: top 10 source IPs filtered to event.outcome:failure."""
    layer_id = "layer_top_ips"
    col_split = "col_split_ip"
    col_y = "col_y_count"
    return {
        "title": title,
        "description": "",
        "visualizationType": "lnsXY",
        "state": {
            "datasourceStates": {
                "formBased": {
                    "layers": {
                        layer_id: {
                            "columnOrder": [col_split, col_y],
                            "columns": {
                                col_split: {
                                    "label": "Top values of source.ip",
                                    "dataType": "ip",
                                    "operationType": "terms",
                                    "sourceField": "source.ip",
                                    "isBucketed": True,
                                    "scale": "ordinal",
                                    "params": {
                                        "size": 10,
                                        "orderBy": {"type": "column", "columnId": col_y},
                                        "orderDirection": "desc",
                                        "otherBucket": False,
                                        "missingBucket": False,
                                        "parentFormat": {"id": "terms"},
                                    },
                                },
                                col_y: {
                                    "label": "Failed logins",
                                    "dataType": "number",
                                    "operationType": "count",
                                    "sourceField": "___records___",
                                    "isBucketed": False,
                                    "scale": "ratio",
                                },
                            },
                            "incompleteColumns": {},
                        }
                    }
                }
            },
            "visualization": {
                "legend": {"isVisible": True, "position": "right"},
                "valueLabels": "hide",
                "fittingFunction": "None",
                "axisTitlesVisibilitySettings": {"x": True, "yLeft": True, "yRight": True},
                "tickLabelsVisibilitySettings": {"x": True, "yLeft": True, "yRight": True},
                "labelsOrientation": {"x": 0, "yLeft": 0, "yRight": 0},
                "gridlinesVisibilitySettings": {"x": False, "yLeft": True, "yRight": True},
                "preferredSeriesType": "bar_horizontal",
                "layers": [
                    {
                        "layerId": layer_id,
                        "accessors": [col_y],
                        "position": "top",
                        "seriesType": "bar_horizontal",
                        "showGridlines": False,
                        "layerType": "data",
                        "xAccessor": col_split,
                    }
                ],
            },
            "query": {"query": "event.outcome : \"failure\"", "language": "kuery"},
            "filters": [],
        },
        "references": [
            {
                "type": "index-pattern",
                "id": data_view_id,
                "name": f"indexpattern-datasource-layer-{layer_id}",
            }
        ],
    }


def _lens_panel(
    panel_id: str,
    x: int,
    y: int,
    w: int,
    h: int,
    title: str,
    attributes: Dict[str, Any],
) -> Dict[str, Any]:
    """Build a byValue Lens dashboard panel.

    The Lens visualisation is embedded inline in the dashboard saved object;
    no separate Lens saved-object is created. The panel-level references are
    duplicated from the attributes.references so Kibana resolves the data
    view both at the panel level and inside the Lens state."""
    refs = attributes.get("references", [])
    panel_refs = []
    for ref in refs:
        panel_refs.append({
            "type": ref["type"],
            "id": ref["id"],
            "name": f"{panel_id}:{ref['name']}",
        })
    return {
        "type": "lens",
        "panelIndex": panel_id,
        "gridData": {"x": x, "y": y, "w": w, "h": h, "i": panel_id},
        "version": "9.3.4",
        "panelRefName": None,
        "embeddableConfig": {
            "enhancements": {},
            "attributes": attributes,
        },
        "title": title,
        "panelConfig": {},
        "references": panel_refs,
    }


# ----- Panels assembly ---------------------------------------------------------------


def _build_panels(view: str, lens_data_view_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Build the panel layout for either the FE or Customer dashboard.

    Both views share the same chart panels; only the surrounding markdown
    narrative differs. Two panels (logins-per-minute time series and
    top-IPs-by-failure bar) render as Lens when `lens_data_view_id` is
    provided. If Lens attribute construction raises, those slots fall back
    to inline-data Vega-Lite so the dashboard never breaks.
    """
    breaches = get_breach_table()
    kpi = _compute_time_to_first_breach()

    intro_md = _md_fe_intro() if view == "fe" else _md_customer_intro()
    closing_md = _md_fe_closing() if view == "fe" else _md_customer_closing()

    # Build Vega specs once each so both dashboards share the same inline data.
    spec_heatmap = _vega_heatmap_country_hour()
    spec_top_ips = _vega_top_source_ips()
    spec_logins = _vega_logins_per_minute()
    spec_asn = _vega_asn_treemap()
    spec_failure_reasons = _vega_failure_reasons()
    spec_targeted = _vega_targeted_users()

    # Try to build the two Lens panels. Each is wrapped in its own try/except so
    # one failure does not lose the other. On failure we fall back to the
    # equivalent inline-data Vega panel so the dashboard always renders.
    lens_logins_panel: Optional[Dict[str, Any]] = None
    lens_top_ips_panel: Optional[Dict[str, Any]] = None
    if lens_data_view_id:
        try:
            attrs_logins = _lens_logins_timeseries_attrs(
                lens_data_view_id,
                "Logins over time - success vs failure (Lens, drag to zoom)",
            )
            lens_logins_panel = _lens_panel(
                "p_line", 0, 26, 48, 14,
                "Logins over time - success vs failure (Lens, drag to zoom)",
                attrs_logins,
            )
        except Exception as exc:
            log.warning("credstuff.lens_logins.fallback_to_vega", error=str(exc))
            lens_logins_panel = None
        try:
            attrs_top_ips = _lens_top_ips_failures_attrs(
                lens_data_view_id,
                "Top source IPs by failed login (Lens)",
            )
            lens_top_ips_panel = _lens_panel(
                "p_ips", 24, 12, 24, 14,
                "Top source IPs by failed login (Lens)",
                attrs_top_ips,
            )
        except Exception as exc:
            log.warning("credstuff.lens_top_ips.fallback_to_vega", error=str(exc))
            lens_top_ips_panel = None

    panels: List[Dict[str, Any]] = []

    # Row 1: switcher (full width, h=4)
    panels.append(_markdown_panel("switcher", 0, 0, 48, 4, _switcher_md(view),
                                  "Switch view"))

    # Row 2: intro markdown (full width, h=8)
    panels.append(_markdown_panel("intro", 0, 4, 48, 8, intro_md,
                                  "Overview"))

    # Row 3: heatmap (24w, h=14) + top IPs (24w, h=14) - top IPs is Lens when available
    panels.append(_vega_panel("p_heat", 0, 12, 24, 14,
                              "Failures by hour x source country", spec_heatmap))
    if lens_top_ips_panel is not None:
        panels.append(lens_top_ips_panel)
    else:
        panels.append(_vega_panel("p_ips", 24, 12, 24, 14,
                                  "Top 10 source IPs by failures", spec_top_ips))

    # Row 4: full-width line chart (48w, h=14) - Lens when available
    if lens_logins_panel is not None:
        panels.append(lens_logins_panel)
    else:
        panels.append(_vega_panel("p_line", 0, 26, 48, 14,
                                  "Logins per 5-min bucket - success vs failure",
                                  spec_logins))

    # Row 5: failure-reason bar (16w, h=12) + targeted users bar (16w, h=12)
    #         + ASN donut (16w, h=12)
    panels.append(_vega_panel("p_reasons", 0, 40, 16, 12,
                              "Auth failure reason distribution", spec_failure_reasons))
    panels.append(_vega_panel("p_targets", 16, 40, 16, 12,
                              "Top targeted users (attempts + breach flag)",
                              spec_targeted))
    panels.append(_vega_panel("p_asn", 32, 40, 16, 12,
                              "Source ASN distribution (failures)", spec_asn))

    # Row 6: time-to-first-breach KPI (16w, h=12) + breach table (32w, h=12)
    panels.append(_markdown_panel("p_ttd", 0, 52, 16, 12, _md_ttd_kpi(kpi),
                                  "Time-to-first-breach"))
    panels.append(_markdown_panel("p_breach", 16, 52, 32, 12, _md_breach_table(breaches),
                                  "Confirmed account compromises"))

    # Row 7: closing narrative (full width, h=12)
    panels.append(_markdown_panel("closing", 0, 64, 48, 12, closing_md,
                                  "Closing narrative"))

    return panels


def _fe_industry_context() -> Dict[str, Any]:
    return {
        "id": "credstuff",
        "name": "Credential stuffing - SOC defender",
        "summary": ("Credential-stuffing wave detected via ML jobs across "
                    "logins, ASN, and country dimensions."),
        "personas": [
            {"role": "CISO",
             "pain": "Time-to-detect ATO is measured in hours, not seconds."},
            {"role": "SOC Lead",
             "pain": "Rule-based alerts in the legacy SIEM generate 30% false-positives."},
            {"role": "Head of Fraud",
             "pain": "Linking login anomalies to downstream fraud is manual today."},
            {"role": "Compliance Officer",
             "pain": "PCI DSS and DORA evidence pulls are 2-3 weeks of manual lift."},
        ],
        "regulations": ["PCI DSS", "DORA", "GDPR", "MITRE T1110.004"],
        "top_competitors": ["battlecard-splunk", "battlecard-microsoft-sentinel",
                            "battlecard-sumologic"],
    }


def _fe_superset_panels(lens_data_view_id: Optional[str] = None) -> List[Dict[str, Any]]:
    from app.services.scenarios.industry_factory import build_fe_superset_panels

    cu_panels = _build_panels("customer", lens_data_view_id=lens_data_view_id)
    legacy_fe = _build_panels("fe", lens_data_view_id=lens_data_view_id)
    fe_only_extras = [p for p in legacy_fe
                      if p.get("embeddableConfig", {}).get("savedVis", {})
                          .get("type") == "markdown"
                      and p.get("panelIndex") not in ("p_switch",)]
    return build_fe_superset_panels(
        _fe_industry_context(),
        customer="SOC team",
        customer_panels=cu_panels,
        fe_only_extras=fe_only_extras,
        id_prefix="cs-fe",
    )


def get_dashboard_panels() -> List[Dict[str, Any]]:
    """FE = customer panels (each prefaced by an FE value-callout) + the
    legacy FE-only markdown talk-track + discovery questions + say/do-not-say."""
    return _fe_superset_panels(lens_data_view_id=None)


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
            "name": f"demo · {SCENARIO_ID}",
            "timeFieldName": "@timestamp",
        },
        "override": True,
    }
    with httpx.Client(timeout=30.0) as client:
        try:
            client.delete(_kbn_url(f"/api/data_views/data_view/{dv_id}"), headers=_kbn_headers())
        except Exception:
            pass
        resp = client.post(_kbn_url("/api/data_views/data_view"),
                           headers=_kbn_headers(), json=body)
        if resp.status_code >= 400:
            log.warning("credstuff.dataview.fallback", status=resp.status_code, body=resp.text[:300])
            body2 = [{
                "id": dv_id,
                "type": "index-pattern",
                "attributes": {
                    "title": INDEX_PATTERN,
                    "name": f"demo · {SCENARIO_ID}",
                    "timeFieldName": "@timestamp",
                },
            }]
            resp2 = client.post(_kbn_url("/api/saved_objects/_bulk_create?overwrite=true"),
                                headers=_kbn_headers(), json=body2)
            if resp2.status_code >= 400:
                raise RuntimeError(
                    f"Kibana data view create failed: {resp2.status_code} {resp2.text[:300]}"
                )
    return dv_id


def _create_one_dashboard(
    *,
    data_view_id: str,
    dashboard_id: str,
    title: str,
    description: str,
    panels: List[Dict[str, Any]],
    extra_data_view_ids: Optional[List[str]] = None,
) -> str:
    """Idempotently create a single dashboard with the given panels.

    Lens panels embed their own per-panel references but Kibana also
    flattens panel references onto the dashboard saved object. We collect
    every unique panel-level reference and merge them with the top-level
    search-source data view reference so the dashboard validates."""
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

    references: List[Dict[str, str]] = [
        {"id": data_view_id, "type": "index-pattern",
         "name": "kibanaSavedObjectMeta.searchSourceJSON.index"},
    ]
    seen_ref_keys = {(ref["type"], ref["id"], ref["name"]) for ref in references}
    for panel in panels:
        for ref in panel.get("references", []) or []:
            key = (ref.get("type"), ref.get("id"), ref.get("name"))
            if None in key or key in seen_ref_keys:
                continue
            references.append({"id": ref["id"], "type": ref["type"], "name": ref["name"]})
            seen_ref_keys.add(key)

    body = [{
        "id": dashboard_id,
        "type": "dashboard",
        "attributes": {
            "title": title,
            "description": description,
            "panelsJSON": panels_json,
            "optionsJSON": options_json,
            "timeRestore": True,
            "timeFrom": "now-3d",
            "timeTo": "now",
            "refreshInterval": {"pause": True, "value": 0},
            "version": 1,
            "kibanaSavedObjectMeta": {"searchSourceJSON": search_source_json},
        },
        "references": references,
    }]
    with httpx.Client(timeout=30.0) as client:
        # Best-effort delete first for idempotency.
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


def _create_dashboard(
    data_view_id: str,
    lens_data_view_id: Optional[str] = None,
) -> Dict[str, str]:
    """Create both the FE and Customer dashboards. Returns a dict of ids.

    When `lens_data_view_id` is provided the two highest-value panels render
    as Lens visualisations using that data view; otherwise every panel falls
    back to the legacy inline-data Vega layout."""
    fe_panels = _fe_superset_panels(lens_data_view_id=lens_data_view_id)
    cu_panels = _build_panels("customer", lens_data_view_id=lens_data_view_id)

    fe_id = _create_one_dashboard(
        data_view_id=data_view_id,
        dashboard_id=DASHBOARD_ID,
        title=f"[FE] {SCENARIO_TITLE}",
        description=(
            "Field Engineer prep view. MITRE T1110.004 alignment, Elastic Security "
            "capabilities, demo talk track, MEDDPICC angle."
        ),
        panels=fe_panels,
    )
    cu_id = _create_one_dashboard(
        data_view_id=data_view_id,
        dashboard_id=CUSTOMER_DASHBOARD_ID,
        title=f"[Customer] {SCENARIO_TITLE}",
        description=(
            "SOC analyst / CISO view. Executive incident report: what was caught, "
            "what was missed, time-to-detection, recommended controls."
        ),
        panels=cu_panels,
    )
    return {"fe": fe_id, "customer": cu_id}


# ============================================================ End-to-end seed =====


def _to_bulk_actions(index: str, docs: List[Dict[str, Any]]):
    for doc in docs:
        yield {"_index": index, "_source": doc}


def seed() -> Dict[str, Any]:
    """Idempotent end-to-end. DELETE existing indices + dashboard, recreate with
    mappings, bulk-ingest, recreate dashboard. Returns counts + dashboard URL."""
    started = time.time()
    if not settings.elasticsearch_api_key and not settings.elasticsearch_password:
        raise RuntimeError("Elasticsearch credentials not configured")
    if not settings.kibana_api_key:
        raise RuntimeError("KIBANA_API_KEY not configured")

    # Generate first so the breach cache is populated when we render panels.
    docs_by_index = generate_documents()

    es = get_client()
    mappings = get_mappings()

    counts: Dict[str, int] = {}
    samples: Dict[str, Dict[str, Any]] = {}
    last_index = list(docs_by_index.keys())[-1]

    for index, docs in docs_by_index.items():
        if es.indices.exists(index=index):
            es.indices.delete(index=index)
        es.indices.create(index=index, body=mappings[index])
        actions = list(_to_bulk_actions(index, docs))
        refresh = "wait_for" if index == last_index else False
        success, errors = bulk(es, actions, chunk_size=500, refresh=refresh, raise_on_error=False)
        counts[index] = success
        if docs:
            samples[index] = docs[0]
        log.info("credstuff.indexed", index=index, count=success,
                 errors=len(errors) if isinstance(errors, list) else 0)

    # Refresh + create data view + dashboard.
    for index in counts:
        try:
            es.indices.refresh(index=index)
        except Exception:
            pass

    data_view_id = _create_data_view()
    # Auth-only data view used by the Lens panels. Idempotent. If it cannot be
    # created the dashboards still render via Vega fallback.
    lens_dv_id = _ensure_data_view()
    dashboard_ids = _create_dashboard(data_view_id, lens_data_view_id=lens_dv_id)

    fe_id = dashboard_ids.get("fe", DASHBOARD_ID)
    cu_id = dashboard_ids.get("customer", CUSTOMER_DASHBOARD_ID)

    return {
        "ok": True,
        "scenario": SCENARIO_ID,
        "indices": counts,
        "doc_count": sum(counts.values()),
        "data_view_id": data_view_id,
        "lens_data_view_id": lens_dv_id,
        "dashboard_id": fe_id,
        "dashboard_url": _dashboard_url(fe_id),
        "fe_dashboard_id": fe_id,
        "fe_dashboard_url": _dashboard_url(fe_id),
        "customer_dashboard_id": cu_id,
        "customer_dashboard_url": _dashboard_url(cu_id),
        "elapsed_seconds": round(time.time() - started, 2),
        "samples": samples,
        "breaches": get_breach_table(),
    }
