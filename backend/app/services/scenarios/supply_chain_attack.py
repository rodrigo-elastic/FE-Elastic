"""
filename: supply_chain_attack.py
description: Demo Data Generator scenario - Supply Chain Attack (Dependency Confusion).

Builds a story-driven, ECS-aligned dataset that mirrors a real-world dependency
confusion attack against a fictional fintech, "Aurelius Pay". A malicious
package matching one of their internal scoped names was published to public
PyPI in week T minus 2. The first compromised CI runner pulled it on T minus 2
day 3. Over the next 9 days the implant phoned home, then in week T attempted
lateral movement: 4 internal services scanned, 2 service accounts had stolen
tokens, and 1 successful lateral hop landed on a staging Postgres.

MITRE techniques covered:
  - T1195.002 Compromise Software Supply Chain
  - T1078     Valid Accounts (token theft, post compromise reuse)
  - T1021     Remote Services (psql lateral hop)

Three indices, ~7600 docs total, plus FE and Customer dashboards (8 panels each)
with 6 inline-data Vega-Lite panels and 3 markdown panels.

Public interface (consumed by routes_demo_data and the seed CLI):

    SCENARIO_ID, SCENARIO_TITLE, SCENARIO_DESCRIPTION
    INDICES: Dict[str, str]
    DASHBOARD_ID: str
    get_mappings()      -> Dict[index_name, mapping_body]
    generate_documents(seed=20260504) -> Dict[index_name, List[doc]]
    get_dashboard_panels()            -> List[panel_dict]
    seed()                            -> Dict[str, Any]

date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import hashlib
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

SCENARIO_ID: str = "supply-chain-attack"
SCENARIO_TITLE: str = "Supply Chain Attack (Dependency Confusion)"
SCENARIOA_DESCRIPTION_PLACEHOLDER = None  # safe lint anchor (unused)
SCENARIO_DESCRIPTION: str = (
    "Aurelius Pay (fictional fintech) was hit with a dependency confusion attack. "
    "A malicious package matching an internal scoped name landed on public PyPI, was "
    "pulled by 4 CI runners, beaconed to a DuckDNS C2 for 9 days, then attempted "
    "lateral movement (host discovery, token theft, one successful psql hop to a "
    "staging Postgres). MITRE T1195.002, T1078, T1021 visible across CI, runtime, "
    "and Elastic Security alerts."
)

INDICES: Dict[str, str] = {
    "build": "demo-supplychain-build-events",
    "runtime": "demo-supplychain-runtime-events",
    "alerts": "demo-supplychain-mitre-alerts",
}

DASHBOARD_ID: str = "demo-supply-chain-attack-dashboard"
CUSTOMER_DASHBOARD_ID: str = "demo-supply-chain-attack-customer-dashboard"
INDEX_PATTERN: str = "demo-supplychain-*"


# ============================================================ Threat model =========

# The malicious package. "auriel-internal-utils" is the obvious tell: an Aurelius
# Pay engineer would recognise it as an internal scoped name (@aurelius/internal-utils
# in npm lingo, or aurelius_internal_utils in PyPI). Public PyPI does not enforce
# scoping, so the typo-squat sits next to the legitimate name.

MALICIOUS_PACKAGE = {
    "name": "auriel-internal-utils",
    "version": "9.99.7",
    "checksum": "sha256:" + hashlib.sha256(b"auriel-internal-utils@9.99.7").hexdigest(),
    "registry": "https://pypi.org/simple/",
    "first_published_iso": None,  # filled below at seed time relative to now
}

# The C2 callback. DuckDNS subdomains are a classic free-tier dynamic DNS abuse
# pattern. Beacon every 4 to 7 hours so we get ~30 to 50 outbound DNS hits in
# 9 days from each compromised runner.
C2_DOMAIN = "aureliuspay-tg.duckdns.org"
C2_DEST_IPS = ["185.199.108.42", "185.199.109.51"]

# 4 compromised CI runners. These are the only hosts that pulled the malicious
# package; everyone else has clean builds.
COMPROMISED_RUNNERS: List[Dict[str, Any]] = [
    {"host": "ci-runner-build-07", "host_id": "h-ci07-" + uuid.uuid5(uuid.NAMESPACE_OID, "ci07").hex[:8],
     "service": "github-actions-runner", "team": "platform-payments"},
    {"host": "ci-runner-build-12", "host_id": "h-ci12-" + uuid.uuid5(uuid.NAMESPACE_OID, "ci12").hex[:8],
     "service": "github-actions-runner", "team": "platform-payments"},
    {"host": "ci-runner-deploy-03", "host_id": "h-ci03d-" + uuid.uuid5(uuid.NAMESPACE_OID, "ci03d").hex[:8],
     "service": "github-actions-runner", "team": "platform-deploy"},
    {"host": "ci-runner-test-21", "host_id": "h-ci21t-" + uuid.uuid5(uuid.NAMESPACE_OID, "ci21t").hex[:8],
     "service": "github-actions-runner", "team": "qa-automation"},
]
# The runner that does the lateral movement (only 1 of the 4 actually pivots).
LATERAL_RUNNER_HOST = "ci-runner-deploy-03"

# Healthy fleet of CI runners (clean, used only for baseline build noise).
CLEAN_RUNNERS: List[Dict[str, Any]] = [
    {"host": f"ci-runner-build-{i:02d}", "host_id": "h-cib-" + uuid.uuid5(uuid.NAMESPACE_OID, f"cib{i}").hex[:8],
     "service": "github-actions-runner",
     "team": "platform-payments" if i % 2 == 0 else "platform-cards"}
    for i in range(1, 16) if i not in (7, 12)
]
CLEAN_RUNNERS += [
    {"host": f"ci-runner-test-{i:02d}", "host_id": "h-cit-" + uuid.uuid5(uuid.NAMESPACE_OID, f"cit{i}").hex[:8],
     "service": "github-actions-runner", "team": "qa-automation"}
    for i in range(1, 25) if i != 21
]
CLEAN_RUNNERS += [
    {"host": f"ci-runner-deploy-{i:02d}", "host_id": "h-cid-" + uuid.uuid5(uuid.NAMESPACE_OID, f"cid{i}").hex[:8],
     "service": "github-actions-runner", "team": "platform-deploy"}
    for i in range(1, 8) if i != 3
]

# Internal scan target subnet. nmap-style probe touches 4 specific IPs.
INTERNAL_SCAN_TARGETS: List[Dict[str, Any]] = [
    {"ip": "192.168.10.21", "service": "auth-internal-api", "port": 8443},
    {"ip": "192.168.10.34", "service": "billing-grpc", "port": 50051},
    {"ip": "192.168.10.57", "service": "fraud-feature-store", "port": 5432},
    {"ip": "192.168.10.88", "service": "staging-postgres", "port": 5432},
]
# The successful lateral hop lands on the staging Postgres.
LATERAL_HOP_TARGET = INTERNAL_SCAN_TARGETS[3]

# 2 service accounts whose tokens get stolen and replayed from anomalous IPs.
COMPROMISED_SERVICE_ACCOUNTS: List[Dict[str, Any]] = [
    {"user": "svc-deploy-bot", "role": "ci-deployer",
     "anomalous_ip": "ci-runner-deploy-03"},  # token replayed from the runner itself
    {"user": "svc-fraud-feature-reader", "role": "fraud-feature-reader",
     "anomalous_ip": "ci-runner-deploy-03"},
]

# Common Python packages that show up in clean CI builds (background noise).
CLEAN_PACKAGES: List[Tuple[str, str]] = [
    ("requests", "2.32.3"), ("urllib3", "2.2.2"), ("fastapi", "0.115.0"),
    ("pydantic", "2.9.2"), ("sqlalchemy", "2.0.36"), ("psycopg2-binary", "2.9.10"),
    ("elasticsearch", "9.0.0"), ("httpx", "0.27.2"), ("uvicorn", "0.32.0"),
    ("pytest", "8.3.3"), ("numpy", "2.1.3"), ("pandas", "2.2.3"),
    ("boto3", "1.35.50"), ("redis", "5.2.0"), ("kafka-python", "2.0.2"),
    ("structlog", "24.4.0"), ("orjson", "3.10.11"), ("black", "24.10.0"),
    ("mypy", "1.13.0"), ("ruff", "0.7.4"),
    # The legitimate package the attacker is squatting against.
    ("aurelius-internal-utils", "1.4.2"),
]

# 14-day attack window anchors (in days before "now"). The seeder uses these to
# place stage-marker timestamps deterministically.
STAGE_DAYS = {
    "publish_malicious": 11,         # T minus 11 days: package lands on public PyPI
    "first_pull": 9,                 # T minus 9 days: first CI runner pulls it
    "beacon_window_start": 9,        # beacons run for the next 9 days
    "scan_day": 2,                   # T minus 2: internal scan
    "token_theft_day": 1,            # T minus 1: tokens replayed
    "lateral_hop_day": 0.6,          # T minus 0.6: successful psql connection
}


# ============================================================ Time helpers =========

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ts(now: datetime, seconds_ago: float) -> str:
    return (now - timedelta(seconds=max(0.0, seconds_ago))).isoformat()


def _days_ago_seconds(days: float) -> float:
    return days * 24 * 3600


# ============================================================ Mappings =============

def get_mappings() -> Dict[str, Dict[str, Any]]:
    """ECS-aligned mappings for the three indices. Strict-typed time / IP / port
    fields, everything else dynamic so we can attach custom labels per stage."""
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
                "module": {"type": "keyword"},
            }
        },
        "host": {
            "properties": {
                "name": {"type": "keyword"},
                "id": {"type": "keyword"},
                "ip": {"type": "ip"},
            }
        },
        "process": {
            "properties": {
                "name": {"type": "keyword"},
                "command_line": {"type": "keyword",
                                 "fields": {"text": {"type": "text"}}},
                "pid": {"type": "long"},
                "parent": {"properties": {
                    "name": {"type": "keyword"},
                    "pid": {"type": "long"},
                }},
            }
        },
        "network": {
            "properties": {
                "direction": {"type": "keyword"},
                "transport": {"type": "keyword"},
                "protocol": {"type": "keyword"},
            }
        },
        "destination": {
            "properties": {
                "ip": {"type": "ip"},
                "port": {"type": "long"},
                "domain": {"type": "keyword"},
            }
        },
        "source": {
            "properties": {
                "ip": {"type": "ip"},
                "port": {"type": "long"},
            }
        },
        "package": {
            "properties": {
                "name": {"type": "keyword"},
                "version": {"type": "keyword"},
                "checksum": {"type": "keyword"},
                "type": {"type": "keyword"},
            }
        },
        "service": {
            "properties": {
                "name": {"type": "keyword"},
                "type": {"type": "keyword"},
            }
        },
        "user": {
            "properties": {
                "name": {"type": "keyword"},
                "id": {"type": "keyword"},
                "role": {"type": "keyword"},
            }
        },
        "threat": {
            "properties": {
                "framework": {"type": "keyword"},
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
        "labels": {"type": "object", "dynamic": True},
        "registry_url": {"type": "keyword"},
        "rule": {
            "properties": {
                "name": {"type": "keyword",
                          "fields": {"text": {"type": "text"}}},
                "severity": {"type": "keyword"},
                "risk_score": {"type": "long"},
            }
        },
        "signal": {
            "properties": {
                "status": {"type": "keyword"},
                "rule_name": {"type": "keyword"},
            }
        },
        "ci": {
            "properties": {
                "runner": {"type": "keyword"},
                "team": {"type": "keyword"},
                "pipeline_id": {"type": "keyword"},
                "job": {"type": "keyword"},
            }
        },
    }
    return {
        INDICES["build"]: {
            "mappings": {"dynamic": "true", "properties": base_dynamic_props}
        },
        INDICES["runtime"]: {
            "mappings": {"dynamic": "true", "properties": base_dynamic_props}
        },
        INDICES["alerts"]: {
            "mappings": {"dynamic": "true", "properties": base_dynamic_props}
        },
    }


# ============================================================ Generators ===========

def _build_event_doc(
    *,
    now: datetime,
    seconds_ago: float,
    runner: Dict[str, Any],
    package_name: str,
    package_version: str,
    package_checksum: str,
    outcome: str,
    is_malicious: bool,
    rng: random.Random,
) -> Dict[str, Any]:
    """A pip install event from a CI runner."""
    pipeline = "pl-" + uuid.uuid5(uuid.NAMESPACE_OID, runner["host"]).hex[:10]
    job = rng.choice(["build-image", "unit-tests", "integration-tests",
                      "deploy-staging", "package-wheel"])
    doc: Dict[str, Any] = {
        "@timestamp": _ts(now, seconds_ago),
        "ecs": {"version": "8.11.0"},
        "event": {
            "kind": "event",
            "category": ["package"],
            "type": ["installation"],
            "action": "package.install",
            "outcome": outcome,
            "dataset": "ci.package_install",
            "module": "ci-runner",
        },
        "host": {"name": runner["host"], "id": runner["host_id"]},
        "service": {"name": runner["service"], "type": "ci"},
        "ci": {
            "runner": runner["host"],
            "team": runner["team"],
            "pipeline_id": pipeline,
            "job": job,
        },
        "package": {
            "name": package_name,
            "version": package_version,
            "checksum": package_checksum,
            "type": "python-wheel",
        },
        "registry_url": "https://pypi.org/simple/",
        "process": {
            "name": "pip",
            "command_line": f"pip install {package_name}=={package_version}",
            "pid": rng.randint(1000, 65000),
            "parent": {"name": "bash", "pid": rng.randint(100, 999)},
        },
    }
    if is_malicious:
        doc["labels"] = {"supply_chain_stage": "initial-install",
                         "compromised": True}
        doc["threat"] = {
            "framework": "MITRE ATT&CK",
            "tactic": {"id": "TA0001", "name": "Initial Access"},
            "technique": {"id": "T1195.002",
                          "name": "Compromise Software Supply Chain"},
        }
    return doc


def _runtime_dns_beacon(
    *,
    now: datetime,
    seconds_ago: float,
    runner: Dict[str, Any],
    rng: random.Random,
) -> Dict[str, Any]:
    """Outbound DNS A-record query to the C2 domain."""
    dest_ip = rng.choice(C2_DEST_IPS)
    return {
        "@timestamp": _ts(now, seconds_ago),
        "ecs": {"version": "8.11.0"},
        "event": {
            "kind": "event",
            "category": ["network", "dns"],
            "type": ["connection", "protocol"],
            "action": "dns.query",
            "outcome": "success",
            "dataset": "endpoint.events.network",
            "module": "endpoint",
        },
        "host": {"name": runner["host"], "id": runner["host_id"]},
        "service": {"name": runner["service"], "type": "ci"},
        "process": {
            "name": "python3.11",
            "command_line": "python3.11 -c <auriel-internal-utils.implant>",
            "pid": rng.randint(1000, 65000),
            "parent": {"name": "pip", "pid": rng.randint(100, 999)},
        },
        "network": {"direction": "egress", "transport": "udp", "protocol": "dns"},
        "destination": {
            "ip": dest_ip,
            "port": 53,
            "domain": C2_DOMAIN,
        },
        "labels": {"supply_chain_stage": "c2-beacon", "compromised": True},
        "threat": {
            "framework": "MITRE ATT&CK",
            "tactic": {"id": "TA0011", "name": "Command and Control"},
            "technique": {"id": "T1071.004", "name": "Application Layer Protocol: DNS"},
        },
    }


def _runtime_internal_scan(
    *,
    now: datetime,
    seconds_ago: float,
    runner: Dict[str, Any],
    target: Dict[str, Any],
    rng: random.Random,
) -> Dict[str, Any]:
    """nmap-style internal probe."""
    return {
        "@timestamp": _ts(now, seconds_ago),
        "ecs": {"version": "8.11.0"},
        "event": {
            "kind": "event",
            "category": ["network", "host"],
            "type": ["info", "connection"],
            "action": "host.discovery",
            "outcome": rng.choice(["success", "success", "failure"]),
            "dataset": "endpoint.events.network",
            "module": "endpoint",
        },
        "host": {"name": runner["host"], "id": runner["host_id"]},
        "service": {"name": runner["service"], "type": "ci"},
        "process": {
            "name": "nmap",
            "command_line": f"nmap -sS -p {target['port']} {target['ip']}",
            "pid": rng.randint(1000, 65000),
            "parent": {"name": "bash", "pid": rng.randint(100, 999)},
        },
        "network": {"direction": "internal", "transport": "tcp", "protocol": "tcp"},
        "destination": {
            "ip": target["ip"],
            "port": target["port"],
            "domain": target["service"],
        },
        "labels": {"supply_chain_stage": "internal-scan", "compromised": True},
        "threat": {
            "framework": "MITRE ATT&CK",
            "tactic": {"id": "TA0007", "name": "Discovery"},
            "technique": {"id": "T1018",
                          "name": "Remote System Discovery"},
        },
    }


def _runtime_token_theft(
    *,
    now: datetime,
    seconds_ago: float,
    runner: Dict[str, Any],
    account: Dict[str, Any],
    rng: random.Random,
) -> Dict[str, Any]:
    """Service account token replayed from an anomalous source IP."""
    return {
        "@timestamp": _ts(now, seconds_ago),
        "ecs": {"version": "8.11.0"},
        "event": {
            "kind": "event",
            "category": ["authentication", "iam"],
            "type": ["info"],
            "action": "auth.token_theft",
            "outcome": "success",
            "dataset": "iam.token_replay",
            "module": "iam",
        },
        "host": {"name": runner["host"], "id": runner["host_id"]},
        "user": {
            "name": account["user"],
            "id": "svc-" + uuid.uuid5(uuid.NAMESPACE_OID, account["user"]).hex[:10],
            "role": account["role"],
        },
        "process": {
            "name": "python3.11",
            "command_line": (
                f"python3.11 -c \"import os; "
                f"os.environ.get('AWS_SECRET_ACCESS_KEY')\""
            ),
            "pid": rng.randint(1000, 65000),
            "parent": {"name": "pip", "pid": rng.randint(100, 999)},
        },
        "labels": {"supply_chain_stage": "token-theft", "compromised": True},
        "threat": {
            "framework": "MITRE ATT&CK",
            "tactic": {"id": "TA0006", "name": "Credential Access"},
            "technique": {"id": "T1552.001",
                          "name": "Credentials In Files"},
        },
    }


def _runtime_lateral_hop(
    *,
    now: datetime,
    seconds_ago: float,
    runner: Dict[str, Any],
    target: Dict[str, Any],
    account: Dict[str, Any],
    rng: random.Random,
    outcome: str = "success",
) -> Dict[str, Any]:
    """Successful psql connection from the runner to the staging Postgres."""
    return {
        "@timestamp": _ts(now, seconds_ago),
        "ecs": {"version": "8.11.0"},
        "event": {
            "kind": "event",
            "category": ["network", "database"],
            "type": ["connection", "start"],
            "action": "remote.service.connect",
            "outcome": outcome,
            "dataset": "endpoint.events.network",
            "module": "endpoint",
        },
        "host": {"name": runner["host"], "id": runner["host_id"]},
        "user": {
            "name": account["user"],
            "id": "svc-" + uuid.uuid5(uuid.NAMESPACE_OID, account["user"]).hex[:10],
            "role": account["role"],
        },
        "process": {
            "name": "psql",
            "command_line": (
                f"psql -h {target['ip']} -p {target['port']} "
                f"-U {account['user']} -d staging_payments"
            ),
            "pid": rng.randint(1000, 65000),
            "parent": {"name": "bash", "pid": rng.randint(100, 999)},
        },
        "network": {"direction": "internal", "transport": "tcp", "protocol": "postgres"},
        "destination": {
            "ip": target["ip"],
            "port": target["port"],
            "domain": target["service"],
        },
        "labels": {"supply_chain_stage": "lateral-hop", "compromised": True,
                   "successful_hop": outcome == "success"},
        "threat": {
            "framework": "MITRE ATT&CK",
            "tactic": {"id": "TA0008", "name": "Lateral Movement"},
            "technique": {"id": "T1021",
                          "name": "Remote Services"},
        },
    }


def _baseline_runtime_event(
    *,
    now: datetime,
    seconds_ago: float,
    runner: Dict[str, Any],
    rng: random.Random,
) -> Dict[str, Any]:
    """Random baseline runtime telemetry: clean DNS, clean process spawn, clean
    egress to whitelisted services. Adds noise so the dashboards do not look
    artificially clean."""
    kind = rng.choice(["dns_clean", "egress_clean", "proc_clean"])
    if kind == "dns_clean":
        domain = rng.choice([
            "pypi.org", "files.pythonhosted.org", "registry.npmjs.org",
            "github.com", "ghcr.io", "api.github.com", "deb.debian.org",
        ])
        return {
            "@timestamp": _ts(now, seconds_ago),
            "ecs": {"version": "8.11.0"},
            "event": {"kind": "event", "category": ["network", "dns"],
                      "type": ["connection"], "action": "dns.query",
                      "outcome": "success", "dataset": "endpoint.events.network",
                      "module": "endpoint"},
            "host": {"name": runner["host"], "id": runner["host_id"]},
            "service": {"name": runner["service"], "type": "ci"},
            "process": {"name": "pip", "command_line": "pip install --quiet",
                        "pid": rng.randint(1000, 65000),
                        "parent": {"name": "bash", "pid": rng.randint(100, 999)}},
            "network": {"direction": "egress", "transport": "udp", "protocol": "dns"},
            "destination": {"domain": domain, "port": 53,
                            "ip": f"140.82.{rng.randint(1, 254)}.{rng.randint(1, 254)}"},
            "labels": {"supply_chain_stage": "baseline"},
        }
    if kind == "egress_clean":
        return {
            "@timestamp": _ts(now, seconds_ago),
            "ecs": {"version": "8.11.0"},
            "event": {"kind": "event", "category": ["network"],
                      "type": ["connection"], "action": "network.connection",
                      "outcome": "success", "dataset": "endpoint.events.network",
                      "module": "endpoint"},
            "host": {"name": runner["host"], "id": runner["host_id"]},
            "service": {"name": runner["service"], "type": "ci"},
            "process": {"name": rng.choice(["docker", "git", "curl", "gh"]),
                        "command_line": rng.choice([
                            "docker push registry.aureliuspay.internal/api:latest",
                            "git fetch origin",
                            "curl -fsSL https://github.com/aureliuspay/api",
                            "gh release create v1.42.0",
                        ]),
                        "pid": rng.randint(1000, 65000),
                        "parent": {"name": "bash", "pid": rng.randint(100, 999)}},
            "network": {"direction": "egress", "transport": "tcp", "protocol": "https"},
            "destination": {"domain": "registry.aureliuspay.internal",
                            "ip": f"10.0.{rng.randint(0, 5)}.{rng.randint(1, 254)}",
                            "port": 443},
            "labels": {"supply_chain_stage": "baseline"},
        }
    # proc_clean
    return {
        "@timestamp": _ts(now, seconds_ago),
        "ecs": {"version": "8.11.0"},
        "event": {"kind": "event", "category": ["process"],
                  "type": ["start"], "action": "process.start",
                  "outcome": "success", "dataset": "endpoint.events.process",
                  "module": "endpoint"},
        "host": {"name": runner["host"], "id": runner["host_id"]},
        "service": {"name": runner["service"], "type": "ci"},
        "process": {"name": rng.choice(["pytest", "ruff", "black", "mypy", "uvicorn"]),
                    "command_line": rng.choice([
                        "pytest -q tests/",
                        "ruff check src/",
                        "black --check src/",
                        "mypy --strict app/",
                        "uvicorn app.main:app --port 8000",
                    ]),
                    "pid": rng.randint(1000, 65000),
                    "parent": {"name": "bash", "pid": rng.randint(100, 999)}},
        "labels": {"supply_chain_stage": "baseline"},
    }


def _alert_doc(
    *,
    now: datetime,
    seconds_ago: float,
    rule_name: str,
    technique_id: str,
    technique_name: str,
    tactic_id: str,
    tactic_name: str,
    runner: Dict[str, Any],
    severity: str,
    risk_score: int,
    description: str,
    rng: random.Random,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Elastic Security alert mapped to a MITRE technique."""
    doc: Dict[str, Any] = {
        "@timestamp": _ts(now, seconds_ago),
        "ecs": {"version": "8.11.0"},
        "event": {
            "kind": "alert",
            "category": ["intrusion_detection"],
            "type": ["info"],
            "action": "security.alert",
            "outcome": "success",
            "dataset": "siem.signals",
            "module": "siem",
        },
        "host": {"name": runner["host"], "id": runner["host_id"]},
        "service": {"name": runner["service"], "type": "ci"},
        "rule": {"name": rule_name, "severity": severity, "risk_score": risk_score},
        "signal": {"status": "open", "rule_name": rule_name},
        "message": description,
        "threat": {
            "framework": "MITRE ATT&CK",
            "tactic": {"id": tactic_id, "name": tactic_name},
            "technique": {"id": technique_id, "name": technique_name},
        },
        "labels": {"supply_chain_alert": True},
    }
    if extra:
        for k, v in extra.items():
            doc[k] = v
    return doc


