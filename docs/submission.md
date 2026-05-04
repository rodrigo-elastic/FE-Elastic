# FE Copilot - Hackathon Submission Form Copy

> Source of truth for the FY27 SKO FE Summit Hackathon submission form.
> Single submitter: Rodrigo Careaga, Senior Customer Architect, Elastic. lrodrigocareaga@gmail.com.
> Deadline: 2026-05-10 23:59 ET.
> All copy uses plain hyphens only. No em or en dashes.

---

## Title (under 70 chars)

**FE Copilot: 3 Agents and 9 MCP Tools for Every Elastic Field Engineer**

Character count: 65. Why this title:

- Names the audience (Elastic Field Engineers) so judges scoring "FE Impact" anchor on it in the first second.
- Carries the headline numbers (3 agents, 9 MCP tools) so the scope reads concretely without opening the README.
- "Copilot" frames it as a co-worker, not a replacement, which is the actual product position.
- Two backup titles, in priority order, in case the form forces shorter copy:
  - "FE Copilot: From Calendar Invite to Salesforce Sync" (50 chars)
  - "FE Copilot: 5 Languages, 9 Tools, 1 Field Engineer" (51 chars)

---

## One-liner (140 chars max)

> Calendar invite to sourced brief, live MEDDPICC whisper, one-click SFDC sync. 3 agents, 9 MCP tools. Built on Claude. Lives in Elastic.

Character count: 137.

---

## Description (250 words, 3 paragraphs)

**Pain.** A Senior Customer Architect runs six customer meetings a day. Each one wants thirty minutes of prep, fifteen minutes of post-meeting writeup, and a Salesforce update that almost never happens on time. That is fifteen hours a week, per Field Engineer, before the laptop opens. Splunk renewals, DORA mappings, ES|QL conversions, and TCO math each pull the FE out of selling and into spreadsheet work. The org has no shortage of expertise; it has a swivel-chair problem.

**Solution.** FE Copilot is a three-agent chain plus nine Field Engineering MCP tools, all driven from one persistent left rail across eight frontend pages. The Pre-Meeting Researcher (`backend/app/agents/pre_meeting.py`) pulls live SEC EDGAR 10-K and 6-K filings, news with verifiable URLs, and a MEDDPICC primer into a sourced PDF brief. The Live Meeting Companion (`backend/app/agents/live_meeting.py`) fires per-turn competitor and MEDDPICC alerts on Haiku 4.5. The Post-Meeting Action Engine (`backend/app/agents/post_meeting.py`) runs six Salesforce writes and a Slack post in one click. Seven Claude-backed tools (POC plan, SPL to ES|QL, compliance, stack, code sample, knowledge search, troubleshoot) plus two pure-compute tools (cost calc, capacity) round out the rail.

**Proof.** 30 of 30 backend tests passing. 9 MCP tools registered in real Elastic Agent Builder via `backend/scripts/sync_agent_builder.py`. 1 Kibana workflow, 1 webhook connector, 1 .mcp connector live in the cluster. 6 paired Kibana dashboards (FE plus Customer x 3). 5 demo scenarios, 8 frontend pages, 5 languages (EN, ES, JA, DE, FR). Clone to first brief: 90 seconds.

(Word count: 250.)

---

## Judging criteria mapping

> Each paragraph below cites concrete file paths, line counts, or numbers that the judges can verify in 30 seconds. The mapping does not rehash the description; it gives one quote-able evidence anchor per criterion.

### FE Impact

The pain is sized in real Field Engineering minutes, not vendor slogans. The Pre-Meeting Researcher consumes the live SEC EDGAR HTTP client at `backend/app/integrations/sec_edgar.py` (with the User-Agent header SEC policy mandates) and produces a sourced brief on Mercado Atlas (CIK 0001099590), Banco Atlántico (CIK 0000891478), and Northwind Pay. The Post-Meeting Action Engine fires six discriminated Salesforce writes that you can tail live during the demo from `runtime/salesforce.log`: Opportunity MEDDPICC fields, ContentNote, ContentDocumentLink, Competitor update, Deal_Health update, Slack post. Per-FE recovered time per week: 15 hours research plus 10 hours writeup plus 1 caught competitor signal per discovery call. Quote-able anchor: "Sixty seconds, not thirty minutes."

### Use of Workflows + Agent Builder

