# FE Copilot - 3 Minute Demo Script

> Hackathon: FY27 SKO FE Summit. "Hack. Build. Automate The Impossible."
> Submission: Rodrigo Careaga, Senior Customer Architect, Elastic.
> Deadline: 2026-05-10 23:59 ET.
> Hard cap: 3:00 (180 seconds), single take, English voiceover only.
> Recording: Loom or QuickTime, 1080p, captions on.
> Backend assumed running at http://127.0.0.1:8123. Kibana at https://fe-summit-hackathon-ed0e8e.kb.us-west-1.aws.found.io.
> Built with Elastic Cloud 9.3.4 and Anthropic Claude. Apache 2.0.

## Tagline

FE Copilot. Eleven personas. Five scenarios. Two workflows. Built for Elastic Field Engineers.

## Judging coverage map

| Beat | Time | Title | Criterion |
|---|---|---|---|
| B0 | 0:00 - 0:08 | Title slate | Polish |
| B1 | 0:08 - 0:35 | Autopilot | Demo Quality |
| B2 | 0:35 - 0:55 | FE Brain | FE Impact |
| B3 | 0:55 - 1:25 | Auro orchestrator | Workflows |
| B4 | 1:25 - 1:55 | Battlecards plus Sloane | Reusability |
| B5 | 1:55 - 2:25 | Demo Data plus paired dashboards | Reusability |
| B6 | 2:25 - 2:50 | Two workflows | Workflows |
| B7 | 2:50 - 3:00 | Outro | Polish |

---

## B0. Title slate (0:00 - 0:08, 8 seconds)

**On-screen action:** Full-bleed black slate, Elastic logo top-left, title "FE Copilot" centered, tagline below.

**EN voiceover:** "FE Copilot. Eleven personas. Five scenarios. Two workflows. Built for Elastic Field Engineers." (13 words)

**B-roll:** Slate dissolves into the warm homepage at the cut.

**Judging:** Polish.

---

## B1. Autopilot (0:08 - 0:35, 27 seconds)

**On-screen action:** Click the gradient hero button "Show me the magic". Caption bar mounts top-center, 7-step dock right, iframe panel center. Mouse parked.

**EN voiceover:** Silent. Presenter does not speak. The autopilot captions carry the narration.

**Captions in order (the on-screen narration):**
1. "Quick Research. Banco Santander."
2. "Brief writes itself. SEC EDGAR, news, Wikipedia. Haiku 4.5."
3. "Brief renders. Every claim cites a source."
4. "Field Assistant. Auro picks two specialists in parallel: POV plan and TCO."
5. "Agent Builder live in Kibana. Eleven MCP tools. Master agent."
6. "Workflow fires. Doc lands. SFDC and Slack write back."
7. "Done. Eleven personas. Two workflows. Five to ten cents per run."

**B-roll:** Subtle confetti at step 1 and step 7. No music. Captions carry rhythm.

**Judging:** DemoQuality.

---

## B2. FE Brain (0:35 - 0:55, 20 seconds)

**On-screen action:** Open `/fe-brain.html`. Click chip "Set up semantic_text with ELSER on Elastic Cloud". Inline [n] citations stream. Right-side citation cards render.

**EN voiceover:** "FE Brain. ELSER hybrid retrieval over Elastic public docs. Four hundred seven chunks. Inline citations. Every claim grounded." (18 words)

**B-roll:** Light zoom on inline citation chips as they paint.

**Judging:** FEImpact.

---

## B3. Auro orchestrator (0:55 - 1:25, 30 seconds)

**On-screen action:** Cmd back to the meeting view the autopilot left us on. Scroll to Field Assistant. Click chip "POV plan + TCO". Two parallel tool-call cards render: `fec_poc_plan` and `fec_cost_calc`. Synthesis below.

**EN voiceover:** "Back on the meeting. Field Assistant. One chip. Auro picks two specialists in parallel. POV plan and TCO. One coherent answer." (22 words)

**B-roll:** Soft arrow overlay between the two tool-call cards collapsing into the synthesis.

**Judging:** Workflows.

---

## B4. Battlecards plus Sloane (1:25 - 1:55, 30 seconds)

**On-screen action:** Open `/battlecards.html`. Click the Splunk card. Full-screen detail loads, embedded chat on the right. Click chip "TCO at 200 GB/day". Sloane returns ten technical dimensions, dollar comparison, savings.

**EN voiceover:** "Battlecards. Click Splunk. Sloane runs TCO. Ten dimensions. One twelve K versus four forty three K. Seventy four point six six percent savings." (23 words)

**B-roll:** Pulse on the savings number. Hold one beat on the "Where Splunk genuinely wins" subheading.

