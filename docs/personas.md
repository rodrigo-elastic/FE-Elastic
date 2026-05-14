# Expert-role roster

FE Copilot's fourteen MCP tools each carry a frozen role definition in `backend/app/agents/prompts/tools.py`. Roles are searchable by expertise keyword (no first-person names), so an FE looking for "ex-Splunk consultant" or "CISA + CISSP compliance" can find the right tool without memorising a roster.

| Tool | Expertise | Output |
|---|---|---|
| `fec_poc_plan` | Senior Solutions Architect, 12y POV experience across observability, security, and search | 4-8 week proof-of-value plan |
| `fec_spl_to_esql` | SPL-to-ESQL migration specialist (ex-Splunk consultant, 10y, 200+ migrations) | SPL query translated to ES\|QL with caveats |
| `fec_compliance` | Field Compliance Architect (ex-PwC, CISA + CISSP, 8y regulated audits) | DORA / HIPAA / PCI / GDPR / SOX / NIS2 mapping to Elastic controls |
| `fec_stack_extract` | Field Discovery Analyst, 9y pre-sales engineering | Canonical tech stack pulled from raw transcripts and dossiers |
| `fec_code_sample` | Field Engineer + SDK cookbook author (Python / TypeScript / Java / Go / Ruby) | Copy-pasteable Elastic SDK snippet for a specific use case |
| `fec_cost_calc` | Senior Field Pricing Architect, 11y TCO modeling, 80+ procurement defenses | Narrative wrapper around the deterministic cost calculator |
| `fec_knowledge_search` | Knowledge & Enablement Architect (ex-docs lead, 8y) | Cited answer over `fec-knowledge` hybrid retrieval (FE Brain) |
| `fec_troubleshoot` | Field Support Engineer, 7y Elastic Cloud support, 1000+ tickets | ES\|QL diagnostics for an error message or log snippet |
| `fec_compare` | Senior Competitive Architect, 15y competitive intelligence | Structured Elastic vs competitor side-by-side |
| `fec_orchestrator` | Senior Field Engineer, 12y multi-tool response orchestration | Plan + 1-3 tool picks + synthesis across them |
| `fec_proposal` | Senior Pursuit Lead, 15y competitive proposal writing | One-page customer proposal (Markdown + PDF artifact) |
| `fec_deploy_validator` | Senior Platform Architect, 12y on production Elasticsearch / Elastic Cloud | Cluster antipattern audit 0-100 with remediation steps |
| `fec_pov_health` | Senior POV Operations Lead, 9y running trial clusters | Stage assessment + risks + next-best actions for an active POV |
| `renewal_defender` *(service)* | Senior Renewal Architect | Retention plays for at-risk accounts |

Two of the tools (`fec_capacity` and the calculator side of `fec_cost_calc`) are pure deterministic compute and intentionally carry no role narrative: they are sized as calculators, not opinion engines. The `fec_cost_calc` role wraps the calculator output with the pricing narrative.

Per-competitor battlecard specialists (33 today) live alongside the master agent in Kibana Agent Builder. See [`../backend/scripts/sync_battlecard_agents.py`](../backend/scripts/sync_battlecard_agents.py) and [`battlecard_skills_template.md`](battlecard_skills_template.md).
