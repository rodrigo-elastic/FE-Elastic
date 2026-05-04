# FE Copilot - Demo Storyboard (5 minutes, single take)

> Presenter: Rodrigo Careaga, Senior Customer Architect at Elastic
> Target runtime: 5:00 (300 seconds), 31 shots
> Capture: Loom or QuickTime, 1080p, 110% browser zoom, dark theme, captions on.
> Beat alignment: 0:00 Hook, 0:25 Pre-meeting, 1:25 Live, 2:15 Post + SF, 3:15 Tools rail, 4:00 Agent Builder, 4:30 Workflow, 4:50 Outro.

All shot URLs assume the backend is serving the frontend on `http://127.0.0.1:8123`. Voiceover cues are keywords; full script lives in `docs/demo-script.md`.

---

## Hook (0:00 - 0:25)

| # | Time | Beat | URL | Action sequence | Overlay caption | VO cue | B-roll | Pre-conditions |
|---|---|---|---|---|---|---|---|---|
| 01 | 0:00 - 0:08 | Hook | n/a (presenter cam) | Open on presenter. Webcam picture-in-picture lower-right. Slate card: "FE Copilot - Three agents, seven tools, one Field Engineer." | FE Copilot - Hackathon FY27 SKO FE Summit | "Three agents. Seven tools. One Field Engineer." | Hold on title slate, fade to dashboard | Webcam on, mic test green, slate PNG ready in Keynote |
| 02 | 0:08 - 0:18 | Hook | http://127.0.0.1:8123/ | Cursor sweeps the hero stat tiles (Accounts, Upcoming, Past meetings, Briefs generated). Hover the gradient title once. | Built on Claude. Lives in Elastic. | "research, live whisper, post-meeting sync" | Slow zoom on hero stats row | Backend up; dashboard tab pinned; localStorage cleared so model pill says Haiku 4.5 |
| 03 | 0:18 - 0:25 | Hook | http://127.0.0.1:8123/ | Scroll down once to reveal Calendar inbox with 4 mock invites. Hover the Revolut row to show "consultants present" pill. | Smart resolver picks the customer, not the consultant | "calendar, smart resolver, consultants filtered" | Highlight the orange consultants-present pill | Calendar mock seeded with Accenture/KPMG mixed invites |

## Pre-meeting (0:25 - 1:25)

| # | Time | Beat | URL | Action sequence | Overlay caption | VO cue | B-roll | Pre-conditions |
|---|---|---|---|---|---|---|---|---|
| 04 | 0:25 - 0:32 | Pre-meeting | http://127.0.0.1:8123/ | In Calendar inbox, click the Revolut row "Run Pre-Meeting" CTA. Page jumps to meeting view. | One click. Brief incoming. | "click, run pre-meeting" | Mouse-click sound effect in post | Revolut meeting record exists; agent runs in under 25s with Haiku |
| 05 | 0:32 - 0:50 | Pre-meeting | http://127.0.0.1:8123/meeting.html?id=mtg-revolut-001 | Watch the brief render section by section: Headline, Why now, Recent signals, Pain points, Discovery questions, Talking points vs Datadog, Risks. Cursor pauses on Recent signals to show the verifiable URL chips. | Live SEC EDGAR + news, every claim sourced | "headline, signals, pain, MEDDPICC, sources" | Highlight a Reuters source chip with a quick zoom | Pre-meeting cache primed for mtg-revolut-001 (run once before recording so stream returns instantly) |
| 06 | 0:50 - 0:58 | Pre-meeting | http://127.0.0.1:8123/meeting.html?id=mtg-revolut-001 | Scroll down to the Customer Journey strip at the top of the page. Highlight the green checkmarks on Discovery and Tech Eval. | Customer journey, 4 stages | "deal stage, discovery to closed-won" | Brief glow on the active stage badge | Journey header renders on first load (no extra click) |
| 07 | 0:58 - 1:08 | Pre-meeting | http://127.0.0.1:8123/meeting.html?id=mtg-revolut-001 | Scroll to the Field Assistant mini-chat under the brief. Click the suggested chip "Top 5 questions to ask". | Field Assistant, grounded in the brief | "suggested prompts, no typing, grounded answers" | Highlight the four chips left-to-right | Agent-Builder mini mounted (`window.AgentBuilderMini` loaded); localStorage `fec.ab.brief.v2.*` cleared |
| 08 | 1:08 - 1:18 | Pre-meeting | http://127.0.0.1:8123/meeting.html?id=mtg-revolut-001 | Wait for the streamed answer to land. Cursor underlines one MEDDPICC anchor in the response. | MEDDPICC, anchored, every answer | "anchored to MEDDPICC, ready to walk in" | Slight zoom into the streamed text | Field Assistant returns inside 8s on Haiku 4.5 |
| 09 | 1:18 - 1:25 | Pre-meeting | http://127.0.0.1:8123/meeting.html?id=mtg-revolut-001 | Click the "Download" ghost button to surface the brief PDF in a new tab, then close it. | Brief, PDF, ready for the call | "downloadable PDF, mobile-ready" | Quick alt-tab to the PDF tab | WeasyPrint deps installed (or HTML fallback acceptable); pop-up blocker off |

