/*
  filename: workflow-settings.js
  description: FE Copilot - Workflow Settings controller. Optimistic toggle updates, auto-sync from Kibana every 30s, create/delete rules, per-rule notification channels.
  Author: Rodrigo Careaga
  Date: 08-05-2026
*/
(function () {
  "use strict";

  var OUTPUT_DEFS = [
    { key: "slack", label: "Slack" },
    { key: "email", label: "Email" },
  ];

  var _lastSynced = null;
  var _selectedTemplate = null;
  var _templates = [];
  var _ruleChannels = {}; // { ruleId: { slack: bool, email: bool, ... } }

  // ------------------------------------------------------------------ Toast

  function _injectToastStyles() {
    if (document.getElementById("ws-toast-style")) return;
    var s = document.createElement("style");
    s.id = "ws-toast-style";
    s.textContent = [
      "#ws-toast { position: fixed; bottom: 20px; right: 20px; background: var(--teal); color: #fff;",
      "  padding: 8px 16px; border-radius: 6px; font-size: 13px; font-weight: 600;",
      "  opacity: 0; transform: translateY(6px); transition: opacity .2s, transform .2s;",
      "  pointer-events: none; z-index: 9999; }",
      "#ws-toast.visible { opacity: 1; transform: translateY(0); }",
    ].join("\n");
    document.head.appendChild(s);
  }

  function _showToast(msg) {
    var el = document.getElementById("ws-toast");
    if (!el) {
      el = document.createElement("div");
      el.id = "ws-toast";
      document.body.appendChild(el);
    }
    el.textContent = msg;
    el.classList.add("visible");
    setTimeout(function () { el.classList.remove("visible"); }, 2000);
  }

  _injectToastStyles();

  // ------------------------------------------------------------------ utils

  function esc(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function pill(text, cls) {
    return '<span class="ws-pill ' + cls + '">' + esc(text) + "</span>";
  }

  function toggleHtml(id, checked) {
    return (
      '<label class="ws-toggle" title="' + (checked ? "Click to disable" : "Click to enable") + '">' +
      '<input type="checkbox" id="' + id + '"' + (checked ? " checked" : "") + " />" +
      '<span class="ws-slider"></span>' +
      "</label>"
    );
  }

  function updateSyncedLabel() {
    var el = document.getElementById("ws-synced");
    if (!el || !_lastSynced) return;
    var secs = Math.round((Date.now() - _lastSynced) / 1000);
    el.textContent = secs < 5 ? "Synced just now" : "Synced " + secs + "s ago";
  }

  // ------------------------------------------------------------------ Per-rule output chips

  function _defaultRuleOutputs() {
    return { slack: true, email: false };
  }

  function _renderOutputChips(ruleId) {
    var ch = _ruleChannels[ruleId] || _defaultRuleOutputs();
    return (
      '<div class="ws-rule-channels" id="rch-' + esc(ruleId) + '" style="display:none;">' +
      '<div class="ws-rule-ch-label">Notify via</div>' +
      '<div class="ws-ch-chips">' +
      OUTPUT_DEFS.map(function (def) {
        var checked = Object.prototype.hasOwnProperty.call(ch, def.key) ? ch[def.key] : false;
        return (
          '<label class="ws-ch-chip">' +
          '<input type="checkbox" data-rule-id="' + esc(ruleId) + '" data-out-key="' + esc(def.key) + '"' + (checked ? " checked" : "") + " />" +
          esc(def.label) +
          "</label>"
        );
      }).join("") +
      "</div></div>"
    );
  }

  function _saveRuleOutputs(ruleId) {
    var patch = {};
    patch[ruleId] = _ruleChannels[ruleId];
    apiPut("/workflow-settings", { rule_channels: patch })
      .then(function () { _showToast("Saved"); })
      .catch(function (err) {
        _showToast("Save failed: " + (typeof sanitizeError === "function" ? sanitizeError(err) : (err.message || "error")));
      });
  }

  // ------------------------------------------------------------------ Rules: render

  function renderRules(rules, kibanaUrl) {
    var el = document.getElementById("ws-rules");
    if (!el) return;

    var kibanaLink = document.getElementById("ws-kibana-link");
    if (kibanaLink && kibanaUrl) {
      kibanaLink.href = kibanaUrl + "/app/management/insightsAndAlerting/triggersActions/rules";
    }

    if (!rules.length) {
      el.innerHTML = '<div class="ws-loading">No automation rules found. Add one below.</div>';
      return;
    }

    el.innerHTML = rules.map(function (rule) {
      var on = !!rule.enabled;
      return (
        '<div class="ws-rule-wrap">' +
        '<div class="ws-row" data-rule-id="' + esc(rule.id) + '">' +
        '<div class="ws-row-info ws-row-clickable" data-expand-id="' + esc(rule.id) + '">' +
        '<div class="ws-row-label">' + esc(rule.name) + ' <span class="ws-expand-arrow" id="arrow-' + esc(rule.id) + '">&#9656;</span></div>' +
        '<div class="ws-row-sub">every ' + esc((rule.schedule && rule.schedule.interval) || "1m") + "</div>" +
        '<div class="ws-row-status" id="rs-' + esc(rule.id) + '"></div>' +
        "</div>" +
        pill(on ? "on" : "off", on ? "on" : "off") +
        toggleHtml("rule-" + rule.id, on) +
        '<button class="ws-del-btn" data-del-id="' + esc(rule.id) + '" title="Delete rule">&times;</button>' +
        "</div>" +
        _renderOutputChips(rule.id) +
        "</div>"
      );
    }).join("");

    // Expand/collapse per-rule output panel
    el.querySelectorAll(".ws-row-clickable").forEach(function (info) {
      info.addEventListener("click", function () {
        var ruleId = info.getAttribute("data-expand-id");
        var panel = document.getElementById("rch-" + ruleId);
        var arrow = document.getElementById("arrow-" + ruleId);
        if (!panel) return;
        var open = panel.style.display !== "none";
        panel.style.display = open ? "none" : "block";
        if (arrow) arrow.textContent = open ? "▶" : "▼";
        if (open) {
          sessionStorage.removeItem("ws.expanded." + ruleId);
        } else {
          sessionStorage.setItem("ws.expanded." + ruleId, "1");
        }
      });
    });

    // Restore expanded panels from sessionStorage
    rules.forEach(function (rule) {
      if (sessionStorage.getItem("ws.expanded." + rule.id)) {
        var panel = document.getElementById("rch-" + rule.id);
        var arrow = document.getElementById("arrow-" + rule.id);
        if (panel) panel.style.display = "block";
        if (arrow) arrow.textContent = "▼";
      }
    });

    // Per-rule output chip handlers — auto-save on change
    el.querySelectorAll("input[data-out-key]").forEach(function (input) {
      input.addEventListener("change", function () {
        var ruleId = input.getAttribute("data-rule-id");
        var outKey = input.getAttribute("data-out-key");
        if (!_ruleChannels[ruleId]) _ruleChannels[ruleId] = _defaultRuleOutputs();
        _ruleChannels[ruleId][outKey] = input.checked;
        _saveRuleOutputs(ruleId);
      });
    });

    // Toggle enable/disable handlers
    el.querySelectorAll('input[id^="rule-"]').forEach(function (input) {
      input.addEventListener("change", function () {
        var ruleId = input.id.slice(5);
        var action = input.checked ? "enable" : "disable";
        var row = input.closest(".ws-row");
        var badge = row && row.querySelector(".ws-pill");
        var status = document.getElementById("rs-" + ruleId);

        input.disabled = true;
        if (badge) { badge.className = "ws-pill " + (input.checked ? "on" : "off"); badge.textContent = input.checked ? "on" : "off"; }
        if (status) { status.className = "ws-row-status applying"; status.textContent = "Applying..."; }

        apiPost("/workflow-settings/kibana-rule/" + ruleId + "/" + action, {})
          .then(function () {
            input.disabled = false;
            _lastSynced = Date.now();
            updateSyncedLabel();
            if (status) { status.className = "ws-row-status"; status.textContent = ""; }
          })
          .catch(function () {
            input.checked = !input.checked;
            input.disabled = false;
            if (badge) { badge.className = "ws-pill " + (input.checked ? "on" : "off"); badge.textContent = input.checked ? "on" : "off"; }
            if (status) { status.className = "ws-row-status err"; status.textContent = "Failed - check Kibana"; }
            setTimeout(function () { if (status) { status.className = "ws-row-status"; status.textContent = ""; } }, 3000);
          });
      });
    });

    // Delete handlers
    el.querySelectorAll("[data-del-id]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var ruleId = btn.getAttribute("data-del-id");
        var wrap = btn.closest(".ws-rule-wrap");
        var name = wrap && wrap.querySelector(".ws-row-label");
        var label = name ? name.textContent.trim() : "this rule";
        if (!confirm("Delete \"" + label + "\"?\n\nThis removes it from Kibana.")) return;
        btn.disabled = true;
        btn.textContent = "...";
        apiDelete("/workflow-settings/rules/" + ruleId)
          .then(function () { loadRules(); })
          .catch(function () {
            btn.disabled = false;
            btn.textContent = "\xd7";
          });
      });
    });
  }

  // ------------------------------------------------------------------ Rules: load / quiet sync

  function loadRules() {
    var el = document.getElementById("ws-rules");
    if (el) el.innerHTML = '<div class="ws-loading">Loading...</div>';

    Promise.all([
      apiGet("/workflow-settings/kibana-status"),
      apiGet("/workflow-settings"),
    ]).then(function (results) {
      var kibanaData = results[0];
      var settingsData = results[1];
      _ruleChannels = settingsData.rule_channels || {};
      _lastSynced = Date.now();
      updateSyncedLabel();
      if (!kibanaData.kibana_configured) {
        if (el) el.innerHTML = '<div class="ws-error">KIBANA_API_KEY not configured.</div>';
        return;
      }
      var kibanaLink = document.getElementById("ws-kibana-link");
      if (kibanaLink && kibanaData.kibana_url) {
        kibanaLink.href = kibanaData.kibana_url + "/app/management/insightsAndAlerting/triggersActions/rules";
      }
      renderRules(kibanaData.rules || [], kibanaData.kibana_url || "");
    }).catch(function (err) {
      if (el) el.innerHTML = '<div class="ws-error">Could not reach Kibana.</div>';
      _showToast("Failed to load rules: " + (typeof sanitizeError === "function" ? sanitizeError(err) : (err.message || "error")));
    });
  }

  function syncRulesQuiet() {
    apiGet("/workflow-settings/kibana-status")
      .then(function (data) {
        _lastSynced = Date.now();
        updateSyncedLabel();
        if (!data.kibana_configured) return;
        (data.rules || []).forEach(function (rule) {
          var input = document.getElementById("rule-" + rule.id);
          var row = input && input.closest(".ws-row");
          var badge = row && row.querySelector(".ws-pill");
          if (input && !input.disabled) {
            var kibanaOn = !!rule.enabled;
            if (input.checked !== kibanaOn) {
              input.checked = kibanaOn;
              if (badge) { badge.className = "ws-pill " + (kibanaOn ? "on" : "off"); badge.textContent = kibanaOn ? "on" : "off"; }
            }
          }
        });
      })
      .catch(function () {});
  }

  // ------------------------------------------------------------------ Add rule form

  function loadTemplates() {
    apiGet("/workflow-settings/rule-templates")
      .then(function (data) {
        _templates = data.templates || [];
        var container = document.getElementById("ws-templates");
        if (!container) return;
        container.innerHTML = _templates.map(function (t) {
          return (
            '<div class="ws-tmpl-card" data-tmpl-id="' + esc(t.id) + '">' +
            '<div class="ws-tmpl-label">' + esc(t.label) + "</div>" +
            '<div class="ws-tmpl-desc">' + esc(t.desc) + "</div>" +
            "</div>"
          );
        }).join("");

        container.querySelectorAll(".ws-tmpl-card").forEach(function (card) {
          card.addEventListener("click", function () {
            container.querySelectorAll(".ws-tmpl-card").forEach(function (c) { c.classList.remove("selected"); });
            card.classList.add("selected");
            _selectedTemplate = card.getAttribute("data-tmpl-id");

            var tmpl = _templates.find(function (t) { return t.id === _selectedTemplate; });
            var fields = document.getElementById("ws-add-fields");
            var nameInput = document.getElementById("ws-rule-name");
            var indexInput = document.getElementById("ws-rule-index");
            if (fields) { fields.style.display = "flex"; }
            if (nameInput && tmpl) nameInput.value = tmpl.default_name || "";
            if (indexInput && tmpl) indexInput.value = tmpl.index || "";
          });
        });
      })
      .catch(function () {});
  }

  function openAddForm() {
    var form = document.getElementById("ws-add-form");
    var fields = document.getElementById("ws-add-fields");
    var msg = document.getElementById("ws-add-msg");
    if (!form) return;
    form.style.display = "block";
    if (fields) fields.style.display = "none";
    if (msg) msg.textContent = "";
    _selectedTemplate = null;
    var tmplContainer = document.getElementById("ws-templates");
    if (tmplContainer) tmplContainer.querySelectorAll(".ws-tmpl-card").forEach(function (c) { c.classList.remove("selected"); });
    loadTemplates();
  }

  function closeAddForm() {
    var form = document.getElementById("ws-add-form");
    if (form) form.style.display = "none";
    _selectedTemplate = null;
  }

  function submitAddRule() {
    if (!_selectedTemplate) return;
    var nameInput = document.getElementById("ws-rule-name");
    var indexInput = document.getElementById("ws-rule-index");
    var scheduleInput = document.getElementById("ws-rule-schedule");
    var submitBtn = document.getElementById("ws-add-submit");
    var msg = document.getElementById("ws-add-msg");

    var name = nameInput ? nameInput.value.trim() : "";
    var index = indexInput ? indexInput.value.trim() : "";
    var schedule = scheduleInput ? scheduleInput.value : "1m";

    if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = "Creating..."; }
    if (msg) msg.textContent = "";

    apiPost("/workflow-settings/rules", { template: _selectedTemplate, name: name, schedule: schedule, index: index })
      .then(function () {
        closeAddForm();
        loadRules();
      })
      .catch(function (e) {
        if (msg) msg.textContent = (typeof sanitizeError === "function" ? sanitizeError(e) : "Error creating rule");
        if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = "Create rule"; }
      });
  }

  // ------------------------------------------------------------------ apiDelete helper

  function apiDelete(path) {
    return fetch((window.FEC_API_BASE ? window.FEC_API_BASE.replace(/\/+$/, "") : "") + "/api/v1" + path, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
    }).then(function (res) {
      if (!res.ok) throw new Error("DELETE " + path + " failed: " + res.status);
      return res.status === 204 ? {} : res.json();
    });
  }

  // ------------------------------------------------------------------ Channels (global)

  function loadChannels() {
    var el = document.getElementById("ws-channels");
    if (!el) return;

    Promise.all([
      apiGet("/workflow-settings"),
      apiGet("/workflow-settings/channels-status"),
    ]).then(function (results) {
      var cfg = results[0];
      var health = results[1];
      var vals = cfg.notification_channels || {};
      var slackOn = !!vals.slack;
      var emailOn = !!vals.email;
      var slackChannel = cfg.slack_channel || "#fe-copilot-briefs";
      var emailAddress = cfg.email_address || "";
      var slackLive = health && health.slack && health.slack.mode === "live";
      var emailKibana = health && health.email && health.email.mode === "kibana";
      var emailConnectorName = (health && health.email && health.email.connector_name) || "";

      var html = "";

      // Slack destination
      html +=
        '<div class="ws-row">' +
        '<div class="ws-row-info">' +
        '<div class="ws-row-label">Slack ' + pill(slackLive ? "live" : "dry-run", slackLive ? "on" : "warn") + "</div>" +
        '<div class="ws-ch-input-wrap">' +
        '<input id="ch-slack-channel" type="text" class="ws-ch-input" placeholder="#channel-name" value="' + esc(slackChannel) + '" />' +
        "</div>" +
        "</div>" +
        toggleHtml("ch-slack", slackOn) +
        "</div>";

      // Email destination
      var emailMode = health && health.email && health.email.mode;
      var emailBadge = emailMode === "email"
        ? pill(emailConnectorName || "Elastic Cloud email", "on")
        : (emailAddress ? pill("address set", "warn") : pill("not set", "warn"));
      html +=
        '<div class="ws-row">' +
        '<div class="ws-row-info">' +
        '<div class="ws-row-label">Email ' + emailBadge + "</div>" +
        '<div class="ws-ch-input-wrap" style="display:flex;gap:6px;align-items:center;">' +
        '<input id="ch-email-address" type="email" class="ws-ch-input" placeholder="you@elastic.co" value="' + esc(emailAddress) + '" style="flex:1;" />' +
        '<button id="ch-email-sync" class="btn btn-sm btn-secondary" title="Apply email to all Kibana rules now" style="white-space:nowrap;font-size:11px;padding:3px 8px;">Sync to Kibana</button>' +
        "</div>" +
        "</div>" +
        toggleHtml("ch-email", emailOn) +
        "</div>";

      el.innerHTML = html;

      // Wire the sync button after rendering.
      var syncBtn = document.getElementById("ch-email-sync");
      if (syncBtn) {
        syncBtn.addEventListener("click", function () {
          var addrEl = document.getElementById("ch-email-address");
          var addr = addrEl ? addrEl.value.trim() : "";
          syncBtn.disabled = true;
          syncBtn.textContent = "Syncing...";
          // If address changed, save first, then sync; otherwise just sync.
          var saveFirst = addr && addr !== emailAddress;
          var savePromise = saveFirst
            ? apiPut("/workflow-settings", { email_address: addr })
            : Promise.resolve(null);
          savePromise
            .then(function () {
              return apiPost("/workflow-settings/sync-email", {});
            })
            .then(function (res) {
              syncBtn.textContent = "Sync to Kibana";
              syncBtn.disabled = false;
              _showToast("Email applied to " + res.rules_updated + " Kibana rule(s)");
              loadChannels();
            })
            .catch(function (err) {
              syncBtn.textContent = "Sync to Kibana";
              syncBtn.disabled = false;
              var raw = err && err.message ? err.message : String(err);
              var detail = raw.replace(/^POST [^ ]+ failed: \d+ - /, "");
              _showToast("Sync failed: " + detail);
            });
        });
      }
    }).catch(function () {
      var el2 = document.getElementById("ws-channels");
      if (el2) el2.innerHTML = '<div class="ws-error">Failed to load channels.</div>';
    });
  }

  function saveChannels() {
    var msgEl = document.getElementById("ws-save-msg");

    var slackToggle = document.getElementById("ch-slack");
    var emailToggle = document.getElementById("ch-email");
    var channels = {
      slack: slackToggle ? slackToggle.checked : false,
      email: emailToggle ? emailToggle.checked : false,
    };

    var slackChannelEl = document.getElementById("ch-slack-channel");
    var emailAddressEl = document.getElementById("ch-email-address");
    var slackChannel = slackChannelEl ? slackChannelEl.value.trim() : "";
    var emailAddress = emailAddressEl ? emailAddressEl.value.trim() : "";

    apiPut("/workflow-settings", {
      notification_channels: channels,
      slack_channel: slackChannel,
      email_address: emailAddress,
    })
      .then(function (res) {
        var sync = res && res._email_sync;
        if (sync && !sync.ok) {
          _showToast("Saved - email sync failed: " + (sync.error || "no .email connector in Kibana"));
          if (msgEl) { msgEl.textContent = "Email sync failed"; setTimeout(function () { msgEl.textContent = ""; }, 5000); }
        } else if (sync && sync.ok) {
          _showToast("Saved - email applied to " + sync.rules_updated + " Kibana rule(s)");
          if (msgEl) { msgEl.textContent = "Saved"; setTimeout(function () { msgEl.textContent = ""; }, 2000); }
        } else {
          _showToast("Saved");
          if (msgEl) { msgEl.textContent = "Saved"; setTimeout(function () { msgEl.textContent = ""; }, 2000); }
        }
        loadChannels();
      })
      .catch(function (err) {
        var msg = typeof sanitizeError === "function" ? sanitizeError(err) : (err.message || "error");
        if (msgEl) { msgEl.textContent = "Error: " + msg; setTimeout(function () { msgEl.textContent = ""; }, 3000); }
      });
  }

  // ------------------------------------------------------------------ Init

  function init() {
    document.getElementById("ws-refresh").addEventListener("click", loadRules);
    document.getElementById("ws-save").addEventListener("click", saveChannels);
    document.getElementById("ws-add-rule").addEventListener("click", openAddForm);
    document.getElementById("ws-add-cancel").addEventListener("click", closeAddForm);
    document.getElementById("ws-add-submit").addEventListener("click", submitAddRule);

    loadRules();
    loadChannels();

    setInterval(syncRulesQuiet, 30000);
    setInterval(updateSyncedLabel, 5000);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
