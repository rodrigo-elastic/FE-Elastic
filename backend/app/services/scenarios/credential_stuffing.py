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


# ----- Vega-Lite specs ---------------------------------------------------------------

def _vega_heatmap_country_hour() -> Dict[str, Any]:
    """Heatmap: failure count by hour-of-day x source country, restricted to attack
    period. Datacenter-country cells will dominate."""
    body = {
        "size": 0,
        "query": {
            "bool": {
                "filter": [
                    {"term": {"event.outcome": "failure"}},
                ]
            }
        },
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
    }
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": "Failed logins · hour x source country (attack windows light up)",
        "data": {
            "url": {
                "%context%": True,
                "%timefield%": "@timestamp",
                "index": INDEX_PATTERN,
                "body": body,
            },
            "format": {"property": "aggregations.by_country.buckets"},
        },
        "transform": [
            {"flatten": ["by_hour.buckets"], "as": ["hb"]},
            {"calculate": "datum.key", "as": "country"},
            {"calculate": "datum.hb.key", "as": "ts"},
            {"calculate": "hours(toDate(datum.hb.key))", "as": "hour_of_day"},
            {"calculate": "datum.hb.doc_count", "as": "failures"},
        ],
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
    """Top 10 source IPs by failure count, color-coded by suspicious-or-not."""
    body = {
        "size": 0,
        "query": {"bool": {"filter": [{"term": {"event.outcome": "failure"}}]}},
        "aggs": {
            "by_ip": {
                "terms": {"field": "source.ip", "size": 10},
                "aggs": {
                    "by_org": {"terms": {"field": "source.as.organization.name", "size": 1}},
                },
            }
        },
    }
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": "Top 10 source IPs by failed-login count",
        "data": {
            "url": {
                "%context%": True,
                "%timefield%": "@timestamp",
                "index": INDEX_PATTERN,
                "body": body,
            },
            "format": {"property": "aggregations.by_ip.buckets"},
        },
        "transform": [
            {"calculate": "datum.key", "as": "ip"},
            {"calculate": "datum.doc_count", "as": "failures"},
            {
                "calculate": "datum.by_org.buckets[0] ? datum.by_org.buckets[0].key : 'unknown'",
                "as": "as_org",
            },
            {
                "calculate": (
                    "indexof(['DigitalOcean LLC','Hetzner Online GmbH','OVH SAS',"
                    "'ANONYMIZED VPN PROVIDER'], datum.as_org) >= 0 ? 'attacker' : 'baseline'"
                ),
                "as": "classification",
            },
        ],
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
    """Two-line time series: success vs failure, with shaded bands over the two attack
    waves. The failure line is obviously anomalous in wave 2."""
    now = _now()
    # Wave 1: 2 days + 30 min ago, 30 min long.
    wave1_end = now - timedelta(seconds=2 * 24 * 3600)
    wave1_start = wave1_end - timedelta(minutes=30)
    # Wave 2: 6h 25min ago, 25 min long.
    wave2_end = now - timedelta(hours=6)
    wave2_start = wave2_end - timedelta(minutes=25)

    body = {
        "size": 0,
        "aggs": {
            "by_outcome": {
                "terms": {"field": "event.outcome", "size": 2},
                "aggs": {
                    "by_minute": {
                        "date_histogram": {
                            "field": "@timestamp",
                            "fixed_interval": "1m",
                            "min_doc_count": 0,
                        }
                    }
                },
            }
        },
    }
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": "Logins per minute - success vs failure (attack waves shaded)",
        "data": {
            "url": {
                "%context%": True,
                "%timefield%": "@timestamp",
                "index": INDEX_PATTERN,
                "body": body,
            },
            "format": {"property": "aggregations.by_outcome.buckets"},
        },
        "transform": [
            {"flatten": ["by_minute.buckets"], "as": ["mb"]},
            {"calculate": "datum.key", "as": "outcome"},
            {"calculate": "datum.mb.key", "as": "ts_ms"},
            {"calculate": "datum.mb.doc_count", "as": "count"},
        ],
        "layer": [
            {
                "data": {
                    "values": [
                        {
                            "wave_start": wave1_start.isoformat(),
                            "wave_end": wave1_end.isoformat(),
                            "label": "Wave 1 - low & slow recon",
                        },
                        {
                            "wave_start": wave2_start.isoformat(),
                            "wave_end": wave2_end.isoformat(),
                            "label": "Wave 2 - aggressive spike",
                        },
                    ]
                },
                "mark": {"type": "rect", "opacity": 0.18, "color": "#7e8794"},
                "encoding": {
                    "x": {"field": "wave_start", "type": "temporal"},
                    "x2": {"field": "wave_end"},
                    "tooltip": [{"field": "label", "type": "nominal"}],
                },
            },
            {
                "mark": {"type": "line", "interpolate": "monotone", "strokeWidth": 2},
                "encoding": {
                    "x": {
                        "field": "ts_ms", "type": "temporal", "title": "Time (UTC)",
                        "axis": {"labelColor": "#cdd", "titleColor": "#cdd"},
                    },
                    "y": {
                        "field": "count", "type": "quantitative", "title": "Logins / min",
                        "axis": {"labelColor": "#cdd", "titleColor": "#cdd"},
                    },
                    "color": {
                        "field": "outcome", "type": "nominal",
                        "scale": {"domain": ["success", "failure"], "range": ["#3fb27f", "#e8455d"]},
                        "title": "Outcome",
                        "legend": {"labelColor": "#cdd", "titleColor": "#cdd"},
                    },
                    "tooltip": [
                        {"field": "ts_ms", "type": "temporal", "title": "Minute"},
                        {"field": "outcome", "type": "nominal"},
                        {"field": "count", "type": "quantitative"},
                    ],
                },
            },
        ],
        "config": {"view": {"stroke": "transparent"}, "background": "transparent"},
    }


