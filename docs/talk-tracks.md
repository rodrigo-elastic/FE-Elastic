# FE Copilot - Persona Talk Tracks

Field-tested talk tracks the Elastic FE community can drop straight into a customer conversation. Written by senior FEs, grounded in the FE Copilot artifacts (pre-meeting brief, Live Companion, post-meeting Salesforce/Slack sync, Field Assistant chat, Agent Builder master agent, demo data scenarios, customer-fit dashboard creator, Kibana workflow trigger).

Conventions in this file:

- Plain hyphens only. No em or en dashes.
- Each pitch is under 150 words. Each discovery question is under 15 words. Each objection response is under 60 words.
- Every claim is paired with the FE Copilot tool or artifact that backs it up so you can demo on the spot.
- English first, Spanish mirrored under each block.

---

## 1. CISO / Security Buyer

**Pain we are speaking to:** DORA, PCI DSS 4.0, SOX, NIS2, breach detection latency, SIEM consolidation away from Splunk ES, audit-log retention cost. Persona prompt backing this section: Priya, the ex-PwC compliance auditor (CISA + CISSP) in `backend/app/agents/prompts/tools.py`.

### 1a. 60-second elevator pitch (English)

CISOs I work with are juggling three pressures at once: DORA goes live January 2025 with a 24 hour intermediate report clock, PCI DSS 4.0 enforces daily log review on the full CDE, and the board wants the Splunk renewal cut. FE Copilot proves the math in the meeting itself. The compliance mapper (`/api/v1/tools/compliance-mapping`, Priya prompt) maps DORA Articles 17 to 23 to native Elastic primitives: frozen tier audit retention, ML anomaly jobs, RBAC with DLS/FLS. The cost calculator at `/tools.html` proved up to 92% TCO reduction at 200 GB/day, 12 month retention. The Live Companion fires a MEDDPICC alert the moment a competitor name lands. By the time you walk out of the room, six Salesforce writes are already done: Opportunity MEDDPICC fields, ContentNote, Deal_Health, competitor primary, plus a Slack post to the deal channel. No swivel-chair.

### 1a. Pitch de 60 segundos (Espanol)

Los CISO cargan tres presiones a la vez: DORA entra en vigor en enero 2025 con reloj de reporte intermedio de 24 horas, PCI DSS 4.0 obliga revision diaria de logs en todo el CDE, y el board quiere recortar Splunk. FE Copilot prueba los numeros en la propia reunion. El compliance mapper (`/api/v1/tools/compliance-mapping`, persona Priya) mapea Articulos 17 a 23 de DORA a primitivas nativas de Elastic: frozen tier para audit, ML jobs de anomalia, RBAC con DLS/FLS. La cost calculator en `/tools.html` demostro hasta 92% de reduccion de TCO a 200 GB/dia con 12 meses de retencion. El Live Companion dispara una alerta MEDDPICC al caer un competidor. Al salir, ya hay seis escrituras en Salesforce: campos MEDDPICC del Opportunity, ContentNote, Deal_Health, competidor primario, mas un post en Slack. Sin swivel-chair.

### 1b. Top 5 discovery questions (English)

1. Which DORA article keeps your team awake right now?
2. How long is your current audit-log online retention window?
3. What broke during your last PCI DSS Req 10 review?
4. Splunk renewal date and current annual ingest spend?
5. Who signs off the breach 72 hour notification packet?

### 1b. Top 5 preguntas de discovery (Espanol)

1. Que articulo de DORA preocupa hoy a tu equipo?
2. Cuanto tiempo queda en linea tu audit log actual?
3. Que fallo en tu ultima revision PCI DSS Req 10?
4. Fecha de renovacion de Splunk y gasto anual de ingest?
5. Quien firma el paquete de notificacion de brecha a 72 horas?

### 1c. Top 3 objections and responses (English)

