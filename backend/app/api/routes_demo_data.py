"""
filename: routes_demo_data.py
description: Demo Data Generator REST surface. Lists the three story scenarios (Black Friday outage, credential stuffing, noisy microservice) and seeds them on demand into the live Elastic cluster, recreating their Kibana dashboards. Each scenario module exposes a deterministic `seed()` that handles both indexing and dashboard creation.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from app.services.scenarios import black_friday, credential_stuffing, noisy_microservice
from app.utils.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/demo-data", tags=["demo-data"])

# Registry of scenario modules. Each module exposes the same public surface:
# SCENARIO_ID, SCENARIO_TITLE, SCENARIO_DESCRIPTION, INDICES, DASHBOARD_ID, seed().
SCENARIOS = {
    black_friday.SCENARIO_ID: black_friday,
    credential_stuffing.SCENARIO_ID: credential_stuffing,
    noisy_microservice.SCENARIO_ID: noisy_microservice,
}


def _meta(mod) -> Dict[str, Any]:
    return {
        "id": mod.SCENARIO_ID,
        "title": mod.SCENARIO_TITLE,
        "description": mod.SCENARIO_DESCRIPTION,
        "indices": list(mod.INDICES.values()),
        "dashboard_id": mod.DASHBOARD_ID,
    }


@router.get("/scenarios")
def list_scenarios() -> Dict[str, List[Dict[str, Any]]]:
    return {"scenarios": [_meta(m) for m in SCENARIOS.values()]}


@router.post("/{scenario_id}/seed")
def seed_scenario(scenario_id: str) -> Dict[str, Any]:
    mod = SCENARIOS.get(scenario_id)
    if mod is None:
        raise HTTPException(status_code=404, detail=f"unknown scenario {scenario_id}")
    log.info("demo_data.seed.start", scenario_id=scenario_id)
    try:
        result = mod.seed()
    except Exception as exc:
        log.warning("demo_data.seed.failed", scenario_id=scenario_id, error=str(exc))
        raise HTTPException(status_code=502, detail=f"seed failed: {exc}")
    log.info("demo_data.seed.ok", scenario_id=scenario_id, indices=result.get("indices"))
    return {"ok": True, **_meta(mod), **result}