def _vega_asn_treemap() -> Dict[str, Any]:
    """Donut chart of failed-login source ASNs (the datacenter footprint becomes
    visually obvious). Vega-Lite arc with theta encoding."""
    body = {
        "size": 0,
        "query": {"bool": {"filter": [{"term": {"event.outcome": "failure"}}]}},
        "aggs": {
            "by_org": {"terms": {"field": "source.as.organization.name", "size": 12}},
        },
    }
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": "Source ASN distribution (failures only)",
        "data": {
            "url": {
                "%context%": True,
                "%timefield%": "@timestamp",
                "index": INDEX_PATTERN,
                "body": body,
            },
            "format": {"property": "aggregations.by_org.buckets"},
        },
        "transform": [
            {"calculate": "datum.key", "as": "as_org"},
            {"calculate": "datum.doc_count", "as": "failures"},
            {
                "calculate": (
                    "indexof(['DigitalOcean LLC','Hetzner Online GmbH','OVH SAS'], "
                    "datum.as_org) >= 0 ? 'datacenter' : "
                    "(datum.as_org == 'ANONYMIZED VPN PROVIDER' ? 'anonymizer' : 'legitimate')"
                ),
                "as": "kind",
            },
        ],
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


# ----- Markdown content --------------------------------------------------------------


