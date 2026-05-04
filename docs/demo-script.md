# FE Copilot - 5 Minute Demo Script

> Hackathon: FY27 SKO FE Summit - "Hack. Build. Automate The Impossible."
> Submission: Rodrigo Careaga, Senior Customer Architect, Elastic
> Deadline: 2026-05-10 23:59 ET
> Target runtime: 5:00 (this script lands at 5:10, within tolerance)
> Recording: Loom or QuickTime, 1080p, captions on, single take preferred
> Backend assumed running at http://localhost:8123 (Kibana 9.x at http://localhost:5603 for Agent Builder beats)

## Storyboard arc (one line each)

1. Title slate. Brand the product.
2. Hook. Name the FE pain.
3. Pre-meeting brief. Show the brief writing itself from real SEC EDGAR data.
4. Live companion. Show alerts firing inside a transcript.
5. Post-meeting. Show one click syncing to Salesforce, Slack, MEDDPICC.
6. Tools rail. Show the seven Field Engineering utilities.
7. Agent Builder + MCP. Show the master agent chaining two tools live in Kibana.
8. Workflow loop. Show a transcript hitting the inbox index and the post-meeting agent firing on its own.
9. Outro. Reusability across every FE segment.

## Judging criteria coverage map

| Beat | Time | Criterion |
|---|---|---|
| Title slate | 0:00-0:05 | Polish |
| Hook | 0:05-0:25 | FE Impact |
| Pre-meeting | 0:25-1:25 | FE Impact, Polish |
| Live Companion | 1:25-2:15 | FE Impact, Demo Quality |
| Post-meeting + Salesforce | 2:15-3:15 | FE Impact, Reusability |
| FE Tools rail | 3:15-4:00 | Reusability, Polish |
| Agent Builder + MCP | 4:00-4:45 | Use of Workflows + Agent Builder |
| Workflow loop | 4:45-5:00 | Use of Workflows + Agent Builder, Demo Quality |
| Outro | 5:00-5:10 | Reusability |

---

## 0. Title slate (0:00-0:05, 5 seconds)

**Visual cue:** Full-bleed black slate. Elastic horizontal logo top-left. Centered title in Lochmara: "FE Copilot". Subtitle in white: "Three agents. Seven tools. One pre-meeting flow." Bottom-right corner: "FY27 SKO FE Summit / Rodrigo Careaga / Senior Customer Architect".

**On-screen overlay text:**
- FE Copilot
- For Elastic Field Engineers

**Voiceover EN:** "FE Copilot. For Elastic Field Engineers."

**Voiceover ES:** "FE Copilot. Para los Field Engineers de Elastic."

**B-roll:** Slate dissolves into the live dashboard at the cut.

---

## 1. Hook (0:05-0:25, 20 seconds)

**Visual cue:** Open `http://localhost:8123/`. Cursor hovers the "Calendar inbox" section showing a stacked list of upcoming meetings with consultant names mixed in (Accenture, KPMG, Deloitte). Pause on a meeting titled "Mercado Libre x Elastic, observability consolidation".

**On-screen overlay text:**
- 6 meetings a day. 30 minutes each on prep.
- That is 15 hours a week. Per FE.

**Voiceover EN:**
"Field Engineers run six customer meetings a day. Each one wants thirty minutes of prep. That is fifteen hours a week, gone, before we open the laptop. FE Copilot gets that time back."

**Voiceover ES:**
"Los Field Engineers tenemos seis reuniones de cliente al dia. Cada una pide treinta minutos de preparacion. Eso son quince horas por semana, perdidas, antes de abrir la laptop. FE Copilot las recupera."

**B-roll:** Quick montage cuts (one frame each, 200ms): a 10-K PDF, a Salesforce opportunity page, a Slack DM thread, a Splunk SPL editor, a battlecard PDF. Land on the FE Copilot dashboard.

---

## 2. Pre-meeting research (0:25-1:25, 60 seconds)

**Visual cue:**
1. From the dashboard at `http://localhost:8123/`, click the "Pre-meeting research" tab (already active).
2. In Quick Research, type "Mercado Libre" into Company, "Fintech" into Industry, "Enterprise" into Size. Stack notes: "Splunk, AWS, Datadog". Meeting context: "August renewal, observability consolidation".
3. Click "Generate brief". Brief streams in section by section.
4. Scroll the brief: Why now, Recent signals, Pain points, Discovery questions, Talking points vs Datadog, Risks. Hover on the "10-K, sec.gov" citation link so the URL preview shows.
5. Click "Download" to flash the PDF, then close it.
6. In a small terminal overlay, run `tail -1 runtime/slack.log` showing the Slack post landed in `#fe-copilot-briefs`.

