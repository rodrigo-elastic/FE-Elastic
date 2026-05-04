# FE Copilot - 5 Minute Demo Script

> Hackathon: FY27 SKO FE Summit - "Hack. Build. Automate The Impossible."
> Submission: Rodrigo Careaga, Senior Customer Architect, Elastic
> Deadline: 2026-05-10 23:59 ET
> Target runtime: 5:00 (this script lands at 5:00, plus or minus 10 seconds)
> Recording: Loom or QuickTime, 1080p, captions on, single take preferred
> Backend assumed running at http://localhost:8123 (Kibana 9.3.4 at http://localhost:5603 for Agent Builder beats)
> Built with Elastic Cloud 9.3.4 and Anthropic Claude. Apache 2.0 open source.

## Judging criteria coverage map

| Beat | Time | Criterion |
|---|---|---|
| B0 Title slate | 0:00-0:10 | Polish |
| B1 Autopilot | 0:10-0:50 | Demo Quality, FE Impact, Use of Workflows + Agent Builder |
| B2 FE Brain | 0:50-1:30 | FE Impact, Polish |
| B3 Pre-meeting brief | 1:30-2:00 | FE Impact, Polish |
| B4 Auro orchestrator | 2:00-2:40 | Use of Workflows + Agent Builder |
| B5 Battlecards + Sloane | 2:40-3:15 | FE Impact, Reusability |
| B6 Demo Data + dashboards | 3:15-4:00 | Reusability, Demo Quality |
| B7 Two workflows | 4:00-4:45 | Use of Workflows + Agent Builder, Demo Quality |
| B8 Outro | 4:45-5:00 | Reusability, Polish |

---

## B0. Title slate (0:00-0:10, 10 seconds)

**Visual cue:** Full-bleed black slate. Elastic horizontal logo top-left. Centered title in Lochmara: "FE Copilot". Subtitle in white: "11 personas. 5 scenarios. 2 workflows. Sub-15s time to value." Bottom-right corner: "FY27 SKO FE Summit / Rodrigo Careaga / Senior Customer Architect, Elastic".

**On-screen overlay text:**
- FE Copilot
- 11 personas. 5 scenarios. 2 workflows. Sub-15s time to value.

**Voiceover EN:** "FE Copilot. Eleven personas. Five scenarios. Two workflows. Sub fifteen seconds to value."

**B-roll:** Slate dissolves into the live homepage at the cut. No music bed under the title; let the silence make the line land.

**Talk track:** Read the EN line slowly. Land on each number. The slate carries for the full ten seconds.

**Judging mapping:** Polish.

---

## B1. Autopilot (0:10-0:50, 40 seconds)

**Visual cue:** Open `http://localhost:8123/`. Click the gradient hero button "Show me the magic". The page dims. Caption bar mounts top-center, 7-step dock right, iframe panel center. The 7 steps run autonomously over forty seconds while the presenter stays silent and motionless.

**On-screen overlay text:** (the autopilot captions are the overlay)

**Voiceover EN:** Silent. The captions speak. Mouse parked on the side of the screen.

**Captions in order (the narration):**
1. "Quick Research. Banco Santander."
2. "Brief writes itself from live SEC EDGAR, news, and Wikipedia. Haiku 4.5."
3. "Brief renders in the meeting view. Every claim cites a source."
4. "Field Assistant. Auro picks two specialists in parallel: POC plan and TCO."
5. "Agent Builder. Live in Kibana. MCP tools listed, master agent owns them."
6. "Workflow fires. Doc lands in fec-transcript-inbox. SFDC and Slack write back."
7. "Demo complete. Eleven personas, two workflows, five to seven cents per run."

**B-roll:** Subtle confetti at step 1 and step 7. No music; the captions carry the rhythm.

**Talk track:** Mute for forty seconds. Do not narrate over captions. Practice once so you do not break silence.

**Judging mapping:** Demo Quality, FE Impact, Use of Workflows + Agent Builder.

---

## B2. FE Brain (0:50-1:30, 40 seconds)

