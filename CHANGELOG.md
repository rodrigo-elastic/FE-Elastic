# Changelog

All notable changes to FE Copilot are recorded here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); version numbers follow semantic versioning.

---

## [1.0.0-hackathon] - 2026-05-05

First public release. Submission for the **Elastic FY27 SKO FE Summit Hackathon** (deadline 2026-05-10). Built solo over 30 days by Rodrigo Careaga, Senior Customer Architect at Elastic. MIT licensed.

### What FE Copilot is

A self-hosted portal that gives Solutions Architects and Customer Architects context-driven AI agents grounded in their own Elastic FE knowledge. Fourteen MCP tools, three agents (pre-meeting brief, post-meeting recap, field assistant), two Kibana Workflows, 31 battlecards, 20 industries, 8 demo scenarios, 5 languages.

### Added

#### Agents and tools (14 MCP tools, 13 personas)

- **Marta** - Senior Solutions Architect persona for `fec_poc_plan`. Anchors POV plans to verbatim transcript quotes; phases the work so the first deliverable lands by Week 2.
- **Diego** - Senior Search Engineer persona for `fec_spl_to_esql`. Translates Splunk SPL into ES|QL with idiom-aware rewrites.
- **Priya** - Compliance & Risk persona for `fec_compliance`. Maps customer obligations (DORA, HIPAA, GDPR, FedRAMP) to Elastic capabilities with audit-ready evidence.
- **Aiko** - Solution Architect persona for `fec_stack_extract`. Pulls competing stack components from a transcript and labels them as keep / replace / coexist.
- **Kenji** - Software Engineer persona for `fec_code_sample`. Generates working Elastic client snippets in Python / Go / Java / Node.js / .NET.
- **Lyra** - Pricing Strategy persona for `fec_cost_calc`. Compares Elastic vs Splunk / Datadog at a given GB-per-day with verified vs estimate badges per line.
- **Mei** - Capacity Planner persona for `fec_capacity`. Sizes Elasticsearch tiers (hot/warm/cold/frozen), shard counts, JVM heap.
- **Ravi** - Knowledge Search persona for `fec_knowledge_search`. Hybrid retrieval over 3,800 Elastic doc chunks with cited answers.
- **Sloane** - Competitive Strategist persona for `fec_compare`. Side-by-side comparison across 31 battlecards sorted by marketshare.
- **Auro** - Master Orchestrator persona for `fec_orchestrator`. Routes a free-form FE question to the right specialists and synthesizes their structured output.
- **Carmen** - Sr. Proposal Lead persona for `fec_proposal`. Generates one-page customer proposals with scope, success criteria, and pricing.
- **Sage** - Renewal Defender persona behind the customer dashboard view. Drafts retention plays from risk signals (usage drop, exec change, support escalation).
- **Astrid** - Senior Platform Architect persona for `fec_deploy_validator` (W29B). Audits Elastic cluster configs and flags antipatterns with severity-ranked remediation.
- **Lina** - Senior POV Operations Lead persona for `fec_pov_health` (W30). Distinguishes conversion signals (multi-team logins, SLOs, alerting rules, dashboards) from churn signals (ingest stalled, default config, single-user). Returns stage_assessment, confidence_score, strengths, risks, next_best_actions, days_to_decision_estimate.

#### Frontend pages

- `/` - Portal home with 14 tool chips, recent meetings list, autopilot launcher.
- `/quick-research.html` - 45-second autopilot demo that drives 9 tool sections silently.
- `/workspace.html` - One card per customer with horizontal stage-coded artifact timeline. Replaces the legacy Kanban; positioned explicitly as synthesizer, not CRM. Salesforce remains the system of record.
- `/customers.html` - 3-layer redirect (HTTP-equiv, JS, manual link) preserving query string and hash. Legacy URL kept working.
- `/meeting.html` - Pre-meeting / post-meeting / live-meeting agent panels with persistent conversation history per agent.
- `/agent-builder.html` - 14 preset bundles plus per-agent tool picker; mini Field Assistant chat.
- `/battlecards.html` - 31 battlecards ranked globally by marketshare, not alphabetical chaos.
- `/industries.html` - 20 industries covering 80 percent of Elastic customers.
- `/fe-brain.html` - Ravi Knowledge Search with 3,800 cited Elastic doc chunks.
- `/tools.html` - All 14 tools in one panel, deep-linkable.
- `/workflow-demo.html` - Two Kibana Workflow recipes (post-meeting Salesforce sync; renewal defender) with live status.
- `/demo-data.html` - 8 pre-seeded scenarios (FSI fraud, HIPAA audit, GDPR audit, government CDM, Black Friday, credential stuffing, supply chain, noisy microservice).
- `/health.html` - Judge-facing system health: build SHA, MCP tool count, FE Brain chunk count, registered Workflows, demo scenarios.
- `/pov-health.html` (W30) - Standalone POV Health workspace with hero, demo summary loader, history grouped by customer, Lina output renderer.

#### MCP and Agent Builder

- 14 `fec_*` tools registered in Kibana Agent Builder via `backend/scripts/sync_agent_builder.py`.
- Master agent "FE Copilot" with three specialists (RFP Responder, Migration Specialist, Compliance Pursuit) and 14 preset bundles in the local Agent Builder UI.
- Native MCP Streamable HTTP server at `/api/v1/mcp`, JSON-RPC over single POST per the MCP 2025-03-26 spec.

#### Workflows

- `infra/workflows/post-meeting-sync.yaml` - Transcript drops in, recap agent runs, Salesforce activity record + MEDDPICC fields update, follow-up email queued.
- `infra/workflows/renewal-defender.yaml` - Risk-signal cluster fires, Sage drafts retention play, Slack DM to AE.

