# FE Copilot - Demo Storyboard (5 minutes, single take)

> Presenter: Rodrigo Careaga, Senior Customer Architect at Elastic
> Target runtime: 5:00 (300 seconds), 28 shots
> Capture: Loom or QuickTime, 1080p, 110 percent browser zoom, dark theme, captions on.
> Beat alignment: B0 0:00 Title, B1 0:10 Autopilot, B2 0:50 FE Brain, B3 1:30 Pre-meeting brief, B4 2:00 Auro, B5 2:40 Battlecards, B6 3:15 Demo Data, B7 4:00 Workflows, B8 4:45 Outro.

All shot URLs assume the backend is serving the frontend on `http://127.0.0.1:8123`. Voiceover cues are keywords; full script lives in `docs/demo-script.md`.

---

## Pre-flight tab order

Pin these tabs, in this exact order, in a clean browser window before recording starts. The Tab order matches the demo sequence so `Cmd <number>` is the keystroke chain. Pre-load each tab so the page is warm and the first paint is instant.

1. `http://127.0.0.1:8123/` - Homepage with autopilot CTA, industry templates, Quick Research (B0, B1, B3, B8).
2. `http://127.0.0.1:8123/fe-brain.html` - FE Brain RAG (B2).
3. `http://127.0.0.1:8123/meeting.html?id=santander-mtg-prev-001` - Backup meeting view in case the autopilot brief id is unstable. The autopilot will redirect to its own freshly minted id; this tab is only a fallback.
4. `http://127.0.0.1:8123/agent-builder.html` - Agent Builder chat for any ad-libbed Q (mostly a fallback during B4).
5. `http://127.0.0.1:8123/battlecards.html` - Battlecards grid (B5).
6. `http://127.0.0.1:8123/demo-data.html` - Demo Data scenarios (B6).
7. `http://127.0.0.1:8123/workflow-demo.html` - Workflow control panel (B7).
8. `https://fe-summit-hackathon-ed0e8e.kb.us-west-1.aws.found.io/app/dashboards` - Kibana dashboards landing (B6 dashboards open into Kibana).
9. Terminal pane (not a browser tab), pre-positioned right one-third of the screen, working directory `/Users/rodrigocareaga/Downloads/FE-Elastic`, ready to `tail -f runtime/salesforce.log` for B7.

---

## Shot-by-shot table

### B0 Title slate (0:00 - 0:10)

| # | Time | Beat | URL | Click sequence | Overlay caption | VO cue | B-roll |
|---|---|---|---|---|---|---|---|
| 01 | 0:00 - 0:10 | B0 Title | n/a (Keynote slate) | Hold the slate. Do not click. Webcam thumb optional bottom-right. | FE Copilot. 11 personas, 5 scenarios, 2 workflows, sub-15s time to value. | "eleven personas, five scenarios, two workflows" | Slate fades into the homepage at 0:10 |

### B1 Autopilot (0:10 - 0:50)

