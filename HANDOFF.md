# FE Copilot - Handoff Notes

Snapshot taken on **2026-05-03** for moving the project from the personal laptop to the work laptop (where Elastic Cloud Enterprise + Agent Builder are available).

Hackathon: FY27 SKO FE Summit. Submission deadline: **2026-05-10 23:59 ET**. Single submitter (Rodrigo Careaga). Email: rodrigo.careaga@elastic.co.

---

## What is already built

### Three core agents
- `backend/app/agents/pre_meeting.py` - account brief generator (SEC EDGAR live API path retained for any future real public-company demo; current fictional accounts have no CIK; news fixtures with fictional URLs, MEDDPICC primer, BANT, Force-field analysis).
- `backend/app/agents/live_meeting.py` - per-turn alerts (competitor mentions, MEDDPICC capture, unanswered questions, risk).
- `backend/app/agents/post_meeting.py` - summary, action items, MEDDPICC update, follow-up email draft, full Salesforce sync (six writes: Opportunity MEDDPICC fields, ContentNote, ContentDocumentLink, Competitor update, Deal_Health update, Slack post).

### Seven FE technical tools (all live, returning 200 against real Claude)
1. POC Plan generator (`/api/v1/tools/poc-plan/{meeting_id}`)
2. SPL to ES|QL translator (`/api/v1/tools/spl-to-esql`)
3. Compliance mapper (`/api/v1/tools/compliance-mapping`)
4. Tech stack extractor (`/api/v1/tools/stack-extract`)
5. Code sample generator (`/api/v1/tools/code-sample`)
6. Cost calculator (Elastic vs Splunk vs Datadog) (`/api/v1/tools/cost-calc`)
7. Capacity planner (`/api/v1/tools/capacity`)

Each Claude-backed tool has an expert persona prompt with knowledge pack: Marta (POV architect, 12y), Diego (ex-Splunk consultant, 200+ migrations), Priya (ex-PwC compliance auditor, CISA + CISSP), Aiko (FE Discovery Analyst), Kenji (SDK cookbook author). All in `backend/app/agents/prompts/tools.py`.

### Frontend
- `frontend/index.html` - dashboard with three entry modes (Quick Research, Transcript paste, Calendar).
- `frontend/tools.html` - seven tool panels.
- `frontend/assets/js/tools-rail.js` - persistent global left sidebar that shows Dashboard + 7 Tools on every page.
- 5-language i18n (English, Spanish, Japanese, German, French).
- Elastic brand: Lochmara primary + cluster accent palette. Multi-color gradient on hero title.

### Infra and integrations
- `backend/app/integrations/google_calendar_mock.py` - mock GCal events with fictional consultant-mixed cases (Pinnacle Consulting, Helix Advisory, Apex Advisory, Vega Consulting) for the smart resolver demo.
- `backend/app/services/company_resolver.py` - smart resolver that filters internal Elastic, deprioritises 17+ consulting firms, falls back to title-keyword.
- `backend/app/integrations/sec_edgar.py` - real SEC EDGAR HTTP client (User-Agent set per SEC policy).
- `backend/app/integrations/salesforce_mock.py` - REST-shaped SFDC mock with capitalized fields and `runtime/salesforce.log`.
- `backend/app/integrations/elasticsearch_repo.py` - ES app indices for accounts, briefs, transcripts, audit.

### Tests
- 30 tests, 100% passing in mock mode. Run with: `PYTHONPATH=backend .venv/bin/python -m pytest backend/tests -q`.
- Conftest isolates tests to `tmp_path` for `runtime_dir` and unreachable ES URL.

### Three demo accounts (fictional, no real customer data)
- Northwind Pay (fintech, EU banking licence Q3 2025, no CIK) - all news, employees, and figures are illustrative demo content.
- Mercado Atlas (LATAM e-commerce + fintech, no CIK) - all news, employees, and figures are illustrative demo content.
- Banco Atlántico (Spanish banking group, no CIK) - all news, employees, and figures are illustrative demo content.

---

## What is scaffolded but pending live wiring (Agent Builder)

Elastic Agent Builder integration is the biggest missing piece for the "Use of Workflows + Agent Builder" judging criterion.

