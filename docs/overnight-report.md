# Overnight automation report

_Generated 2026-05-04 05:00:04Z_

## Batch results

### 0015_smoke

```
[2026-05-03T22:07:41Z] [0015_smoke] demo-black-friday-outage-dashboard=200
[2026-05-03T22:07:42Z] [0015_smoke] demo-black-friday-outage-customer-dashboard=200
[2026-05-03T22:07:43Z] [0015_smoke] demo-credential-stuffing-dashboard=200
[2026-05-03T22:07:44Z] [0015_smoke] demo-credential-stuffing-customer-dashboard=200
[2026-05-03T22:07:46Z] [0015_smoke] demo-noisy-microservice-dashboard=200
[2026-05-03T22:07:47Z] [0015_smoke] demo-noisy-microservice-customer-dashboard=200
[2026-05-03T22:07:47Z] [0015_smoke] done
[2026-05-03T22:15:16Z] [0015_smoke] start

=== pytest ===
..............................                                           [100%]
30 passed in 0.62s
[2026-05-03T22:15:17Z] [0015_smoke] pytest exit=0

=== /api/v1/health ===
[2026-05-03T22:15:17Z] [0015_smoke] health=200

=== reseed demo dashboards ===
[2026-05-03T22:15:50Z] [0015_smoke] seed black-friday-outage=200
[2026-05-03T22:16:19Z] [0015_smoke] seed credential-stuffing=200
[2026-05-03T22:16:46Z] [0015_smoke] seed noisy-microservice=200

=== verify all 6 dashboards live ===
[2026-05-03T22:16:47Z] [0015_smoke] demo-black-friday-outage-dashboard=200
[2026-05-03T22:16:48Z] [0015_smoke] demo-black-friday-outage-customer-dashboard=200
[2026-05-03T22:16:49Z] [0015_smoke] demo-credential-stuffing-dashboard=200
[2026-05-03T22:16:51Z] [0015_smoke] demo-credential-stuffing-customer-dashboard=200
[2026-05-03T22:16:52Z] [0015_smoke] demo-noisy-microservice-dashboard=200
[2026-05-03T22:16:54Z] [0015_smoke] demo-noisy-microservice-customer-dashboard=200
[2026-05-03T22:16:54Z] [0015_smoke] done
```

### 0100_audit

```
[2026-05-03T23:00:54Z] [0100_audit] start

=== em/en dash sweep ===
[2026-05-03T23:00:54Z] [0100_audit] unicode dashes in source=0

=== python compile check ===
[2026-05-03T23:00:54Z] [0100_audit] compile exit=0

=== live dashboards: panel inline-data audit ===
[2026-05-03T23:00:55Z] [0100_audit] demo-black-friday-outage-dashboard: panels=9 md=4 vega_inline=5 vega_url=0 dashes=0
[2026-05-03T23:00:56Z] [0100_audit] demo-black-friday-outage-customer-dashboard: panels=9 md=4 vega_inline=5 vega_url=0 dashes=0
[2026-05-03T23:00:57Z] [0100_audit] demo-credential-stuffing-dashboard: panels=11 md=5 vega_inline=6 vega_url=0 dashes=0
[2026-05-03T23:00:59Z] [0100_audit] demo-credential-stuffing-customer-dashboard: panels=11 md=5 vega_inline=6 vega_url=0 dashes=0
[2026-05-03T23:01:00Z] [0100_audit] demo-noisy-microservice-dashboard: panels=8 md=3 vega_inline=5 vega_url=0 dashes=0
[2026-05-03T23:01:02Z] [0100_audit] demo-noisy-microservice-customer-dashboard: panels=8 md=3 vega_inline=5 vega_url=0 dashes=0

=== audit log size ===
      41 runtime/audit.jsonl
[2026-05-03T23:01:02Z] [0100_audit] done
```

### 0200_keepalive

