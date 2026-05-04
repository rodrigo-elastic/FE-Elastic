# FE Copilot - Day-of-Submission Demo Checklist

> Single source of truth for the day Rodrigo records the take and submits the form.
> Plain hyphens only. No em or en dashes.
> Total elapsed time, end to end, target: 4 hours from "open laptop" to "form submitted".
> The recording window is the most expensive part of the day. Cheap fixes go in pre-recording. Do not skip an item.

---

## A. Pre-recording (18 items)

Run every item in order. If any check fails, stop and fix before continuing.

1. [ ] `cd /Users/rodrigocareaga/Downloads/FE-Elastic` and `source .venv/bin/activate`.
2. [ ] Confirm `.env` has `ANTHROPIC_API_KEY=sk-ant-...`, `KIBANA_API_KEY=...`, and `ELASTICSEARCH_URL` pointing at the live cluster. If anything is missing, source from 1Password.
3. [ ] `git status` is clean. `git pull origin main` if there are remote commits.
4. [ ] `PYTHONPATH=backend python -m pytest backend/tests -q` shows 30 of 30 passing in mock mode.
5. [ ] Start backend: `PYTHONPATH=backend uvicorn app.main:app --port 8123 --log-level warning` in a dedicated terminal pane. Wait for the "Uvicorn running on http://127.0.0.1:8123" line.
6. [ ] Start ngrok: `ngrok http 8123 --log=stdout > runtime/ngrok.log &` then `cat runtime/last_ngrok_url` confirms the URL is recorded. The webhook is reachable from Kibana.
7. [ ] Run integration smoke: `PYTHONPATH=backend python -m scripts.integration_smoke`. Confirm GO across all checks (Anthropic, Elasticsearch, Kibana, Agent Builder, workflows, ad-hoc endpoints, RAG retrieval). Do not record on any RED.
8. [ ] Re-seed all 5 demo scenarios: via curl loop: `for s in black-friday-outage credential-stuffing noisy-microservice gdpr-audit-timeline supply-chain-attack; do curl -sS -X POST http://127.0.0.1:8123/api/v1/demo-data/$s/seed -o /dev/null -w "$s: %{http_code}\\n"; done`. All 5 should return 200.
9. [ ] Sync Agent Builder: `PYTHONPATH=backend python -m scripts.sync_agent_builder` returns `ok: true` for all 11 `fec_*` tools and the master agent `fec_field_assistant`.
10. [ ] Sync both Kibana workflows: `curl -sS -X POST http://127.0.0.1:8123/api/v1/workflows/sync | jq` returns ok. `curl -sS http://127.0.0.1:8123/api/v1/workflows/status | jq '.workflows'` shows both rules and both connectors registered.
11. [ ] Reset browser localStorage: in DevTools console on each demo page run `localStorage.clear()`. Pages: `/`, `/fe-brain.html`, `/meeting.html?id=santander-mtg-prev-001`, `/agent-builder.html`, `/battlecards.html`, `/demo-data.html`, `/workflow-demo.html`. Then close DevTools.
12. [ ] Open all 9 tabs in the order specified in `docs/storyboard.md` (homepage, fe-brain, backup meeting, agent-builder, battlecards, demo-data, workflow-demo, Kibana dashboards, plus a terminal pane). Pin each tab.
13. [ ] Set browser zoom to 110 percent on every demo tab (`Cmd =` twice from default). Hide bookmarks bar (`Cmd Shift B`).
14. [ ] Pick the theme. Light or Dark, set system-wide and confirm every page renders cleanly. Default: Dark on macOS, with the FE Copilot UI in its dark theme. Both work; pick one and stick with it for the take.
15. [ ] Verify the autopilot dry-run: click "Show me the magic" on the homepage. The full 7 step run completes inside 40 seconds with zero failed steps. Watch the completion card report a non-zero brief id and a cost under ten cents. Click "Watch again" to confirm the run is repeatable. Then refresh the homepage so the button is fresh for the take.
16. [ ] Verify Cmd+K opens the command palette on at least three pages (homepage, meeting view, battlecards). Press Esc to close. Confirm the palette mounts within 200ms.
17. [ ] Verify Field Assistant returns within 30 seconds: on the meeting page used by B3, click the "POV plan + TCO" chip and confirm a streamed response with two visible tool-call cards lands inside 30 seconds. Refresh the page to clear the response after the dry run.
18. [ ] Recording setup: Loom or QuickTime at 1080p / 30fps, mic test playback green, webcam framed lower-right at 280px wide (or off if you prefer voice-only), captions enabled, click highlighting on, vertical split with browser left two-thirds and terminal right one-third. macOS Focus mode "Do Not Disturb" on. Slack snoozed for 1 hour. Calendar alerts off. Mail closed.

