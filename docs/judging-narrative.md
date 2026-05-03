# Judging Narrative

How FE Copilot maps to the FY27 SKO FE Summit Hackathon criteria.

## FE Impact

Quantified time savings per FE per week:

- Pre-meeting research: 30 to 45 minutes saved per customer call.
- Post-meeting follow-through: 20 to 30 minutes saved (action items, SFDC entry, email draft).
- Live whisper: catches at least one competitor or MEDDPICC signal per discovery call that the FE would miss while focused on rapport.

End-to-end coverage of the meeting workflow (research, live signals, follow-up) means the FE can run more accounts at the same quality bar.

## Use of Workflows + Agent Builder

Three discrete agents, chained, each modeled as a Workflow:

1. **Pre-Meeting Researcher** (Opus 4.7 + adaptive thinking + effort:high): triggered on calendar event 1 hour before the meeting.
2. **Live Meeting Companion** (Haiku 4.5): per-turn webhook from the transcript stream.
3. **Post-Meeting Action Engine** (Opus 4.7 + adaptive thinking + effort:high): triggered on transcript completion.

Structured outputs are forced via `output_config.format` with explicit JSON schemas, so each step's output plugs cleanly into the next workflow node without parsing brittleness. Prompt caching keeps the per-call cost low across many accounts.

## Polish & Usability

- Single-page dashboard, no framework, no build step.
- Polished PDF brief (WeasyPrint), with HTML fallback so demos never hard-fail.
- Mock mode lets the demo run offline if the network is flaky at the venue.
- All mocked integrations (Slack, Salesforce, Calendar) leave file artifacts the FE can show on screen.

## Reusability

- Synthetic data generator and the three-agent chain are portable to any new FE account: swap the synthetic fixtures and the same workflows fire.
- Mock integrations encapsulate the boundary; switching to real Slack and Salesforce is a one-file change per integration.
- The repository abstraction (`app.repositories.synthetic`) makes it trivial to swap to Elasticsearch as the source of truth.

## Demo Quality

- Scripted 3 minute walkthrough.
- Deterministic synthetic data anchored to `NOW = 2026-05-02 09:00 UTC` so the same demo plays every time.
- Three discrete narratives (Acme: consolidation; Globex: regulated finance; Initech: cross-sell), so judges can ask for any of the three.
- All run locally with `docker compose` plus `uvicorn`.