| # | Time | Beat | URL | Click sequence | Overlay caption | VO cue | B-roll |
|---|---|---|---|---|---|---|---|
| 02 | 0:10 - 0:14 | B1 Autopilot | http://127.0.0.1:8123/ | Slate cut. Page is warm. Cursor moves to the hero gradient button labeled "Show me the magic". | The button clicks itself. | (silent, autopilot caption: "Quick Research, Banco Santander") | Soft confetti at click |
| 03 | 0:14 - 0:21 | B1 Autopilot | http://127.0.0.1:8123/ | Click "Show me the magic". Overlay mounts. Caption bar top, 7-step dock right, iframe panel center. Step 2 fires `POST /agents/pre-meeting/ad-hoc` for Banco Santander. | Live SEC EDGAR plus news plus Wikipedia. Haiku 4.5. | (silent, caption "Brief writes itself") | Iframe loading shimmer |
| 04 | 0:21 - 0:28 | B1 Autopilot | http://127.0.0.1:8123/meeting.html?id=<adhoc>&adhoc=1 | Iframe swaps to the rendered brief. Step 3 caption appears in the bar: "Brief renders. Every claim cites a source." Cursor stays on the side, do not move. | Brief rendered. Citations inline. | (silent) | Brief headline pulse |
| 05 | 0:28 - 0:34 | B1 Autopilot | http://127.0.0.1:8123/agent-builder.html (in iframe) | Step 4 fires real `POST /agent-builder/converse` for the chained POC plan + TCO prompt. Tool-call cards render inside the iframe. | Auro chains POC plan and TCO. Two specialists, one answer. | (silent) | Tool-call cards collapse animation |
| 06 | 0:34 - 0:42 | B1 Autopilot | http://127.0.0.1:8123/workflow-demo.html (in iframe) | Step 6 fires `POST /workflows/demo-fire`. The "Recent webhook fires" stream pulses with a new entry. | Workflow rule fires. SFDC plus Slack. | (silent) | New row pulse |
| 07 | 0:42 - 0:50 | B1 Autopilot | overlay completion card | Step 7 confetti. Completion card: "Demo complete. Cost ~$0.07. Time 38s." Cursor stays parked. | Demo complete. ~$0.07 per run. | (silent, presenter unmutes for B2) | Confetti burst, then dismiss |

### B2 FE Brain (0:50 - 1:30)

| # | Time | Beat | URL | Click sequence | Overlay caption | VO cue | B-roll |
|---|---|---|---|---|---|---|---|
| 08 | 0:50 - 0:56 | B2 FE Brain | http://127.0.0.1:8123/fe-brain.html | Cmd 2 to FE Brain tab. Page is warm. Suggested chips visible under composer. Click chip "How do I tune ILM for hot+warm+frozen 200 GB/day?". | ELSER hybrid retrieval. Elastic public docs. | "ELSER hybrid retrieval, four hundred seven chunks" | Composer fills with chip text |
| 09 | 0:56 - 1:08 | B2 FE Brain | http://127.0.0.1:8123/fe-brain.html | Wait for the streamed answer. Six to nine seconds on hybrid plus rerank. Inline citations [1] [2] [3] appear as the text lands. | 407 chunks. 103 URLs. Hybrid plus rerank. | "query expansion, BM25, RRF, rerank" | Light zoom on the inline citation chips |
| 10 | 1:08 - 1:18 | B2 FE Brain | http://127.0.0.1:8123/fe-brain.html | Hover [1] to surface URL preview. Cursor pans to right-side citations panel; pause on the elastic.co/guide ILM lifecycle URL. | Mei, ex-enablement docs lead. | "Mei, five out of five on the audit" | Right-side panel pulse on render |
| 11 | 1:18 - 1:30 | B2 FE Brain | http://127.0.0.1:8123/fe-brain.html | Scroll the answer once to show the depth (cold to frozen tier transitions, snapshot policy reference). No click. | 5 of 5: relevance, grounding, coverage, tone. | "five out of five" | Hold on the answer for two seconds before the cut |

### B3 Pre-meeting brief grounded (1:30 - 2:00)

| # | Time | Beat | URL | Click sequence | Overlay caption | VO cue | B-roll |
|---|---|---|---|---|---|---|---|
| 12 | 1:30 - 1:36 | B3 Brief | http://127.0.0.1:8123/ | Cmd 1 back to homepage. Three industry template tiles visible. Click the Banking tile. Quick Research form pre-populates with banking discovery preset. | 3 industry templates. Banking selected. | "three templates, click banking" | Tile lift animation |
| 13 | 1:36 - 1:46 | B3 Brief | http://127.0.0.1:8123/ | Type "Banco Santander" into Company. Click Submit on Quick Research. Page begins streaming. | Banco Santander. Live SEC EDGAR. | "type Banco Santander, hit Quick Research" | Composer focus ring, then submit pulse |
| 14 | 1:46 - 1:54 | B3 Brief | http://127.0.0.1:8123/meeting.html?id=<id>&adhoc=1 | Page redirects to the meeting view. Brief headline visible at top. Scroll down to "Sources used". | Sources used. Real URLs. | "every source is real" | Smooth scroll to Sources panel |
| 15 | 1:54 - 2:00 | B3 Brief | sec.gov filing tab | Click one SEC EDGAR link. New tab opens to the live filing. Hold one second. Close the tab. Return to meeting page. | The citation is real. | "the filing opens, the citation is real" | Brief flash of EDGAR page |