## Live (1:25 - 2:15)

| # | Time | Beat | URL | Action sequence | Overlay caption | VO cue | B-roll | Pre-conditions |
|---|---|---|---|---|---|---|---|---|
| 10 | 1:25 - 1:32 | Live | http://127.0.0.1:8123/meeting.html?id=mtg-revolut-001 | Click the "Live Companion" tab. Page fades to the live panel. | Live Companion, Haiku 4.5 per turn | "live companion, sub-second" | Tab transition micro-animation | Transcript fixture present for Revolut meeting |
| 11 | 1:32 - 1:42 | Live | http://127.0.0.1:8123/meeting.html?id=mtg-revolut-001 | Click "Replay transcript". Watch the first 3-4 turns appear with colored alert chips for Datadog and Grafana mentions. | Competitor mentions, MEDDPICC signals, inline | "Datadog, Grafana, MEDDPICC, every turn" | Slow zoom on the first red competitor chip | Live agent runs against Haiku 4.5 (default in selector); replay speed factor at default |
| 12 | 1:42 - 1:55 | Live | http://127.0.0.1:8123/meeting.html?id=mtg-revolut-001 | Highlight the suggested "whisper line" under one alert. Cursor pauses on the source-quote link inside the alert. | Whisper lines, traceable to the transcript | "whisper, suggested line, traceable" | Pulse highlight the whisper text | Replay still running; do not click again |
| 13 | 1:55 - 2:05 | Live | http://127.0.0.1:8123/meeting.html?id=mtg-revolut-001 | Scroll down to the Field Assistant Live mini-chat. Click the "What should I say next?" chip. | Field Assistant, situational awareness | "what should I say next, on the fly" | Quick zoom on the chip click | Mini-chat preamble includes last 8 transcript turns; clear localStorage `fec.ab.live.v2.*` |
| 14 | 2:05 - 2:15 | Live | http://127.0.0.1:8123/meeting.html?id=mtg-revolut-001 | Watch the answer stream in (a 2-3 sentence next-question suggestion anchored to MEDDPICC). | Anchored to MEDDPICC, in real time | "deal advances, no fumbling" | Soft underline the MEDDPICC keyword | Streaming endpoint reachable; no rate-limit errors |

## Post + SF (2:15 - 3:15)

| # | Time | Beat | URL | Action sequence | Overlay caption | VO cue | B-roll | Pre-conditions |
|---|---|---|---|---|---|---|---|---|
| 15 | 2:15 - 2:22 | Post + SF | http://127.0.0.1:8123/meeting.html?id=mtg-revolut-001 | Click the "Post-Meeting" tab. Click "Run Post-Meeting Agent". | Post-Meeting Action Engine | "meeting ends, agent fires" | Cursor click sound effect | Post-meeting cache primed once before recording so render is fast |
| 16 | 2:22 - 2:38 | Post + SF | http://127.0.0.1:8123/meeting.html?id=mtg-revolut-001 | Wait for render: Summary, Action items grid, MEDDPICC 2-column grid, Competitor mentions, Follow-up email block. Cursor sweeps each section. | Summary, actions, MEDDPICC, email - one click | "summary, action items, MEDDPICC, email draft" | Quick zooms on each block | Post-meeting agent returns in under 15s on Sonnet |
| 17 | 2:38 - 2:48 | Post + SF | http://127.0.0.1:8123/meeting.html?id=mtg-revolut-001 | Hover an action item to surface the verbatim source quote. Click "Open quote" to scroll the Live tab to the matching transcript turn (highlight-flash). | Every claim, traceable to a quote | "verbatim, auditable, no hallucination" | Highlight-flash glow captured cleanly | `openTranscriptAt` handler wired (already in meeting.js); Live tab pre-rendered |
| 18 | 2:48 - 3:00 | Post + SF | terminal (split view, right half) | Switch to a pre-arranged terminal pane. Run `tail -n 20 runtime/salesforce.log | jq .` to show six writes (Opportunity MEDDPICC, ContentNote, ContentDocumentLink, Competitor, Deal_Health, Slack). | Salesforce sync, six writes, all logged | "Salesforce, six writes, append-only audit" | Zoom in on the `_action` discriminator field | Terminal pre-positioned; `runtime/salesforce.log` exists with fresh entries from shot 16 |
| 19 | 3:00 - 3:08 | Post + SF | terminal | Run `tail -n 5 runtime/audit.jsonl | jq '{model, input_tokens, output_tokens}'`. | Audit log, tokens per call | "audit, tokens, mock vs live" | Terminal cursor blinks on the model field | `runtime/audit.jsonl` has post-meeting entries |
| 20 | 3:08 - 3:15 | Post + SF | http://127.0.0.1:8123/meeting.html?id=mtg-revolut-001 | Back to browser. Scroll to the follow-up email block. Click the "Copy email" affordance. | Ready to paste into Gmail | "follow-up email, ready to send" | Brief zoom on the email subject line | Clipboard permission granted to the browser |

