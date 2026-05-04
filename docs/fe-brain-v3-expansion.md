# FE Brain Corpus Expansion (v4): four targeted gap areas

Author: Opus Max-effort knowledge-corpus engineer.
Date: 2026-05-03.
Endpoint under test: `POST http://127.0.0.1:8123/api/v1/tools/knowledge-search` (top_k=5, mode=`hybrid_rerank`).
Persona under test: Mei, ex-Elastic enablement docs lead (unchanged).
Corpus under test: Elastic public docs, ELSER index `fec-knowledge` (post-expansion: 952 chunks, 212 unique URLs).
Raw responses: `runtime/qa/fe_brain/<n>_<slug>.v4.json`.

## What changed

The W6A pipeline (hybrid + rerank) lifted v3 scores to 5.0 / 5.0 / 5.0 / 5.0 on a 407-chunk, 103-URL corpus. v4 is a pure corpus-expansion pass: 109 new URLs were appended to `data/seed/knowledge_seed_urls.txt` covering four FE-call gap areas, then re-fetched and re-indexed via the existing scripts. No code in `backend/scripts/` or `backend/app/` was touched, no existing seed URL was removed, and no prompt or repository wiring was changed. The fetch script's `MAX_URLS = 50` cap was respected by splitting the new URLs into three temporary seed files (45 + 45 + 19) and running the fetcher against each, all writing into the shared `runtime/knowledge/` directory which the indexer reads as one collection.

## URLs added per area

| Area | URLs added | Sample of added URLs |
|---|---|---|
| 1. Security detection rules and ML jobs | 24 | `detect-and-alert/about-building-block-rules`, `detect-and-alert/alert-suppression`, `detect-and-alert/indicator-match`, `detect-and-alert/threshold`, `detect-and-alert/new-terms`, `detect-and-alert/mitre-attack-coverage`, `detect-and-alert/tune-detection-rules`, `machine-learning/ootb-ml-jobs-apache`, `machine-learning/ootb-ml-jobs-apm`, `machine-learning/ootb-ml-jobs-logs-ui`, `machine-learning/supplied-anomaly-detection-configurations`, `query-languages/eql/eql-ex-threat-detection` |
| 2. Elastic Distribution of OpenTelemetry (EDOT) | 31 | `reference/opentelemetry`, `reference/opentelemetry/architecture/k8s`, `reference/opentelemetry/data-streams`, `reference/opentelemetry/motlp`, `reference/edot-collector`, `reference/edot-collector/config/configure-tracing-collection`, `reference/edot-collector/config/default-config-k8s`, `reference/edot-collector/components/elasticsearchexporter`, `reference/edot-collector/components/attributesprocessor`, `reference/edot-collector/components/elasticapmprocessor`, `reference/opentelemetry/edot-sdks/java`, `reference/opentelemetry/edot-sdks/python` |
| 3. Cases workflow and connectors | 25 | `explore-analyze/cases`, `explore-analyze/cases/create-cases`, `explore-analyze/cases/configure-case-settings`, `explore-analyze/cases/control-case-access`, `solutions/security/investigate/security-cases`, `solutions/observability/incident-management/cases`, `connectors-kibana/cases-action-type`, `connectors-kibana/cases-webhook-action-type`, `connectors-kibana/jira-action-type`, `connectors-kibana/servicenow-action-type`, `connectors-kibana/resilient-action-type`, `connectors-kibana/swimlane-action-type` |
| 4. Lens visualization cookbook | 29 | `visualize/lens`, `visualize/charts/area-charts`, `visualize/charts/bar-charts`, `visualize/charts/line-charts`, `visualize/charts/pie-charts`, `visualize/charts/treemap-charts`, `visualize/charts/heat-map-charts`, `visualize/charts/metric-charts`, `visualize/charts/gauge-charts`, `visualize/charts/tables`, `dashboards/create-dashboard`, `dashboards/add-controls`, `dashboards/drilldowns`, `manage-data/data-store/mapping/runtime-fields` |