**Visual cue:** Open `/fe-brain.html`. Click suggested chip "How do I tune ILM for hot+warm+frozen 200 GB/day?". Wait six to nine seconds for the streamed answer. Hover [1][2][3] inline citations. Pan cursor to right-side citations panel; pause on the elastic.co/guide ILM URL.

**On-screen overlay text:**
- FE Brain. ELSER hybrid retrieval, Elastic public docs.
- 407 chunks. 103 URLs. Hybrid plus rerank.
- 5 of 5 on the W4D audit (relevance, grounding, coverage, tone).

**Voiceover EN:**
"FE Brain. ELSER hybrid retrieval over the Elastic public docs. Four hundred seven chunks, one hundred three URLs. Query expansion plus BM25 plus reciprocal rank fusion plus a Haiku rerank. Mei, ex enablement docs lead. Five out of five on the audit."

**B-roll:** Zoom on the three inline citation chips. Right-side panel pulses on render.

**Talk track:** Click slowly. Wait two seconds before reading. Land hard on "five out of five".

**Judging mapping:** FE Impact, Polish.

---

## B3. Pre-meeting brief grounded (1:30-2:00, 30 seconds)

**Visual cue:** Open `/`. Click Banking tile (one of 3 industry templates). Type "Banco Santander" in Company. Submit Quick Research. Page redirects to `/meeting.html`. Scroll to "Sources used". Click one SEC EDGAR link, hold one second, close tab.

**On-screen overlay text:**
- 3 industry templates. One click into Quick Research.
- Banco Santander. Live SEC EDGAR. Real URLs.

**Voiceover EN:**
"Three industry templates. Banking, retail, public sector. Click banking. Type Banco Santander. Hit Quick Research. Brief writes itself in under twenty seconds. Every source real. SEC EDGAR. News with verifiable URLs. Wikipedia. I click the EDGAR link. The filing opens. The citation is real."

**B-roll:** Zoom on the headline as it streams. Pulse the EDGAR URL chip before the click.

**Talk track:** Let the redirect breathe. Do not click around while the brief streams; the streaming is the proof.

**Judging mapping:** FE Impact, Polish.

---

## B4. Auro orchestrator (2:00-2:40, 40 seconds)

**Visual cue:** On the meeting page, scroll to the Field Assistant mini panel in the Brief tab. Click chip "POV plan + TCO". Two collapsible tool-call cards render inline (`fec_poc_plan` and `fec_cost_calc`, parallel) plus a unified synthesis below. Cursor pauses on the parallel-arrow indicator.

**On-screen overlay text:**
- Auro orchestrator. Master agent over MCP.
- Parallel tool calls: fec_poc_plan + fec_cost_calc.
- One question. Two specialists. One coherent answer.

**Voiceover EN:**
"One question. Click the chip. POV plan plus TCO. Auro is the conductor. The master agent picks two specialists, fec underscore poc plan and fec underscore cost calc, runs them in parallel over MCP, and synthesizes a unified answer. One question. Two specialists. One coherent answer. Auro is the conductor."

**B-roll:** Picture-in-picture animation of the two tool-call cards collapsing into the synthesis. Soft arrow overlay connecting them.

**Talk track:** Land "Auro is the conductor" twice; it bookends the beat. Do not click during synthesis stream.

**Judging mapping:** Use of Workflows + Agent Builder.

---

## B5. Battlecards + Sloane (2:40-3:15, 35 seconds)

**Visual cue:** Open `/battlecards.html`. Click the Splunk card. Page transitions to full-screen detail (two-thirds card, one-third embedded chat right). Click chip "TCO at 200 GB/day". Sloane returns 10 technical dimensions, $112k vs $443k, 74.66 percent savings, plus a "Where Splunk genuinely wins" section. Underline the savings number, scroll to honest gaps.

**On-screen overlay text:**
- Battlecards. Full-screen detail with embedded chat.
- 10 technical dimensions. $112k vs $443k. 74.66 percent savings.
- Honest gaps named.

