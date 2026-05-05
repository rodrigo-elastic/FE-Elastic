# FE Copilot - Submission Readiness Checklist

> Single source of truth for shipping the FY27 SKO FE Summit Hackathon submission. Built by Rodrigo Careaga. Deadline: 2026-05-10 23:59 ET.

Read this top to bottom on the day of recording, then on the day of submission. Every item has a status (READY, ACTION-REQUIRED, BLOCKED) and the person responsible.

---

## 1. Hackathon eligibility

| Item | Status | Owner |
|---|---|---|
| FE org membership | READY | Rodrigo (already FE) |
| Solo team OK | READY | Rules allow solo |
| Sign-up form submitted | **ACTION-REQUIRED by 2026-05-06 midnight ET** | Rodrigo |
| Cross-functional input flagged appropriately | READY | Solo, no cross-functional submitters |
| All work created for the hackathon | READY | Repo timeline since 2026-05-03, every commit dated post-announcement |
| No customer data used | READY | All 8 fictional customers (Northwind Pay, Banco Atlántico, Mercado Atlas, Atlas Health, Federal Demonstration Agency, Helix Bank, Atlas Eyewear, Fjordbank); demo banner explicit; W23B compliance audit confirms 0 leaks |

---

## 2. Live system state

| | Count | Source of truth |
|---|---|---|
| MCP tools registered in Kibana | 12 | `backend/scripts/sync_agent_builder.py` MCP_TOOLS list |
| Agents in Kibana (master + 3 user-built) | 4 | `/api/v1/agent-builder/agents` (master `fec_field_assistant` plus `fec_user_migration_specialist`, `fec_user_compliance_pursuit`, `fec_user_rfp_responder`) |
| Battlecards (sorted by global marketshare) | 31 | `backend/data/seed/battlecards.json` |
| Industries (cover ~80% of customers) | 20 | `data/seed/industries.json` |
| Demo scenarios (paired FE + Customer dashboards) | 8 | `backend/app/services/scenarios/` |
| Kibana dashboards live | 16 | `/api/v1/health/full` `demo_data.dashboards` |
| Kibana workflows | 2 alerting rules + 1 webhook handler (renewal) | `backend/app/api/routes_workflows.py` |
| FE Brain corpus | 1300 chunks (live ES count: 3837 with W26D drift) | `fec-knowledge` index |
| Frontend pages | 13 | `frontend/*.html` |
| Locales | 5 (EN, ES, JA, DE, FR) | `frontend/assets/js/i18n.js` 414 keys per locale |
| Backend tests | 30 of 30 passing | `backend/tests/` |
| E2E test harness | 12 of 13 PASS | `backend/scripts/e2e_tests.py` |
| API contract tests | 0 violations | `backend/scripts/api_contract_tests.py` |
| Link crawler | 55 URLs depth-2, 0 broken | `backend/scripts/link_crawler.py` |
| Integration smoke | 9 of 9 GO | `backend/scripts/integration_smoke.py` |

---

## 3. QA artifacts (overnight batches)

5 waves, 19 sub-agents, 17 audit reports. All landed in `docs/qa-w*-*.md`.

| Wave | Batches | Outcome |
|---|---|---|
| W19 | a11y baseline, compliance, perf, e2e | Foundational pass, 100% green |
| W23 | a11y deep, compliance, perf CWV, e2e regression | 16 a11y findings fixed; 11 of 11 pages green CWV; 0 regressions |
| W24 | dark mode, cmd palette, link crawler | 8 dark fixes; 28 cmd commands plus 31 battlecards plus 20 industries indexed; 55 URLs clean (mobile skipped per user) |
| W25 | data integrity, API contracts, error paths, retry policy | 7 sanitizer fixes, 33 contract violations fixed, 12 sanitizeError migrations, NEW api-retry.js |
| W26 | copy QA EN, i18n, SEO/social, demo data freshness | 23 stale numbers refreshed, 414 keys per locale, sitemap+robots+manifest, dates shift relative to NOW |
| W27 | deps, secrets, build repro, docs lint | 3 CVEs fixed, 0 secrets in history, 2.62 s warm boot, 7 of 7 README claims verified |

Total: 0 functional regressions across 5 waves.

---

## 4. Recording prep (do these BEFORE rolling tape)

### Production setup (review `docs/video-script-v2.md`)

- Cam A: medium shot, centered, locked focus on eyes, 5500 K WB
- Cam B: 30 to 45 deg off-axis, tighter framing, same WB
- Shure mic: 15 cm from mouth off-axis 20 deg, 48 kHz 24-bit, pop filter on
- Elgato Key Light: 45 deg above eye, 4500 to 5500 K, 30 to 40 percent brightness
- Slate clap at start of every take so audio syncs

### Environment

