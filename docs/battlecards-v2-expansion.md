# Battlecards v2 Expansion (15 to 20)

This expansion appends 5 high-impact competitor battlecards to `backend/data/seed/battlecards.json`, taking the corpus from 15 to 20. Each card was scoped for honest competitive framing: where the competitor genuinely beats Elastic, where Elastic genuinely beats the competitor, and the discovery work needed to qualify.

## New Cards (one-line each)

1. **Cisco AppDynamics + Splunk bundle** (`cisco-appd-splunk-bundle`): Cisco's post-acquisition pitch is three products on three bills under one logo, not a unified data plane.
2. **Dragos** (`dragos`): Best-in-class OT/ICS detection; complementary to Elastic, which acts as the SIEM that bridges OT alerts into the IT SOC.
3. **ServiceNow ITOM** (`servicenow-itom`): Wins for SNOW-centric shops that want event-to-incident automation; loses on data sovereignty, log-scale economics and ML maturity.
4. **Splunk Cloud** (`splunk-cloud`): Distinct from Splunk Enterprise: workload (SVC) pricing, regional egress and residency tradeoffs reshape the competitive math.
5. **Wiz** (`wiz`): Best-in-class CSPM and cloud-graph correlation; complementary to Elastic, which acts as the SIEM consuming Wiz findings and storing the long-retention runtime data.

## Where Each Competitor Genuinely Beats Elastic (no strawman)

- **Cisco bundle**: One logo, one support escalation path, aligned renewal calendars across AppD, Splunk and ThousandEyes. ThousandEyes path-level network telemetry has no Elastic equivalent.
- **Dragos**: Deep OT protocol decoders (Modbus, DNP3, IEC-61850, OPC-UA), industry-tuned threat groups and air-gap-friendly deployment. Elastic does not match Dragos at the OT-protocol depth layer.
- **ServiceNow ITOM**: For customers who already run ServiceNow as system of record, Event Management plus CMDB plus Flow Designer is the shortest path from alert to ticket to runbook. Elastic does not own the ITSM workflow.
- **Splunk Cloud**: Mature managed-service playbook, SPL muscle memory across thousands of analysts, and a dense partner ecosystem for content and apps. Workload pricing is genuinely friendlier than legacy ingest pricing for steady-state workloads.
- **Wiz**: Agentless cloud workload scanning, the Wiz Security Graph, and cloud-config-plus-vuln-plus-identity-plus-exposure correlation are purpose-built and well-tuned. Elastic does not replace this layer.

## Where Elastic Genuinely Beats Each

- **Cisco bundle**: One cluster for logs, metrics, APM, RUM, synthetics and Security; per-GB ingest plus storage tiers replaces three pricing models; OTel-native via EDOT; frozen tier on object storage included.
- **Dragos**: Full IT plus identity plus cloud plus endpoint coverage that Dragos does not attempt; per-GB plus frozen tier economics for the high-volume IT log layer; converged IT/OT SOC view via Dragos alert ingest.
- **ServiceNow ITOM**: Self-hosted, multi-cloud or air-gapped deployment versus SNOW-instance-only; per-GB plus frozen tier at log scale; mature ML anomaly detection and ELSER inference; bidirectional ServiceNow connector preserves the ITSM workflow without paying SNOW prices for the data plane.
- **Splunk Cloud**: Per-GB ingest plus auto-scaling handles spikes without re-tiering the contract; broader regional footprint on AWS/GCP/Azure with PrivateLink; frozen tier on object storage at retention scale; same platform owns Security on one license.
- **Wiz**: SIEM-tier log retention and correlation that Wiz does not provide; native ingest of Wiz findings via webhook and REST; detection rules across identity, endpoint, network and cloud, not posture-only; frozen tier for 12+ months of queryable retention.

## Cisco-Splunk-AppD Bundle Uncertainty

The Cisco bundle is a roadmap purchase, not a unified product today: AppDynamics, ThousandEyes and Splunk still have separate data stores, separate agents, separate pricing models (DDU-style, per-test subscription, workload/ingest) and separate engineering orgs, so post-acquisition integration risk is real and customers signing the bundle now are betting on a 24-month integration story that has not yet shipped.

## Verification

- `python -m json.tool backend/data/seed/battlecards.json` parses cleanly.
- Seed file contains 20 cards (15 original plus 5 new); all `id` slugs are lowercase-hyphenated and unique.
- `fec-battlecards` index reseeded via `_client.index` over the existing index (the built-in `_seed_battlecards_if_empty` only fires on an empty index).
- `GET /api/v1/battlecards` returns 20 items.
- No em dashes, no en dashes, no non-ASCII characters in the seed file.

## v3: Vertical Reorganisation and 11 New Main Competitors (20 to 31)

This expansion adds 11 net-new cards covering the verticals Elastic actually competes in for the 2026 hackathon narrative, and tags every existing card with its `vertical` and `is_main_competitor` flags so the frontend can filter the corpus.

### Schema additions on every card

- `vertical`: one of `direct_search_vector`, `observability_logs`, `ai_search_ecommerce`, `security_siem_xdr`.
- `is_main_competitor`: boolean. Marks the headline competitor in each vertical.
- New cards also carry: `proof_points` (metric + source), `objection_handlers` (q/a, replaces `common_objections` for new cards but the JS falls back to `common_objections` for legacy cards), `pricing_anchor` (one-line public list pricing), `gotchas` (3 to 5 honest gaps where the competitor genuinely beats Elastic), `clincher` (one-line closer).