## Tools rail (3:15 - 4:00)

| # | Time | Beat | URL | Action sequence | Overlay caption | VO cue | B-roll | Pre-conditions |
|---|---|---|---|---|---|---|---|---|
| 21 | 3:15 - 3:22 | Tools rail | http://127.0.0.1:8123/tools.html | Click "Tools" in the persistent left rail. Page loads with seven panels collapsed. Hover the rail to show it stays pinned. | Persistent rail, every page | "seven tools, one rail, every page" | Quick pan up the left rail | Rail injected (tools-rail.js loaded); no duplicate sidebar markup |
| 22 | 3:22 - 3:32 | Tools rail | http://127.0.0.1:8123/tools.html#tool-spl | Click panel 02 (SPL to ES|QL). Paste the demo SPL: `index=trades source=app sourcetype=access \| stats count by user \| sort -count \| head 10`. Click "Convert to ES|QL". | Splunk renewals, in seconds | "SPL to ES dot Q L, Diego, ex-Splunk consultant" | Fast typing or pre-filled clipboard paste | SPL block pre-copied to clipboard via Raycast snippet `;splDemo` |
| 23 | 3:32 - 3:42 | Tools rail | http://127.0.0.1:8123/tools.html#tool-spl | Watch the ES|QL response render with migration caveats. Cursor underlines the `STATS BY user` line. | ES|QL output + migration caveats | "translation, caveats, copy-pasteable" | Brief zoom on the caveats block | Claude returns in under 8s on Haiku 4.5 |
| 24 | 3:42 - 3:52 | Tools rail | http://127.0.0.1:8123/tools.html#tool-cost | Click panel 04 (Cost calculator). Inputs are pre-filled at 500 GB/day, 18 months, 20/20/60 hot/warm/frozen, current spend $3M. Click "Calculate TCO". | Elastic vs Splunk vs Datadog, 12-month TCO | "TCO, frozen tier, three-way compare" | Highlight the savings delta number | Pure compute - returns instantly; no Claude call |
| 25 | 3:52 - 4:00 | Tools rail | http://127.0.0.1:8123/tools.html#tool-compliance | Click panel 03 (Compliance). Pre-tick FCA + GDPR + PCI-DSS. Click "Map to Elastic controls". Highlight one regulation row that maps to native Elastic Security controls. | Compliance mapping, native controls | "Priya, ex-PwC, native controls" | Quick zoom on a regulation-to-control mapping row | `comp-industry` field pre-filled with "UK retail bank" |

## Agent Builder (4:00 - 4:30)

| # | Time | Beat | URL | Action sequence | Overlay caption | VO cue | B-roll | Pre-conditions |
|---|---|---|---|---|---|---|---|---|
| 26 | 4:00 - 4:08 | Agent Builder | http://127.0.0.1:8123/agent-builder.html | Click "Agent Builder" in the rail. Page loads with the green "Connected" pill, "agent: fec_field_assistant", "7 MCP tools". | Agent Builder, live in your Kibana | "Agent Builder, MCP, master agent owns the seven" | Slow pan across the three pills | KIBANA_API_KEY set; sync_agent_builder.py run successfully; status pill green |
| 27 | 4:08 - 4:18 | Agent Builder | http://127.0.0.1:8123/agent-builder.html | Click the "Chain: SPL + cost" suggested chip. The composer fills in. Click Send. | Chained tools, one prompt | "chained tools, the agent decides" | Capture the chip click + composer fill | Master agent `fec_field_assistant` declares both tools; converse endpoint returns within 12s |
| 28 | 4:18 - 4:30 | Agent Builder | http://127.0.0.1:8123/agent-builder.html | Watch the response stream: reasoning step, tool call to `fec_spl_to_esql`, tool call to `fec_cost_calc`, final answer. Cursor pauses on each tool-call block. | Two tool calls, one answer | "reasoning, tool call, tool call, answer" | Highlight each tool-call card as it appears | SSE stream working (`/converse-async` reachable); both tools registered |

