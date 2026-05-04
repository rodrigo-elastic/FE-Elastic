# FE Copilot Integration Smoke Report

- Generated: 2026-05-04T12:24:51Z
- Backend base: http://localhost:8123
- Elasticsearch: https://fe-summit-hackathon-ed0e8e.es.us-west-1.aws.found.io
- Kibana: https://fe-summit-hackathon-ed0e8e.kb.us-west-1.aws.found.io
- Total runtime: 21.28 s

## Verdict

**CAUTION**  --  passed=8, failed=1, skipped=0

Critical steps (1, 2, 3, 4, 7) must all pass.
Non-critical steps (5, 6, 8, 9) may fail up to 2 times for CAUTION.

## Step Results

| # | Step | Status | Critical | Duration (ms) | Notes |
| ---: | --- | --- | --- | ---: | --- |
| 1 | Backend health + pytest 30/30 | PASS | yes | 807 | health=ok, pytest=30 passed |
| 2 | Elasticsearch indices (fec-* + demo-*) green | PASS | yes | 652 | 21 found / 20 expected, fec-knowledge=2830 docs |
| 3 | Kibana saved objects (dashboards + tools + agent + .mcp + rule) | PASS | yes | 1768 | dashboards=13 (demo 10/10, customer-fit=3), fec-tools=12/12, agent=yes, mcp=1, rule=1 |
| 4 | MCP server (tools/list = 12, fec_cost_calc tool/call) | PASS | yes | 3 | tools/list=12, fec_cost_calc OK (elastic $28,080) |
| 5 | Tools REST (compute + knowledge-search; OPTIONS for heavy) | PASS | no | 15737 | cost-calc=200, capacity=200, knowledge-search=200, heavy-routes=405/405/405/405/405 |
| 6 | Workflow status + webhook handler | PASS | no | 2184 | registered=True, rule=registered, connector=registered, webhook_status=200 |
| 7 | Frontend pages reachable | PASS | yes | 12 | /=200/18194b, /index.html=200/18194b, /tools.html=200/18588b, /meeting.html?id=revolut-mtg-prev-001=200/9841b, /agent-builder.html=200/4475b, /demo-data.html=200/2628b, /workflow-demo.html=200/8201b, /fe-brain.html=200/5291b, /battlecards.html=200/6394b |
| 8 | Em/en dash audit (backend + frontend + docs + data) | PASS | no | 21 | scanned=178 files, dash hits=0 |
| 9 | Git status (uncommitted <=2; HEAD == origin/main) | FAIL | no | 61 | uncommitted=14 (modified=10, untracked=4), HEAD=c533619c0362, origin/main=9ad252c9d49e \| 10 modified files (>2); HEAD != origin/main |

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
    "duration_ms": 807,
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
    "duration_ms": 652,
    "notes": "21 found / 20 expected, fec-knowledge=2830 docs",
    "detail": {
      "index_count": 21,
      "fec_knowledge_docs": 2830
    }
  },
  "3": {
    "name": "Kibana saved objects (dashboards + tools + agent + .mcp + rule)",
    "status": "PASS",
    "duration_ms": 1768,
    "notes": "dashboards=13 (demo 10/10, customer-fit=3), fec-tools=12/12, agent=yes, mcp=1, rule=1",
    "detail": {
      "dashboard_total": 13,
      "customer_fit_dashboards": 3,
      "agent_builder_tools_total": 24,
      "fec_tools_present": 12,
      "agents": [
        "elastic-ai-agent",
        "fec_field_assistant"
      ],
      "mcp_connectors": 1,
      "mcp_server_url": "https://headlamp-squatting-usable.ngrok-free.dev/api/v1/mcp",
      "alerting_rules": 1
    }
  },
  "4": {
    "name": "MCP server (tools/list = 12, fec_cost_calc tool/call)",
    "status": "PASS",
    "duration_ms": 3,
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
    "duration_ms": 15737,
    "notes": "cost-calc=200, capacity=200, knowledge-search=200, heavy-routes=405/405/405/405/405",
    "detail": {
      "cost_calc_status": 200,
      "capacity_status": 200,
      "knowledge_status": 200,
      "knowledge_answer_len": 1468,
      "knowledge_citations": 2,
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
    "duration_ms": 2184,
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
    "duration_ms": 12,
    "notes": "/=200/18194b, /index.html=200/18194b, /tools.html=200/18588b, /meeting.html?id=revolut-mtg-prev-001=200/9841b, /agent-builder.html=200/4475b, /demo-data.html=200/2628b, /workflow-demo.html=200/8201b, /fe-brain.html=200/5291b, /battlecards.html=200/6394b",
    "detail": {
      "/": {
        "status": 200,
        "bytes": 18194
      },
      "/index.html": {
        "status": 200,
        "bytes": 18194
      },
      "/tools.html": {
        "status": 200,
        "bytes": 18588
      },
      "/meeting.html?id=revolut-mtg-prev-001": {
        "status": 200,
        "bytes": 9841
      },
      "/agent-builder.html": {
        "status": 200,
        "bytes": 4475
      },
      "/demo-data.html": {
        "status": 200,
        "bytes": 2628
      },
      "/workflow-demo.html": {
        "status": 200,
        "bytes": 8201
      },
      "/fe-brain.html": {
        "status": 200,
        "bytes": 5291
      },
      "/battlecards.html": {
        "status": 200,
        "bytes": 6394
      }
    }
  },
  "8": {
    "name": "Em/en dash audit (backend + frontend + docs + data)",
    "status": "PASS",
    "duration_ms": 21,
    "notes": "scanned=178 files, dash hits=0",
    "detail": {
      "files_scanned": 178,
      "files_with_dashes": 0,
      "examples": []
    }
  },
  "9": {
    "name": "Git status (uncommitted <=2; HEAD == origin/main)",
    "status": "FAIL",
    "duration_ms": 61,
    "notes": "uncommitted=14 (modified=10, untracked=4), HEAD=c533619c0362, origin/main=9ad252c9d49e | 10 modified files (>2); HEAD != origin/main",
    "detail": {
      "uncommitted_lines": 14,
      "uncommitted_sample": [
        " M backend/app/agents/prompts/tools.py",
        " M backend/app/agents/schemas.py",
        " M backend/app/api/routes_mcp.py",
        " M backend/app/api/routes_tools.py",
        " M backend/data/seed/battlecards.json"
      ],
      "modified_lines": 10,
      "head": "c533619c0362",
      "origin_main": "9ad252c9d49e",
      "pushed_to_origin_main": false
    }
  }
}
```