### B4 Auro orchestrator (2:00 - 2:40)

| # | Time | Beat | URL | Click sequence | Overlay caption | VO cue | B-roll |
|---|---|---|---|---|---|---|---|
| 16 | 2:00 - 2:08 | B4 Auro | http://127.0.0.1:8123/meeting.html?id=<id>&adhoc=1 | Stay on meeting page. Scroll to Field Assistant mini panel inside the Brief tab. Click suggested chip "POV plan + TCO". | Field Assistant. Auro orchestrator. | "one question, click the chip" | Chip click ripple |
| 17 | 2:08 - 2:20 | B4 Auro | http://127.0.0.1:8123/meeting.html?id=<id>&adhoc=1 | Composer fills. Response begins streaming. Two collapsible tool-call cards render inline: `fec_poc_plan` and `fec_cost_calc`, side by side. | Parallel: fec_poc_plan + fec_cost_calc. | "Auro picks two specialists in parallel" | Soft arrow overlay between the cards |
| 18 | 2:20 - 2:32 | B4 Auro | http://127.0.0.1:8123/meeting.html?id=<id>&adhoc=1 | Wait for synthesis block to render below the two tool-call cards. Cursor underlines the synthesis heading. | One question. Two specialists. One coherent answer. | "Auro is the conductor" | Underline pulse on the synthesis heading |
| 19 | 2:32 - 2:40 | B4 Auro | http://127.0.0.1:8123/meeting.html?id=<id>&adhoc=1 | Hold on the synthesis. Do not click. Let the take breathe before the cut. | MCP. Master agent. Kibana 9.3.4. | "Auro is the conductor" (second time) | Hold steady, fade cut |

### B5 Battlecards + Sloane (2:40 - 3:15)

| # | Time | Beat | URL | Click sequence | Overlay caption | VO cue | B-roll |
|---|---|---|---|---|---|---|---|
| 20 | 2:40 - 2:48 | B5 Battlecards | http://127.0.0.1:8123/battlecards.html | Cmd 5 to Battlecards. Grid of 15 cards visible. Cursor sweeps once, then click the Splunk card. | 15 cards. Click Splunk. | "I click Splunk" | Grid-to-detail transition |
| 21 | 2:48 - 2:58 | B5 Battlecards | http://127.0.0.1:8123/battlecards.html#splunk | Page transitions to full-screen detail. Card content on the left two-thirds; embedded chat on the right third. Click suggested chip "TCO at 200 GB/day". | Full-screen detail. Embedded chat right. | "ask Sloane for the TCO" | Detail view fade-in |
| 22 | 2:58 - 3:08 | B5 Battlecards | http://127.0.0.1:8123/battlecards.html#splunk | Wait for Sloane response. 10 dimensions table renders. Cursor underlines $112k vs $443k and the 74.66 percent line. | $112k vs $443k. 74.66 percent savings. | "ten dimensions, seventy four point six six percent" | Soft pulse on the savings number |
| 23 | 3:08 - 3:15 | B5 Battlecards | http://127.0.0.1:8123/battlecards.html#splunk | Scroll embedded chat to the "Where Splunk genuinely wins" section. Hold for a beat. | Honest gaps named. | "comparative intelligence with no spin" | Hold on the honest-gaps subheading |

### B6 Demo Data + paired dashboards (3:15 - 4:00)