### 11 new cards

Direct Search and Vector Database Rivals (the Elastic core, all flagged main):

1. **AWS OpenSearch** (`battlecard-aws-opensearch`): the ex-7.10 fork. Honest framing: AWS console integration is tighter; ELSER, semantic_text, ES|QL, APM and Security ship in Elastic and not in OpenSearch.
2. **Pinecone** (`battlecard-pinecone`): vector-only managed DB. Honest framing: Pinecone wins on pure-vector p99 at extreme scale; Elastic wins on hybrid BM25 plus dense plus ELSER under one query and avoids running two databases.
3. **Weaviate** (`battlecard-weaviate`): vector-native open source. Honest framing: GraphQL ergonomics are nicer; Elastic wins on three-way RRF hybrid plus enterprise governance and observability on the same cluster.
4. **Milvus** (`battlecard-milvus`): billion-scale vectors and Zilliz Cloud. Honest framing: Milvus dominates pure-vector benchmarks and offers GPU index build; Elastic wins on operational simplicity and hybrid retrieval with filters.
5. **Typesense** (`battlecard-typesense`): lightweight site search. Honest framing: faster to launch one site; Elastic wins as the platform when search expands to RAG, observability or security.
6. **Meilisearch** (`battlecard-meilisearch`): JS-friendly typo-tolerant search. Honest framing: best-in-class DX on small SaaS; Elastic wins on enterprise IAM, audit, FedRAMP and multi-tenant scale.

AI Search and E-commerce Discovery (all flagged main):

7. **Algolia** (`battlecard-algolia`): search-as-a-service e-commerce leader. Honest framing: merchandising UI and global edge latency are mature; Elastic wins on per-GB economics at large catalogs, data sovereignty and platform breadth.
8. **Coveo** (`battlecard-coveo`): enterprise relevance plus recommendations, Salesforce/ServiceNow centric. Honest framing: Coveo ML personalization and packaged Salesforce integration are mature; Elastic wins on open ML, lower TCO and unified observability plus security.
9. **Lucidworks** (`battlecard-lucidworks`): Apache Solr commercial wrapper. Honest framing: deep Solr expertise and a strong Lab process; Elastic wins on velocity, hybrid retrieval (ELSER) and platform breadth.

Security SIEM/XDR/EDR (all flagged main):

10. **CrowdStrike** (`battlecard-crowdstrike`): Falcon EDR/XDR leader. Honest framing: Falcon endpoint detection is best-in-class; Elastic positions as the SIEM that consumes Falcon, retains long via frozen tier, and correlates across non-endpoint domains.
11. **SentinelOne** (`battlecard-sentinelone`): autonomous EDR. Honest framing: S1 rollback and quarantine are best-in-class; Elastic positions as the open SIEM with longer retention and hunt capabilities than Singularity Data Lake.

### Final vertical distribution

- `direct_search_vector`: 6 cards, all main, all new.
- `observability_logs`: 13 cards (12 existing plus 1 from this round; this round added none here, the 13 is the existing observability footprint), 5 main (Splunk, Datadog, Dynatrace, Grafana, New Relic).
- `ai_search_ecommerce`: 3 cards, all main, all new.
- `security_siem_xdr`: 9 cards (7 existing plus 2 new for CrowdStrike and SentinelOne), 3 main (CrowdStrike, SentinelOne, Sumo Logic).
- Total: 31 cards. 17 mains.

### Frontend filtering

The grid view at `/battlecards.html` now shows:

- Four vertical chips at the top (Direct Search/Vector, Observability/Logs, AI Search/E-commerce, Security/SIEM) plus an All-verticals chip.
- A "Main competitors only" toggle, defaulting on.
- A vertical badge on every card and in the detail-view hero, plus a "main" pill on flagged cards.
- Live counts on each chip that respect the toggle.

i18n keys added in five languages (EN, ES, JA, DE, FR): `bc.vert.all`, `bc.vert.{vertical}`, `bc.vert.{vertical}.short`, `bc.toggle.mains`.

### Reseed mechanism

`_seed_battlecards_if_empty` only runs on an empty index, so a new endpoint was added: `POST /api/v1/battlecards/reseed` which calls a new `ElasticsearchRepo.reseed_battlecards` that force-indexes every card in the seed file by `id`. This was used to push the v3 corpus into ES on the running cluster.

### v3 verification

```
curl -s http://localhost:8123/api/v1/battlecards | jq '[.items[] | {id, vertical, is_main_competitor}] | group_by(.vertical) | map({vertical: .[0].vertical, count: length, mains: map(select(.is_main_competitor)) | length})'
```

Returns the four-group histogram with counts 6, 13, 3, 9 and main counts 6, 5, 3, 3.

- `python -m json.tool backend/data/seed/battlecards.json` parses cleanly with 31 cards.
- All taglines under 90 characters; no em dashes, no en dashes anywhere in the touched files (battlecards.json, battlecards.html, battlecards.js, battlecards.css, routes_battlecards.py, elasticsearch_repo.py, battlecards-v2-expansion.md, i18n.js).
- `GET /api/v1/battlecards/by-competitor/pinecone` returns the new card with `vertical`, `is_main_competitor`, `proof_points`, `pricing_anchor`, `gotchas`, `objection_handlers` and `clincher` fields populated.
