# W25C - Error path UX deep audit

Batch 3, axis C. Verifies graceful degradation across the most likely demo failure modes for FE Copilot. Author: Rodrigo Careaga. Date: 2026-05-04.

## Executive summary

Every fetch error path in `frontend/assets/js/` was audited. A new `sanitizeError()` helper was added in `frontend/assets/js/api.js` and wired through the toasts, banners, and inline error renderers that previously rendered `err.message` raw. Internal Python paths, traceback markers, and addresses are stripped, the message is collapsed onto one line, and the result is hard-capped at 200 chars.

A friendly "Kibana not configured or unreachable" toast was added to `/agent-builder.html` so that judges hitting the page in a degraded environment (no `KIBANA_API_KEY`, ngrok tunnel down) see a clear status message instead of a silent dry-run.

The `health.html` warnings region was extended with a friendly-label dictionary (`WARNING_LABELS`) so the `elasticsearch_unavailable` and workflow-missing codes render as actionable sentences, not snake_case tokens.

Smoke result: 8/9 PASS, 1 CAUTION on the git hygiene step (`uncommitted=31` because of these very fixes; pure code/feature checks all PASS, em-dash audit 0 hits over 218 files).

## Per-failure-mode results

### 1. Anthropic credits empty - PASS

Reproduction:
```python
PYTHONPATH=backend .venv/bin/python -c "
from unittest.mock import MagicMock
from app.integrations.claude_client import ClaudeService

mock_client = MagicMock()
class FakeError(Exception): pass
mock_client.messages.create.side_effect = FakeError('Your credit balance is too low to access the API.')

svc = ClaudeService(api_key='real-key-xxx', mock_mode=False)
svc._client = mock_client

from pydantic import BaseModel
class T(BaseModel):
    summary: str
schema = {'type':'object','properties':{'summary':{'type':'string'}}, 'required':['summary']}
out = svc.call_structured(system='S', user='U', schema=schema, output_model=T,
                            mock_payload={'summary':'mock fallback fired ok'})
print('FALLBACK FIRED:', out.summary)
"
```

Result: `claude.fallback_to_mock reason=credits` is logged and the structured output is satisfied from `mock_payload`. The audit log records `mode=fallback` plus `fallback_reason=credits`.

Code refs:
- `backend/app/integrations/claude_client.py:152-182` - the recoverable-error branch detects `"credit balance is too low"`, `"billing"`, `"rate_limit"`, `"429"`, and `"Connection"` substrings and returns the validated `mock_payload` instead of raising.
- `backend/app/agents/pre_meeting.py:76` - passes `mock_payload=prompt.mock_response(company["id"])`.
- `backend/app/agents/post_meeting.py:61, 173` - same pattern for both run paths.
- `backend/app/api/routes_tools.py:255, 301, 326, 355, 379, 571, 693, 903, 1079, 1182, 1413` - every Claude call in the tools router passes a `mock_payload`.

Auxiliary live curl test against the running backend (no special env override needed because `auto_mock` is already true for empty keys):

```
curl -s -X POST http://localhost:8123/api/v1/tools/knowledge-search \
     -H 'Content-Type: application/json' \
     -d '{"query": "How do I configure ELSER?"}'
```

Returns `200` with `{"answer": "Mock fallback: ...", "citations": []}` even when the corpus is empty or the LLM is offline. No 5xx, no toast.

### 2. ngrok tunnel down - PASS (with new toast)

Reproduction: temporarily unset `KIBANA_API_KEY` (or block egress to the Kibana cluster) and reload `/agent-builder.html`.

Result before this batch: the `ab-pill-status` pill flipped to "Dry-run" red but the rest of the page was silent. A judge reading the page had no reason to believe Kibana was configured but unreachable, vs. simply not configured.