```

=== backend health ===
[2026-05-04T00:00:02Z] [0200_keepalive] backend=200

=== ngrok tunnel reachability ===
[2026-05-04T00:00:02Z] [0200_keepalive] ngrok=200

=== workflow status ===
{"ok":true,"registered":true,"rule_id":"f1424106-270b-472d-ac97-640a609489e0","connector_id":"80ed37e4-fad4-4b08-a03a-b0e95726f2e5","rule_status":"registered","connector_status":"registered","inbox_index":"fec-transcript-inbox","inbox_exists":true,"webhook_url":"https://headlamp-squatting-usable.ngrok-free.dev/api/v1/workflows/triggered","ngrok_url":"https://headlamp-squatting-usable.ngrok-free.dev","recent_fires":[]}

=== agent-builder status ===
{"live":true,"kibana_url":"https://fe-summit-hackathon-ed0e8e.kb.us-west-1.aws.found.io","configured_tools":["fec_poc_plan","fec_spl_to_esql","fec_compliance","fec_stack_extract","fec_code_sample","fec_cost_calc","fec_capacity"],"configured_agent":"fec_field_assistant"}

=== elastic indices health ===
health status index                     uuid                   pri rep docs.count docs.deleted store.size pri.store.size dataset.size
green  open   fec-briefs                UdseePqJQxyJoJPAJQrE3A   1   1         47            0    340.5kb        170.2kb      170.2kb
green  open   demo-credstuff-sessions   VHHA85p1QR6KknTp88-lqQ   1   1          6            0     56.1kb           28kb         28kb
green  open   demo-noisy-deployments    XaFPKiNiQ0KTO_16ys7MpA   1   0         25            0     27.7kb         27.7kb       27.7kb
green  open   fec-post-meetings         OR623Y5qQVaXj-X0uB0SAg   1   1         30            0    225.2kb        112.6kb      112.6kb
green  open   fec-transcript-inbox      uT4PsS77Q2GAmiSP6PoqUA   1   1          0            0      3.9kb           247b         247b
green  open   demo-blackfriday-apm      ys-VJVTNTe6uNTr9tof6pA   1   1       1500            0      1.3mb        696.3kb      696.3kb
green  open   fec-audit                 0PsAyq7SQ8y85pKVIA7Q8g   1   1         29            0    103.4kb         51.7kb       51.7kb
green  open   demo-blackfriday-metrics  _ESRxbR-TqyE-P4mbIOlig   1   1        600            0    355.1kb        177.5kb      177.5kb
green  open   demo-credstuff-iplookup   AmGLCAGKTCK-BwldLLG7pw   1   1         50            0     44.8kb         22.4kb       22.4kb
green  open   demo-blackfriday-checkout SLzcDYznTByR2vKJAJ7uGg   1   1       3500            0      4.2mb          2.1mb        2.1mb
green  open   demo-noisy-traces         aS5LMDNMS7KDkQIIwoOjLw   1   0       5500            0      3.5mb          3.5mb        3.5mb
green  open   fec-battlecards           Gl4XNxsRQNuXk4uUvvtHDg   1   1         20            0     40.7kb         20.3kb       20.3kb
green  open   demo-noisy-logs           42ndJZBtQtyoPVbl9BUrKw   1   0       3500            0      1.6mb          1.6mb        1.6mb
green  open   demo-credstuff-auth       BeLd4JukR7ivOQTD-VYZ5A   1   1       3613            0      2.4mb          1.2mb        1.2mb
[2026-05-04T00:00:04Z] [0200_keepalive] done
```

### 0300_screenshots

