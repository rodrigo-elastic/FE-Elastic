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

from app.config import settings
from app.services.scenarios import (
    black_friday,
    credential_stuffing,
    fsi_banking_fraud,
    gdpr_audit,
    government_cdm,
    healthcare_hipaa_audit,
    noisy_microservice,
    supply_chain_attack,
)
from app.utils.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/demo-data", tags=["demo-data"])

# Registry of scenario modules. Each module exposes the same public surface:
# SCENARIO_ID, SCENARIO_TITLE, SCENARIO_DESCRIPTION, INDICES, DASHBOARD_ID, seed().
SCENARIOS = {
    black_friday.SCENARIO_ID: black_friday,
    credential_stuffing.SCENARIO_ID: credential_stuffing,
    noisy_microservice.SCENARIO_ID: noisy_microservice,
    gdpr_audit.SCENARIO_ID: gdpr_audit,
    supply_chain_attack.SCENARIO_ID: supply_chain_attack,
    fsi_banking_fraud.SCENARIO_ID: fsi_banking_fraud,
    healthcare_hipaa_audit.SCENARIO_ID: healthcare_hipaa_audit,
    government_cdm.SCENARIO_ID: government_cdm,
}


def _meta(mod) -> Dict[str, Any]:
    out = {
        "id": mod.SCENARIO_ID,
        "title": mod.SCENARIO_TITLE,
        "description": mod.SCENARIO_DESCRIPTION,
        "indices": list(mod.INDICES.values()),
        "dashboard_id": mod.DASHBOARD_ID,
    }
    # Optional fields the new flagship scenarios expose; older scenarios omit
    # them and we leave the keys absent rather than null so the UI can detect.
    industry = getattr(mod, "INDUSTRY_ID", None)
    customer = getattr(mod, "CUSTOMER_NAME", None)
    customer_dashboard_id = getattr(mod, "CUSTOMER_DASHBOARD_ID", None)
    if industry:
        out["industry_id"] = industry
    if customer:
        out["customer_name"] = customer
    if customer_dashboard_id:
        out["customer_dashboard_id"] = customer_dashboard_id
    return out


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

    # Normalise the seed response into a stable shape for the UI:
    # - dashboard_url:           the FE view (the legacy default)
    # - dashboard_url_customer:  the paired customer view (constructed from a
    #   convention-based id; not every scenario surfaces it explicitly)
    # - doc_counts:              {index_name: count}
    fe_url = (
        result.get("dashboard_url")
        or result.get("dashboard", {}).get("dashboard_url")
        or result.get("fe_dashboard_url")
    )
    customer_url_from_result = (
        result.get("dashboard_url_customer")
        or result.get("customer_dashboard_url")
        or (result.get("customer_dashboard") or {}).get("dashboard_url")
        or (result.get("dashboard_customer") or {}).get("dashboard_url")
    )
    # Convention-based fallback: replace "-dashboard" suffix with "-customer-dashboard".
    base_id = mod.DASHBOARD_ID
    if base_id.endswith("-dashboard"):
        customer_id = base_id[: -len("-dashboard")] + "-customer-dashboard"
    elif base_id.endswith("-customer-dashboard"):
        customer_id = base_id
    else:
        customer_id = f"{base_id}-customer-dashboard"
    fallback_customer_url = settings.kibana_url.rstrip("/") + f"/app/dashboards#/view/{customer_id}"

    counts = (
        result.get("actual_doc_counts")
        or result.get("indexed_doc_counts")
        or (result.get("indices") if isinstance(result.get("indices"), dict)
            and all(isinstance(v, int) for v in result.get("indices", {}).values())
            else {})
    )

    return {
        "ok": True,
        **_meta(mod),
        "dashboard_url": fe_url,
        "dashboard_url_customer": customer_url_from_result or fallback_customer_url,
        "doc_counts": counts,
        # Keep the raw upstream response too for debugging / power users.
        "raw": result,
    }