---

## B. Recording (9 beats, 5:00 total)

> See `docs/storyboard.md` for the full per-shot table (URL, click sequence, overlay caption, voiceover cue, b-roll). The list below is the index. Do not re-read the storyboard mid-take; trust the prep.

| Beat | Shots | Time | Storyboard pointer |
|---|---|---|---|
| B0 Title slate | 01 | 0:00 - 0:10 | Slate, no clicks. Read the slate line. |
| B1 Autopilot | 02 to 07 | 0:10 - 0:50 | Click "Show me the magic" once. Stay silent. Captions narrate. |
| B2 FE Brain | 08 to 11 | 0:50 - 1:30 | Click ILM chip on `/fe-brain.html`. Voiceover: ELSER hybrid retrieval, 5 of 5. |
| B3 Pre-meeting brief | 12 to 15 | 1:30 - 2:00 | Banking template, type "Banco Santander", click an EDGAR link. |
| B4 Auro orchestrator | 16 to 19 | 2:00 - 2:40 | Field Assistant chip "POV plan + TCO". Voiceover: Auro is the conductor (twice). |
| B5 Battlecards + Sloane | 20 to 23 | 2:40 - 3:15 | Click Splunk card. Chip "TCO at 200 GB/day". Read $112k vs $443k, 74.66 percent. |
| B6 Demo Data + dashboards | 24 to 27 | 3:15 - 4:00 | Black Friday FE then Customer dashboard. Voiceover: same data, two audiences. |
| B7 Two workflows | 28 to 31 | 4:00 - 4:45 | Fire demo transcript. Tail SFDC log. Read the agents-trigger-workflows line. |
| B8 Outro | 32 | 4:45 - 5:00 | Five chips, GitHub URL, stack lockup, "thank you". |

Per-beat rules:

- Read the on-screen overlay caption as written. Do not improvise.
- B1 is silent for the presenter. The autopilot captions carry the narration. If you talk over the autopilot, cut and restart.
- Voiceover language: English first take, Spanish second take if time allows. Submit the EN take unless the judges' panel skews ES. Both versions live in `docs/demo-script.md`.
- If a single shot fails, do not stop the take. Continue, and re-shoot only the failing shot in a separate clip; stitch in post.
- Hard cap: three full takes total. Pick the best, do not keep re-recording past three.

---

## C. Post-recording (5 items)

1. [ ] Trim head and tail to the first frame of the slate and the last frame of the GitHub URL hold. Use Loom's built-in trim or QuickTime's "Trim" command.
2. [ ] Captions: enable Loom auto-captions, then proofread them against `docs/demo-script.md`. Fix any misread vendor names (Datadog, Splunk, Cribl, Banco Santander, MEDDPICC, ES dot Q L, ELSER). Confirm the autopilot captions appear (Loom captions the autopilot caption bar's spoken words; if the autopilot captions are display-only and not transcribed, add them as on-screen text in post).
3. [ ] Upload to the Google Drive folder shared internally at Elastic (`Elastic > FE > FY27 SKO Hackathon > Submissions`). Set sharing to "Anyone at Elastic with the link".
4. [ ] Get the shareable link. Verify it opens in an incognito Chrome window without auth prompts (Elastic SSO redirect is acceptable; password prompt is not).
5. [ ] Paste the Drive link into the "Demo URL" placeholder at the top of `docs/submission.md`. Commit the change locally.

---

## D. Submission (8 items)

1. [ ] Open the FY27 SKO FE Summit Hackathon submission form.
2. [ ] Paste each field from `docs/submission.md` into the form: Title, One-liner, Description, judging mapping, Demo URL, Repo URL, Tech stack, Team, Time to value, Languages.
3. [ ] Attach the video link in the form's Demo URL field. Re-read every pasted field once for typos before clicking Submit.
4. [ ] Click Submit. Screenshot the confirmation page; save to `runtime/submission_confirmation.png`.
5. [ ] Post the Slack draft from `docs/announcements.md` to the internal Slack channel (`#fy27-sko-fe-summit` or whichever the org has stood up). Include the Drive link, the GitHub URL, and the screenshot.
6. [ ] Save the form's confirmation email to a `Hackathon FY27` Gmail label.
7. [ ] Add a calendar reminder for the day after the announcement: "FE Copilot hackathon retro: write up what worked, what did not, and what to ship into FE Copilot v2." Set the reminder for 2026-05-15 09:00.
8. [ ] Close the laptop. Eat something.