Result after this batch:
- `ab-pill-status` shows "Dry-run" with `ab-pill-err`.
- A toast appears at the top of `/agent-builder.html`: "Kibana not configured or unreachable. Agent Builder runs in dry-run mode; the master agent and tool catalogue are still browsable." The toast is throttled to fire once per page load.
- If `/agent-builder/status` itself errors (network kill), the same flow plus a sanitized error string fires the toast.

Code refs:
- `frontend/assets/js/agent-builder.js:156-210` - the new `loadStatus()` body. `_kibanaToastShown` guard prevents the toast spamming on re-renders.
- `backend/app/api/routes_agent_builder.py:65-73` - the `status()` endpoint returns `live=ab.is_live()`; `is_live()` is `False` when the API key is missing or the cluster is unreachable.

The autopilot keeps running because it points all of its iframes at `localhost:8123`, not at the Kibana origin.

### 3. Elasticsearch unreachable - PASS

Verification path:

```
curl -s http://localhost:8123/api/v1/health
# {"status":"ok","service":"fe-copilot"} ALWAYS

curl -s http://localhost:8123/api/v1/health/full | jq '.status, .warnings'
# "yellow" + ["elasticsearch_unavailable", ...] when ES is down
# "green" + [] when ES is up and seeded
```

Result:
- `/api/v1/health` is the simple liveness probe and returns 200/`status:ok` regardless. Confirmed in `backend/app/api/routes_health.py:212-214`.
- `/api/v1/health/full` returns `status="yellow"` plus a `warnings` array containing `elasticsearch_unavailable` whenever `get_es_repo().available` is false (`routes_health.py:255-334`). It never raises.
- `/battlecards.html` falls back to the on-disk seed JSON when ES is unavailable. `frontend/assets/js/battlecards.js:1102-1116` plus `routes_battlecards.py` already handle the missing index with the seed file (also visible in the route file `_match_local` helper at `routes_tools.py:789`).
- `/industries.html` reads the static industries catalogue from disk via `/api/v1/industries`, no ES dependency.
- `/demo-data.html` reads `SCENARIOS` from `routes_demo_data.SCENARIOS`, no live ES dependency for the listing (only for the seed action).
- `/customers.html` Kanban renders the "no records match" empty state when ES is empty.

After this batch the `health.html` warnings banner now translates `elasticsearch_unavailable` to the friendly sentence "Elasticsearch cluster is unreachable. Battlecards, FE Brain, and dashboards run on the on-disk seed fallback." See `frontend/assets/js/health.js:97-124` (`WARNING_LABELS`).

### 4. Kibana 502 (alerting plugin slow or restarting) - PASS

Reproduction:

```
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8123/api/v1/workflows/status
# Always 200, never 5xx
```

Result: `/workflows/status` swallows every Kibana error inside a try/except and reports `rule_status="probe-error: <truncated>"` on the JSON instead of throwing. Code at `backend/app/api/routes_workflows.py:601-637`.

`/workflow-demo.html` paints the rule pill red but the page still renders. The sanitizer wrap on `workflow-demo.js:81-167` makes the on-screen "Status fetch failed" / "Sync failed" / "Fire failed" / "Trigger failed" lines safe.

Retry policy: the autopilot already calls a category-aware `apiPostWithRetry` helper with up to 3 retries plus exponential backoff (visible at `frontend/assets/js/autopilot.js:355-371`). The default `apiPost` does not retry, which is by design (every retryable POST in the demo path goes through `apiPostWithRetry`).

### 5. Browser offline - PARTIAL (documented gap)

Reproduction: open DevTools, Network tab, throttle to "Offline", then click any button on `/index.html`.

Result:
- `apiGet` and `apiPost` now translate the bare `TypeError: Failed to fetch` from `fetch()` into the friendly "Network unavailable - check your connection (GET /xxx)" message before throwing. See `frontend/assets/js/api.js`.
- There is no service worker registered in this project; we do not ship cached pages. A judge running the demo offline will see the friendly error toast on every action but the page itself stays interactive (everything is statically served from `localhost:8123`).
- A documented gap, not a regression. Adding a service worker is out of scope for this batch.