- Door closed, phone on Do Not Disturb, Mac in Focus mode
- Browser fullscreen, bookmarks bar hidden
- Click X on the demo-data banner so the amber strip is gone
- Pre-open these tabs (in order): /, /quick-research.html, /customers.html, /fe-brain.html, /agent-builder.html, /battlecards.html, /industries.html, /workflow-demo.html, /health.html
- Run the autopilot once 5 minutes before the take so all 9 iframes are warm
- Top up Anthropic credits if you want the live FE Brain query in the close-up to actually return

### Voice warm-up (5 minutes)

- Hum a 5-note scale up and down for 90 seconds
- "The lips, the teeth, the tip of the tongue" times 5
- Water at room temperature, no dairy, no caffeine in the last 30 min

---

## 5. Recording (the take)

Plan for 3 takes minimum. Block 60 minutes.

| Take | Goal |
|---|---|
| 1 | Warm-up. Expect to discard. Hit all 9 beats; do not stop on small stumbles. |
| 2 | Production take. All 9 beats clean. Energy holds through the autopilot silence. |
| 3 | Insurance take, alt deliveries on the CTA if you want options. |

If take 2 nails it, take 3 is optional.

### Beat timing reminder (from `docs/video-script-v2.md`)

| Time | Beat |
|---|---|
| 0:00-0:08 | Hook (Cam B): "Every Field Engineer at Elastic loses six hours a week..." |
| 0:08-0:18 | Promise (Cam A): "FE Copilot gives those hours back. One click. Forty five seconds. Watch." |
| 0:18-1:00 | Autopilot (Cam A locked, SILENT, captions narrate) |
| 1:00-1:05 | Pivot (Cam B): "Now let me show you why each one matters." |
| 1:05-1:25 | FE Brain (Cam A then Cam B): "Stop pinging Slack." |
| 1:25-1:50 | Agent Builder (Cam A): "RFP Responder. Migration. Compliance. Lives in your Kibana cluster." |
| 1:50-2:15 | Battlecards plus Industries (Cam A): "Sorted by marketshare." |
| 2:15-2:35 | Customers Kanban (Cam A): "Same color across the Kanban means same account." |
| 2:35-2:50 | Workflows (Cam B then Cam A): "The rep does nothing." |
| 2:50-3:00 | CTA (Cam B): "Six hours back. github dot com slash rodrigo dash elastic slash F E dash Elastic. Take it home." |

Total spoken words: 232. Silent autopilot: 42 s. Demo click time: 46 s. Math closes at 3:00 plus or minus 2 seconds.

---

## 6. Post-production

1. Sync audio to Cam A using slate clap.
2. Mute Cam A and Cam B audio. Use Shure mic as sole audio track.
3. Apply 11-cut camera map from `docs/video-script-v2.md` Section 5.
4. Color: lift shadows +5, drop highlights -5; match Cam B to Cam A on a neutral surface.
5. Audio: high-pass at 100 Hz, light de-esser if needed, target -16 LUFS integrated.
6. Captions: Whisper-large transcribe, manual cleanup, burn in (not YouTube auto-cc).
7. Export 1080p H.264 at 10 Mbps, 48 kHz AAC at 256 kbps, mp4.
8. Final length 3:00 plus or minus 2 seconds.
9. Filename: `FE-Copilot-FY27-SKO-Hackathon-RodrigoCareaga.mp4`

---

## 7. Submission form (copy-paste ready, see `docs/submission.md`)

| Field | Source |
|---|---|
| Title (under 70 chars) | "FE Copilot: 3 Agents and 12 MCP Tools for Every Elastic Field Engineer" (66 chars) |
| One-liner (140 max) | "Calendar invite to sourced brief, live MEDDPICC whisper, one-click SFDC sync. 3 agents, 12 MCP tools. Built on Claude. Lives in Elastic." (138 chars) |
| Description (250 words) | See `docs/submission.md` "Description" section |
| FE Impact paragraph | See `docs/submission.md` "Judging criteria mapping" |
| Workflows + Agent Builder paragraph | Same |
| Polish paragraph | Same |
| Reusability paragraph | Same (incl. "Complementary, not duplicate" framing for Klue/Highspot) |
| Demo Quality paragraph | Same |
| Demo URL | gDrive video link (paste after upload) |
| Repo URL | https://github.com/rodrigo-elastic/FE-Elastic |
| Live cluster URL | https://fe-summit-hackathon-ed0e8e.kb.us-west-1.aws.found.io |
| Anthropic tokens needed | Note in form: yes, additional tokens for May |

---

## 8. Risk register (mitigations in place)

| Risk | Mitigation |
|---|---|
| Anthropic credits exhausted mid-demo | Graceful fallback to mock_payload in `claude_client.call_structured`. Demo continues, audit log records mode=fallback |
| ngrok tunnel rotates during recording | Backend supervisor restarts sync. Re-record affected beat |
| Kibana cluster slow or 502 | `/workflows/status` swallows exceptions and returns 200 with rule_status=probe-error. UI shows red pill, page still renders |
| ES cluster down | `/health/full` returns yellow with warnings. Battlecards, industries, demo-data fall back to seed |
| Browser offline | Friendly "Network unavailable" toast (no service worker, partial mitigation) |
| Backend dies overnight | Restart command: `pkill -f 'uvicorn.*8123'; PYTHONPATH=backend nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8123 > /tmp/fec-backend.log 2>&1 &` |
| Real customer name leak | W12A rename + W21 cleanup + W23B compliance audit; 0 leaks in user-facing copy |
| Em-dash leak (looks AI-generated) | 0 hits across 230+ files in every smoke run; `—`/`–` literal escapes used in any audit script that needs to mention them |