# ============================================================ Master generator =====

def generate_documents(seed: int = 20260504) -> Dict[str, List[Dict[str, Any]]]:
    """Generate all documents for the scenario, deterministic with `seed`."""
    rng = random.Random(seed)
    now = _now()

    build_docs: List[Dict[str, Any]] = []
    runtime_docs: List[Dict[str, Any]] = []
    alert_docs: List[Dict[str, Any]] = []

    # ---------- Build events: ~3000 install logs spread across ~14 days. -----
    # Of these, exactly the first malicious-pull events live on the 4
    # compromised runners, on T minus 9 day-boundary (with small jitter).

    # Background clean installs (clean fleet): ~2700 events.
    for _ in range(2700):
        runner = rng.choice(CLEAN_RUNNERS)
        pkg_name, pkg_ver = rng.choice(CLEAN_PACKAGES)
        seconds_ago = rng.uniform(60, 14 * 24 * 3600)
        checksum = "sha256:" + hashlib.sha256(
            f"{pkg_name}@{pkg_ver}".encode("utf-8")
        ).hexdigest()
        build_docs.append(_build_event_doc(
            now=now, seconds_ago=seconds_ago, runner=runner,
            package_name=pkg_name, package_version=pkg_ver,
            package_checksum=checksum,
            outcome=rng.choice(["success"] * 19 + ["failure"]),
            is_malicious=False, rng=rng,
        ))

    # Compromised runners also do clean installs (the malicious one is just one
    # entry among many); ~70 clean installs per compromised runner.
    for runner in COMPROMISED_RUNNERS:
        for _ in range(70):
            pkg_name, pkg_ver = rng.choice(CLEAN_PACKAGES)
            seconds_ago = rng.uniform(60, 14 * 24 * 3600)
            checksum = "sha256:" + hashlib.sha256(
                f"{pkg_name}@{pkg_ver}".encode("utf-8")
            ).hexdigest()
            build_docs.append(_build_event_doc(
                now=now, seconds_ago=seconds_ago, runner=runner,
                package_name=pkg_name, package_version=pkg_ver,
                package_checksum=checksum,
                outcome="success", is_malicious=False, rng=rng,
            ))

    # The malicious package install (one record per compromised runner, day T-9
    # with small jitter so they cluster but don't overlap exactly).
    for i, runner in enumerate(COMPROMISED_RUNNERS):
        seconds_ago = _days_ago_seconds(STAGE_DAYS["first_pull"]) + rng.uniform(
            -2 * 3600, 6 * 3600 + i * 1800
        )
        build_docs.append(_build_event_doc(
            now=now, seconds_ago=seconds_ago, runner=runner,
            package_name=MALICIOUS_PACKAGE["name"],
            package_version=MALICIOUS_PACKAGE["version"],
            package_checksum=MALICIOUS_PACKAGE["checksum"],
            outcome="success", is_malicious=True, rng=rng,
        ))

    # ---------- Runtime events: ~4500 docs (beacons, scans, theft, baseline). --

    # C2 beacons: every 4 to 7 hours from each compromised runner over 9 days.
    for runner in COMPROMISED_RUNNERS:
        t_remaining = _days_ago_seconds(STAGE_DAYS["beacon_window_start"])
        # Walk forward in time by sampling beacon intervals until we reach now.
        while t_remaining > 60:
            interval = rng.uniform(4 * 3600, 7 * 3600)
            t_remaining -= interval
            if t_remaining < 60:
                break
            runtime_docs.append(_runtime_dns_beacon(
                now=now, seconds_ago=t_remaining, runner=runner, rng=rng,
            ))

    # Internal scan: 6 probes total (the brief mentions 4 internal IPs scanned
    # plus 2 retry attempts) from the lateral runner, on T-2.
    lateral_runner = next(r for r in COMPROMISED_RUNNERS
                          if r["host"] == LATERAL_RUNNER_HOST)
    scan_base = _days_ago_seconds(STAGE_DAYS["scan_day"])
    for j, target in enumerate(INTERNAL_SCAN_TARGETS):
        runtime_docs.append(_runtime_internal_scan(
            now=now, seconds_ago=scan_base - j * 90, runner=lateral_runner,
            target=target, rng=rng,
        ))
    # 2 retry probes against the staging Postgres (port closed/filtered first).
    for k in range(2):
        runtime_docs.append(_runtime_internal_scan(
            now=now, seconds_ago=scan_base - 4 * 90 - k * 120,
            runner=lateral_runner, target=LATERAL_HOP_TARGET, rng=rng,
        ))

    # Token theft: 2 events on T minus 1 (one per compromised service account).
    theft_base = _days_ago_seconds(STAGE_DAYS["token_theft_day"])
    for k, account in enumerate(COMPROMISED_SERVICE_ACCOUNTS):
        runtime_docs.append(_runtime_token_theft(
            now=now, seconds_ago=theft_base - k * 1800,
            runner=lateral_runner, account=account, rng=rng,
        ))

    # Lateral hop: 6 attempts total (5 failed, 1 successful) on T minus 0.6.
    lateral_base = _days_ago_seconds(STAGE_DAYS["lateral_hop_day"])
    failed_attempts = 5
    for k in range(failed_attempts):
        runtime_docs.append(_runtime_lateral_hop(
            now=now, seconds_ago=lateral_base + k * 60,
            runner=lateral_runner, target=LATERAL_HOP_TARGET,
            account=COMPROMISED_SERVICE_ACCOUNTS[0], rng=rng, outcome="failure",
        ))
    # The single successful hop.
    runtime_docs.append(_runtime_lateral_hop(
        now=now, seconds_ago=lateral_base - 30,
        runner=lateral_runner, target=LATERAL_HOP_TARGET,
        account=COMPROMISED_SERVICE_ACCOUNTS[0], rng=rng, outcome="success",
    ))

    # Baseline runtime telemetry: ~4000 events across all runners (clean fleet
    # plus compromised runners doing normal work).
    all_runners = COMPROMISED_RUNNERS + CLEAN_RUNNERS
    for _ in range(4000):
        runner = rng.choice(all_runners)
        seconds_ago = rng.uniform(60, 14 * 24 * 3600)
        runtime_docs.append(_baseline_runtime_event(
            now=now, seconds_ago=seconds_ago, runner=runner, rng=rng,
        ))

    # ---------- MITRE alert docs: ~120 alerts. --------------------------------
    # Heaviest weight on T1195.002 (the original supply-chain technique), the
    # one a SOC analyst should immediately see dominate the bar chart.

    # T1195.002 alerts: 70 (the dependency-confusion install fires repeated
    # signals as the implant boots, persists, and is re-detected by the EDR).
    for k in range(70):
        runner = COMPROMISED_RUNNERS[k % len(COMPROMISED_RUNNERS)]
        seconds_ago = _days_ago_seconds(STAGE_DAYS["first_pull"]) - rng.uniform(
            -3 * 3600, 9 * 24 * 3600
        )
        alert_docs.append(_alert_doc(
            now=now, seconds_ago=max(60.0, seconds_ago),
            rule_name="Suspicious Package Installed From Public Registry "
                      "Matching Internal Scope",
            technique_id="T1195.002",
            technique_name="Compromise Software Supply Chain",
            tactic_id="TA0001", tactic_name="Initial Access",
            runner=runner, severity="critical", risk_score=92,
            description=(
                f"Runner {runner['host']} pulled "
                f"{MALICIOUS_PACKAGE['name']}=={MALICIOUS_PACKAGE['version']} from "
                f"public PyPI; checksum does not match the internal Artifactory "
                f"mirror. Downstream beacons to {C2_DOMAIN} confirmed."
            ),
            extra={"package": {"name": MALICIOUS_PACKAGE["name"],
                               "version": MALICIOUS_PACKAGE["version"],
                               "checksum": MALICIOUS_PACKAGE["checksum"]}},
            rng=rng,
        ))

    # T1071.004 (DNS C2) alerts: 24 (one per beacon-cluster anomaly).
    for k in range(24):
        runner = COMPROMISED_RUNNERS[k % len(COMPROMISED_RUNNERS)]
        seconds_ago = rng.uniform(
            60, _days_ago_seconds(STAGE_DAYS["beacon_window_start"])
        )
        alert_docs.append(_alert_doc(
            now=now, seconds_ago=seconds_ago,
            rule_name="Periodic DNS Query To Newly Observed Domain",
            technique_id="T1071.004",
            technique_name="Application Layer Protocol: DNS",
            tactic_id="TA0011", tactic_name="Command and Control",
            runner=runner, severity="high", risk_score=78,
            description=(
                f"Runner {runner['host']} is beaconing to "
                f"{C2_DOMAIN} on a regular cadence (every 4 to 7 hours). "
                f"Domain age under 30 days; DuckDNS dynamic DNS provider."
            ),
            extra={"destination": {"domain": C2_DOMAIN,
                                    "ip": rng.choice(C2_DEST_IPS),
                                    "port": 53}},
            rng=rng,
        ))

    # T1018 (Remote System Discovery) alerts: 6 (one per scan probe).
    for k in range(6):
        seconds_ago = scan_base - k * 90
        target = INTERNAL_SCAN_TARGETS[k % len(INTERNAL_SCAN_TARGETS)]
        alert_docs.append(_alert_doc(
            now=now, seconds_ago=seconds_ago,
            rule_name="Network Sweep Of Internal Subnet From CI Runner",
            technique_id="T1018",
            technique_name="Remote System Discovery",
            tactic_id="TA0007", tactic_name="Discovery",
            runner=lateral_runner, severity="high", risk_score=73,
            description=(
                f"Runner {lateral_runner['host']} scanned "
                f"{target['ip']}:{target['port']} ({target['service']}). "
                f"CI runners do not normally probe internal data services."
            ),
            extra={"destination": {"ip": target["ip"],
                                    "port": target["port"],
                                    "domain": target["service"]}},
            rng=rng,
        ))

    # T1552.001 / T1078 (Valid Accounts via stolen tokens) alerts: 8.
    for k in range(8):
        account = COMPROMISED_SERVICE_ACCOUNTS[k % len(COMPROMISED_SERVICE_ACCOUNTS)]
        seconds_ago = theft_base - k * 1800
        alert_docs.append(_alert_doc(
            now=now, seconds_ago=seconds_ago,
            rule_name="Service Account Token Replayed From Anomalous Source",
            technique_id="T1078",
            technique_name="Valid Accounts",
            tactic_id="TA0001", tactic_name="Initial Access",
            runner=lateral_runner, severity="critical", risk_score=88,
            description=(
                f"Service account {account['user']} (role {account['role']}) "
                f"authenticated from {lateral_runner['host']}, which is not "
                f"in its 30-day allow-list. Token issued 6 hours earlier from "
                f"its expected origin."
            ),
            extra={"user": {"name": account["user"], "role": account["role"]}},
            rng=rng,
        ))

    # T1021 (Remote Services / lateral hop) alerts: 12.
    for k in range(12):
        seconds_ago = lateral_base + (k - 6) * 60
        outcome_label = "successful" if k == 0 else "attempted"
        alert_docs.append(_alert_doc(
            now=now, seconds_ago=max(60.0, seconds_ago),
            rule_name=f"CI Runner Made {outcome_label.title()} Postgres "
                      f"Connection To Staging Data Service",
            technique_id="T1021",
            technique_name="Remote Services",
            tactic_id="TA0008", tactic_name="Lateral Movement",
            runner=lateral_runner, severity="critical", risk_score=95,
            description=(
                f"Runner {lateral_runner['host']} initiated a "
                f"{outcome_label} psql session against "
                f"{LATERAL_HOP_TARGET['ip']}:{LATERAL_HOP_TARGET['port']} "
                f"({LATERAL_HOP_TARGET['service']}). This runner has no "
                f"prior connection history to data-tier services."
            ),
            extra={"destination": {"ip": LATERAL_HOP_TARGET["ip"],
                                    "port": LATERAL_HOP_TARGET["port"],
                                    "domain": LATERAL_HOP_TARGET["service"]},
                   "user": {"name": COMPROMISED_SERVICE_ACCOUNTS[0]["user"]}},
            rng=rng,
        ))

    rng.shuffle(build_docs)
    rng.shuffle(runtime_docs)
    rng.shuffle(alert_docs)

    return {
        INDICES["build"]: build_docs,
        INDICES["runtime"]: runtime_docs,
        INDICES["alerts"]: alert_docs,
    }