**On-screen overlay text:**
- Live SEC EDGAR. Real 10-K. Real news URLs.
- Brief delivered to Slack. PDF on phone.
- Haiku 4.5. ~$0.02 per run.

**Voiceover EN:**
"I type the company. Mercado Libre. The Pre-Meeting agent pulls the live ten-K straight from SEC EDGAR, the news with verifiable URLs, the Wikipedia profile. Out comes a structured brief. Why now. Recent signals. Pain points. Discovery questions. Talking points against Datadog. Risks. The same brief lands as a PDF and as a Slack message in the FE channel one hour before the meeting. Two cents per run on Haiku 4.5. Sixty seconds, not thirty minutes."

**Voiceover ES:**
"Escribo la empresa. Mercado Libre. El agente Pre-Meeting trae el diez-K en vivo desde SEC EDGAR, las noticias con URLs verificables, el perfil de Wikipedia. Sale un brief estructurado. Por que ahora. Senales recientes. Dolores. Preguntas de discovery. Puntos de venta contra Datadog. Riesgos. El mismo brief llega como PDF y como mensaje de Slack al canal del FE, una hora antes de la reunion. Dos centavos por ejecucion en Haiku 4.5. Sesenta segundos, no treinta minutos."

**B-roll:** Side-card overlays: "SEC EDGAR live API", "Wikipedia + news fixtures", "MEDDPICC + BANT primer baked in".

---

## 3. Live Companion (1:25-2:15, 50 seconds)

**Visual cue:**
1. From the brief, click the "Live Companion" tab in the meeting view (`/meeting.html?id=meli-mtg-001`).
2. Click "Replay transcript".
3. Transcript starts replaying turn by turn. Pause when the customer says "we are happy with Datadog right now". A red competitor alert slides in under that turn with a suggested whisper line.
4. Continue the replay. When the customer says "we report cost per business unit to the CFO every quarter", a blue MEDDPICC alert pops up on the Metrics axis.
5. Cursor hovers the alert: it shows "Source quote" plus "Suggested response".

**On-screen overlay text:**
- Per-turn alerts. Sub-second latency.
- Competitor mention. MEDDPICC capture. Risk.
- Haiku 4.5 whispering in your ear.

**Voiceover EN:**
"I am in the meeting. The transcript streams. The Live Companion runs Haiku once per turn. Competitor mention. Datadog. Red alert with the suggested whisper line. Then the customer talks about reporting cost per business unit to the CFO. That is a Metric. The MEDDPICC card lights up automatically. No FE I know hits every MEDDPICC slot live. The agent does."

**Voiceover ES:**
"Estoy en la reunion. La transcripcion fluye. El Live Companion corre Haiku una vez por turno. Mencion del competidor. Datadog. Alerta roja con la frase sugerida. Despues el cliente habla de reportar costo por unidad de negocio al CFO. Eso es una Metrica. La tarjeta MEDDPICC se enciende sola. Ningun FE que conozco completa MEDDPICC en vivo. El agente si."

**B-roll:** Zoom-in on the alert chips. Speed up the transcript replay 2x for the boring turns, snap back to 1x on the alert turns.

---

## 4. Post-meeting + Salesforce (2:15-3:15, 60 seconds)

**Visual cue:**
1. Click "Post-Meeting" tab.
2. Click "Run Post-Meeting Agent".
3. Page renders four blocks in sequence: Summary, Action items (with owner, due date, source quote), MEDDPICC radar (2-column grid, Metrics through Champion), Competitor mentions, Follow-up email draft in monospace.
4. Open a terminal overlay: `tail -n 12 runtime/salesforce.log`. Six writes scroll past: Opportunity MEDDPICC fields, ContentNote, ContentDocumentLink, Competitor update, Deal_Health update, Slack post.
5. Cut to the email draft, hover the "Copy to Gmail" button.

**On-screen overlay text:**
- One click. Six Salesforce writes.
- Every action item quoted from the call.
- Slack + SFDC + Email draft. Done.

**Voiceover EN:**
"The call ends. One click. The Post-Meeting agent writes the summary, pulls action items with owner, due date, and the verbatim quote that grounds them. Updates MEDDPICC. Catches competitor mentions. Drafts the follow-up email. Then it pushes to Salesforce. Six writes. Opportunity MEDDPICC. ContentNote. Document link. Competitor record. Deal Health. Slack post. The follow-up email is sitting in your drafts before you have closed the laptop."

