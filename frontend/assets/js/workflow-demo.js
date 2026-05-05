/*
  filename: workflow-demo.js
  description: Workflow demo page logic. Talks to /api/v1/workflows for sync, demo-fire, status, and recent webhook hits. Renders rule + connector ids and a live log of fires; auto-refreshes every 15 seconds.
  Author: Rodrigo Careaga
  Date: 03-05-2026
*/
(function () {
  const $status = document.getElementById("wf-status");
  const $fires = document.getElementById("wf-fires");
  const $fireResult = document.getElementById("wf-fire-result");
  const $btnSync = document.getElementById("wf-sync");
  const $btnRefresh = document.getElementById("wf-refresh");
  const $btnFire = document.getElementById("wf-fire");
  const $btnTriggerNow = document.getElementById("wf-trigger-now");

  let refreshTimer = null;

  function pill(label, kind) {
    return `<span class="wf-pill ${kind}">${label}</span>`;
  }

  function row(key, val) {
    return `<div class="wf-row"><span class="wf-key">${key}</span><span class="wf-val">${val ?? "-"}</span></div>`;
  }

  function fmtKind(s) {
    if (!s) return "warn";
    if (s === "registered") return "ok";
    if (s.startsWith("missing") || s.startsWith("probe-error")) return "err";
    return "warn";
  }

  function renderStatus(data) {
    const ruleKind = fmtKind(data.rule_status);
    const connKind = fmtKind(data.connector_status);
    const inboxPill = data.inbox_exists ? pill("exists", "ok") : pill("missing", "err");
    const overall = data.registered
      ? pill("workflow registered", "ok")
      : pill("not registered", "warn");
    $status.innerHTML = `
      <div style="margin-bottom: 12px;">${overall}</div>
      ${row("Rule status", `${pill(data.rule_status || "-", ruleKind)}`)}
      ${row("Rule id", `<code>${data.rule_id || "-"}</code>`)}
      ${row("Connector status", `${pill(data.connector_status || "-", connKind)}`)}
      ${row("Connector id", `<code>${data.connector_id || "-"}</code>`)}
      ${row("Inbox index", `<code>${data.inbox_index}</code> ${inboxPill}`)}
      ${row("Webhook URL", `<code>${data.webhook_url}</code>`)}
    `;
    renderFires(data.recent_fires || []);
  }

  function renderFires(fires) {
    if (!fires || fires.length === 0) {
      $fires.innerHTML = '<div class="wf-empty">No fires yet. Click "Fire demo transcript" and wait ~60 seconds.</div>';
      return;
    }
    $fires.innerHTML = fires
      .map((f) => {
        const ok = f.processed === true;
        const cls = ok ? "ok" : "err";
        const tag = ok ? "PROCESSED" : "SKIPPED";
        const when = f.received_at || "";
        const reason = f.reason ? `<div>reason: <code>${f.reason}</code></div>` : "";
        const post = f.post_meeting_id ? `<div>post-meeting id: <code>${f.post_meeting_id}</code></div>` : "";
        const company = f.company_name ? `<div>company: <code>${f.company_name}</code></div>` : "";
        const counts = f.processed
          ? `<div>action items: <strong>${f.action_items ?? 0}</strong> · SFDC tasks: <strong>${f.sfdc_tasks ?? 0}</strong></div>`
          : "";
        return `<div class="wf-fire">
          <span class="${cls}">[${tag}]</span> <span class="when">${when}</span>
          <div>matched docs: ${f.matched_docs ?? 0}</div>
          ${company}
          ${post}
          ${counts}
          ${reason}
        </div>`;
      })
      .join("");
  }

  async function loadStatus() {
    try {
      const data = await apiGet("/workflows/status");
      renderStatus(data);
    } catch (err) {
      $status.innerHTML = `<div class="wf-error-line">Status fetch failed: ${err.message}</div>`;
    }
  }

  async function loadFires() {
    try {
      const data = await apiGet("/workflows/recent-fires?limit=10");
      renderFires(data.fires || []);
    } catch (err) {
      // best-effort silent
    }
  }

  async function doSync() {
    $btnSync.disabled = true;
    $btnSync.textContent = "Syncing…";
    try {
      const r = await apiPost("/workflows/sync", {});
      $fireResult.innerHTML = `<div class="wf-result"><strong>Workflow synced.</strong>
        <pre>${JSON.stringify(r, null, 2)}</pre></div>`;
      await loadStatus();
    } catch (err) {
      $fireResult.innerHTML = `<div class="wf-result is-err"><strong>Sync failed:</strong> ${err.message}</div>`;
    } finally {
      $btnSync.disabled = false;
      $btnSync.textContent = "Sync workflow";
    }
  }

  async function doFire() {
    $btnFire.disabled = true;
    $btnFire.textContent = "Indexing transcript…";
    try {
      const r = await apiPost("/workflows/demo-fire", {});
      $fireResult.innerHTML = `<div class="wf-result">
        <strong>Transcript indexed into <code>${r.index}</code>.</strong>
        <div>doc id: <code>${r.doc_id}</code></div>
        <div class="wf-status-note">${r.note || ""}</div>
        <div style="margin-top:8px">Watching for the alerting rule to fire (auto-refresh every 15s)…</div>
      </div>`;
      // accelerate polling for ~3 minutes
      let ticks = 0;
      const fast = setInterval(async () => {
        ticks += 1;
        await loadFires();
        await loadStatus();
        if (ticks > 18) clearInterval(fast); // 18 * 10s = 3 min
      }, 10000);
    } catch (err) {
      $fireResult.innerHTML = `<div class="wf-result is-err"><strong>Fire failed:</strong> ${err.message}</div>`;
    } finally {
      $btnFire.disabled = false;
      $btnFire.textContent = "Fire demo transcript";
    }
  }

  async function doTriggerNow() {
    $btnTriggerNow.disabled = true;
    $btnTriggerNow.textContent = "Triggering…";
    try {
      // Directly invoke the webhook endpoint with a synthetic payload so we don't have to wait
      // for the Kibana scheduler. The handler will look up the most recent unprocessed doc.
      const r = await apiPost("/workflows/triggered", {
        alert_id: "manual-trigger",
        rule_id: "manual",
        rule_name: "manual-bypass",
      });
      $fireResult.innerHTML = `<div class="wf-result">
        <strong>Manual trigger result:</strong>
        <pre>${JSON.stringify(r, null, 2)}</pre>
      </div>`;
      await loadStatus();
    } catch (err) {
      $fireResult.innerHTML = `<div class="wf-result is-err"><strong>Trigger failed:</strong> ${err.message}</div>`;
    } finally {
      $btnTriggerNow.disabled = false;
      $btnTriggerNow.textContent = "Trigger now (skip wait)";
    }
  }

  function startAutoRefresh() {
    if (refreshTimer) clearInterval(refreshTimer);
    refreshTimer = setInterval(loadStatus, 15000);
  }

  $btnSync.addEventListener("click", doSync);
  $btnRefresh.addEventListener("click", loadStatus);
  $btnFire.addEventListener("click", doFire);
  $btnTriggerNow.addEventListener("click", doTriggerNow);

  loadStatus();
  startAutoRefresh();
})();
