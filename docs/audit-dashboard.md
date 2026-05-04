# FE Copilot Self Observability dashboard

Elastic monitoring Elastic. The FE Copilot backend writes one audit record
per Claude API call into the `fec-audit` Elasticsearch index (see
`backend/app/integrations/claude_client.py::_audit`). This dashboard reads
that index live so a Field Engineer can answer questions like "how much did
this demo cost?", "which tool was the noisiest?", and "are we burning Opus
tokens when Haiku would do?" without ever leaving Kibana.

## What it shows

Saved objects created by `backend/scripts/sync_audit_dashboard.py`:

- **Data view** `fec-audit-dv` over the `fec-audit` index. Time field is
  `ts` (ISO 8601, mapped as `date`) because that is the field shape the
  audit writer produces. The conventional `@timestamp` field is **not**
  present in the index.
- **Dashboard** `fec-audit-self-observability` titled
  `FE Copilot - Self Observability`.

Default time window is `now-7d` to `now`. Panel inventory (10 total):

| # | Panel | Type | Purpose |
| - | ----- | ---- | ------- |
| 1 | FE Copilot self observability | Markdown header | Title plus a one paragraph framing of what the dashboard is for. |
| 2 | Total Claude API calls | Lens KPI (`lnsLegacyMetric`) | `count(records)` over the active time window. |
| 3 | Total tokens consumed | Lens KPI | Formula `sum(input_tokens) + sum(output_tokens)`. |
| 4 | Mock mode share | Lens KPI | Formula `count(kql='mode : "mock"') / count() * 100`, formatted as a percent. |
| 5 | Tokens by model over time | Lens line (`lnsXY`) | Date histogram on `ts`, split by top 5 `model`, y axis is the `input + output` formula sum. |
| 6 | Top agents and tools by call count | Lens horizontal bar | Top 10 by `agent.keyword`, y axis `count()`. |
| 7 | p95 latency by agent | Lens line | Percentile 95 of `latency_ms` over `ts`, split by `agent`. Renders empty until the audit writer emits `latency_ms`; the structural panel is intentional. |
| 8 | Per agent token and latency rollup | Lens datatable (`lnsDatatable`) | Sortable rollup: agent, calls, avg input tokens, avg output tokens, avg latency. |
| 9 | Top 10 most expensive meetings | Lens datatable | Top 10 `meeting_id` values by total tokens; lets you spot expensive sessions. |
| 10 | What this dashboard tells you | Markdown narrative | Reading guide plus the field shape this dashboard assumes (kept in sync with `fec-audit/_mapping`). |

## Audit field shape (validated against `fec-audit/_mapping`)

| Field | Type | Source |
| ----- | ---- | ------ |
| `ts` | date | `_audit` writer, ISO 8601 string. |
| `model` | keyword | Anthropic model id (`claude-opus-4-7`, `claude-haiku-4-5`). |
| `mode` | keyword | `live` for real Anthropic calls, `mock` for offline demo runs. |
| `input_tokens` | long | `usage.input_tokens` from the Anthropic SDK. |
| `output_tokens` | long | `usage.output_tokens`. |
| `cache_read_input_tokens` | long | `usage.cache_read_input_tokens` (prompt cache hits). |
| `cache_creation_input_tokens` | long | `usage.cache_creation_input_tokens` (cache writes). |
| `agent` | keyword | The calling agent or tool wrapper, set via `audit_meta`. |
| `tool` | text + `tool.keyword` | The tool name when the call originated from a tool route. |
| `meeting_id` | keyword | Provenance, attached by every meeting scoped agent and tool. |
| `company_id` | keyword | Same. |

The latency panel and the latency column in the per-agent rollup target a
field named `latency_ms` that is **not** currently emitted. They render
cleanly empty and are kept on the dashboard so the moment that field is
added to the audit writer, the visualisations light up with no further
work.

## How to refresh

The script is idempotent. Each run deletes and recreates both the data
view and the dashboard, so you can safely run it any time.

```bash
PYTHONPATH=backend .venv/bin/python -m scripts.sync_audit_dashboard
```

It expects `KIBANA_URL` and `KIBANA_API_KEY` (and the corresponding
Elasticsearch credentials for the `_count` lookup) to be set in `.env`.
On success it prints a JSON summary that includes `dashboard_url`,
`fec_audit_doc_count`, and `lens_fallbacks`. The exit code is `0` on
success, `1` if Kibana credentials are missing, `2` if the dashboard
`_bulk_create` call failed.

## Failure handling

Each Lens panel build is wrapped in `try/except`. If a single panel spec
is rejected by Kibana or raises during construction, that slot is replaced
by a Markdown placeholder so the dashboard layout stays intact and the
remaining panels still ship. Failures are recorded in
`lens_fallbacks` in the run summary so they are visible at a glance.

If the data view itself cannot be created (Kibana down, permissions),
every Lens panel is replaced with a Markdown placeholder and the
dashboard is still created so the URL stays stable.