| # | Time | Beat | URL | Click sequence | Overlay caption | VO cue | B-roll |
|---|---|---|---|---|---|---|---|
| 24 | 3:15 - 3:24 | B6 Demo Data | http://127.0.0.1:8123/demo-data.html | Cmd 6 to Demo Data. 5 scenario cards visible: Black Friday, Bank fraud, Public sector breach, SaaS churn, Logistics SLA. Status pill "seeded" on each. Cursor sweeps the row. | 5 story driven scenarios. Each seeded. | "five scenarios" | Row sweep |
| 25 | 3:24 - 3:38 | B6 Demo Data | https://fe-summit-hackathon-ed0e8e.kb.us-west-1.aws.found.io/app/dashboards (Kibana FE) | On the Black Friday card, click "Open [FE] dashboard". Browser switches to Kibana. Scroll through panels: errors-by-service Lens, p99 latency line, KPI cards, top failing endpoints table. | FE flavor. Errors by service, p99, SLO. | "errors by service, p99 latency, KPI cards" | Slow scroll, hold one second per panel |
| 26 | 3:38 - 3:50 | B6 Demo Data | https://fe-summit-hackathon-ed0e8e.kb.us-west-1.aws.found.io/app/dashboards (Kibana Customer) | Cmd 6 back to Demo Data. Click the dashboard switcher button on the Black Friday card to flip to the Customer view. Browser opens the paired Customer dashboard in Kibana. Scroll. | Customer flavor. Same data. Two audiences. | "the customer sees SLO burn and revenue at risk" | Slow scroll, then cut |
| 27 | 3:50 - 4:00 | B6 Demo Data | http://127.0.0.1:8123/demo-data.html | Cmd 6 back to Demo Data page. Hover any other scenario card briefly to imply "five of these exist". | 10 paired Kibana dashboards. | "ten paired dashboards, one click flips the lens" | Hover lift on a second card |

### B7 Two workflows (4:00 - 4:45)

| # | Time | Beat | URL | Click sequence | Overlay caption | VO cue | B-roll |
|---|---|---|---|---|---|---|---|
| 28 | 4:00 - 4:08 | B7 Workflows | http://127.0.0.1:8123/workflow-demo.html | Cmd 7 to Workflow demo. Status panel at top: both rules registered (transcript inbox + orphan action items), both pills green, connector status webhook reachable. | 2 workflows registered. Both green. | "two workflows close the loop" | Pulse on both green pills |
| 29 | 4:08 - 4:18 | B7 Workflows | http://127.0.0.1:8123/workflow-demo.html | Click "Fire demo transcript". Toast confirms doc indexed into fec-transcript-inbox. Wait two seconds. New row appears in "Recent webhook fires". | Doc indexed. Rule fires. Webhook hits backend. | "the first rule fires, the agent runs" | New row pulse |
| 30 | 4:18 - 4:32 | B7 Workflows | terminal (right one-third) | Switch focus to the pre-positioned terminal. Run `tail -f runtime/salesforce.log`. Six writes scroll past from Workflow 1: Opportunity MEDDPICC, ContentNote, ContentDocumentLink, Competitor, Deal Health, Slack post. | Workflow 1: 6 SFDC writes. | "six writes, all logged" | Cursor blinks on the model field |
| 31 | 4:32 - 4:45 | B7 Workflows | terminal | Continue tailing. Within 60 to 90 seconds the second wave appears prefixed `[Auto]`: Salesforce Tasks created by Workflow 2 for orphan high-impact action items. Cursor underlines one task subject. | Workflow 2: orphan tasks auto-created. | "agents trigger workflows, workflows trigger agents" | Underline on `[Auto]` prefix |

### B8 Outro (4:45 - 5:00)

