/*
  filename: agent-builder-tools.js
  description: Custom-tool CRUD UI for the Agent Builder page. Lists user tools (prefixed `fec_user_tool_`) in the left rail and drives the create-tool modal that POSTs to /api/v1/agent-builder/tools. Built-in MCP tools (lock-icon) are read-only and surfaced via the same list but cannot be edited or deleted here.
  Author: Rodrigo Careaga
  Date: 05-13-2026
*/
(function () {
  "use strict";

  const USER_TOOL_PREFIX = "fec_user_tool_";
  const PARAM_TYPES = ["string", "integer", "number", "boolean", "date", "keyword"];

  function $(sel) { return document.querySelector(sel); }
  function $$(sel) { return Array.from(document.querySelectorAll(sel)); }

  function toast(msg, kind) {
    if (typeof window.toast === "function") return window.toast(msg, kind || "ok");
    if (kind === "bad") console.error("[ab-tools]", msg);
    else console.log("[ab-tools]", msg);
  }

  async function api(method, path, body) {
    const opts = { category: method === "GET" ? "compute" : "workflow", timeoutMs: 30000, silent: true, label: "AB tool" };
    if (method === "GET" && typeof window.apiGetWithRetry === "function") return window.apiGetWithRetry(path, opts);
    if (method === "POST" && typeof window.apiPostWithRetry === "function") return window.apiPostWithRetry(path, body, opts);
    if (method === "PUT") {
      const url = "/api/v1" + path;
      const r = await fetch(url, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      if (!r.ok) throw new Error(`PUT ${path} -> ${r.status}`);
      return r.json();
    }
    if (method === "DELETE" && typeof window.apiDeleteWithRetry === "function") return window.apiDeleteWithRetry(path, opts);
    // Fallback to legacy api.js helpers.
    if (method === "GET" && typeof window.apiGet === "function") return window.apiGet(path);
    if (method === "POST" && typeof window.apiPost === "function") return window.apiPost(path, body);
    throw new Error("no API helper available");
  }

  // ============================================================ List rail

  async function refreshToolsList() {
    const host = $("#ab-tools-list");
    if (!host) return;
    host.innerHTML = '<div class="ab-sidebar-item ab-muted">Loading tools...</div>';
    try {
      const data = await api("GET", "/agent-builder/tools");
      const tools = (data && data.tools) || [];
      if (!tools.length) {
        host.innerHTML = '<div class="ab-sidebar-item ab-muted">No tools registered yet.</div>';
        return;
      }
      const userTools = tools.filter((t) => String(t.id || "").startsWith(USER_TOOL_PREFIX));
      const builtIn = tools.filter((t) => !String(t.id || "").startsWith(USER_TOOL_PREFIX));
      host.innerHTML = "";
      if (userTools.length) {
        userTools.forEach((t) => host.appendChild(renderToolRow(t, false)));
      } else {
        host.appendChild(makeNode('<div class="ab-sidebar-item ab-muted">No custom tools yet. Click + above to add one.</div>'));
      }
      if (builtIn.length) {
        const sep = makeNode('<div class="ab-sidebar-sep" style="margin-top:10px;font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);padding:8px 0 4px">Built-in (' + builtIn.length + ')</div>');
        host.appendChild(sep);
        builtIn.slice(0, 16).forEach((t) => host.appendChild(renderToolRow(t, true)));
      }
    } catch (e) {
      host.innerHTML = '<div class="ab-sidebar-item ab-muted">Tools unavailable: ' + (e && e.message ? e.message : "unknown") + "</div>";
    }
  }

  function makeNode(html) {
    const wrap = document.createElement("div");
    wrap.innerHTML = html;
    return wrap.firstElementChild;
  }

  function renderToolRow(tool, readOnly) {
    const row = document.createElement("div");
    row.className = "ab-sidebar-item" + (readOnly ? " ab-readonly" : "");
    row.setAttribute("role", "listitem");
    const id = tool.id || tool.tool_id || "";
    const name = tool.name || tool.description || id;
    const tags = Array.isArray(tool.tags) ? tool.tags : [];
    row.innerHTML = `
      <div style="display:flex;align-items:center;gap:8px;justify-content:space-between">
        <div style="min-width:0;flex:1">
          <div style="font-weight:600;font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
            ${readOnly ? '<span title="Built-in tool (read-only)" aria-hidden="true">&#128274; </span>' : ''}${escapeHtml(name)}
          </div>
          <div style="font-size:11px;color:var(--muted);font-family:ui-monospace,monospace;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escapeHtml(id)}</div>
          ${tags.length ? '<div style="margin-top:4px;display:flex;gap:4px;flex-wrap:wrap">' + tags.slice(0, 4).map((t) => '<span class="ab-tool-tag">' + escapeHtml(t) + '</span>').join('') + '</div>' : ''}
        </div>
        ${readOnly ? '' : '<button type="button" class="ab-sidebar-del" title="Delete this custom tool" aria-label="Delete tool ' + escapeAttr(id) + '">&times;</button>'}
      </div>
    `;
    const delBtn = row.querySelector(".ab-sidebar-del");
    if (delBtn) {
      delBtn.addEventListener("click", async (ev) => {
        ev.stopPropagation();
        if (!confirm("Delete custom tool '" + id + "'? Agents referencing it will lose access.")) return;
        try {
          await api("DELETE", "/agent-builder/tools/" + encodeURIComponent(id));
          toast("Deleted " + id, "ok");
          refreshToolsList();
        } catch (e) {
          toast("Delete failed: " + (e && e.message ? e.message : "unknown"), "bad");
        }
      });
    }
    return row;
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }
  function escapeAttr(s) { return escapeHtml(s); }

  // ============================================================ Modal

  function openModal() {
    const m = $("#ab-tool-modal");
    if (!m) return;
    m.hidden = false;
    // Seed with one empty param row.
    if (!$("#ab-tf-params").childElementCount) addParamRow();
    setTimeout(() => $("#ab-tf-slug").focus(), 30);
  }
  function closeModal() {
    const m = $("#ab-tool-modal");
    if (m) m.hidden = true;
  }

  function addParamRow(seed) {
    const host = $("#ab-tf-params");
    if (!host) return;
    const idx = host.children.length;
    const row = document.createElement("div");
    row.className = "ab-param-row";
    row.dataset.idx = String(idx);
    row.innerHTML = `
      <div style="display:grid;grid-template-columns: 1fr 110px 1fr 90px 1fr auto; gap:6px; align-items:center; margin-top:6px">
        <input type="text" class="ab-tp-name" placeholder="paramName" autocomplete="off" pattern="[a-zA-Z_][a-zA-Z0-9_]*" maxlength="40" />
        <select class="ab-tp-type">${PARAM_TYPES.map((t) => '<option value="' + t + '">' + t + '</option>').join('')}</select>
        <input type="text" class="ab-tp-desc" placeholder="Description shown to the agent" maxlength="400" />
        <label style="font-size:11px;color:var(--muted);display:flex;align-items:center;gap:4px"><input type="checkbox" class="ab-tp-opt" /> optional</label>
        <input type="text" class="ab-tp-default" placeholder="default (optional)" />
        <button type="button" class="ab-tp-remove" title="Remove param" aria-label="Remove parameter">&times;</button>
      </div>
    `;
    if (seed) {
      row.querySelector(".ab-tp-name").value = seed.name || "";
      row.querySelector(".ab-tp-type").value = PARAM_TYPES.includes(seed.type) ? seed.type : "string";
      row.querySelector(".ab-tp-desc").value = seed.description || "";
      row.querySelector(".ab-tp-opt").checked = !!seed.optional;
      row.querySelector(".ab-tp-default").value = seed.defaultValue == null ? "" : String(seed.defaultValue);
    }
    row.querySelector(".ab-tp-remove").addEventListener("click", () => row.remove());
    host.appendChild(row);
  }

  function readParams() {
    const out = {};
    $$(".ab-param-row").forEach((row) => {
      const name = (row.querySelector(".ab-tp-name").value || "").trim();
      if (!name) return;
      const type = row.querySelector(".ab-tp-type").value;
      const desc = (row.querySelector(".ab-tp-desc").value || "").trim() || name;
      const opt = row.querySelector(".ab-tp-opt").checked;
      const defRaw = (row.querySelector(".ab-tp-default").value || "").trim();
      const spec = { type, description: desc };
      if (opt) spec.optional = true;
      if (defRaw !== "") spec.defaultValue = coerce(defRaw, type);
      out[name] = spec;
    });
    return out;
  }

  function coerce(raw, type) {
    if (type === "integer") { const n = parseInt(raw, 10); return Number.isFinite(n) ? n : raw; }
    if (type === "number") { const n = parseFloat(raw); return Number.isFinite(n) ? n : raw; }
    if (type === "boolean") return /^(true|1|yes|on)$/i.test(raw);
    return raw;
  }

  async function submitForm(ev) {
    if (ev && ev.preventDefault) ev.preventDefault();
    const status = $("#ab-tf-status");
    const btn = $("#ab-tf-submit");
    const body = {
      slug: ($("#ab-tf-slug").value || "").trim(),
      type: "esql",
      description: ($("#ab-tf-description").value || "").trim(),
      query: ($("#ab-tf-query").value || "").trim(),
      tags: ($("#ab-tf-tags").value || "").split(",").map((s) => s.trim()).filter(Boolean),
      params: readParams(),
    };
    status.textContent = "";
    btn.disabled = true;
    btn.textContent = "Creating...";
    try {
      const result = await api("POST", "/agent-builder/tools", body);
      toast("Tool " + result.tool_id + " created", "ok");
      closeModal();
      // Reset form for next time.
      $("#ab-tool-form").reset();
      $("#ab-tf-params").innerHTML = "";
      refreshToolsList();
    } catch (e) {
      const msg = e && e.message ? e.message : String(e);
      status.textContent = msg;
      status.style.color = "var(--pink, #F04E98)";
    } finally {
      btn.disabled = false;
      btn.textContent = "Create tool";
    }
  }

  function injectStyles() {
    if (document.getElementById("ab-tools-style")) return;
    const s = document.createElement("style");
    s.id = "ab-tools-style";
    s.textContent = [
      ".ab-tool-tag { background: var(--bg-grid, #1a1d24); color: var(--muted, #8b919a); border: 1px solid var(--border-soft, #232733); border-radius: 999px; padding: 1px 7px; font-size: 10px; }",
      ".ab-sidebar-del { background: transparent; border: 1px solid transparent; color: var(--muted, #8b919a); cursor: pointer; font-size: 16px; padding: 2px 6px; border-radius: 4px; }",
      ".ab-sidebar-del:hover { background: rgba(240, 78, 152, 0.12); color: #F04E98; border-color: rgba(240, 78, 152, 0.35); }",
      ".ab-sidebar-item.ab-readonly { opacity: 0.78; }",
      ".ab-muted { color: var(--muted, #8b919a); font-style: italic; font-size: 12px; }",
      ".ab-param-row .ab-tp-remove { background: transparent; border: 1px solid var(--border-soft, #232733); color: var(--muted, #8b919a); border-radius: 4px; cursor: pointer; padding: 4px 8px; font-size: 13px; }",
      ".ab-param-row .ab-tp-remove:hover { color: #F04E98; border-color: rgba(240, 78, 152, 0.35); }",
      ".ab-params-list .ab-param-row input, .ab-params-list .ab-param-row select { padding: 6px 8px; font-size: 12px; }",
    ].join("\n");
    document.head.appendChild(s);
  }

  // ============================================================ Wire up

  function wire() {
    injectStyles();
    const newBtn = $("#ab-new-tool");
    if (newBtn) newBtn.addEventListener("click", openModal);
    $$("[data-ab-tool-close]").forEach((b) => b.addEventListener("click", closeModal));
    const form = $("#ab-tool-form");
    if (form) form.addEventListener("submit", submitForm);
    const addParam = $("#ab-tf-add-param");
    if (addParam) addParam.addEventListener("click", () => addParamRow());
    const q = $("#ab-tf-query");
    const qc = $("#ab-tf-query-count");
    if (q && qc) {
      const upd = () => { qc.textContent = String(q.value.length); };
      q.addEventListener("input", upd);
      upd();
    }
    refreshToolsList();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", wire);
  } else {
    wire();
  }
})();
