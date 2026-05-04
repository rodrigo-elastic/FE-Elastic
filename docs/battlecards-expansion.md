# Battlecards expansion audit

Date: 2026-05-03
Owner: Rodrigo Careaga
Seed file: `backend/data/seed/battlecards.json`
Index: `fec-battlecards` on Elastic Cloud
API: `GET /api/v1/battlecards`

## Result

| Metric | Before | After |
| --- | --- | --- |
| Cards in seed | 3 | 15 |
| Cards in ES index | 3 | 15 |
| API items returned | 3 | 15 |
| Em-dashes in seed | 0 | 0 |
| En-dashes in seed | 0 | 0 |
| JSON parse | OK | OK |

## 12 cards added (one-line summary each)

1. **AppDynamics** (Cisco APM): single data plane and OTel-native versus AppD plus Splunk plus ThousandEyes stitching.
2. **Chronicle** (Google SecOps): deployment flexibility and open detection rules versus GCP-only data residency.
3. **Cribl** (data pipeline): reframe the problem; Elastic frozen tier removes the SIEM cost driver Cribl exists to fix. Co-exist where the customer already runs it.
4. **Dynatrace** (full-stack APM + Davis AI): predictable per-GB pricing versus DDU/DPS opacity; OTel-first agent strategy.
5. **Exabeam** (UEBA SIEM): entity analytics included on the same cluster, no separate UEBA SKU; open detection format.
6. **Grafana** (LGTM stack): consolidate four datastores to one; co-exist on the dashboard layer via the Grafana Elasticsearch datasource.
7. **Graylog** (open-source log mgmt + SIEM): same Lucene foundation under the hood, but with frozen tier, native ML, and real Security workspace.
8. **Honeycomb** (event-based observability): scope of platform argument; Honeycomb is APM-adjacent only, customers buy a second tool for logs.
9. **Loki** (Grafana log aggregator): cheap on storage, expensive on free-text query at TB/day; frozen tier matches the storage story without the search penalty.
10. **Microsoft Sentinel** (Azure SIEM): cloud and source flexibility; ingest cost on non-Microsoft data; portable detection rules versus KQL lock-in.
11. **New Relic** (full-stack observability): no per-user platform tax; OTel-first; logs as first-class on the same cluster.
12. **QRadar** (IBM SIEM): modern cloud deployment and detection engineering versus appliance heritage and EPS pricing; many customers already evaluating replacement.

## Where each competitor genuinely beats Elastic (be honest in the room)

- **AppDynamics**: Business iQ's revenue-tied APM is more turnkey out of the box if the customer has invested in the BiQ data model. Deep .NET and Java instrumentation maturity.
- **Chronicle**: Flat-rate ingest at petabyte scale is genuinely cheaper if the customer is all-Google and never pivots. VirusTotal-derived intel is unique.
- **Cribl**: Inline routing UI is friendlier than YAML pipelines for a team that authors routing logic frequently. Edge collection on heterogeneous hosts.
- **Dynatrace**: Davis AI's root-cause analysis on traces is the strongest in the APM segment today. OneAgent auto-discovery is best-of-class on common stacks.
- **Exabeam**: Smart Timelines analyst experience is genuinely loved; tuned UEBA model library is mature.
- **Grafana**: Brand and community love among ops/SRE; Mimir is genuinely strong on Prometheus cardinality at scale.
- **Graylog**: Cheaper at the entry point, especially open core; UI is simpler for junior analysts.
- **Honeycomb**: BubbleUp on high-cardinality event data is a category-defining workflow; query latency on wide events is excellent.
- **Loki**: Lowest ingest cost in the log market for label-based queries; tightest integration with the Grafana visualisation layer.
- **Microsoft Sentinel**: Best-in-class for an all-Microsoft estate; Defender XDR + Sentinel + Entra signal correlation; E5 bundle includes a data allotment.
- **New Relic**: Free tier and per-user model is unbeatable for small teams under 20 users; NRQL is well-known and the agent footprint is mature.
- **QRadar**: FedRAMP authorisation pathway is well-trodden; entrenched in many federal and large-bank SOCs with years of content built up.

