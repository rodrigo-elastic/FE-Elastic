# FE Copilot API Contract Tests (w25b)

- Backend base: http://localhost:8123
- Endpoints exercised: 65
- Cases run: 201
- Heavy endpoints SKIPPED (Anthropic credits / mutating cluster state): 18
- Contract violations: 0
- Runtime: 29.05 s

## Per-endpoint case results

| # | Method | Path | Case | Expected | Observed | Pass | Note |
| ---: | --- | --- | --- | --- | ---: | --- | --- |
| 1 | GET | `/health` | happy | 200 | 200 | PASS | {"status":"ok","service":"fe-copilot"} |
| 2 | POST | `/health` | wrong-method | 405 | 405 | PASS |  |
| 3 | GET | `/health` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 4 | GET | `/version` | happy | 200 | 200 | PASS | {"version":"0.1.0","service":"fe-copilot"} |
| 5 | POST | `/version` | wrong-method | 405 | 405 | PASS |  |
| 6 | GET | `/version` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 7 | GET | `/info` | happy | 200 | 200 | PASS | {"service":"fe-copilot","version":"0.1.0","mock_mode":false,"models":{"default":"claude-haiku-4-5","pre_meeting":"claude-haiku-4-5","post_me |
| 8 | POST | `/info` | wrong-method | 405 | 405 | PASS |  |
| 9 | GET | `/info` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 10 | GET | `/health/full` | happy | 200 | 200 | PASS | {"status":"green","warnings":[],"build":{"sha":"3b11760","timestamp":"2026-05-05T10:48:59+02:00"},"mcp_tools":{"count":12,"list":["fec_poc_p |
| 11 | POST | `/health/full` | wrong-method | 405 | 405 | PASS |  |
| 12 | GET | `/health/full` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 13 | POST | `/elasticsearch/reconnect` | happy | 200 | 200 | PASS | {"available":true,"url":"https://fe-summit-hackathon-ed0e8e.es.us-west-1.aws.found.io"} |
| 14 | GET | `/elasticsearch/reconnect` | wrong-method | 405 | 405 | PASS |  |
| 15 | POST | `/elasticsearch/reconnect` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 16 | POST | `/kibana/setup` | happy | 200 or 502 or 409 | 200 | PASS | {"ok":true,"url":"https://fe-summit-hackathon-ed0e8e.kb.us-west-1.aws.found.io","items":[{"id":"fec-briefs","name":"FE Copilot Briefs","stat |
| 17 | GET | `/kibana/setup` | wrong-method | 405 | 405 | PASS |  |
| 18 | POST | `/kibana/setup` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 19 | GET | `/meetings` | happy | 200 | 200 | PASS | [{"id":"atlantico-mtg-prev-002","company_id":"atlantico","title":"Banco Atlántico x Elastic, regulatory mapping working session","start_time |
| 20 | POST | `/meetings` | wrong-method | 405 | 405 | PASS |  |
| 21 | GET | `/meetings` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 22 | GET | `/meetings/upcoming` | happy | 200 | 200 | PASS | [{"company_id":"northwind","meeting_id":"northwind-mtg-001","title":"Northwind Pay x Elastic, observability cost & SIEM consolidation","star |
| 23 | POST | `/meetings/upcoming` | wrong-method | 405 | 405 | PASS |  |
| 24 | GET | `/meetings/upcoming` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 25 | GET | `/meetings/{meeting_id}` | happy | 200 | 200 | PASS | {"meeting":{"id":"atlantico-mtg-prev-002","company_id":"atlantico","title":"Banco Atlántico x Elastic, regulatory mapping working session"," |
| 26 | GET | `/meetings/{meeting_id}` | missing | 404 | 404 | PASS |  |
| 27 | GET | `/meetings/{meeting_id}` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 28 | POST | `/agents/pre-meeting/ad-hoc` | invalid | 422 | 422 | PASS | empty body |
| 29 | POST | `/agents/pre-meeting/ad-hoc` | invalid | 422 | 422 | PASS | empty company_name |
| 30 | GET | `/agents/pre-meeting/ad-hoc` | wrong-method | 405 | 405 | PASS |  |
| 31 | POST | `/agents/pre-meeting/ad-hoc` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 32 | POST | `/agents/pre-meeting/{meeting_id}` | missing | 404 | 404 | PASS | {"detail":"meeting_id __no_such_id_for_contract_check__ not found in synthetic data"} |
| 33 | GET | `/agents/pre-meeting/{meeting_id}` | wrong-method | 405 | 405 | PASS |  |
| 34 | POST | `/agents/pre-meeting/{meeting_id}` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 35 | POST | `/agents/post-meeting/from-transcript` | invalid | 422 | 422 | PASS | empty body |
| 36 | POST | `/agents/post-meeting/from-transcript` | invalid | 422 | 422 | PASS | transcript too short |
| 37 | GET | `/agents/post-meeting/from-transcript` | wrong-method | 405 | 405 | PASS |  |
| 38 | POST | `/agents/post-meeting/from-transcript` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 39 | POST | `/agents/post-meeting/{meeting_id}` | missing | 404 | 404 | PASS | {"detail":"meeting_id __no_such_id_for_contract_check__ not found"} |
| 40 | GET | `/agents/post-meeting/{meeting_id}` | wrong-method | 405 | 405 | PASS |  |
| 41 | POST | `/agents/post-meeting/{meeting_id}` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 42 | POST | `/agents/live-meeting/{meeting_id}/turn/{turn_index}` | missing | 404 | 404 | PASS | {"detail":"transcript not found"} |
| 43 | POST | `/agents/live-meeting/{meeting_id}/turn/{turn_index}` | invalid | 422 | 422 | PASS | non-int turn_index |
| 44 | GET | `/agents/live-meeting/{meeting_id}/turn/{turn_index}` | wrong-method | 405 | 405 | PASS |  |
| 45 | POST | `/agents/live-meeting/{meeting_id}/turn/{turn_index}` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 46 | GET | `/briefs` | happy | 200 | 200 | PASS | {"items":[{"type":"pre_meeting","meeting_id":"ad-hoc-test-co-20260505-082828","company_name":"Test Co","headline":"Consolidate fragmented mo |
| 47 | POST | `/briefs` | wrong-method | 405 | 405 | PASS |  |
| 48 | GET | `/briefs` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 49 | POST | `/briefs/reindex` | happy | 200 or 503 | 200 | PASS | {"ok":true,"indexed":{"briefs":2,"post_meetings":2},"es_url":"https://fe-summit-hackathon-ed0e8e.es.us-west-1.aws.found.io"} |
| 50 | GET | `/briefs/reindex` | wrong-method | 405 | 405 | PASS |  |
| 51 | POST | `/briefs/reindex` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 52 | GET | `/briefs/{meeting_id}` | happy | 200 | 200 | PASS | {"exists":false,"meeting_id":"atlantico-mtg-prev-002"} |
| 53 | GET | `/briefs/{meeting_id}` | missing | 200 or 404 | 200 | PASS | by design returns 200 + exists:false |
| 54 | GET | `/briefs/{meeting_id}` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 55 | GET | `/briefs/{meeting_id}/artifact` | missing | 404 | 404 | PASS | {"detail":"brief not generated yet"} |
| 56 | GET | `/briefs/{meeting_id}/artifact` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 57 | GET | `/briefs/{meeting_id}/post` | happy | 200 | 200 | PASS | {"meeting_id":"atlantico-mtg-prev-002","company_id":"atlantico","generated_at":"2026-05-04T17:07:45.014774+00:00","summary":"Banco Atlántico |
| 58 | GET | `/briefs/{meeting_id}/post` | missing | 200 or 404 | 200 | PASS | by design returns 200 + exists:false |
| 59 | GET | `/briefs/{meeting_id}/post` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 60 | GET | `/audit` | happy | 200 | 200 | PASS | {"entries":[{"ts":"2026-05-05T08:49:06.718013+00:00","model":"claude-haiku-4-5","mode":"hybrid_rerank","input_tokens":0,"output_tokens":0,"f |
| 61 | POST | `/audit` | wrong-method | 405 | 405 | PASS |  |
| 62 | GET | `/audit` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 63 | GET | `/battlecards` | happy | 200 | 200 | PASS | {"items":[{"id":"battlecard-algolia","competitor":"Algolia","competitor_slug":"algolia","vertical":"ai_search_ecommerce","industries":["reta |
| 64 | DELETE | `/battlecards` | wrong-method | 405 | 405 | PASS |  |
| 65 | GET | `/battlecards` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 66 | GET | `/battlecards/by-competitor/{name}` | happy | 200 | 200 | PASS | {"id":"battlecard-algolia","competitor":"Algolia","competitor_slug":"algolia","vertical":"ai_search_ecommerce","industries":["retail-ecommer |
| 67 | GET | `/battlecards/by-competitor/{name}` | missing | 404 | 404 | PASS |  |
| 68 | GET | `/battlecards/by-competitor/{name}` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 69 | POST | `/battlecards/reseed` | happy | 200 | 200 | PASS | {"ok":true,"indexed":31,"total":31} |
| 70 | GET | `/battlecards/reseed` | wrong-method | 405 | 405 | PASS |  |
| 71 | POST | `/battlecards/reseed` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 72 | GET | `/salesforce/tasks` | happy | 200 | 200 | PASS | {"count":90,"items":[{"_action":"Slack.post","Channel":"#deal-transcript-northwind-bank-workflow-demo","OpportunityId":"006TRANSCRIPTNORTH", |
| 73 | POST | `/salesforce/tasks` | wrong-method | 405 | 405 | PASS |  |
| 74 | GET | `/salesforce/tasks` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 75 | GET | `/salesforce/account/{company_id}` | happy | 200 | 200 | PASS | {"Id":"001ATLANTICO000000","Name":"Banco Atlántico","Industry":"Banking","NumberOfEmployees":"5,000+","OwnerName":"Field Engineering","Type" |
| 76 | GET | `/salesforce/account/{company_id}` | missing | 200 or 404 | 200 | PASS | by design returns 200 with empty company info |
| 77 | GET | `/salesforce/account/{company_id}` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 78 | GET | `/calendar/events` | happy | 200 | 200 | PASS | {"items":[{"id":"gcal-evt-005","summary":"FE team weekly sync","description":"Internal Elastic FE team weekly.","start":{"dateTime":"2026-05 |
| 79 | POST | `/calendar/events` | wrong-method | 405 | 405 | PASS |  |
| 80 | GET | `/calendar/events` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 81 | GET | `/calendar/events/{event_id}` | happy | 200 | 200 | PASS | {"id":"gcal-evt-005","summary":"FE team weekly sync","description":"Internal Elastic FE team weekly.","start":{"dateTime":"2026-05-05T10:50: |
| 82 | GET | `/calendar/events/{event_id}` | missing | 404 | 404 | PASS |  |
| 83 | GET | `/calendar/events/{event_id}` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 84 | POST | `/tools/poc-plan/{meeting_id}` | missing | 404 | 404 | PASS | {"detail":"meeting __no_such_id_for_contract_check__ not found"} \| missing meeting |
| 85 | GET | `/tools/poc-plan/{meeting_id}` | wrong-method | 405 | 405 | PASS |  |
| 86 | POST | `/tools/poc-plan/{meeting_id}` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 87 | POST | `/tools/spl-to-esql` | invalid | 422 | 422 | PASS | {"detail":[{"type":"missing","loc":["body","spl"],"msg":"Field required","input":{}}]} \| empty body |
| 88 | GET | `/tools/spl-to-esql` | wrong-method | 405 | 405 | PASS |  |
| 89 | POST | `/tools/spl-to-esql` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 90 | POST | `/tools/compliance-mapping` | invalid | 422 | 422 | PASS | {"detail":[{"type":"missing","loc":["body","regulations"],"msg":"Field required","input":{}}]} \| empty body |
| 91 | GET | `/tools/compliance-mapping` | wrong-method | 405 | 405 | PASS |  |
| 92 | POST | `/tools/compliance-mapping` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 93 | POST | `/tools/stack-extract` | invalid | 422 | 422 | PASS | {"detail":[{"type":"string_too_short","loc":["body","text"],"msg":"String should have at least 20 characters","input":"x","ctx":{"min_length \| text too short |
| 94 | GET | `/tools/stack-extract` | wrong-method | 405 | 405 | PASS |  |
| 95 | POST | `/tools/stack-extract` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 96 | POST | `/tools/code-sample` | invalid | 422 | 422 | PASS | {"detail":[{"type":"missing","loc":["body","language"],"msg":"Field required","input":{}},{"type":"missing","loc":["body","use_case"],"msg": \| empty body |
| 97 | GET | `/tools/code-sample` | wrong-method | 405 | 405 | PASS |  |
| 98 | POST | `/tools/code-sample` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 99 | POST | `/tools/troubleshoot` | invalid | 422 | 422 | PASS | {"detail":[{"type":"string_too_short","loc":["body","error_text"],"msg":"String should have at least 3 characters","input":"x","ctx":{"min_l \| error_text too s |
| 100 | GET | `/tools/troubleshoot` | wrong-method | 405 | 405 | PASS |  |
| 101 | POST | `/tools/troubleshoot` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 102 | POST | `/tools/compare` | invalid | 422 | 422 | PASS | {"detail":[{"type":"missing","loc":["body","competitor"],"msg":"Field required","input":{}}]} \| empty body |
| 103 | GET | `/tools/compare` | wrong-method | 405 | 405 | PASS |  |
| 104 | POST | `/tools/compare` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 105 | POST | `/tools/orchestrator` | invalid | 422 | 422 | PASS | {"detail":[{"type":"missing","loc":["body","query"],"msg":"Field required","input":{}}]} \| empty body |
| 106 | GET | `/tools/orchestrator` | wrong-method | 405 | 405 | PASS |  |
| 107 | POST | `/tools/orchestrator` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 108 | POST | `/tools/proposal` | invalid | 422 | 422 | PASS | {"detail":[{"type":"missing","loc":["body","meeting_id"],"msg":"Field required","input":{}}]} \| empty body |
| 109 | GET | `/tools/proposal` | wrong-method | 405 | 405 | PASS |  |
| 110 | POST | `/tools/proposal` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 111 | POST | `/tools/cost-calc` | happy | 200 | 200 | PASS | {"inputs":{"ingest_gb_day":50.0,"retention_months":12,"hot_pct":30.0,"warm_pct":30.0,"frozen_pct":40.0,"current_spend_annual_usd":1000000.0, |
| 112 | POST | `/tools/cost-calc` | invalid | 422 | 422 | PASS | empty body |
| 113 | POST | `/tools/cost-calc` | invalid | 422 | 422 | PASS | negative ingest |
| 114 | GET | `/tools/cost-calc` | wrong-method | 405 | 405 | PASS |  |
| 115 | POST | `/tools/cost-calc` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 116 | POST | `/tools/capacity` | happy | 200 | 200 | PASS | {"inputs":{"peak_indexing_eps":10000,"hot_data_gb":1000,"warm_data_gb":500,"replicas":1,"peak_qps":100},"hot":{"node_type":"i3.xlarge equiva |
| 117 | POST | `/tools/capacity` | invalid | 422 | 422 | PASS | empty body |
| 118 | GET | `/tools/capacity` | wrong-method | 405 | 405 | PASS |  |
| 119 | POST | `/tools/capacity` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 120 | POST | `/tools/knowledge-search` | happy | 200 | 200 | PASS | {"answer":"Mock fallback: the knowledge index is not yet populated. Once the corpus and embeddings are ready, this tool will return a ground |
| 121 | POST | `/tools/knowledge-search` | invalid | 422 | 422 | PASS | empty body |
| 122 | POST | `/tools/knowledge-search` | invalid | 422 | 422 | PASS | query too short |
| 123 | GET | `/tools/knowledge-search` | wrong-method | 405 | 405 | PASS |  |
| 124 | POST | `/tools/knowledge-search` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 125 | GET | `/tools/knowledge-search/health` | happy | 200 | 200 | PASS | {"available":true,"documents":1300,"urls":321} |
| 126 | POST | `/tools/knowledge-search/health` | wrong-method | 405 | 405 | PASS |  |
| 127 | GET | `/tools/knowledge-search/health` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 128 | GET | `/agent-builder/status` | happy | 200 | 200 | PASS | {"live":true,"kibana_url":"https://fe-summit-hackathon-ed0e8e.kb.us-west-1.aws.found.io","configured_tools":["fec_poc_plan","fec_spl_to_esql |
| 129 | POST | `/agent-builder/status` | wrong-method | 405 | 405 | PASS |  |
| 130 | GET | `/agent-builder/status` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 131 | GET | `/agent-builder/tools` | happy | 200 | 200 | PASS | {"tools":[{"id":"platform.core.search","type":"builtin","description":"A powerful tool for searching and analyzing data within your Elastics |
| 132 | POST | `/agent-builder/tools` | wrong-method | 405 | 405 | PASS |  |
| 133 | GET | `/agent-builder/tools` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 134 | GET | `/agent-builder/agents` | happy | 200 | 200 | PASS | {"agents":[{"id":"elastic-ai-agent","name":"Elastic AI Agent","description":"Elastic AI Agent","configuration":{"tools":[{"tool_ids":["platf |
| 135 | POST | `/agent-builder/agents` | wrong-method | 405 or 422 | 422 | PASS | POST exists with required body so an empty body is 422; either is acceptable |
| 136 | GET | `/agent-builder/agents` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 137 | GET | `/agent-builder/agents/{agent_id}` | invalid | 422 | 422 | PASS | bad id format |
| 138 | GET | `/agent-builder/agents/{agent_id}` | missing | 404 or 409 | 404 | PASS | {"detail":"{\"statusCode\":404,\"error\":\"Not Found\",\"message\":\"Agent __no_such_id_for_contract_check__ not found\",\"attributes\":{}}" |
| 139 | GET | `/agent-builder/agents/{agent_id}` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 140 | POST | `/agent-builder/agents` | invalid | 422 | 422 | PASS | empty body |
| 141 | POST | `/agent-builder/agents` | invalid | 422 | 422 | PASS | fields too short |
| 142 | PUT | `/agent-builder/agents` | wrong-method | 405 | 405 | PASS |  |
| 143 | POST | `/agent-builder/agents` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 144 | DELETE | `/agent-builder/agents/{agent_id}` | invalid | 422 | 422 | PASS | bad id format |
| 145 | DELETE | `/agent-builder/agents/fec_field_assistant` | wrong-method | 403 | 403 | PASS | master is reserved |
| 146 | DELETE | `/agent-builder/agents/{agent_id}` | missing | 404 or 409 | 404 | PASS | {"detail":"{\"statusCode\":404,\"error\":\"Not Found\",\"message\":\"Agent fec_user___no_such_id_for_contract_check__ not found\",\"attribut |
| 147 | DELETE | `/agent-builder/agents/{agent_id}` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 148 | POST | `/agent-builder/converse` | invalid | 422 | 422 | PASS | empty body |
| 149 | POST | `/agent-builder/converse` | invalid | 422 | 422 | PASS | empty message |
| 150 | GET | `/agent-builder/converse` | wrong-method | 405 | 405 | PASS |  |
| 151 | POST | `/agent-builder/converse` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 152 | POST | `/mcp` | happy | 200 | 200 | PASS | {"jsonrpc":"2.0","id":1,"result":{"tools":[{"name":"fec_poc_plan","description":"Produce a 4-8 week Proof-of-Value plan grounded in the late |
| 153 | POST | `/mcp` | invalid | 400 | 400 | PASS | non-JSON body |
| 154 | GET | `/mcp` | wrong-method | 405 | 405 | PASS |  |
| 155 | POST | `/mcp` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 156 | POST | `/kibana/dashboard/{meeting_id}` | missing | 404 or 409 or 502 | 404 | PASS | {"detail":"meeting __no_such_id_for_contract_check__ not found - run the Pre-Meeting agent first so the brief lands on disk."} |
| 157 | GET | `/kibana/dashboard/{meeting_id}` | wrong-method | 405 | 405 | PASS |  |
| 158 | POST | `/kibana/dashboard/{meeting_id}` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 159 | GET | `/demo-data/scenarios` | happy | 200 | 200 | PASS | {"scenarios":[{"id":"black-friday-outage","title":"Black Friday Outage","description":"Lumen Apparel - a growing fintech-backed e-commerce p |
| 160 | POST | `/demo-data/scenarios` | wrong-method | 405 | 405 | PASS |  |
| 161 | GET | `/demo-data/scenarios` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 162 | POST | `/demo-data/{scenario_id}/seed` | missing | 404 | 404 | PASS | {"detail":"unknown scenario __no_such_id_for_contract_check__"} |
| 163 | GET | `/demo-data/{scenario_id}/seed` | wrong-method | 405 | 405 | PASS |  |
| 164 | POST | `/demo-data/{scenario_id}/seed` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 165 | GET | `/workflows/status` | happy | 200 | 200 | PASS | {"ok":true,"registered":true,"rule_id":"f1424106-270b-472d-ac97-640a609489e0","connector_id":"80ed37e4-fad4-4b08-a03a-b0e95726f2e5","rule_st |
| 166 | PUT | `/workflows/status` | wrong-method | 405 | 405 | PASS |  |
| 167 | GET | `/workflows/status` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 168 | GET | `/workflows/sync` | wrong-method | 405 | 405 | PASS |  |
| 169 | POST | `/workflows/sync` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 170 | GET | `/workflows/sync` | wrong-method | 405 | 405 | PASS |  |
| 171 | DELETE | `/workflows/sync` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 172 | POST | `/workflows/triggered` | happy | 200 or 202 | 200 | PASS | {"ok":true,"processed_count":0,"post_meeting_result":null,"reason":"no-unprocessed-docs"} |
| 173 | GET | `/workflows/triggered` | wrong-method | 405 | 405 | PASS |  |
| 174 | POST | `/workflows/triggered` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 175 | GET | `/workflows/demo-fire` | wrong-method | 405 | 405 | PASS |  |
| 176 | POST | `/workflows/demo-fire` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 177 | GET | `/workflows/recent-fires` | happy | 200 | 200 | PASS | {"ok":true,"fires":[{"received_at":"2026-05-05T08:50:25.533981+00:00","alert_id":"smoke-test","rule_id":"smoke-test","rule_name":"Smoke Test |
| 178 | POST | `/workflows/recent-fires` | wrong-method | 405 | 405 | PASS |  |
| 179 | GET | `/workflows/recent-fires` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 180 | POST | `/workflows/post-meeting-action-orphan` | happy | 200 | 200 | PASS | {"ok":true,"tasks_created":0,"tasks":[],"scanned_docs":2,"matched_orphans":0} |
| 181 | GET | `/workflows/post-meeting-action-orphan` | wrong-method | 405 | 405 | PASS |  |
| 182 | POST | `/workflows/post-meeting-action-orphan` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 183 | GET | `/workflows/orphan-demo-fire` | wrong-method | 405 | 405 | PASS |  |
| 184 | POST | `/workflows/orphan-demo-fire` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 185 | POST | `/workflows/renewal-at-risk` | happy | 200 | 200 | PASS | {"ok":true,"play":{"account_id":"smoke","account_name":"smoke","severity":"low","top_3_signals":[],"retention_play":"Account smoke is showin |
| 186 | GET | `/workflows/renewal-at-risk` | wrong-method | 405 | 405 | PASS |  |
| 187 | POST | `/workflows/renewal-at-risk` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 188 | GET | `/workflows/renewal-demo-fire` | wrong-method | 405 | 405 | PASS |  |
| 189 | POST | `/workflows/renewal-demo-fire` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 190 | GET | `/workflows/sfdc-auto-tasks` | happy | 200 | 200 | PASS | {"ok":true,"tasks":[{"created_at":"2026-05-04T10:47:07.480964+00:00","workflow":"orphan-action","rule_id":"931f6f84-1d01-484d-a0f6-cc9ec1737 |
| 191 | POST | `/workflows/sfdc-auto-tasks` | wrong-method | 405 | 405 | PASS |  |
| 192 | GET | `/workflows/sfdc-auto-tasks` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 193 | GET | `/industries` | happy | 200 | 200 | PASS | {"items":[{"id":"fsi-banking","name":"Financial Services - Banking","icon":"bank","summary":"Retail, commercial, and investment banking. Spl |
| 194 | POST | `/industries` | wrong-method | 405 | 405 | PASS |  |
| 195 | GET | `/industries` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 196 | GET | `/industries/{industry_id}` | happy | 200 | 200 | PASS | {"id":"fsi-banking","name":"Financial Services - Banking","icon":"bank","summary":"Retail, commercial, and investment banking. Splunk replac |
| 197 | GET | `/industries/{industry_id}` | missing | 404 | 404 | PASS |  |
| 198 | GET | `/industries/{industry_id}` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |
| 199 | GET | `/stats/savings` | happy | 200 | 200 | PASS | {"this_week":{"hours_saved":100.1,"tool_calls":568,"agent_runs":38,"workflows_fired":20,"delta_vs_last_week":"+100%"},"last_week":{"hours_sa |
| 200 | POST | `/stats/savings` | wrong-method | 405 | 405 | PASS |  |
| 201 | GET | `/stats/savings` | cors | 200/204 + ACAO header | 200 | PASS | aca-origin='http://example.test', status=200 |

## Contract violations found

None. All cases passed.

## Notes on intentional deviations

- `GET /briefs/{meeting_id}` and `GET /briefs/{meeting_id}/post` return 200 with `{exists: false}` when missing. Documented behaviour: keeps the dashboard from filling the browser console with expected misses for unrun briefs.
- `GET /salesforce/account/{company_id}` returns 200 with empty company info on missing ids. Salesforce mock is read-through and never 404s.
- Heavy LLM endpoints (`/agents/*`, `/tools/poc-plan`, `/tools/spl-to-esql`, `/tools/compliance-mapping`, `/tools/stack-extract`, `/tools/code-sample`, `/tools/troubleshoot`, `/tools/compare`, `/tools/orchestrator`, `/tools/proposal`) are exercised with structurally invalid payloads only, plus an OPTIONS preflight, plus a missing-resource probe where applicable. Happy paths are SKIPPED to avoid Anthropic credit usage.
- MCP `tools/call` is also SKIPPED because every tool call routes back through one of the heavy LLM endpoints above.
- `/workflows/sync` (POST + DELETE), `/workflows/demo-fire`, `/workflows/orphan-demo-fire`, `/workflows/renewal-demo-fire` are SKIPPED on happy path because they mutate the live Kibana cluster. Only wrong-method and CORS checks run.

## Fixes applied during this pass

1. **Static frontend mount was eating 405s.** `backend/app/main.py` now installs an HTTP middleware that intercepts paths under `/api/v1/` and returns 405 with a proper `Allow` header when an API route matches the path with a different method. Without this, requests like `GET /api/v1/elasticsearch/reconnect` (POST-only) fell through to the `/` static mount and surfaced as 404, hiding the method-mismatch from API consumers.
2. **`/briefs/{meeting_id}` swallowed reserved keywords.** A `GET /briefs/reindex` matched the path parameter and returned 200 with `exists:false`, masking the fact that `/briefs/reindex` is POST-only. `routes_briefs.py` now reserves the `reindex` keyword in `get_brief` and raises `HTTPException(405)` with `Allow: POST` so the contract is honoured.
3. **CORS preflight stayed correct.** The new method-mismatch middleware skips OPTIONS explicitly so FastAPI's CORSMiddleware can answer preflight with the expected `Access-Control-Allow-*` headers.

