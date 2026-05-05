# FE Copilot - Cue Cards

Print this. Tape it next to the monitor. Each card is one beat. Numbers in brackets are the elapsed-time mark you should hit at the START of the card.

---

## [0:00] Title slate

CLICK: nothing. Slate is on screen.

SAY (EN): "FE Copilot. For Elastic Field Engineers."
SAY (ES): "FE Copilot. Para los Field Engineers de Elastic."

---

## [0:05] Hook

CLICK: open `http://localhost:8123/`. Hover the Calendar inbox.

SAY (EN): "Six meetings a day. Thirty minutes prep each. Fifteen hours a week, gone. FE Copilot gets that time back."
SAY (ES): "Seis reuniones al dia. Treinta minutos de prep cada una. Quince horas por semana, perdidas. FE Copilot las recupera."

---

## [0:25] Pre-meeting

CLICK: Pre-meeting research tab.
TYPE: Mercado Atlas, Fintech, Enterprise, Splunk AWS Datadog, August renewal observability consolidation.
CLICK: Generate brief. Scroll. Click Download. Show `runtime/slack.log`.

SAY (EN): "Mercado Atlas. Live ten-K from SEC EDGAR. News with verifiable URLs. Wikipedia. Out comes a structured brief. Why now. Pain. Discovery. Talk track vs Datadog. Risks. Drops to Slack and PDF, one hour pre-meeting. Two cents per run on Haiku 4.5."
SAY (ES): "Mercado Atlas. Diez-K en vivo desde SEC EDGAR. Noticias con URLs verificables. Wikipedia. Sale un brief estructurado. Por que ahora. Dolor. Discovery. Talk track contra Datadog. Riesgos. Cae a Slack y PDF una hora antes. Dos centavos por run en Haiku 4.5."

---

## [1:25] Live Companion

CLICK: Live Companion tab. Replay transcript.
PAUSE on Datadog mention. PAUSE on Metric mention.

SAY (EN): "I am in the meeting. Haiku runs once per turn. Datadog mention, red alert with the suggested whisper. Customer talks cost per BU to the CFO. MEDDPICC Metrics card lights up automatically."
SAY (ES): "Estoy en la reunion. Haiku corre una vez por turno. Mencion de Datadog, alerta roja con la frase sugerida. El cliente habla de costo por BU al CFO. La tarjeta de Metricas de MEDDPICC se enciende sola."

---

## [2:15] Post-meeting + Salesforce

CLICK: Post-Meeting tab. Run Post-Meeting Agent.
SCROLL through Summary, Action items, MEDDPICC, Email.
SHOW: `tail -n 12 runtime/salesforce.log`. Six writes.

SAY (EN): "One click. Summary. Action items with owner, date, verbatim quote. MEDDPICC. Competitors. Email draft. Six Salesforce writes. Slack post. Done before you close the laptop."
SAY (ES): "Un click. Resumen. Action items con responsable, fecha, cita textual. MEDDPICC. Competidores. Borrador de correo. Seis escrituras a Salesforce. Post de Slack. Listo antes de cerrar la laptop."

---

## [3:15] FE Tools rail

CLICK: Tools in the sidebar.
DEMO: SPL to ES-QL with `index=web sourcetype=access | stats count by host | sort -count | head 10`.
DEMO: Cost calc 200 GB per day, 12 months, 1.5M USD.
DEMO: Compliance DORA + PCI DSS.

SAY (EN): "Same sidebar, every page. Twelve utilities. SPL to ES-QL. Cost. Compliance. POC. Capacity. Stack. Code. Knowledge. Troubleshoot. Compare. Orchestrator. Proposal. Each one wraps a Claude expert with twelve to twenty years in the field."
SAY (ES): "La misma barra lateral en cada pagina. Doce utilidades. SPL a ES-QL. Costo. Compliance. POC. Capacidad. Stack. Codigo. Knowledge. Troubleshoot. Compare. Orchestrator. Proposal. Cada una envuelve un experto en Claude, doce a veinte anos de campo."

---

## [4:00] Agent Builder + MCP

CLICK: Agent Builder in sidebar. Show 12-MCP-tools pill.
CLICK: chip "Chain: SPL + cost". Watch tool calls render inline.
CUT to Kibana Stack Management Agent Builder Tools list.
CUT back to a meeting view. CLICK: Create dashboard in Kibana. Show 8 panels and FE / Customer tabs.

SAY (EN): "Inside Kibana. Agent Builder. Master agent fec underscore field assistant owns twelve MCP tools. One question chains two of them. And from any meeting, one click renders the eight-panel customer-fit dashboard inside the customer's own cluster. FE tab and customer tab."
SAY (ES): "Dentro de Kibana. Agent Builder. El agente maestro fec guion bajo field assistant es dueno de doce herramientas MCP. Una pregunta encadena dos. Y desde cualquier reunion, un click crea el dashboard customer-fit de ocho paneles dentro del cluster del propio cliente. Pestana FE y pestana customer."

---

## [4:45] Workflow loop

CLICK: Workflow in sidebar.
CLICK: Fire demo transcript. CLICK: Trigger now.
WATCH the green webhook fire arrive.

SAY (EN): "Transcript hits the inbox index. Kibana workflow fires. Post-meeting agent runs. Salesforce and Slack update. No human in the loop."
SAY (ES): "El transcript cae al inbox. El workflow de Kibana se dispara. El agente Post-Meeting corre. Salesforce y Slack se actualizan. Sin humano en el medio."

---

## [5:00] Outro

CUT: dashboard. Zoom out. Brand card.

SAY (EN): "Three agents. Twelve tools. Eight panels. Five languages. Same code. Every FE segment. Thank you."
SAY (ES): "Tres agentes. Doce herramientas. Ocho paneles. Cinco idiomas. El mismo codigo. Cada segmento de FE. Gracias."

---

## Pacing tips

- Speak at 150 to 165 words per minute. Each EN block above is sized to its time.
- If you lag, drop one B-roll cut, never a number.
- If you overshoot the Tools rail beat, skip the Compliance demo, keep SPL and Cost.
- Re-record the outro alone if the main take ends at 5:15 or later. Splice it in.