| # | Time | Beat | URL | Click sequence | Overlay caption | VO cue | B-roll |
|---|---|---|---|---|---|---|---|
| 32 | 4:45 - 5:00 | B8 Outro | http://127.0.0.1:8123/ | Cmd 1 back to homepage. Webcam returns to fuller frame. Five rapid-fire chips pop along the bottom strip in order, each on screen 1.5 to 2 seconds: Cmd+K, 5 languages, mobile, a11y, Apache 2.0. Final card overlays bottom-third with the GitHub URL and the stack lockup. | github.com/rodrigo-elastic/FE-Elastic. Built with Elastic Cloud 9.3.4 and Anthropic Claude. | "Cmd K, five languages, mobile, a11y, Apache two point zero, thank you" | Final logo dissolve to black, URL holds two seconds |

Note on shot count: 32 numbered shots (with shot 01 the slate) across 9 beats. Shot 01 is the static slate and shots 02 through 07 cover the autopilot beat at six discrete narrative moments inside the autonomous run.

---

## Recording tips

- **Click slowly.** Each click should land on the beat. A scripted click cadence sells the demo as a real product walkthrough; a fast click cadence sells it as a screen recording.
- **Wait two seconds after each action.** Captions catch up. Streaming text catches up. Your voiceover catches up. The audience's eye catches up. Do not rush.
- **Do not move the mouse during the autopilot.** The captions are the narration. A moving cursor pulls focus. Park the mouse on the side of the screen at 0:14 and leave it there until 0:50.
- **Keep your hands off the keyboard during streaming responses.** Every keystroke rings on the mic. Every accidental Cmd-Tab cuts the take.
- **Read the EN voiceover from the script, not from memory.** A clean read at 0:50, 1:30, 2:00, 2:40, 3:15, and 4:00 is worth ten retries from memory.
- **Land the headline lines twice.** "Auro is the conductor" in B4. "Agents trigger workflows, workflows trigger agents" in B7. Two reps each, with a half-second pause.
- **Single take or stitched, never a hybrid.** If you cut, restart from a beat boundary. Do not stitch mid-beat.
- **Do not record after midnight.** Tired voiceover is the single biggest reason demos miss. Sleep, then record.

---

## Common pitfalls + fallbacks

### P1. Autopilot times out at step 2 (Quick Research)

- Cause: Anthropic 429 or cold cache or the ad-hoc endpoint hangs past 18 seconds.
- Recovery: The autopilot itself catches the timeout, marks step 2 failed, and continues. The presenter does nothing. Voiceover stays muted; the captions handle the apology.
- Hard fallback: Cut after the autopilot. Restart the take from B0. Do not try to ad-lib over a failed autopilot.

### P2. Autopilot iframe fails to load the brief at step 3

- Cause: ad-hoc meeting id race condition (brief not yet on disk when the iframe requests it).
- Recovery: The autopilot retries once internally. If it still fails, step 3 caption shows "panel unavailable, continuing".
- Hard fallback: After the take, if step 3 was visibly blank for more than 3 seconds, cut and re-record from B0. The autopilot is the open of the demo and must look clean.

### P3. Field Assistant chip in B4 returns an empty answer

- Cause: localStorage carrying a broken thread (`fec.ab.brief.v2.*`), or the streamed response lost a chunk.
- Recovery: In the console run `localStorage.clear()`, refresh the meeting page, click the chip again. Voiceover ad-lib in EN: "let me restart that thread". Resume.
- Hard fallback: Cmd 4 to `/agent-builder.html` and ask the same question against the master agent. Cosmetically different, same content.

### P4. Workflow webhook does not fire within the take window in B7 (orphan wave)

- Cause: Kibana .es-query rules poll every 60s; the orphan wave can take up to 90 seconds to land. Take started inside the dead zone.
- Recovery: Pre-prime the workflow during pre-flight. Click "Fire demo transcript" 90 seconds before the recording starts so the orphan wave lands inside the recording window.
- Hard fallback: If the orphan wave does not land, voiceover for B7 shifts to "Workflow 2 fires within ninety seconds; here is the prior run from a minute ago," and the terminal shows the pre-primed entries.

### P5. Kibana 401s on the dashboard tab in B6

