# FE Copilot Integration Smoke Report

- Generated: 2026-05-05T10:51:12Z
- Backend base: http://localhost:8123
- Elasticsearch: https://fe-summit-hackathon-ed0e8e.es.us-west-1.aws.found.io
- Kibana: https://fe-summit-hackathon-ed0e8e.kb.us-west-1.aws.found.io
- Total runtime: 8.03 s

## Verdict

**CAUTION**  --  passed=8, failed=1, skipped=0

Critical steps (1, 2, 3, 4, 7) must all pass.
Non-critical steps (5, 6, 8, 9) may fail up to 2 times for CAUTION.

## Step Results

| # | Step | Status | Critical | Duration (ms) | Notes |
| ---: | --- | --- | --- | ---: | --- |
| 1 | Backend health + pytest 30/30 | PASS | yes | 915 | health=ok, pytest=30 passed |
| 2 | Elasticsearch indices (fec-* + demo-*) green | PASS | yes | 645 | 32 found / 29 expected, fec-knowledge=3837 docs |
| 3 | Kibana saved objects (dashboards + tools + agent + .mcp + rule) | PASS | yes | 1856 | dashboards=20 (demo 16/16, customer-fit=4), fec-tools=12/12, agent=yes, mcp=1, rule=1 |
| 4 | MCP server (tools/list = 12, fec_cost_calc tool/call) | PASS | yes | 6 | tools/list=12, fec_cost_calc OK (elastic $28,080) |
| 5 | Tools REST (compute + knowledge-search; OPTIONS for heavy) | PASS | no | 2318 | cost-calc=200, capacity=200, knowledge-search=200, heavy-routes=405/405/405/405/405 |
| 6 | Workflow status + webhook handler | PASS | no | 2134 | registered=True, rule=registered, connector=registered, webhook_status=200 |
| 7 | Frontend pages reachable | PASS | yes | 19 | /=200/25756b, /index.html=200/25756b, /tools.html=200/24212b, /meeting.html?id=northwind-mtg-prev-001=200/12618b, /agent-builder.html=200/10642b, /demo-data.html=200/4385b, /workflow-demo.html=200/12953b, /fe-brain.html=200/7007b, /battlecards.html=200/13435b |
| 8 | Em/en dash audit (backend + frontend + docs + data) | PASS | no | 29 | scanned=232 files, dash hits=0 |
| 9 | Git status (uncommitted <=2; HEAD == origin/main) | FAIL | no | 75 | uncommitted=4 (modified=4, untracked=0), HEAD=40e32e0c5df6, origin/main=40e32e0c5df6 \| 4 modified files (>2) |

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
    "duration_ms": 915,
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
    "duration_ms": 645,
    "notes": "32 found / 29 expected, fec-knowledge=3837 docs",
    "detail": {
      "index_count": 32,
      "fec_knowledge_docs": 3837
    }
  },
  "3": {
    "name": "Kibana saved objects (dashboards + tools + agent + .mcp + rule)",
    "status": "PASS",
    "duration_ms": 1856,
    "notes": "dashboards=20 (demo 16/16, customer-fit=4), fec-tools=12/12, agent=yes, mcp=1, rule=1",
    "detail": {
      "dashboard_total": 20,
      "customer_fit_dashboards": 4,
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
    "duration_ms": 2318,
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
    "duration_ms": 2134,
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
    "notes": "/=200/25756b, /index.html=200/25756b, /tools.html=200/24212b, /meeting.html?id=northwind-mtg-prev-001=200/12618b, /agent-builder.html=200/10642b, /demo-data.html=200/4385b, /workflow-demo.html=200/12953b, /fe-brain.html=200/7007b, /battlecards.html=200/13435b",
    "detail": {
      "/": {
        "status": 200,
        "bytes": 25756
      },
      "/index.html": {
        "status": 200,
        "bytes": 25756
      },
      "/tools.html": {
        "status": 200,
        "bytes": 24212
      },
      "/meeting.html?id=northwind-mtg-prev-001": {
        "status": 200,
        "bytes": 12618
      },
      "/agent-builder.html": {
        "status": 200,
        "bytes": 10642
      },
      "/demo-data.html": {
        "status": 200,
        "bytes": 4385
      },
      "/workflow-demo.html": {
        "status": 200,
        "bytes": 12953
      },
      "/fe-brain.html": {
        "status": 200,
        "bytes": 7007
      },
      "/battlecards.html": {
        "status": 200,
        "bytes": 13435
      },
      "/health.html": {
        "status": 200,
        "bytes": 15028
      },
      "/industries.html": {
        "status": 200,
        "bytes": 9120
      },
      "/quick-research.html": {
        "status": 200,
        "bytes": 10464
      },
      "/customers.html": {
        "status": 200,
        "bytes": 22279
      }
    }
  },
  "8": {
    "name": "Em/en dash audit (backend + frontend + docs + data)",
    "status": "PASS",
    "duration_ms": 29,
    "notes": "scanned=232 files, dash hits=0",
    "detail": {
      "files_scanned": 232,
      "files_with_dashes": 0,
      "examples": []
    }
  },
  "9": {
    "name": "Git status (uncommitted <=2; HEAD == origin/main)",
    "status": "FAIL",
    "duration_ms": 75,
    "notes": "uncommitted=4 (modified=4, untracked=0), HEAD=40e32e0c5df6, origin/main=40e32e0c5df6 | 4 modified files (>2)",
    "detail": {
      "uncommitted_lines": 4,
      "uncommitted_sample": [
        " M docs/integration-smoke-report.md",
        " M frontend/assets/css/styles.css",
        " M frontend/assets/js/quick-research-filter.js",
        " M frontend/meeting.html"
      ],
      "modified_lines": 4,
      "head": "40e32e0c5df6",
      "origin_main": "40e32e0c5df6",
      "pushed_to_origin_main": true
    }
  }
}
```