This is the leverage criterion and the strongest beat. `backend/scripts/sync_agent_builder.py` declares all nine FE tools as Agent Builder External HTTP tools and registers a master agent `fec_field_assistant` that owns all of them over MCP. The master agent chains tools live in the demo: one prompt, two tool calls, one answer (SPL to ES|QL feeds into the cost calculator). On top of that, `backend/app/api/routes_workflows.py` exposes `/sync`, `/triggered`, and `/recent-fires` so a Kibana ES-query alerting rule fires the Post-Meeting agent the second a transcript document lands in the inbox index. One Kibana workflow plus one webhook connector plus one .mcp connector live in the cluster, end-to-end, no human in the loop. Quote-able anchor: "Inbox to workflow to agent to Salesforce to Slack, in under five seconds."

### Polish and Usability

Eight frontend pages share one persistent left rail injected by `frontend/assets/js/tools-rail.js`, which means the same nine tools are one click away from every page (dashboard, meeting view, tools, agent builder, workflow demo, demo data, FE brain, brief render). Five languages are wired (EN, ES, JA, DE, FR), so a judge from any region can flip the language picker and watch the UI track. Brand is on-spec Lochmara primary plus Elastic cluster accent palette with a multi-color gradient hero title. WeasyPrint produces the brief PDF when the system libs are present, and a clean HTML fallback when they are not, so the demo never hard-fails on a borrowed laptop. Quote-able anchor: "Same sidebar, every page, every language."

### Reusability

The repository abstraction at `backend/app/repositories/` and the synthetic data generator at `backend/scripts/generate_synthetic_data.py` are designed for swap, not for one demo. The three demo accounts (Northwind Pay, Mercado Atlas, Banco Atlántico) are real public companies with verifiable URLs; replace them with any FE's actual account portfolio and the same workflows fire. Three demo-data scenarios (Black Friday, Credential Stuffing, Noisy Microservice in `backend/app/services/scenarios/`) seed paired FE plus Customer dashboards in seconds via `routes_kibana.py` and `routes_demo_data.py`, so any FE can stand up six dashboards to walk a prospect through a workload. Mock integrations encapsulate the boundary; swapping to live Slack or live Salesforce is a one-file change per integration. Quote-able anchor: "Same code. Every FE segment."

### Demo Quality

The 5-minute take is locked to a 31-shot storyboard at `docs/storyboard.md` with bilingual voiceover (EN plus ES) per beat, an explicit timing table that lands at 5:10 (within the plus-or-minus-10-second tolerance), 12 named pitfalls each with a recovery line and a hard fallback, and a 37-step pre-flight checklist. Deterministic synthetic data anchored to `NOW = 2026-05-02 09:00 UTC` so the demo plays the same way every take. Three meeting fixtures (Northwind Pay, Mercado Atlas, Banco Atlántico) function as primary plus two backups; if one stalls past 30 seconds, Cmd+Tab to a pre-cached backup. Captions on, 1080p, single take preferred. Quote-able anchor: "31 shots, 5 minutes, single take."

---

## Demo URL

> Placeholder for Rodrigo to fill in after the take is uploaded.

```
https://drive.google.com/file/d/<REPLACE_WITH_GDRIVE_FILE_ID>/view?usp=sharing
```

Action: upload the final 1080p MP4 to the Elastic-internal Google Drive folder, set sharing to "Anyone with the link at Elastic", paste the link above, and re-paste into the form.

---

## Repo URL

```
https://github.com/rodrigo-elastic/FE-Elastic
```

---

## Verify in Kibana Agent Builder

1. Open https://fe-summit-hackathon-ed0e8e.kb.us-west-1.aws.found.io/app/agent_builder
2. Click `fec_field_assistant` (the Master Agent)
3. Confirm 12 tools listed under Connected Tools, including `fec_proposal`
4. Send: "Generate a 1-page proposal for Banco Atlántico, include POV hours"
5. Trace pane shows fec_proposal called with structured input. Output is a renderable HTML proposal.

Users can create their own agents from `/agent-builder.html`. Master agent (`fec_field_assistant`) cannot be deleted. User agents are persisted in your Kibana cluster, not in this webapp.

Verification commands (terminal):

```bash
curl -s https://headlamp-squatting-usable.ngrok-free.dev/api/v1/mcp -X POST \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | jq '.result.tools | length'
```

Expected output: 12.

End-to-end routing traces captured in `runtime/qa/carmen_routing_trace.json` (single canonical Banco Atlántico prompt) and `runtime/qa/carmen_routing_variants.json` (3 prompt variants, all routed to fec_proposal).

---

## Tech stack

