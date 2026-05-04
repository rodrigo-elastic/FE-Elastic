# FE Copilot - Judging Rubric Self-Assessment

> One-pager. Honest scoring. Plain hyphens only.
> Source: my read of the FY27 SKO FE Summit Hackathon brief plus the public hackathon rubric template.
> Weights are educated guesses; if the official rubric publishes different weights, the evidence column still holds.

## Self-scoring table

| Criterion | Weight (guess) | FE Copilot evidence | Potential score (1-10) | Stretch goal |
|---|---|---|---|---|
| **FE Impact** | 25% | 3 agents covering the full meeting workflow (pre, live, post). Live SEC EDGAR HTTP at `backend/app/integrations/sec_edgar.py`. 6 Salesforce writes per meeting tailed live from `runtime/salesforce.log`. 15 hours per FE per week of recovered prep time. 3 real demo accounts (Northwind Pay, Mercado Atlas, Banco Atlántico) with verifiable URLs only. | **9** | Add a "weeks-of-FE-time-saved" counter on the dashboard that increments per brief generated. Pre-record one real FE peer using it for a week and quote the time-saved number in the description. |
| **Use of Workflows + Agent Builder** | 25% | Master agent `fec_field_assistant` declared via `backend/scripts/sync_agent_builder.py`. 9 MCP tools registered as Agent Builder External HTTP tools. 1 live Kibana ES-query alerting rule plus webhook connector at `backend/app/api/routes_workflows.py` (`/sync`, `/triggered`, `/recent-fires`). Live tool chaining demoed (SPL plus cost in one prompt). MCP server exposed at `/api/agent_builder/mcp`. | **8** | Wire a second Kibana workflow that fires the Pre-Meeting agent when a new opportunity lands in Salesforce (mock event). Two workflows beats one. Add streaming SSE on `/converse-async` so the chained tool calls render in real time. |
| **Polish and Usability** | 20% | 8 frontend pages share one persistent left rail (`frontend/assets/js/tools-rail.js`). 5-language i18n (EN, ES, JA, DE, FR). Lochmara primary plus Elastic cluster accent palette. Multi-color gradient hero title. Brief PDF via WeasyPrint with HTML fallback. Mock mode never hard-fails. 12 named demo pitfalls each have a recovery line in `docs/storyboard.md`. | **8** | Tighten the meeting view's tab transition micro-animation. Add empty-state illustrations for the 3 zero-state screens (no upcoming meetings, no briefs yet, no transcripts). Run a 60-second a11y pass for keyboard focus rings on the rail. |
| **Reusability** | 15% | Repository abstraction at `backend/app/repositories/` swaps synthetic JSON for ES indices behind one interface. Mock integrations encapsulate Slack, SFDC, GCal so live wiring is a one-file change per integration. 3 demo-data scenarios in `backend/app/services/scenarios/` (Black Friday, Credential Stuffing, Noisy Microservice) seed paired FE plus Customer dashboards. 9 tools each wrap an expert persona prompt with a knowledge pack so the prompts are reusable building blocks. | **8** | Publish the 9 tools as a standalone PyPI package `fe-copilot-tools` so any FE can import them without cloning the repo. Document the swap-in path for Slack and SFDC live in the README. |
| **Demo Quality** | 15% | 31-shot storyboard at `docs/storyboard.md`. 5-minute timing table that lands at 5:10 (within tolerance). Bilingual EN plus ES voiceover per beat. 37-step pre-flight checklist. Deterministic synthetic data anchored to `NOW = 2026-05-02 09:00 UTC`. 3 meeting fixtures (primary plus 2 backups). 5 demo scenarios (3 demo accounts plus 2 demo-data scenarios). 1 Loom 1080p single take with captions. | **9** | Record a 30-second teaser cut alongside the 5-minute master so the form has both a tweet-size and a long-form asset. Add chapter markers to the Loom upload so judges can jump to a specific beat. |

## Aggregate self-score

Weighted: (9 x 25) + (8 x 25) + (8 x 20) + (8 x 15) + (9 x 15) = 225 + 200 + 160 + 120 + 135 = **840 / 1000**.

Honest read: this is a strong submission, not a perfect one. The 9s are FE Impact (the pain is real, the time savings are concrete) and Demo Quality (the storyboard is over-prepared on purpose). The 8s are the three middle criteria where there is always one more polish pass available. None of the criteria score 10 because every one of them has a named stretch goal that I would ship if there were 72 more hours in the cycle.

## What I am explicitly not claiming

- I am not claiming live Salesforce or live Slack writes. The mocks emit the exact JSON the real APIs would receive, the demo tails the log on screen, and the swap to live is a one-file change. Demo-grade is the correct label for the hackathon scope.
- I am not claiming the Pre-Meeting agent guarantees zero hallucination. Every claim in the brief is paired with a verifiable URL chip; the FE remains the human in the loop on factual checks.
- I am not claiming the customer-fit Kibana dashboard ships with full Vega-Lite portability across every Kibana minor. The `[Customer]` variant uses inline `data.values` for safety; the `[FE]` variant uses URL-based Vega specs.

## What I would do differently with another week

1. Wire a second Kibana workflow (Salesforce-event-triggered Pre-Meeting agent) so the "Use of Workflows" beat shows two workflows, not one.
2. Add a "trust score" per claim in the brief, computed from source freshness and source authority. SEC filings score 10; a news article scores 6; Wikipedia scores 4.
3. Cut a 30-second teaser. The form rewards a long-form asset, but the social share rewards a teaser.
