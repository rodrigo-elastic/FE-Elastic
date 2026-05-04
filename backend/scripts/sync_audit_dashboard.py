"""
filename: sync_audit_dashboard.py
description: Idempotent sync of the "FE Copilot - Self Observability" Kibana dashboard. Builds a data view (fec-audit-dv) over the fec-audit index and a single dashboard (fec-audit-self-observability) made of one Markdown header, three Lens KPIs, two Lens line charts, one Lens bar chart, two Lens datatables, and one Markdown narrative footer. Each Lens panel is wrapped in try/except; if a Lens spec build raises, that slot is replaced by a Markdown placeholder so the dashboard always renders. Run with: PYTHONPATH=backend .venv/bin/python -m scripts.sync_audit_dashboard.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
import sys
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx

from app.config import settings
from app.utils.logging import get_logger

log = get_logger(__name__)


# ============================================================ Constants =============

AUDIT_INDEX = "fec-audit"
DATA_VIEW_ID = "fec-audit-dv"
DASHBOARD_ID = "fec-audit-self-observability"
DASHBOARD_TITLE = "FE Copilot - Self Observability"
KIBANA_VERSION = "9.3.4"

# The audit index uses "ts" (ISO 8601 string mapped as date), not "@timestamp",
# because that is the field shape produced by app.integrations.claude_client._audit.
# Documented in docs/audit-dashboard.md and in the dashboard's narrative panel.
TIME_FIELD = "ts"


# ============================================================ Kibana helpers ========


def _kbn_url(path: str) -> str:
    return settings.kibana_url.rstrip("/") + path


def _kbn_headers() -> Dict[str, str]:
    return {
        "Authorization": f"ApiKey {settings.kibana_api_key}",
        "Content-Type": "application/json",
        "kbn-xsrf": "fe-copilot",
    }


def _dashboard_url(dashboard_id: str) -> str:
    return settings.kibana_url.rstrip("/") + f"/app/dashboards#/view/{dashboard_id}"


# ============================================================ Data view =============


def _ensure_data_view(client: httpx.Client) -> Optional[str]:
    """GET-then-POST. Returns the data view id on success, or None on failure.

    The fec-audit index uses "ts" (date) as its timestamp field.
    """
    get_url = _kbn_url(f"/api/data_views/data_view/{DATA_VIEW_ID}")
    post_url = _kbn_url("/api/data_views/data_view")
    delete_url = _kbn_url(f"/api/data_views/data_view/{DATA_VIEW_ID}")

    # Best-effort delete so a stale data view with a different timeFieldName
    # is replaced. Failure here is fine; POST below will still try.
    try:
        client.delete(delete_url, headers=_kbn_headers())
    except Exception:
        pass

    body = {
        "data_view": {
            "id": DATA_VIEW_ID,
            "name": AUDIT_INDEX,
            "title": AUDIT_INDEX,
            "timeFieldName": TIME_FIELD,
        },
        "override": True,
    }
    try:
        resp = client.post(post_url, headers=_kbn_headers(), json=body)
        if resp.status_code in (200, 201):
            return DATA_VIEW_ID
        if resp.status_code == 409:
            return DATA_VIEW_ID
        log.warning("audit_dashboard.data_view.failed",
                    status=resp.status_code, body=resp.text[:300])
        # Last chance: GET. If it exists from a prior run, use it.
        resp_get = client.get(get_url, headers=_kbn_headers())
        if resp_get.status_code == 200:
            return DATA_VIEW_ID
        return None
    except Exception as exc:
        log.warning("audit_dashboard.data_view.exception", error=str(exc))
        return None


# ============================================================ Audit doc count =======


def _audit_doc_count(client: httpx.Client) -> int:
    """Best-effort count of fec-audit. The dashboard renders cleanly even at zero."""
    if not (settings.elasticsearch_api_key or settings.elasticsearch_password):
        return 0
    try:
        url = settings.elasticsearch_url.rstrip("/") + f"/{AUDIT_INDEX}/_count"
        if settings.elasticsearch_api_key:
            headers = {"Authorization": f"ApiKey {settings.elasticsearch_api_key}"}
        else:
            import base64
            cred = f"{settings.elasticsearch_username}:{settings.elasticsearch_password}"
            headers = {"Authorization": "Basic " + base64.b64encode(cred.encode()).decode()}
        resp = client.get(url, headers=headers)
        if resp.status_code == 200:
            return int(resp.json().get("count", 0))
    except Exception as exc:
        log.warning("audit_dashboard.count.exception", error=str(exc))
    return 0


# ============================================================ Markdown panels =======


def _markdown_panel(panel_id: str, x: int, y: int, w: int, h: int, markdown: str,
                    title: str = "") -> Dict[str, Any]:
    """By-value markdown panel wrapped in the legacy visualization embeddable.

    Kibana 9.x does not register a top-level "markdown" embeddable factory;
    markdown panels must be wrapped as type "visualization" with savedVis.type
    "markdown" so the visualization embeddable picks them up.
    """
    return {
        "type": "visualization",
        "panelIndex": panel_id,
        "gridData": {"x": x, "y": y, "w": w, "h": h, "i": panel_id},
        "version": KIBANA_VERSION,
        "embeddableConfig": {
            "enhancements": {},
            "savedVis": {
                "type": "markdown",
                "title": title,
                "description": "",
                "params": {"fontSize": 12, "openLinksInNewTab": True, "markdown": markdown},
                "uiState": {},
                "data": {
                    "aggs": [],
                    "searchSource": {"query": {"language": "kuery", "query": ""}, "filter": []},
                },
            },
        },
        "title": title,
    }


def _md_header() -> str:
    return (
        "## FE Copilot self-observability\n\n"
        "_Elastic monitoring Elastic. Every Claude API call this app makes is "
        "indexed into `fec-audit` from `app.integrations.claude_client._audit`. "
        "This dashboard reads that index live so a Field Engineer can answer "
        "questions like 'how much did this demo cost?', 'which tool was the "
        "noisiest?', and 'are we burning Opus tokens when Haiku would do?' "
        "without ever leaving Kibana._\n\n"
        "**Time field:** `ts` (ISO 8601, mapped as `date`)  \n"
        "**Index:** `fec-audit`  \n"
        "**Data view:** `fec-audit-dv`"
    )


def _md_narrative() -> str:
    return (
        "## What this dashboard tells you\n\n"
        "**Cost per pipeline run.** Total tokens last 7 days times the "
        "model price gives the cash burn for the demo. Use the "
        "_tokens by model_ chart to spot when an Opus call ran where a "
        "Haiku call would have been enough.\n\n"
        "**Slow tools.** The _top tools by call count_ bar chart and the "
        "_tool x avg tokens_ table together identify which tool is the "
        "fattest hog of input tokens. The latency line chart will populate "
        "once `latency_ms` lands in the audit writer (currently structural).\n\n"
        "**Mock vs live mix.** The _mock-mode %_ KPI distinguishes offline "
        "demo runs (mode=`mock`, zero tokens) from real Anthropic calls "
        "(mode=`live`, real token counts). A high mock rate during a "
        "judge-facing demo means the API key was misconfigured, not that "
        "the agents are cheap.\n\n"
        "**Field shape this dashboard assumes** (validated against "
        "`fec-audit/_mapping`):\n\n"
        "- `ts` (date) - call timestamp\n"
        "- `model` (keyword) - claude-opus-4-7, claude-haiku-4-5, etc.\n"
        "- `mode` (keyword) - `live` or `mock`\n"
        "- `input_tokens`, `output_tokens` (long) - raw token usage\n"
        "- `cache_read_input_tokens`, `cache_creation_input_tokens` "
        "(long) - prompt-cache accounting\n"
        "- `agent` (keyword) - the calling agent or tool wrapper\n"
        "- `tool` (text + tool.keyword) - the tool name when applicable\n"
        "- `meeting_id`, `company_id` (keyword) - call provenance\n\n"
        "_Dashboard generated by `backend/scripts/sync_audit_dashboard.py`. "
        "Re-run that script to recreate (it deletes and rebuilds in place)._"
    )


def _md_placeholder(panel_label: str, reason: str) -> str:
    return (
        f"## {panel_label}\n\n"
        f"_Lens panel build failed; structural placeholder shown so the "
        f"dashboard layout stays intact. Reason: {reason}_"
    )


# ============================================================ Lens helpers ==========


def _lens_panel_wrapper(panel_id: str, x: int, y: int, w: int, h: int,
                        title: str, attributes: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": "lens",
        "panelIndex": panel_id,
        "gridData": {"x": x, "y": y, "w": w, "h": h, "i": panel_id},
        "version": KIBANA_VERSION,
        "embeddableConfig": {
            "enhancements": {},
            "attributes": attributes,
        },
        "title": title,
    }


def _lens_references(dv_id: str) -> List[Dict[str, str]]:
    return [{
        "name": "indexpattern-datasource-layer-layer1",
        "type": "index-pattern",
        "id": dv_id,
    }]


# ----- KPI metric ----------------------------------------------------------


def _lens_kpi_count(panel_id: str, x: int, y: int, w: int, h: int,
                   title: str, dv_id: str) -> Dict[str, Any]:
    """Total Claude API calls in the dashboard time window. count() over docs."""
    attributes = {
        "title": title,
        "description": "Total Claude API calls captured in fec-audit.",
        "visualizationType": "lnsLegacyMetric",
        "type": "lens",
        "references": _lens_references(dv_id),
        "state": {
            "datasourceStates": {
                "formBased": {
                    "layers": {
                        "layer1": {
                            "columnOrder": ["metric_col"],
                            "columns": {
                                "metric_col": {
                                    "label": "Claude API calls",
                                    "dataType": "number",
                                    "operationType": "count",
                                    "sourceField": "___records___",
                                    "isBucketed": False,
                                    "scale": "ratio",
                                    "params": {"format": {"id": "number",
                                                            "params": {"decimals": 0}}},
                                },
                            },
                            "incompleteColumns": {},
                        },
                    },
                },
            },
            "visualization": {
                "layerId": "layer1",
                "accessor": "metric_col",
                "layerType": "data",
                "textAlign": "center",
                "titlePosition": "bottom",
                "size": "xl",
            },
            "filters": [],
            "query": {"language": "kuery", "query": ""},
        },
    }
    return _lens_panel_wrapper(panel_id, x, y, w, h, title, attributes)


def _lens_kpi_total_tokens(panel_id: str, x: int, y: int, w: int, h: int,
                           title: str, dv_id: str) -> Dict[str, Any]:
    """Total tokens consumed (input + output) using a formula column."""
    attributes = {
        "title": title,
        "description": "Sum of input_tokens + output_tokens across all calls.",
        "visualizationType": "lnsLegacyMetric",
        "type": "lens",
        "references": _lens_references(dv_id),
        "state": {
            "datasourceStates": {
                "formBased": {
                    "layers": {
                        "layer1": {
                            "columnOrder": ["metric_col_formulaX0",
                                             "metric_col_formulaX1",
                                             "metric_col"],
                            "columns": {
                                "metric_col_formulaX0": {
                                    "label": "Part of input + output tokens",
                                    "dataType": "number",
                                    "operationType": "sum",
                                    "sourceField": "input_tokens",
                                    "isBucketed": False,
                                    "scale": "ratio",
                                    "customLabel": True,
                                },
                                "metric_col_formulaX1": {
                                    "label": "Part of input + output tokens",
                                    "dataType": "number",
                                    "operationType": "sum",
                                    "sourceField": "output_tokens",
                                    "isBucketed": False,
                                    "scale": "ratio",
                                    "customLabel": True,
                                },
                                "metric_col": {
                                    "label": "Total tokens",
                                    "dataType": "number",
                                    "operationType": "formula",
                                    "isBucketed": False,
                                    "scale": "ratio",
                                    "params": {
                                        "formula": "sum(input_tokens) + sum(output_tokens)",
                                        "isFormulaBroken": False,
                                        "format": {"id": "number",
                                                    "params": {"decimals": 0}},
                                    },
                                    "references": ["metric_col_formulaX0",
                                                    "metric_col_formulaX1"],
                                    "customLabel": True,
                                },
                            },
                            "incompleteColumns": {},
                        },
                    },
                },
            },
            "visualization": {
                "layerId": "layer1",
                "accessor": "metric_col",
                "layerType": "data",
                "textAlign": "center",
                "titlePosition": "bottom",
                "size": "xl",
            },
            "filters": [],
            "query": {"language": "kuery", "query": ""},
        },
    }
    return _lens_panel_wrapper(panel_id, x, y, w, h, title, attributes)


def _lens_kpi_mock_pct(panel_id: str, x: int, y: int, w: int, h: int,
                       title: str, dv_id: str) -> Dict[str, Any]:
    """Mock-mode percentage = count(mode:'mock') / count() * 100, via formula."""
    attributes = {
        "title": title,
        "description": "Share of calls executed in mock mode (no Anthropic key).",
        "visualizationType": "lnsLegacyMetric",
        "type": "lens",
        "references": _lens_references(dv_id),
        "state": {
            "datasourceStates": {
                "formBased": {
                    "layers": {
                        "layer1": {
                            "columnOrder": ["metric_col_formulaX0",
                                             "metric_col_formulaX1",
                                             "metric_col"],
                            "columns": {
                                "metric_col_formulaX0": {
                                    "label": "Part of mock %",
                                    "dataType": "number",
                                    "operationType": "count",
                                    "sourceField": "___records___",
                                    "isBucketed": False,
                                    "scale": "ratio",
                                    "filter": {"language": "kuery",
                                                "query": "mode : \"mock\""},
                                    "customLabel": True,
                                },
                                "metric_col_formulaX1": {
                                    "label": "Part of mock %",
                                    "dataType": "number",
                                    "operationType": "count",
                                    "sourceField": "___records___",
                                    "isBucketed": False,
                                    "scale": "ratio",
                                    "customLabel": True,
                                },
                                "metric_col": {
                                    "label": "Mock mode %",
                                    "dataType": "number",
                                    "operationType": "formula",
                                    "isBucketed": False,
                                    "scale": "ratio",
                                    "params": {
                                        "formula": "count(kql='mode : \"mock\"') / count() * 100",
                                        "isFormulaBroken": False,
                                        "format": {"id": "number",
                                                    "params": {"decimals": 1,
                                                                "suffix": " %"}},
                                    },
                                    "references": ["metric_col_formulaX0",
                                                    "metric_col_formulaX1"],
                                    "customLabel": True,
                                },
                            },
                            "incompleteColumns": {},
                        },
                    },
                },
            },
            "visualization": {
                "layerId": "layer1",
                "accessor": "metric_col",
                "layerType": "data",
                "textAlign": "center",
                "titlePosition": "bottom",
                "size": "xl",
            },
            "filters": [],
            "query": {"language": "kuery", "query": ""},
        },
    }
    return _lens_panel_wrapper(panel_id, x, y, w, h, title, attributes)


# ----- Line charts ---------------------------------------------------------


def _lens_tokens_by_model(panel_id: str, x: int, y: int, w: int, h: int,
                          title: str, dv_id: str) -> Dict[str, Any]:
    """Stacked line: total tokens (input+output) over time, split by model."""
    attributes = {
        "title": title,
        "description": "Total tokens (input + output) over time, split by model.",
        "visualizationType": "lnsXY",
        "type": "lens",
        "references": _lens_references(dv_id),
        "state": {
            "datasourceStates": {
                "formBased": {
                    "layers": {
                        "layer1": {
                            "columnOrder": ["x_col", "split_col",
                                             "metric_col_formulaX0",
                                             "metric_col_formulaX1",
                                             "metric_col"],
                            "columns": {
                                "x_col": {
                                    "label": "ts",
                                    "dataType": "date",
                                    "operationType": "date_histogram",
                                    "sourceField": TIME_FIELD,
                                    "isBucketed": True,
                                    "scale": "interval",
                                    "params": {"interval": "auto",
                                                "includeEmptyRows": True,
                                                "dropPartials": False},
                                },
                                "split_col": {
                                    "label": "Top values of model",
                                    "dataType": "string",
                                    "operationType": "terms",
                                    "sourceField": "model",
                                    "isBucketed": True,
                                    "scale": "ordinal",
                                    "params": {
                                        "size": 5,
                                        "orderBy": {"type": "column",
                                                     "columnId": "metric_col"},
                                        "orderDirection": "desc",
                                        "otherBucket": False,
                                        "missingBucket": False,
                                        "parentFormat": {"id": "terms"},
                                    },
                                },
                                "metric_col_formulaX0": {
                                    "label": "Part of total tokens",
                                    "dataType": "number",
                                    "operationType": "sum",
                                    "sourceField": "input_tokens",
                                    "isBucketed": False,
                                    "scale": "ratio",
                                    "customLabel": True,
                                },
                                "metric_col_formulaX1": {
                                    "label": "Part of total tokens",
                                    "dataType": "number",
                                    "operationType": "sum",
                                    "sourceField": "output_tokens",
                                    "isBucketed": False,
                                    "scale": "ratio",
                                    "customLabel": True,
                                },
                                "metric_col": {
                                    "label": "Total tokens",
                                    "dataType": "number",
                                    "operationType": "formula",
                                    "isBucketed": False,
                                    "scale": "ratio",
                                    "params": {
                                        "formula": "sum(input_tokens) + sum(output_tokens)",
                                        "isFormulaBroken": False,
                                        "format": {"id": "number",
                                                    "params": {"decimals": 0}},
                                    },
                                    "references": ["metric_col_formulaX0",
                                                    "metric_col_formulaX1"],
                                    "customLabel": True,
                                },
                            },
                            "incompleteColumns": {},
                        },
                    },
                },
            },
            "visualization": {
                "preferredSeriesType": "line",
                "layers": [
                    {
                        "layerId": "layer1",
                        "accessors": ["metric_col"],
                        "position": "top",
                        "seriesType": "line",
                        "showGridlines": False,
                        "layerType": "data",
                        "xAccessor": "x_col",
                        "splitAccessor": "split_col",
                    },
                ],
                "title": title,
                "legend": {"isVisible": True, "position": "right"},
                "valueLabels": "hide",
                "fittingFunction": "Linear",
                "axisTitlesVisibilitySettings": {"x": True, "yLeft": True,
                                                  "yRight": True},
                "tickLabelsVisibilitySettings": {"x": True, "yLeft": True,
                                                  "yRight": True},
                "labelsOrientation": {"x": 0, "yLeft": 0, "yRight": 0},
                "gridlinesVisibilitySettings": {"x": True, "yLeft": True,
                                                "yRight": True},
            },
            "filters": [],
            "query": {"language": "kuery", "query": ""},
        },
    }
    return _lens_panel_wrapper(panel_id, x, y, w, h, title, attributes)


def _lens_p95_latency_by_agent(panel_id: str, x: int, y: int, w: int, h: int,
                                title: str, dv_id: str) -> Dict[str, Any]:
    """p95 of latency_ms over time, split by agent. Field is structural; the
    panel renders empty until `latency_ms` is added to the audit writer."""
    attributes = {
        "title": title,
        "description": "p95 of latency_ms over time, split by agent.",
        "visualizationType": "lnsXY",
        "type": "lens",
        "references": _lens_references(dv_id),
        "state": {
            "datasourceStates": {
                "formBased": {
                    "layers": {
                        "layer1": {
                            "columnOrder": ["x_col", "split_col", "metric_col"],
                            "columns": {
                                "x_col": {
                                    "label": "ts",
                                    "dataType": "date",
                                    "operationType": "date_histogram",
                                    "sourceField": TIME_FIELD,
                                    "isBucketed": True,
                                    "scale": "interval",
                                    "params": {"interval": "auto",
                                                "includeEmptyRows": True,
                                                "dropPartials": False},
                                },
                                "split_col": {
                                    "label": "Top values of agent",
                                    "dataType": "string",
                                    "operationType": "terms",
                                    "sourceField": "agent",
                                    "isBucketed": True,
                                    "scale": "ordinal",
                                    "params": {
                                        "size": 8,
                                        "orderBy": {"type": "column",
                                                     "columnId": "metric_col"},
                                        "orderDirection": "desc",
                                        "otherBucket": False,
                                        "missingBucket": False,
                                        "parentFormat": {"id": "terms"},
                                    },
                                },
                                "metric_col": {
                                    "label": "p95 of latency_ms",
                                    "dataType": "number",
                                    "operationType": "percentile",
                                    "sourceField": "latency_ms",
                                    "isBucketed": False,
                                    "scale": "ratio",
                                    "params": {
                                        "percentile": 95,
                                        "format": {"id": "number",
                                                    "params": {"decimals": 0,
                                                                "suffix": " ms"}},
                                    },
                                },
                            },
                            "incompleteColumns": {},
                        },
                    },
                },
            },
            "visualization": {
                "preferredSeriesType": "line",
                "layers": [
                    {
                        "layerId": "layer1",
                        "accessors": ["metric_col"],
                        "position": "top",
                        "seriesType": "line",
                        "showGridlines": False,
                        "layerType": "data",
                        "xAccessor": "x_col",
                        "splitAccessor": "split_col",
                    },
                ],
                "title": title,
                "legend": {"isVisible": True, "position": "right"},
                "valueLabels": "hide",
                "fittingFunction": "Linear",
                "axisTitlesVisibilitySettings": {"x": True, "yLeft": True,
                                                  "yRight": True},
                "tickLabelsVisibilitySettings": {"x": True, "yLeft": True,
                                                  "yRight": True},
                "labelsOrientation": {"x": 0, "yLeft": 0, "yRight": 0},
                "gridlinesVisibilitySettings": {"x": True, "yLeft": True,
                                                "yRight": True},
            },
            "filters": [],
            "query": {"language": "kuery", "query": ""},
        },
    }
    return _lens_panel_wrapper(panel_id, x, y, w, h, title, attributes)


# ----- Bar chart -----------------------------------------------------------


def _lens_top_agents_bar(panel_id: str, x: int, y: int, w: int, h: int,
                         title: str, dv_id: str) -> Dict[str, Any]:
    """Bar chart: top 10 agents by call count. agent is the keyword field that
    backs both raw agents (pre_meeting, post_meeting, live_meeting) and tool
    wrappers (tool_*). count() is the y axis."""
    attributes = {
        "title": title,
        "description": "Top 10 agents and tool wrappers by call count.",
        "visualizationType": "lnsXY",
        "type": "lens",
        "references": _lens_references(dv_id),
        "state": {
            "datasourceStates": {
                "formBased": {
                    "layers": {
                        "layer1": {
                            "columnOrder": ["x_col", "metric_col"],
                            "columns": {
                                "x_col": {
                                    "label": "Top values of agent",
                                    "dataType": "string",
                                    "operationType": "terms",
                                    "sourceField": "agent",
                                    "isBucketed": True,
                                    "scale": "ordinal",
                                    "params": {
                                        "size": 10,
                                        "orderBy": {"type": "column",
                                                     "columnId": "metric_col"},
                                        "orderDirection": "desc",
                                        "otherBucket": False,
                                        "missingBucket": False,
                                        "parentFormat": {"id": "terms"},
                                    },
                                },
                                "metric_col": {
                                    "label": "Calls",
                                    "dataType": "number",
                                    "operationType": "count",
                                    "sourceField": "___records___",
                                    "isBucketed": False,
                                    "scale": "ratio",
                                    "params": {"format": {"id": "number",
                                                            "params": {"decimals": 0}}},
                                },
                            },
                            "incompleteColumns": {},
                        },
                    },
                },
            },
            "visualization": {
                "preferredSeriesType": "bar_horizontal",
                "layers": [
                    {
                        "layerId": "layer1",
                        "accessors": ["metric_col"],
                        "position": "top",
                        "seriesType": "bar_horizontal",
                        "showGridlines": False,
                        "layerType": "data",
                        "xAccessor": "x_col",
                    },
                ],
                "title": title,
                "legend": {"isVisible": False, "position": "right"},
                "valueLabels": "show",
                "fittingFunction": "None",
                "axisTitlesVisibilitySettings": {"x": True, "yLeft": True,
                                                  "yRight": True},
                "tickLabelsVisibilitySettings": {"x": True, "yLeft": True,
                                                  "yRight": True},
                "labelsOrientation": {"x": 0, "yLeft": 0, "yRight": 0},
                "gridlinesVisibilitySettings": {"x": True, "yLeft": True,
                                                "yRight": True},
            },
            "filters": [],
            "query": {"language": "kuery", "query": ""},
        },
    }
    return _lens_panel_wrapper(panel_id, x, y, w, h, title, attributes)


# ----- Tables --------------------------------------------------------------


def _lens_tool_summary_table(panel_id: str, x: int, y: int, w: int, h: int,
                              title: str, dv_id: str) -> Dict[str, Any]:
    """Datatable: agent, calls, avg input tokens, avg output tokens, avg latency.

    Sortable in Kibana out of the box. Latency column will show "0" until
    latency_ms lands in the audit writer; structural placeholder is fine.
    """
    attributes = {
        "title": title,
        "description": "Per-agent token + latency rollup, sortable.",
        "visualizationType": "lnsDatatable",
        "type": "lens",
        "references": _lens_references(dv_id),
        "state": {
            "datasourceStates": {
                "formBased": {
                    "layers": {
                        "layer1": {
                            "columnOrder": ["agent_col", "calls_col",
                                             "in_avg_col", "out_avg_col",
                                             "lat_avg_col"],
                            "columns": {
                                "agent_col": {
                                    "label": "Agent",
                                    "dataType": "string",
                                    "operationType": "terms",
                                    "sourceField": "agent",
                                    "isBucketed": True,
                                    "scale": "ordinal",
                                    "params": {
                                        "size": 50,
                                        "orderBy": {"type": "column",
                                                     "columnId": "calls_col"},
                                        "orderDirection": "desc",
                                        "otherBucket": False,
                                        "missingBucket": False,
                                        "parentFormat": {"id": "terms"},
                                    },
                                },
                                "calls_col": {
                                    "label": "Calls",
                                    "dataType": "number",
                                    "operationType": "count",
                                    "sourceField": "___records___",
                                    "isBucketed": False,
                                    "scale": "ratio",
                                    "params": {"format": {"id": "number",
                                                            "params": {"decimals": 0}}},
                                },
                                "in_avg_col": {
                                    "label": "Avg input tokens",
                                    "dataType": "number",
                                    "operationType": "average",
                                    "sourceField": "input_tokens",
                                    "isBucketed": False,
                                    "scale": "ratio",
                                    "params": {"format": {"id": "number",
                                                            "params": {"decimals": 0}}},
                                },
                                "out_avg_col": {
                                    "label": "Avg output tokens",
                                    "dataType": "number",
                                    "operationType": "average",
                                    "sourceField": "output_tokens",
                                    "isBucketed": False,
                                    "scale": "ratio",
                                    "params": {"format": {"id": "number",
                                                            "params": {"decimals": 0}}},
                                },
                                "lat_avg_col": {
                                    "label": "Avg latency (ms)",
                                    "dataType": "number",
                                    "operationType": "average",
                                    "sourceField": "latency_ms",
                                    "isBucketed": False,
                                    "scale": "ratio",
                                    "params": {"format": {"id": "number",
                                                            "params": {"decimals": 0,
                                                                        "suffix": " ms"}}},
                                },
                            },
                            "incompleteColumns": {},
                        },
                    },
                },
            },
            "visualization": {
                "layerId": "layer1",
                "layerType": "data",
                "columns": [
                    {"columnId": "agent_col"},
                    {"columnId": "calls_col"},
                    {"columnId": "in_avg_col"},
                    {"columnId": "out_avg_col"},
                    {"columnId": "lat_avg_col"},
                ],
                "sorting": {"columnId": "calls_col", "direction": "desc"},
            },
            "filters": [],
            "query": {"language": "kuery", "query": ""},
        },
    }
    return _lens_panel_wrapper(panel_id, x, y, w, h, title, attributes)


def _lens_top_meetings_table(panel_id: str, x: int, y: int, w: int, h: int,
                              title: str, dv_id: str) -> Dict[str, Any]:
    """Datatable: top 10 most-expensive meetings by total tokens (input+output).

    The audit writer attaches `meeting_id` to most calls (pre/post/live agents,
    most tools), so this table doubles as a "which session burned the most
    Anthropic spend" view. Falls back to "(no meeting_id)" for tool calls
    fired outside a meeting context.
    """
    attributes = {
        "title": title,
        "description": "Top 10 meetings by total tokens (input + output).",
        "visualizationType": "lnsDatatable",
        "type": "lens",
        "references": _lens_references(dv_id),
        "state": {
            "datasourceStates": {
                "formBased": {
                    "layers": {
                        "layer1": {
                            "columnOrder": ["session_col", "calls_col",
                                             "tokens_col_formulaX0",
                                             "tokens_col_formulaX1",
                                             "tokens_col"],
                            "columns": {
                                "session_col": {
                                    "label": "Meeting / session",
                                    "dataType": "string",
                                    "operationType": "terms",
                                    "sourceField": "meeting_id",
                                    "isBucketed": True,
                                    "scale": "ordinal",
                                    "params": {
                                        "size": 10,
                                        "orderBy": {"type": "column",
                                                     "columnId": "tokens_col"},
                                        "orderDirection": "desc",
                                        "otherBucket": True,
                                        "missingBucket": True,
                                        "parentFormat": {"id": "terms"},
                                    },
                                },
                                "calls_col": {
                                    "label": "Calls",
                                    "dataType": "number",
                                    "operationType": "count",
                                    "sourceField": "___records___",
                                    "isBucketed": False,
                                    "scale": "ratio",
                                    "params": {"format": {"id": "number",
                                                            "params": {"decimals": 0}}},
                                },
                                "tokens_col_formulaX0": {
                                    "label": "Part of total tokens",
                                    "dataType": "number",
                                    "operationType": "sum",
                                    "sourceField": "input_tokens",
                                    "isBucketed": False,
                                    "scale": "ratio",
                                    "customLabel": True,
                                },
                                "tokens_col_formulaX1": {
                                    "label": "Part of total tokens",
                                    "dataType": "number",
                                    "operationType": "sum",
                                    "sourceField": "output_tokens",
                                    "isBucketed": False,
                                    "scale": "ratio",
                                    "customLabel": True,
                                },
                                "tokens_col": {
                                    "label": "Total tokens",
                                    "dataType": "number",
                                    "operationType": "formula",
                                    "isBucketed": False,
                                    "scale": "ratio",
                                    "params": {
                                        "formula": "sum(input_tokens) + sum(output_tokens)",
                                        "isFormulaBroken": False,
                                        "format": {"id": "number",
                                                    "params": {"decimals": 0}},
                                    },
                                    "references": ["tokens_col_formulaX0",
                                                    "tokens_col_formulaX1"],
                                    "customLabel": True,
                                },
                            },
                            "incompleteColumns": {},
                        },
                    },
                },
            },
            "visualization": {
                "layerId": "layer1",
                "layerType": "data",
                "columns": [
                    {"columnId": "session_col"},
                    {"columnId": "calls_col"},
                    {"columnId": "tokens_col"},
                ],
                "sorting": {"columnId": "tokens_col", "direction": "desc"},
            },
            "filters": [],
            "query": {"language": "kuery", "query": ""},
        },
    }
    return _lens_panel_wrapper(panel_id, x, y, w, h, title, attributes)


# ============================================================ Layout ===============


def _safe_lens(builder: Callable[..., Dict[str, Any]],
                panel_id: str, x: int, y: int, w: int, h: int,
                title: str, dv_id: str,
                fallback_label: str,
                fallbacks: List[str]) -> Dict[str, Any]:
    """Try the Lens builder; fall back to a markdown placeholder on failure.

    Records the failure in `fallbacks` so the run summary can surface it.
    """
    try:
        return builder(panel_id, x, y, w, h, title, dv_id)
    except Exception as exc:
        log.warning("audit_dashboard.lens.fallback",
                    panel_id=panel_id, builder=builder.__name__, error=str(exc))
        fallbacks.append(f"{builder.__name__}: {exc}")
        return _markdown_panel(panel_id, x, y, w, h,
                                _md_placeholder(fallback_label, str(exc)),
                                title=title)


def build_panels(dv_id: Optional[str], fallbacks: List[str]) -> List[Dict[str, Any]]:
    """48-wide grid. KPIs sit on row 8-18 (h=10), each w=12 so three fit
    side-by-side (16w each would also work; 12 keeps 12 spare for symmetry).

    Layout (y is in grid units, h adds to the next row's y):
    - Header  y=0, h=8
    - 3 KPIs  y=8, h=10  (each 16w so they pack 48)
    - Tokens-by-model  y=18, h=14, w=24
    - Top agents bar   y=18, h=14, w=24
    - p95 latency      y=32, h=14, w=24
    - Tool summary     y=32, h=14, w=24
    - Top meetings     y=46, h=14, w=48
    - Narrative footer y=60, h=12, w=48
    """
    panels: List[Dict[str, Any]] = []

    # Header.
    panels.append(_markdown_panel("p_header", 0, 0, 48, 8, _md_header(),
                                    title="FE Copilot self-observability"))

    # KPI row. Three 16-wide tiles to fill 48.
    if dv_id:
        panels.append(_safe_lens(_lens_kpi_count, "p_kpi_calls",
                                  0, 8, 16, 10, "Total Claude API calls",
                                  dv_id, "Total Claude API calls", fallbacks))
        panels.append(_safe_lens(_lens_kpi_total_tokens, "p_kpi_tokens",
                                  16, 8, 16, 10, "Total tokens consumed",
                                  dv_id, "Total tokens consumed", fallbacks))
        panels.append(_safe_lens(_lens_kpi_mock_pct, "p_kpi_mock",
                                  32, 8, 16, 10, "Mock mode share",
                                  dv_id, "Mock mode share", fallbacks))
    else:
        for i, label in enumerate([
            ("p_kpi_calls", "Total Claude API calls"),
            ("p_kpi_tokens", "Total tokens consumed"),
            ("p_kpi_mock", "Mock mode share"),
        ]):
            pid, lab = label
            panels.append(_markdown_panel(
                pid, i * 16, 8, 16, 10,
                _md_placeholder(lab, "data view unavailable"), title=lab))

    # Mid section, two 24-wide rows.
    if dv_id:
        panels.append(_safe_lens(_lens_tokens_by_model, "p_tokens_by_model",
                                  0, 18, 24, 14, "Tokens by model over time",
                                  dv_id, "Tokens by model over time", fallbacks))
        panels.append(_safe_lens(_lens_top_agents_bar, "p_top_agents",
                                  24, 18, 24, 14, "Top agents and tools by call count",
                                  dv_id, "Top agents and tools by call count",
                                  fallbacks))
        panels.append(_safe_lens(_lens_p95_latency_by_agent, "p_p95_latency",
                                  0, 32, 24, 14, "p95 latency by agent",
                                  dv_id, "p95 latency by agent", fallbacks))
        panels.append(_safe_lens(_lens_tool_summary_table, "p_tool_table",
                                  24, 32, 24, 14,
                                  "Per-agent token and latency rollup",
                                  dv_id, "Per-agent token and latency rollup",
                                  fallbacks))
        panels.append(_safe_lens(_lens_top_meetings_table, "p_top_meetings",
                                  0, 46, 48, 14,
                                  "Top 10 most expensive meetings",
                                  dv_id, "Top 10 most expensive meetings",
                                  fallbacks))
    else:
        layout = [
            ("p_tokens_by_model", 0, 18, 24, 14, "Tokens by model over time"),
            ("p_top_agents", 24, 18, 24, 14, "Top agents and tools by call count"),
            ("p_p95_latency", 0, 32, 24, 14, "p95 latency by agent"),
            ("p_tool_table", 24, 32, 24, 14,
             "Per-agent token and latency rollup"),
            ("p_top_meetings", 0, 46, 48, 14,
             "Top 10 most expensive meetings"),
        ]
        for pid, x, y, w, h, lab in layout:
            panels.append(_markdown_panel(
                pid, x, y, w, h,
                _md_placeholder(lab, "data view unavailable"), title=lab))

    # Narrative footer.
    panels.append(_markdown_panel("p_narrative", 0, 60, 48, 12, _md_narrative(),
                                    title="What this dashboard tells you"))
    return panels


# ============================================================ Dashboard create ======


def _delete_dashboard(client: httpx.Client, dashboard_id: str) -> bool:
    url = _kbn_url(f"/api/saved_objects/dashboard/{dashboard_id}?force=true")
    try:
        resp = client.delete(url, headers=_kbn_headers())
        return resp.status_code < 400 or resp.status_code == 404
    except Exception as exc:
        log.warning("audit_dashboard.dashboard.delete.exception", error=str(exc))
        return False


def _create_dashboard(client: httpx.Client, panels: List[Dict[str, Any]]) -> Tuple[str, str]:
    panels_json = json.dumps(panels, ensure_ascii=False)
    options_json = json.dumps({
        "useMargins": True,
        "hidePanelTitles": False,
        "syncColors": True,
        "syncCursor": True,
        "syncTooltips": True,
    })
    search_source_json = json.dumps({"query": {"language": "kuery", "query": ""},
                                      "filter": []})
    description = (
        "FE Copilot self-observability. Built from the project's own "
        "audit log (fec-audit). Tracks Claude API spend, tool usage, "
        "model mix, and mock vs live execution. Idempotently rebuilt by "
        "backend/scripts/sync_audit_dashboard.py."
    )

    body = [{
        "id": DASHBOARD_ID,
        "type": "dashboard",
        "attributes": {
            "title": DASHBOARD_TITLE,
            "description": description,
            "panelsJSON": panels_json,
            "optionsJSON": options_json,
            "timeRestore": True,
            "timeFrom": "now-7d",
            "timeTo": "now",
            "refreshInterval": {"pause": True, "value": 0},
            "version": 1,
            "kibanaSavedObjectMeta": {"searchSourceJSON": search_source_json},
        },
    }]

    url = _kbn_url("/api/saved_objects/_bulk_create?overwrite=true")
    resp = client.post(url, headers=_kbn_headers(), json=body)
    if resp.status_code >= 400:
        raise RuntimeError(
            f"Kibana dashboard create failed: {resp.status_code} {resp.text[:400]}"
        )
    return DASHBOARD_ID, _dashboard_url(DASHBOARD_ID)


# ============================================================ Entry point ===========


def main() -> int:
    if not settings.kibana_api_key:
        print("KIBANA_API_KEY not set; cannot sync the audit dashboard.",
              file=sys.stderr)
        return 1

    started = datetime.now(timezone.utc)
    fallbacks: List[str] = []

    with httpx.Client(timeout=45.0) as client:
        doc_count = _audit_doc_count(client)
        log.info("audit_dashboard.fec_audit.count", count=doc_count)

        dv_id = _ensure_data_view(client)
        if not dv_id:
            log.warning("audit_dashboard.data_view.missing",
                        note="dashboard will use markdown placeholders for Lens panels")

        panels = build_panels(dv_id, fallbacks)

        _delete_dashboard(client, DASHBOARD_ID)
        try:
            dashboard_id, dashboard_url = _create_dashboard(client, panels)
        except Exception as exc:
            log.error("audit_dashboard.create.failed", error=str(exc))
            print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
            return 2

    summary = {
        "ok": True,
        "dashboard_id": dashboard_id,
        "dashboard_url": dashboard_url,
        "data_view_id": dv_id,
        "panels": len(panels),
        "fec_audit_doc_count": doc_count,
        "lens_fallbacks": fallbacks,
        "started_at": started.isoformat(),
        "elapsed_seconds": round(
            (datetime.now(timezone.utc) - started).total_seconds(), 2),
    }
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
