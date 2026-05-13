/*
  filename: agent-builder-mini.js
  description: Reusable inline Agent Builder chat panel. Mount inside any container with `AgentBuilderMini.mount(host, { contextLabel, contextPreamble, suggestions, storageKey, agentId })` - talks to /api/v1/agent-builder/converse with optional per-instance conversation persistence and a context preamble that is prepended to the first user message only.
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

  // Lightweight Markdown renderer covering what the LLM actually emits:
  // ATX headings, fenced code, inline code, bold, italic, links, ordered
  // and unordered lists, blockquotes, horizontal rules, and paragraphs.
  // Order of operations matters: escape HTML first, then carve out fenced
  // code, then handle block-level rules line by line, then inline rules.
  function renderMarkdown(text) {
    if (text == null) return "";
    let src = String(text);
    // 1. Carve out fenced code so the content is not touched by inline rules.
    const codeBlocks = [];
    // Sentinel must survive trim/escapeHtml. " CODE0 " loses its surrounding
    // spaces during paragraph trim() and leaks a literal "CODE0" to the user;
    // a unique multi-char marker is safe through every downstream pass.
    src = src.replace(/```([a-zA-Z0-9_+\-]*)\n?([\s\S]*?)```/g, (_, lang, code) => {
      const i = codeBlocks.length;
      codeBlocks.push({ lang: String(lang || "").trim(), code: String(code || "") });
      return "\n__FECBLOCK_" + i + "__\n";
    });
    // 2. Escape HTML on everything else.
    src = escapeHtml(src);
    // 3. Block-level pass, line by line. We classify each line and group
    //    consecutive list items / paragraph lines into a single block.
    const lines = src.split(/\n/);
    const out = [];
    let i = 0;
    function flushPara(buf) {
      if (!buf.length) return;
      out.push("<p>" + buf.join(" ") + "</p>");
    }
    while (i < lines.length) {
      const ln = lines[i];
      // Horizontal rule: --- or *** alone on a line
      if (/^\s*(?:-{3,}|\*{3,})\s*$/.test(ln)) {
        out.push("<hr>");
        i++;
        continue;
      }
      // ATX headings #, ##, ### (we render up to h6).
      const h = /^(\#{1,6})\s+(.+?)\s*#*\s*$/.exec(ln);
      if (h) {
        const lvl = h[1].length;
        out.push("<h" + lvl + ">" + h[2] + "</h" + lvl + ">");
        i++;
        continue;
      }
      // Blockquote
      if (/^>\s?/.test(ln)) {
        const buf = [];
        while (i < lines.length && /^>\s?/.test(lines[i])) {
          buf.push(lines[i].replace(/^>\s?/, ""));
          i++;
        }
        out.push("<blockquote>" + buf.join("<br>") + "</blockquote>");
        continue;
      }
      // Unordered list
      if (/^\s*[-*]\s+/.test(ln)) {
        const buf = [];
        while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
          buf.push("<li>" + lines[i].replace(/^\s*[-*]\s+/, "") + "</li>");
          i++;
        }
        out.push("<ul>" + buf.join("") + "</ul>");
        continue;
      }
      // Ordered list
      if (/^\s*\d+\.\s+/.test(ln)) {
        const buf = [];
        while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
          buf.push("<li>" + lines[i].replace(/^\s*\d+\.\s+/, "") + "</li>");
          i++;
        }
        out.push("<ol>" + buf.join("") + "</ol>");
        continue;
      }
      // Blank line: paragraph separator
      if (/^\s*$/.test(ln)) {
        i++;
        continue;
      }
      // Default: paragraph. Collect contiguous non-empty, non-block lines.
      const buf = [];
      while (i < lines.length
             && !/^\s*$/.test(lines[i])
             && !/^(\#{1,6})\s+/.test(lines[i])
             && !/^\s*(?:-{3,}|\*{3,})\s*$/.test(lines[i])
             && !/^\s*[-*]\s+/.test(lines[i])
             && !/^\s*\d+\.\s+/.test(lines[i])
             && !/^>\s?/.test(lines[i])) {
        buf.push(lines[i].trim());
        i++;
      }
      flushPara(buf);
    }
    let html = out.join("\n");
    // 4. Inline rules. Bold before italic so * inside ** is preserved.
    html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/__([^_]+)__/g, "<strong>$1</strong>");
    // Italic: leading boundary is start-of-string, whitespace, "(", or ">"
    // (the latter matters because the block pass wraps paragraphs in <p>,
    // so a line starting with *italic* has > as the preceding char).
    html = html.replace(/(^|[\s(>])\*([^*\n]+)\*/g, "$1<em>$2</em>");
    html = html.replace(/(^|[\s(>])_([^_\n]+)_/g, "$1<em>$2</em>");
    // Inline code
    html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
    // Links [text](url)
    html = html.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
    // 5. Restore fenced code blocks last so their content is untouched.
    html = html.replace(/__FECBLOCK_(\d+)__/g, (_, n) => {
      const block = codeBlocks[+n] || { lang: "", code: "" };
      const cls = block.lang ? ' class="lang-' + escapeHtml(block.lang) + '"' : "";
      return "<pre><code" + cls + ">" + escapeHtml(block.code) + "</code></pre>";
    });
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

    // Persist not just the conversation_id but the full transcript so
    // questions and answers survive a page reload. Storage layout:
    //   <storageKey>          -> conversation_id (existing)
    //   <storageKey>.messages -> JSON array of {role, text, steps?, stats?}
    const historyKey = cfg.storageKey ? cfg.storageKey + ".messages" : null;
    function loadHistory() {
      if (!historyKey) return [];
      try {
        const raw = localStorage.getItem(historyKey);
        const arr = raw ? JSON.parse(raw) : [];
        return Array.isArray(arr) ? arr : [];
      } catch (_e) { return []; }
    }
    function saveHistory(arr) {
      if (!historyKey) return;
      try { localStorage.setItem(historyKey, JSON.stringify(arr)); } catch (_e) { /* private mode or quota */ }
    }
    const state = {
      conversationId: cfg.storageKey ? localStorage.getItem(cfg.storageKey) : null,
      preambleSent: cfg.storageKey ? !!localStorage.getItem(cfg.storageKey) : false,
      inFlight: false,
      history: loadHistory(),
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
            document.createTextNode(" - call"),
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
      const copyBtn = $el("button", { class: "abm-export-btn", type: "button", title: "Copy markdown plus formatted HTML to clipboard" }, "📋 Copy");
      copyBtn.addEventListener("click", () => {
        copyRich(rawMarkdown).then((ok) => {
          copyBtn.textContent = ok ? "✓ Copied" : "✗ Failed";
          setTimeout(() => (copyBtn.textContent = "📋 Copy"), 1200);
        });
      });
      const printBtn = $el("button", { class: "abm-export-btn", type: "button", title: "Print / save as PDF" }, "🖨 Print");
      printBtn.addEventListener("click", () => printResponse(title, rawMarkdown));
      const driveBtn = $el("button", { class: "abm-export-btn", type: "button", title: "Copy formatted content to clipboard, then opens a new Google Doc. Press Cmd/Ctrl+V to paste with bold, headings, lists preserved." }, "📁 Open in Drive");
      driveBtn.addEventListener("click", () => {
        // Order: copy first (before the navigation steals focus), then open
        // Drive in a new tab. Cross-origin auto-paste is impossible without
        // OAuth into the Google Docs API, so we copy as text/html plus
        // text/plain so a Cmd+V in the new tab pastes with bold, headings
        // and lists already applied (Google Docs respects HTML clipboard).
        copyRich(rawMarkdown).then((ok) => {
          const win = window.open("https://docs.google.com/document/create?usp=openurl", "_blank");
          if (ok) {
            driveBtn.textContent = "✓ Copied. Paste with Cmd+V";
          } else {
            driveBtn.textContent = "✗ Clipboard blocked";
            if (win) {
              // Fallback: surface the markdown in the new tab so the user can
              // copy by hand.
              try {
                win.document.open();
                win.document.write(`<pre style="white-space:pre-wrap;font:14px monospace;padding:24px">${escapeHtml(rawMarkdown)}</pre>`);
                win.document.close();
              } catch (_) {}
            }
          }
          setTimeout(() => (driveBtn.textContent = "📁 Open in Drive"), 3000);
        });
      });
      row.appendChild(copyBtn);
      row.appendChild(printBtn);
      row.appendChild(driveBtn);
      return row;
    }

    // Rich clipboard write: puts BOTH text/plain (the raw markdown) and
    // text/html (the rendered HTML) on the clipboard in one writeItem call.
    // When the user pastes into Google Docs the editor takes the text/html
    // payload and preserves bold, headings, lists, links. Paste into a plain
    // text editor still gets the raw markdown. Falls back to plain-text
    // clipboard then to a hidden-textarea + execCommand for legacy paths.
    async function copyRich(markdown) {
      const html = "<meta charset=\"utf-8\">" + renderMarkdown(markdown);
      // Modern path: write both plain and html together via ClipboardItem.
      if (navigator.clipboard && typeof window.ClipboardItem === "function") {
        try {
          const items = new window.ClipboardItem({
            "text/plain": new Blob([markdown], { type: "text/plain" }),
            "text/html": new Blob([html], { type: "text/html" }),
          });
          await navigator.clipboard.write([items]);
          return true;
        } catch (_) { /* fall through */ }
      }
      // Plain-text fallback (some browsers reject ClipboardItem with html).
      if (navigator.clipboard && navigator.clipboard.writeText) {
        try {
          await navigator.clipboard.writeText(markdown);
          return true;
        } catch (_) { /* fall through */ }
      }
      // execCommand fallback inside a user gesture: render the HTML into a
      // contenteditable div, select it, copy. Google Docs gets the formatted
      // copy too. Empty rawMarkdown short-circuits.
      try {
        const div = document.createElement("div");
        div.contentEditable = "true";
        div.innerHTML = html;
        div.style.position = "fixed";
        div.style.left = "-9999px";
        div.style.opacity = "0";
        document.body.appendChild(div);
        const range = document.createRange();
        range.selectNodeContents(div);
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
        const ok = document.execCommand("copy");
        sel.removeAllRanges();
        document.body.removeChild(div);
        return ok;
      } catch (_) {
        return false;
      }
    }
    // Backward-compatible alias used in older paths.
    const copyToClipboard = copyRich;

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
      // Persist the user turn before the LLM round-trip so a refresh mid-call
      // does not lose the question.
      state.history.push({ role: "user", text });
      saveHistory(state.history);
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
        state.history.push({ role: "assistant", text: msg, steps: res?.steps, stats });
        saveHistory(state.history);
      } catch (e) {
        const safe = (typeof sanitizeError === "function") ? sanitizeError(e) : (e && e.message) || String(e);
        renderError(slot, safe);
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
      state.history = [];
      if (cfg.storageKey) localStorage.removeItem(cfg.storageKey);
      if (historyKey) localStorage.removeItem(historyKey);
      chat.innerHTML = "";
    }

    // Replay any persisted messages so the user sees their prior questions
    // and answers when they return to the page.
    function replayHistory() {
      if (!state.history.length) return;
      state.history.forEach((m) => {
        if (m.role === "user") {
          renderUser(m.text);
        } else if (m.role === "assistant") {
          const slot = $el("div", { class: "abm-msg abm-msg-assistant" }, [
            $el("div", { class: "abm-msg-body" }),
          ]);
          chat.appendChild(slot);
          renderAssistant(slot.firstChild, { text: m.text || "", steps: m.steps, stats: m.stats });
        }
      });
      scrollChat();
    }
    replayHistory();

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

  global.AgentBuilderMini = { mount, renderMarkdown, escapeHtml };
})(window);
