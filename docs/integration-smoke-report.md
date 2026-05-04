# FE Copilot Integration Smoke Report

- Generated: 2026-05-04T21:51:23Z
- Backend base: http://localhost:8123
- Elasticsearch: https://fe-summit-hackathon-ed0e8e.es.us-west-1.aws.found.io
- Kibana: https://fe-summit-hackathon-ed0e8e.kb.us-west-1.aws.found.io
- Total runtime: 8.13 s

## Verdict

**GO**  --  passed=9, failed=0, skipped=0

Critical steps (1, 2, 3, 4, 7) must all pass.
Non-critical steps (5, 6, 8, 9) may fail up to 2 times for CAUTION.

## Step Results

| # | Step | Status | Critical | Duration (ms) | Notes |
| ---: | --- | --- | --- | ---: | --- |
| 1 | Backend health + pytest 30/30 | PASS | yes | 815 | health=ok, pytest=30 passed |
| 2 | Elasticsearch indices (fec-* + demo-*) green | PASS | yes | 604 | 32 found / 29 expected, fec-knowledge=3837 docs |
| 3 | Kibana saved objects (dashboards + tools + agent + .mcp + rule) | PASS | yes | 1823 | dashboards=19 (demo 16/16, customer-fit=3), fec-tools=12/12, agent=yes, mcp=1, rule=1 |
| 4 | MCP server (tools/list = 12, fec_cost_calc tool/call) | PASS | yes | 6 | tools/list=12, fec_cost_calc OK (elastic $28,080) |
| 5 | Tools REST (compute + knowledge-search; OPTIONS for heavy) | PASS | no | 2617 | cost-calc=200, capacity=200, knowledge-search=200, heavy-routes=405/405/405/405/405 |
| 6 | Workflow status + webhook handler | PASS | no | 2129 | registered=True, rule=registered, connector=registered, webhook_status=200 |
| 7 | Frontend pages reachable | PASS | yes | 19 | /=200/23231b, /index.html=200/23231b, /tools.html=200/22438b, /meeting.html?id=northwind-mtg-prev-001=200/9841b, /agent-builder.html=200/9087b, /demo-data.html=200/2879b, /workflow-demo.html=200/10356b, /fe-brain.html=200/5291b, /battlecards.html=200/11870b |
| 8 | Em/en dash audit (backend + frontend + docs + data) | PASS | no | 26 | scanned=204 files, dash hits=0 |
| 9 | Git status (uncommitted <=2; HEAD == origin/main) | PASS | no | 56 | uncommitted=2 (modified=2, untracked=0), HEAD=4fa37d2e53b8, origin/main=4fa37d2e53b8 |

## Aggregate

- passed: 9
- failed: 0
- skipped: 0
- total steps: 9

## Raw Detail