```
[2026-05-04T01:00:04Z] [0300_screenshots] start
[20505:7448392:0504/030011.390163:ERROR:google_apis/gcm/engine/registration_request.cc:291] Registration response error message: DEPRECATED_ENDPOINT
Trying to load the allocator multiple times. This is *not* supported.
751693 bytes written to file /Users/rodrigocareaga/Downloads/FE-Elastic/docs/screenshots/dashboard.png
[2026-05-04T01:00:12Z] [0300_screenshots] captured dashboard (751693 bytes)
655489 bytes written to file /Users/rodrigocareaga/Downloads/FE-Elastic/docs/screenshots/tools.png
[2026-05-04T01:00:14Z] [0300_screenshots] captured tools (655489 bytes)
737079 bytes written to file /Users/rodrigocareaga/Downloads/FE-Elastic/docs/screenshots/agent_builder.png
[2026-05-04T01:00:16Z] [0300_screenshots] captured agent_builder (737079 bytes)
901787 bytes written to file /Users/rodrigocareaga/Downloads/FE-Elastic/docs/screenshots/demo_data.png
[2026-05-04T01:00:18Z] [0300_screenshots] captured demo_data (901787 bytes)
[20693:7450168:0504/030019.057351:ERROR:base/process/process_mac.cc:53] task_policy_set TASK_CATEGORY_POLICY: (os/kern) invalid argument (4)
[20693:7450168:0504/030019.057379:ERROR:base/process/process_mac.cc:98] task_policy_set TASK_SUPPRESSION_POLICY: (os/kern) invalid argument (4)
Trying to load the allocator multiple times. This is *not* supported.
738319 bytes written to file /Users/rodrigocareaga/Downloads/FE-Elastic/docs/screenshots/workflow_demo.png
[20693:7450154:0504/030021.003764:ERROR:google_apis/gcm/engine/registration_request.cc:291] Registration response error message: DEPRECATED_ENDPOINT
[20693:7450131:0504/030021.004072:ERROR:chrome/browser/web_applications/os_integration/os_integration_manager.cc:257] Can't perform OS integration while the browser is shutting down.
[20693:7450131:0504/030021.027046:ERROR:chrome/browser/web_applications/externally_managed_app_manager.cc:680] https://www.youtube.com/s/notifications/manifest/cr_install.html from install source 1 failed to install with reason 21
[2026-05-04T01:00:21Z] [0300_screenshots] captured workflow_demo (738319 bytes)
Trying to load the allocator multiple times. This is *not* supported.
[20732:7450643:0504/030023.796180:ERROR:google_apis/gcm/engine/registration_request.cc:291] Registration response error message: DEPRECATED_ENDPOINT
767317 bytes written to file /Users/rodrigocareaga/Downloads/FE-Elastic/docs/screenshots/meeting_revolut.png
[2026-05-04T01:00:24Z] [0300_screenshots] captured meeting_revolut (767317 bytes)
564025 bytes written to file /Users/rodrigocareaga/Downloads/FE-Elastic/docs/screenshots/meeting_meli.png
[2026-05-04T01:00:26Z] [0300_screenshots] captured meeting_meli (564025 bytes)
Trying to load the allocator multiple times. This is *not* supported.
[20790:7451479:0504/030029.633226:ERROR:google_apis/gcm/engine/registration_request.cc:291] Registration response error message: DEPRECATED_ENDPOINT
562592 bytes written to file /Users/rodrigocareaga/Downloads/FE-Elastic/docs/screenshots/meeting_santander.png
[2026-05-04T01:00:29Z] [0300_screenshots] captured meeting_santander (562592 bytes)
[2026-05-04T01:00:29Z] [0300_screenshots] done
```

### 0400_ab_smoke

```
[2026-05-04T02:00:30Z] [0400_ab_smoke] start

=== tool-use prompts ===
[2026-05-04T02:00:51Z] [0400_ab_smoke] [spl] len=910 steps=2 ttft=17123
[2026-05-04T02:01:13Z] [0400_ab_smoke] [cost] len=1010 steps=2 ttft=18695
[2026-05-04T02:02:02Z] [0400_ab_smoke] [compliance] len=7330 steps=2 ttft=31373
[2026-05-04T02:02:02Z] [0400_ab_smoke] done
```

### 0500_data_integrity