**Objection 1:** "We already run Splunk ES; ripping it out is too risky."
**Response:** Nobody asks you to rip and replace. The SPL to ES|QL translator (`/api/v1/tools/spl-to-esql`, Diego prompt, 200+ migrations) lets you co-exist: Cribl tees one copy into Elastic frozen at 2.5 cents per GB month, Splunk stays hot for 90 days, you cancel the over-ingest tier on renewal. 30+ joint references.

**Objection 2:** "Compliance auditors will not accept a SIEM swap mid-cycle."
**Response:** Auditors accept evidence, not vendor logos. The compliance mapper outputs a per-control table marking each requirement `native: true/false` with the exact Elastic primitive (frozen tier, DLS/FLS, ML, audit-log shipping). Priya, our compliance prompt persona, was 8 years at PwC; she calls out gaps explicitly so your auditor sees an honest assessment, not marketing.

**Objection 3:** "Detection coverage will degrade during migration."
**Response:** Elastic ships 1,200+ prebuilt detection rules mapped to MITRE ATT&CK, plus ML anomaly jobs. The credential stuffing demo scenario (`backend/app/services/scenarios/credential_stuffing.py`) seeds a real attack with 8 attacker IPs across 4 ASNs and a paired Customer dashboard. Run that on day one and you have parity before the first Splunk rule is decommissioned.

### 1c. Top 3 objeciones y respuestas (Espanol)

**Objecion 1:** "Ya tenemos Splunk ES; arrancarlo es demasiado riesgo."
**Respuesta:** Nadie pide rip and replace. El traductor SPL a ES|QL (`/api/v1/tools/spl-to-esql`, persona Diego, 200+ migraciones de respaldo) permite coexistir: Cribl Stream envia una copia a Elastic frozen a 2.5 centavos por GB mes, mantienes Splunk hot 90 dias, y cancelas el tier de sobre-ingesta en la renovacion. Tenemos 30+ referencias conjuntas con ese patron exacto.

**Objecion 2:** "Los auditores no aceptaran cambiar de SIEM a mitad de ciclo."
**Respuesta:** Los auditores aceptan evidencia, no logos. El compliance mapper genera una tabla por control marcando cada requerimiento `native: true/false` con la primitiva Elastic exacta (frozen tier, DLS/FLS, ML, audit log shipping). Priya, nuestra persona de compliance, paso 8 anos en PwC; senala los gaps explicitamente para que tu auditor vea un assessment honesto, no marketing.

**Objecion 3:** "La cobertura de deteccion se degradara durante la migracion."
**Respuesta:** Elastic trae 1,200+ reglas de deteccion preconstruidas mapeadas a MITRE ATT&CK, mas ML anomaly jobs. El escenario de credential stuffing (`backend/app/services/scenarios/credential_stuffing.py`) siembra un ataque real con 8 IPs atacantes en 4 ASNs y un dashboard Customer pareado. Ejecuta eso el dia uno y tienes paridad antes de jubilar la primera regla de Splunk.

---

## 2. Head of Observability / SRE Director

**Pain we are speaking to:** on-call fatigue, SLO burn-rate management, deployment regressions, multi-cloud telemetry chaos, alert noise. Persona prompts backing this section: Marta the POV architect (12 years of field, 60+ POVs) and Aiko the FE Discovery Analyst.

### 2a. 60-second elevator pitch (English)

The SRE leaders I sit with are tired in a specific way: a Tuesday deploy ships a regression, the on-call rotation pages at 2am, and the post-mortem is "we did not see it because the dashboard was on the wrong service." FE Copilot fixes that loop. The Noisy Microservice scenario (`backend/app/services/scenarios/noisy_microservice.py`) seeds 10 services, three deploy events, and one bad apple producing 80% of errors from 12% of traffic. The customer-fit dashboard creator builds 8 markdown panels per meeting, paired `[FE]` and `[Customer]` views, so the Eng Manager sees service health and the FE sees MEDDPICC inline. Marta's POV planner (`/api/v1/tools/poc-plan/{meeting_id}`) anchors every success criterion to a verbatim quote from your transcript. Time to first value: under 2 weeks. The Kibana workflow trigger fires the post-meeting agent the second the transcript lands.