## Workflow (4:30 - 4:50)

| # | Time | Beat | URL | Action sequence | Overlay caption | VO cue | B-roll | Pre-conditions |
|---|---|---|---|---|---|---|---|---|
| 29 | 4:30 - 4:40 | Workflow | http://127.0.0.1:8123/workflow-demo.html | Click "Workflow" in the rail. Status card shows "Rule active, 1-minute schedule". Click "Trigger now (skip wait)". | Doc lands, workflow fires, agent runs | "doc, workflow, agent, SFDC, Slack" | Highlight the four-step flow card at top | Kibana alerting rule synced (`/workflows/sync` returned ok); webhook reachable |
| 30 | 4:40 - 4:50 | Workflow | http://127.0.0.1:8123/workflow-demo.html | Watch a new entry land in the "Recent webhook fires" list (auto-refresh every 15s, but trigger-now skips). Click the entry to expand and show the post-meeting payload. | End-to-end, no human in the loop | "no human, no copy-paste, no swivel chair" | Pulse highlight the new fire row | `runtime/workflows.log` gets a new entry; webhook returns 200 |

## Outro (4:50 - 5:00)

| # | Time | Beat | URL | Action sequence | Overlay caption | VO cue | B-roll | Pre-conditions |
|---|---|---|---|---|---|---|---|---|
| 31 | 4:50 - 5:00 | Outro | http://127.0.0.1:8123/ | Cut back to the dashboard. Hover hero gradient. Webcam returns to full frame. End slate: "Three agents. Seven tools. Two integrations. Built on Claude. Lives in Elastic." | Three agents. Seven tools. Two integrations. | "Built on Claude. Lives in Elastic. Thank you." | Fade to black, Elastic + Claude logos lockup | End slate PNG ready in Keynote; outro music bed pre-trimmed to 8s |

---

## Pre-flight checklist

Run every item, in order, before hitting record. If any step fails, stop and fix before proceeding - a failure mid-take costs 10 minutes of re-take.

### A. Backend and data

1. `cd /Users/rodrigocareaga/Downloads/FE-Elastic`
2. `source .venv/bin/activate`
3. Verify `.env` has `ANTHROPIC_API_KEY=sk-ant-...` and `KIBANA_API_KEY=...`. If missing, source from 1Password.
4. `rm -rf runtime/briefs runtime/post_meeting runtime/emails runtime/slack.log runtime/salesforce.log` (clean slate, but keep audit log).
5. `PYTHONPATH=backend python -m scripts.generate_synthetic_data` (regenerates Revolut, MELI, Santander records).
6. `PYTHONPATH=backend uvicorn app.main:app --port 8123 --log-level warning` in a dedicated terminal pane. Wait for "Uvicorn running on http://127.0.0.1:8123".
7. `curl -s http://127.0.0.1:8123/api/v1/health | jq .` - expect `{"ok": true, ...}`.
8. `docker compose -f infra/docker-compose.yml up -d` (Elasticsearch on 9202, Kibana on 5603). Wait until `curl -s http://127.0.0.1:9202 | jq .tagline` returns the ES tagline.
9. `PYTHONPATH=backend python -m scripts.sync_agent_builder` - confirm `ok: true` for all seven `fec_*` tools and the master agent.
10. `PYTHONPATH=backend python -m scripts.sync_kibana_workflow` (or use the "Sync workflow" button in the UI once) - confirm rule status `active`.
11. Visit `/api/v1/agent-builder/status` in the browser - confirm `live: true`.

### B. Demo cache priming (do twice for each, the second run hits cache)