# ============================================================ Dashboard panels =====


def _markdown_panel(panel_id: str, x: int, y: int, w: int, h: int, markdown: str,
                    title: str = "") -> Dict[str, Any]:
    """Markdown panel wrapped as a legacy `visualization` embeddable so Kibana
    9.x renders it the same way as a Vega panel."""
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
                "params": {"fontSize": 12, "openLinksInNewTab": True,
                           "markdown": markdown},
                "uiState": {},
                "data": {
                    "aggs": [],
                    "searchSource": {"query": {"language": "kuery", "query": ""},
                                       "filter": []},
                },
            },
        },
        "title": title,
    }


def _vega_panel(panel_id: str, x: int, y: int, w: int, h: int, title: str,
                spec: Dict[str, Any]) -> Dict[str, Any]:
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
                    "searchSource": {"query": {"language": "kuery", "query": ""},
                                       "filter": []},
                },
            },
        },
        "title": title,
    }


# ----- Vega-Lite specs (inline data) ------------------------------------------------


def _vega_alerts_by_technique() -> Dict[str, Any]:
    """Bar chart of alert counts by MITRE technique id. T1195.002 dominates."""
    values: List[Dict[str, Any]] = []
    try:
        es = get_client()
        r = es.search(index=INDICES["alerts"], body={
            "size": 0,
            "query": {"bool": {"filter": [
                {"range": {"@timestamp": {"gte": "now-14d", "lte": "now"}}},
            ]}},
            "aggs": {
                "by_tech": {
                    "terms": {"field": "threat.technique.id", "size": 20},
                    "aggs": {
                        "tech_name": {"terms": {"field": "threat.technique.name",
                                                  "size": 1}},
                    },
                }
            },
        })
        for b in r["aggregations"]["by_tech"]["buckets"]:
            tech_id = b["key"]
            name_buckets = b.get("tech_name", {}).get("buckets") or []
            tech_name = name_buckets[0]["key"] if name_buckets else ""
            values.append({
                "technique_id": tech_id,
                "technique_name": tech_name,
                "label": f"{tech_id} {tech_name}",
                "alerts": int(b.get("doc_count") or 0),
            })
    except Exception as exc:
        log.warning("supplychain.spec_techniques.compute.failed", error=str(exc))

    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": "Alerts by MITRE technique (14d window)",
        "data": {"values": values},
        "mark": {"type": "bar", "tooltip": True, "cornerRadiusEnd": 3},
        "encoding": {
            "y": {
                "field": "label", "type": "nominal", "sort": "-x",
                "title": "MITRE technique",
                "axis": {"labelColor": "#cdd", "titleColor": "#cdd",
                          "labelLimit": 320},
            },
            "x": {
                "field": "alerts", "type": "quantitative", "title": "Alert count",
                "axis": {"labelColor": "#cdd", "titleColor": "#cdd"},
            },
            "color": {
                "field": "technique_id", "type": "nominal",
                "scale": {
                    "domain": ["T1195.002", "T1078", "T1021", "T1071.004", "T1018"],
                    "range": ["#e8455d", "#f0a830", "#a14bd2", "#7e8794", "#5b8bbd"],
                },
                "title": "Technique",
                "legend": {"labelColor": "#cdd", "titleColor": "#cdd"},
            },
            "tooltip": [
                {"field": "technique_id", "type": "nominal"},
                {"field": "technique_name", "type": "nominal"},
                {"field": "alerts", "type": "quantitative"},
            ],
        },
        "config": {"view": {"stroke": "transparent"}, "background": "transparent"},
    }


