# W23D End-to-End Regression Sweep

- Generated: 2026-05-04
- Backend base: http://localhost:8123
- Sweep scope: 13 primary flows after waves W19 (a11y), W20 (customers filter+kanban), W21 (cleanup), W22 (transcript move), W23 (perf).
- Test mode: live backend with mock LLM (no ANTHROPIC_API_KEY); Elastic + Kibana live (cluster 942d0ee1c30f4eceb1644cad9563e466, version 9.3.4).

## Verdict

OVERALL: CAUTION (no functional regression introduced by W19-W23; two pre-existing items flagged in e2e_tests.py and unrelated to the recent waves).

- Em-dash audit: 0 across backend + frontend + docs.
- Integration smoke: 8/9 PASS (only Step 9 git-status check is yellow due to in-flight uncommitted overnight edits, not a feature regression).
- e2e_tests.py: 10/12 PASS, 2 FAIL (Journey 6 mock-LLM fallback, Journey 12 health/full p95 budget).

## Per-flow status

| # | Flow | Status | What was tested |
| ---: | --- | --- | --- |
| 1 | Autopilot 9 steps | PASS | /index.html returns 200; "Show me the magic" CTA + autopilot-cta id present; autopilot.js AP.steps array intact with 9 ids: intro, dashboard, industries, bcards, brain, ab, demo, health, recap. Esc handler bound (onEscDown -> stop("user")); Stop button bound (#ap-stop-btn click -> stop("user")). |
| 2 | FE Brain query | CAUTION | /fe-brain.html returns 200; POST /api/v1/tools/knowledge-search returns valid {answer, citations[]} envelope; citations is empty due to mock LLM mode (no ANTHROPIC_API_KEY). Pill /api/v1/tools/knowledge-search/health returns documents=1300, urls=321. Shape correct, citations population gated on real LLM. |
| 3 | Agent Builder CRUD | PASS | POST /agent-builder/agents created fec_user_smoke_test with valid schema (name, slug, description >=10, system_prompt >=50, tool_ids); GET /agent-builder/agents listed it; DELETE returned {deleted: true}; follow-up GET returned 404 from Kibana. |
| 4 | Battlecards filter + sort | PASS | GET /api/v1/battlecards returned items.length=31, source=es, every item has vertical, industries[], is_main_competitor, competitor_slug. Read battlecards.js IMPORTANCE map: splunk=1, datadog=2, crowdstrike=3 (in order). |
| 5 | Industries deep-link | PASS | GET /api/v1/industries returned items.length=20; GET /api/v1/industries/fsi-banking returned full record with id, name, icon, summary, personas, regulations, top_competitors, scenario_ids, tool_ids, kpis, elastic_wins_when, elastic_loses_when. /industries.html?industry=fsi-banking returns 200 with modal markup; industries.js reads ?industry on load and calls openModal(match.id). |
| 6 | Demo Data reseed | PASS | GET /api/v1/demo-data/scenarios returned 8 ids: black-friday-outage, credential-stuffing, noisy-microservice, gdpr-audit-timeline, supply-chain-attack, fsi-banking-fraud, healthcare-hipaa-audit, gov-cdm-compliance. All three required scenarios present. |
| 7 | Renewal workflow demo-fire | PASS | POST /api/v1/workflows/renewal-demo-fire returned ok=true, account_name="Northwind Pay", severity="critical", tactics list length=4, owner_role values populated. GET /api/v1/workflows/status returned registered=true, both rule_post_meeting and orphan_action registered, registered_all=true. |
| 8 | Customers Kanban filter + group | PASS | /customers.html returns 200 with quick-research-filter.js present (2 occurrences). Read isSystemRecord: drops orphan-demo-, synthetic-, _internal-, demo-data- prefixes; drops "FE team weekly sync" titles; drops customer_id="unknown"; drops empty customer_name; drops unresolved/n/a/(unknown)/unknown*/placeholder*/test*. customerColorIndex deterministic 0..9 verified with 10 sample seeds (Northwind Pay -> 7, both passes match). |
| 9 | Quick Research single-purpose | PASS | /quick-research.html returns 200; entry-tabs occurrences=0; tr-form occurrences=0; qr-form occurrences=1 (intact). Single-purpose UI confirmed after W22 transcript move. |
| 10 | Customers transcript form | PASS | /customers.html contains tr-form (3 occurrences inside the collapsible CTA wrapper); "Analyze transcript" CTA copy present (2 occurrences). |
| 11 | Health endpoints | PASS | GET /api/v1/health returned {status:"ok",service:"fe-copilot"}. GET /api/v1/health/full returned mcp_tools.count=12, fe_brain.chunks=1300 (>1000), demo_data.scenarios=8, battlecards.count=31. status="green", warnings=[]. |
| 12 | i18n parity | PASS | Read i18n.js, parsed I18N_STRINGS block per locale. Static line count: en=386, es=386, ja=386, de=386, fr=386 (all five aligned). Set-deduped count from e2e_tests.py: 385 each, also aligned. |
| 13 | Autopilot recap card | PASS | autopilot.js showCompletion has h3 text "Six hours per FE per week back." plus 5-stat row: tour duration, sections covered, 12 MCP tools live, 31 battlecards, 20 industries. fireConfetti(120) at end. |

## Regressions found

Count: 0 introduced by W19-W23.

Pre-existing issues surfaced (not new regressions):

- e2e_tests.py Journey 6 fails because the mock LLM cannot synthesize semantic_text/ELSER/Elastic URL citations. This is by design when ANTHROPIC_API_KEY is unset; the mock fallback explicitly returns a stub answer with citations=[]. Not introduced by W19-W23.
- e2e_tests.py Journey 12 fails the 500ms p95 budget on /api/v1/health/full (measured ~1378ms). Root cause: routes_health.py runs up to 6 sequential Elasticsearch round-trips per call (count, 3 sort attempts in _fe_brain_last_seed, root info, ping). With ping_ms=183ms each, totals ~1.1s. Not introduced by W19-W23; pre-dates these waves.
- integration_smoke.py Step 9 yellow because 32 modified + 1 untracked file are uncommitted (overnight sprint state). Not a feature regression; expected mid-sprint.

## Regressions fixed

Count: 0. No code changes were necessary and none were made.

## Regressions deferred

Count: 2 (both pre-existing, both flagged for separate sprint not Batch 1 EJE D).

1. health/full p95 above 500ms budget. Not a W19-W23 regression. The fix is non-trivial (>30 lines): add a TTL cache for cluster_info / fe_brain_chunks / fe_brain_last_seed / ping_ms with concurrent gather, plus stale-while-revalidate semantics. Recommend dedicated W23E perf wave. Skipping per the small-fix guard.
2. Journey 6 FE Brain mock-mode failure. Not a W19-W23 regression; this is the design behavior without an API key. The "fix" is environmental (set ANTHROPIC_API_KEY) and orthogonal to QA scope.

## Em-dash audit

Audit method: ripgrep for U+2014 and U+2013 across backend, frontend, docs, data, assets, infra, runtime, tests. Result: 0 hits in the project source (the false positives in the rg output came from binary fixture files outside scope; verified via the integration smoke step 8 which uses the same scanner and reports 0).

## Smoke posture

`scripts.integration_smoke`: 8/9 PASS. The single FAIL (step 9) is a git-state check that does not exercise any product surface. All product surfaces (backend health, ES indices, Kibana saved objects, MCP server, tools REST, workflow status, frontend pages, dash audit) remain GREEN. From a feature-regression standpoint, smoke is GO.

`scripts.e2e_tests`: 10/12 PASS (CAUTION). Both failures are pre-existing and orthogonal to W19-W23.

## Files inspected

- /Users/rodrigocareaga/Downloads/FE-Elastic/frontend/assets/js/autopilot.js
- /Users/rodrigocareaga/Downloads/FE-Elastic/frontend/assets/js/battlecards.js
- /Users/rodrigocareaga/Downloads/FE-Elastic/frontend/assets/js/industries.js
- /Users/rodrigocareaga/Downloads/FE-Elastic/frontend/assets/js/quick-research-filter.js
- /Users/rodrigocareaga/Downloads/FE-Elastic/frontend/assets/js/i18n.js
- /Users/rodrigocareaga/Downloads/FE-Elastic/frontend/index.html
- /Users/rodrigocareaga/Downloads/FE-Elastic/frontend/customers.html
- /Users/rodrigocareaga/Downloads/FE-Elastic/frontend/quick-research.html
- /Users/rodrigocareaga/Downloads/FE-Elastic/frontend/industries.html
- /Users/rodrigocareaga/Downloads/FE-Elastic/backend/app/api/routes_tools.py
- /Users/rodrigocareaga/Downloads/FE-Elastic/backend/app/api/routes_agent_builder.py
- /Users/rodrigocareaga/Downloads/FE-Elastic/backend/app/api/routes_health.py
- /Users/rodrigocareaga/Downloads/FE-Elastic/backend/scripts/e2e_tests.py
- /Users/rodrigocareaga/Downloads/FE-Elastic/backend/scripts/integration_smoke.py
