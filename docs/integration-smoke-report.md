# FE Copilot Integration Smoke Report

- Generated: 2026-05-05T08:48:24Z
- Backend base: http://localhost:8123
- Elasticsearch: https://fe-summit-hackathon-ed0e8e.es.us-west-1.aws.found.io
- Kibana: https://fe-summit-hackathon-ed0e8e.kb.us-west-1.aws.found.io
- Total runtime: 19.56 s

## Verdict

**CAUTION**  --  passed=8, failed=1, skipped=0

Critical steps (1, 2, 3, 4, 7) must all pass.
Non-critical steps (5, 6, 8, 9) may fail up to 2 times for CAUTION.

## Step Results

| # | Step | Status | Critical | Duration (ms) | Notes |
| ---: | --- | --- | --- | ---: | --- |
| 1 | Backend health + pytest 30/30 | PASS | yes | 4900 | health=ok, pytest=30 passed |
| 2 | Elasticsearch indices (fec-* + demo-*) green | PASS | yes | 570 | 32 found / 29 expected, fec-knowledge=3837 docs |
| 3 | Kibana saved objects (dashboards + tools + agent + .mcp + rule) | PASS | yes | 1609 | dashboards=19 (demo 16/16, customer-fit=3), fec-tools=12/12, agent=yes, mcp=1, rule=1 |
| 4 | MCP server (tools/list = 12, fec_cost_calc tool/call) | PASS | yes | 4750 | tools/list=12, fec_cost_calc OK (elastic $28,080) |
| 5 | Tools REST (compute + knowledge-search; OPTIONS for heavy) | PASS | no | 2346 | cost-calc=200, capacity=200, knowledge-search=200, heavy-routes=405/405/405/405/405 |
| 6 | Workflow status + webhook handler | PASS | no | 2858 | registered=True, rule=registered, connector=registered, webhook_status=200 |
| 7 | Frontend pages reachable | PASS | yes | 2398 | /=200/23854b, /index.html=200/23854b, /tools.html=200/22734b, /meeting.html?id=northwind-mtg-prev-001=200/10389b, /agent-builder.html=200/9196b, /demo-data.html=200/2988b, /workflow-demo.html=200/11525b, /fe-brain.html=200/5587b, /battlecards.html=200/11985b |
| 8 | Em/en dash audit (backend + frontend + docs + data) | PASS | no | 47 | scanned=220 files, dash hits=0 |
| 9 | Git status (uncommitted <=2; HEAD == origin/main) | FAIL | no | 53 | uncommitted=39 (modified=33, untracked=6), HEAD=d5ca3a79f1ec, origin/main=d5ca3a79f1ec \| 33 modified files (>2) |

## Aggregate

- passed: 8
- failed: 1
- skipped: 0
- total steps: 9

## Raw Detail

```json
{
  "1": {
    "name": "Backend health + pytest 30/30",
    "status": "PASS",
    "duration_ms": 4900,
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
    "duration_ms": 570,
    "notes": "32 found / 29 expected, fec-knowledge=3837 docs",
    "detail": {
      "index_count": 32,
      "fec_knowledge_docs": 3837
    }
  },
  "3": {
    "name": "Kibana saved objects (dashboards + tools + agent + .mcp + rule)",
    "status": "PASS",
    "duration_ms": 1609,
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
    "duration_ms": 4750,
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
    "duration_ms": 2346,
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
    "duration_ms": 2858,
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
    "duration_ms": 2398,
    "notes": "/=200/23854b, /index.html=200/23854b, /tools.html=200/22734b, /meeting.html?id=northwind-mtg-prev-001=200/10389b, /agent-builder.html=200/9196b, /demo-data.html=200/2988b, /workflow-demo.html=200/11525b, /fe-brain.html=200/5587b, /battlecards.html=200/11985b",
    "detail": {
      "/": {
        "status": 200,
        "bytes": 23854
      },
      "/index.html": {
        "status": 200,
        "bytes": 23854
      },
      "/tools.html": {
        "status": 200,
        "bytes": 22734
      },
      "/meeting.html?id=northwind-mtg-prev-001": {
        "status": 200,
        "bytes": 10389
      },
      "/agent-builder.html": {
        "status": 200,
        "bytes": 9196
      },
      "/demo-data.html": {
        "status": 200,
        "bytes": 2988
      },
      "/workflow-demo.html": {
        "status": 200,
        "bytes": 11525
      },
      "/fe-brain.html": {
        "status": 200,
        "bytes": 5587
      },
      "/battlecards.html": {
        "status": 200,
        "bytes": 11985
      },
      "/health.html": {
        "status": 200,
        "bytes": 13596
      },
      "/industries.html": {
        "status": 200,
        "bytes": 7329
      },
      "/quick-research.html": {
        "status": 200,
        "bytes": 8687
      },
      "/customers.html": {
        "status": 200,
        "bytes": 19931
      }
    }
  },
  "8": {
    "name": "Em/en dash audit (backend + frontend + docs + data)",
    "status": "PASS",
    "duration_ms": 47,
    "notes": "scanned=220 files, dash hits=0",
    "detail": {
      "files_scanned": 220,
      "files_with_dashes": 0,
      "examples": []
    }
  },
  "9": {
    "name": "Git status (uncommitted <=2; HEAD == origin/main)",
    "status": "FAIL",
    "duration_ms": 53,
    "notes": "uncommitted=39 (modified=33, untracked=6), HEAD=d5ca3a79f1ec, origin/main=d5ca3a79f1ec | 33 modified files (>2)",
    "detail": {
      "uncommitted_lines": 39,
      "uncommitted_sample": [
        " M backend/app/api/routes_briefs.py",
        " M backend/app/main.py",
        " M docs/integration-smoke-report.md",
        " M frontend/agent-builder.html",
        " M frontend/assets/js/agent-builder-mini.js"
      ],
      "modified_lines": 33,
      "head": "d5ca3a79f1ec",
      "origin_main": "d5ca3a79f1ec",
      "pushed_to_origin_main": true
    }
  }
}
```

