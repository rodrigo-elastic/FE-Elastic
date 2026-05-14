# Built with

- **Elastic Cloud 9.3.4** with Kibana Agent Builder and Workflows; `fec-knowledge` index of ELSER-embedded documentation; six live customer-fit dashboards rendered from meeting context; the live `fe-summit-hackathon-ed0e8e` deployment hosts the demo cluster.
- **Kibana inference connectors with strict no-fallback** for customer data. `get_elastic_service()` plus `call_structured(strict=True)` route every QBR, TAR, and weekly-slides call through Kibana so private customer text never reaches the direct Anthropic API; four fallback paths (Kibana error, empty response, JSON parse failure, schema validation failure) raise instead of silently bypassing.
- **Elastic AutoOps** as a free TCO proof point against Splunk PS health checks: outbound webhooks land at `POST /api/v1/autoops/webhook` and the brief widget surfaces cluster signals plus a competitive card live during the call.
- **Anthropic Claude** Haiku 4.5 as the cheap default ($0.02 per full pipeline run), Opus 4.7 enabled per agent for deep reasoning, prompt caching on the stable system block, structured output via `output_config.format`.
- **Model Context Protocol (MCP)** server at `/api/v1/mcp/*` exposing fourteen tools for Kibana Agent Builder to introspect.
- **AWS ECS Fargate** as the production deploy target. The backend runs at `https://fe-c85291a2a8b144188ee6be1078e79a95.ecs.us-east-1.on.aws` and is the URL the Kibana connector and the Kibana Workflow webhooks point at.
- **Python 3.11+, FastAPI, Pydantic, structlog** for the backend; one Uvicorn process serves both the API and the frontend.
- **Vanilla HTML, JS, CSS** frontend with no framework and no build step. Five languages wired through `frontend/assets/js/i18n.js`. Elastic Lochmara primary palette.
- **WeasyPrint** for PDF briefs and **python-pptx** for the QBR and weekly-slides decks; both have graceful fallbacks when system libs are missing.
- **SEC EDGAR** live HTTP client for the pre-meeting brief (real 10-K, 6-K, 20-F filings; User-Agent set per SEC policy).
