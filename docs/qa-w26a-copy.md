# QA W26A: English copy audit

> Auto-generated: 2026-05-04
> Pass: Opus Max-effort copy edit across user-facing English copy.
> Scope: README.md, docs/submission.md, docs/architecture.md, docs/teleprompter.md, docs/video-script-v2.md, docs/compliance.md, docs/demo-script.md, frontend/*.html, frontend/assets/js/*.js (i18n EN block plus visible strings).

## Summary

| Metric | Count |
|---|---|
| Files audited | 22 (7 docs + 13 HTML pages + 2 JS bundles with user-visible copy) |
| Em-dash hits | 0 |
| En-dash hits | 0 |
| Marketing fluff hits | 0 (none found of: leading, world-class, cutting-edge, best-in-class, next-generation, revolutionary, game-changing, synergy, robust, powerful filler, exciting, thrilled) |
| Body-copy exclamation points | 0 (only badge image markdown in README, which is structural) |
| Customer-name leaks | 0 (no Revolut, Santander, Mercadolibre, KPMG, Accenture, Deloitte, Capgemini, Zara, Ray-Ban, Globex, Acme) |
| Stale numbers fixed | 23 |
| Stale license refs fixed | 6 (Apache 2.0 -> MIT) |

## Per-file pass/fail

| File | Status | Notes |
|---|---|---|
| README.md | PASS (after fix) | Tool count 9->12, page count 8->13, scenarios 5->8, brain chunks 160->3837, persona list extended to 10, removed stale "Twelfth MCP tool: fec_proposal" roadmap item. |
| docs/submission.md | PASS (after fix) | All 9-MCP-tool refs to 12, 8-pages to 13, related body text aligned. |
| docs/architecture.md | PASS (after fix) | Mermaid diagram 7+2->10+RAG+orchestrator (12 total), pages 8->13, brain 160->3837, persona list aligned. |
| docs/teleprompter.md | PASS (after fix) | Brain chunks "nine hundred fifty two" -> "thirty eight hundred", "Eleven personas" -> "Ten personas", "Apache 2.0" -> "M I T license", "Eleven MCP tools" -> "Twelve MCP tools", "Five scenarios"/"Ten paired" -> "Eight scenarios"/"Eight paired". |
| docs/video-script-v2.md | PASS (after fix) | "thirteen hundred chunks" -> "thirty eight hundred", footnote 1300 -> 3837, "Apache two point oh" -> "M I T license" (twice). |
| docs/compliance.md | PASS | Already clean. No changes required. |
| docs/demo-script.md | PASS (after fix) | "Apache 2.0" -> "MIT License" (3x), "Eleven personas" -> "Ten personas" (3x), "Eleven MCP tools" -> "Twelve MCP tools", chunks "four hundred seven" -> "thirty eight hundred", "Five scenarios"/"Ten paired" -> "Eight scenarios"/"Eight paired". |
| frontend/index.html | PASS | i18n keys point at correct counts (12 tools, 31 battlecards, 20 industries, 8 scenarios, 3837 chunks). |
| frontend/tools.html | PASS (after fix) | "Eight utilities" -> "Twelve utilities" with the full list spelled out. |
| frontend/agent-builder.html | PASS | No stale claims. |
| frontend/audit.html | PASS | No stale claims. |
| frontend/battlecards.html | PASS | No stale claims. |
| frontend/customers.html | PASS | No stale claims. |
| frontend/demo-data.html | PASS | No stale claims. |
| frontend/fe-brain.html | PASS | No stale claims. |
| frontend/health.html | PASS | No stale claims. |
| frontend/industries.html | PASS | No stale claims. |
| frontend/meeting.html | PASS | No stale claims. |
| frontend/quick-research.html | PASS | No stale claims. |
| frontend/workflow-demo.html | PASS | No stale claims. |
| frontend/assets/js/i18n.js | PASS | EN block consistent with verified counts. |
| frontend/assets/js/autopilot.js | PASS (after fix) | "Apache 2.0. Eleven personas." -> "MIT License. Ten personas." Health caption "twenty battlecards by vertical" -> "thirty one battlecards across four verticals". |

## Verifications (counts traced to source)

| Claim | Source of truth | Verified value |
|---|---|---|
| 12 MCP tools | `backend/app/api/routes_mcp.py` `TOOLS = [...]` | 12 (poc_plan, spl_to_esql, compliance, stack_extract, code_sample, cost_calc, capacity, knowledge_search, troubleshoot, compare, orchestrator, proposal) |
| 31 battlecards | `data/seed/battlecards.json` | 31 |
| 20 industries | `data/seed/industries.json` | 20 |
| 8 demo scenarios | `backend/app/api/routes_demo_data.py` `SCENARIOS` | 8 (black_friday, credential_stuffing, noisy_microservice, gdpr_audit, supply_chain_attack, fsi_banking_fraud, healthcare_hipaa_audit, government_cdm) |
| 8 paired dashboards | `backend/app/services/scenarios/*.py` `CUSTOMER_DASHBOARD_ID` | 8 paired (16 total dashboards) |
| 3837 fec-knowledge chunks | `docs/integration-smoke-report.md` row 2 | 3837 |
| 13 frontend HTML pages | `ls frontend/*.html` | 13 (agent-builder, audit, battlecards, customers, demo-data, fe-brain, health, index, industries, meeting, quick-research, tools, workflow-demo) |
| 5 languages | `frontend/assets/js/i18n.js` `I18N_LOCALES` | 5 (en, es, ja, de, fr) |
| 10 named personas | `backend/app/api/routes_mcp.py` Persona: lines | 10 (Marta, Diego, Priya, Aiko, Kenji, Mei, Ravi, Sloane, Auro, Carmen) |
| 2 Kibana workflows | `backend/app/api/routes_workflows.py` | 2 (post-meeting transcripts, orphan high-impact action items) |
| MIT License | `LICENSE` first line | "MIT License" (NOT Apache 2.0) |

## Fluff words searched (none found)

Pattern: `\b(leading|world-class|cutting-edge|best-in-class|next-generation|revolutionary|game-changing|synergy|synergies|powerful|robust|exciting|thrilled)\b`

Single hit was `decimal-leading-zero` in `frontend/assets/css/battlecards.css` (CSS counter style, not user copy). Excluded.

## Customer-name compliance

Approved fictional set used throughout: Northwind Pay, Banco Atlantico, Mercado Atlas, Atlas Health, Federal Demonstration Agency, Helix Bank, Atlas Eyewear, Helix Advisory, Pinnacle Consulting, Apex Advisory, Vega Consulting.

No leaks of disallowed names (Revolut, Santander, Mercadolibre, KPMG, Accenture, Deloitte, Capgemini, Zara, Ray-Ban, Globex, Acme) in user-facing copy.

Note (out of scope): `runtime/audit.jsonl` does contain historical company_id values "revolut" and "mercado-libre" from earlier dev runs. The runtime/ tree is gitignored and not user-facing. No edit applied per task scope ("backend code is out of scope, this is copy only").

## Em-dash / en-dash audit

`grep -rln $'\xe2\x80\x94' frontend/ docs/<scope> README.md` -> 0 hits.
`grep -rln $'\xe2\x80\x93' frontend/ docs/<scope> README.md` -> 0 hits.

Other docs/ files outside this audit (qa-w24b-dark-mode.md, qa-w25b-api-contracts.md, storyboard.md, i18n.md, badges.md) still contain em-dashes; these are out of the W26A scope and were not edited.

## Voice consistency

Apple-style spot-checks pass:

- README "30-second tour" / "30-second elevator": concrete numbers, no exclamation points in body copy.
- Demo-script B-roll cues: declarative, falsifiable.
- Teleprompter: short sentences, spelled-out numbers for read.
- Architecture: every component description maps to a file path.

No instances of "exciting" or "thrilled" found in any in-scope file. No exclamation points in body copy outside of structural markdown badge link syntax (5 hits in README, all on shields.io image links - not body copy).

## Unverifiable claims encountered

| Claim | File | Decision |
|---|---|---|
| "$0.02 per pipeline run on Haiku 4.5" | README L65 | Kept. Claim is an order-of-magnitude estimate and Haiku 4.5 list pricing supports it; not falsifiable to one cent but defensible for marketing copy. |
| "Five to ten cents per autopilot run" | demo-script L17, L67, L231, L233 | Kept. Same reasoning. |
| "26x faster", "360x faster" | demo-script L17, L227, L228 | Kept. Both anchor to stated baselines (40 min -> 90 sec; 3 hr -> 30 sec). |
| "Six hours per FE per week" | README, teleprompter, demo-script | Kept. Stated as benchmark in talking copy; documented in HANDOFF.md as the value claim. |
| "26x", "360x" | demo-script | Kept; arithmetic from stated baselines. |
| "200+ migrations" (Diego persona) | routes_mcp.py | Kept (persona biography, not a measurable claim). |

## Fixes applied

23 numeric fixes plus 6 license fixes plus 1 frontend tools.html paragraph rewrite. Targeted edits only; no document-level rewrites.

## Smoke status

After edits, integration smoke must remain GO. See run command in handoff. Edits are pure text in markdown / HTML / JS comment-strings; no Python code touched, no API surface changed.
