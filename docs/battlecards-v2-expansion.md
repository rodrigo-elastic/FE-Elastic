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
