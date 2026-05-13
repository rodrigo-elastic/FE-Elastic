/*
  filename: battlecard-chat.js
  description: Per-competitor "Specialist" chat adapter for the battlecards detail view. Resolves the live Kibana Agent Builder agent for the competitor via GET /battlecards/by-competitor/{name}/agent, then posts user messages to /battlecards/by-competitor/{name}/ask with a per-competitor conversation_id persisted in localStorage (key: fec.battlecard_chat.<slug>). Falls back to /agent-builder/converse with the resolved agent_id when the convenience endpoint is unavailable, and to the master agent (fec_field_assistant) when no specialist is provisioned. Renders markdown via AgentBuilderMini.renderMarkdown to preserve the __FECBLOCK_N__ fenced-code-block fix. Exposes BattlecardChat.mount(host, { card }) and the returned handle exposes dispose() so callers can swap competitors without leaking listeners or DOM.
  Author: Rodrigo Careaga
  Date: 13-05-2026
*/
(function (global) {
  const STORAGE_PREFIX = "fec.battlecard_chat.";
  const MASTER_AGENT_ID = "fec_field_assistant";

  function $el(tag, attrs, children) {
    const node = document.createElement(tag);
    if (attrs) {
      for (const k of Object.keys(attrs)) {
        const v = attrs[k];
        if (v == null || v === false) continue;
        if (k === "class") node.className = v;
        else if (k === "html") node.innerHTML = v;
        else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
        else if (v === true) node.setAttribute(k, "");
        else node.setAttribute(k, v);
      }
    }
    const arr = Array.isArray(children) ? children : (children == null ? [] : [children]);
    for (const c of arr) {
      if (c == null || c === false) continue;
      node.appendChild(typeof c === "string" || typeof c === "number"
        ? document.createTextNode(String(c))
        : c);
    }
    return node;
  }

  function escapeHtml(s) {
    if (global.AgentBuilderMini && AgentBuilderMini.escapeHtml) return AgentBuilderMini.escapeHtml(s);
    return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function renderMarkdown(text) {
    if (global.AgentBuilderMini && AgentBuilderMini.renderMarkdown) return AgentBuilderMini.renderMarkdown(text);
    return "<p>" + escapeHtml(text || "") + "</p>";
  }

  function slugOf(card) {
    if (!card) return "";
    return String(card.competitor_slug || card.competitor || "").toLowerCase().trim().replace(/\s+/g, "-");
  }

  function sanitize(err) {
    if (typeof global.sanitizeError === "function") return global.sanitizeError(err);
    return (err && err.message) || String(err);
  }

  // --------------------------------------------------------- API helpers
  // We always go through apiPostWithRetry / apiGetWithRetry if available so
  // the panel benefits from the same timeout + retry envelope as the rest of
  // the app. Falls back to bare apiPost / apiGet if api-retry.js is not loaded.
  function get(path) {
    if (typeof global.apiGetWithRetry === "function") {
      return apiGetWithRetry(path, { category: "compute", silent: true });
    }
    return apiGet(path);
  }
  function post(path, body, opts) {
    opts = Object.assign({ category: "llm", silent: true }, opts || {});
    if (typeof global.apiPostWithRetry === "function") {
      return apiPostWithRetry(path, body, opts);
    }
    return apiPost(path, body);
  }

  // --------------------------------------------------------------- mount
  function mount(host, opts) {
    opts = opts || {};
    const card = opts.card || {};
    const competitor = card.competitor || "Competitor";
    const slug = slugOf(card);
    const storageKey = STORAGE_PREFIX + slug;
    const historyKey = storageKey + ".messages";

    // ----- state
    const state = {
      conversationId: null,
      agentId: MASTER_AGENT_ID,
      agentAvailable: false,
      skillId: null,
      mode: "resolving", // "live" | "master" | "offline" | "resolving"
      preambleSent: false,
      inFlight: false,
      history: [],
      disposed: false,
    };
    try {
      state.conversationId = localStorage.getItem(storageKey) || null;
      state.preambleSent = !!state.conversationId;
      const raw = localStorage.getItem(historyKey);
      state.history = raw ? (JSON.parse(raw) || []) : [];
      if (!Array.isArray(state.history)) state.history = [];
    } catch (_) { state.history = []; }

    function saveHistory() {
      try { localStorage.setItem(historyKey, JSON.stringify(state.history)); } catch (_) {}
    }

    // ---------------------------------------------------------- preamble
    function buildPreamble() {
      // Keep it shorter than the master-agent preamble; the specialist agent
      // is already grounded on the competitor. We just hand it the live card
      // so it can quote the latest talking points and proof.
      const lines = [];
      lines.push("You are the Elastic " + competitor + " Specialist. Answer in the FE's voice, anchored to the battlecard below. Cite proof points when relevant; flag honest gotchas when the customer is in scope for them.");
      lines.push("");
      lines.push("## Battlecard: Elastic vs " + competitor);
      if (card.tagline) lines.push("> " + card.tagline);
      if (card.key_pain) {
        lines.push("");
        lines.push("### Customer pain");
        lines.push(card.key_pain);
      }
      const tps = Array.isArray(card.talking_points) ? card.talking_points : [];
      if (tps.length) {
        lines.push("");
        lines.push("### Talking points");
        tps.forEach((p, i) => {
          lines.push((i + 1) + ". " + (p.angle || "Angle") + ": " + (p.claim || ""));
          if (p.proof) lines.push("   Proof: " + p.proof);
        });
      }
      const objs = Array.isArray(card.objection_handlers) && card.objection_handlers.length
        ? card.objection_handlers
        : (Array.isArray(card.common_objections) ? card.common_objections : []);
      if (objs.length) {
        lines.push("");
        lines.push("### Common objections");
        objs.forEach((o) => {
          lines.push("Q: " + (o.q || ""));
          lines.push("A: " + (o.a || ""));
        });
      }
      const dq = Array.isArray(card.discovery_questions) ? card.discovery_questions : [];
      if (dq.length) {
        lines.push("");
        lines.push("### Discovery questions");
        dq.forEach((q, i) => lines.push((i + 1) + ". " + q));
      }
      if (card.clincher) {
        lines.push("");
        lines.push("### Clincher");
        lines.push(card.clincher);
      }
      return lines.join("\n");
    }

    // ----------------------------------------------------------- DOM tree
    host.innerHTML = "";
    host.classList.add("bcc-host");

    // Header
    const titleEl = $el("span", { class: "bcc-title" }, "Ask the " + competitor + " Specialist");
    const pill = $el("span", {
      class: "bcc-pill bcc-pill-resolving",
      "aria-live": "polite",
      title: "Checking specialist availability...",
    }, "checking...");
    const resetBtn = $el("button", {
      class: "bcc-reset",
      type: "button",
      title: "Start a new conversation with the specialist",
      "aria-label": "Start a new conversation",
    }, "new");
    const header = $el("div", { class: "bcc-header" }, [titleEl, pill, resetBtn]);
    const subtitle = $el("div", { class: "bcc-subtitle" },
      "Powered by Kibana Agent Builder. Grounded in the live battlecard and the Elastic competitive playbook."
    );

    // Suggestion chips (built from discovery_questions, capped at 3)
    const dq = Array.isArray(card.discovery_questions) ? card.discovery_questions.slice(0, 3) : [];
    const chipRow = $el("div", { class: "bcc-chips", role: "group", "aria-label": "Suggested questions" });
    if (!dq.length) {
      // Reasonable fallback prompts if the card has no discovery_questions yet.
      const fallback = [
        "How do I handle the most common " + competitor + " objection?",
        "Give me 3 discovery questions that surface a " + competitor + " replacement opportunity.",
        "Top 3 reasons Elastic wins against " + competitor + ".",
      ];
      fallback.forEach((q) => chipRow.appendChild($el("button", {
        class: "bcc-chip", type: "button", "data-prompt": q,
      }, q.length > 80 ? q.slice(0, 78) + "..." : q)));
    } else {
      dq.forEach((q) => chipRow.appendChild($el("button", {
        class: "bcc-chip", type: "button", "data-prompt": q,
      }, q.length > 80 ? q.slice(0, 78) + "..." : q)));
    }

    // Transcript
    const transcript = $el("div", {
      class: "bcc-transcript",
      role: "log",
      "aria-live": "polite",
      "aria-label": competitor + " specialist transcript",
    });

    // Composer
    const input = $el("textarea", {
      class: "bcc-input",
      rows: "2",
      placeholder: "Ask the " + competitor + " Specialist...",
      "aria-label": "Message the " + competitor + " specialist",
    });
    const sendBtn = $el("button", {
      class: "bcc-send",
      type: "button",
      "aria-label": "Send message",
    }, "Send");
    const composer = $el("div", { class: "bcc-composer" }, [input, sendBtn]);

    // Mobile collapse: a "Show chat" button mirrors the panel state.
    const mobileToggle = $el("button", {
      class: "bcc-mobile-toggle",
      type: "button",
      "aria-expanded": "false",
      "aria-controls": "bcc-panel-" + slug,
    }, "Show " + competitor + " Specialist chat");

    const panel = $el("div", {
      class: "bcc-panel",
      id: "bcc-panel-" + slug,
    }, [header, subtitle, chipRow, transcript, composer]);

    host.appendChild(mobileToggle);
    host.appendChild(panel);

    // ---------------------------------------------------------- rendering
    function scrollTranscript() {
      transcript.scrollTop = transcript.scrollHeight;
    }
    function renderUser(text) {
      transcript.appendChild($el("div", { class: "bcc-msg bcc-msg-user" }, [
        $el("div", { class: "bcc-msg-body" }, text),
      ]));
      scrollTranscript();
    }
    function renderAssistantSlot() {
      const slot = $el("div", { class: "bcc-msg bcc-msg-assistant" }, [
        $el("div", { class: "bcc-loader" }, "Thinking..."),
      ]);
      transcript.appendChild(slot);
      scrollTranscript();
      return slot;
    }
    function renderAssistant(slot, text) {
      slot.innerHTML = "";
      slot.appendChild($el("div", { class: "bcc-msg-body", html: renderMarkdown(text || "") }));
      scrollTranscript();
    }
    function renderError(slot, msg) {
      slot.innerHTML = "";
      slot.appendChild($el("div", { class: "bcc-msg-body bcc-error" }, msg));
    }
    function replay() {
      if (!state.history.length) return;
      state.history.forEach((m) => {
        if (m.role === "user") renderUser(m.text);
        else if (m.role === "assistant") {
          const slot = $el("div", { class: "bcc-msg bcc-msg-assistant" }, [
            $el("div", { class: "bcc-msg-body", html: renderMarkdown(m.text || "") }),
          ]);
          transcript.appendChild(slot);
        }
      });
      scrollTranscript();
    }
    replay();

    // --------------------------------------------------- specialist pill
    function setPillMode(mode) {
      state.mode = mode;
      pill.classList.remove("bcc-pill-resolving", "bcc-pill-live", "bcc-pill-fallback", "bcc-pill-offline");
      if (mode === "live") {
        pill.classList.add("bcc-pill-live");
        pill.textContent = "Specialist live";
        pill.title = "Connected to the " + competitor + " specialist agent in Kibana Agent Builder.";
      } else if (mode === "master") {
        pill.classList.add("bcc-pill-fallback");
        pill.textContent = "Master agent (fallback)";
        pill.title = "No dedicated specialist for " + competitor + " yet. Falling back to the FE master agent.";
      } else if (mode === "offline") {
        pill.classList.add("bcc-pill-offline");
        pill.textContent = "Specialist offline";
        pill.title = "Could not reach the agent builder. The battlecard is still readable; try again in a minute.";
      } else {
        pill.classList.add("bcc-pill-resolving");
        pill.textContent = "checking...";
      }
    }
    setPillMode("resolving");

    // --------------------------------------------------------- agent resolve
    async function resolveAgent() {
      try {
        const data = await get("/battlecards/by-competitor/" + encodeURIComponent(competitor) + "/agent");
        if (state.disposed) return;
        if (data && data.available && data.agent_id) {
          state.agentId = data.agent_id;
          state.skillId = data.skill_id || null;
          state.agentAvailable = true;
          setPillMode("live");
        } else if (data && data.agent_id) {
          // Endpoint responded but specialist not provisioned; use whatever
          // it suggests (likely the master agent id).
          state.agentId = data.agent_id;
          state.agentAvailable = false;
          setPillMode("master");
        } else {
          state.agentId = MASTER_AGENT_ID;
          state.agentAvailable = false;
          setPillMode("master");
        }
      } catch (_e) {
        if (state.disposed) return;
        // Endpoint not deployed yet (404) or upstream 502. Keep the chat
        // usable by falling back to the master agent on /agent-builder/converse.
        state.agentId = MASTER_AGENT_ID;
        state.agentAvailable = false;
        setPillMode("master");
      }
    }
    resolveAgent();

    // ----------------------------------------------------------- sending
    async function callConvenienceEndpoint(text) {
      const body = { message: text };
      if (state.conversationId) body.conversation_id = state.conversationId;
      return post("/battlecards/by-competitor/" + encodeURIComponent(competitor) + "/ask", body);
    }
    async function callDirectConverse(text) {
      const body = { message: text, agent_id: state.agentId };
      if (state.conversationId) body.conversation_id = state.conversationId;
      return post("/agent-builder/converse", body);
    }

    async function send(rawText) {
      const text = (rawText == null ? input.value : rawText).trim();
      if (!text || state.inFlight || state.disposed) return;
      state.inFlight = true;
      sendBtn.disabled = true;
      sendBtn.textContent = "Sending...";

      // Build the outgoing payload. On the first message of a new conversation
      // we attach the battlecard preamble so the specialist agent has the
      // latest card content even if its Kibana skill is slightly behind.
      let outgoing = text;
      if (!state.preambleSent) {
        outgoing = buildPreamble() + "\n\n---\n\n" + text;
        state.preambleSent = true;
      }

      renderUser(text);
      state.history.push({ role: "user", text });
      saveHistory();
      input.value = "";
      const slot = renderAssistantSlot();

      let res = null;
      let convenienceFailed = false;
      try {
        res = await callConvenienceEndpoint(outgoing);
      } catch (e) {
        // 404/405/5xx -> try the direct converse path. Anything else (network
        // off, CORS) will probably blow up there too but we still surface the
        // direct-converse error to the user instead of the wrapper error.
        convenienceFailed = true;
      }
      if (convenienceFailed) {
        try {
          res = await callDirectConverse(outgoing);
        } catch (e) {
          if (!state.disposed) {
            renderError(slot, "Specialist temporarily offline: " + sanitize(e));
            // Roll back the preamble flag so the next attempt re-sends context.
            state.preambleSent = !!state.conversationId;
            if (state.mode !== "offline") setPillMode("offline");
          }
          state.inFlight = false;
          sendBtn.disabled = false;
          sendBtn.textContent = "Send";
          return;
        }
      }

      if (state.disposed) return;
      // Persist the conversation id so the thread survives a reload.
      const newCid = res && (res.conversation_id || (res.response && res.response.conversation_id));
      if (newCid) {
        state.conversationId = newCid;
        try { localStorage.setItem(storageKey, newCid); } catch (_) {}
      }
      const answer = (res && res.response && res.response.message) || (res && res.message) || "(empty response)";
      renderAssistant(slot, answer);
      state.history.push({ role: "assistant", text: answer });
      saveHistory();
      state.inFlight = false;
      sendBtn.disabled = false;
      sendBtn.textContent = "Send";
      input.focus();
    }

    // ------------------------------------------------------------- reset
    function reset() {
      state.conversationId = null;
      state.preambleSent = false;
      state.history = [];
      try { localStorage.removeItem(storageKey); } catch (_) {}
      try { localStorage.removeItem(historyKey); } catch (_) {}
      transcript.innerHTML = "";
      input.focus();
    }

    // -------------------------------------------------------- mobile UX
    function applyMobileState() {
      const isSmall = window.matchMedia && window.matchMedia("(max-width: 768px)").matches;
      if (isSmall) {
        host.classList.add("bcc-collapsed");
        mobileToggle.setAttribute("aria-expanded", "false");
      } else {
        host.classList.remove("bcc-collapsed");
        mobileToggle.setAttribute("aria-expanded", "true");
      }
    }
    applyMobileState();
    const onResize = () => applyMobileState();
    window.addEventListener("resize", onResize);

    function toggleMobile() {
      const collapsed = host.classList.toggle("bcc-collapsed");
      mobileToggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
      mobileToggle.textContent = collapsed
        ? "Show " + competitor + " Specialist chat"
        : "Hide chat";
      if (!collapsed) {
        try { input.focus({ preventScroll: true }); } catch (_) { input.focus(); }
      }
    }

    // ---------------------------------------------------------- wiring
    const onSendClick = () => send();
    const onKeyDown = (ev) => {
      if (ev.key === "Enter" && !ev.shiftKey) {
        ev.preventDefault();
        send();
      }
    };
    const onChipClick = (ev) => {
      const b = ev.target.closest && ev.target.closest(".bcc-chip");
      if (!b) return;
      ev.preventDefault();
      const p = b.getAttribute("data-prompt") || "";
      input.value = p;
      send(p);
    };
    const onResetClick = () => reset();

    sendBtn.addEventListener("click", onSendClick);
    input.addEventListener("keydown", onKeyDown);
    chipRow.addEventListener("click", onChipClick);
    resetBtn.addEventListener("click", onResetClick);
    mobileToggle.addEventListener("click", toggleMobile);

    // Auto-focus the composer when not on mobile so the FE can start typing
    // right away. On mobile we keep focus on the toggle to avoid the keyboard
    // popping up unsolicited.
    if (!host.classList.contains("bcc-collapsed")) {
      // Defer to next frame so the detail view is painted first.
      requestAnimationFrame(() => {
        try { input.focus({ preventScroll: true }); } catch (_) { /* noop */ }
      });
    }

    function dispose() {
      state.disposed = true;
      sendBtn.removeEventListener("click", onSendClick);
      input.removeEventListener("keydown", onKeyDown);
      chipRow.removeEventListener("click", onChipClick);
      resetBtn.removeEventListener("click", onResetClick);
      mobileToggle.removeEventListener("click", toggleMobile);
      window.removeEventListener("resize", onResize);
      host.innerHTML = "";
      host.classList.remove("bcc-host", "bcc-collapsed");
    }

    return { send, reset, dispose, element: host };
  }

  global.BattlecardChat = { mount };
})(window);
