# FE Copilot - Day-of-Submission Demo Checklist

> Single source of truth for the day Rodrigo records and submits.
> Plain hyphens only. No em or en dashes.
> Hard cap: 3:00 (180 s), single take, English voiceover only.
> Target end-to-end: 4 hours from "open laptop" to "form submitted".

---

## A. Pre-recording (14 items)

Run in order. If any check fails, stop and fix.

1. [ ] `cd /Users/rodrigocareaga/Downloads/FE-Elastic` and `source .venv/bin/activate`.
2. [ ] `.env` has `ANTHROPIC_API_KEY`, `KIBANA_API_KEY`, `ELASTICSEARCH_URL` for the live cluster. Source from 1Password if missing.
3. [ ] `git status` clean. `git pull origin main` if behind.
4. [ ] `PYTHONPATH=backend python -m pytest backend/tests -q` shows 30 of 30 passing in mock mode.
5. [ ] Start backend: `PYTHONPATH=backend uvicorn app.main:app --port 8123 --log-level warning`. Wait for the "Uvicorn running" line.
6. [ ] Start ngrok: `ngrok http 8123 --log=stdout > runtime/ngrok.log &`. `cat runtime/last_ngrok_url` confirms the webhook URL is reachable from Kibana.
7. [ ] Integration smoke: `PYTHONPATH=backend python -m scripts.integration_smoke`. GO across all checks (Anthropic, Elasticsearch, Kibana, Agent Builder, workflows, ad-hoc, RAG). Do not record on any RED.
8. [ ] Re-seed the 5 scenarios: `for s in black-friday-outage credential-stuffing noisy-microservice gdpr-audit-timeline supply-chain-attack; do curl -sS -X POST http://127.0.0.1:8123/api/v1/demo-data/$s/seed -o /dev/null -w "$s: %{http_code}\n"; done`. All 5 return 200.
9. [ ] Sync Agent Builder and workflows: `PYTHONPATH=backend python -m scripts.sync_agent_builder` returns ok for the 11 `fec_*` tools and `fec_field_assistant`. Then `curl -sS -X POST http://127.0.0.1:8123/api/v1/workflows/sync | jq` returns ok and `curl -sS http://127.0.0.1:8123/api/v1/workflows/status | jq '.workflows'` shows both rules registered.
10. [ ] Reset localStorage: in DevTools console run `localStorage.clear()` on `/`, `/fe-brain.html`, `/meeting.html?id=santander-mtg-prev-001`, `/battlecards.html`, `/demo-data.html`, `/workflow-demo.html`. Close DevTools.
11. [ ] Open the 7 tabs from `docs/storyboard.md` in pre-flight order, plus the terminal pane ready for `tail -f runtime/salesforce.log`. Pin every tab. Browser zoom 110 percent. Hide bookmarks bar (`Cmd Shift B`).
12. [ ] Autopilot dry-run: click "Show me the magic". The 7-step run completes inside 27 s with zero failed steps. Card reports a brief id and cost under ten cents. Refresh the homepage.
13. [ ] Pre-prime Workflow 2: 90 s before recording, click "Fire demo transcript" once on `/workflow-demo.html` so the orphan `[Auto]` wave is in flight when B6 starts.
14. [ ] Recording setup: 1080p / 30fps, mic green, captions on, click highlighting on, browser two thirds left, terminal one third right. Do Not Disturb on. Slack snoozed. Mail closed.

---

## B. Recording (8 beats, 3:00 total)

> Per-shot detail in `docs/storyboard.md`. Do not re-read mid-take; trust the prep.

| Beat | Shots | Time | Storyboard pointer |
|---|---|---|---|
| B0 Title slate | 01 | 0:00 - 0:08 | Slate, no clicks. Read the slate line. |
| B1 Autopilot | 02 to 04 | 0:08 - 0:35 | Click "Show me the magic". 27 s of silence. Captions narrate. |
| B2 FE Brain | 05 to 06 | 0:35 - 0:55 | Chip "Set up semantic_text with ELSER on Elastic Cloud". Citations. |
| B3 Auro orchestrator | 07 to 09 | 0:55 - 1:25 | On the autopilot's meeting, Field Assistant chip "POV plan + TCO". |
| B4 Battlecards plus Sloane | 10 to 12 | 1:25 - 1:55 | Splunk card, chip "TCO at 200 GB/day". $112k vs $443k, 74.66 percent. |
| B5 Demo Data plus dashboards | 13 to 15 | 1:55 - 2:25 | Black Friday FE then Customer dashboard via switcher. |
| B6 Two workflows | 16 to 18 | 2:25 - 2:50 | Fire transcript, tail SFDC log, watch the `[Auto]` wave land. |
| B7 Outro | 19 | 2:50 - 3:00 | Homepage, GitHub URL, stack lockup, dissolve. |

Per-beat rules:
- Read the on-screen overlay caption as written.
- B1 is silent for the presenter. If you talk over the autopilot, cut and restart.
- English only. Spanish is not in the take.
- If one shot fails, do not stop. Re-shoot the failing shot in a separate clip; stitch in post.
- Three full takes max. Pick the best.

---

## C. Post-recording (5 items)

1. [ ] Trim head and tail to the first frame of the slate and the last frame of the GitHub URL hold.
2. [ ] Captions: enable Loom auto-captions, then proofread against `docs/demo-script.md`. Fix vendor names (Datadog, Splunk, Cribl, Banco Santander, MEDDPICC, ES dot Q L, ELSER). Add the autopilot caption strings as on-screen text in post if Loom misses them.
3. [ ] Upload to Google Drive (`Elastic > FE > FY27 SKO Hackathon > Submissions`). Sharing: "Anyone at Elastic with the link".
4. [ ] Verify the share link opens in incognito Chrome without a password prompt (SSO redirect is fine).
5. [ ] Paste the Drive link into the "Demo URL" placeholder at the top of `docs/submission.md`. Commit locally.

---

## D. Submission (7 items)

1. [ ] Open the FY27 SKO FE Summit Hackathon submission form.
2. [ ] Paste each field from `docs/submission.md` into the form: Title, One-liner, Description, judging mapping, Demo URL, Repo URL, Tech stack, Team, Time to value, Languages.
3. [ ] Re-read every pasted field once for typos. Click Submit.
4. [ ] Screenshot the confirmation page; save to `runtime/submission_confirmation.png`.
5. [ ] Post the Slack draft from `docs/announcements.md` to `#fy27-sko-fe-summit`. Include Drive link, GitHub URL, screenshot.
6. [ ] Save the form's confirmation email to a `Hackathon FY27` Gmail label.
7. [ ] Add a calendar reminder for 2026-05-15 09:00: "FE Copilot hackathon retro: what worked, what did not, what ships into v2."
