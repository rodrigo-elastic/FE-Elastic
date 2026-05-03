# FE Copilot - Compliance and Deployment Notes

**Goal:** show how this hackathon prototype maps to a production deployment inside Elastic and how it would extrapolate to a customer's environment without rebuilding the agent chain.

## Data flow (what crosses the boundary)

```
[FE input / synthetic fixture] -> [FE Copilot backend] -> [Anthropic API]
                                          |
                                          +--> [Slack mock]
                                          +--> [Salesforce mock]
                                          +--> [runtime/audit.jsonl]
                                          +--> [runtime/briefs/*.json + PDF/HTML]
                                          +--> [runtime/post_meeting/*.json]
                                          +--> [runtime/emails/*.json]
```

What leaves the host:

- The system prompt for the active agent (frozen, Elastic-controlled).
- The user dossier or transcript (from synthetic fixtures or, for Quick Research, only what the FE typed).
- Nothing else. No environment variables, no other meetings, no audit log.

What stays on the host (for traceability):

- `runtime/audit.jsonl`: append-only record of every Claude call (timestamp, model, agent, meeting_id, token usage, mode).
- Generated artifacts (briefs, PDFs, post-meeting JSON, follow-up email drafts).
- Slack and Salesforce mock log files.

## Audit surface

- File: `runtime/audit.jsonl` (append-only JSON Lines).
- API: `GET /api/v1/audit?limit=N` returns the latest N entries plus aggregate token totals.
- UI: footer of the dashboard shows running totals (calls, input tokens, output tokens) and links to the JSON endpoint.
- Each entry carries: `ts`, `model`, `mode` (`live` or `mock`), `input_tokens`, `output_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`, plus caller-supplied `audit_meta` (agent name, meeting_id, company_id, ad-hoc flag).

This is enough to satisfy a basic compliance ask: "show me every model call this system has made in the last hour." For SOC 2 / ISO 27001 the file would be shipped to a SIEM (the same Elasticsearch cluster used elsewhere in the demo), but the local file already gives the audit primitive.

## Per-agent model pinning

`MODEL_PRE_MEETING`, `MODEL_POST_MEETING`, `MODEL_LIVE_MEETING` env vars override the global `MODEL_DEFAULT`. Compliance teams that have approved only specific Claude versions can pin each agent independently without touching code. The default is `claude-haiku-4-5` (cheapest tier).

## Deployment paths

### A. Local / single FE

The current setup. One uvicorn process, JSON files under `runtime/`. Useful for local trials and the hackathon demo.

### B. Elastic-hosted (Anthropic via approved gateway)

Recommended for an internal pilot.

- The agent chain runs inside Elastic Cloud (or an internal Kubernetes cluster).
- Anthropic calls go through the Elastic-approved AI gateway. `claude_client.py` already accepts an `Anthropic` SDK client at construction time; pointing it at a gateway URL is one line in `app/integrations/claude_client.py` (use `Anthropic(base_url=...)` per the SDK).
- Audit log ships to the same Elasticsearch cluster as a daily index (`fec-audit-YYYY-MM-DD`). The structured JSONL lines map 1:1 to ES documents.
- Synthetic data is replaced by a real ES index (`companies`, `meetings`, `transcripts`, etc.). The repository abstraction (`app/repositories/synthetic.py`) has a clear interface a real `elasticsearch_repo.py` can implement; the agents do not need to change.
- Slack and Salesforce mocks are swapped for the real clients in `app/integrations/`. The function signatures already match Slack Web API and SFDC REST shapes.

### C. Customer-environment extrapolation

For a customer that wants to run the same chain on their own data and inside their own boundary:

1. Drop in their own `synthetic.py` replacement that points at their CRM and observability data.
2. Configure their preferred model gateway (OpenAI-compatible, Bedrock, Vertex). The Anthropic SDK supports custom `base_url`; or, replace `claude_client.py` with a thin equivalent.
3. Audit log stays inside the customer's environment.

Because every cross-boundary call goes through `ClaudeService.call_structured` (a single function), and every external integration is a `*_mock.py` swap point, extending to a real customer is a configuration exercise, not a refactor.

## PII handling (out of scope, documented for the next phase)

Today, all input data is synthetic. The boundaries to harden when that changes:

1. **Pre-Meeting input**: news, tickets, transcripts may contain PII. Add a redaction pre-processor in `app/agents/pre_meeting.py` before `prompt.render_user_prompt`.
2. **Post-Meeting input**: same. Redact speaker emails and customer-supplied figures unless explicitly opted in.
3. **Audit log**: do not store raw prompts or responses, only metadata. The current implementation already does this (only token counts and IDs).
4. **Quick Research**: only the user-typed fields are sent. Add a length cap (already in place via Pydantic validators) and a basic email/phone redactor before submission.

## Compliance posture summary

| Concern | Status |
|---|---|
| What leaves the boundary | Documented and minimal; only the rendered prompt and the user dossier. |
| Audit log | Implemented (append-only JSONL + API + dashboard footer). |
| Approved-model pinning | Implemented (per-agent env var override). |
| PII redaction | Not implemented. Synthetic data only today; clear hook documented for the next phase. |
| Deployment story | Documented: local, Elastic-hosted via gateway, or customer-environment via integration swap. |
| Boundary auditability | Single choke point (`ClaudeService.call_structured`); easy to instrument or gate. |