```
{"ts": "2026-05-03T19:48:56.501466+00:00", "model": "claude-haiku-4-5", "mode": "live", "input_tokens": 741, "output_tokens": 209, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0, "agent": "live_meeting", "meeting_id": "northwind-mtg-prev-001", "speaker": "Rodrigo (Elastic FE)"}
{"ts": "2026-05-03T19:48:59.758097+00:00", "model": "claude-haiku-4-5", "mode": "live", "input_tokens": 767, "output_tokens": 179, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0, "agent": "live_meeting", "meeting_id": "northwind-mtg-prev-001", "speaker": "Sarah Chen (Northwind Pay VP Engineering)"}
{"ts": "2026-05-03T19:49:03.301898+00:00", "model": "claude-haiku-4-5", "mode": "live", "input_tokens": 784, "output_tokens": 229, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0, "agent": "live_meeting", "meeting_id": "northwind-mtg-prev-001", "speaker": "Mike Taylor (Northwind Pay Platform Lead)"}
{"ts": "2026-05-03T19:49:07.246162+00:00", "model": "claude-haiku-4-5", "mode": "live", "input_tokens": 742, "output_tokens": 183, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0, "agent": "live_meeting", "meeting_id": "northwind-mtg-prev-001", "speaker": "Rodrigo (Elastic FE)"}
{"ts": "2026-05-03T19:49:10.424980+00:00", "model": "claude-haiku-4-5", "mode": "live", "input_tokens": 729, "output_tokens": 183, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0, "agent": "live_meeting", "meeting_id": "northwind-mtg-prev-001", "speaker": "Sarah Chen (Northwind Pay VP Engineering)"}
{"ts": "2026-05-03T19:49:13.997477+00:00", "model": "claude-haiku-4-5", "mode": "live", "input_tokens": 723, "output_tokens": 179, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0, "agent": "live_meeting", "meeting_id": "northwind-mtg-prev-001", "speaker": "Rodrigo (Elastic FE)"}
{"ts": "2026-05-03T19:49:17.607694+00:00", "model": "claude-haiku-4-5", "mode": "live", "input_tokens": 740, "output_tokens": 126, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0, "agent": "live_meeting", "meeting_id": "northwind-mtg-prev-001", "speaker": "Mike Taylor (Northwind Pay Platform Lead)"}
{"ts": "2026-05-03T19:49:20.301315+00:00", "model": "claude-haiku-4-5", "mode": "live", "input_tokens": 749, "output_tokens": 174, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0, "agent": "live_meeting", "meeting_id": "northwind-mtg-prev-001", "speaker": "Rodrigo (Elastic FE)"}
{"ts": "2026-05-03T19:49:23.532508+00:00", "model": "claude-haiku-4-5", "mode": "live", "input_tokens": 768, "output_tokens": 137, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0, "agent": "live_meeting", "meeting_id": "northwind-mtg-prev-001", "speaker": "Sarah Chen (Northwind Pay VP Engineering)"}
{"ts": "2026-05-03T19:49:26.564797+00:00", "model": "claude-haiku-4-5", "mode": "live", "input_tokens": 753, "output_tokens": 120, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0, "agent": "live_meeting", "meeting_id": "northwind-mtg-prev-001", "speaker": "Rodrigo (Elastic FE)"}
{"ts": "2026-05-03T19:49:47.590129+00:00", "model": "claude-haiku-4-5", "mode": "live", "input_tokens": 2476, "output_tokens": 2782, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0, "agent": "tool_compliance", "tool": "compliance_mapping", "regulations": ["DORA", "FCA SYSC", "PCI DSS", "GDPR"], "industry": "UK retail bank"}
{"ts": "2026-05-03T19:50:23.078510+00:00", "model": "claude-haiku-4-5", "mode": "live", "input_tokens": 2315, "output_tokens": 195, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0, "agent": "tool_stack_extract", "tool": "stack_extract"}
{"ts": "2026-05-03T19:52:21.901519+00:00", "model": "claude-haiku-4-5", "mode": "live", "input_tokens": 2466, "output_tokens": 1541, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0, "agent": "tool_compliance", "tool": "compliance_mapping", "regulations": ["DORA", "PCI DSS"], "industry": "UK retail bank"}
{"ts": "2026-05-03T20:08:23.441508+00:00", "model": "claude-sonnet-4-6", "mode": "live", "input_tokens": 2109, "output_tokens": 4096, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0, "agent": "pre_meeting", "meeting_id": "northwind-mtg-prev-001", "company_id": "northwind"}
{"ts": "2026-05-03T20:14:32.900196+00:00", "model": "claude-sonnet-4-6", "mode": "live", "input_tokens": 2109, "output_tokens": 4096, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0, "agent": "pre_meeting", "meeting_id": "northwind-mtg-prev-001", "company_id": "northwind"}
{"ts": "2026-05-03T21:35:42.617873+00:00", "model": "claude-haiku-4-5", "mode": "ad_hoc", "input_tokens": 925, "output_tokens": 1484, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0, "agent": "pre_meeting", "company_name": "Northwind Pay", "meeting_id": "ad-hoc-northwind-20260503-213542"}
{"ts": "2026-05-03T21:37:10.437005+00:00", "model": "claude-opus-4-7", "mode": "ad_hoc", "input_tokens": 1213, "output_tokens": 2004, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0, "agent": "pre_meeting", "company_name": "Ray-Ban", "meeting_id": "ad-hoc-ray-ban-20260503-213710"}
{"ts": "2026-05-03T21:38:38.752966+00:00", "model": "claude-haiku-4-5", "mode": "live", "input_tokens": 2189, "output_tokens": 65, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0, "agent": "tool_stack_extract", "tool": "stack_extract"}
{"ts": "2026-05-04T02:00:35.247775+00:00", "model": "claude-haiku-4-5", "mode": "live", "input_tokens": 1339, "output_tokens": 354, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0, "agent": "tool_spl_esql", "tool": "spl_to_esql"}
{"ts": "2026-05-04T02:01:17.639465+00:00", "model": "claude-haiku-4-5", "mode": "live", "input_tokens": 2466, "output_tokens": 1821, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0, "agent": "tool_compliance", "tool": "compliance_mapping", "regulations": ["DORA", "PCI DSS"], "industry": "UK retail bank"}

=== salesforce log size ===
      27 runtime/salesforce.log

=== workflow recent fires ===
{
    "ok": true,
    "fires": []
}
[2026-05-04T03:00:03Z] [0500_data_integrity] done
```

