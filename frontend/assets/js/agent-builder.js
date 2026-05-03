/*
  filename: agent-builder.js
  description: Drives the Agent Builder chat panel. Loads status, sends messages to /api/v1/agent-builder/converse, persists conversation_id in localStorage, renders reasoning + tool-call steps inline.
  Author: Rodrigo Careaga
  Date: 03-05-2026
*/
(function () {
  const STORAGE_KEY = "fec.agent_builder.conversation_id";
  const $ = (sel) => document.querySelector(sel);

  const state = {
    conversationId: localStorage.getItem(STORAGE_KEY) || null,
    inFlight: false,
    kibanaUrl: null,
    agentId: "fec_field_assistant",
  };

  // ============================================================ Status
  async function loadStatus() {
    try {
      const s = await apiGet("/agent-builder/status");
      state.kibanaUrl = s.kibana_url || null;
      const pillStatus = $("#ab-pill-status");
      const pillTools = $("#ab-pill-tools");
      const pillKibana = $("#ab-pill-kibana");
      pillStatus.textContent = s.live ? "Live" : "Dry-run";
      pillStatus.classList.remove("ab-pill-muted");
      pillStatus.classList.add(s.live ? "ab-pill-ok" : "ab-pill-err");
      pillTools.textContent = `${(s.configured_tools || []).length} MCP tools`;
      pillTools.classList.remove("ab-pill-muted");
      pillTools.classList.add("ab-pill-ok");
      if (state.kibanaUrl) {
        pillKibana.href = state.kibanaUrl + "/app/agent_builder";
      } else {
        pillKibana.style.display = "none";
      }
    } catch (e) {
      const pillStatus = $("#ab-pill-status");
      pillStatus.textContent = "Status unavailable";
      pillStatus.classList.add("ab-pill-err");
    }
  }

  // ============================================================ Render helpers
  function el(tag, attrs = {}, children = []) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === "class") node.className = v;
      else if (k === "html") node.innerHTML = v;
      else node.setAttribute(k, v);
    }
    (Array.isArray(children) ? children : [children]).forEach((c) => {
      if (c == null) return;
      node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    });
    return node;
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  // Lightweight Markdown-ish renderer for the assistant body. Handles **bold**, `code`,
  // ```fenced blocks```, bulleted lists. Anything fancier degrades gracefully to plain text.
  function renderMarkdown(text) {
    let html = escapeHtml(text);
    html = html.replace(/```([\s\S]*?)```/g, (_, code) => `<pre><code>${code}</code></pre>`);
    html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
    html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/^- (.+)$/gm, "<li>$1</li>");
    html = html.replace(/(?:<li>[\s\S]*?<\/li>\n?)+/g, (m) => `<ul>${m}</ul>`);
    html = html.replace(/\n{2,}/g, "<br><br>");
    html = html.replace(/\n/g, "<br>");
    return html;
  }

  function renderUserMessage(text) {
    const chat = $("#ab-chat");
    chat.appendChild(
      el("div", { class: "ab-msg ab-msg-user" }, [
        el("div", { class: "ab-msg-role" }, "You"),
        el("div", { class: "ab-msg-body" }, text),
      ])
    );
    scrollChat();
  }

  function renderLoading() {
    const chat = $("#ab-chat");
    const node = el("div", { class: "ab-msg ab-msg-assistant", "data-loading": "1" }, [
      el("div", { class: "ab-msg-role" }, "FE Copilot"),
      el("div", { class: "ab-loader" }, "Thinking…"),
    ]);
    chat.appendChild(node);
    scrollChat();
    return node;
  }

  function renderSteps(steps) {
    if (!Array.isArray(steps) || steps.length === 0) return null;
    const wrap = el("div", { class: "ab-steps" });
    wrap.appendChild(el("div", { class: "ab-msg-role" }, `${steps.length} step${steps.length > 1 ? "s" : ""}`));
    steps.forEach((s, i) => {
      const stepDiv = el("div", { class: `ab-step ab-step-${s.type === "tool_call" ? "toolcall" : s.type}` });
      stepDiv.appendChild(el("span", { class: "ab-step-icon" }, String(i + 1)));
      const body = el("div", { class: "ab-step-body" });
      if (s.type === "tool_call") {
        body.appendChild(el("div", {}, [
          el("span", { class: "ab-step-name" }, s.tool_id || "tool"),
          document.createTextNode(" - call"),
        ]));
        if (s.params) {
          body.appendChild(el("pre", { class: "ab-step-detail" }, JSON.stringify(s.params, null, 2)));
        }
      } else if (s.type === "reasoning") {
        body.appendChild(el("div", {}, [el("span", { class: "ab-step-name" }, "reasoning")]));
        if (s.reasoning) {
          const r = typeof s.reasoning === "string" ? s.reasoning : JSON.stringify(s.reasoning, null, 2);
          body.appendChild(el("pre", { class: "ab-step-detail" }, r.slice(0, 1000)));
        }
      } else {
        body.appendChild(el("div", { class: "ab-step-name" }, s.type || "step"));
      }
      stepDiv.appendChild(body);
      wrap.appendChild(stepDiv);
    });
    return wrap;
  }

  function renderAssistantMessage(slot, payload) {
    slot.innerHTML = "";
    const role = el("div", { class: "ab-msg-role" }, "FE Copilot");
    const body = el("div", { class: "ab-msg-body", html: renderMarkdown(payload.text || "") });
    slot.appendChild(role);
    slot.appendChild(body);
    const steps = renderSteps(payload.steps);
    if (steps) slot.appendChild(steps);
    if (payload.stats) {
      const stats = `${payload.stats.input_tokens ?? "?"} in / ${payload.stats.output_tokens ?? "?"} out · ${payload.stats.ttft_ms ?? "?"}ms first token · model: ${payload.stats.model || "?"}`;
      slot.appendChild(el("div", { class: "ab-msg-stats" }, stats));
    }
    slot.removeAttribute("data-loading");
    scrollChat();
  }

  function renderError(slot, message) {
    slot.innerHTML = "";
    slot.appendChild(el("div", { class: "ab-msg-role" }, "Error"));
    slot.appendChild(el("div", { class: "ab-msg-body" }, message));
    slot.removeAttribute("data-loading");
  }

  function scrollChat() {
    const composer = document.querySelector(".ab-composer");
    if (composer) composer.scrollIntoView({ behavior: "smooth", block: "end" });
  }

  // ============================================================ Send loop
  async function send(text) {
    if (state.inFlight || !text.trim()) return;
    state.inFlight = true;
    const sendBtn = $("#ab-send");
    sendBtn.disabled = true;
    sendBtn.textContent = "Sending…";

    renderUserMessage(text);
    const slot = renderLoading();

    try {
      const body = { message: text, agent_id: state.agentId };
      if (state.conversationId) body.conversation_id = state.conversationId;
      const res = await apiPost("/agent-builder/converse", body);
      if (res && res.conversation_id) {
        state.conversationId = res.conversation_id;
        localStorage.setItem(STORAGE_KEY, state.conversationId);
      }
      const msg = (res && res.response && res.response.message) || res?.message || "(no response)";
      const stats = res
        ? {
            input_tokens: res.model_usage?.input_tokens,
            output_tokens: res.model_usage?.output_tokens,
            ttft_ms: res.time_to_first_token,
            model: res.model_usage?.model,
          }
        : null;
      renderAssistantMessage(slot, { text: msg, steps: res?.steps, stats });
    } catch (e) {
      renderError(slot, e.message || String(e));
    } finally {
      state.inFlight = false;
      sendBtn.disabled = false;
      sendBtn.textContent = "Send";
      $("#ab-input").value = "";
      $("#ab-input").focus();
    }
  }

  // ============================================================ Wire up
  function reset() {
    state.conversationId = null;
    localStorage.removeItem(STORAGE_KEY);
    const chat = $("#ab-chat");
    chat.innerHTML = "";
    chat.appendChild(
      el("div", { class: "ab-empty" }, "New thread started. Ask the Field Assistant anything.")
    );
  }

  function init() {
    loadStatus();

    $("#ab-form").addEventListener("submit", () => {
      const txt = $("#ab-input").value;
      send(txt);
    });
    $("#ab-input").addEventListener("keydown", (ev) => {
      if ((ev.metaKey || ev.ctrlKey) && ev.key === "Enter") {
        ev.preventDefault();
        send($("#ab-input").value);
      }
    });
    $("#ab-reset").addEventListener("click", reset);
    document.querySelectorAll(".ab-chip").forEach((b) => {
      b.addEventListener("click", () => {
        const p = b.getAttribute("data-prompt") || "";
        $("#ab-input").value = p;
        send(p);
      });
    });

    if (!state.conversationId) {
      $("#ab-chat").appendChild(
        el("div", { class: "ab-empty" }, "Pick a suggested prompt above or type your own to start.")
      );
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