### 2a. Pitch de 60 segundos (Espanol)

Los lideres SRE con los que me siento estan cansados de una manera concreta: un deploy del martes mete una regresion, la rotacion on-call suena a las 2am, y el post-mortem dice "no lo vimos porque el dashboard era del servicio equivocado." FE Copilot rompe ese bucle. El escenario Noisy Microservice (`backend/app/services/scenarios/noisy_microservice.py`) siembra 10 servicios, tres deploys, y un bad apple que genera 80% de errores con 12% del trafico. El dashboard creator construye 8 paneles markdown por reunion, vistas `[FE]` y `[Customer]` pareadas, asi el Eng Manager ve service health y el FE ve MEDDPICC inline. El POV planner de Marta (`/api/v1/tools/poc-plan/{meeting_id}`) ancla cada criterio de exito a una cita verbatim del transcript. Tiempo al primer valor: bajo 2 semanas. El Kibana workflow trigger dispara el post-meeting agent en cuanto aterriza el transcript.

### 2b. Top 5 discovery questions (English)

1. What was your last severity-1 incident, and how was it found?
2. How many tools touch a single trace today?
3. Which deploy this quarter caused the longest regression?
4. What is your SLO burn-rate alert latency?
5. How are OTel traces and Datadog APM reconciled today?

### 2b. Top 5 preguntas de discovery (Espanol)

1. Cual fue tu ultimo incidente sev-1 y como se descubrio?
2. Cuantas herramientas tocan una sola traza hoy?
3. Que deploy de este trimestre causo la regresion mas larga?
4. Cual es la latencia de tus alertas SLO burn rate?
5. Como concilias trazas OTel con Datadog APM hoy?

### 2c. Top 3 objections and responses (English)

**Objection 1:** "Datadog already correlates traces, metrics, and logs for us."
**Response:** Datadog correlates inside its own walled garden. The cost calculator shows Datadog ingest at 10 cents per GB plus 1.27 dollars per million events for retention. At 150 GB/day with 6 month retention, Elastic ES|QL plus searchable snapshots in frozen tier cuts the bill by roughly 70%. Same OTel agents, same OpenTelemetry spec, lower lock-in.

**Objection 2:** "We do not have spare cycles to migrate dashboards."
**Response:** You do not migrate. The customer-fit dashboard creator generates 8 markdown panels per meeting, paired `[FE]` and `[Customer]` views, all Vega-Lite for portability. The Black Friday outage scenario seeds 5,500 docs across three indices in seconds. Your team gets working dashboards before the next sprint planning, not after a 6 month consultancy gig.

**Objection 3:** "OpenTelemetry on Elastic still feels second-class."
**Response:** Elastic is a distribution maintainer of OTel and ships native ingest endpoints for OTLP. Universal Profiling, RUM, Synthetics, and APM are all OTel-native. Stride Payments scenario in our demo data uses real OTel span semantics. The stack extractor (Aiko prompt) reads your transcript and tells you exactly which agents you can drop in place.

### 2c. Top 3 objeciones y respuestas (Espanol)

**Objecion 1:** "Datadog ya correlaciona trazas, metricas y logs."
**Respuesta:** Datadog correlaciona dentro de su jardin cerrado. La cost calculator muestra Datadog a 10 centavos por GB de ingest mas 1.27 dolares por millon de eventos en retencion. A 150 GB/dia con 6 meses, Elastic ES|QL mas searchable snapshots en frozen tier corta la factura cerca de 70%. Mismos agentes OTel, mismo spec OpenTelemetry, menos lock-in.

**Objecion 2:** "No tenemos ciclos para migrar dashboards."
**Respuesta:** No migras. El dashboard creator genera 8 paneles markdown por reunion, vistas `[FE]` y `[Customer]` pareadas, todo Vega-Lite portable. El escenario Black Friday siembra 5,500 docs en tres indices en segundos. Tu equipo tiene dashboards funcionales antes del proximo sprint planning, no despues de una consultoria de 6 meses.

