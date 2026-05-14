# Operations notes

Day-to-day operational knobs that don't belong on the README front page.

## Kibana API key privileges

When you create the `KIBANA_API_KEY` from Step 2 of the Quickstart, paste this into the "Role descriptors" field:

```json
{
  "fec_copilot": {
    "elasticsearch": {
      "indices": [{"names": ["fec-*", "demo-*"], "privileges": ["all"]}]
    },
    "kibana": [{
      "spaces": ["default"],
      "base": [],
      "feature": {
        "actions": ["all"],
        "alerting": ["all"],
        "dashboard": ["all"],
        "agent_builder": ["all"]
      }
    }]
  }
}
```

This gives FE Copilot enough to:
- Read/write the `fec-*` and `demo-*` indices.
- Create and update Kibana Saved Objects (the per-scenario dashboards).
- Manage Actions / Connectors (the `.email` and `.inference` connectors).
- Manage Alerting Rules (the Kibana Workflows that watch `fec-transcript-inbox`).
- Use the Agent Builder API (create, update, list agents and skills).

## Quick-iteration loops

- **Backend hot-reload:** `cd backend && ../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8123 --reload`
- **Frontend only:** there is no build step. Edit the HTML/JS/CSS and refresh the tab.
- **Sync Agent Builder after a tool prompt change:** `PYTHONPATH=backend python -m scripts.sync_agent_builder` (idempotent).
- **Sync per-competitor specialists after a battlecard change:** `PYTHONPATH=backend python -m scripts.sync_battlecard_agents` (idempotent).
- **Seed a demo scenario into Kibana:** `curl -X POST http://127.0.0.1:8123/api/v1/demo-data/<scenario-id>/seed` or click Seed Scenario on the matching industry card.

## Production deploy

The team-shared production environment runs at `https://fe-c85291a2a8b144188ee6be1078e79a95.ecs.us-east-1.on.aws` on AWS ECS Fargate.

Manual deploy (do this when GitHub Actions is not set up to deploy for you):

```bash
aws ecr get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin 461485115270.dkr.ecr.us-east-1.amazonaws.com
docker buildx build --platform linux/amd64 \
  -t 461485115270.dkr.ecr.us-east-1.amazonaws.com/fe-copilot:latest --push .
aws ecs update-service \
  --cluster genesys-fargate-kibana-donotdelete \
  --service fe-copilot-50d3 \
  --force-new-deployment \
  --region us-east-1
```

The ECS service uses a CANARY strategy (5% for 3 minutes, then full rollover) so a deploy takes ~5-7 minutes to reach steady state. Full playbook in [`deploy.md`](deploy.md).

## Audit and observability

Every Claude call lands in `runtime/audit.jsonl` with input/output token counts plus a JSON-encoded record of which tool was invoked. The same data is mirrored into `fec-audit` in Elasticsearch when ES is configured; the audit page at `/audit.html` reads it live so the FE org can monitor its own token spend.

`scripts/sync_audit_dashboard.py` creates the Kibana dashboard (token spend per agent, per day, per FE) on demand.

## CI

GitHub Actions runs on every push:
- **Lint**: ruff + a custom em-dash / en-dash check (U+2014 and U+2013 are banned in committed text; use ASCII hyphen instead).
- **Tests**: `pytest backend/tests` (30 tests, all mock-mode, no network or API keys).

Both jobs target Python 3.11 and pin `actions/checkout@v5` and `actions/setup-python@v6`.

## i18n / theme / a11y

The frontend ships five languages (English, Spanish, Japanese, German, French) wired through `frontend/assets/js/i18n.js`. Dark and light themes are bootstrapped inline on every page (look for the `data-theme` script at the top of each HTML file). Accessibility audit notes are in [`a11y.md`](a11y.md) when present; the key invariants are persistent `aria-live` regions on every long-running surface, skip-to-main on every page, and keyboard handlers for the agent-builder, customer-health, and battlecard chat surfaces.