```json
{
  "1": {
    "name": "Backend health + pytest 30/30",
    "status": "PASS",
    "duration_ms": 815,
    "notes": "health=ok, pytest=30 passed",
    "detail": {
      "health_status": 200,
      "pytest_returncode": 0,
      "pytest_passed": 30,
      "pytest_failed": 0,
      "pytest_errors": 0
    }
  },
  "2": {
    "name": "Elasticsearch indices (fec-* + demo-*) green",
    "status": "PASS",
    "duration_ms": 604,
    "notes": "32 found / 29 expected, fec-knowledge=3837 docs",
    "detail": {
      "index_count": 32,
      "fec_knowledge_docs": 3837
    }
  },
  "3": {
    "name": "Kibana saved objects (dashboards + tools + agent + .mcp + rule)",
    "status": "PASS",
    "duration_ms": 1823,
    "notes": "dashboards=19 (demo 16/16, customer-fit=3), fec-tools=12/12, agent=yes, mcp=1, rule=1",
    "detail": {
      "dashboard_total": 19,
      "customer_fit_dashboards": 3,
      "agent_builder_tools_total": 24,
      "fec_tools_present": 12,
      "agents": [
        "elastic-ai-agent",
        "fec_field_assistant",
        "fec_user_migration_specialist",
        "fec_user_compliance_pursuit",
        "fec_user_rfp_responder"
      ],
      "mcp_connectors": 1,
      "mcp_server_url": "https://headlamp-squatting-usable.ngrok-free.dev/api/v1/mcp",
      "alerting_rules": 1
    }
  },
  "4": {
    "name": "MCP server (tools/list = 12, fec_cost_calc tool/call)",
    "status": "PASS",
    "duration_ms": 6,
    "notes": "tools/list=12, fec_cost_calc OK (elastic $28,080)",
    "detail": {
      "tool_count": 12,
      "tools": [
        "fec_poc_plan",
        "fec_spl_to_esql",
        "fec_compliance",
        "fec_stack_extract",
        "fec_code_sample",
        "fec_cost_calc",
        "fec_capacity",
        "fec_knowledge_search",
        "fec_troubleshoot",
        "fec_compare",
        "fec_orchestrator",
        "fec_proposal"
      ],
      "cost_calc_isError": false,
      "cost_calc_has_elastic": true,
      "cost_calc_has_splunk": true
    }
  },
  "5": {
    "name": "Tools REST (compute + knowledge-search; OPTIONS for heavy)",
    "status": "PASS",
    "duration_ms": 2617,
    "notes": "cost-calc=200, capacity=200, knowledge-search=200, heavy-routes=405/405/405/405/405",
    "detail": {
      "cost_calc_status": 200,
      "capacity_status": 200,
      "knowledge_status": 200,
      "knowledge_answer_len": 237,
      "knowledge_citations": 0,
      "heavy_route_status": {
        "/tools/compliance-mapping": 405,
        "/tools/code-sample": 405,
        "/tools/troubleshoot": 405,
        "/tools/stack-extract": 405,
        "/tools/poc-plan/__no_such_meeting__": 405
      }
    }
  },
  "6": {
    "name": "Workflow status + webhook handler",
    "status": "PASS",
    "duration_ms": 2129,
    "notes": "registered=True, rule=registered, connector=registered, webhook_status=200",
    "detail": {
      "registered": true,
      "rule_status": "registered",
      "connector_status": "registered",
      "webhook_status": 200,
      "webhook_processed": 0
    }
  },
  "7": {
    "name": "Frontend pages reachable",
    "status": "PASS",
    "duration_ms": 19,
    "notes": "/=200/23231b, /index.html=200/23231b, /tools.html=200/22438b, /meeting.html?id=northwind-mtg-prev-001=200/9841b, /agent-builder.html=200/9087b, /demo-data.html=200/2879b, /workflow-demo.html=200/10356b, /fe-brain.html=200/5291b, /battlecards.html=200/11870b",
    "detail": {
      "/": {
        "status": 200,
        "bytes": 23231
      },
      "/index.html": {
        "status": 200,
        "bytes": 23231
      },
      "/tools.html": {
        "status": 200,
        "bytes": 22438
      },
      "/meeting.html?id=northwind-mtg-prev-001": {
        "status": 200,
        "bytes": 9841
      },
      "/agent-builder.html": {
        "status": 200,
        "bytes": 9087
      },
      "/demo-data.html": {
        "status": 200,
        "bytes": 2879
      },
      "/workflow-demo.html": {
        "status": 200,
        "bytes": 10356
      },
      "/fe-brain.html": {
        "status": 200,
        "bytes": 5291
      },
      "/battlecards.html": {
        "status": 200,
        "bytes": 11870
      },
      "/health.html": {
        "status": 200,
        "bytes": 13300
      },
      "/industries.html": {
        "status": 200,
        "bytes": 6930
      },
      "/quick-research.html": {
        "status": 200,
        "bytes": 14807
      },
      "/customers.html": {
        "status": 200,
        "bytes": 11233
      }
    }
  },
  "8": {
    "name": "Em/en dash audit (backend + frontend + docs + data)",
    "status": "PASS",
    "duration_ms": 26,
    "notes": "scanned=204 files, dash hits=0",
    "detail": {
      "files_scanned": 204,
      "files_with_dashes": 0,
      "examples": []
    }
  },
  "9": {
    "name": "Git status (uncommitted <=2; HEAD == origin/main)",
    "status": "PASS",
    "duration_ms": 56,
    "notes": "uncommitted=2 (modified=2, untracked=0), HEAD=4fa37d2e53b8, origin/main=4fa37d2e53b8",
    "detail": {
      "uncommitted_lines": 2,
      "uncommitted_sample": [
        " M docs/integration-smoke-report.md",
        " M frontend/assets/js/quick-research-filter.js"
      ],
      "modified_lines": 2,
      "head": "4fa37d2e53b8",
      "origin_main": "4fa37d2e53b8",
      "pushed_to_origin_main": true
    }
  }
}
```

