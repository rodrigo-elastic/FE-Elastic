# Project layout

```
FE-Elastic/
  backend/                Python 3.11 FastAPI app
    app/
      agents/             pre / live / post agents + frozen prompts (pre_meeting.py enforces the
                          AutoOps-vs-Splunk talking point) + JSON schemas + offline mocks
      api/                26 routers: agents, tools, briefs, meetings, calendar, salesforce,
                          audit, demo-data, kibana, mcp, agent-builder, workflows,
                          workflow-settings (per-rule email toggle), battlecards,
                          health, autoops, qbr, tar, weekly-slides, handover,
                          industries, notifications, stats, customer-health
      integrations/       Anthropic + ES clients; Kibana inference connector with strict guard
                          (claude_client.py: get_elastic_service + call_structured(strict=True));
                          Slack/Calendar/SFDC mocks; SEC EDGAR HTTP; Agent Builder;
                          email_sender (Kibana .email connector + SMTP + disk fallback)
      repositories/       Read-only access over synthetic JSON fixtures (cached)
      services/           PDF builder, PPTX builder, transcript parser, email drafter,
                          company resolver, renewal_defender, scenarios (8 flagships +
                          industry_factory for 20 per-industry scenarios),
                          battlecard_skill_builder
      models/             Pydantic domain models
    data/                 autoops_events.json (pre-seeded AutoOps events)
    data/seed/            battlecards.json (33), renewal_signals.json, ES mappings
    data/synthetic/       companies.json (3 fictional accounts), generated fixtures (gitignored)
    scripts/              generate_synthetic_data.py, seed_elasticsearch.py,
                          sync_agent_builder.py, sync_battlecard_agents.py,
                          sync_audit_dashboard.py, run_pipeline.py, scenario seeders
    tests/                30 tests, all passing in mock mode
  frontend/               Static HTML pages + assets (no build step, 5 languages)
    assets/js/            tools-rail.js, i18n.js, autoops-widget.js (Brief-tab AutoOps panel),
                          tar-widget.js (Brief-tab TAR panel), presales-playbook.js,
                          customer-health.js, battlecard-chat.js, agent-builder-tools.js,
                          qbr.js, weekly-slides.js
  data/seed/              industries.json (20 industries), industry_templates.json
  infra/                  docker-compose.yml + Dockerfile.backend
  docs/                   architecture.md + the long-form sections (why_we_win.md,
                          how_it_works.md, feature_tour.md, personas.md, roadmap.md,
                          built_with.md, battlecard_skills_template.md, talk-tracks.md,
                          deploy.md, supervisor.md, screenshots/, gifs/)
  Dockerfile              Production image, deployed to AWS ECS Fargate
  runtime/                Slack/SFDC logs, audit.jsonl, generated PDFs, email drafts,
                          slides/, qbr/, tar/, pov_health/ (gitignored)
  LICENSE                 MIT
```