---

## 9. Final pre-submission checklist (the day of)

In order:

1. [ ] Sign-up form submitted (deadline May 6)
2. [ ] Anthropic credits topped up
3. [ ] Smoke 9/9 GO: `PYTHONPATH=backend .venv/bin/python -m scripts.integration_smoke`
4. [ ] E2E pass: `PYTHONPATH=backend .venv/bin/python -m scripts.e2e_tests` (10 of 12 PASS, 2 SKIP, 0 FAIL)
5. [ ] Link crawler clean: `PYTHONPATH=backend .venv/bin/python -m scripts.link_crawler`
6. [ ] Em-dash audit 0 across the repo
7. [ ] Practice run with the teleprompter from start to finish
8. [ ] Cameras + lights + mic dialed in
9. [ ] Take 1 (warm-up)
10. [ ] Take 2 (production take)
11. [ ] Take 3 (insurance) optional
12. [ ] Pick the best take, run post-production
13. [ ] Export 1080p mp4 at 3:00 plus or minus 2 s
14. [ ] Upload to gDrive, share "anyone at Elastic with the link can view"
15. [ ] Paste video link into `docs/submission.md` (and into the submission form)
16. [ ] Fill the submission form using `docs/submission.md` as source
17. [ ] Submit before 2026-05-10 23:59 ET
18. [ ] Post in `#sko27fe-hackathon` that you submitted (optional but builds momentum)

---

## 10. What is NOT shipping (honest scope)

- Klue, Highspot, Salesforce, Gainsight, Slack live integrations are NOT wired. Their MCP tool stubs are documented in `docs/architecture.md` "Complementary integration with existing FE tooling" as a 1-day swap when greenlit.
- Mobile responsive: skipped per user direction, current breakpoints work but a deep mobile pass was not done.
- Service worker / offline mode: friendly toast only, no full PWA caching.
- Multi-tenant: single-FE deployment. Concurrent demo would need session isolation.
- LLM live: requires Anthropic credits topped up. Mock fallback covers the demo if credits run out.
- Real customer data: never used. The 8 demo accounts are fictional.

This honest-scope statement is also referenced in `docs/submission.md` Reusability paragraph and in the README.

---

## 11. Reports index

All overnight QA findings live here. Read on demand:

| Report | Topic |
|---|---|
| `docs/qa-w19-*.md` | Foundational a11y + compliance + perf + e2e |
| `docs/qa-w23a-a11y-deep.md` | Deep WCAG 2.1 AA, 16 fixes |
| `docs/qa-w23b-compliance.md` | Privacy + customer-name compliance |
| `docs/qa-w23c-perf.md` | Core Web Vitals across 11 pages |
| `docs/qa-w23d-e2e-regression.md` | 12 of 13 user journeys |
| `docs/qa-w24b-dark-mode.md` | Dark theme parity, 8 fixes |
| `docs/qa-w24c-cmd-palette.md` | Cmd+K, 28 commands + 31 cards + 20 industries |
| `docs/qa-w24d-link-crawler.md` | 55 URLs, 0 broken |
| `docs/qa-w25a-data-integrity.md` | Sanitizer hardening, 50-record stress |
| `docs/qa-w25b-api-contracts.md` | 33 violations fixed, 0 remaining |
| `docs/qa-w25c-error-paths.md` | 6 failure modes, 5 PASS plus 1 partial |
| `docs/qa-w25d-retry-timeout.md` | 11 callers migrated to api-retry |
| `docs/qa-w26a-copy.md` | EN copy QA, 23 stale numbers |
| `docs/qa-w26b-i18n.md` | 414 keys per locale |
| `docs/qa-w26c-seo.md` | OG, Twitter, sitemap, manifest |
| `docs/qa-w26d-demo-data-freshness.md` | NOW-relative dates |
| `docs/qa-w27a-deps.md` | 3 CVEs fixed |
| `docs/qa-w27b-secrets.md` | 0 secrets in history |
| `docs/qa-w27c-build-repro.md` | 2.62 s warm boot |
| `docs/qa-w27d-docs-lint.md` | 7 of 7 README claims verified |

---

## 12. One-line summary for the submission form

If you only have one line to paste, use this:

> FE Copilot: 12 MCP tools, 3 agents, 8 demo scenarios, 31 battlecards, 20 industries, 5 languages, 13 frontend pages, 30 of 30 backend tests, 9 of 9 smoke green, 0 of 230+ em dashes, 0 customer-name leaks. Six hours per FE per week back. Apache 2 oh wait, MIT.