#### Internationalization

- Five locales: English (default), Spanish, Japanese, German, French.
- Locale files at `frontend/assets/i18n/<lang>.json`.
- All user-facing strings keyed; no untranslated raw text in production paths.

#### Quality gates

- 30 pytest tests covering agents, repositories, services, integrations.
- Ruff lint, Python syntax check (compileall), em-dash / en-dash forbid grep across `backend/`, `frontend/`, `docs/`.
- Integration smoke (9 steps: backend health + pytest, ES indices, Kibana saved objects, MCP server, Tools REST, Workflow webhook, frontend pages, dash audit, git status). Emits GO / CAUTION / NO-GO verdict.
- GitHub Actions CI workflow runs pytest + ruff + dash audit + integration smoke on every push and PR. Status badge in README.

#### Documentation

- `README.md` - 30-second tour, full architecture, fork instructions, demo URLs.
- `docs/video-script-v3-elastic-voice.md` - 3-minute submission video script in verified Elastic vocabulary (Kulkarni, Exner, Banon quotes; SA/CA JD phrasing; "Proof of Value" not "POC"; "Agent Builder" not "Elastic Cloud Agent Builder").
- `docs/demo-trailer-30s.md` and `docs/demo-trailer-campy-30s.md` - Two 30-second trailer cuts (serious for LinkedIn / submission post; campy infomercial for Slack peer post).
- `docs/trailer-production-guide.md` - Single-session editing guide cutting both 30s trailers from the same 3-minute master.
- `docs/fe-impact-math.md` - Line-by-line cost model behind the "six hours per FE per week" claim. Anchored on Salesforce State of Sales. Conservative by 28 percent against the underlying model.
- `docs/fork-it-in-30-minutes.md` - Seven-step fork path for any Elastic SA / CA. File paths, env wiring, persona swaps, Agent Builder sync, smoke verification.
- `docs/architecture.md` - System diagram, data boundaries, complementary-not-competing positioning vs Klue / Highspot / Salesforce / Gainsight.
- `docs/submission.md` - Submission form copy and gDrive demo link.
- `docs/submission-readiness.md` - 12-section checklist used as single source of truth for go / no-go.
- `docs/integration-smoke-report.md` - Latest auto-generated smoke report.
- `HANDOFF.md` - Single-page handoff for the next FE who picks this up.

### Notable design decisions

- **Synthesizer, not CRM.** Salesforce remains the system of record. FE Copilot is the layer that fans out to Klue, Highspot, Gainsight, and Salesforce so the FE answers in one place. Documented in `docs/architecture.md` (Complementary integration matrix).
- **Mock fallback chain.** When Anthropic credits are exhausted or rate limits hit, every tool degrades to a deterministic structured fixture so the demo always works. Fixtures live next to the production prompts.
- **Persona-led prompts.** Each tool is a one-shot Claude call with a 30-line persona system prompt that encodes years of FE field experience, not a generic assistant. Personas are inline so anyone can audit them in `backend/app/agents/prompts/tools.py`.
- **Forced output schema.** Every tool uses Anthropic `output_config.format` to force a Pydantic-validated JSON shape. No free-form text leaks into UI.
- **No em-dashes.** A grep gate rejects `—` and `–` everywhere in the repo. Reads as obviously AI-generated; ASCII `-` only.

### Known limitations (called out by design)

- The cost calculator uses public list pricing for Splunk and Datadog. Real-world deals discount; numbers are demo-grade and labeled.
- The customer dashboard view in Kibana ships disabled by default. Enable per-account via `backend/app/api/routes_kibana.py`.
- The deploy validator (Astrid) and POV health monitor (Lina) ship with mock fallbacks tuned to the canned demo summaries. Adapt `mock_response()` for new accounts.
- Salesforce sync runs through the `salesforce-update.yaml` Workflow only; no direct Salesforce SDK calls in the Python backend (boundary is intentional).

### Source attribution

Every Elastic-vocabulary claim in `docs/video-script-v3-elastic-voice.md` and supporting docs traces to a public URL: Elastic SA/CA job descriptions, Q2/Q3 FY26 earnings press, Agent Builder GA press release (2026-01-22), Kulkarni at AWS re:Invent 2025, Ken Exner at Help Net Security 2026-01-23, Elastic Security Labs 2026-02. Source ledger in section 9 of the v3 video script.

---

## Pre-1.0 development log

Thirty days of solo development from 2026-04-05 to 2026-05-05. Key waves:

- **W21** - Customers Kanban cleanup; per-customer color tag across views.
- **W22** - Battlecards ranked globally by marketshare; agent-builder bundles.
- **W23** - QA overnight batches: a11y, compliance, e2e, perf.
- **W24** - Dark mode parity, link crawler, command palette, `?` shortcuts dialog, 31 battlecards + 20 industries.
- **W25** - Data integrity, API contracts, error paths, retry / timeout policy.
- **W26** - Copy QA EN, i18n round-trip, SEO / social meta, demo data freshness.
- **W27** - Deps, secrets, build repro, docs lint.
- **W28** - Hero polish, customer legend, About maker, mobile, personas, audit, 30s trailer.
- **W29A** - Workspace redesign (one card per customer, horizontal stage-coded timeline). Positioned as synthesizer, not CRM.
- **W29B** - Deployment Validator (Astrid) as 13th MCP tool with structured output and severity-ranked findings.
- **W30** - POV / Trial Health Dashboard (Lina) as 14th MCP tool, dedicated `/pov-health.html`, Agent Builder bundles updated, smoke bumped 13 -> 14.

Full commit history at `git log --oneline`.
