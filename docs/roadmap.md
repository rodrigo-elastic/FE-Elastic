# Roadmap

What ships in this hackathon submission is opinionated and complete enough to use day-to-day, but the project is built so the same patterns extend further. Each item lists the value it unlocks, not just the feature.

## Near term (weeks 1 to 4 after submission)

- **Production deploy on AWS ECS Fargate (shipped)**: the backend now runs at `https://fe-c85291a2a8b144188ee6be1078e79a95.ecs.us-east-1.on.aws`. The Kibana inference connector, the Workflow webhooks, and the AutoOps webhook all point at that URL. Image lives in ECR (`461485115270.dkr.ecr.us-east-1.amazonaws.com/fe-copilot:latest`); deploy is `docker buildx build --platform linux/amd64`, push to ECR, then `aws ecs update-service --force-new-deployment` on `fe-copilot-50d3` in cluster `genesys-fargate-kibana-donotdelete`.
- **Salesforce live integration**: replace the SFDC mock with a real OAuth2 connection to a sandbox org. Map the existing six writes (Close Plan deal-qualification record, ContentNote, ContentDocumentLink, Competitor update, Deal_Health update, Slack post) to live calls. The mock surface stays as a fallback for offline demos. Estimated effort: 1 day for the OAuth flow, 1 day per object for field mapping.
- **Real Slack integration**: replace the Slack mock with a real workspace bot. Adds a `/fec` slash command so a FE can invoke the master agent without leaving Slack. Estimated effort: half a day for the bot scaffold, two days for the slash command role work.
- **FE Brain corpus expansion to 1000+ chunks**: add the Elastic Security detection rules repo, the EDOT (Elastic Distribution of OpenTelemetry) reference, the Cases workflow guide, and the Lens visualisation cookbook.
- **Thirteenth MCP tool: `fec_renewal_signals`**: scans deal-health and risk signals on an account and emits a retention play with talking points, owner, and Slack post. Builds on the live Renewal Defender workflow.
- **AutoOps-as-MCP-tool (`fec_autoops_signals`)**: promote the AutoOps webhook relay into a first-class MCP tool the master agent can call mid-conversation.
- **Customer 360 data source (`fec_c360_snapshot`)**: pull C360 account view data (subscriptions, consumption credits, support ticket trends, feature adoption) from Salesforce/Tableau into the pre-meeting brief.
- **Seismic BVR surfacing**: when the post-meeting agent detects a Race to Displace or GenAI deal, surface the matching Seismic Business Value Review template as a Slack link.

## Medium term (months 1 to 3)

- **Multi-tenant**: per-FE storage namespacing, per-FE Anthropic API key on the request, per-FE token quota. Same instance hosts an entire FE community.
- **Email digest before meetings**: a scheduled job reads the calendar and emails the FE a one-page brief 60 minutes before each customer call.
- **Active learning loop**: every Field Assistant response gets a thumbs-up/down; negative ratings feed a synthetic Q+A dataset that re-tunes the role prompts on a weekly cadence.
- **Voice input on Field Assistant**: browser Speech API for real-time dictation.
- **Slack bot front door**: same nine-tool master agent, accessible from any Slack channel via `@FECopilot`.
- **Custom branding per FE region**: logo upload, colour overrides, default language per region.

## Long term (months 3 to 6)

- **RAG over internal Elastic knowledge**: extend the FE Brain corpus to Confluence, Slack archives, recorded enablement videos transcribed with Whisper.
- **Customer-direct UX**: a sandboxed view where the customer can ask the master agent questions during a co-discovery session.
- **Salesforce CTI integration**: detect when a FE is on a customer call, auto-launch the live companion, auto-fill the post-meeting record from the call transcript.
- **More demo data scenarios**: search relevance regression, vector search quality decay, multi-tenant noisy neighbour, regional failover replay, identity provider migration.
- **Active monitoring of the FE Copilot itself**: `fec-audit` already feeds the self-observability dashboard. Add SLO burn alerts on token spend per FE, anomaly detection on tool failure rates, weekly cost reports per region.
- **Open-sourcing the role pack**: extract the role prompts into a separate repo so other companies can adapt them. Each role becomes a community-maintained YAML with versioning.

## Complementary tools, not duplicate work

Elastic already pays for excellent competitive intelligence platforms. The 33 battlecards shipped in this repo are scaffolding meant to demonstrate the FE flow, NOT a replacement for the curated research that lives elsewhere:

- **Seismic**: the current home for Elastic competitive content (battlecards, win wires, enablement decks).
- **Highspot / Showpad**: source of truth for sales collateral, certified pitch decks, and customer references.
- **Salesforce / Gainsight**: source of truth for account ownership, opportunity stage, and renewal signals.
- **Slack `#fe-help`, `#competitive`, regional FE channels**: live tribal knowledge.

The intended near-term integration story is for FE Copilot to read from these systems, not duplicate them. The master agent gets a `seismic_battlecard_lookup` MCP tool that pulls the current Seismic card for a given competitor at conversation time. The `fec_compare` role synthesises Seismic's facts plus Elastic's positioning into the response, with a citation back to the Seismic doc.