def _vega_attack_timeline() -> Dict[str, Any]:
    """14-day timeline with each attack stage as a colored band on a single
    horizontal track. Inline data is computed from the known stage anchors."""
    now = _now()

    def t(days_ago: float) -> str:
        return (now - timedelta(seconds=_days_ago_seconds(days_ago))).isoformat()

    bands = [
        {"stage": "1. Malicious package published",
         "start": t(11.2), "end": t(11.0), "stage_id": "publish",
         "color_key": "publish"},
        {"stage": "2. First CI runner pulls package",
         "start": t(9.3), "end": t(9.0), "stage_id": "first-pull",
         "color_key": "first-pull"},
        {"stage": "3. C2 beacons every 4 to 7 hours",
         "start": t(9.0), "end": t(2.5), "stage_id": "beacon",
         "color_key": "beacon"},
        {"stage": "4. Internal scan from compromised runner",
         "start": t(2.1), "end": t(1.95), "stage_id": "scan",
         "color_key": "scan"},
        {"stage": "5. Service account token theft",
         "start": t(1.1), "end": t(0.95), "stage_id": "token-theft",
         "color_key": "token-theft"},
        {"stage": "6. Successful psql lateral hop",
         "start": t(0.62), "end": t(0.58), "stage_id": "lateral-hop",
         "color_key": "lateral-hop"},
    ]

    # Pull alert event points so the timeline shows the alerts laying on top of
    # the stage bands.
    alert_points: List[Dict[str, Any]] = []
    try:
        es = get_client()
        r = es.search(index=INDICES["alerts"], body={
            "size": 0,
            "query": {"range": {"@timestamp": {"gte": "now-14d", "lte": "now"}}},
            "aggs": {
                "by_tech": {
                    "terms": {"field": "threat.technique.id", "size": 10},
                    "aggs": {
                        "by_hour": {
                            "date_histogram": {
                                "field": "@timestamp",
                                "fixed_interval": "3h",
                                "min_doc_count": 1,
                            }
                        }
                    },
                },
            },
        })
        for tb in r["aggregations"]["by_tech"]["buckets"]:
            tech_id = tb["key"]
            for hb in tb["by_hour"]["buckets"]:
                ts = hb.get("key_as_string") or hb.get("key")
                alert_points.append({
                    "ts": ts,
                    "technique_id": tech_id,
                    "alerts": int(hb.get("doc_count") or 0),
                })
    except Exception as exc:
        log.warning("supplychain.spec_timeline.compute.failed", error=str(exc))

    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": "14 day attack timeline (stages + alert points)",
        "layer": [
            {
                "data": {"values": bands},
                "mark": {"type": "rect", "opacity": 0.45},
                "encoding": {
                    "x": {"field": "start", "type": "temporal",
                          "axis": {"labelColor": "#cdd", "titleColor": "#cdd",
                                    "title": "Time (UTC)"}},
                    "x2": {"field": "end"},
                    "y": {"field": "stage", "type": "nominal", "sort": [
                              "1. Malicious package published",
                              "2. First CI runner pulls package",
                              "3. C2 beacons every 4 to 7 hours",
                              "4. Internal scan from compromised runner",
                              "5. Service account token theft",
                              "6. Successful psql lateral hop",
                          ],
                          "title": "Stage",
                          "axis": {"labelColor": "#cdd", "titleColor": "#cdd",
                                    "labelLimit": 380}},
                    "color": {
                        "field": "color_key", "type": "nominal",
                        "scale": {
                            "domain": ["publish", "first-pull", "beacon",
                                       "scan", "token-theft", "lateral-hop"],
                            "range": ["#a14bd2", "#e8455d", "#f0a830",
                                      "#5b8bbd", "#3fb27f", "#e8455d"],
                        },
                        "legend": {"labelColor": "#cdd", "titleColor": "#cdd",
                                    "title": "Stage"},
                    },
                    "tooltip": [
                        {"field": "stage", "type": "nominal"},
                        {"field": "start", "type": "temporal", "title": "From"},
                        {"field": "end", "type": "temporal", "title": "To"},
                    ],
                },
            },
            {
                "data": {"values": alert_points},
                "mark": {"type": "circle", "opacity": 0.75,
                         "stroke": "#1a1d24", "strokeWidth": 0.5},
                "encoding": {
                    "x": {"field": "ts", "type": "temporal"},
                    "y": {"value": 0},
                    "size": {"field": "alerts", "type": "quantitative",
                              "title": "Alerts in 3h",
                              "legend": {"labelColor": "#cdd",
                                          "titleColor": "#cdd"}},
                    "color": {"value": "#cdd"},
                    "tooltip": [
                        {"field": "ts", "type": "temporal"},
                        {"field": "technique_id", "type": "nominal"},
                        {"field": "alerts", "type": "quantitative"},
                    ],
                },
            },
        ],
        "config": {"view": {"stroke": "transparent"}, "background": "transparent"},
    }


