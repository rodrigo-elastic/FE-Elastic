# FE Copilot - Demo Storyboard (3 minutes, single take)

> Presenter: Rodrigo Careaga, Senior Customer Architect, Elastic.
> Hard cap: 3:00 (180 s), 19 shots across 8 beats.
> Capture: 1080p, 110 percent zoom, dark theme, captions on. English voiceover only.

Backend on `http://127.0.0.1:8123`. Voiceover cues are keywords; full lines in `docs/demo-script.md`.

---

## Why this matters

The average Elastic Field Engineer loses 30 to 40 minutes of unbilled prep per meeting, splits attention to type notes during the call, and drops another 30 to 60 minutes on Salesforce hygiene afterward. Splunk TCO escalations pull a Solutions Engineer for 1 to 2 hours; compliance mappings cost $400 to $600 per hour. FE Copilot returns roughly 6 hours per FE per week and delivers a cited brief in 90 seconds, a POV plan in 30 seconds, and a Splunk TCO in 8 seconds.

---

## Pre-flight tab order (7 tabs plus terminal)

Pin in order. `Cmd <number>` chains the demo.

1. `http://127.0.0.1:8123/` (Homepage, autopilot CTA. B0, B1, B7.)
2. `http://127.0.0.1:8123/fe-brain.html` (B2.)
3. `http://127.0.0.1:8123/meeting.html?id=atlantico-mtg-prev-001` (Backup meeting view if the autopilot's freshly minted id misbehaves. B3 normally lives on the autopilot's redirect target.)
4. `http://127.0.0.1:8123/battlecards.html` (B4.)
5. `http://127.0.0.1:8123/demo-data.html` (B5.)
6. `http://127.0.0.1:8123/workflow-demo.html` (B6.)
7. `https://fe-summit-hackathon-ed0e8e.kb.us-west-1.aws.found.io/app/dashboards` (Kibana paired views, B5.)

Terminal pane (right one third), cwd `/Users/rodrigocareaga/Downloads/FE-Elastic`, ready for `tail -f runtime/salesforce.log`. The agent-builder tab and the second backup-meeting tab from the 5:00 storyboard are removed; both were fallbacks for cut beats.

---

## Shot-by-shot table