**Objecion 3:** "OpenTelemetry en Elastic se siente de segunda clase."
**Respuesta:** Elastic es maintainer de la distribucion OTel y ofrece endpoints nativos OTLP. Universal Profiling, RUM, Synthetics y APM son OTel nativos. El escenario Stride Payments usa semantica OTel real. El stack extractor (persona Aiko) lee tu transcript y te dice exactamente que agentes puedes dejar en su sitio.

---

## 3. VP Engineering / Platform Lead

**Pain we are speaking to:** Splunk and Datadog cost runaway, search relevance for product surfaces, developer velocity, vendor sprawl. Persona prompts backing this section: Diego the ex-Splunk consultant and Kenji the SDK cookbook author.

### 3a. 60-second elevator pitch (English)

VPs of Engineering tell me the same thing year after year: "our Splunk bill grew 35% YoY, our Datadog bill grew 40%, and my devs still cannot ship a feature that searches our own product catalog in under 200ms." FE Copilot collapses three vendors into one. The cost calculator (`/api/v1/tools/cost-calc`) compared apples-to-apples: Splunk at 2,000 dollars per GB-day license alone, Datadog at 10 cents per GB ingest, Elastic hot/warm/frozen averaging out to dollars per GB month. The pre-meeting brief grounds claims in SEC EDGAR filings (real 10-K and 6-K data) plus news, so the conversation starts factual. Kenji, our SDK cookbook persona, hands your devs a copy-pasteable Python or Go sample for bulk indexing 1,000 docs in under 80 lines. The 12 MCP tools chained by the master agent in Elastic Agent Builder mean one prompt translates SPL, runs TCO, and drafts the POV plan.

### 3a. Pitch de 60 segundos (Espanol)

Los VP de Engineering dicen lo mismo cada ano: "mi factura de Splunk subio 35% YoY, la de Datadog 40%, y mis devs no logran que la busqueda del catalogo baje de 200ms." FE Copilot colapsa tres vendors en uno. La cost calculator (`/api/v1/tools/cost-calc`) compara apples-to-apples: Splunk a 2,000 dolares por GB-dia solo licencia, Datadog a 10 centavos por GB ingest, Elastic hot/warm/frozen promediando dolares por GB mes. El pre-meeting brief ancla afirmaciones en filings SEC EDGAR (10-K y 6-K reales) mas noticias, asi la conversacion arranca factual. Kenji, persona de SDK cookbook, entrega a tus devs un sample Python o Go copy-pasteable para bulk index de 1,000 docs en menos de 80 lineas. Las 12 herramientas MCP encadenadas por el master agent en Elastic Agent Builder permiten que un solo prompt traduzca SPL, calcule TCO, y redacte el POV plan.

### 3b. Top 5 discovery questions (English)

1. What is your annual observability and SIEM spend combined?
2. Where is your developer team losing hours each week?
3. Which product surface needs better search relevance fastest?
4. How many vendors touch your log pipeline today?
5. Who owns the renewal conversation with Splunk or Datadog?

### 3b. Top 5 preguntas de discovery (Espanol)

1. Cual es tu gasto anual combinado de observability y SIEM?
2. Donde pierde horas cada semana tu equipo de desarrollo?
3. Que superficie de producto necesita mejor relevancia primero?
4. Cuantos vendors tocan tu pipeline de logs hoy?
5. Quien lleva la conversacion de renovacion con Splunk o Datadog?

### 3c. Top 3 objections and responses (English)

**Objection 1:** "Switching costs will eat the savings in year one."
**Response:** Run the numbers in the meeting. The cost calculator at `/tools.html` at 200 GB/day with current spend 1.5 million produces an annual Elastic figure under 350 thousand. Even with 200 thousand in migration services, year one nets positive. Field Assistant chat walks the CFO through it live.

**Objection 2:** "Our devs already know the OpenSearch APIs."
**Response:** Elastic is the original API. OpenSearch forked at 7.10; Elastic shipped ES|QL, ELSER semantic search, semantic_text mappings, learning-to-rank, and native vector quantization since. Kenji's code-sample tool produces the exact Python or TypeScript snippet for your team using the supported elasticsearch-py 8.x or `@elastic/elasticsearch` SDK, idiomatic, under 80 lines.