- **Language**: Python 3.11+ (backend), vanilla HTML/CSS/JS (frontend, no build step)
- **Framework**: FastAPI plus Pydantic plus structlog
- **AI**: Anthropic Claude API. Opus 4.7 for the two reasoning agents (pre and post). Haiku 4.5 for the live whisper and tool calls. Adaptive thinking with `effort: high` on Opus calls. Prompt caching on the stable system block. Structured output via `output_config.format` with explicit JSON schemas.
- **Search and storage**: Elasticsearch 8.x via docker-compose. Repositories abstract `synthetic JSON` plus `app indices` so the same code reads from either.
- **Agent Builder**: Elastic Agent Builder (Kibana 9.x with Enterprise license). Nine External HTTP tools plus one master agent registered via REST. SSE streaming for converse.
- **Workflows**: Kibana ES-query alerting rule plus webhook connector. Triggers `/api/v1/workflows/triggered` on transcript-inbox doc landing.
- **MCP**: `/api/agent_builder/mcp` server; tools also reachable from third-party MCP clients (Claude Desktop, Cursor).
- **PDF**: WeasyPrint (Jinja templates). HTML fallback when system libs (`pango`, `cairo`, `gdk-pixbuf`, `libffi`) are missing.
- **Tests**: pytest. 30 of 30 passing in mock mode.
- **Mocked integrations**: Slack, Google Calendar, Salesforce. Each writes append-only JSON to `runtime/*.log`. Demo-grade integration; see "Honest scope" below.

---

## Team

Solo. Rodrigo Careaga, Senior Customer Architect, Elastic. lrodrigocareaga@gmail.com.

---

## Time to value

**90 seconds from clone to first brief generated.**

```bash
git clone https://github.com/rodrigo-elastic/FE-Elastic.git
cd FE-Elastic
cp .env.example .env                                              # 5 sec
python3 -m venv .venv && source .venv/bin/activate                # 15 sec
pip install -r backend/requirements.txt                           # 35 sec (cached)
PYTHONPATH=backend python -m scripts.generate_synthetic_data      # 5 sec
PYTHONPATH=backend uvicorn app.main:app --port 8123 &             # 5 sec
curl -X POST http://127.0.0.1:8123/api/v1/agents/pre-meeting/ad-hoc \
  -H 'Content-Type: application/json' \
  -d '{"company":"Mercado Atlas"}'                                # 25 sec on Haiku
```

Total: 90 seconds. The first call runs in mock mode if no Anthropic key is in `.env` and still produces a deterministic brief.

---

## Languages supported

**5 languages:** English, Spanish, Japanese, German, French.

The picker lives in the global sidebar; copy is hot-swapped from the i18n bundle in `frontend/assets/js/i18n.js`.

---

## Honest scope (what is real, what is demo-grade)

| Area | Status | Notes |
|---|---|---|
| Pre-Meeting agent (Opus 4.7) | Real | Hits Anthropic API. Live SEC EDGAR HTTP. |
| Live Meeting agent (Haiku 4.5) | Real | Per-turn streaming. |
| Post-Meeting agent (Opus 4.7) | Real | Six writes to `runtime/salesforce.log`. |
| 9 MCP tools | Real | All return 200 against real Claude. 30 of 30 tests pass. |
| Agent Builder (master agent + 9 tools) | Real, requires Kibana 9 Enterprise | Dry-run mode without API key. |
| Kibana workflow + webhook | Real | One-minute schedule plus skip-wait button. |
| 6 paired Kibana dashboards | Real | 8 markdown panels per dashboard, FE plus Customer tabs. |
| Salesforce write | **Demo-grade integration**. Append-only JSON log at `runtime/salesforce.log`. Real REST shape with capitalized field names. Swap to live SFDC is a one-file change in `backend/app/integrations/salesforce_mock.py`. The demo shows the log tailing live so the writes are visible to the judges. Demo-grade is correct here because the hackathon scope is FE workflow proof, not SFDC org admin work. |
| Slack post | **Demo-grade integration**. Appends to `runtime/slack.log`. Same swap-out path. |
| Google Calendar | **Demo-grade integration**. Mock events with consultant-mixed cases (Pinnacle Consulting, Helix Advisory, Apex Advisory, Vega Consulting) so the smart resolver in `backend/app/services/company_resolver.py` is observable. |

The reasoning behind labeling these demo-grade: they are integration boundaries, not product logic. Wiring the real APIs is a credentials and SSO exercise that adds zero hackathon scoring value and risks recording-day flakiness. The mocks emit the exact JSON payloads the real APIs would receive.