### 6. Naked stack traces - PASS

Audit: every `console.error`, `toast(err.message ...)`, `alert(err.message ...)`, and inline `innerHTML = ... err.message ...` in `frontend/assets/js/` was reviewed. Each render path now goes through `sanitizeError()` (or its inline equivalent that strips paths and caps to 200 chars).

Files modified (12):
- `frontend/assets/js/api.js` (added `sanitizeError`, network-fail translation)
- `frontend/assets/js/agent-builder.js` (Kibana-down toast plus 3 sanitized renders)
- `frontend/assets/js/agent-builder-mini.js` (sanitized inline error)
- `frontend/assets/js/health.js` (sanitizer plus friendly warning labels)
- `frontend/assets/js/workflow-demo.js` (4 sanitized inline errors)
- `frontend/assets/js/demo-data.js` (2 sanitized errors plus toast)
- `frontend/assets/js/industries.js` (sanitized inline error)
- `frontend/assets/js/battlecards.js` (sanitized inline error, switched to console.warn)
- `frontend/assets/js/audit.js` (sanitized table-cell error)
- `frontend/assets/js/app.js` (4 sanitized toasts in the upload + Kibana flows)
- `frontend/assets/js/meeting.js` (4 sanitized toasts in the meeting flows)
- `frontend/assets/js/quick-research-filter.js` (2 sanitized toasts in the calendar flows)

`battlecards.js` console.error was downgraded to console.warn so a routine ES-unreachable startup does not paint the DevTools console with red error noise during the demo.

## Sanitizer contract

```js
sanitizeError(err) -> string
```

- Accepts string, Error, or anything with a `.message`.
- Strips `Traceback ...` chatter, collapses newlines, normalizes whitespace.
- Removes absolute filesystem paths (`/Users`, `/home`, `/var`, `/tmp`, `/opt`, `/root`, `/app`).
- Removes `File "...", line N` markers.
- Removes hex object addresses (`at 0x7f...`).
- Removes `<MyClass object at ...>` repr fragments.
- Hard cap: 200 chars then `...`.
- Falls back to "Unknown error" or "Request failed" rather than ever returning the empty string.

## Smoke result

```
[PASS] step 1: Backend health + pytest 30/30
[PASS] step 2: Elasticsearch indices fec-* + demo-* green
[PASS] step 3: Kibana saved objects (dashboards + tools + agent + .mcp + rule)
[PASS] step 4: MCP server (tools/list = 12, fec_cost_calc tool/call)
[PASS] step 5: Tools REST (compute + knowledge-search; OPTIONS for heavy)
[PASS] step 6: Workflow status + webhook handler
[PASS] step 7: Frontend pages reachable (9/9)
[PASS] step 8: Em/en dash audit -- scanned=218 files, dash hits=0
[FAIL] step 9: Git hygiene -- uncommitted=31 (modified=31, untracked=4)

VERDICT: CAUTION (8 PASS, 1 FAIL on hygiene only)
```

The single failing step is the git hygiene check, which fires because the very fixes documented above are uncommitted. Every runtime, integration, frontend, MCP, and em-dash check passes. Commit + push will flip the verdict to GO.

## What was NOT touched

- The autopilot orchestration.
- Demo scenarios, battlecards, industries, FE Brain corpus.
- Backend Anthropic / Elasticsearch / Kibana integration logic - only the frontend rendering of those failure paths was tightened.
- Teleprompter, demo-script.

## Em-dash / en-dash audit

Re-ran the standalone audit script over `frontend/`, `backend/app/`, and `docs/`. Excluded the prompt files that explicitly reference the unicode characters (`backend/app/agents/prompts/*`) and the smoke/e2e harnesses that test the audit itself (`integration_smoke.py`, `e2e_tests.py`). Hit count: 0.