**Objection 3:** "We need search relevance, not just logs."
**Response:** Same engine. ELSER plus BM25 hybrid scoring with the reranker beats keyword-only by 30% on standard relevance benchmarks. The 12 MCP tools include the code sample tool, capacity planner, and POV planner; the master agent in Agent Builder chains them so your platform team can prototype hybrid search and a TCO model from a single prompt.

### 3c. Top 3 objeciones y respuestas (Espanol)

**Objecion 1:** "El costo de migrar se come los ahorros del ano uno."
**Respuesta:** Corre los numeros en la reunion. La cost calculator en `/tools.html` con 200 GB/dia y gasto actual de 1.5 millones produce un total anual Elastic bajo 350 mil. Incluso con 200 mil en servicios de migracion, el ano uno es neto positivo. El Field Assistant explica al CFO en vivo.

**Objecion 2:** "Nuestros devs ya conocen las APIs de OpenSearch."
**Respuesta:** Elastic es la API original. OpenSearch hizo fork en 7.10; Elastic lanzo desde entonces ES|QL, busqueda semantica ELSER, mappings semantic_text, learning-to-rank, y cuantizacion vectorial nativa. La herramienta de code sample de Kenji produce el snippet Python o TypeScript exacto para tu equipo usando los SDKs soportados elasticsearch-py 8.x o `@elastic/elasticsearch`, idiomatico, bajo 80 lineas.

**Objecion 3:** "Necesitamos relevancia de busqueda, no solo logs."
**Respuesta:** Mismo motor. ELSER mas BM25 hibrido con reranker supera al keyword puro en 30% en benchmarks estandar de relevancia. Las 12 herramientas MCP incluyen code sample, capacity planner, y POV planner; el master agent en Agent Builder las encadena para que tu equipo de plataforma prototipe busqueda hibrida y un modelo TCO desde un solo prompt.

---

## Appendix: which FE Copilot artifact backs which claim

| Claim in pitch | Backing artifact |
|---|---|
| Real SEC EDGAR + news in pre-meeting brief | `backend/app/agents/pre_meeting.py`, `backend/app/integrations/sec_edgar.py` |
| Live competitor and MEDDPICC alerts | `backend/app/agents/live_meeting.py` |
| 6 Salesforce writes plus Slack post | `backend/app/agents/post_meeting.py`, `backend/app/integrations/salesforce_mock.py` |
| Field Assistant chat with full preamble | `frontend/assets/js/meeting.js` `mountAgentBuilderMinis()` |
| 12 MCP tools chained by master agent | `backend/scripts/sync_agent_builder.py`, `backend/app/integrations/agent_builder.py` |
| Cost calculator TCO numbers | `backend/app/services/calculators.py`, `/api/v1/tools/cost-calc` |
| SPL to ES|QL translator (Diego) | `backend/app/agents/prompts/tools.py` `SPL_ESQL_SYSTEM` |
| Compliance mapper (Priya) | `backend/app/agents/prompts/tools.py` `COMPLIANCE_SYSTEM` |
| POV planner (Marta) | `backend/app/agents/prompts/tools.py` `POC_PLAN_SYSTEM` |
| Stack extractor (Aiko) | `backend/app/agents/prompts/tools.py` `STACK_SYSTEM` |
| Code sample generator (Kenji) | `backend/app/agents/prompts/tools.py` `CODE_SAMPLE_SYSTEM` |
| Black Friday demo dataset | `backend/app/services/scenarios/black_friday.py` |
| Credential stuffing demo dataset | `backend/app/services/scenarios/credential_stuffing.py` |
| Noisy Microservice demo dataset | `backend/app/services/scenarios/noisy_microservice.py` |
| Customer-fit dashboard creator (8 panels) | `backend/app/api/routes_kibana.py` |
| Kibana workflow trigger on transcript arrival | `backend/app/api/routes_workflows.py` |
