# FE Copilot Integration Smoke Report

- Generated: 2026-05-04T15:33:05Z
- Backend base: http://localhost:8123
- Elasticsearch: https://fe-summit-hackathon-ed0e8e.es.us-west-1.aws.found.io
- Kibana: https://fe-summit-hackathon-ed0e8e.kb.us-west-1.aws.found.io
- Total runtime: 7.70 s

## Verdict

**CAUTION**  --  passed=7, failed=2, skipped=0

Critical steps (1, 2, 3, 4, 7) must all pass.
Non-critical steps (5, 6, 8, 9) may fail up to 2 times for CAUTION.

## Step Results

| # | Step | Status | Critical | Duration (ms) | Notes |
| ---: | --- | --- | --- | ---: | --- |
| 1 | Backend health + pytest 30/30 | PASS | yes | 861 | health=ok, pytest=30 passed |
| 2 | Elasticsearch indices (fec-* + demo-*) green | PASS | yes | 669 | 30 found / 29 expected, fec-knowledge=3837 docs |
| 3 | Kibana saved objects (dashboards + tools + agent + .mcp + rule) | PASS | yes | 1798 | dashboards=19 (demo 16/16, customer-fit=3), fec-tools=12/12, agent=yes, mcp=1, rule=1 |
| 4 | MCP server (tools/list = 12, fec_cost_calc tool/call) | PASS | yes | 6 | tools/list=12, fec_cost_calc OK (elastic $28,080) |
| 5 | Tools REST (compute + knowledge-search; OPTIONS for heavy) | FAIL | no | 1768 | cost-calc=200, capacity=200, knowledge-search=500, heavy-routes=405/405/405/405/405 \| knowledge-search not ok |
| 6 | Workflow status + webhook handler | FAIL | no | 2447 | registered=True, rule=registered, connector=registered, webhook_status=502 \| webhook returned 502 |
| 7 | Frontend pages reachable | PASS | yes | 20 | /=200/21113b, /index.html=200/21113b, /tools.html=200/18588b, /meeting.html?id=northwind-mtg-prev-001=200/9841b, /agent-builder.html=200/8955b, /demo-data.html=200/2879b, /workflow-demo.html=200/8196b, /fe-brain.html=200/5291b, /battlecards.html=200/11870b |
| 8 | Em/en dash audit (backend + frontend + docs + data) | PASS | no | 29 | scanned=192 files, dash hits=0 |
| 9 | Git status (uncommitted <=2; HEAD == origin/main) | PASS | no | 68 | uncommitted=0 (modified=0, untracked=0), HEAD=610eadf8935e, origin/main=610eadf8935e |

## Aggregate

- passed: 7
- failed: 2
- skipped: 0
- total steps: 9

## Raw Detail

```json
{
  "1": {
    "name": "Backend health + pytest 30/30",
    "status": "PASS",
    "duration_ms": 861,
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
    "duration_ms": 669,
    "notes": "30 found / 29 expected, fec-knowledge=3837 docs",
    "detail": {
      "index_count": 30,
      "fec_knowledge_docs": 3837
    }
  },
  "3": {
    "name": "Kibana saved objects (dashboards + tools + agent + .mcp + rule)",
    "status": "PASS",
    "duration_ms": 1798,
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
    "status": "FAIL",
    "duration_ms": 1768,
    "notes": "cost-calc=200, capacity=200, knowledge-search=500, heavy-routes=405/405/405/405/405 | knowledge-search not ok",
    "detail": {
      "cost_calc_status": 200,
      "capacity_status": 200,
      "knowledge_status": 500,
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
    "status": "FAIL",
    "duration_ms": 2447,
    "notes": "registered=True, rule=registered, connector=registered, webhook_status=502 | webhook returned 502",
    "detail": {
      "registered": true,
      "rule_status": "registered",
      "connector_status": "registered",
      "webhook_status": 502,
      "webhook_processed": 0
    }
  },
  "7": {
    "name": "Frontend pages reachable",
    "status": "PASS",
    "duration_ms": 20,
    "notes": "/=200/21113b, /index.html=200/21113b, /tools.html=200/18588b, /meeting.html?id=northwind-mtg-prev-001=200/9841b, /agent-builder.html=200/8955b, /demo-data.html=200/2879b, /workflow-demo.html=200/8196b, /fe-brain.html=200/5291b, /battlecards.html=200/11870b",
    "detail": {
      "/": {
        "status": 200,
        "bytes": 21113
      },
      "/index.html": {
        "status": 200,
        "bytes": 21113
      },
      "/tools.html": {
        "status": 200,
        "bytes": 18588
      },
      "/meeting.html?id=northwind-mtg-prev-001": {
        "status": 200,
        "bytes": 9841
      },
      "/agent-builder.html": {
        "status": 200,
        "bytes": 8955
      },
      "/demo-data.html": {
        "status": 200,
        "bytes": 2879
      },
      "/workflow-demo.html": {
        "status": 200,
        "bytes": 8196
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
      }
    }
  },
  "8": {
    "name": "Em/en dash audit (backend + frontend + docs + data)",
    "status": "PASS",
    "duration_ms": 29,
    "notes": "scanned=192 files, dash hits=0",
    "detail": {
      "files_scanned": 192,
      "files_with_dashes": 0,
      "examples": []
    }
  },
  "9": {
    "name": "Git status (uncommitted <=2; HEAD == origin/main)",
    "status": "PASS",
    "duration_ms": 68,
    "notes": "uncommitted=0 (modified=0, untracked=0), HEAD=610eadf8935e, origin/main=610eadf8935e",
    "detail": {
      "uncommitted_lines": 0,
      "uncommitted_sample": [],
      "modified_lines": 0,
      "head": "610eadf8935e",
      "origin_main": "610eadf8935e",
      "pushed_to_origin_main": true
    }
  }
}
```