- Cause: KIBANA_API_KEY expired or session cookie cleared.
- Recovery: Re-export `KIBANA_API_KEY` in the uvicorn shell, restart the backend, refresh the Kibana tab. Sign in if prompted.
- Hard fallback: Skip the Kibana scroll. Show only the demo-data page with the seeded counts. Voiceover line: "five scenarios, ten paired dashboards, all live in Kibana, here is the seed page".

### P6. Vega panel inside a Kibana dashboard fails to render in B6

- Cause: Kibana 9.3 sometimes rejects URL-based Vega specs.
- Recovery: Open the [Customer] variant of the dashboard which uses inline `data.values` only. Both URLs are returned by the seed call (`dashboard_url_customer`).
- Hard fallback: Skip the failing panel. Scroll past it without lingering.

### P7. Browser dev console is open during the take

- Cause: Cmd Option I left on from debugging.
- Recovery: Cut. The dev console screams "this is a screen recording, not a product". Re-open the browser fresh, close DevTools, restart from the beat boundary.

### P8. Integration smoke flagged a fail before recording

- Cause: One of the smoke checks (Kibana, Agent Builder, workflow rules, Anthropic key) failed the GO check.
- Recovery: Do not record. Fix the failing check. Re-run `PYTHONPATH=backend python -m scripts.integration_smoke`. Only proceed when GO is unanimous.
- Hard fallback: There is no fallback. A failed smoke means the demo will fail mid-take. Fix it.

### P9. Battlecard chat in B5 returns the wrong card content (cross-talk)

- Cause: Embedded chat thread carrying state from a prior card.
- Recovery: Refresh `/battlecards.html`, click the Splunk card again, click the chip again. The thread resets per card.
- Hard fallback: Switch to a different card (Datadog or Dynatrace) for the take. Sloane's structure is identical across cards; only the dollar numbers change.

### P10. Cmd+K command palette does not open in pre-flight

- Cause: `command-palette.js` not loaded (cache miss) or focus trapped in an embedded chat textarea.
- Recovery: Hard refresh (Cmd Shift R). Click an empty area of the page. Try Cmd+K again.
- Hard fallback: Do not show Cmd+K in the take. The outro chips name it as a feature; the chip alone is enough proof.

### P11. SEC EDGAR link in B3 returns a 404 or a redirect

- Cause: SEC URL formatting changed for the filing type, or the brief cited a stale URL.
- Recovery: Pre-flight verifies one EDGAR link works for Banco Santander. Click that one specifically; do not click the first link in the list, click the verified one.
- Hard fallback: Hover the link without clicking; voiceover line shifts to "every URL is real and verifiable, here is the EDGAR filing".

### P12. Demo Data scenario cards show "not seeded"

- Cause: Re-seed step in pre-flight skipped or partial.
- Recovery: Click "Re-seed" on each card. Wait 30 to 60 seconds for indices to populate. Refresh the page.
- Hard fallback: Show only the scenarios that did seed. The script says "five scenarios" but if four are seeded, voiceover ad-lib: "four scenarios live, the fifth is rebuilding".

### P13. Autopilot hero button does not appear on the homepage

- Cause: `autopilot.js` not loaded, or the IIFE failed to find the hero section.
- Recovery: Hard refresh. Check console for `window.FEAutopilot`. Restart uvicorn if the asset path is wrong.
- Hard fallback: There is no good fallback. The autopilot is the open. Fix it before recording.

### P14. Microphone level too low or peaking

- Cause: macOS input gain reset, or a different input device picked up.
- Recovery: System Settings -> Sound -> Input. Confirm the right mic is selected. Set input level to 75 percent. Test record 10 seconds. Adjust.
- Hard fallback: Re-record the audio track separately and re-time it in post against the silent screen capture.

---

End of storyboard. Single source of truth for the take. If a shot here disagrees with `docs/demo-script.md`, the script wins for words and the storyboard wins for clicks.
