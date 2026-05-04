# FE Copilot End-to-End Test Report

- Generated: 2026-05-04T22:57:08Z
- Backend base: http://localhost:8123
- Total runtime: 107.01 s

## Verdict

**CAUTION**  ::  passed=10, failed=2, skipped=0

Verdict rules: GO when failed=0; CAUTION when failed in [1, 2]; NO-GO otherwise.

## Journey Results

| # | Journey | Status | Duration (ms) | Detail |
| ---: | --- | --- | ---: | --- |
| 1 | Journey 1: Field Assistant solves a TCO question | PASS | 13846 | tools=fec_cost_calc, response_chars=1201, has_dollar=True |
| 2 | Journey 2: Create + use + delete a custom agent | PASS | 31785 | create=ok, converse_chars=1997, delete=ok |
| 3 | Journey 3: All 12 MCP tools individually (minimum-valid input) | PASS | 6493 | ok=11/12, hard_fail=0, soft_skip=1 |
| 4 | Journey 4: Battlecards vertical filter parity | PASS | 807 | total=31, source=es, ai_search_ecommerce=3, observability_logs=13, direct_search_vector=6, security_siem_xdr=9 |
| 5 | Journey 5: Demo scenario reseed cycle (black-friday) | PASS | 30085 | reseed=ok, dashboard_url=set, page=200 |
| 6 | Journey 6: FE Brain query quality | FAIL | 2759 | answer_chars=237, elastic_urls=0, has_semantic_text=False, has_elser=False \| elastic_urls=0 (<2); missing 'semantic_text'; missing 'ELSER' |
| 7 | Journey 7: Cost calculator with data-quality badges | PASS | 1 | line_items=10, qualities={'demo_estimate': 6, 'verified_list_price': 4} |
| 8 | Journey 8: Master agent routing for proposal request | PASS | 13249 | tools=fec_proposal, response_chars=1345 |
| 9 | Journey 9: Industries (W15A) - 20 entries with rich shape | PASS | 6 | 20 industries, fsi-banking fully populated |
| 10 | Journey 10: i18n keys parity across all 5 locales | PASS | 15 | counts=en=385, es=385, ja=385, de=385, fr=385 (all aligned) |
| 11 | Journey 11: Em/en dash audit (.py, .js, .css, .html, .md, .json) | PASS | 22 | scanned=204, dash hits=0 |
| 12 | Journey 12: Performance budgets (health/full p95, agents, battlecards) | FAIL | 7908 | health/full_p95=1378ms, agents=661ms, battlecards=757ms \| health/full p95=1378ms (>=500) |

## Aggregate

- passed: 10
- failed: 2
- skipped: 0
- total journeys: 12

## Raw Detail

