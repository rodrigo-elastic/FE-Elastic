# FE Copilot

AI-powered assistant for Elastic Field Engineers. Hackathon submission for the **FY27 SKO FE Summit Hackathon** (theme: "Hack. Build. Automate The Impossible.", deadline 2026-05-10).

A chain of three agents automates the FE meeting workflow:

1. **Pre-Meeting Researcher**: account brief delivered via Slack and PDF, 1 hour before the meeting.
2. **Live Meeting Companion**: real-time competitor and MEDDPICC alerts per transcript turn.
3. **Post-Meeting Action Engine**: structured summary, action items, Salesforce push, follow-up email draft.

All three agents default to **Haiku 4.5** (~$0.02 per full pipeline run). Each agent is independently upgradable to Sonnet 4.6 or Opus 4.7 by setting `MODEL_PRE_MEETING` / `MODEL_POST_MEETING` / `MODEL_LIVE_MEETING` in `.env`.

> All data in this project is synthetic. No customer data is used or stored.

## Stack

- Python 3.11+, FastAPI, Pydantic, structlog
- Anthropic Claude API: Opus 4.7 for reasoning agents, Haiku 4.5 for live alerts
- Prompt caching on the stable system block; structured output via `output_config.format`
- Elasticsearch 8.x via `docker-compose`
- Plain HTML, JS, and CSS frontend (served by FastAPI)
- WeasyPrint for PDF generation (graceful HTML fallback when system libs are missing)
- Mocked Slack, Google Calendar, and Salesforce integrations (file-based logs)

## Project layout

```
FE-Elastic/
  backend/
    app/
      agents/                 Pre-Meeting, Live, Post-Meeting agent classes
        prompts/              System prompts, JSON schemas, offline mocks per agent
        schemas.py            Pydantic models mirroring forced JSON outputs
      api/                    FastAPI routers
      integrations/           Anthropic + ES clients; Slack/Calendar/SFDC mocks
      repositories/           Read-only access over synthetic JSON fixtures
      services/               PDF builder (Jinja + WeasyPrint), transcript parser, email drafter
      models/                 Pydantic domain models
    data/
      synthetic/              Generated fixtures (gitignored)
      seed/es_mappings.json   Elasticsearch mappings
    scripts/                  generate_synthetic_data.py, seed_elasticsearch.py, run_pipeline.py
    tests/                    Unit and end-to-end tests in mock mode
  frontend/                   Static dashboard (index.html + meeting.html + assets)
  infra/                      docker-compose.yml + Dockerfile.backend
  docs/                       architecture.md, demo-script.md, judging-narrative.md
  runtime/                    Slack/SFDC logs, generated PDFs, email drafts (gitignored)
```

## Setup

1. Copy the env template (the demo runs in mock mode if you skip this):
   ```bash
   cp .env.example .env
   # Optional: set ANTHROPIC_API_KEY=sk-ant-... to call Opus 4.7 for real
   ```

2. Create a virtualenv and install dependencies (Python 3.11+):
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r backend/requirements.txt
   ```
   For full PDF support on macOS:
   ```bash
   brew install pango cairo gdk-pixbuf libffi
   ```
   (Without these, the brief is written as HTML; the demo still works.)

3. Generate synthetic data (deterministic, offline):
   ```bash
   PYTHONPATH=backend python -m scripts.generate_synthetic_data
   ```

4. Run the backend (also serves the frontend):
   ```bash
   PYTHONPATH=backend uvicorn app.main:app --reload --port 8123
   ```
   Port 8123 is the project default (8000 / 8080 / 9000 are commonly used by other tools). Override with `--port` or `APP_PORT` in `.env`.

5. Open the dashboard at http://localhost:8123.

### Optional: Elasticsearch

```bash
docker compose -f infra/docker-compose.yml up -d
PYTHONPATH=backend python -m scripts.seed_elasticsearch
```

## Running the agent pipeline end-to-end

Smoke test with mock Claude (no key needed):

```bash
PYTHONPATH=backend python -m scripts.run_pipeline
```

Output shows the Pre-Meeting headline, Post-Meeting summary plus action item count plus SFDC task IDs, and the Live agent alerts on a sample turn.

## Tests

```bash
PYTHONPATH=backend pytest
```

The suite runs every test in mock mode (no API key required). 26 tests cover synthetic data shape, the three agents, services, and the FastAPI health endpoints.

## Demo

See `docs/demo-script.md` for the 3 minute walkthrough.

## License

MIT. See `LICENSE`.
