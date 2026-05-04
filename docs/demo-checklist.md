# FE Copilot - Day-of-Submission Demo Checklist

> Single source of truth for the day Rodrigo records the take and submits the form.
> Plain hyphens only. No em or en dashes.
> Total elapsed time, end to end, target: 4 hours from "open laptop" to "form submitted".

---

## A. Pre-recording (15 items)

Run every item in order. If any check fails, stop and fix before continuing. The recording window is the most expensive part of the day; cheap fixes go here.

1. [ ] `cd /Users/rodrigocareaga/Downloads/FE-Elastic` and `source .venv/bin/activate`.
2. [ ] Confirm `.env` has both `ANTHROPIC_API_KEY=sk-ant-...` and `KIBANA_API_KEY=...`. If missing, source from 1Password.
3. [ ] `git status` is clean. `git pull origin main` if there are remote commits.
4. [ ] `PYTHONPATH=backend python -m pytest backend/tests -q` shows 30 of 30 passing in mock mode.
5. [ ] `rm -rf runtime/briefs runtime/post_meeting runtime/emails runtime/slack.log runtime/salesforce.log` for a clean slate. Keep `runtime/audit.jsonl` intact.
6. [ ] `PYTHONPATH=backend python -m scripts.generate_synthetic_data` to regenerate Revolut, MELI, and Santander records.
7. [ ] `docker compose -f infra/docker-compose.yml up -d` and confirm Elasticsearch responds at `http://127.0.0.1:9202` and Kibana at `http://127.0.0.1:5603`.
8. [ ] `PYTHONPATH=backend uvicorn app.main:app --port 8123 --log-level warning` in a dedicated terminal pane. Wait for the "Uvicorn running" line.
9. [ ] `curl -s http://127.0.0.1:8123/api/v1/health | jq .` returns `{"ok": true, ...}`.
10. [ ] `PYTHONPATH=backend python -m scripts.sync_agent_builder` returns `ok: true` for all 9 `fec_*` tools and the master agent.
11. [ ] `PYTHONPATH=backend python -m scripts.sync_kibana_workflow` returns rule status `active` (or use the `/workflows/sync` button).
12. [ ] Browser: clean Chrome profile or Arc Space. Sign out of personal accounts. Hide bookmarks bar. 110 percent zoom on every demo tab. Dark theme on.
13. [ ] Disable notifications: macOS Focus mode "Do Not Disturb", Slack snoozed for 1 hour, calendar alerts off, Mail closed.
14. [ ] Prime the Claude cache: open `/meeting.html?id=mtg-revolut-001`, run Pre-Meeting then Post-Meeting agents once each (so the second take hits cache); on `/agent-builder.html` send the "Chain: SPL plus cost" prompt once and clear the thread; on `/tools.html` run SPL converter, Cost calc, Compliance mapper once each.
15. [ ] Recording setup: Loom or QuickTime at 1080p / 30fps, mic test playback green, webcam framed lower-right at 280px wide, captions enabled, click highlighting on, vertical split with browser left two-thirds and terminal right one-third.

---

## B. Recording (31 storyboard shots)

> See `docs/storyboard.md` for the full per-shot table (URL, action sequence, overlay caption, voiceover cue, b-roll, pre-conditions). The list below is the index. Do not re-read the storyboard mid-take; trust the prep.

| Beat | Shots | Time | Location |
|---|---|---|---|
| Hook | 01, 02, 03 | 0:00 - 0:25 | Webcam slate, dashboard, calendar inbox |
| Pre-meeting | 04, 05, 06, 07, 08, 09 | 0:25 - 1:25 | Revolut meeting view |
| Live Companion | 10, 11, 12, 13, 14 | 1:25 - 2:15 | Revolut meeting view, Live tab |
| Post-meeting plus Salesforce | 15, 16, 17, 18, 19, 20 | 2:15 - 3:15 | Revolut meeting view, Post tab plus terminal |
| Tools rail | 21, 22, 23, 24, 25 | 3:15 - 4:00 | `/tools.html` panels 02, 04, 03 |
| Agent Builder | 26, 27, 28 | 4:00 - 4:30 | `/agent-builder.html` |
| Workflow | 29, 30 | 4:30 - 4:50 | `/workflow-demo.html` |
| Outro | 31 | 4:50 - 5:00 | Dashboard plus end slate |

Per-shot rules:

- Read the on-screen overlay caption as written. Do not improvise the caption text.
- Voiceover language: English first take, Spanish second take if time allows. The form takes one video; pick the EN take unless the judges' panel skews ES.
- If a shot fails, do not stop the take. Continue, and re-shoot only the failing shot in a separate clip; stitch in post.
- Hard cap: three takes total. Pick the best, do not keep re-recording past three.

---

## C. Post-recording (5 items)

1. [ ] Trim head and tail to the first frame of slate and the last frame of the end slate. Use Loom's built-in trim or QuickTime's "Trim" command.
2. [ ] Captions: enable Loom auto-captions, then proofread them against `docs/demo-script.md`. Fix any misread vendor names (Datadog, Splunk, Cribl, MEDDPICC, ES|QL).
3. [ ] Upload to Google Drive folder shared internally at Elastic (`Elastic > FE > FY27 SKO Hackathon > Submissions`). Set sharing to "Anyone at Elastic with the link".
4. [ ] Get the shareable link. Verify it opens in an incognito Chrome window without auth prompts (Elastic SSO redirect is acceptable; password prompt is not).
5. [ ] Paste the Drive link into the "Demo URL" placeholder at the top of `docs/submission.md`. Commit the change locally.

---

## D. Submission

1. [ ] Open the FY27 SKO FE Summit Hackathon submission form.
2. [ ] Paste each field from `docs/submission.md` into the form: Title, One-liner, Description, judging mapping, Demo URL, Repo URL, Tech stack, Team, Time to value, Languages.
3. [ ] Re-read every pasted field once for typos before clicking Submit.
4. [ ] Click Submit. Screenshot the confirmation page; save to `runtime/submission_confirmation.png`.
5. [ ] Send the confirmation screenshot plus the Drive link to the internal Slack channel (`#fy27-sko-fe-summit` or whichever the org has stood up).
6. [ ] Save the form's confirmation email to a `Hackathon FY27` Gmail label.
7. [ ] Add a calendar reminder for the day after the announcement: "FE Copilot hackathon retro: write up what worked, what did not, and what to ship into FE Copilot v2." Set the reminder for 2026-05-15 09:00.
8. [ ] Close the laptop. Eat something.