**Voiceover EN:**
"Battlecards. I click Splunk. Full-screen detail with chat embedded on the right. I ask Sloane for the TCO at two hundred gigs a day. Ten technical dimensions. One hundred twelve thousand versus four hundred forty three thousand. Seventy four point six six percent savings. And the honest gaps section names where Splunk genuinely wins. Sloane was a competitive architect for fifteen years. Comparative intelligence with no spin."

**B-roll:** Pulse on the dollar numbers. Zoom on "Where Splunk genuinely wins".

**Talk track:** Read dollars carefully. Pronounce "seventy four point six six" cleanly.

**Judging mapping:** FE Impact, Reusability.

---

## B6. Demo Data + paired dashboards (3:15-4:00, 45 seconds)

**Visual cue:** Open `/demo-data.html`. Five scenario cards visible: Black Friday outage, Bank fraud spike, Public sector breach, SaaS churn, Logistics SLA. On the Black Friday card click "Open [FE] dashboard". Browser switches to Kibana FE-flavored dashboard. Scroll through errors-by-service Lens, p99 latency line, KPI cards, top failing endpoints. Back to demo-data, click the switcher to the Customer view. Same data, business framing.

**On-screen overlay text:**
- 5 scenarios. 10 paired Kibana dashboards.
- Same data. Two audiences. FE and Customer.

**Voiceover EN:**
"Demo Data. Five story driven scenarios. Black Friday outage. Bank fraud spike. Public sector breach. SaaS churn. Logistics SLA. Each scenario seeds a real Elasticsearch index and ships ten paired Kibana dashboards. FE flavor and Customer flavor. Same data. Two audiences. The FE sees errors by service and p99 latency. The customer sees SLO burn and revenue at risk. One click flips the lens."

**B-roll:** Hold one second on each Kibana panel as you scroll. Do not zoom in.

**Talk track:** Speak through the Kibana scroll. Land on "Same data. Two audiences." with a pause.

**Judging mapping:** Reusability, Demo Quality.

---

## B7. Two workflows closing the loop (4:00-4:45, 45 seconds)

**Visual cue:** Open `/workflow-demo.html`. Status panel: both rules registered (Workflow 1 transcript inbox, Workflow 2 orphan action items), connector reachable, both pills green. Click "Fire demo transcript". Toast confirms doc indexed into `fec-transcript-inbox`. New row appears in "Recent webhook fires". Cut to terminal pane right: `tail -f runtime/salesforce.log`. Six writes from Workflow 1 scroll past (Opportunity MEDDPICC, ContentNote, ContentDocumentLink, Competitor, Deal Health, Slack). Second wave prefixed `[Auto]`: Salesforce Tasks from Workflow 2 for orphan high-impact items.

**On-screen overlay text:**
- Workflow 1: doc -> rule -> webhook -> agent -> SFDC + Slack.
- Workflow 2: agent output -> rule -> webhook -> orphan SFDC tasks.
- Agents trigger workflows. Workflows trigger agents. Loop closed.

**Voiceover EN:**
"Two workflows close the loop. A doc lands in fec dash transcript dash inbox. The first Kibana rule fires. The webhook calls our backend. The post meeting agent runs. The post meeting record indexes into fec dash post dash meetings. That index write is the trigger for the second rule. The second rule fires. The orphan webhook scans the action items. Every high impact item with no owner becomes a Salesforce task, prefixed Auto. Agents trigger workflows. Workflows trigger agents. The customer rep does nothing."

**B-roll:** Clock overlay showing elapsed seconds from "Fire" to first SFDC write (target under five seconds), then to first orphan task (target under ninety seconds; pre-prime so the second wave lands in the beat).

**Talk track:** Longest line in the script. Slow down. Hit the rhythm: "Agents trigger workflows. Workflows trigger agents." That is the headline of the submission.

**Judging mapping:** Use of Workflows + Agent Builder, Demo Quality.

---

## B8. Outro (4:45-5:00, 15 seconds)