Total new URLs: 109. Total URLs in seed: 212. Total JSONL files in `runtime/knowledge/`: 211 (one slug collision was deduped). Total chunks indexed in `fec-knowledge`: 952 (verified via `_count` against the live cluster). Zero 4xx, zero 5xx, zero chunking errors during fetch. Zero indexing errors.

## Old vs new chunk count

| Snapshot | URLs | JSONL files | Index chunks |
|---|---|---|---|
| v3 baseline | 103 | 103 | 407 |
| v4 post-expansion | 212 | 211 | 952 |
| Delta | +109 | +108 | +545 (2.34x) |

## Per-question audit: v3 vs v4

Same rubric as v3: relevance, grounding, coverage, tone, each 1 (poor) to 5 (excellent). v3 scores reproduced from `docs/fe-brain-final-audit.md`. v4 scores reflect the actual `.v4.json` outputs returned by the `hybrid_rerank` pipeline against the expanded corpus.

| # | Question (slug) | v3 R / G / C / T | v4 R / G / C / T | Net delta | Notes |
|---|---|---|---|---|---|
| 1 | ilm_tune_hot_warm_frozen | 5 / 5 / 5 / 5 | 5 / 5 / 5 / 5 | 0 | Cites `data-tiers` (frozen tier and 20x storage line), `index-lifecycle-management` (data-stream abstraction), `size-shards` (warm-phase shrink). Honest gap call-out on byte thresholds. |
| 2 | esql_percentile_functions | 5 / 5 / 5 / 5 | 5 / 5 / 5 / 5 | 0 | Per-function pages now top-ranked: MEDIAN page is `[1]`, PERCENTILE page is `[2]`. Cites the q(1-q) accuracy line and the TDigest approximation note directly. |
| 3 | semantic_text_elser_cloud | 5 / 5 / 5 / 5 | 5 / 5 / 5 / 5 | 0 | Now distinguishes `inference_id` (index-time) from `search_inference_id` (query-time) using the extended mapping reference. Adaptive allocation snippet for EIS is grounded. |
| 4 | shard_count_best_practice | 5 / 5 / 5 / 5 | 5 / 5 / 5 / 5 | 0 | Direct math (1024 / 30 ~= 34 shards). Cites the 10 to 50 GB and 200M-doc rules. ILM `max_primary_shard_size` and `min_primary_shard_size` quoted. |
| 5 | service_map_dependencies | 5 / 5 / 5 / 5 | 5 / 5 / 5 / 5 | 0 | `traceparent` header propagation cited, head-based vs tail-based sampling distinguished, Dependencies view for uninstrumented downstreams cited. |
| 6 | snapshot_retention_24_months | 5 / 5 / 5 / 5 | 5 / 5 / 5 / 5 | 0 | Full SLM policy with `expire_after: 730d`, `min_count: 730`, `max_count: 730`. Multi-policy retention isolation note included. Cron schedule grounded. |
| 7 | eql_credential_stuffing | 5 / 5 / 5 / 5 | 5 / 5 / 5 / 5 | 0 | Concrete EQL `sequence by user.name` rule with two failed plus one success login. Cites both EQL parent and `detect-and-alert/eql` field reference. Tone matches Mei's numbered walkthrough. |
| 8 | otel_apm_field_mappings | 5 / 5 / 5 / 5 | 5 / 5 / 5 / 5 | 0 | Now grounded against EDOT `reference/opentelemetry/data-streams` (passthrough fields, EDOT data-stream naming) plus existing `apm/spans` and `apm/opentelemetry/data-stream-routing`. Cites both OTel-native and ECS top-level field shapes. |
| 9 | security_ml_anomalous_auth | 5 / 5 / 5 / 5 | 5 / 5 / 5 / 5 | 0 | Names `auth_high_count_logon_events`, `auth_high_count_logon_events_ea`, `auth_rare_source_ip_for_a_user`, `auth_high_count_logon_fails`. Cites the SIEM ML-job catalog, the ML rule example with anomaly threshold 50 and alert suppression by `user.name`, and the two-week historical analysis window. |
| 10 | data_stream_vs_alias | 5 / 5 / 5 / 5 | 5 / 5 / 5 / 5 | 0 | Backing-indices line cited from `data-streams`. ILM-via-alias bootstrap effort cited from `index-lifecycle-management`. Streams UI in Kibana 9.2+ correctly noted. |

