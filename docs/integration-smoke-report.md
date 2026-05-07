# FE Copilot Integration Smoke Report

- Generated: 2026-05-05T12:56:33Z
- Backend base: http://localhost:8123
- Elasticsearch: (none)
- Kibana: (none)
- Total runtime: 6.39 s

## Verdict

**CAUTION**  --  passed=6, failed=1, skipped=2

Critical steps (1, 2, 3, 4, 7) must all pass.
Non-critical steps (5, 6, 8, 9) may fail up to 2 times for CAUTION.

## Step Results

| # | Step | Status | Critical | Duration (ms) | Notes |
| ---: | --- | --- | --- | ---: | --- |
| 1 | Backend health + pytest 30/30 | PASS | yes | 1091 | health=ok, pytest=30 passed |
| 2 | Elasticsearch indices (fec-* + demo-*) green | SKIP | yes | 0 | ELASTICSEARCH_URL or ELASTICSEARCH_API_KEY missing |
| 3 | Kibana saved objects (dashboards + tools + agent + .mcp + rule) | SKIP | yes | 0 | KIBANA_URL or KIBANA_API_KEY missing |
| 4 | MCP server (tools/list = 14, fec_cost_calc tool/call) | PASS | yes | 2 | tools/list=14, fec_cost_calc OK (elastic $28,080) |
| 5 | Tools REST (compute + knowledge-search; OPTIONS for heavy) | PASS | no | 2906 | cost-calc=200, capacity=200, knowledge-search=200, heavy-routes=405/405/405/405/405 |
| 6 | Workflow status + webhook handler | PASS | no | 2223 | registered=True, rule=registered, connector=registered, webhook_status=200 |
| 7 | Frontend pages reachable | PASS | yes | 29 | /=200/26406b, /index.html=200/26406b, /tools.html=200/28709b, /meeting.html?id=northwind-mtg-prev-001=200/12618b, /agent-builder.html=200/10642b, /demo-data.html=200/4385b, /workflow-demo.html=200/12953b, /fe-brain.html=200/7007b, /battlecards.html=200/13435b |
| 8 | Em/en dash audit (backend + frontend + docs + data) | PASS | no | 46 | scanned=240 files, dash hits=0 |
| 9 | Git status (uncommitted <=2; HEAD == origin/main) | FAIL | no | 48 | uncommitted=1 (modified=1, untracked=0), HEAD=2dd09754875b, origin/main=e0fdd9fa6c39 \| HEAD != origin/main |

## Aggregate

- passed: 6
- failed: 1
- skipped: 2
- total steps: 9

## Raw Detail

```json
{
  "1": {
    "name": "Backend health + pytest 30/30",
    "status": "PASS",
    "duration_ms": 1091,
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
    "status": "SKIP",
    "duration_ms": 0,
    "notes": "ELASTICSEARCH_URL or ELASTICSEARCH_API_KEY missing",
    "detail": {}
  },
  "3": {
    "name": "Kibana saved objects (dashboards + tools + agent + .mcp + rule)",
    "status": "SKIP",
    "duration_ms": 0,
    "notes": "KIBANA_URL or KIBANA_API_KEY missing",
    "detail": {}
  },
  "4": {
    "name": "MCP server (tools/list = 14, fec_cost_calc tool/call)",
    "status": "PASS",
    "duration_ms": 2,
    "notes": "tools/list=14, fec_cost_calc OK (elastic $28,080)",
    "detail": {
      "tool_count": 14,
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
        "fec_proposal",
        "fec_deploy_validator",
        "fec_pov_health"
      ],
      "cost_calc_isError": false,
      "cost_calc_has_elastic": true,
      "cost_calc_has_splunk": true
    }
  },
  "5": {
    "name": "Tools REST (compute + knowledge-search; OPTIONS for heavy)",
    "status": "PASS",
    "duration_ms": 2906,
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
    "duration_ms": 2223,
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
    "duration_ms": 29,
    "notes": "/=200/26406b, /index.html=200/26406b, /tools.html=200/28709b, /meeting.html?id=northwind-mtg-prev-001=200/12618b, /agent-builder.html=200/10642b, /demo-data.html=200/4385b, /workflow-demo.html=200/12953b, /fe-brain.html=200/7007b, /battlecards.html=200/13435b",
    "detail": {
      "/": {
        "status": 200,
        "bytes": 26406
      },
      "/index.html": {
        "status": 200,
        "bytes": 26406
      },
      "/tools.html": {
        "status": 200,
        "bytes": 28709
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
        "bytes": 1588
      },
      "/workspace.html": {
        "status": 200,
        "bytes": 22092
      },
      "/pov-health.html": {
        "status": 200,
        "bytes": 7980
      }
    }
  },
  "8": {
    "name": "Em/en dash audit (backend + frontend + docs + data)",
    "status": "PASS",
    "duration_ms": 46,
    "notes": "scanned=240 files, dash hits=0",
    "detail": {
      "files_scanned": 240,
      "files_with_dashes": 0,
      "examples": []
    }
  },
  "9": {
    "name": "Git status (uncommitted <=2; HEAD == origin/main)",
    "status": "FAIL",
    "duration_ms": 48,
    "notes": "uncommitted=1 (modified=1, untracked=0), HEAD=2dd09754875b, origin/main=e0fdd9fa6c39 | HEAD != origin/main",
    "detail": {
      "uncommitted_lines": 1,
      "uncommitted_sample": [
        " M .github/workflows/ci.yml"
      ],
      "modified_lines": 1,
      "head": "2dd09754875b",
      "origin_main": "e0fdd9fa6c39",
      "pushed_to_origin_main": false
    }
  }
}
```