def _vega_top_compromised_hosts() -> Dict[str, Any]:
    """Bar chart of host.name by alert count - the 4 compromised runners pop."""
    values: List[Dict[str, Any]] = []
    try:
        es = get_client()
        r = es.search(index=INDICES["alerts"], body={
            "size": 0,
            "query": {"range": {"@timestamp": {"gte": "now-14d", "lte": "now"}}},
            "aggs": {
                "by_host": {
                    "terms": {"field": "host.name", "size": 10},
                    "aggs": {
                        "tech_count": {
                            "cardinality": {"field": "threat.technique.id"},
                        },
                    },
                },
            },
        })
        for b in r["aggregations"]["by_host"]["buckets"]:
            host = b["key"]
            classification = ("compromised"
                              if host in {r["host"] for r in COMPROMISED_RUNNERS}
                              else "baseline")
            values.append({
                "host": host,
                "alerts": int(b.get("doc_count") or 0),
                "techniques": int(b.get("tech_count", {}).get("value") or 0),
                "classification": classification,
            })
    except Exception as exc:
        log.warning("supplychain.spec_top_hosts.compute.failed", error=str(exc))

    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": "Top hosts by alert count (compromised runners highlighted)",
        "data": {"values": values},
        "mark": {"type": "bar", "tooltip": True, "cornerRadiusEnd": 3},
        "encoding": {
            "y": {
                "field": "host", "type": "nominal", "sort": "-x",
                "title": "Host",
                "axis": {"labelColor": "#cdd", "titleColor": "#cdd",
                          "labelLimit": 240},
            },
            "x": {
                "field": "alerts", "type": "quantitative", "title": "Alert count",
                "axis": {"labelColor": "#cdd", "titleColor": "#cdd"},
            },
            "color": {
                "field": "classification", "type": "nominal",
                "scale": {
                    "domain": ["compromised", "baseline"],
                    "range": ["#e8455d", "#5b8bbd"],
                },
                "legend": {"labelColor": "#cdd", "titleColor": "#cdd",
                            "title": "Classification"},
            },
            "tooltip": [
                {"field": "host", "type": "nominal"},
                {"field": "alerts", "type": "quantitative"},
                {"field": "techniques", "type": "quantitative",
                 "title": "Distinct techniques"},
                {"field": "classification", "type": "nominal"},
            ],
        },
        "config": {"view": {"stroke": "transparent"}, "background": "transparent"},
    }