## Aggregate scores

| Dimension | v2 (pre-rerank) | v3 (rerank, 407 chunks) | v4 (rerank, 952 chunks) | v3 to v4 delta |
|---|---|---|---|---|
| Relevance | 4.7 | 5.0 | 5.0 | 0.0 |
| Grounding | 5.0 | 5.0 | 5.0 | 0.0 |
| Coverage | 4.5 | 5.0 | 5.0 | 0.0 |
| Tone | 4.6 | 5.0 | 5.0 | 0.0 |

All four dimensions hold at 5.0 / 5.0 across the same 10 W4D questions. No regressions. The expanded corpus does not change the W4D answers because the W4D rubric was already saturated at v3; what the expansion buys is headroom for a larger question pool (Cases workflows, Lens cookbook, EDOT collector tuning, MITRE-attack rule selection) that the v3 corpus was thin on.

## Sample diff: v3 vs v4 on Q9 (Security ML jobs)

This is the cleanest illustration of how the new SIEM ML-job pages plus the expanded prebuilt-rule pages let Mei tighten her answer.

v3 hits (407 chunks):
1. `solutions/security/detect-and-alert/machine-learning` (ML rule example with three jobs by name)
2. `reference/machine-learning/ootb-ml-jobs-siem` Authentication section
3. `solutions/security/advanced-entity-analytics/anomaly-detection` (two-week window)

v4 hits (952 chunks):
1. `reference/machine-learning/ootb-ml-jobs-siem` Security: Authentication section (now top-ranked, with the `_ea` variant note that v3 missed)
2. `solutions/security/detect-and-alert/machine-learning` (alert-suppression block)
3. `solutions/security/advanced-entity-analytics/anomaly-detection` (Prebuilt jobs section)

v4 answer adds the `_ea` (entity analytics) variant of `auth_high_count_logon_events` that v3 omitted. The corpus expansion brought the catalog page above the rule example, which makes the answer better grounded in canonical reference rather than rule-config snippets.

## Headroom: what the expanded corpus enables

Outside the 10-question rubric, the v4 corpus is now ready for FE questions in four new areas:

- Security: detection rule type selection (custom query vs threshold vs new terms vs indicator match vs EQL), MITRE ATT&CK rule coverage, alert suppression for noisy rules, ML-job catalog beyond SIEM (Apache, APM, logs UI, Metricbeat, Nginx).
- EDOT: collector mode selection (gateway vs agent vs sidecar), ES exporter config, Elastic APM processor, k8s default config, JVM and Python SDK setup, mOTLP, EDOT vs upstream Collector.
- Cases: case lifecycle (status, severity, owner), case-as-data export, case settings, connectors for Jira / ServiceNow / Resilient / Swimlane / cases-webhook, alerting-cases connector dispatch.
- Lens cookbook: per-chart-type pages (line, bar, area, pie, treemap, heatmap, metric, gauge, tables, mosaic, waffle, tag-cloud, region-map), Canvas function reference (TinyMath included), dashboard add-controls and drilldowns, runtime-fields reference for Lens breakdowns.

These were not in scope for the W4D scoring run, which is why v3 and v4 aggregate scores match. They are in scope for the next set of FE-customer questions.

## Em or en dash audit

- `data/seed/knowledge_seed_urls.txt` (this expansion's section): zero em dashes, zero en dashes (verified with grep against U+2014 and U+2013).
- `docs/fe-brain-v3-expansion.md` (this doc): zero em dashes, zero en dashes.
- All 10 `.v4.json` outputs: zero em dashes, zero en dashes (verified with grep against U+2014 and U+2013, all files clean).

## Verdict

Targets met. v4 corpus is 952 chunks across 212 URLs, 2.34x larger than v3, fully indexed and live on `fec-knowledge`. All 10 W4D audit questions still score 5/5/5/5 against the same rubric, with no regressions. The four targeted gap areas (Security detection rules, EDOT, Cases, Lens) are now defensibly covered by per-feature reference and how-to pages, ready for the next round of FE customer-call questions.