**Visual cue:** Cut back to the homepage. Five rapid-fire chips pop along the bottom, each 1.5 to 2 seconds: "Cmd+K command palette", "Five languages", "Mobile responsive", "axe-core a11y, zero violations", "Apache 2.0 open source". Final card overlays bottom-third: "github.com/rodrigo-elastic/FE-Elastic". Lockup: "Built with Elastic Cloud 9.3.4 and Anthropic Claude".

**On-screen overlay text:**
- Cmd+K. 5 languages. Mobile. a11y. Apache 2.0.
- github.com/rodrigo-elastic/FE-Elastic
- Built with Elastic Cloud 9.3.4 and Anthropic Claude.

**Voiceover EN:**
"Cmd K command palette. Five languages. Mobile responsive. axe-core, zero violations. Apache two point zero, open source. github dot com slash rodrigo dash elastic slash F E dash Elastic. Built with Elastic Cloud nine point three point four and Anthropic Claude. Thank you."

**B-roll:** Logo dissolve to black with the GitHub URL on the last frame for two seconds. No music sting; let the URL breathe.

**Talk track:** Read chips at a clip. Slow on the GitHub URL so a viewer can copy it. Land "Thank you" cleanly.

**Judging mapping:** Reusability, Polish.

---

## Timing math

| Beat | Start | End | Duration |
|---|---|---|---|
| B0 Title slate | 0:00 | 0:10 | 0:10 |
| B1 Autopilot | 0:10 | 0:50 | 0:40 |
| B2 FE Brain | 0:50 | 1:30 | 0:40 |
| B3 Pre-meeting brief | 1:30 | 2:00 | 0:30 |
| B4 Auro orchestrator | 2:00 | 2:40 | 0:40 |
| B5 Battlecards + Sloane | 2:40 | 3:15 | 0:35 |
| B6 Demo Data + dashboards | 3:15 | 4:00 | 0:45 |
| B7 Two workflows | 4:00 | 4:45 | 0:45 |
| B8 Outro | 4:45 | 5:00 | 0:15 |
| **Total** | | | **5:00** |

Exactly five minutes. Within the plus or minus ten second tolerance.

---

## Diff vs the old script

The previous script ran 5:10 across nine beats sized for the 7-tool, 3-agent build. Two segments were cut to land the new 5:00 cut and to let the autopilot do the storytelling.

**Cut: Live Companion replay (was 1:25 to 2:15, 50 seconds).** The live transcript replay duplicates what Auro now does inside the Field Assistant on the Brief tab. The replay was clicky, took fifty seconds to land two alerts, and pulled focus from the orchestration story. Auro covers the same per-turn intelligence in B4 with a single chip click and one clean response.

**Cut: Tools rail walkthrough (was 3:15 to 4:00, 45 seconds).** Walking each panel one at a time felt like a feature tour, not a product story. The new structure shows tools through the autopilot (B1 hits four of them implicitly) and through the Auro chip in B4 (parallel POC plan plus TCO). The eleven personas are named in the captions and the voiceover; the rail itself is no longer the act.

**Added: Autopilot opens the demo (B1).** The autopilot is the single biggest demo moment. It compresses three live beats into forty seconds of autonomous narration. Letting it open means judges see the entire product before the presenter has typed a character.

**Added: FE Brain (B2).** The W4D RAG audit landed at five out of five. It deserved its own beat, not a footnote.

**Added: Demo Data plus paired dashboards (B6).** Ten paired Kibana dashboards over five scenarios is a reusability claim the old script could only gesture at. Showing the FE-vs-Customer flip in real Kibana proves it.

**Added: Two workflows, both directions of the loop (B7).** The old script only showed Workflow 1 (doc to agent). Workflow 2 (agent output to orphan SFDC tasks) is the inverse; together they close the bi-directional loop the rubric calls "Use of Workflows + Agent Builder".

**Added: explicit numbers in slate and outro.** Eleven personas, five scenarios, two workflows, ten paired dashboards, four hundred seven chunks, five out of five, seventy four point six six percent, five to ten cents per autopilot run.

**Added: explicit GitHub URL, Apache 2.0, and stack lockup (B8).** The old outro left these implicit. They belong in the last fifteen seconds.
