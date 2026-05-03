/*
  filename: agent-builder-mini.js
  description: Reusable inline Agent Builder chat panel. Mount inside any container with `AgentBuilderMini.mount(host, { contextLabel, contextPreamble, suggestions, storageKey, agentId })` — talks to /api/v1/agent-builder/converse with optional per-instance conversation persistence and a context preamble that is prepended to the first user message only.
  Author: Rodrigo Careaga
  Date: 03-05-2026
*/
(function (global) {
  const DEFAULT_AGENT = "fec_field_assistant";

  function $el(tag, attrs = {}, children = []) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === "class") node.className = v;
      else if (k === "html") node.innerHTML = v;
      else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
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

  // ============================================================ Component
  function mount(host, opts = {}) {
    if (!host) return null;
    const cfg = {
      contextLabel: opts.contextLabel || "",
      contextPreamble: opts.contextPreamble || "",
      suggestions: opts.suggestions || [],
      storageKey: opts.storageKey || null,
      agentId: opts.agentId || DEFAULT_AGENT,
      title: opts.title || "Field Assistant",
    };

    const state = {
      conversationId: cfg.storageKey ? localStorage.getItem(cfg.storageKey) : null,
      preambleSent: cfg.storageKey ? !!localStorage.getItem(cfg.storageKey) : false,
      inFlight: false,
    };

    host.innerHTML = "";
    host.classList.add("abm-host");

    // Header with context chip
    const header = $el("div", { class: "abm-header" }, [
      $el("span", { class: "abm-title" }, cfg.title),
      cfg.contextLabel ? $el("span", { class: "abm-context-chip" }, cfg.contextLabel) : null,
      $el("button", {
        class: "abm-reset",
        title: "Start a new conversation",
        type: "button",
      }, "↺ new"),
    ]);
    host.appendChild(header);

    // Suggestions
    const suggestionsRow = $el("div", { class: "abm-suggestions" });
    cfg.suggestions.forEach((s) => {
      const text = typeof s === "string" ? s : s.prompt;
      const label = typeof s === "string" ? s : (s.label || s.prompt);
      suggestionsRow.appendChild(
        $el("button", { class: "abm-chip", type: "button", "data-prompt": text }, label)
      );
    });
    if (cfg.suggestions.length) host.appendChild(suggestionsRow);

    // Chat history
    const chat = $el("div", { class: "abm-chat" });
    host.appendChild(chat);

    // Composer
    const input = $el("textarea", {
      class: "abm-input",
      rows: "2",
      placeholder: "Ask the Field Assistant…",
    });
    const sendBtn = $el("button", { class: "btn primary abm-send", type: "button" }, "Send");
    const composer = $el("div", { class: "abm-composer" }, [input, sendBtn]);
    host.appendChild(composer);

    // ============================================================ Helpers
    function scrollChat() {
      chat.scrollTop = chat.scrollHeight;
    }

    function renderUser(text) {
      chat.appendChild(
        $el("div", { class: "abm-msg abm-msg-user" }, [
          $el("div", { class: "abm-msg-body" }, text),
        ])
      );
      scrollChat();
    }

    function renderLoading() {
      const node = $el("div", { class: "abm-msg abm-msg-assistant" }, [
        $el("div", { class: "abm-loader" }, "Thinking…"),
      ]);
      chat.appendChild(node);
      scrollChat();
      return node;
    }

    function renderSteps(steps) {
      if (!Array.isArray(steps) || steps.length === 0) return null;
      const wrap = $el("details", { class: "abm-steps" });
      wrap.appendChild(
        $el("summary", {}, `${steps.length} step${steps.length > 1 ? "s" : ""} (reasoning + tool calls)`)
      );
      steps.forEach((s, i) => {
        const row = $el("div", { class: `abm-step abm-step-${s.type === "tool_call" ? "toolcall" : s.type}` });
        row.appendChild($el("span", { class: "abm-step-num" }, String(i + 1)));
        const body = $el("div", { class: "abm-step-body" });
        if (s.type === "tool_call") {
          body.appendChild($el("div", {}, [
            $el("strong", {}, s.tool_id || "tool"),
            document.createTextNode(" — call"),
          ]));
          if (s.params) {
            body.appendChild($el("pre", { class: "abm-step-detail" }, JSON.stringify(s.params, null, 2)));
          }
        } else if (s.type === "reasoning") {
          body.appendChild($el("strong", {}, "reasoning"));
          if (s.reasoning) {
            const r = typeof s.reasoning === "string" ? s.reasoning : JSON.stringify(s.reasoning);
            body.appendChild($el("pre", { class: "abm-step-detail" }, r.slice(0, 600)));
          }
        } else {
          body.appendChild($el("strong", {}, s.type || "step"));
        }
        row.appendChild(body);
        wrap.appendChild(row);
      });
      return wrap;
    }

    function renderAssistant(slot, payload) {
      slot.innerHTML = "";
      slot.appendChild($el("div", { class: "abm-msg-body", html: renderMarkdown(payload.text || "") }));
      const steps = renderSteps(payload.steps);
      if (steps) slot.appendChild(steps);
      slot.appendChild(buildExportRow(payload.text || "", cfg.contextLabel || "FE Copilot response"));
      if (payload.stats) {
        const s = payload.stats;
        slot.appendChild(
          $el("div", { class: "abm-msg-stats" },
            `${s.input_tokens ?? "?"} in / ${s.output_tokens ?? "?"} out · ${s.ttft_ms ?? "?"}ms · ${s.model || "?"}`)
        );
      }
      scrollChat();
    }

    function buildExportRow(rawMarkdown, title) {
      const row = $el("div", { class: "abm-export-row" });
      const copyBtn = $el("button", { class: "abm-export-btn", type: "button", title: "Copy markdown to clipboard" }, "📋 Copy");
      copyBtn.addEventListener("click", async () => {
        try {
          await navigator.clipboard.writeText(rawMarkdown);
          copyBtn.textContent = "✓ Copied";
          setTimeout(() => (copyBtn.textContent = "📋 Copy"), 1200);
        } catch (_) {
          copyBtn.textContent = "✗ Failed";
        }
      });
      const printBtn = $el("button", { class: "abm-export-btn", type: "button", title: "Print / save as PDF" }, "🖨 Print");
      printBtn.addEventListener("click", () => printResponse(title, rawMarkdown));
      const driveBtn = $el("button", { class: "abm-export-btn", type: "button", title: "Copy markdown then open a new Google Doc" }, "📁 Open in Drive");
      driveBtn.addEventListener("click", async () => {
        try { await navigator.clipboard.writeText(rawMarkdown); } catch (_) {}
        window.open("https://docs.google.com/document/create?usp=docs_home", "_blank", "noreferrer");
      });
      row.appendChild(copyBtn);
      row.appendChild(printBtn);
      row.appendChild(driveBtn);
      return row;
    }

    function printResponse(title, markdown) {
      const win = window.open("", "_blank", "width=900,height=1000");
      if (!win) return;
      const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>${escapeHtml(title)}</title>
<style>
  body { font-family: -apple-system, Inter, system-ui, sans-serif; max-width: 760px; margin: 36px auto; padding: 0 24px; color: #1d2128; line-height: 1.55; }
  h1 { font-size: 22px; margin: 0 0 14px; color: #0077CC; }
  pre { background: #f3f5f7; padding: 12px; border-radius: 6px; overflow-x: auto; font-size: 12.5px; }
  code { background: #f3f5f7; padding: 1px 5px; border-radius: 4px; }
  table { border-collapse: collapse; }
  th, td { border: 1px solid #d0d4dc; padding: 6px 10px; }
  .meta { color: #6a7075; font-size: 12px; margin-bottom: 18px; }
</style></head><body>
<h1>${escapeHtml(title)}</h1>
<div class="meta">Generated by FE Copilot · ${new Date().toLocaleString()}</div>
<div>${renderMarkdown(markdown)}</div>
<script>setTimeout(() => window.print(), 300);</script>
</body></html>`;
      win.document.open();
      win.document.write(html);
      win.document.close();
    }

    function renderError(slot, message) {
      slot.innerHTML = "";
      slot.appendChild($el("div", { class: "abm-msg-body abm-error" }, message));
    }

    // ============================================================ Send
    async function send(text) {
      if (state.inFlight || !text.trim()) return;
      state.inFlight = true;
      sendBtn.disabled = true;
      sendBtn.textContent = "Sending…";

      // Prepend context preamble on first message of this conversation only.
      let outgoing = text;
      if (cfg.contextPreamble && !state.preambleSent) {
        outgoing = `${cfg.contextPreamble}\n\n---\n\n${text}`;
        state.preambleSent = true;
      }

      renderUser(text); // show the user-facing text without the preamble
      const slot = renderLoading();

      try {
        const body = { message: outgoing, agent_id: cfg.agentId };
        if (state.conversationId) body.conversation_id = state.conversationId;
        const res = await apiPost("/agent-builder/converse", body);
        if (res && res.conversation_id) {
          state.conversationId = res.conversation_id;
          if (cfg.storageKey) localStorage.setItem(cfg.storageKey, state.conversationId);
        }
        const msg = (res && res.response && res.response.message) || res?.message || "(empty response)";
        const stats = res
          ? {
              input_tokens: res.model_usage?.input_tokens,
              output_tokens: res.model_usage?.output_tokens,
              ttft_ms: res.time_to_first_token,
              model: res.model_usage?.model,
            }
          : null;
        renderAssistant(slot, { text: msg, steps: res?.steps, stats });
      } catch (e) {
        renderError(slot, e.message || String(e));
      } finally {
        state.inFlight = false;
        sendBtn.disabled = false;
        sendBtn.textContent = "Send";
        input.value = "";
        input.focus();
      }
    }

    function reset() {
      state.conversationId = null;
      state.preambleSent = false;
      if (cfg.storageKey) localStorage.removeItem(cfg.storageKey);
      chat.innerHTML = "";
    }

    // ============================================================ Wiring
    sendBtn.addEventListener("click", () => send(input.value));
    input.addEventListener("keydown", (ev) => {
      if ((ev.metaKey || ev.ctrlKey) && ev.key === "Enter") {
        ev.preventDefault();
        send(input.value);
      }
    });
    suggestionsRow.querySelectorAll(".abm-chip").forEach((b) => {
      b.addEventListener("click", () => {
        const p = b.getAttribute("data-prompt") || "";
        input.value = p;
        send(p);
      });
    });
    header.querySelector(".abm-reset")?.addEventListener("click", reset);

    return {
      send,
      reset,
      element: host,
    };
  }

  global.AgentBuilderMini = { mount };
})(window);
