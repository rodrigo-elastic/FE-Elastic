/*
  filename: customer-health.js
  description: Renders the Customer Health dashboard. Hits /api/v1/customer-health
  for the rolled-up list, then /api/v1/customer-health/{id} for the detail pane
  on selection. Inline SVG sparkline + feature pills + proactive task cards.
  Tasks remember "scheduled" state in localStorage so the FE can dismiss what's
  already in motion without round-tripping the backend.
  Author: Rodrigo Careaga
  Date: 05-13-2026
*/
(function () {
  "use strict";

  const $ = (sel, root) => (root || document).querySelector(sel);

  const STORAGE_KEY = "fec.customer_health.scheduled";

  function loadScheduled() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}") || {};
    } catch (_) {
      return {};
    }
  }
  function saveScheduled(map) {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(map)); } catch (_) {}
  }

  function el(tag, attrs, children) {
    const n = document.createElement(tag);
    if (attrs) {
      for (const k of Object.keys(attrs)) {
        if (k === "class") n.className = attrs[k];
        else if (k === "html") n.innerHTML = attrs[k];
        else if (k.startsWith("on") && typeof attrs[k] === "function") n.addEventListener(k.slice(2), attrs[k]);
        else n.setAttribute(k, attrs[k]);
      }
    }
    if (children) {
      (Array.isArray(children) ? children : [children]).forEach((c) => {
        if (c == null) return;
        n.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
      });
    }
    return n;
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function fmtNum(n) {
    if (n == null || isNaN(n)) return "-";
    return Number(n).toLocaleString("en-US");
  }
  function fmtUsd(n) {
    if (n == null || isNaN(n)) return "-";
    return "$" + Math.round(n / 1000).toLocaleString("en-US") + "k";
  }

  // ============================================================ List rail

  async function loadList() {
    const host = $("#ch-list");
    host.innerHTML = '<div class="ch-empty">Loading customers...</div>';
    const status = $("#status");
    try {
      const data = await (window.apiGetWithRetry
        ? window.apiGetWithRetry("/customer-health", { category: "compute", timeoutMs: 10000, silent: true, label: "Customer Health" })
        : window.apiGet("/customer-health"));
      const customers = (data && data.customers) || [];
      status.textContent = customers.length + " accounts";
      if (!customers.length) {
        host.innerHTML = '<div class="ch-empty">No customers on file.</div>';
        return;
      }
      host.innerHTML = "";
      customers.forEach((c) => host.appendChild(renderRow(c)));
      // Auto-select the first (most at-risk) so the detail pane never sits empty.
      const first = customers[0];
      if (first) selectCustomer(first.id);
    } catch (e) {
      host.innerHTML = '<div class="ch-empty">Failed to load: ' + escapeHtml(e && e.message ? e.message : String(e)) + '</div>';
      status.textContent = "Offline";
    }
  }

  function renderRow(c) {
    const row = el("button", {
      class: "ch-row",
      type: "button",
      "data-customer": c.id,
      onclick: () => selectCustomer(c.id),
    });
    const headChildren = [
      el("span", { class: "ch-score " + c.health_status }, String(c.health_score)),
      el("span", { class: "ch-row-name" }, c.name),
    ];
    if (c.proactive_count > 0) {
      headChildren.push(el("span", { class: "pill", style: "font-size:10.5px; padding:2px 8px; background:rgba(11,100,221,0.15); color:var(--primary, #0B64DD); border-radius:999px" }, String(c.proactive_count) + " " + (c.proactive_count === 1 ? "task" : "tasks")));
    }
    const head = el("div", { class: "ch-row-head" }, headChildren);
    const metaParts = [];
    if (c.days_to_renewal != null) {
      metaParts.push("renewal " + c.days_to_renewal + "d");
    }
    if (c.adoption_trend_pct != null) {
      const arrow = c.adoption_trend_pct >= 0 ? "↑" : "↓";
      metaParts.push("ingest " + arrow + " " + Math.abs(c.adoption_trend_pct).toFixed(0) + "%");
    }
    if (c.open_p1_tickets) metaParts.push(c.open_p1_tickets + "× P1");
    if (c.last_contact_days != null && c.last_contact_days >= 0) {
      metaParts.push(c.last_contact_days + "d since contact");
    }
    const meta = el("div", { class: "ch-row-meta" }, metaParts.map((m) => el("span", {}, m)));
    row.appendChild(head);
    row.appendChild(meta);
    return row;
  }

  async function selectCustomer(id) {
    document.querySelectorAll(".ch-row").forEach((r) => {
      r.classList.toggle("is-selected", r.getAttribute("data-customer") === id);
    });
    const host = $("#ch-detail");
    host.innerHTML = '<div class="ch-empty">Loading...</div>';
    try {
      const data = await (window.apiGetWithRetry
        ? window.apiGetWithRetry("/customer-health/" + encodeURIComponent(id), { category: "compute", timeoutMs: 10000, silent: true, label: "Customer detail" })
        : window.apiGet("/customer-health/" + encodeURIComponent(id)));
      renderDetail(data);
    } catch (e) {
      host.innerHTML = '<div class="ch-empty">Failed to load: ' + escapeHtml(e && e.message ? e.message : String(e)) + '</div>';
    }
  }

  // ============================================================ Detail pane

  function renderDetail(d) {
    const host = $("#ch-detail");
    host.innerHTML = "";
    if (!d || !d.customer) { host.innerHTML = '<div class="ch-empty">No data.</div>'; return; }

    // Header
    const head = el("div", { class: "ch-detail-head" });
    head.appendChild(el("div", { style: "flex:1; min-width:0" }, [
      el("h2", { class: "ch-detail-title" }, d.customer.name),
      el("div", { class: "ch-detail-sub" }, [
        el("span", {}, d.customer.industry || ""),
        d.customer.size ? el("span", {}, " · " + d.customer.size) : null,
      ]),
    ]));
    head.appendChild(el("div", { class: "ch-detail-score-block" }, [
      el("span", { class: "ch-detail-score-big" }, String(d.health_score)),
      el("span", { class: "ch-score " + d.health_status }, d.health_status.replace("_", " ")),
    ]));
    host.appendChild(head);

    // Signals at-a-glance grid
    host.appendChild(renderSignals(d));

    // Adoption trajectory
    host.appendChild(renderAdoption(d.adoption || {}));

    // Proactive tasks
    host.appendChild(renderTasks(d.customer.id, d.proactive_tasks || []));
  }

  function signalCard(lbl, val, sub, kind) {
    return el("div", { class: "ch-signal-card" }, [
      el("div", { class: "ch-signal-lbl" }, lbl),
      el("div", { class: "ch-signal-val" + (kind ? " " + kind : "") }, val),
      sub != null ? el("div", { class: "ch-signal-sub" }, sub) : null,
    ]);
  }

  function renderSignals(d) {
    const wrap = el("div", { class: "ch-section" });
    wrap.appendChild(el("div", { class: "ch-section-h" }, [el("h3", {}, "Signals at-a-glance")]));
    const grid = el("div", { class: "ch-signals-grid" });

    const r = (d.signals && d.signals.renewal) || {};
    const renewalKind = r.days_remaining == null ? null : (r.days_remaining <= 60 ? "red" : r.days_remaining <= 120 ? "yellow" : "green");
    grid.appendChild(signalCard(
      "Renewal",
      r.days_remaining != null ? r.days_remaining + " days" : "n/a",
      r.arr_usd ? fmtUsd(r.arr_usd) + " ARR" + (r.date ? " · lands " + r.date : "") : (r.date || "no renewal on file"),
      renewalKind
    ));

    const t = (d.signals && d.signals.tickets) || {};
    const ticketsKind = t.p1 ? "red" : (t.open ? "yellow" : "green");
    const trendStr = t.trend_30d == null ? "" : (t.trend_30d > 0 ? "+" + t.trend_30d + " vs prior 30d" : (t.trend_30d < 0 ? t.trend_30d + " vs prior 30d" : "flat vs prior 30d"));
    grid.appendChild(signalCard(
      "Open tickets",
      String(t.open || 0) + (t.p1 ? "  (" + t.p1 + " P1)" : ""),
      trendStr,
      ticketsKind
    ));

    const a = (d.signals && d.signals.autoops) || {};
    const autoopsKind = a.status === "red" ? "red" : (a.status === "yellow" ? "yellow" : "green");
    grid.appendChild(signalCard(
      "AutoOps cluster",
      (a.status || "n/a").toUpperCase(),
      (a.alert_count != null ? a.alert_count + " alerts" : "") + (a.high_severity_count ? " · " + a.high_severity_count + " high" : ""),
      autoopsKind
    ));

    const lc = (d.signals && d.signals.last_contact) || null;
    const daysAgo = lc && lc.days_ago != null ? lc.days_ago : null;
    const lcKind = lc == null || daysAgo == null ? "yellow" : (daysAgo <= 30 ? "green" : daysAgo <= 90 ? "yellow" : "red");
    const lcVal = lc == null ? "Never" : (lc.is_future ? "Upcoming in " + Math.abs(daysAgo) + "d" : daysAgo + "d ago");
    grid.appendChild(signalCard(
      "Last contact",
      lcVal,
      lc && lc.title ? lc.title.slice(0, 60) : "",
      lcKind
    ));

    const pov = (d.signals && d.signals.pov_health) || null;
    if (pov) {
      const povKind = pov.stage_assessment === "on_track" ? "green" : pov.stage_assessment === "at_risk" ? "yellow" : "red";
      grid.appendChild(signalCard(
        "POV health",
        (pov.stage_assessment || "n/a").replace("_", " "),
        (pov.confidence_score != null ? pov.confidence_score + "% confidence" : "") + (pov.days_to_decision_estimate != null ? " · " + pov.days_to_decision_estimate + "d to decision" : ""),
        povKind
      ));
    }

    wrap.appendChild(grid);

    // Renewal signal details (if any)
    if (r.signals && r.signals.length) {
      const det = el("details", { style: "margin-top: 14px;" });
      det.appendChild(el("summary", { style: "cursor:pointer; font-size:12px; color:var(--muted)" }, r.signal_count + " renewal signal(s) on file"));
      const list = el("ul", { class: "muted small", style: "margin-top:8px; padding-left:18px" });
      r.signals.slice(0, 5).forEach((s) => {
        list.appendChild(el("li", { style: "margin-bottom:4px" }, [
          el("strong", { style: "color: var(--ink)" }, (s.severity || "").toUpperCase() + " · " + (s.signal_type || "")),
          el("span", {}, " - " + (s.summary || "")),
        ]));
      });
      det.appendChild(list);
      wrap.appendChild(det);
    }
    return wrap;
  }

  // ----------------------------------------------------- Sparkline (inline SVG)
  function renderSparkline(series) {
    if (!series || !series.length) return el("div", { class: "muted small" }, "No ingest data.");
    const W = 600, H = 90, PAD_L = 40, PAD_R = 10, PAD_T = 8, PAD_B = 18;
    const innerW = W - PAD_L - PAD_R, innerH = H - PAD_T - PAD_B;
    const vals = series.map((s) => s.value);
    const minV = Math.min(...vals), maxV = Math.max(...vals);
    const span = Math.max(1, maxV - minV);
    const stepX = innerW / Math.max(1, series.length - 1);
    const points = series.map((s, i) => {
      const x = PAD_L + i * stepX;
      const y = PAD_T + innerH - ((s.value - minV) / span) * innerH;
      return [x, y];
    });
    const path = points.map((p, i) => (i === 0 ? "M" : "L") + p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ");
    const areaPath = path + " L" + points[points.length - 1][0].toFixed(1) + "," + (PAD_T + innerH) + " L" + points[0][0].toFixed(1) + "," + (PAD_T + innerH) + " Z";

    const svg = `
      <svg class="ch-spark" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="90-day ingest GB/day trend">
        <text class="ch-spark-axis" x="${PAD_L - 6}" y="${PAD_T + 4}" text-anchor="end">${Math.round(maxV)}</text>
        <text class="ch-spark-axis" x="${PAD_L - 6}" y="${PAD_T + innerH}" text-anchor="end">${Math.round(minV)}</text>
        <text class="ch-spark-axis" x="${PAD_L - 6}" y="${H - 4}" text-anchor="end">GB/day</text>
        <path class="ch-spark-area" d="${areaPath}" />
        <path class="ch-spark-line" d="${path}" />
        ${points.map((p) => '<circle class="ch-spark-dot" cx="' + p[0].toFixed(1) + '" cy="' + p[1].toFixed(1) + '" r="2.4" />').join("")}
      </svg>
    `;
    const wrap = el("div", { class: "ch-spark-wrap", html: svg });
    const labels = el("div", { class: "ch-spark-labels" });
    labels.appendChild(el("span", {}, "13 weeks ago"));
    labels.appendChild(el("span", {}, "now"));
    wrap.appendChild(labels);
    return wrap;
  }

  function renderAdoption(adoption) {
    const wrap = el("div", { class: "ch-section" });
    const ingest = adoption.ingest_gb_day || {};
    const trend = ingest.trend_pct == null ? 0 : ingest.trend_pct;
    const trendCls = trend >= 5 ? "up" : trend <= -5 ? "down" : "flat";
    const trendStr = (trend >= 0 ? "+" : "") + trend.toFixed(1) + "% over 90d";
    const head = el("div", { class: "ch-section-h" }, [
      el("h3", {}, "Adoption trajectory"),
      el("span", { class: "ch-trend " + trendCls }, trendStr),
    ]);
    wrap.appendChild(head);
    wrap.appendChild(renderSparkline(ingest.series || []));

    const features = adoption.feature_usage || [];
    if (features.length) {
      wrap.appendChild(el("div", { style: "font-size:11.5px; font-weight:700; letter-spacing:.06em; text-transform:uppercase; color:var(--muted); margin:14px 0 8px" }, "Feature usage"));
      const list = el("div", { class: "ch-features" });
      features.forEach((f) => {
        const days = f.last_used_days;
        const label = days <= 0 ? "today" : days <= 7 ? "this week" : days <= 30 ? days + "d" : days <= 180 ? Math.round(days / 30) + "mo" : Math.round(days / 30) + "mo";
        list.appendChild(el("span", { class: "ch-feature " + (f.status || "stale"), title: f.feature + " - last used " + days + " days ago" }, [
          el("span", {}, f.feature),
          el("span", { class: "ch-feature-days" }, "(" + label + ")"),
        ]));
      });
      wrap.appendChild(list);
    }
    return wrap;
  }

  // ----------------------------------------------------- Proactive tasks
  function renderTasks(customerId, tasks) {
    const wrap = el("div", { class: "ch-section" });
    wrap.appendChild(el("div", { class: "ch-section-h" }, [
      el("h3", {}, "Proactive tasks"),
      el("span", { class: "muted small" }, tasks.length + (tasks.length === 1 ? " suggestion" : " suggestions")),
    ]));
    if (!tasks.length) {
      wrap.appendChild(el("div", { class: "ch-empty" }, "No proactive tasks queued. This account is on cruise control."));
      return wrap;
    }
    const scheduled = loadScheduled();
    const list = el("div", {});
    tasks.forEach((t) => {
      const isDone = !!scheduled[t.id];
      const row = el("div", { class: "ch-task" + (isDone ? " is-scheduled" : "") });
      row.appendChild(el("div", { class: "ch-task-sev " + (t.severity || "low") }));
      const body = el("div", { class: "ch-task-body" });
      body.appendChild(el("div", { class: "ch-task-title" }, t.title));
      body.appendChild(el("div", { class: "ch-task-rationale" }, t.rationale));
      const meta = el("div", { class: "ch-task-meta" });
      meta.appendChild(el("span", { class: "pill" }, (t.severity || "").toUpperCase()));
      if (t.suggested_owner) meta.appendChild(el("span", { class: "pill" }, "owner: " + t.suggested_owner));
      if (t.suggested_action) meta.appendChild(el("span", { class: "pill" }, t.suggested_action.replace(/_/g, " ")));
      (t.trigger || []).forEach((tr) => meta.appendChild(el("span", { class: "pill" }, tr.replace(/_/g, " "))));
      body.appendChild(meta);
      row.appendChild(body);
      const actions = el("div", { class: "ch-task-actions" });
      actions.appendChild(el("button", {
        class: "ch-task-btn",
        type: "button",
        onclick: (ev) => {
          const s = loadScheduled();
          if (s[t.id]) delete s[t.id]; else s[t.id] = { customer_id: customerId, ts: Date.now() };
          saveScheduled(s);
          ev.currentTarget.closest(".ch-task").classList.toggle("is-scheduled");
          ev.currentTarget.textContent = ev.currentTarget.closest(".ch-task").classList.contains("is-scheduled") ? "Undo" : "Mark scheduled";
        },
      }, isDone ? "Undo" : "Mark scheduled"));
      row.appendChild(actions);
      list.appendChild(row);
    });
    wrap.appendChild(list);
    return wrap;
  }

  // ============================================================ Wire up
  function init() {
    loadList();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
