"""
filename: main.py
description: FastAPI entrypoint. Wires CORS, routers, static frontend.
date: 02-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.routing import Match

from app.api import (
    routes_agent_builder,
    routes_agents,
    routes_audit,
    routes_autoops,
    routes_battlecards,
    routes_briefs,
    routes_calendar,
    routes_demo_data,
    routes_handover,
    routes_health,
    routes_industries,
    routes_kibana,
    routes_mcp,
    routes_meetings,
    routes_notifications,
    routes_salesforce,
    routes_stats,
    routes_tools,
    routes_workflow_settings,
    routes_workflows,
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

    # Start the pre-meeting brief auto-scheduler.
    from app.services.brief_scheduler import scheduler_loop
    scheduler_task = asyncio.create_task(scheduler_loop())

    yield

    scheduler_task.cancel()
    log.info("app.shutdown")


_is_prod = settings.app_env == "production"
app = FastAPI(
    title="FE Copilot",
    description="AI-powered assistant for Field Engineers.",
    version=__version__,
    lifespan=lifespan,
    openapi_url=None if _is_prod else "/openapi.json",
    docs_url=None if _is_prod else "/docs",
    redoc_url=None if _is_prod else "/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def no_cache_config_middleware(request: Request, call_next):
    """Force no-cache for config.js so browsers always fetch the fresh routing logic."""
    response = await call_next(request)
    if request.url.path == "/config.js":
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@app.middleware("http")
async def api_method_not_allowed_middleware(request: Request, call_next):
    """Convert 404 from the static frontend mount into a proper 405 for API paths.

    FastAPI mounts the static frontend at ``/`` so unknown paths under
    ``/api/v1/`` return 404 from StaticFiles instead of Starlette's built-in
    405 method-mismatch response. For paths under ``/api/v1/`` we override that:
    if any API route matches the path under a different method, we return 405
    with a proper ``Allow`` header before the static mount sees it.
    """
    path = request.url.path
    method = request.method
    # Skip OPTIONS so the CORS middleware can handle preflight responses.
    if path.startswith("/api/v1/") and method != "OPTIONS":
        full_match_found = False
        partial_methods: set = set()
        for route in app.routes:
            matcher = getattr(route, "matches", None)
            methods = getattr(route, "methods", None)
            if matcher is None or not methods:
                continue
            match, _ = matcher({"type": "http", "method": method, "path": path})
            if match == Match.FULL:
                full_match_found = True
                break
            if match == Match.PARTIAL:
                partial_methods.update(methods)
        if not full_match_found and partial_methods:
            return JSONResponse(
                {"detail": "Method Not Allowed"},
                status_code=405,
                headers={"Allow": ", ".join(sorted(partial_methods))},
            )
    return await call_next(request)


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
app.include_router(routes_autoops.router, prefix="/api/v1")
app.include_router(routes_mcp.router, prefix="/api/v1")
app.include_router(routes_kibana.router, prefix="/api/v1")
app.include_router(routes_demo_data.router, prefix="/api/v1")
app.include_router(routes_workflows.router, prefix="/api/v1")
app.include_router(routes_workflow_settings.router, prefix="/api/v1")
app.include_router(routes_notifications.router, prefix="/api/v1")
app.include_router(routes_industries.router, prefix="/api/v1")
app.include_router(routes_stats.router, prefix="/api/v1")
app.include_router(routes_handover.router, prefix="/api/v1")

# Serve the markdown docs folder (compliance.md, architecture.md, etc.) before the catch-all frontend mount.
docs_path = Path(__file__).resolve().parents[2] / "docs"
if docs_path.exists():
    app.mount("/docs-md", StaticFiles(directory=str(docs_path)), name="docs-md")

# Serve the static frontend at the project root, after API routes are mounted.
frontend_path = Path(__file__).resolve().parents[2] / "frontend"
if frontend_path.exists():
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")
    log.info("frontend.mounted", path=str(frontend_path))
