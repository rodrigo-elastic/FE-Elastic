"""
filename: routes_health.py
description: Health and version endpoints. Confirms the FastAPI app is running.
date: 02-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

from fastapi import APIRouter

from app.config import settings
from app.integrations import kibana_client
from app.repositories.elasticsearch_repo import get_repo as get_es_repo

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "fe-copilot"}


@router.get("/version")
async def version() -> dict:
    return {"version": __version__, "service": "fe-copilot"}


@router.get("/info")
async def info() -> dict:
    """Exposes per-agent model assignment, mock-mode flag, and ES connection status."""
    key = settings.anthropic_api_key.strip()
    mock_mode = key in ("", "sk-ant-replace-me")
    es = get_es_repo()
    return {
        "service": "fe-copilot",
        "version": __version__,
        "mock_mode": mock_mode,
        "models": {
            "default": settings.model_default,
            "pre_meeting": settings.model_for("pre_meeting"),
            "post_meeting": settings.model_for("post_meeting"),
            "live_meeting": settings.model_for("live_meeting"),
        },
        "elasticsearch": {
            "url": settings.elasticsearch_url,
            "available": es.available,
        },
        "kibana": {
            "url": settings.kibana_url,
            "available": kibana_client.ping(),
            "discover": {
                "briefs": kibana_client.discover_url("fec-briefs"),
                "post_meetings": kibana_client.discover_url("fec-post-meetings"),
                "audit": kibana_client.discover_url("fec-audit"),
                "battlecards": kibana_client.discover_url("fec-battlecards"),
            },
        },
    }


@router.post("/elasticsearch/reconnect")
async def elasticsearch_reconnect() -> dict:
    es = get_es_repo()
    es.reconnect()
    if es.available:
        es.ensure_indices()
    return {"available": es.available, "url": settings.elasticsearch_url}


@router.post("/kibana/setup")
async def kibana_setup() -> dict:
    """Idempotently create the four FE Copilot data views in Kibana so Discover is one click away."""
    return kibana_client.setup_data_views()