| # | Time | Beat | URL / pane | Click sequence | Overlay caption | VO cue | Pain anchored |
|---|---|---|---|---|---|---|---|
| 01 | 0:00 - 0:08 | B0 Title | Keynote slate | Hold the slate. No clicks. | FE Copilot. 11 personas. 5 scenarios. 2 workflows. | "six hours a week, back" | 6 hours per FE per week of unbilled toil. |
| 02 | 0:08 - 0:17 | B1 Autopilot | `/` | Click "Show me the magic". Steps 1 to 2 fire. | Quick Research, Banco Atlántico. SEC EDGAR. | (silent) | 40 minute pre-meeting brief collapses to 90 seconds. |
| 03 | 0:17 - 0:26 | B1 Autopilot | iframe `/meeting.html` | Steps 3 to 4. Brief renders, Field Assistant auto-runs. | Auro chains POV plan and TCO. | (silent) | POV plan and TCO that normally take half a day. |
| 04 | 0:26 - 0:35 | B1 Autopilot | iframe `/workflow-demo.html` plus card | Steps 5 to 7. Card: "Demo complete. ~$0.07". | Workflow fires. SFDC plus Slack. Done. | (silent) | Salesforce hygiene that gets skipped on Friday night. |
| 05 | 0:35 - 0:45 | B2 FE Brain | `/fe-brain.html` | Cmd 2. Click chip "Set up semantic_text with ELSER on Elastic Cloud". | ELSER hybrid. 407 chunks. | "stop pinging Slack" | 5 to 10 daily Slack pings for ES-QL or ELSER syntax. |
| 06 | 0:45 - 0:55 | B2 FE Brain | same | [1] [2] [3] paint. Pan cursor to citation cards. | Every claim grounded. | "ten seconds, not five minutes" | Knowledge gaps; 10 seconds vs a 5 minute Slack ping. |
| 07 | 0:55 - 1:05 | B3 Auro | autopilot meeting | Scroll to Field Assistant. Click chip "POV plan + TCO". | Auro orchestrator. | "one chip" | POV plan writing burns 2 to 4 hours per account. |
| 08 | 1:05 - 1:15 | B3 Auro | same | Two tool-call cards render: `fec_poc_plan` and `fec_cost_calc`. | Parallel tool calls. | "two in parallel" | Cross-customer learnings stuck in 40 Notion pages. |
| 09 | 1:15 - 1:25 | B3 Auro | same | Synthesis renders. Underline heading. Hold. | One coherent answer. | "three hours becomes thirty seconds" | One answer instead of seven tabs and a Slack thread. |
| 10 | 1:25 - 1:35 | B4 Battlecards | `/battlecards.html` | Cmd 4. Click Splunk card. Full-screen detail. | Click Splunk. | "no SE escalation" | Battlecards live in a stale PDF; SE-only TCO modeling. |
| 11 | 1:35 - 1:45 | B4 Battlecards | `#splunk` | Click chip "TCO at 200 GB/day". 10-dim table. | $112k vs $443k. | "ten dimensions" | Splunk TCO costs an SE 1 to 2 hours and ships days late. |
| 12 | 1:45 - 1:55 | B4 Battlecards | same | Underline savings line. Scroll to "Where Splunk genuinely wins". | 74.66 percent. Honest gaps. | "seventy four percent savings" | Customer cost questions answered in 8 seconds, cited. |
| 13 | 1:55 - 2:05 | B5 Demo Data | `/demo-data.html` | Cmd 5. 5 scenario cards visible. Sweep the row. | 5 scenarios. 10 paired dashboards. | "fifteen seconds" | Tailored Kibana dashboard normally takes half a day. |
| 14 | 2:05 - 2:15 | B5 Demo Data | Kibana FE | Click "Open [FE]" on Black Friday. Scroll errors, p99, KPIs. | FE flavor. | "FE view" | Generic dashboard ships; customer leaves wanting more. |
| 15 | 2:15 - 2:25 | B5 Demo Data | Kibana Customer | Cmd 5 back. Switcher to Customer. Paired dashboard. | Same data. Two audiences. | "flip the switcher" | Two reframed dashboards from one dataset, instantly. |
| 16 | 2:25 - 2:34 | B6 Workflows | `/workflow-demo.html` | Cmd 6. Both rules green. Click "Fire demo transcript". | 2 workflows. Doc indexed. | "fire the transcript" | Live note-taking pulls the FE off the customer signal. |
| 17 | 2:34 - 2:42 | B6 Workflows | terminal | Tail scrolls 6 writes: Opp MEDDPICC, ContentNote, Link, Competitor, Deal Health, Slack. | Workflow 1: 6 SFDC writes. | "Salesforce writes scroll" | 30 to 60 minutes of SFDC hygiene per meeting, automated. |
| 18 | 2:42 - 2:50 | B6 Workflows | terminal | `[Auto]` wave lands: Workflow 2 orphan tasks. | Workflow 2: orphan tasks. | "Friday-night updates, gone" | Forecast drift from skipped Salesforce updates. |
| 19 | 2:50 - 3:00 | B7 Outro | `/` | Cmd 1. Lower-third: github URL. Logo dissolve. | Cmd K. 5 languages. MIT License. | "six hours per FE per week" | The aggregate. MIT License, every FE benefits day one. |

19 shots. Sum: 8 + 27 + 20 + 30 + 30 + 30 + 25 + 10 = 180 s exact.

---

## Recording tips

- Click on the beat. The autopilot is the only place hands stay still; everywhere else, cadence sells the take.
- Park the cursor off-screen at 0:08 and leave it there until 0:35. The captions are the narration.
- Read the EN voiceover from the script at every beat boundary (0:08, 0:35, 0:55, 1:25, 1:55, 2:25, 2:50). Memory loses against tape.

---

## Common pitfalls and fallbacks

1. **Autopilot times out at step 2.** Anthropic 429 or cold cache. Autopilot catches it and continues; presenter stays muted. If step 3 panel is blank for 3+ s, cut and restart from B0.
2. **Field Assistant chip in B3 returns empty.** localStorage stuck. DevTools, `localStorage.clear()`, refresh, click again. Hard fallback: backup meeting tab `meeting.html?id=atlantico-mtg-prev-001`.
3. **Workflow orphan wave does not fire inside B6.** Kibana .es-query rules poll every 60 s. Pre-prime by firing the demo transcript 90 s before recording so the `[Auto]` wave lands inside the window.
4. **Kibana 401s in B5.** `KIBANA_API_KEY` expired. Re-export and restart uvicorn. Hard fallback: skip the Kibana scroll and stay on `/demo-data.html`.
5. **Battlecard chat returns the wrong card content.** Cross-talk in the embedded thread. Refresh `/battlecards.html`, click Splunk, click chip again. Hard fallback: switch to Datadog or Dynatrace; structure is identical.
6. **Autopilot iframe fails to load the brief at step 3.** ad-hoc id race. Autopilot retries once. If still blank, cut and restart from B0; the autopilot is the open and must look clean.
7. **Browser dev console open during the take.** Cmd Option I left on from debugging. Cut. Re-open browser fresh, restart from beat boundary.
8. **Microphone level too low or peaking.** macOS input gain reset. System Settings, Sound, Input, set to 75 percent. Test 10 s.

If a shot here disagrees with `docs/demo-script.md`, the script wins for words and the storyboard wins for clicks.
