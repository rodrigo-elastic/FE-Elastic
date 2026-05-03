"""
filename: main.py
description: FastAPI entrypoint. Wires CORS, routers, static frontend.
date: 02-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import (
    routes_agent_builder,
    routes_agents,
    routes_audit,
    routes_battlecards,
    routes_briefs,
    routes_calendar,
    routes_health,
    routes_kibana,
    routes_mcp,
    routes_meetings,
    routes_salesforce,
    routes_tools,
)
from app.config import settings
from app.utils.logging import get_logger

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    log.info("app.startup", env=settings.app_env, version=__version__)
    # Best-effort: ensure ES app indices exist if the cluster is reachable.
    try:
        from app.repositories.elasticsearch_repo import get_repo as get_es_repo

        es = get_es_repo()
        if es.available:
            statuses = es.ensure_indices()
            log.info("app.startup.es_indices", statuses=statuses)
    except Exception as exc:
        log.warning("app.startup.es_ensure_failed", error=str(exc))
    yield
    log.info("app.shutdown")


app = FastAPI(
    title="FE Copilot",
    description="AI-powered assistant for Field Engineers.",
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes_health.router, prefix="/api/v1")
app.include_router(routes_meetings.router, prefix="/api/v1")
app.include_router(routes_agents.router, prefix="/api/v1")
app.include_router(routes_briefs.router, prefix="/api/v1")
app.include_router(routes_audit.router, prefix="/api/v1")
app.include_router(routes_battlecards.router, prefix="/api/v1")
app.include_router(routes_salesforce.router, prefix="/api/v1")
app.include_router(routes_calendar.router, prefix="/api/v1")
app.include_router(routes_tools.router, prefix="/api/v1")
app.include_router(routes_agent_builder.router, prefix="/api/v1")
app.include_router(routes_mcp.router, prefix="/api/v1")
app.include_router(routes_kibana.router, prefix="/api/v1")

# Serve the markdown docs folder (compliance.md, architecture.md, etc.) before the catch-all frontend mount.
docs_path = Path(__file__).resolve().parents[2] / "docs"
if docs_path.exists():
    app.mount("/docs-md", StaticFiles(directory=str(docs_path)), name="docs-md")

# Serve the static frontend at the project root, after API routes are mounted.
frontend_path = Path(__file__).resolve().parents[2] / "frontend"
if frontend_path.exists():
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")
    log.info("frontend.mounted", path=str(frontend_path))
