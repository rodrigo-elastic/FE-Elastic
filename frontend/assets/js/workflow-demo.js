/*
  filename: workflow-demo.js
  description: FE Copilot - Workflow demo page. Fires the three Kibana workflows and renders the activity log.
  Author: Rodrigo Careaga
  Date: 08-05-2026
*/
(function () {
  "use strict";

  var $log = document.getElementById("wf-log");

  // ------------------------------------------------------------------ helpers

  function _relTime(iso) {
    if (!iso) return "";
    var d = new Date(iso);
    if (isNaN(d.getTime())) return iso.slice(0, 16).replace("T", " ");
    var diffMs = Date.now() - d.getTime();
    if (diffMs < 60000)   return "just now";
    if (diffMs < 3600000) return Math.floor(diffMs / 60000) + "m ago";
    if (diffMs < 86400000) return Math.floor(diffMs / 3600000) + "h ago";
    return Math.floor(diffMs / 86400000) + "d ago";
  }

  function showResult(el, msg, isErr) {
    if (!el) return;
    el.textContent = msg;
    el.className = "wf-card-result visible" + (isErr ? " err" : "");
  }

  function busy(btn, label) {
    btn.disabled = true;
    btn._orig = btn.textContent;
    btn.textContent = label || "Running...";
  }

  function done(btn) {
    btn.disabled = false;
    btn.textContent = btn._orig || "Fire";
  }

  // ------------------------------------------------------------------ log

  function renderLog(fires) {
    if (!fires || !fires.length) {
      $log.innerHTML = '<div class="wf-log-empty">No activity yet. Fire a workflow above.</div>';
      return;
    }
    $log.innerHTML = fires.map(function (f) {
      var ok = f.processed === true;
      var company = f.company_name || f.account_name || "";
      var workflow = f.workflow === "orphan-action" ? "Orphan action" : f.workflow === "renewal" ? "Renewal defense" : "Post-meeting";
      var when = _relTime(f.received_at || f.created_at || "");
      var detail = "";
      if (ok && f.action_items != null) detail += f.action_items + " action items";
      if (ok && f.sfdc_tasks)  detail += (detail ? " - " : "") + f.sfdc_tasks + " SFDC tasks";
      if (ok && f.tasks_created != null) detail += (detail ? " - " : "") + f.tasks_created + " tasks created";
      if (!ok && f.reason)     detail = f.reason;
      return (
        '<div class="wf-log-row">' +
        '<div class="wf-log-dot ' + (ok ? "ok" : "skip") + '"></div>' +
        '<div class="wf-log-body">' +
        '<div class="wf-log-company">' +
        "<strong>" + (company ? company : workflow) + "</strong>" +
        " " +
        '<span class="wf-pill ' + (ok ? "ok" : "skip") + '">' + (ok ? "done" : "skipped") + "</span>" +
        "</div>" +
        '<div class="wf-log-meta">' + (ok ? "&#x2713; " : "- ") + workflow + (when ? " &bull; " + when : "") + (detail ? " &bull; " + detail : "") + "</div>" +
        "</div>" +
        "</div>"
      );
    }).join("");
  }

  function loadLog() {
    apiGet("/workflows/recent-fires?limit=12")
      .then(function (d) { renderLog(d.fires || []); })
      .catch(function () {});
  }

  // ------------------------------------------------------------------ workflow 1: post-meeting

  document.getElementById("wf-fire").addEventListener("click", function () {
    var btn = this;
    var res = document.getElementById("wf-fire-result");
    busy(btn, "Indexing...");
    showResult(res, "", false);

    apiPost("/workflows/demo-fire", {})
      .then(function () {
        showResult(res, "Transcript indexed. Kibana rule fires within ~60s - watch the log below.");
        var ticks = 0;
        var t = setInterval(function () {
          loadLog();
          if (++ticks >= 18) clearInterval(t);
        }, 10000);
      })
      .catch(function (e) {
        showResult(res, (typeof sanitizeError === "function" ? sanitizeError(e) : e.message) || "Failed", true);
      })
      .finally(function () { done(btn); });
  });

  // ------------------------------------------------------------------ workflow 2: orphan action

  document.getElementById("wf-fire-orphan").addEventListener("click", function () {
    var btn = this;
    var res = document.getElementById("wf-orphan-result");
    busy(btn, "Running...");
    showResult(res, "", false);

    apiPost("/workflows/orphan-demo-fire", {})
      .then(function () {
        return apiPost("/workflows/post-meeting-action-orphan", { alert_id: "manual", rule_id: "manual", rule_name: "manual" });
      })
      .then(function (d) {
        var n = (d && d.tasks_created) || 0;
        showResult(res, n + " Salesforce task" + (n !== 1 ? "s" : "") + " created for unassigned high-impact items.");
        loadLog();
      })
      .catch(function (e) {
        showResult(res, (typeof sanitizeError === "function" ? sanitizeError(e) : e.message) || "Failed", true);
      })
      .finally(function () { done(btn); });
  });

  // ------------------------------------------------------------------ workflow 3: renewal defense

  document.getElementById("wf-fire-renewal").addEventListener("click", function () {
    var btn = this;
    var res = document.getElementById("wf-renewal-result");
    busy(btn, "Running...");
    showResult(res, "", false);

    apiPost("/workflows/renewal-demo-fire", {})
      .then(function (d) {
        var p = (d && d.play) || {};
        var msg = (p.account_name || "Account") + " - severity " + (p.severity || "?") + " - due " + (p.due_date || "?") + ". " + (p.retention_play || "").slice(0, 160);
        showResult(res, msg);
        loadLog();
      })
      .catch(function (e) {
        showResult(res, (typeof sanitizeError === "function" ? sanitizeError(e) : e.message) || "Failed", true);
      })
      .finally(function () { done(btn); });
  });

  // ------------------------------------------------------------------ init

  loadLog();
  setInterval(loadLog, 15000);
})();