### 0600_docs

```
backend/app/agents/prompts/tools.py
backend/app/agents/schemas.py
backend/app/api/__init__.py
backend/app/api/routes_agent_builder.py
backend/app/api/routes_agents.py
backend/app/api/routes_audit.py
backend/app/api/routes_battlecards.py
backend/app/api/routes_briefs.py
backend/app/api/routes_calendar.py
backend/app/api/routes_demo_data.py
backend/app/api/routes_health.py
backend/app/api/routes_kibana.py
backend/app/api/routes_mcp.py
backend/app/api/routes_meetings.py
backend/app/api/routes_salesforce.py
backend/app/api/routes_tools.py
backend/app/api/routes_workflows.py
backend/app/config.py
backend/app/integrations/__init__.py
backend/app/integrations/agent_builder.py
backend/app/integrations/calendar_mock.py
backend/app/integrations/claude_client.py
backend/app/integrations/elasticsearch_client.py
backend/app/integrations/google_calendar_mock.py
backend/app/integrations/kibana_client.py

=== calling claude -p (one-shot, max-turns 1) ===
/Users/rodrigocareaga/Downloads/FE-Elastic/runtime/overnight/batches/0600_docs.sh: line 47: timeout: command not found
[2026-05-04T04:00:03Z] [0600_docs] claude exit=127
[2026-05-04T04:00:03Z] [0600_docs] done
```

## Screenshots captured

drwxr-xr-x  10 rodrigocareaga  staff     320 May  4 03:00 .
drwxr-xr-x@  8 rodrigocareaga  staff     256 May  4 07:00 ..
-rw-r--r--@  1 rodrigocareaga  staff  737079 May  4 03:00 agent_builder.png
-rw-r--r--@  1 rodrigocareaga  staff  751693 May  4 03:00 dashboard.png
-rw-r--r--@  1 rodrigocareaga  staff  901787 May  4 03:00 demo_data.png
-rw-r--r--@  1 rodrigocareaga  staff  564025 May  4 03:00 meeting_meli.png
-rw-r--r--@  1 rodrigocareaga  staff  767317 May  4 03:00 meeting_revolut.png
-rw-r--r--@  1 rodrigocareaga  staff  562592 May  4 03:00 meeting_santander.png
-rw-r--r--@  1 rodrigocareaga  staff  655489 May  4 03:00 tools.png
-rw-r--r--@  1 rodrigocareaga  staff  738319 May  4 03:00 workflow_demo.png

## Git status

```
c8158c4 Inject post-meeting record into Field Assistant preamble
84f020c Fix four UX bugs: noisy seed URL, ad-hoc dashboard, model status, drive copy
30b814d Split each scenario into [FE] and [Customer] dashboards with shared inline-data charts
1073212 Inline-data Vega for Black Friday: bypass Kibana data fetcher entirely
3749a3e Rewrite Black Friday Vega panels with simpler specs that render
f827cf4 Strip em dash from all source files
c6c6780 Fix Black Friday Vega specs that returned 400 from Elasticsearch
75330c9 Demo Data Generator (3 scenarios) + Kibana Workflow trigger + dashboard fix
c94b751 Meeting page: model selector, contextual AB chats, Kibana dashboard creator
65e107a P1: Agent Builder chat UI, ES API key auth, longer converse timeout
b47f5aa Agent Builder live: MCP server + 7 tools registered in Kibana 9.3
b535525 FE Copilot baseline: 3 agents, 7 tools, Agent Builder scaffold
```