12. Open `/meeting.html?id=mtg-revolut-001`, click "Run Pre-Meeting Agent", wait for full render. Repeat once. Then click "Run Post-Meeting Agent", wait for render. Repeat once.
13. On the Live tab, click "Replay transcript" once and let it complete. Then refresh the page so the replay button is fresh for the take.
14. Open `/agent-builder.html`, send the "Chain: SPL + cost" prompt once. Confirm the response renders with two tool-call cards. Click "New thread" to clear.
15. Open `/tools.html`, run the SPL converter, the Cost calculator, and the Compliance mapper once each to warm Claude.
16. Open `/demo-data.html`, seed at least the Black Friday scenario so dashboards exist. (Optional for the 5-min cut but useful as a backup b-roll.)
17. Open `/workflow-demo.html`, click "Sync workflow", then "Fire demo transcript", confirm a new fire arrives in under 90s. Clear the fires list before recording (refresh).

### C. Browser hygiene

18. Use a clean Chrome profile or Arc Space dedicated to the demo. Sign out of any personal accounts visible in the top-right.
19. Set browser zoom to 110% on every demo tab (`Cmd =` twice from default).
20. Hide the bookmarks bar (`Cmd Shift B`).
21. Enable dark theme system-wide (System Settings -> Appearance -> Dark).
22. DevTools closed. No extension popovers visible.
23. Clear localStorage on every page that uses the Field Assistant mini: `localStorage.clear()` in the console on `/meeting.html` and `/agent-builder.html`. Reload.
24. Disable notifications: macOS Focus mode "Do Not Disturb", Slack snoozed for 1 hour, calendar alerts off.
25. Close every other app: no Slack badge, no Mail, no Calendar dock badges.

### D. Recording setup

26. Loom or QuickTime opened, output set to 1080p, 30fps. Mic input verified by recording a 5-second test and playing it back.
27. Webcam framing: head and shoulders, lower-right corner, 280px wide.
28. Captions: enable Loom auto-captions OR pre-write them from the script.
29. Cursor highlighting: turn on Loom's "highlight clicks" or use Cursor Pro app at default settings.
30. Pre-arrange a vertical split: browser on left two-thirds, terminal on right one-third. Terminal at 14pt, white-on-black, font Menlo.
31. Pre-load the terminal with two stacked panes: top pane = `runtime/`, bottom pane ready to run `tail` commands. Pre-type both `tail` commands but do not execute.

### E. Tab pre-loading (see Tab order below for exact order)

32. Open every tab from the Tab order list, top to bottom, then `Cmd 1` back to the dashboard.
33. On every tab, scroll to the top so opening transitions look identical.
34. Verify no error toasts visible on any tab.

### F. Final 60 seconds

35. Webcam light on, ring light angled, no glare on glasses.
36. Take a deep breath. Read the first three lines of the script aloud to warm up.
37. Hit record. Wait 2 seconds before speaking the hook.

---

## Tab order

Pin these, in this exact order, in a clean browser window. The Tab order matches the demo sequence so `Cmd <number>` is the keystroke chain.

1. `http://127.0.0.1:8123/` - Dashboard (Hook + Outro).
2. `http://127.0.0.1:8123/meeting.html?id=mtg-revolut-001` - Revolut meeting view (Pre-meeting + Live + Post).
3. `http://127.0.0.1:8123/meeting.html?id=mtg-meli-001` - Mercado Libre meeting view (backup if Revolut errors).
4. `http://127.0.0.1:8123/meeting.html?id=mtg-santander-001` - Santander meeting view (second backup).
5. `http://127.0.0.1:8123/tools.html` - Tools rail (Tools beat).
6. `http://127.0.0.1:8123/agent-builder.html` - Agent Builder chat (Agent Builder beat).
7. `http://127.0.0.1:8123/workflow-demo.html` - Workflow demo (Workflow beat).
8. `http://127.0.0.1:8123/demo-data.html` - Demo Data (b-roll only, not in main script).
9. `http://127.0.0.1:8123/api/v1/audit` - Audit JSON (b-roll for shot 19 if terminal fails).
10. `http://127.0.0.1:5603/app/dashboards` - Kibana dashboards (b-roll if Vega panels are needed).

Plus one terminal window (not a browser tab) sized to the right third of the screen, working directory `/Users/rodrigocareaga/Downloads/FE-Elastic`.

---

## Common pitfalls + fallbacks

### P1. Pre-Meeting agent stalls past 30 seconds (shot 04-05)

- Cause: Anthropic rate limit or cold cache.
- Recovery: Switch the model picker to `Haiku 4.5 (cheap)` and re-click Run. Voiceover ad-lib: "and on Haiku 4.5 the brief lands in under ten seconds."
- Hard fallback: Cut to tab 3 (MELI meeting) which is pre-cached; resume the script there.