Files already written (run in dry-run mode locally; need a real Kibana 9.x with Enterprise license to go live):
- `backend/app/integrations/agent_builder.py` - Kibana REST client for `/api/agent_builder/{tools, agents, skills, converse}`.
- `backend/scripts/sync_agent_builder.py` - declares the seven FE Copilot tools as Agent Builder External HTTP tools and creates a master agent `fec_field_assistant` that owns all seven.
- `backend/app/api/routes_agent_builder.py` - FastAPI surface with `/agent-builder/{status, tools, agents, sync, converse}`.
- `KIBANA_API_KEY` field added to `.env.example` and `app/config.py`.

Endpoints work in dry-run mode today:
```bash
curl http://127.0.0.1:8123/api/v1/agent-builder/status   # live: false (no API key)
curl -X POST http://127.0.0.1:8123/api/v1/agent-builder/sync   # logs payloads, returns ok:true per tool
```

---

## Transfer to the work laptop

Recommended path: **private GitHub repo** (Elastic-internal or your personal). The project is not yet a git repo; initialising and pushing to a private origin is the cleanest way to keep iterating without re-zipping.

### 1. Rotate the Anthropic key before pushing anywhere
The current `.env` has a real `sk-ant-*` key in line 2. The `.env` file is gitignored so it will not be committed, but rotate the key in the Anthropic console anyway as a precaution before transferring the laptop folder.

### 2. Initialise git on the personal laptop
```bash
cd /Volumes/Workspace/Claude/Projects/FE-Elastic
git init
git add .
git status   # confirm .env, runtime/, .venv/ are NOT staged
git commit -m "Initial commit: FE Copilot hackathon submission baseline"
```

### 3. Push to a private remote
Either GitHub (`gh repo create fe-copilot --private --push`) or Elastic-internal Bitbucket. Then on the work laptop:
```bash
git clone <remote-url>
cd fe-copilot
cp .env.example .env   # then fill in ANTHROPIC_API_KEY and KIBANA_API_KEY
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
PYTHONPATH=backend python -m scripts.generate_synthetic_data
PYTHONPATH=backend uvicorn app.main:app --reload --port 8123
```

### 4. (Alternate) Plain folder transfer
If git is not an option:
```bash
# On personal laptop
cd /Volumes/Workspace/Claude/Projects/FE-Elastic
rm -rf .venv runtime/* .pytest_cache __pycache__ backend/**/__pycache__
zip -r fe-copilot.zip . -x ".env"   # exclude live secret
# Move the zip to the work laptop, unzip, then rebuild the venv there.
```

---

## Next steps on the work laptop (priority order)

### P0 - Light up Agent Builder against real Kibana
1. Bump `infra/docker-compose.yml` Kibana image from `8.13.4` to a stack 9.x release that ships Agent Builder, OR point `KIBANA_URL` at your work Elastic Cloud Enterprise deployment.
2. Generate a Kibana API key with privileges for `agent_builder:*`. Put it in `.env` as `KIBANA_API_KEY=...`.
3. Bring the stack up: `docker compose -f infra/docker-compose.yml up -d`.
4. Run the sync: `PYTHONPATH=backend python -m scripts.sync_agent_builder`. Confirm response says `ok: true` for all seven tools and the master agent.
5. Open Kibana in the browser: `Stack Management -> Agent Builder -> Tools` and confirm the seven `fec_*` tools appear. Open the `fec_field_assistant` agent and chat with it.
6. If Kibana cannot reach our backend at `host.docker.internal:8123`, expose the backend via ngrok (`ngrok http 8123`) and update `BACKEND_BASE` at the top of `backend/scripts/sync_agent_builder.py` to the ngrok URL, then re-run sync.

### P1 - Wire Agent Builder into the FE Copilot UI
1. Add an "Agent Builder" entry in the persistent sidebar (`frontend/assets/js/tools-rail.js` PAGES list).
2. Add a chat panel that calls `POST /api/v1/agent-builder/converse` and renders streaming responses. Use SSE if available (`/converse-async` endpoint) for the demo wow factor.
3. Demo flow for the video: ask the master agent "I have a Splunk query, translate it to ES|QL and tell me the cost of running this in Elastic at 200 GB/day for 12 months." It should chain `fec_spl_to_esql` and `fec_cost_calc`.