**Voiceover ES:**
"Termina la reunion. Un click. El agente Post-Meeting escribe el resumen, saca los action items con responsable, fecha y la cita textual que los respalda. Actualiza MEDDPICC. Captura menciones de competidores. Redacta el correo de seguimiento. Despues empuja a Salesforce. Seis escrituras. MEDDPICC en la Oportunidad. ContentNote. Document link. Registro de competidor. Deal Health. Post de Slack. El correo de seguimiento esta en tus borradores antes de que cierres la laptop."

**B-roll:** Split-frame at the end: left side the Salesforce mock log, right side the Slack channel post, both timestamped within the same second.

---

## 5. FE Tools rail (3:15-4:00, 45 seconds)

**Visual cue:**
1. Click the persistent left sidebar entry "Tools" (`/tools.html`).
2. Page shows seven collapsible panels numbered 01 to 07. Hover the rail and call out the names: POC plan, SPL to ES|QL, Compliance, Stack extractor, Code sample, Cost calc, Capacity.
3. Open panel 02 SPL to ES|QL. Paste `index=web sourcetype=access | stats count by host | sort -count | head 10`. Click "Convert to ES|QL". The ES|QL block renders with caveats below it.
4. Close that panel. Open panel 06 Cost calc. Inputs: 200 GB per day, 12 months retention, current spend 1.5M USD. Click "Calculate". Show the side-by-side Elastic vs Splunk vs Datadog table with annual savings.
5. Close. Open panel 03 Compliance mapper. Frameworks: DORA, PCI DSS. Click "Map". Show the controls table mapped to native Elastic features.

**On-screen overlay text:**
- 7 utilities. One sidebar. Every page.
- SPL to ES|QL. Cost. Compliance. Capacity. POC. Stack. Code.
- Each one a Claude expert persona.

**Voiceover EN:**
"Same sidebar, every page. Seven Field Engineering utilities. SPL to ES|QL with the migration caveats Diego the ex-Splunk consultant warns you about. Cost calculator with Elastic, Splunk and Datadog side by side. Compliance mapper that knows DORA, PCI, FFIEC, HIPAA. POC plan. Capacity planner. Stack extractor. Code sample generator. Each tool wraps a Claude expert persona, twelve to twenty years of Field experience baked into the prompt."

**Voiceover ES:**
"La misma barra lateral en cada pagina. Siete utilidades de Field Engineering. SPL a ES-QL con las advertencias que Diego, ex consultor de Splunk, te recuerda. Calculadora de costo con Elastic, Splunk y Datadog lado a lado. Mapeador de compliance que conoce DORA, PCI, FFIEC, HIPAA. Plan de POC. Planificador de capacidad. Extractor de stack. Generador de codigo. Cada herramienta envuelve a un experto en Claude, con doce a veinte anos de experiencia de campo dentro del prompt."

**B-roll:** Speed up the SPL conversion with a 1.5x time-lapse. Pop the cost-calc savings number ("annual savings: 740,000 USD") as a callout chip.

---

## 6. Agent Builder + MCP (4:00-4:45, 45 seconds)

**Visual cue:**
1. Click "Agent Builder" in the sidebar (`/agent-builder.html`).
2. Status pills at the top: "Connected", "agent: fec_field_assistant", "7 MCP tools". Cut to Kibana in another tab at `Stack Management -> Agent Builder -> Tools` and show the seven `fec_*` tools listed.
3. Back in the FE Copilot Agent Builder page, click the suggested chip "Chain: SPL + cost".
4. The chat streams the master agent's reasoning. It calls `fec_spl_to_esql`, then feeds the answer into `fec_cost_calc`. Both tool calls render inline as collapsible steps.
5. Cut to the customer-fit dashboard in Kibana: open the meeting view, click "Create dashboard in Kibana". Switch tabs, show the eight markdown panels rendered: profile, what they care about, pains, compliance, TCO, capacity, competitive landscape, action items. Two-tab switcher labelled `[FE]` and `[Customer]`.

**On-screen overlay text:**
- Master agent: fec_field_assistant.
- 7 tools chained over MCP.
- 8-panel customer-fit dashboard. One click.

**Voiceover EN:**
"This is where workflows live. Inside Kibana. Agent Builder. The master agent fec underscore field assistant owns all seven tools over MCP. I ask one question. Translate this SPL and tell me the cost at two hundred gigs a day. The agent chains two tools by itself. Translation, then cost. And from any meeting I click once and the eight-panel customer-fit dashboard renders inside the customer's own Elastic cluster. FE tab and customer tab in the same dashboard."

