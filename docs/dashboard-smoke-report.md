# Dashboard Smoke Test Report

Audit date: 2026-05-03
Auditor: Opus 4.7 QA pass on FE Copilot demo dashboards
Scope: 11 Kibana dashboards (5 FE + 5 Customer + 1 customer-fit)
Stack: `fe-summit-hackathon-ed0e8e` (Elastic Cloud, us-west-1)

## Methodology

Visual headless-browser capture was attempted but skipped: Kibana web routes
require either an interactive session cookie or per-request `Authorization: ApiKey`
header injection, and Chrome headless on this workstation has no extension
loader, no Puppeteer or Playwright, and no Node runtime. Per the task spec,
this is the documented fallback case, so the audit used the structured
saved-object verification path (option B in the spec).

For each dashboard the auditor ran:

1. `GET /api/saved_objects/dashboard/<id>` via the project Kibana API key.
2. Parsed `attributes.panelsJSON` into the panel array.
3. Classified each panel by type (markdown, Vega/Vega-Lite, Lens, other).
4. For every Vega spec, recursively walked the spec tree (handling
   single-data, layered `layer[].data.values`, `hconcat`, `vconcat`, `concat`,
   `facet`, `repeat`, and nested `spec`) and counted inline rows under
   `data.values` plus Elasticsearch `data.url.index` references.
5. For every Lens panel, parsed the embedded `attributes.references` and
   `state.datasourceStates` to confirm a real `index-pattern` reference.
6. For every markdown panel, measured content length and scanned for the
   placeholder strings `TODO` and `(no data)`.
7. Cross-checked every referenced index with `POST /<index>/_count` and
   sampled the latest `@timestamp` to confirm fresh ingest within the
   dashboard default time window.
8. Verified `attributes.timeRestore` is `true` and `timeFrom` / `timeTo`
   are populated, so panels open with a sensible window even if the demo
   operator forgets to set the time picker.

Per-dashboard panel snapshots are stored at
`runtime/qa/dashboard_smoke/<dashboard-id>.json` and the full raw audit at
`runtime/qa/dashboard_smoke/raw-audit.json`. The driving scripts are
`runtime/qa/dashboard_smoke/audit.py` and
`runtime/qa/dashboard_smoke/snapshot.py`.

## Underlying index document counts

All referenced indices are populated and currently ingesting (latest doc
timestamps are within the same day as the audit, 2026-05-04 UTC).

| index                       | doc count | latest @timestamp           |
| --------------------------- | --------- | --------------------------- |
| demo-blackfriday-metrics    |       600 | 2026-05-04T07:20:00Z        |
| demo-blackfriday-*          |     5,600 | (rollup, fresh)             |
| demo-credstuff-auth         |     3,613 | 2026-05-04T07:24:03Z        |
| demo-credstuff-*            |     3,669 | (rollup, fresh)             |
| demo-noisy-traces           |     5,500 | 2026-05-04T07:21:37Z        |
| demo-noisy-logs             |     3,500 | (fresh)                     |
| demo-noisy-*                |     9,025 | (rollup, fresh)             |
| demo-gdpr-*                 |     4,717 | (90d window, fresh)         |
| demo-supplychain-*          |     7,275 | (14d window, fresh)         |

## Per-dashboard table