### P2 - Lock in the demo
1. Re-record any demo screenshots that have stale data.
2. Write the 5-minute video script (see the structure I drafted: 0:00 hook, 1:25 pre-meeting, 2:15 live, 3:15 post + SF, 4:25 tools rail, 5:00 Agent Builder + close).
3. Record with Loom or QuickTime, 1080p, captions on. Upload to gDrive shared internally at Elastic.
4. Submit the link via the hackathon form before midnight ET on May 10.

### P3 - Polish leftovers (only if time allows)
1. Workflows: register one Kibana Workflow that triggers `fec_post_meeting` when a transcript file lands in a watched index. (Demonstrates "agents trigger workflows and workflows invoke agents".)
2. MCP server: expose the seven tools via `/api/agent_builder/mcp` so a third-party MCP client (Claude Desktop, Cursor) can use them.
3. Battlecards page: there is a `routes_battlecards.py` endpoint already; finish the UI surface if time allows.

---

## Run and test cheat sheet

```bash
# Activate env
source .venv/bin/activate

# Run backend (serves frontend at /)
PYTHONPATH=backend uvicorn app.main:app --reload --port 8123

# Run all tests
PYTHONPATH=backend python -m pytest backend/tests -q

# Generate synthetic data
PYTHONPATH=backend python -m scripts.generate_synthetic_data

# Smoke test a tool endpoint
curl -s -X POST http://127.0.0.1:8123/api/v1/tools/cost-calc \
  -H "Content-Type: application/json" \
  -d '{"ingest_gb_day":120,"retention_months":12,"current_spend_annual_usd":1500000}' | jq .

# Sync tools to Agent Builder (dry-run if no KIBANA_API_KEY)
PYTHONPATH=backend python -m scripts.sync_agent_builder
```

---

## Files you will most likely edit on the work laptop

| Area | File |
|---|---|
| Bump Kibana version | `infra/docker-compose.yml` |
| Add KIBANA_API_KEY | `.env` |
| Agent Builder client | `backend/app/integrations/agent_builder.py` |
| Tool / agent definitions for sync | `backend/scripts/sync_agent_builder.py` |
| Backend HTTP route reachable by Kibana | `BACKEND_BASE` constant in `sync_agent_builder.py` |
| Sidebar add new entry | `frontend/assets/js/tools-rail.js` (PAGES list) |
| Chat panel for converse | new file: `frontend/assets/js/agent-builder-chat.js` |
| Expert prompt tweaks | `backend/app/agents/prompts/tools.py` |

---

## Known gotchas

- **Port 9202 (ES) and 5603 (Kibana)** in docker-compose are non-default to avoid conflicts with other ES clusters running locally.
- **WeasyPrint** needs `pango cairo gdk-pixbuf libffi` (macOS: `brew install`); without these the brief PDF falls back to HTML.
- **Tests assume mock mode** via conftest forcing `ANTHROPIC_API_KEY=""`. Run with the real key only outside pytest.
- **Salesforce mock** writes to `runtime/salesforce.log` per call, with `_action` discriminator. Inspect with `tail -f runtime/salesforce.log`.
- **Audit log** at `runtime/audit.jsonl` for every Claude call (token counts, model, mock vs live).
- **SEC EDGAR** requires the User-Agent header per SEC policy; already set in `sec_edgar.py`.

---

## Status as of handoff

- 30/30 backend tests passing
- 11+ API endpoints live (3 agents + 7 tools + agent-builder + calendar + briefs + audit + meetings + salesforce + battlecards + health)
- Frontend dashboard + tools page both running on port 8123
- Persistent sidebar visible from every page
- Anthropic key in `.env` (rotate before transferring)
- Elastic Agent Builder: scaffolded, needs Kibana 9 + Enterprise to go live
- Demo data: fictional accounts (Northwind Pay, Mercado Atlas, Banco Atlántico) with illustrative .example URLs only
- Languages: English, Spanish, Japanese, German, French
