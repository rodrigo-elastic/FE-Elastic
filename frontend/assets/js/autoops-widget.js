/*
  filename: autoops-widget.js
  description: AutoOps cluster signals widget for the meeting brief panel.
  Fetches live alerts from /api/v1/autoops/alerts and renders a compact
  health card showing severity, category, and recommendation. Also renders
  the AutoOps vs Splunk competitive card when Splunk is detected in the brief.
  Author: Rodrigo Careaga
  Date: 05-06-2026
*/
(function () {
  "use strict";

  const SEV_ICON = { critical: "🔴", warning: "🟡", info: "🔵" };
  const SEV_CLASS = { critical: "ao-sev-critical", warning: "ao-sev-warning", info: "ao-sev-info" };
  const CAT_LABEL = {
    jvm: "JVM", shards: "Shards", queries: "Queries",
    indexing: "Indexing", storage: "Storage", mapping: "Mapping",
  };

  const CSS = `
    .ao-card{border:1px solid var(--border,#2a2b30);border-radius:8px;margin:20px 0 4px;overflow:hidden;font-size:13px}
    .ao-header{display:flex;align-items:center;gap:10px;padding:10px 14px;background:var(--surface,#111217);border-bottom:1px solid var(--border,#2a2b30)}
    .ao-dot{width:8px;height:8px;border-radius:50%;background:#00BFB3;animation:ao-pulse 2s infinite;flex-shrink:0}
    .ao-dot.warn{background:#FEC514}.ao-dot.crit{background:#F04E98}
    @keyframes ao-pulse{0%,100%{opacity:1}50%{opacity:.35}}
    .ao-header-title{font-weight:700;color:var(--text,#d4d9e0);font-size:12px;letter-spacing:.03em;text-transform:uppercase}
    .ao-header-cluster{font-size:11px;color:var(--text-muted,#5a6270);margin-left:auto;font-family:ui-monospace,monospace}
    .ao-body{padding:10px 14px;display:flex;flex-direction:column;gap:8px;background:var(--bg,#07080c)}
    .ao-alert{display:flex;gap:10px;align-items:flex-start;padding:8px 10px;border-radius:6px;background:var(--surface,#111217);border:1px solid var(--border,#1e1f24)}
    .ao-alert.ao-sev-warning{border-color:#FEC51440;background:#FEC51408}
    .ao-alert.ao-sev-critical{border-color:#F04E9840;background:#F04E9808}
    .ao-alert.ao-sev-info{border-color:#1BA9F520;background:#1BA9F508}
    .ao-alert-icon{font-size:14px;flex-shrink:0;margin-top:1px}
    .ao-alert-body{flex:1;min-width:0}
    .ao-alert-title{font-weight:600;color:var(--text,#d4d9e0);line-height:1.35}
    .ao-alert-cat{display:inline-block;font-size:10px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:var(--text-muted,#5a6270);margin-left:6px}
    .ao-alert-desc{color:var(--text-muted,#8b919a);margin-top:3px;line-height:1.45;font-size:12px}
    .ao-alert-rec{margin-top:5px;font-size:12px;color:#00BFB3;line-height:1.4}
    .ao-alert-rec::before{content:"→ ";font-weight:700}
    .ao-resolved{font-size:10px;color:var(--text-muted,#5a6270);margin-top:3px}
    .ao-footer{padding:8px 14px;border-top:1px solid var(--border,#1e1f24);display:flex;align-items:center;gap:8px;background:var(--surface,#111217)}
    .ao-footer-health{font-size:11px;font-weight:600;color:#00BFB3}
    .ao-footer-health.warn{color:#FEC514}.ao-footer-health.crit{color:#F04E98}
    .ao-footer-link{font-size:11px;color:var(--text-muted,#5a6270);text-decoration:none}
    .ao-footer-link:hover{color:#00BFB3}
    .ao-open-btn{margin-left:auto;display:inline-flex;align-items:center;gap:5px;padding:5px 12px;border-radius:5px;background:#00BFB320;border:1px solid #00BFB340;color:#00BFB3;font-size:11px;font-weight:700;text-decoration:none;letter-spacing:.03em;transition:background .15s}
    .ao-open-btn:hover{background:#00BFB330;color:#00BFB3}
    .ao-comp-card{border:1px solid #FEC51430;border-radius:8px;margin:10px 0 4px;overflow:hidden;font-size:13px}
    .ao-comp-header{display:flex;align-items:center;gap:8px;padding:10px 14px;background:#FEC51408;border-bottom:1px solid #FEC51430}
    .ao-comp-title{font-weight:700;color:#FEC514;font-size:12px;letter-spacing:.03em;text-transform:uppercase}
    .ao-comp-sub{font-size:11px;color:var(--text-muted,#8b919a);margin-left:4px}
    .ao-comp-body{padding:10px 14px;background:var(--bg,#07080c)}
    .ao-comp-body ul{padding-left:0;list-style:none;display:flex;flex-direction:column;gap:6px}
    .ao-comp-body li{font-size:12px;color:var(--text-muted,#8b919a);line-height:1.5;padding-left:14px;position:relative}
    .ao-comp-body li::before{content:"•";position:absolute;left:0;color:#FEC514;font-weight:700}
  `;

  function injectStyles() {
    if (document.getElementById("ao-styles")) return;
    const s = document.createElement("style");
    s.id = "ao-styles";
    s.textContent = CSS;
    document.head.appendChild(s);
  }

  function healthDotClass(health) {
    if (health === "critical") return "crit";
    if (health === "warning") return "warn";
    return "";
  }

  function relativeTime(iso) {
    if (!iso) return "";
    const diff = (Date.now() - new Date(iso).getTime()) / 1000;
    if (diff < 60) return "just now";
    if (diff < 3600) return `${Math.round(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.round(diff / 3600)}h ago`;
    return `${Math.round(diff / 86400)}d ago`;
  }

  function renderAlerts(data) {
    const alerts = data.alerts || [];
    const health = data.health || "green";
    const clusters = (data.clusters || []).join(", ") || "fe-summit-hackathon";

    const dotClass = healthDotClass(health);
    const footerClass = dotClass;
    const healthLabel = health === "green"
      ? "All systems green"
      : health === "warning"
        ? `${data.warnings || 0} active warning${data.warnings !== 1 ? "s" : ""}`
        : `${data.criticals || 0} critical alert${data.criticals !== 1 ? "s" : ""}`;

    const alertsHtml = alerts.length === 0
      ? `<div class="ao-alert ao-sev-info"><div class="ao-alert-icon">✅</div><div class="ao-alert-body"><div class="ao-alert-title">No active alerts</div><div class="ao-alert-desc">Cluster is operating within healthy parameters.</div></div></div>`
      : alerts.map(a => {
          const sevClass = SEV_CLASS[a.severity] || "ao-sev-info";
          const icon = SEV_ICON[a.severity] || "🔵";
          const cat = CAT_LABEL[a.category] || (a.category || "");
          const resolvedHtml = a.resolved
            ? `<div class="ao-resolved">Resolved ${relativeTime(a.resolved_at)}</div>`
            : "";
          const recHtml = a.recommendation
            ? `<div class="ao-alert-rec">${a.recommendation}</div>`
            : "";
          return `<div class="ao-alert ${sevClass}">
            <div class="ao-alert-icon">${icon}</div>
            <div class="ao-alert-body">
              <div class="ao-alert-title">${a.title}<span class="ao-alert-cat">${cat}</span></div>
              <div class="ao-alert-desc">${a.description || ""}</div>
              ${recHtml}
              ${resolvedHtml}
            </div>
          </div>`;
        }).join("");

    return `<div class="ao-card">
      <div class="ao-header">
        <span class="ao-dot ${dotClass}"></span>
        <span class="ao-header-title">AutoOps · Cluster Signals</span>
        <span class="ao-header-cluster">${clusters} · us-west-1</span>
      </div>
      <div class="ao-body">${alertsHtml}</div>
      <div class="ao-footer">
        <span class="ao-footer-health ${footerClass}">${healthLabel}</span>
        <a class="ao-footer-link" href="https://www.elastic.co/platform/autoops" target="_blank" rel="noopener">elastic.co/autoops</a>
        <a class="ao-open-btn" href="https://app.auto-ops.cloud.elastic.co/regions/us-west-1/organizations/2427792696/deployments/ed0e8e5f57c041069ed419aa94054e09/overview?nodes=tGsVj5NRR-mumzjLgJOcBA,OgAEpWh5QBSkcjkGTaQSfg,pAGZ_naUTkGr58UC4c5jOQ,0QwS3a2BRmCo1om5UKYlzg&dataNodes=tGsVj5NRR-mumzjLgJOcBA,OgAEpWh5QBSkcjkGTaQSfg" target="_blank" rel="noopener">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
          Open AutoOps
        </a>
      </div>
    </div>`;
  }

  function renderCompetitiveCard(data) {
    const points = (data.points || []).map(p => `<li>${p}</li>`).join("");
    return `<div class="ao-comp-card">
      <div class="ao-comp-header">
        <span class="ao-comp-title">AutoOps vs Splunk</span>
        <span class="ao-comp-sub">- free diagnostic Splunk cannot match</span>
      </div>
      <div class="ao-comp-body"><ul>${points}</ul></div>
    </div>`;
  }

  async function mount(hostId) {
    const host = document.getElementById(hostId || "autoops-widget");
    if (!host) return;
    injectStyles();

    // Fetch alerts and competitive card in parallel
    const [alertsRes, compRes] = await Promise.allSettled([
      fetch("/api/v1/autoops/summary").then(r => r.ok ? r.json() : null),
      fetch("/api/v1/autoops/competitive").then(r => r.ok ? r.json() : null),
    ]);

    const alertData = alertsRes.status === "fulfilled" ? alertsRes.value : null;
    const compData = compRes.status === "fulfilled" ? compRes.value : null;

    let html = "";
    if (alertData) html += renderAlerts(alertData);
    if (compData) html += renderCompetitiveCard(compData);
    if (html) host.innerHTML = html;
  }

  // Auto-mount on DOMContentLoaded
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => mount());
  } else {
    mount();
  }

  window.AutoOpsWidget = { mount };
})();