**Judging:** Reusability.

---

## B5. Demo Data plus paired dashboards (1:55 - 2:25, 30 seconds)

**On-screen action:** Open `/demo-data.html`. Five scenario cards visible. Click "Open [FE]" on Black Friday. Kibana FE dashboard loads. Scroll once. Back to Demo Data, click switcher to Customer view.

**EN voiceover:** "Demo Data. Five scenarios. Ten paired Kibana dashboards. Black Friday FE view. Flip the switcher. Same data, customer framing." (20 words)

**B-roll:** Hold one second per Kibana panel. No zoom.

**Judging:** Reusability.

---

## B6. Two workflows (2:25 - 2:50, 25 seconds)

**On-screen action:** Open `/workflow-demo.html`. Click "Fire demo transcript". Toast confirms doc indexed. Cut to terminal pane: `tail -f runtime/salesforce.log`. Six writes scroll. Second wave prefixed `[Auto]`.

**EN voiceover:** "Two workflows. Fire the transcript. Kibana rule fires. Webhook hits the agent. Salesforce writes scroll. Agents trigger workflows. Workflows trigger agents." (22 words)

**B-roll:** Underline pulse on the `[Auto]` prefix when the orphan wave lands.

**Judging:** Workflows.

---

## B7. Outro (2:50 - 3:00, 10 seconds)

**On-screen action:** Cut back to homepage. Lower-third overlay: GitHub URL, stack lockup. Logo dissolve to black at 3:00.

**EN voiceover:** "Eleven personas. Two workflows. Cmd K palette. Five languages. Apache 2.0. github dot com slash rodrigo dash elastic slash F E dash Elastic." (24 words)

**B-roll:** GitHub URL holds for the final two seconds.

**Judging:** Polish.

---

## Timing math

| Beat | Start | End | Duration |
|---|---|---|---|
| B0 Title slate | 0:00 | 0:08 | 0:08 |
| B1 Autopilot | 0:08 | 0:35 | 0:27 |
| B2 FE Brain | 0:35 | 0:55 | 0:20 |
| B3 Auro orchestrator | 0:55 | 1:25 | 0:30 |
| B4 Battlecards plus Sloane | 1:25 | 1:55 | 0:30 |
| B5 Demo Data plus dashboards | 1:55 | 2:25 | 0:30 |
| B6 Two workflows | 2:25 | 2:50 | 0:25 |
| B7 Outro | 2:50 | 3:00 | 0:10 |
| **Total** | | | **3:00** |

Sum: 8 + 27 + 20 + 30 + 30 + 30 + 25 + 10 = 180 seconds exact.

---

## Diff vs the 5 minute version

Three cuts from the 5:00 script land us at 3:00. Each cut is intentional and the lost content is recovered elsewhere in the new flow.

**Cut 1: Old B3 "Pre-meeting brief grounded" (was 30 seconds).** The autopilot already streams the Banco Santander brief in B1, captions narrate it, and the iframe shows the citation panel. Re-running the same flow live in a separate beat duplicates work and drains a third of the new budget. The autopilot carries it.

**Cut 2: Long voiceover blocks.** The 5:00 cut had 60 to 80 word voiceovers per beat. The 3:00 cut keeps every voiceover under 25 words. Short declarative sentences. Land each number, move on. Total spoken word count across the whole video sits well under the 280 word ceiling.

**Cut 3: The "5 languages, mobile responsive, a11y" rapid-fire chip strip in the outro.** Five chips at 1.5 to 2 seconds each ate a third of the outro. Merged into a single line in the new B7 voiceover.

Two minor adjustments rolled in alongside the cuts:
- The polished pause moments (two-second holds after click, breathing space in B4 of the 5:00 script) are gone. Timing is tight; the presenter cannot linger.
- B1 grew from 40 seconds to 27 seconds of silence. The autopilot completes the seven steps in that window, captions still narrate, and the voiceover word count for the whole video drops because the presenter is muted through the longest beat.

---

## Word count and reading pace

Voiceover is English only. Spanish is not included.

| Beat | Words |
|---|---|
| B0 Title | 13 |
| B1 Autopilot | 0 (silent) |
| B2 FE Brain | 18 |
| B3 Auro | 22 |
| B4 Battlecards | 23 |
| B5 Demo Data | 20 |
| B6 Workflows | 22 |
| B7 Outro | 24 |
| **Total** | **142** |

142 spoken words across 153 seconds of presenter audio (180 minus 27 silent autopilot seconds). Effective pace: 55 words per minute including all on-screen actions and breath. Read at a natural 150 words per minute, every beat lands inside its budget with two to four seconds of click and breath room.
