/*
  filename: health.js
  description: Health dashboard renderer for /health.html. Polls /api/v1/health/full every 30s, paints the status badge, six big-number stat cards (MCP tools, FE Brain chunks, workflows, demo scenarios, battlecards, Elastic cluster), warnings list, and the build footer (sha + commit timestamp + relative last-check stamp).
  Author: Rodrigo Careaga
  Date: 04-05-2026
*/
(function () {
  const REFRESH_MS = 30000;
  let lastChecked = null;
  let lastTimer = null;

  function $(id) { return document.getElementById(id); }

  function tt(key, fallback) {
    if (typeof t === "function") return t(key, fallback);
    return fallback || key;
  }

  function setText(id, value) {
    const el = $(id);
    if (el) el.textContent = value;
  }

  function setStatus(status) {
    const badge = $("health-status-badge");
    const label = $("health-status-label");
    if (!badge || !label) return;
    const safe = (status === "green" || status === "yellow" || status === "red") ? status : "loading";
    badge.dataset.status = safe;
    const dict = {
      green:   tt("health.status.green",   "All systems green"),
      yellow:  tt("health.status.yellow",  "Degraded, demo still works"),
      red:     tt("health.status.red",     "Offline"),
      loading: tt("health.status.loading", "Loading..."),
    };
    label.textContent = dict[safe];
  }

  function fmtNumber(n) {
    if (n === null || n === undefined || Number.isNaN(n)) return "-";
    return Number(n).toLocaleString();
  }

  function fmtRelative(iso) {
    if (!iso) return "-";
    const then = new Date(iso).getTime();
    if (Number.isNaN(then)) return iso;
    const now = Date.now();
    const sec = Math.max(0, Math.round((now - then) / 1000));
    if (sec < 5) return tt("health.time.justnow", "just now");
    if (sec < 60) return sec + " " + tt("health.time.s", "s ago");
    const min = Math.round(sec / 60);
    if (min < 60) return min + " " + tt("health.time.m", "min ago");
    const hr = Math.round(min / 60);
    if (hr < 24) return hr + " " + tt("health.time.h", "h ago");
    const day = Math.round(hr / 24);
    return day + " " + tt("health.time.d", "d ago");
  }

  function fmtIso(iso) {
    if (!iso) return "-";
    try {
      const d = new Date(iso);
      if (Number.isNaN(d.getTime())) return iso;
      return d.toISOString().replace("T", " ").replace(/\.\d+Z$/, "Z");
    } catch (_e) { return iso; }
  }

  function renderWorkflows(wf) {
    const post = wf && wf.rule_post_meeting === "registered";
    const orphan = wf && wf.rule_orphan_actions === "registered";
    const okCount = (post ? 1 : 0) + (orphan ? 1 : 0);
    setText("card-wf-val", okCount + "/2");
    const foot = $("card-wf-foot");
    if (!foot) return;
    foot.innerHTML = "";
    foot.appendChild(makeChip(tt("health.wf.post", "post-meeting"), post ? "ok" : "bad"));
    foot.appendChild(makeChip(tt("health.wf.orphan", "orphan-actions"), orphan ? "ok" : "bad"));
  }

  function makeChip(label, tone) {
    const span = document.createElement("span");
    span.className = "ab-pill ab-pill-muted";
    span.style.padding = "2px 8px";
    span.style.fontSize = "11.5px";
    if (tone === "ok") {
      span.style.borderColor = "rgba(147, 201, 14, 0.45)";
      span.style.background = "rgba(147, 201, 14, 0.10)";
    } else if (tone === "bad") {
      span.style.borderColor = "rgba(255, 102, 102, 0.55)";
      span.style.background = "rgba(255, 102, 102, 0.10)";
    }
    span.textContent = label;
    return span;
  }

  function renderWarnings(warnings) {
    const host = $("health-warnings");
    const ul = $("health-warnings-list");
    if (!host || !ul) return;
    if (!warnings || !warnings.length) {
      host.hidden = true;
      ul.innerHTML = "";
      return;
    }
    host.hidden = false;
    ul.innerHTML = "";
    warnings.forEach((w) => {
      const li = document.createElement("li");
      li.textContent = w.replace(/_/g, " ");
      ul.appendChild(li);
    });
  }

  function paint(data) {
    setStatus(data.status);

    // Hero pills.
    const cluster = (data.elastic && data.elastic.cluster) || tt("health.cluster.unknown", "unknown cluster");
    setText("health-cluster-name", cluster);
    setText("health-cluster-version", (data.elastic && data.elastic.version) || "-");
    const ping = data.elastic && Number.isFinite(data.elastic.ping_ms) ? data.elastic.ping_ms : -1;
    setText("health-ping-ms", ping >= 0 ? (ping + " ms") : "-");

    // Card 1: MCP tools.
    const mcpCount = (data.mcp_tools && data.mcp_tools.count) || 0;
    setText("card-mcp-val", fmtNumber(mcpCount));
    const mcpFoot = $("card-mcp-foot");
    if (mcpFoot) {
      mcpFoot.innerHTML = "";
      const list = (data.mcp_tools && data.mcp_tools.list) || [];
      list.slice(0, 6).forEach((id) => {
        mcpFoot.appendChild(makeChip(id, "ok"));
      });
      if (list.length > 6) {
        mcpFoot.appendChild(makeChip("+" + (list.length - 6), null));
      }
    }

    // Card 2: FE Brain chunks.
    const chunks = (data.fe_brain && data.fe_brain.chunks) || 0;
    setText("card-brain-val", fmtNumber(chunks));
    const brainFoot = $("card-brain-foot");
    if (brainFoot) {
      brainFoot.innerHTML = "";
      brainFoot.appendChild(makeChip(
        tt("health.brain.lastseed", "last seed:") + " " + fmtRelative((data.fe_brain && data.fe_brain.last_seed) || ""),
        chunks > 0 ? "ok" : "bad",
      ));
      brainFoot.appendChild(makeChip("fec-knowledge", null));
    }

    // Card 3: Workflows.
    renderWorkflows(data.workflows);

    // Card 4: Demo scenarios.
    const scenarios = (data.demo_data && data.demo_data.scenarios) || 0;
    const dashboards = (data.demo_data && data.demo_data.dashboards) || 0;
    setText("card-demo-val", fmtNumber(scenarios));
    const demoFoot = $("card-demo-foot");
    if (demoFoot) {
      demoFoot.innerHTML = "";
      demoFoot.appendChild(makeChip(dashboards + " " + tt("health.demo.dashboards", "Kibana dashboards"), null));
    }

    // Card 5: Battlecards.
    const bc = (data.battlecards && data.battlecards.count) || 0;
    setText("card-bc-val", fmtNumber(bc));
    const bcFoot = $("card-bc-foot");
    if (bcFoot) {
      bcFoot.innerHTML = "";
      bcFoot.appendChild(makeChip("fec-battlecards", null));
    }

    // Card 6: Elastic cluster (smaller font, label is the cluster name).
    const elasticVal = $("card-elastic-val");
    if (elasticVal) {
      const v = (data.elastic && data.elastic.version) || "-";
      elasticVal.textContent = v;
    }
    const elFoot = $("card-elastic-foot");
    if (elFoot) {
      elFoot.innerHTML = "";
      elFoot.appendChild(makeChip(cluster, data.elastic && data.elastic.available ? "ok" : "bad"));
      if (ping >= 0) elFoot.appendChild(makeChip(ping + " ms", "ok"));
    }

    // Warnings.
    renderWarnings(data.warnings || []);

    // Footer: build SHA + timestamp + agent + connector.
    const buildSha = (data.build && data.build.sha) || "-";
    const buildTs = (data.build && data.build.timestamp) || "";
    setText("health-build-sha", buildSha);
    setText("health-build-ts", fmtIso(buildTs));
    setText("health-agent-id", (data.kibana && data.kibana.agent_builder_agent) || "-");
    setText("health-connector-name", (data.kibana && data.kibana.mcp_connector) || "-");

    lastChecked = data.checked_at || new Date().toISOString();
    setText("health-last-check", fmtRelative(lastChecked));
  }

  function paintError(err) {
    setStatus("red");
    const cards = ["card-mcp-val", "card-brain-val", "card-wf-val", "card-demo-val", "card-bc-val", "card-elastic-val"];
    cards.forEach((id) => setText(id, "-"));
    setText("health-cluster-name", tt("health.cluster.offline", "backend offline"));
    setText("health-cluster-version", "-");
    setText("health-ping-ms", "-");
    renderWarnings(["backend_unreachable: " + (err && err.message ? err.message : err)]);
  }

  async function load() {
    try {
      const data = await apiGet("/health/full");
      paint(data);
    } catch (err) {
      console.warn("[health] fetch failed", err);
      paintError(err);
    }
  }

  function tickRelative() {
    if (!lastChecked) return;
    setText("health-last-check", fmtRelative(lastChecked));
  }

  function init() {
    // Translate static text now that strings are loaded.
    if (typeof applyI18n === "function") applyI18n(document);
    if (typeof renderLangPicker === "function") {
      renderLangPicker(document.getElementById("lang-host"));
    }
    load();
    if (lastTimer) clearInterval(lastTimer);
    setInterval(load, REFRESH_MS);
    lastTimer = setInterval(tickRelative, 5000);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