### P2. Field Assistant mini-chat returns an empty answer (shot 07-08, 13-14)

- Cause: localStorage carrying a broken thread, or the streamed response lost a chunk.
- Recovery: In the console run `localStorage.clear()`, refresh, click the same chip again. The script line "let me restart that thread" covers the recovery.
- Hard fallback: Open the full `/agent-builder.html` and ask the same question against the master agent.

### P3. Live transcript replay fires alerts in the wrong order (shot 11-12)

- Cause: Haiku 4.5 returning out-of-order MEDDPICC tags on a parallel turn.
- Recovery: Pause the recording mentally, click "Replay transcript" again. Voiceover: "let me run that one more time so we can see every alert."
- Hard fallback: Skip to shot 13 (Field Assistant chip) and rely on the existing colored chips that already rendered.

### P4. Salesforce log is empty in shot 18

- Cause: Post-meeting agent in shot 16 ran in mock mode, OR the file was just rotated.
- Recovery: Run the post-meeting agent once more before the take. Confirm `tail -f runtime/salesforce.log` ticks during the take.
- Hard fallback: Open `http://127.0.0.1:8123/api/v1/salesforce/log` in a browser tab (tab 9) which renders the same JSON.

### P5. Audit log JSON is too noisy to read in shot 19

- Cause: Long audit history.
- Recovery: Pre-filter: `tail -n 200 runtime/audit.jsonl | jq -c 'select(.kind=="post_meeting") | {model, input_tokens, output_tokens}' | tail -n 5`.
- Hard fallback: Just say "every Claude call lands in the audit log" and skip the terminal shot.

### P6. Tools panel returns a 500 (shot 22-25)

- Cause: Anthropic 429 (rate limit) or transient backend error.
- Recovery: Switch model to Haiku 4.5 in that panel. Re-submit. Toast errors are visible in the bottom-right.
- Hard fallback: Show the Cost calculator (panel 04) twice - it is pure compute and never fails. Skip the failing panel.

### P7. Vega panel inside a Kibana dashboard fails to render (b-roll only)

- Cause: Kibana 9.3 sometimes rejects URL-based Vega specs.
- Recovery: Open the [Customer] variant of the dashboard which uses inline `data.values` only. Both URLs are returned by the seed call (`dashboard_url_customer`).
- Hard fallback: Skip the Kibana b-roll entirely; the demo-data page already shows the seed counts.

### P8. Agent Builder returns "live: false" pill (shot 26)

- Cause: `KIBANA_API_KEY` not exported, or Kibana not on 9.x with Agent Builder enabled.
- Recovery: Stop, fix the API key in `.env`, restart uvicorn, re-run `sync_agent_builder.py`. Do not record without the green pill.
- Hard fallback: If Kibana cannot be brought live in time, the dry-run mode also streams reasoning - voiceover ad-lib: "running in local-mock mode for the recording, against real Claude" and continue.

### P9. Workflow webhook does not fire within 90s (shot 29-30)

- Cause: Kibana rule scheduled at 1-minute interval, demo run started inside the dead zone.
- Recovery: Click "Trigger now (skip wait)" instead of waiting for the rule. The button hits `/workflows/triggered` directly. Adjust the voiceover from "the rule polls every minute" to "and to keep the demo tight, trigger-now skips the wait."
- Hard fallback: Show the existing entries in the Recent fires list from the priming run; voiceover: "this fire is from a minute ago when I primed the demo."

### P10. Agent gives an unexpected answer in any chat shot

- Recovery line: "Let me reframe that." Then re-send the same chip prompt verbatim. Each chip prompt is canned in `meeting.js` lines 175-250 and `agent-builder.html` lines 47-52, so reproducibility is high.
- Last resort: Cut the take, restart from the beginning of the affected beat. The Hook + Pre-meeting block is the most expensive to redo, so restart from a beat boundary not from the top.

### P11. Browser tab crashes mid-take

- Recovery: `Cmd Shift T` reopens it. The dashboard and meeting tabs are stateless; the chat tabs persist via localStorage so the conversation survives.
- Hard fallback: Cut, restart from the last completed beat boundary.

### P12. Terminal pane scrolled away during recording

- Recovery: `Cmd K` clears the screen. Re-paste the `tail` command from a sticky note above the keyboard.

---

End of storyboard. Single source of truth for the take. If a shot here disagrees with `docs/demo-script.md`, the script wins for words and the storyboard wins for clicks.