def _vega_attack_graph() -> Dict[str, Any]:
    """Node + edge layout: C2 domain to compromised CI runners to internal scan
    targets. Implemented as a Vega-Lite layered chart with manually placed
    coordinates so it renders without a graph engine."""
    # Three columns of nodes: x=0 (C2), x=1 (CI runners), x=2 (internal targets).
    nodes: List[Dict[str, Any]] = [
        {"id": C2_DOMAIN, "label": C2_DOMAIN, "x": 0, "y": 2, "kind": "c2"},
    ]
    runner_y = [0, 1.3, 2.6, 3.9]
    for i, r in enumerate(COMPROMISED_RUNNERS):
        nodes.append({"id": r["host"], "label": r["host"],
                      "x": 1, "y": runner_y[i], "kind": "runner"})
    target_y = [0.2, 1.6, 3.0, 4.4]
    for i, tgt in enumerate(INTERNAL_SCAN_TARGETS):
        kind = ("hop-target"
                if tgt["ip"] == LATERAL_HOP_TARGET["ip"] else "scan-target")
        nodes.append({"id": tgt["ip"],
                      "label": f"{tgt['service']} ({tgt['ip']})",
                      "x": 2, "y": target_y[i], "kind": kind})

    edges: List[Dict[str, Any]] = []
    # C2 -> runners (beacon edges).
    c2_node = nodes[0]
    for i, r in enumerate(COMPROMISED_RUNNERS):
        edges.append({
            "x": c2_node["x"], "y": c2_node["y"],
            "x2": 1, "y2": runner_y[i],
            "edge_kind": "beacon",
            "label": "C2 beacon",
        })
    # Lateral runner -> internal scan targets.
    lr_idx = next(i for i, r in enumerate(COMPROMISED_RUNNERS)
                  if r["host"] == LATERAL_RUNNER_HOST)
    for i, tgt in enumerate(INTERNAL_SCAN_TARGETS):
        kind = "lateral" if tgt["ip"] == LATERAL_HOP_TARGET["ip"] else "scan"
        edges.append({
            "x": 1, "y": runner_y[lr_idx],
            "x2": 2, "y2": target_y[i],
            "edge_kind": kind,
            "label": kind,
        })

    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": "Attack graph: C2 -> CI runners -> internal targets",
        "layer": [
            {
                "data": {"values": edges},
                "mark": {"type": "rule", "strokeWidth": 2, "opacity": 0.55},
                "encoding": {
                    "x": {"field": "x", "type": "quantitative",
                            "axis": None, "scale": {"domain": [-0.3, 2.3]}},
                    "x2": {"field": "x2"},
                    "y": {"field": "y", "type": "quantitative",
                            "axis": None, "scale": {"domain": [-0.5, 4.8]}},
                    "y2": {"field": "y2"},
                    "color": {
                        "field": "edge_kind", "type": "nominal",
                        "scale": {
                            "domain": ["beacon", "scan", "lateral"],
                            "range": ["#f0a830", "#5b8bbd", "#e8455d"],
                        },
                        "legend": {"labelColor": "#cdd",
                                    "titleColor": "#cdd",
                                    "title": "Edge"},
                    },
                    "tooltip": [{"field": "label", "type": "nominal"}],
                },
            },
            {
                "data": {"values": nodes},
                "mark": {"type": "circle", "size": 600, "opacity": 0.95,
                         "stroke": "#1a1d24", "strokeWidth": 1.2},
                "encoding": {
                    "x": {"field": "x", "type": "quantitative", "axis": None},
                    "y": {"field": "y", "type": "quantitative", "axis": None},
                    "color": {
                        "field": "kind", "type": "nominal",
                        "scale": {
                            "domain": ["c2", "runner", "scan-target", "hop-target"],
                            "range": ["#a14bd2", "#e8455d", "#5b8bbd", "#3fb27f"],
                        },
                        "legend": {"labelColor": "#cdd",
                                    "titleColor": "#cdd",
                                    "title": "Node"},
                    },
                    "tooltip": [{"field": "label", "type": "nominal"},
                                 {"field": "kind", "type": "nominal"}],
                },
            },
            {
                "data": {"values": nodes},
                "mark": {"type": "text", "dy": -16, "fontSize": 11,
                         "color": "#cdd"},
                "encoding": {
                    "x": {"field": "x", "type": "quantitative", "axis": None},
                    "y": {"field": "y", "type": "quantitative", "axis": None},
                    "text": {"field": "label", "type": "nominal"},
                },
            },
        ],
        "config": {"view": {"stroke": "transparent"}, "background": "transparent"},
    }


def _vega_top_packages() -> Dict[str, Any]:
    """Bar chart of top installed packages with the malicious one flagged."""
    values: List[Dict[str, Any]] = []
    try:
        es = get_client()
        r = es.search(index=INDICES["build"], body={
            "size": 0,
            "query": {"range": {"@timestamp": {"gte": "now-14d", "lte": "now"}}},
            "aggs": {
                "by_pkg": {"terms": {"field": "package.name", "size": 12}},
            },
        })
        for b in r["aggregations"]["by_pkg"]["buckets"]:
            name = b["key"]
            classification = ("malicious"
                              if name == MALICIOUS_PACKAGE["name"]
                              else "clean")
            values.append({
                "package": name,
                "installs": int(b.get("doc_count") or 0),
                "classification": classification,
            })
    except Exception as exc:
        log.warning("supplychain.spec_packages.compute.failed", error=str(exc))

    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": "Top installed packages (14d) - malicious package flagged",
        "data": {"values": values},
        "mark": {"type": "bar", "tooltip": True, "cornerRadiusEnd": 3},
        "encoding": {
            "y": {"field": "package", "type": "nominal", "sort": "-x",
                    "title": "Package",
                    "axis": {"labelColor": "#cdd", "titleColor": "#cdd",
                              "labelLimit": 280}},
            "x": {"field": "installs", "type": "quantitative",
                    "title": "Install count",
                    "axis": {"labelColor": "#cdd", "titleColor": "#cdd"}},
            "color": {
                "field": "classification", "type": "nominal",
                "scale": {"domain": ["malicious", "clean"],
                           "range": ["#e8455d", "#5b8bbd"]},
                "legend": {"labelColor": "#cdd", "titleColor": "#cdd",
                            "title": "Classification"},
            },
            "tooltip": [
                {"field": "package", "type": "nominal"},
                {"field": "installs", "type": "quantitative"},
                {"field": "classification", "type": "nominal"},
            ],
        },
        "config": {"view": {"stroke": "transparent"}, "background": "transparent"},
    }


def _vega_severity_breakdown() -> Dict[str, Any]:
    """Donut of alert severity (critical vs high vs medium)."""
    values: List[Dict[str, Any]] = []
    try:
        es = get_client()
        r = es.search(index=INDICES["alerts"], body={
            "size": 0,
            "query": {"range": {"@timestamp": {"gte": "now-14d", "lte": "now"}}},
            "aggs": {
                "by_sev": {"terms": {"field": "rule.severity", "size": 10}},
            },
        })
        for b in r["aggregations"]["by_sev"]["buckets"]:
            values.append({
                "severity": b["key"],
                "alerts": int(b.get("doc_count") or 0),
            })
    except Exception as exc:
        log.warning("supplychain.spec_severity.compute.failed", error=str(exc))

    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": "Alert severity distribution",
        "data": {"values": values},
        "mark": {"type": "arc", "innerRadius": 60, "tooltip": True,
                 "stroke": "#1a1d24"},
        "encoding": {
            "theta": {"field": "alerts", "type": "quantitative"},
            "color": {
                "field": "severity", "type": "nominal",
                "scale": {
                    "domain": ["critical", "high", "medium", "low"],
                    "range": ["#e8455d", "#f0a830", "#5b8bbd", "#3fb27f"],
                },
                "legend": {"labelColor": "#cdd", "titleColor": "#cdd",
                            "title": "Severity"},
            },
            "tooltip": [
                {"field": "severity", "type": "nominal"},
                {"field": "alerts", "type": "quantitative"},
            ],
        },
        "config": {"view": {"stroke": "transparent"}, "background": "transparent"},
    }


