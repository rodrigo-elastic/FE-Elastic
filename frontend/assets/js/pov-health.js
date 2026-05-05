/*
  filename: pov-health.js
  description: Workspace-only logic for /pov-health.html. Wires the demo-summary loader and the History panel that lists every persisted POV health check from runtime/pov_health/*.json. Reuses runPovHealth + renderPovHealth from tools.js for the form runner.
  Author: Rodrigo Careaga
  Date: 04-05-2026
*/
(function () {
  // The canonical "Atlas Health, week 3 of 8" summary the brief calls out.
  const DEMO_SUMMARY =
    "Atlas Health, week 3 of 8, ingesting 12 GB/day from 2 namespaces. " +
    "1 dashboard built by the customer platform engineer. No SLOs configured. " +
    "No alerting rules beyond integration defaults. Single user only (the platform engineer). " +
    "ELSER not yet enabled. JVM heap nominal. Customer Champion is the platform engineering lead " +
    "but the security and app dev orgs have not been engaged yet.";

  function bindDemoLoader() {
    const btn = document.getElementById("pv-load-demo");
    if (!btn) return;
    btn.addEventListener("click", function () {
      const ta = document.getElementById("pv-summary");
      const cust = document.getElementById("pv-customer");
      const wk = document.getElementById("pv-week");
      if (ta) ta.value = DEMO_SUMMARY;
      if (cust && !cust.value) cust.value = "Atlas Health";
      if (wk && !wk.value) wk.value = "3";
    });
  }

  function stageBadgeStyle(stage) {
    const s = String(stage || "").toLowerCase();
    if (s === "on_track") return "background: rgba(20, 158, 134, 0.18); color: #0c6b59; border: 1px solid rgba(20, 158, 134, 0.50);";
    if (s === "at_risk")  return "background: rgba(246, 192, 0, 0.20); color: #8a6d00; border: 1px solid rgba(246, 192, 0, 0.55);";
    if (s === "stalled")  return "background: rgba(220, 53, 69, 0.18); color: #a01f2e; border: 1px solid rgba(220, 53, 69, 0.55);";
    return "background: rgba(100, 116, 139, 0.14); color: #334155; border: 1px solid rgba(100, 116, 139, 0.32);";
  }

  function stageLabel(stage) {
    const s = String(stage || "").toLowerCase();
    if (s === "on_track") return "On track";
    if (s === "at_risk") return "At risk";
    if (s === "stalled") return "Stalled";
    return s || "unknown";
  }

  function fmtDate(iso) {
    if (!iso) return "";
    try {
      const d = new Date(iso);
      if (isNaN(d.getTime())) return iso;
      return d.toLocaleString();
    } catch (_e) {
      return iso;
    }
  }

  async function loadHistory() {
    const host = document.getElementById("pv-history");
    const status = document.getElementById("pv-history-status");
    if (!host) return;
    if (typeof clear === "function") clear(host); else host.innerHTML = "";
    if (status) status.textContent = "Loading...";
    let data;
    try {
      data = await apiGet("/tools/pov-health/history");
    } catch (e) {
      if (status) status.textContent = "Failed to load history.";
      host.appendChild(el("div", { class: "muted small" }, "Could not load history. Run a POV health check first to seed runtime/pov_health/."));
      return;
    }
    const groups = (data && data.groups) || [];
    const total = (data && data.total) || 0;
    if (status) status.textContent = total + " record" + (total === 1 ? "" : "s");
    if (!groups.length) {
      host.appendChild(el("div", { class: "muted small" }, "No POV health checks yet. Run one above to populate the history."));
      return;
    }

    groups.forEach((g) => {
      const groupHead = el("div", {
        style: "margin: 14px 0 6px; display: flex; align-items: center; gap: 10px;",
      }, [
        el("h3", { class: "tool-section", style: "margin: 0; font-size: 16px;" }, g.customer_name || g.slug),
        el("span", { class: "muted small" }, (g.items || []).length + " check" + ((g.items || []).length === 1 ? "" : "s")),
      ]);
      host.appendChild(groupHead);

      (g.items || []).forEach((item) => {
        const card = el("div", {
          class: "comp-card",
          style: "padding: 12px 14px; margin-bottom: 8px; cursor: pointer;",
        });
        const head = el("div", {
          class: "comp-head",
          style: "padding-bottom: 6px; margin-bottom: 6px; gap: 10px; align-items: center;",
        }, [
          el("span", {
            class: "native-badge",
            style: "font-size: 11px; letter-spacing: 0.4px; " + stageBadgeStyle(item.stage_assessment),
          }, stageLabel(item.stage_assessment)),
          el("span", {
            class: "native-badge",
            style: "font-size: 11px; background: rgba(100, 116, 139, 0.12); color: #334155; border: 1px solid rgba(100, 116, 139, 0.32);",
          }, "Confidence: " + (item.confidence_score != null ? item.confidence_score : "?") + " / 100"),
          item.week_number
            ? el("span", { class: "muted small" }, "Week " + item.week_number)
            : el("span", {}),
          el("span", { class: "muted small", style: "margin-left: auto;" }, fmtDate(item.generated_at)),
        ]);
        card.appendChild(head);
        if (item.executive_summary) {
          card.appendChild(el("div", { class: "muted small", style: "line-height: 1.5;" }, item.executive_summary));
        }
        card.addEventListener("click", async function () {
          try {
            if (status) status.textContent = "Loading record...";
            const full = await apiGet("/tools/pov-health/history/" + encodeURIComponent(item.filename));
            if (typeof window.renderPovHealth === "function") {
              window.renderPovHealth(full, "pv-result");
              const target = document.getElementById("pv-result");
              if (target && typeof target.scrollIntoView === "function") {
                target.scrollIntoView({ behavior: "smooth", block: "start" });
              }
            }
            if (status) status.textContent = total + " record" + (total === 1 ? "" : "s");
          } catch (e) {
            if (status) status.textContent = "Failed to load record.";
          }
        });
        host.appendChild(card);
      });
    });
  }

  function bindHistoryRefresh() {
    const btn = document.getElementById("pv-history-refresh");
    if (!btn) return;
    btn.addEventListener("click", function () { loadHistory(); });
  }

  function init() {
    bindDemoLoader();
    bindHistoryRefresh();
    // Refresh history after every successful run so a freshly persisted check appears immediately.
    const form = document.getElementById("pv-form");
    if (form) {
      form.addEventListener("submit", function () {
        // The submit handler in tools.js is async; queue a delayed refresh
        // so the artifact lands on disk before we re-list.
        setTimeout(loadHistory, 1500);
      });
    }
    loadHistory();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