| dashboard_id                                        | panels | md | vega_inline | vega_url | lens | empty | indices doc_count                | verdict |
| --------------------------------------------------- | -----: | -: | ----------: | -------: | ---: | ----: | -------------------------------- | :-----: |
| demo-black-friday-outage-dashboard                  |      9 |  4 |           3 |        0 |    2 |     0 | demo-blackfriday-metrics 600     |  READY  |
| demo-black-friday-outage-customer-dashboard         |      9 |  4 |           3 |        0 |    2 |     0 | demo-blackfriday-metrics 600     |  READY  |
| demo-credential-stuffing-dashboard                  |     11 |  5 |           4 |        0 |    2 |     0 | demo-credstuff-* 3,669           |  READY  |
| demo-credential-stuffing-customer-dashboard         |     11 |  5 |           4 |        0 |    2 |     0 | demo-credstuff-* 3,669           |  READY  |
| demo-noisy-microservice-dashboard                   |      8 |  3 |           3 |        0 |    2 |     0 | demo-noisy-traces 5,500          |  READY  |
| demo-noisy-microservice-customer-dashboard          |      8 |  3 |           3 |        0 |    2 |     0 | demo-noisy-traces 5,500          |  READY  |
| demo-gdpr-audit-dashboard                           |     10 |  4 |           6 |        0 |    0 |     0 | demo-gdpr-* 4,717                |  READY  |
| demo-gdpr-audit-customer-dashboard                  |     10 |  4 |           6 |        0 |    0 |     0 | demo-gdpr-* 4,717                |  READY  |
| demo-supply-chain-attack-dashboard                  |     10 |  4 |           6 |        0 |    0 |     0 | demo-supplychain-* 7,275         |  READY  |
| demo-supply-chain-attack-customer-dashboard         |     10 |  4 |           6 |        0 |    0 |     0 | demo-supplychain-* 7,275         |  READY  |
| fec-northwind-mtg-prev-001                            |      8 |  8 |           0 |        0 |    0 |     0 | n/a (markdown only)              |  READY  |

Totals: 11 dashboards, 104 panels, 0 empty panels detected, 0 missing
saved objects, 0 dangling Lens references.

## Notes and caveats

- **Lens live panels (Black Friday).** The Black Friday FE and Customer
  dashboards each include two Lens panels (`p99 latency by service (live)`
  and `Funnel: abandonment vs payment success (live)`). Their references
  are stored in the embedded Lens `attributes.references` rather than on
  the dashboard root references list. Both point at the
  `demo-blackfriday-metrics-dv` data view, which resolves to
  `demo-blackfriday-metrics` (600 docs, last ingest 2026-05-04T07:20Z).
  Verified directly via the embedded Lens config.
- **Noisy microservice Lens panels.** Errors-by-service and error-rate
  charts both reference `demo-noisy-traces-dv` -> `demo-noisy-traces`
  (5,500 docs, fresh).
- **Vega spec walker false positive cleared.** An initial pass flagged
  the Noisy `Deployment regression timeline`, Noisy `Error budget burn-down`,
  Supply Chain `14 day attack timeline`, and Supply Chain `Attack graph`
  as empty because their data lives under `layer[].data.values`. After
  switching the audit to a recursive walk those panels resolved with
  inline rows of 47, 168, 6, and 8+12 respectively. No empty panels
  remain.
- **fec-northwind-mtg-prev-001.** This is an all-markdown customer-fit
  dashboard (8 markdown panels, no charts). It does not have
  `timeRestore` set (timeFrom and timeTo are null) but does not need it
  because it has no time-bound visualizations. Verdict READY.
- **Time windows.** Default `timeFrom` / `timeTo` on every demo dashboard
  is wide enough to cover the seeded data (Credential Stuffing now-3d,
  Black Friday and Noisy now-7d, Supply Chain now-14d, GDPR now-90d).
  All seeded indices have at least one document inside the default window.

## Issues found

None blocking. All 11 dashboards passed structured verification with
zero empty panels, zero missing references, and zero dangling indices.

## Em / en dash audit

The report and all artifacts in `runtime/qa/dashboard_smoke/` were
hand-checked for em (U+2014) and en (U+2013) dashes. None present.
Dashboard titles in the source data do contain em / en dashes (for
example `[FE] Black Friday Outage - Field Engineer view`). Those are
external strings owned by the scenario seeders and were preserved as is
per the no-modify rule, but the surrounding prose in this report uses
ASCII hyphens only.

## Final verdict

Go for demo video recording. All 11 target dashboards are present in
Kibana, every panel has either inline data or a populated index
reference, every referenced index has fresh documents within the
default time window, and there are no missing data views or broken
Lens references. The only QA gap is that this audit was structural,
not pixel-level. If a final visual sanity check is desired, the
recommended path is to log in to Kibana once interactively, open each
dashboard ID, and screenshot. Loading times and Vega render quality
cannot be verified from saved-object inspection alone.