## Where Elastic genuinely beats each (the line we lead with)

- **AppDynamics**: One data plane covering APM + logs + metrics + security. AppD is APM-only, full stop.
- **Chronicle**: Multi-cloud and on-prem deployment, plus open detection rules on GitHub. Chronicle is GCP-only.
- **Cribl**: Frozen tier on object storage removes the underlying cost driver Cribl was sold to fix. Plus we can co-exist (Cribl can ship to Elastic).
- **Dynatrace**: Per-GB pricing versus DDU opacity; OTel-native; logs and security on the same cluster as APM.
- **Exabeam**: Entity analytics included; open detection rules with Git CI; same platform serves observability use cases.
- **Grafana**: One cluster instead of four (Mimir/Loki/Tempo/Pyroscope); free-text search depth on logs; Security workspace.
- **Graylog**: Frozen tier; native ML; real Security with MITRE coverage; ELSER for semantic search.
- **Honeycomb**: Logs and security on the same cluster; same OTel-native ingest, broader scope.
- **Loki**: Inverted index for low-latency free-text queries at TB/day; matching frozen-tier storage economics.
- **Microsoft Sentinel**: Per-GB ingest with no Azure-source preference; multi-cloud deployment; portable detection rules.
- **New Relic**: No per-user platform tax; frozen tier; security workspace on the same cluster.
- **QRadar**: Cloud-native deployment; per-GB pricing versus EPS; modern detection engineering CI; current-generation UI.

## Suggested research follow-ups

- **Cribl**: Validate the latest 'reduce SIEM bill' claim language; collect a real customer story where Elastic's frozen tier closed the same gap without Cribl in the path.
- **Microsoft Sentinel**: Track the Defender XDR + Sentinel UI consolidation; ingest cost on third-party sources changes quarterly. Also confirm current E5 included-data cap.
- **QRadar**: Watch the IBM-to-Palo-Alto QRadar SaaS divestiture story; many customers will be in flux for 12 to 18 months. Expansion opportunity.
- **Chronicle**: Confirm current Google Security Operations rebrand and pricing tiers (curated, enterprise, enterprise plus).
- **Honeycomb**: Track their pricing changes after the recent rebrands; verify whether logs-as-first-class is on their 2026 roadmap.
- **Dynatrace**: Confirm DPS commit conversion math against current published list; this changes annually.
- **Grafana**: Track Grafana Cloud pricing on active series; cardinality conversations are the wedge.
- **Exabeam**: Track New-Scale platform migration completion; many customers are stuck on classic.
- **AppDynamics**: Track the Cisco Splunk integration roadmap; the bundled story is the real threat over 18 months.
- **All**: Pull a real customer benchmark for query latency at the customer's actual scale; the marketing-versus-reality gap is where we win.

## Process notes

- Edited `backend/data/seed/battlecards.json` only. No code touched.
- Re-seeded ES via `delete_by_query` then per-card `_client.index` (the existing `_seed_battlecards_if_empty` short-circuits when count > 0, so a force-path was needed). Used the existing repo and client; no new code introduced.
- Verified `python -m json.tool` parse, em/en dash audit (zero), and `GET /api/v1/battlecards` returns 15 items sourced from ES.
- Cards alphabetised by `competitor_slug`; IDs follow the `battlecard-<slug>` pattern; taglines all under 90 characters.

## Constraints honoured

- No em-dashes or en-dashes anywhere in the seed.
- No invented features. Every claim maps to a real Elastic capability (frozen tier, ES|QL, ELSER, MITRE coverage, Elastic Agent, EDOT, Timeline, detection-rules repo).
- Honest assessment of competitor strengths in this doc so the FE is not blindsided.
- No code files modified.