def _md_header() -> str:
    return (
        "## Credential Stuffing Attack - SOC Playbook\n\n"
        "**MITRE: T1110.004 Credential Stuffing | TA0006 Credential Access**\n\n"
        "An attacker is burning through a leaked credential dump (~10k unique emails "
        "harvested from a 2024 breach of an unrelated SaaS) against `app.bigcorp.com`. "
        "Two waves observed:\n\n"
        "1. **Wave 1 - Low-and-slow recon (~2 days ago, 30 min):** ~50 attempts/min "
        "aggregate from 8 datacenter / VPN IPs. Pattern testing - mostly probing for "
        "valid usernames.\n"
        "2. **Wave 2 - Aggressive spike (~6 hours ago, 25 min):** thunder-herd from "
        "6 datacenter IPs. Peak ~60 attempts/min/IP; 4 confirmed account compromises "
        "with follow-on session creation + password reset attempts.\n\n"
        "**Elastic Security capabilities that catch this:**\n"
        "- ML auth jobs: `auth_high_count_logon_fails`, `auth_rare_source_ip_for_a_user`\n"
        "- Prebuilt detection rule: *Multiple Logon Failures from the Same Source*\n"
        "- Behavior Analytics: anomalous geo + ASN for known users\n"
        "- EQL hunt: `sequence by source.ip [authentication where event.outcome=='failure'] "
        "with maxspan=10m`\n"
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


def _md_mitre_narrative() -> str:
    return (
        "## MITRE ATT&CK Mapping & Elastic Countermeasures\n\n"
        "| MITRE | Stage | Elastic Security capability |\n"
        "| --- | --- | --- |\n"
        "| **[T1110.004](https://attack.mitre.org/techniques/T1110/004/) Credential Stuffing** "
        "| Initial pre-auth probing | ML job `auth_high_count_logon_fails` (anomaly detection on "
        "failure-rate per source.ip); prebuilt detection rule *Threat Intel IP* + *Multiple Logon "
        "Failures From the Same Source* |\n"
        "| **[T1078](https://attack.mitre.org/techniques/T1078/) Valid Accounts** "
        "| Post-breach session creation | Behavior Analytics anomalous-geo rule "
        "(`source.geo.country_iso_code` mismatch vs user's 30-day baseline); auto-create Case "
        "with affected user + IOC pivot |\n"
        "| **[T1556](https://attack.mitre.org/techniques/T1556/) Modify Authentication Process** "
        "| Attacker password-reset / MFA bypass | EQL rule chains successful login + "
        "`event.action:user-password-reset` from a non-trusted ASN within 10 min; Endpoint "
        "Integration auto-revokes session via response action |\n\n"
        "**SOC workflow:** Cases auto-bundles related alerts > Workflow agent escalates to "
        "Tier-2 > Endpoint integration revokes sessions for breached users + force-rotates "
        "MFA factors > IOCs (8 IPs, 4 ASNs) pushed to threat-intel index for blocklist."
    )


# ----- Panels assembly ---------------------------------------------------------------


def get_dashboard_panels() -> List[Dict[str, Any]]:
    """Returns 7 panels in the prescribed 48-wide grid layout."""
    breaches = get_breach_table()
    panels = []

    # Row 1: full-width markdown header (h=8)
    panels.append(_markdown_panel("p1", 0, 0, 48, 8, _md_header(),
                                  "Credential stuffing — incident overview"))

    # Row 2: heatmap left (24w, h=14) + top IPs right (24w, h=14)
    panels.append(_vega_panel("p2", 0, 8, 24, 14,
                              "Failures by hour x source country",
                              _vega_heatmap_country_hour()))
    panels.append(_vega_panel("p3", 24, 8, 24, 14,
                              "Top 10 source IPs by failures",
                              _vega_top_source_ips()))

    # Row 3: full-width line chart (48w, h=14)
    panels.append(_vega_panel("p4", 0, 22, 48, 14,
                              "Logins per minute - success vs failure",
                              _vega_logins_per_minute()))

    # Row 4: breach markdown table (24w, h=12) + ASN donut (24w, h=12)
    panels.append(_markdown_panel("p5", 0, 36, 24, 12, _md_breach_table(breaches),
                                  "Recent public breach corpus (HIBP-style)"))
    panels.append(_vega_panel("p6", 24, 36, 24, 12,
                              "Source ASN distribution (failures only)",
                              _vega_asn_treemap()))

    # Row 5: full-width MITRE narrative (48w, h=10)
    panels.append(_markdown_panel("p7", 0, 48, 48, 10, _md_mitre_narrative(),
                                  "MITRE ATT&CK mapping & Elastic detection"))

    return panels


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


def _dashboard_url() -> str:
    return settings.kibana_url.rstrip("/") + f"/app/dashboards#/view/{DASHBOARD_ID}"


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


def _create_dashboard(data_view_id: str) -> str:
    panels = get_dashboard_panels()
    panels_json = json.dumps(panels, ensure_ascii=False)
    options_json = json.dumps({
        "useMargins": True,
        "hidePanelTitles": False,
        "syncColors": True,
        "syncCursor": True,
        "syncTooltips": True,
    })
    search_source_json = json.dumps({"query": {"language": "kuery", "query": ""}, "filter": []})

    body = [{
        "id": DASHBOARD_ID,
        "type": "dashboard",
        "attributes": {
            "title": f"FE Copilot Demo · {SCENARIO_TITLE}",
            "description": SCENARIO_DESCRIPTION,
            "panelsJSON": panels_json,
            "optionsJSON": options_json,
            "timeRestore": True,
            "timeFrom": "now-3d",
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
        # Best-effort delete first for idempotency.
        try:
            client.delete(_kbn_url(f"/api/saved_objects/dashboard/{DASHBOARD_ID}"),
                          headers=_kbn_headers())
        except Exception:
            pass
        resp = client.post(
            _kbn_url("/api/saved_objects/_bulk_create?overwrite=true"),
            headers=_kbn_headers(), json=body,
        )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Kibana dashboard create failed: {resp.status_code} {resp.text[:400]}"
            )
    return DASHBOARD_ID


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
    dashboard_id = _create_dashboard(data_view_id)

    return {
        "ok": True,
        "scenario": SCENARIO_ID,
        "indices": counts,
        "doc_count": sum(counts.values()),
        "data_view_id": data_view_id,
        "dashboard_id": dashboard_id,
        "dashboard_url": _dashboard_url(),
        "elapsed_seconds": round(time.time() - started, 2),
        "samples": samples,
        "breaches": get_breach_table(),
    }