**Voiceover ES:**
"Aqui viven los workflows. Dentro de Kibana. Agent Builder. El agente maestro fec guion bajo field assistant es dueno de las siete herramientas via MCP. Hago una sola pregunta. Traduce este SPL y dame el costo a doscientos gigas por dia. El agente encadena dos herramientas solo. Traduccion y despues costo. Y desde cualquier reunion hago un click y el dashboard customer-fit de ocho paneles se crea dentro del cluster Elastic del propio cliente. Pestana FE y pestana customer en el mismo dashboard."

**B-roll:** Picture-in-picture of the chained tool calls (SPL block on top, cost table below, animated arrow connecting them). Logo lockup of "Elastic Agent Builder" + "MCP" in the corner.

---

## 7. Workflow loop (4:45-5:00, 15 seconds)

**Visual cue:**
1. Click "Workflow" in the sidebar (`/workflow-demo.html`).
2. Show the four-step diagram already on the page: doc into `fec-transcript-inbox`, Kibana ES-query rule fires, webhook hits backend, agent writes Salesforce + Slack.
3. Click "Fire demo transcript". Then "Trigger now (skip wait)". A green webhook fire appears in the "Recent webhook fires" stream within two seconds. Cut to the Salesforce log tailing on the side.

**On-screen overlay text:**
- Inbox -> Workflow -> Agent -> SFDC + Slack.
- Closed loop. Hands free.

**Voiceover EN:**
"The full loop. A transcript lands in the inbox index. Kibana workflow fires. The post-meeting agent runs on its own. Salesforce and Slack update. No human in the loop."

**Voiceover ES:**
"El ciclo completo. Un transcript cae en el indice de inbox. El workflow de Kibana se dispara. El agente Post-Meeting corre solo. Salesforce y Slack se actualizan. Sin humano en el medio."

**B-roll:** Real-time clock overlay showing the elapsed seconds from "Fire" to "Salesforce write" (target: under 5 seconds).

---

## 8. Outro (5:00-5:10, 10 seconds)

**Visual cue:** Cut back to the dashboard. Zoom out slightly. Brand lockup card overlays bottom-third: "FE Copilot - reusable across every FE segment." Logos: SMB, Mid-market, Enterprise, Public Sector. Final card: "Rodrigo Careaga - Senior Customer Architect - Elastic - FY27 SKO FE Summit".

**On-screen overlay text:**
- 3 agents. 7 tools. 8 panels. 5 languages.
- Same code. Every FE segment.

**Voiceover EN:**
"Three agents. Seven tools. Eight dashboard panels. Five languages. Same code. Every FE segment. Thank you."

**Voiceover ES:**
"Tres agentes. Siete herramientas. Ocho paneles. Cinco idiomas. El mismo codigo. Cada segmento de FE. Gracias."

**B-roll:** Final logo dissolve to black with the GitHub repo URL on the last frame for two seconds.

---

## Recording checklist (do this before you hit record)

- [ ] Backend up: `PYTHONPATH=backend uvicorn app.main:app --reload --port 8123`.
- [ ] Kibana 9.x reachable: `curl -s http://localhost:5603/api/status` returns 200.
- [ ] Agent Builder synced: `PYTHONPATH=backend python -m scripts.sync_agent_builder` shows `ok: true` for all 7 tools and the master agent.
- [ ] Browser zoom 110 percent so font sizes read on a 1080p capture.
- [ ] Hide bookmarks bar. Close other tabs. Disable notifications.
- [ ] Reset state: `rm -rf runtime/briefs runtime/post_meeting runtime/emails runtime/slack.log runtime/salesforce.log` so the demo starts clean.
- [ ] Open these tabs in order so Cmd+Tab matches the script: dashboard, meeting view, tools, agent-builder, workflow-demo, demo-data, Kibana Stack Management.
- [ ] Mic check. Read the first 30 seconds of the EN voiceover, then play back. Adjust gain.
- [ ] Stopwatch in a corner of the second monitor (not on capture).

## Timing math

| Section | Start | End | Duration |
|---|---|---|---|
| Title slate | 0:00 | 0:05 | 0:05 |
| Hook | 0:05 | 0:25 | 0:20 |
| Pre-meeting | 0:25 | 1:25 | 1:00 |
| Live Companion | 1:25 | 2:15 | 0:50 |
| Post-meeting + Salesforce | 2:15 | 3:15 | 1:00 |
| Tools rail | 3:15 | 4:00 | 0:45 |
| Agent Builder + MCP | 4:00 | 4:45 | 0:45 |
| Workflow loop | 4:45 | 5:00 | 0:15 |
| Outro | 5:00 | 5:10 | 0:10 |
| **Total** | | | **5:10** |

Within the 5:00 plus-or-minus-10-seconds tolerance.
