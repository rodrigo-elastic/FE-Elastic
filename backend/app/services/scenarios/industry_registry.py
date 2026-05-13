"""
filename: industry_registry.py
description: Loads `data/seed/industries.json` once and produces a namespace
    object per industry that quacks like one of the existing scenario modules
    (black_friday, fsi_banking_fraud, etc). Each namespace exposes
    SCENARIO_ID, SCENARIO_TITLE, SCENARIO_DESCRIPTION, INDICES, DASHBOARD_ID,
    CUSTOMER_DASHBOARD_ID, INDUSTRY_ID, CUSTOMER_NAME, and a seed() callable.

    `register_into(SCENARIOS)` mutates an existing scenarios dict in place,
    keyed by the synthetic SCENARIO_ID of shape `industry-<industry_id>`.

date: 13-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

from app.services.scenarios.industry_factory import build_industry_scenario
from app.utils.logging import get_logger

log = get_logger(__name__)

# data/seed/industries.json lives at <repo>/data/seed/industries.json. From this
# file (backend/app/services/scenarios/industry_registry.py) the repo root is
# parents[4].
_INDUSTRIES_SEED_PATH: Path = (
    Path(__file__).resolve().parents[4] / "data" / "seed" / "industries.json"
)


def _load_industries() -> List[Dict[str, Any]]:
    if not _INDUSTRIES_SEED_PATH.exists():
        log.warning("industry_registry.seed.missing",
                    path=str(_INDUSTRIES_SEED_PATH))
        return []
    try:
        data = json.loads(_INDUSTRIES_SEED_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        log.warning("industry_registry.seed.decode_failed", error=str(exc))
        return []
    return data if isinstance(data, list) else []


def _to_namespace(scenario: Dict[str, Any]) -> SimpleNamespace:
    """Adapt the factory's dict-shaped scenario into a module-like namespace
    so routes_demo_data.SCENARIOS values look identical to a real module."""
    return SimpleNamespace(**scenario)


def _build_all() -> Dict[str, SimpleNamespace]:
    out: Dict[str, SimpleNamespace] = {}
    for cfg in _load_industries():
        try:
            scenario = build_industry_scenario(cfg)
        except Exception as exc:
            log.warning("industry_registry.build.failed",
                        industry_id=cfg.get("id"), error=str(exc))
            continue
        ns = _to_namespace(scenario)
        out[ns.SCENARIO_ID] = ns
    return out


# Built eagerly at import time so module-load order matches the other scenarios.
ALL_INDUSTRY_SCENARIOS: Dict[str, SimpleNamespace] = _build_all()


def register_into(scenarios_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Mutate `scenarios_dict` in place, adding one entry per industry. Existing
    keys are NOT overwritten (so the hand-crafted flagship scenarios win when
    their SCENARIO_ID happens to collide with an industry id)."""
    for scenario_id, ns in ALL_INDUSTRY_SCENARIOS.items():
        if scenario_id in scenarios_dict:
            continue
        scenarios_dict[scenario_id] = ns
    return scenarios_dict


def list_industry_scenario_ids() -> List[str]:
    """Stable-sorted list of registered industry scenario ids."""
    return sorted(ALL_INDUSTRY_SCENARIOS.keys())