# ----- Markdown content -------------------------------------------------------------


def _switcher_md(active: str) -> str:
    """Header switcher with anchor links to the other view."""
    fe_url = settings.kibana_url.rstrip("/") + f"/app/dashboards#/view/{DASHBOARD_ID}"
    cu_url = settings.kibana_url.rstrip("/") + f"/app/dashboards#/view/{CUSTOMER_DASHBOARD_ID}"
    fe_label = "**[FE] Field Engineer prep**" if active == "fe" else "[FE] Field Engineer prep"
    cu_label = "**[Customer] SOC / CISO view**" if active == "customer" else "[Customer] SOC / CISO view"
    return (
        "### Supply Chain Attack (Dependency Confusion) - dashboard switcher\n\n"
        f"Pick your view:  [{fe_label}]({fe_url})  |  [{cu_label}]({cu_url})\n\n"
        "_Same data, two narratives. FE view is the demo prep with MITRE + ML "
        "detection rules + Cases workflow. Customer view is the executive "
        "incident report with business risk + 30 day remediation plan._"
    )


def _md_fe_intro() -> str:
    return (
        "## [FE] Supply Chain Attack - Field Engineer prep\n\n"
        "**MITRE: T1195.002 Compromise Software Supply Chain | T1078 Valid "
        "Accounts | T1021 Remote Services**\n\n"
        "Aurelius Pay (fictional fintech) was hit with a textbook dependency "
        "confusion attack. The malicious package `auriel-internal-utils==9.99.7` "
        "was published to public PyPI in week T minus 2. The first compromised "
        "CI runner pulled it on T minus 9 day. Over the next 9 days the implant "
        "phoned home to `aureliuspay-tg.duckdns.org` every 4 to 7 hours. In "
        "week T zero the operator pivoted: 4 internal services scanned (event."
        "action: `host.discovery`), 2 service account tokens replayed from "
        "anomalous origins (event.action: `auth.token_theft`), and 1 successful "
        "psql lateral hop landed on the staging Postgres at "
        "`192.168.10.88:5432`.\n\n"
        "**Demo talk track:**\n"
        "1. Open with the technique bar (top right): T1195.002 dominates the "
        "alert volume. That single chart says supply chain compromise.\n"
        "2. Drop into the 14-day timeline: each stage band tells the operator's "
        "story in chronological order. The dwell time between first install "
        "and lateral hop is roughly 9 days, which is exactly the median for "
        "this technique class.\n"
        "3. Pivot to top hosts: 4 CI runners light up red while the rest of the "
        "fleet stays blue. Click into `ci-runner-deploy-03` to see all 5 "
        "techniques on one host.\n"
        "4. Use the attack graph to show the operator path visually: C2 domain "
        "to runners to internal targets. The green node is the successful hop.\n"
        "5. Close with the package bar: `auriel-internal-utils` shows up only "
        "on the 4 compromised runners while `aurelius-internal-utils` (the "
        "legitimate scoped name) is on every clean runner.\n\n"
        "**Elastic Security capabilities that catch this end to end:**\n"
        "- Prebuilt detection rule: *Suspicious Package Installed From Public "
        "Registry Matching Internal Scope* (anchors on T1195.002).\n"
        "- ML rule: `network_anomalous_dns_lookup` flags the DuckDNS C2 "
        "cadence within hours of first beacon.\n"
        "- Behavior Analytics: `host.discovery` + `auth.token_theft` + "
        "`remote.service.connect` from the same host within 48 hours triggers "
        "the killchain composition rule.\n"
        "- Cases workflow: every alert auto-bundles by `host.id`, escalates "
        "to Tier 2 with the attack graph as the cover image, and ships to "
        "PagerDuty + Slack `#sec-incident`.\n\n"
        "**Source quotes (use verbatim):**\n"
        "- *Sonatype State of the Software Supply Chain 2024:* \"Dependency "
        "confusion attacks grew 633% year over year; the median time from "
        "package publish to first pull is 32 hours.\"\n"
        "- *Elastic Security docs:* \"The killchain composition rule chains "
        "T1195 with T1078 and T1021 events from the same host.id within a "
        "rolling 14 day window.\""
    )


def _md_customer_intro() -> str:
    return (
        "## [Customer] Supply Chain Attack - Security Incident Report\n\n"
        "**Incident class:** Dependency confusion attack with lateral movement  \n"
        "**MITRE techniques:** T1195.002 / T1078 / T1021  \n"
        "**Status:** Contained - active response and 30 day remediation in "
        "progress\n\n"
        "**What happened.** A malicious Python package matching one of our "
        "internal scoped names (`auriel-internal-utils`) was published to "
        "public PyPI eleven days ago. Four of our CI runners pulled it during "
        "routine builds. The package shipped a small implant that beaconed to "
        "a DuckDNS subdomain (`aureliuspay-tg.duckdns.org`) every 4 to 7 hours "
        "for 9 days. Yesterday the operator pivoted: scanned 4 internal "
        "services from one of the compromised runners, replayed the tokens of "
        "2 service accounts, and successfully connected to our staging "
        "Postgres database (no production data was reached).\n\n"
        "**Headline numbers:**\n"
        "- **1** malicious package on public PyPI matching an internal name\n"
        "- **4** compromised CI runners (out of ~50 in the fleet)\n"
        "- **6** lateral movement attempts inside the staging segment\n"
        "- **1** successful hop to a staging Postgres database\n"
        "- **0** production data services touched\n\n"
        "**What was caught:** every alert correlated to the runner that "
        "pulled the package; Tier 2 was paged within 12 minutes of the first "
        "C2 beacon by the ML anomaly rule.\n\n"
        "**What was missed (and is now in scope):** the initial install on "
        "T minus 9 did not page directly because the package install came "
        "through pip with a valid checksum (the malicious one). The new "
        "internal-scope-name allow list closes that gap."
    )


def _md_kpi_line() -> str:
    return (
        "## Headline figures\n\n"
        "| Metric | Value |\n"
        "| --- | --- |\n"
        "| Malicious packages on public PyPI | **1** |\n"
        "| Compromised CI runners | **4** |\n"
        "| Lateral movement attempts | **6** |\n"
        "| Successful hops to staging Postgres | **1** |\n"
        "| Distinct MITRE techniques observed | **5** "
        "(T1195.002, T1071.004, T1018, T1078, T1021) |\n"
        "| Time from first beacon to ML rule firing | **12 minutes** |\n"
    )


def _md_fe_closing() -> str:
    return (
        "## How this becomes a customer conversation\n\n"
        "**Talk track for the next call:**\n"
        "- **Why this story lands:** dependency confusion is the most "
        "broadly understood supply-chain failure mode in 2026 (Apple, "
        "Microsoft, Yelp all hit publicly). Every CISO has read the "
        "Birsan write-up. They want to know if their tooling would catch "
        "the same chain end to end.\n"
        "- **Elastic differentiator:** the killchain composition rule. "
        "Splunk ES does not chain MITRE techniques across hosts in a single "
        "rule out of the box; CrowdStrike does endpoint-only and misses CI "
        "runner package telemetry. Elastic ingests the build pipeline, "
        "runtime telemetry, and IAM events into one ECS index and chains "
        "them with EQL `sequence by host.id` over 14 days.\n"
        "- **Cases workflow:** auto bundle, attack graph cover image, "
        "PagerDuty + Slack handoff, MITRE coverage matrix automatically "
        "populated. SOC analyst opens one Case and sees the full kill chain.\n"
        "- **MEDDPICC angle:** Metric is mean time to detect for supply "
        "chain compromise. Industry baseline is ~9 to 14 days; we caught "
        "the C2 beacon at 12 minutes from first phone home.\n\n"
        "## MITRE ATT&CK mapping and Elastic countermeasures\n\n"
        "| MITRE | Stage | Elastic Security capability |\n"
        "| --- | --- | --- |\n"
        "| **[T1195.002](https://attack.mitre.org/techniques/T1195/002/) "
        "Compromise Software Supply Chain** | Initial install of malicious "
        "package | Prebuilt rule *Suspicious Package Installed From Public "
        "Registry Matching Internal Scope*; integrated checksum diff vs "
        "internal Artifactory mirror |\n"
        "| **[T1071.004](https://attack.mitre.org/techniques/T1071/004/) "
        "DNS C2** | Periodic beaconing to DuckDNS | ML rule "
        "`network_anomalous_dns_lookup`; threat intel match on dynamic DNS "
        "providers |\n"
        "| **[T1018](https://attack.mitre.org/techniques/T1018/) Remote "
        "System Discovery** | Internal nmap-style probe | EQL "
        "`process where process.name=='nmap' and host.name like 'ci-*'` |\n"
        "| **[T1078](https://attack.mitre.org/techniques/T1078/) Valid "
        "Accounts** | Stolen service account token replay | Behavior "
        "Analytics rule `service_account_anomalous_origin` |\n"
        "| **[T1021](https://attack.mitre.org/techniques/T1021/) Remote "
        "Services** | psql lateral hop to staging Postgres | EQL "
        "killchain composition: `sequence by host.id [process where "
        "process.name=='nmap'] [authentication where event.action=="
        "'auth.token_theft'] [process where process.name=='psql']` |\n\n"
        "**Call to action.** Schedule a 45 minute live walkthrough on the "
        "customer's CI fleet next week. Mirror their staging package "
        "registry feed into a free Elastic Cloud trial and reproduce this "
        "dashboard against their data inside the same call."
    )