```json
{
  "1": {
    "name": "Journey 1: Field Assistant solves a TCO question",
    "status": "PASS",
    "duration_ms": 13846,
    "notes": "tools=fec_cost_calc, response_chars=1201, has_dollar=True",
    "detail": {
      "tool_ids": [
        "fec_cost_calc"
      ],
      "response_chars": 1201
    }
  },
  "2": {
    "name": "Journey 2: Create + use + delete a custom agent",
    "status": "PASS",
    "duration_ms": 31785,
    "notes": "create=ok, converse_chars=1997, delete=ok",
    "detail": {
      "agent_id": "fec_user_e2e_migr_935334",
      "create_status": 200,
      "create_body": {
        "agent_id": "fec_user_e2e_migr_935334",
        "name": "E2E Migration Specialist",
        "tool_count": 4,
        "tool_ids": [
          "fec_poc_plan",
          "fec_compare",
          "fec_cost_calc",
          "fec_capacity"
        ],
        "kibana_url": "https://fe-summit-hackathon-ed0e8e.kb.us-west-1.aws.found.io/app/agent_builder"
      },
      "agents_after_create": 6,
      "converse_status": 200,
      "converse_chars": 1997,
      "delete_status": 200,
      "agents_after_delete": 5
    }
  },
  "3": {
    "name": "Journey 3: All 12 MCP tools individually (minimum-valid input)",
    "status": "PASS",
    "duration_ms": 6493,
    "notes": "ok=11/12, hard_fail=0, soft_skip=1",
    "detail": {
      "per_tool": {
        "fec_poc_plan": {
          "http": 200,
          "isError": true,
          "chars": 95,
          "soft_skip": true
        },
        "fec_spl_to_esql": {
          "http": 200,
          "isError": false,
          "chars": 160
        },
        "fec_compliance": {
          "http": 200,
          "isError": false,
          "chars": 251
        },
        "fec_stack_extract": {
          "http": 200,
          "isError": false,
          "chars": 186
        },
        "fec_code_sample": {
          "http": 200,
          "isError": false,
          "chars": 333
        },
        "fec_cost_calc": {
          "http": 200,
          "isError": false,
          "chars": 4044
        },
        "fec_capacity": {
          "http": 200,
          "isError": false,
          "chars": 934
        },
        "fec_knowledge_search": {
          "http": 200,
          "isError": false,
          "chars": 268
        },
        "fec_troubleshoot": {
          "http": 200,
          "isError": false,
          "chars": 1209
        },
        "fec_compare": {
          "http": 200,
          "isError": false,
          "chars": 2054
        },
        "fec_orchestrator": {
          "http": 200,
          "isError": false,
          "chars": 4351
        },
        "fec_proposal": {
          "http": 200,
          "isError": false,
          "chars": 1632
        }
      },
      "soft_skips": [
        "fec_poc_plan (missing post-meeting record)"
      ]
    }
  },
  "4": {
    "name": "Journey 4: Battlecards vertical filter parity",
    "status": "PASS",
    "duration_ms": 807,
    "notes": "total=31, source=es, ai_search_ecommerce=3, observability_logs=13, direct_search_vector=6, security_siem_xdr=9",
    "detail": {
      "total": 31,
      "source": "es",
      "counts": {
        "ai_search_ecommerce": 3,
        "observability_logs": 13,
        "direct_search_vector": 6,
        "security_siem_xdr": 9
      }
    }
  },
  "5": {
    "name": "Journey 5: Demo scenario reseed cycle (black-friday)",
    "status": "PASS",
    "duration_ms": 30085,
    "notes": "reseed=ok, dashboard_url=set, page=200",
    "detail": {
      "scenario_ids": [
        "black-friday-outage",
        "credential-stuffing",
        "noisy-microservice",
        "gdpr-audit-timeline",
        "supply-chain-attack",
        "fsi-banking-fraud",
        "healthcare-hipaa-audit",
        "gov-cdm-compliance"
      ],
      "seed_status": 200,
      "dashboard_url": "https://fe-summit-hackathon-ed0e8e.kb.us-west-1.aws.found.io/app/dashboards#/view/demo-black-friday-outage-dashboard",
      "doc_counts": {
        "demo-blackfriday-checkout": 3500,
        "demo-blackfriday-apm": 1500,
        "demo-blackfriday-metrics": 600
      },
      "page_status": 200
    }
  },
  "6": {
    "name": "Journey 6: FE Brain query quality",
    "status": "FAIL",
    "duration_ms": 2759,
    "notes": "answer_chars=237, elastic_urls=0, has_semantic_text=False, has_elser=False | elastic_urls=0 (<2); missing 'semantic_text'; missing 'ELSER'",
    "detail": {
      "answer_chars": 237,
      "citation_count": 0,
      "elastic_urls": []
    }
  },
  "7": {
    "name": "Journey 7: Cost calculator with data-quality badges",
    "status": "PASS",
    "duration_ms": 1,
    "notes": "line_items=10, qualities={'demo_estimate': 6, 'verified_list_price': 4}",
    "detail": {
      "line_items": 10,
      "qualities": {
        "demo_estimate": 6,
        "verified_list_price": 4
      }
    }
  },
  "8": {
    "name": "Journey 8: Master agent routing for proposal request",
    "status": "PASS",
    "duration_ms": 13249,
    "notes": "tools=fec_proposal, response_chars=1345",
    "detail": {
      "tool_ids": [
        "fec_proposal"
      ],
      "response_chars": 1345
    }
  },
  "9": {
    "name": "Journey 9: Industries (W15A) - 20 entries with rich shape",
    "status": "PASS",
    "duration_ms": 6,
    "notes": "20 industries, fsi-banking fully populated",
    "detail": {
      "list_status": 200,
      "count": 20,
      "detail_status": 200,
      "fsi_personas": true,
      "fsi_regulations": true,
      "fsi_top_competitors": true
    }
  },
  "10": {
    "name": "Journey 10: i18n keys parity across all 5 locales",
    "status": "PASS",
    "duration_ms": 15,
    "notes": "counts=en=385, es=385, ja=385, de=385, fr=385 (all aligned)",
    "detail": {
      "counts": {
        "en": 385,
        "es": 385,
        "ja": 385,
        "de": 385,
        "fr": 385
      },
      "missing": {},
      "extra": {}
    }
  },
  "11": {
    "name": "Journey 11: Em/en dash audit (.py, .js, .css, .html, .md, .json)",
    "status": "PASS",
    "duration_ms": 22,
    "notes": "scanned=204, dash hits=0",
    "detail": {
      "files_scanned": 204,
      "files_with_dashes": 0,
      "examples": []
    }
  },
  "12": {
    "name": "Journey 12: Performance budgets (health/full p95, agents, battlecards)",
    "status": "FAIL",
    "duration_ms": 7908,
    "notes": "health/full_p95=1378ms, agents=661ms, battlecards=757ms | health/full p95=1378ms (>=500)",
    "detail": {
      "health_full_times_ms": [
        1236,
        1247,
        1261,
        1365,
        1378
      ],
      "health_full_p95_ms": 1378,
      "agents_ms": 661,
      "battlecards_ms": 757
    }
  }
}
```