def _md_customer_closing() -> str:
    return (
        "## What was caught, what was missed, and the 30 day remediation plan\n\n"
        "**Caught:**\n"
        "- All 4 compromised runners were correlated to a single root cause "
        "package (`auriel-internal-utils==9.99.7`) within 12 minutes of the "
        "first C2 beacon.\n"
        "- The lateral movement chain (scan to token theft to psql hop) was "
        "stitched together by the killchain composition rule and presented "
        "as a single Case to the on-call analyst.\n"
        "- Successful psql connection was logged at the destination database "
        "and matched to the offending source within 30 seconds.\n\n"
        "**Missed (and now in scope):**\n"
        "- The initial install at T minus 9 day was not a paging event by "
        "itself - pip ran with a valid checksum (because the malicious "
        "checksum was self-consistent). The detection fired only when the "
        "implant beaconed.\n"
        "- The two compromised service accounts had token TTLs of 24 hours, "
        "which is too long for a CI runner role.\n\n"
        "**30 day remediation plan:**\n"
        "1. **Days 1 to 3** - Internal-scope-name allow list. Block any "
        "public-registry pull whose package name overlaps an internal "
        "Artifactory namespace. Effort: 2 engineering days plus change "
        "control.\n"
        "2. **Days 4 to 10** - Service account token TTL squeeze: drop CI "
        "runner roles from 24 hours to 1 hour, with workload identity "
        "federation for renewal. Effort: 1 sprint.\n"
        "3. **Days 11 to 17** - Default-deny egress from CI runners to any "
        "destination outside the corporate registry / GitHub / Datadog "
        "allow list. Effort: 1 sprint plus change-control review.\n"
        "4. **Days 18 to 24** - Killchain composition rule rolled out to "
        "production tier (currently staging only). Effort: 3 days.\n"
        "5. **Days 25 to 30** - Tabletop exercise replaying this scenario "
        "with Tier 2 + IR + Eng leadership; success criterion is mean time "
        "to detect under 30 minutes for the full chain.\n\n"
        "**Executive summary one-liner:** Elastic Security detected and "
        "contained a dependency confusion attack against 4 CI runners "
        "before the operator reached production data. The 30 day "
        "remediation plan closes the residual gaps."
    )


# ----- Panels assembly --------------------------------------------------------------


def _build_panels(view: str) -> List[Dict[str, Any]]:
    """Build the 9-panel layout (3 markdown + 6 Vega) for either the FE or
    Customer dashboard."""

    intro_md = _md_fe_intro() if view == "fe" else _md_customer_intro()
    closing_md = _md_fe_closing() if view == "fe" else _md_customer_closing()
    kpi_md = _md_kpi_line()

    spec_techniques = _vega_alerts_by_technique()
    spec_timeline = _vega_attack_timeline()
    spec_top_hosts = _vega_top_compromised_hosts()
    spec_graph = _vega_attack_graph()
    spec_packages = _vega_top_packages()
    spec_severity = _vega_severity_breakdown()

    panels: List[Dict[str, Any]] = []

    # Row 1: switcher header (full, h=4)
    panels.append(_markdown_panel("switcher", 0, 0, 48, 4,
                                   _switcher_md(view), "Switch view"))

    # Row 2: intro markdown (full, h=8)
    panels.append(_markdown_panel("intro", 0, 4, 48, 8,
                                   intro_md, "Overview"))

    # Row 3: alerts by MITRE technique (24w, h=14) + top compromised hosts (24w, h=14)
    panels.append(_vega_panel("p_tech", 0, 12, 24, 14,
                               "Alerts by MITRE technique", spec_techniques))
    panels.append(_vega_panel("p_hosts", 24, 12, 24, 14,
                               "Top hosts by alert count", spec_top_hosts))

    # Row 4: 14-day attack timeline (full width, h=14)
    panels.append(_vega_panel("p_timeline", 0, 26, 48, 14,
                               "14 day attack timeline", spec_timeline))

    # Row 5: attack graph (24w, h=14) + packages (24w, h=14)
    panels.append(_vega_panel("p_graph", 0, 40, 24, 14,
                               "Attack graph: C2 to runners to targets",
                               spec_graph))
    panels.append(_vega_panel("p_packages", 24, 40, 24, 14,
                               "Top installed packages", spec_packages))

    # Row 6: severity donut (16w, h=12) + KPI markdown (32w, h=12)
    panels.append(_vega_panel("p_severity", 0, 54, 16, 12,
                               "Alert severity", spec_severity))
    panels.append(_markdown_panel("p_kpi", 16, 54, 32, 12, kpi_md,
                                   "Headline figures"))

    # Row 7: closing narrative (full width, h=12)
    panels.append(_markdown_panel("closing", 0, 66, 48, 12, closing_md,
                                   "Closing narrative"))

    return panels


def _fe_industry_context() -> Dict[str, Any]:
    return {
        "id": "supply-chain",
        "name": "Supply chain attack - DevSecOps response",
        "summary": ("npm/SolarWinds-class supply chain compromise: detect the "
                    "package, trace the blast radius, evict the implant."),
        "personas": [
            {"role": "CISO",
             "pain": "Cannot answer 'are we exposed?' inside the 24h SEC disclosure window."},
            {"role": "Head of AppSec",
             "pain": "Package SBOM is in 3 systems; no single query layer."},
            {"role": "DevSecOps Lead",
             "pain": "Build-system telemetry is not joined to runtime telemetry."},
            {"role": "Compliance Officer",
             "pain": "EO 14028 / FedRAMP evidence pulls take weeks."},
        ],
        "regulations": ["EO 14028", "NIST 800-161", "FedRAMP", "SOC 2"],
        "top_competitors": ["battlecard-splunk", "battlecard-microsoft-sentinel",
                            "battlecard-chronicle"],
    }


def _fe_superset_panels() -> List[Dict[str, Any]]:
    from app.services.scenarios.industry_factory import build_fe_superset_panels

    cu_panels = _build_panels("customer")
    legacy_fe = _build_panels("fe")
    fe_only_extras = [p for p in legacy_fe
                      if p.get("embeddableConfig", {}).get("savedVis", {})
                          .get("type") == "markdown"
                      and p.get("panelIndex") not in ("switcher",)]
    return build_fe_superset_panels(
        _fe_industry_context(),
        customer="DevSecOps and SOC",
        customer_panels=cu_panels,
        fe_only_extras=fe_only_extras,
        id_prefix="sc-fe",
    )


def get_dashboard_panels() -> List[Dict[str, Any]]:
    """FE = customer superset + FE-only talk track + discovery + say/do-not-say."""
    return _fe_superset_panels()


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
            client.delete(_kbn_url(f"/api/data_views/data_view/{dv_id}"),
                          headers=_kbn_headers())
        except Exception:
            pass
        resp = client.post(_kbn_url("/api/data_views/data_view"),
                           headers=_kbn_headers(), json=body)
        if resp.status_code >= 400:
            log.warning("supplychain.dataview.fallback",
                        status=resp.status_code, body=resp.text[:300])
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
                    f"Kibana data view create failed: "
                    f"{resp2.status_code} {resp2.text[:300]}"
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
            "timeFrom": "now-14d",
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
    fe_panels = _fe_superset_panels()
    cu_panels = _build_panels("customer")

    fe_id = _create_one_dashboard(
        data_view_id=data_view_id,
        dashboard_id=DASHBOARD_ID,
        title=f"[FE] {SCENARIO_TITLE}",
        description=(
            "Field Engineer prep view. MITRE T1195.002 / T1078 / T1021 alignment, "
            "Elastic Security ML and killchain composition rules, Cases workflow, "
            "MEDDPICC angle."
        ),
        panels=fe_panels,
    )
    cu_id = _create_one_dashboard(
        data_view_id=data_view_id,
        dashboard_id=CUSTOMER_DASHBOARD_ID,
        title=f"[Customer] {SCENARIO_TITLE}",
        description=(
            "SOC analyst / CISO view. Executive incident report with business "
            "risk framing and 30 day remediation plan."
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
    with mappings, bulk-ingest, recreate dashboards. Returns counts + URLs."""
    started = time.time()
    if not settings.elasticsearch_api_key and not settings.elasticsearch_password:
        raise RuntimeError("Elasticsearch credentials not configured")
    if not settings.kibana_api_key:
        raise RuntimeError("KIBANA_API_KEY not configured")

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
        success, errors = bulk(es, actions, chunk_size=500, refresh=refresh,
                                raise_on_error=False)
        counts[index] = success
        if docs:
            # Prefer an alert sample on the alerts index for nicer CLI output.
            sample = next(
                (d for d in docs if d.get("event", {}).get("kind") == "alert"),
                docs[0],
            )
            samples[index] = sample
        log.info("supplychain.indexed", index=index, count=success,
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
        "elapsed_seconds": round(time.time() - started, 2),
        "samples": samples,
    }
