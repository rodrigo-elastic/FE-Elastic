/*
  filename: war-room.js
  description: Deal Strategy War Room - SKO flagship WOW feature.
    Streams four parallel agents (Competitive, Compliance, Cost, Renewal)
    via Server-Sent Events from /api/v1/war-room/{meeting_id}/stream and
    renders the live debate in a full-screen modal. A synthesis card
    appears below the 2x2 grid and streams the final 3-bullet take.
    Falls back to a non-streaming POST when SSE is blocked or stalls.
  Public API: window.WarRoom.open({ meetingId, customerName, focus })
  Author: Rodrigo Careaga
  Date: 13-05-2026
*/
(function () {
  "use strict";

  // ----------------------------------------------------------------
  // Role catalogue. Keep order stable; the grid renders in this order.
  // ----------------------------------------------------------------
  const ROLES = [
    {
      key: "competitive",
      label: "Competitive",
      desc: "Beats Splunk, Datadog, vendor X",
      color: "teal",
      icon:
        '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
        'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
        '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>',
    },
    {
      key: "compliance",
      label: "Compliance",
      desc: "Regulatory + data-residency angle",
      color: "blue",
      icon:
        '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
        'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
        '<path d="M12 2 4 5v6c0 5 3.5 9.5 8 11 4.5-1.5 8-6 8-11V5l-8-3z"/>' +
        '<path d="m9 12 2 2 4-4"/></svg>',
    },
    {
      key: "cost",
      label: "Cost / TCO",
      desc: "Pricing, sizing, savings math",
      color: "gold",
      icon:
        '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
        'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
        '<line x1="12" y1="1" x2="12" y2="23"/>' +
        '<path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 1 1 0 7H6"/></svg>',
    },
    {
      key: "renewal",
      label: "Renewal Defender",
      desc: "Risk + expansion levers",
      color: "pink",
      icon:
        '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
        'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
        '<path d="M3 12a9 9 0 0 1 15.5-6.3L21 8"/><polyline points="21 3 21 8 16 8"/>' +
        '<path d="M21 12a9 9 0 0 1-15.5 6.3L3 16"/><polyline points="3 21 3 16 8 16"/></svg>',
    },
  ];

  const ROLE_KEYS = ROLES.map((r) => r.key);

  // ----------------------------------------------------------------
  // Helpers (self-contained: file may load before/after ui.js).
  // ----------------------------------------------------------------
  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }
  function $(sel, root) { return (root || document).querySelector(sel); }
  function safeToast(msg, kind) {
    try { if (typeof window.toast === "function") window.toast(msg, kind); } catch (_) {}
  }
  function lsKey(meetingId) { return "fec.war_room." + String(meetingId || "default"); }

  function saveCache(meetingId, payload) {
    try {
      localStorage.setItem(lsKey(meetingId), JSON.stringify({ ts: Date.now(), payload: payload }));
    } catch (_) {}
  }
  function loadCache(meetingId) {
    try {
      const raw = localStorage.getItem(lsKey(meetingId));
      if (!raw) return null;
      const obj = JSON.parse(raw);
      return obj && obj.payload ? obj.payload : null;
    } catch (_) { return null; }
  }

  // ----------------------------------------------------------------
  // Module-level state. Only one modal can be open at a time.
  // ----------------------------------------------------------------
  let state = null;

  // ----------------------------------------------------------------
  // Public: open(...)
  // ----------------------------------------------------------------
  function open(opts) {
    if (state) close();
    opts = opts || {};
    const meetingId = opts.meetingId || "ad-hoc";
    const customerName = opts.customerName || "Customer";
    const focus = opts.focus || "";

    state = {
      meetingId: meetingId,
      customerName: customerName,
      focus: focus,
      es: null,
      backdrop: null,
      cards: {},        // role key -> { card, body, pill, raw }
      bodyBuffers: {},  // role -> running token string
      synthBuffer: "",
      pendingFrame: null,
      sawFirstSseEvent: false,
      sawSynthesis: false,
      synthStartTimer: null,
      offlineTimer: null,
      finalPayload: null,
      keyHandler: null,
    };

    const node = buildModal();
    document.body.appendChild(node);
    state.backdrop = node;

    // Wire keyboard
    state.keyHandler = function (ev) {
      if (ev.key === "Escape") { close(); return; }
      if ((ev.metaKey || ev.ctrlKey) && ev.key === "Enter") {
        ev.preventDefault();
        rerun();
      }
    };
    document.addEventListener("keydown", state.keyHandler);

    // Hydrate from cache so reopening shows the last take instantly.
    const cached = loadCache(meetingId);
    if (cached) hydrateFromPayload(cached, /*cached*/ true);

    // Kick off the live stream
    startStream();
  }

  function close() {
    if (!state) return;
    try { if (state.es) state.es.close(); } catch (_) {}
    if (state.keyHandler) document.removeEventListener("keydown", state.keyHandler);
    if (state.synthStartTimer) clearTimeout(state.synthStartTimer);
    if (state.offlineTimer) clearTimeout(state.offlineTimer);
    if (state.pendingFrame) cancelAnimationFrame(state.pendingFrame);
    if (state.backdrop && state.backdrop.parentNode) {
      state.backdrop.parentNode.removeChild(state.backdrop);
    }
    state = null;
  }

  // ----------------------------------------------------------------
  // DOM construction
  // ----------------------------------------------------------------
  function buildModal() {
    const backdrop = document.createElement("div");
    backdrop.className = "wr-backdrop";
    backdrop.addEventListener("click", (ev) => {
      if (ev.target === backdrop) close();
    });

    const modal = document.createElement("div");
    modal.className = "wr-modal";
    modal.setAttribute("role", "dialog");
    modal.setAttribute("aria-modal", "true");
    modal.setAttribute("aria-label", "Deal Strategy War Room");

    modal.innerHTML =
      '<div class="wr-head">' +
        '<div class="wr-head-titles">' +
          '<div class="wr-head-eyebrow">Deal Strategy War Room</div>' +
          '<div class="wr-head-title">' + esc(state.customerName) + '</div>' +
          '<div class="wr-head-sub">Four expert agents arguing your deal in parallel' +
            (state.focus ? ' · focus: ' + esc(state.focus) : '') + '</div>' +
        '</div>' +
        '<div class="wr-head-actions">' +
          '<button type="button" class="wr-close" aria-label="Close">' +
            '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>' +
          '</button>' +
        '</div>' +
      '</div>' +
      '<div class="wr-body">' +
        '<div class="wr-grid" id="wr-grid"></div>' +
        '<div class="wr-synth" id="wr-synth">' +
          '<div class="wr-synth-head">' +
            '<div class="wr-synth-title">Synthesis · final recommendation</div>' +
            '<div class="wr-synth-conf" id="wr-synth-conf" hidden></div>' +
          '</div>' +
          '<div class="wr-synth-stream" id="wr-synth-stream"></div>' +
          '<ol class="wr-synth-bullets" id="wr-synth-bullets"></ol>' +
          '<div class="wr-synth-why" id="wr-synth-why" hidden></div>' +
        '</div>' +
      '</div>' +
      '<div class="wr-foot">' +
        '<div class="wr-foot-hint">' +
          '<kbd>Esc</kbd> close · <kbd>' + (isMac() ? '⌘' : 'Ctrl') + '</kbd>+<kbd>Enter</kbd> re-run' +
        '</div>' +
        '<div class="wr-foot-actions">' +
          '<button type="button" class="btn ghost" id="wr-copy">Copy synthesis</button>' +
          '<button type="button" class="btn ghost" id="wr-slack">Send to Slack</button>' +
          '<button type="button" class="btn primary" id="wr-rerun">Re-run</button>' +
        '</div>' +
      '</div>';

    backdrop.appendChild(modal);

    // Build the four agent cards
    const grid = modal.querySelector("#wr-grid");
    ROLES.forEach((r) => {
      const card = document.createElement("div");
      card.className = "wr-card";
      card.setAttribute("data-role", r.key);
      card.innerHTML =
        '<div class="wr-card-head">' +
          '<span class="wr-role-icon">' + r.icon + '</span>' +
          '<div style="flex:1; min-width:0">' +
            '<div class="wr-role-name">' + esc(r.label) + '</div>' +
            '<div class="wr-role-desc">' + esc(r.desc) + '</div>' +
          '</div>' +
          '<span class="wr-pill">Waiting</span>' +
        '</div>' +
        '<div class="wr-card-body is-waiting">' +
          '<span class="wr-typing"><span></span><span></span><span></span></span>' +
        '</div>';
      grid.appendChild(card);
      state.cards[r.key] = {
        card: card,
        body: card.querySelector(".wr-card-body"),
        pill: card.querySelector(".wr-pill"),
        raw: null,
      };
      state.bodyBuffers[r.key] = "";
    });

    // Wire footer buttons
    modal.querySelector(".wr-close").addEventListener("click", close);
    modal.querySelector("#wr-copy").addEventListener("click", copySynthesis);
    modal.querySelector("#wr-slack").addEventListener("click", sendToSlack);
    modal.querySelector("#wr-rerun").addEventListener("click", rerun);

    return backdrop;
  }

  function isMac() {
    try { return /Mac|iPhone|iPad/.test(navigator.platform || ""); } catch (_) { return false; }
  }

  // ----------------------------------------------------------------
  // Cache hydration (render a saved payload instantly while live runs)
  // ----------------------------------------------------------------
  function hydrateFromPayload(payload, fromCache) {
    if (!payload) return;
    const agents = payload.agents || {};
    ROLE_KEYS.forEach((k) => {
      const a = agents[k];
      if (!a) return;
      const slot = state.cards[k];
      if (!slot) return;
      const text = a.text || a.summary || a.body || "";
      if (text) {
        slot.body.classList.remove("is-waiting");
        slot.body.textContent = text;
        attachJsonDetails(slot, a);
      }
      setPill(slot.pill, "Done", "is-done");
    });
    if (payload.synthesis) {
      renderSynthesisFinal(payload.synthesis);
    }
    if (fromCache) {
      const synth = $("#wr-synth", state.backdrop);
      if (synth && payload.synthesis) {
        synth.classList.add("is-visible");
        const why = $("#wr-synth-why", state.backdrop);
        if (why && payload.synthesis.why) {
          why.innerHTML = "<strong>Why</strong> " + esc(payload.synthesis.why) +
            ' &middot; <em style="opacity:0.7">cached from previous run</em>';
          why.hidden = false;
        }
      }
    }
  }

  // ----------------------------------------------------------------
  // SSE stream
  // ----------------------------------------------------------------
  function startStream() {
    const url = "/api/v1/war-room/" + encodeURIComponent(state.meetingId) +
                "/stream?focus=" + encodeURIComponent(state.focus || "");

    if (typeof window.EventSource !== "function") {
      fallbackToPost("EventSource not available in this browser");
      return;
    }

    let es;
    try {
      es = new EventSource(url);
    } catch (e) {
      fallbackToPost("EventSource construction failed");
      return;
    }
    state.es = es;

    // If nothing has streamed within 3s, assume the endpoint is dead.
    state.offlineTimer = setTimeout(() => {
      if (!state.sawFirstSseEvent) {
        try { es.close(); } catch (_) {}
        fallbackToPost("No SSE bytes within 3s");
      }
    }, 3000);

    // If synthesis_done hasn't arrived within 35s, fall back. This guards
    // against a hung stream that streamed some tokens but never finished.
    state.synthStartTimer = setTimeout(() => {
      if (!state.sawSynthesis) {
        try { es.close(); } catch (_) {}
        fallbackToPost("Synthesis not produced within 35s");
      }
    }, 35000);

    es.addEventListener("agent_started", (ev) => onSseFirstByte() && handleAgentStarted(parse(ev)));
    es.addEventListener("agent_token",   (ev) => onSseFirstByte() && handleAgentToken(parse(ev)));
    es.addEventListener("agent_done",    (ev) => onSseFirstByte() && handleAgentDone(parse(ev)));
    es.addEventListener("agent_error",   (ev) => onSseFirstByte() && handleAgentError(parse(ev)));
    es.addEventListener("synthesis_token", (ev) => onSseFirstByte() && handleSynthToken(parse(ev)));
    es.addEventListener("synthesis_done",  (ev) => onSseFirstByte() && handleSynthDone(parse(ev)));
    es.addEventListener("done", (_ev) => { try { es.close(); } catch (_) {} });

    es.onerror = function (_ev) {
      // Native readyState 2 = CLOSED. Anything else: let timers decide.
      if (es.readyState === 2 && !state.sawSynthesis) {
        if (!state.sawFirstSseEvent) {
          fallbackToPost("SSE connection closed before any bytes");
        }
      }
    };
  }

  function onSseFirstByte() {
    if (!state || !state.es) return false;
    if (!state.sawFirstSseEvent) {
      state.sawFirstSseEvent = true;
      if (state.offlineTimer) { clearTimeout(state.offlineTimer); state.offlineTimer = null; }
    }
    return true;
  }

  function parse(ev) {
    try { return JSON.parse(ev.data); } catch (_) { return {}; }
  }

  // ----------------------------------------------------------------
  // Event handlers
  // ----------------------------------------------------------------
  function handleAgentStarted(d) {
    const slot = state.cards[d.role];
    if (!slot) return;
    slot.card.classList.add("is-active");
    setPill(slot.pill, "Thinking", "is-thinking");
    state.bodyBuffers[d.role] = "";
    slot.body.classList.remove("is-waiting");
    slot.body.innerHTML = '<span class="wr-typing"><span></span><span></span><span></span></span>';
  }

  function handleAgentToken(d) {
    if (!state.cards[d.role]) return;
    state.bodyBuffers[d.role] += (d.text || "");
    scheduleRender();
  }

  function handleAgentDone(d) {
    const slot = state.cards[d.role];
    if (!slot) return;
    const result = d.result || {};
    slot.raw = result;
    // Prefer the final clean text if present, otherwise keep streamed buffer.
    const finalText = result.text || result.summary || result.body || state.bodyBuffers[d.role] || "";
    state.bodyBuffers[d.role] = finalText;
    scheduleRender();
    setPill(slot.pill, "Done", "is-done");
    slot.card.classList.remove("is-active");
    requestAnimationFrame(() => attachJsonDetails(slot, result));
  }

  function handleAgentError(d) {
    const slot = state.cards[d.role];
    if (!slot) return;
    setPill(slot.pill, "Error", "is-error");
    slot.card.classList.remove("is-active");
    slot.body.classList.remove("is-waiting");
    slot.body.textContent = "Agent error: " + (d.error || "unknown failure");
  }

  function handleSynthToken(d) {
    if (!state.sawSynthesis) {
      const synth = $("#wr-synth", state.backdrop);
      if (synth) synth.classList.add("is-visible");
    }
    state.sawSynthesis = true;
    state.synthBuffer += (d.text || "");
    scheduleRender();
  }

  function handleSynthDone(d) {
    state.sawSynthesis = true;
    if (state.synthStartTimer) { clearTimeout(state.synthStartTimer); state.synthStartTimer = null; }
    renderSynthesisFinal(d);
    state.finalPayload = collectFinalPayload(d);
    saveCache(state.meetingId, state.finalPayload);
  }

  function collectFinalPayload(synth) {
    const agents = {};
    ROLE_KEYS.forEach((k) => {
      const slot = state.cards[k];
      agents[k] = slot && slot.raw
        ? slot.raw
        : { text: state.bodyBuffers[k] || "" };
    });
    return { agents: agents, synthesis: synth || null };
  }

  // ----------------------------------------------------------------
  // rAF-throttled token rendering
  // ----------------------------------------------------------------
  function scheduleRender() {
    if (state.pendingFrame) return;
    state.pendingFrame = requestAnimationFrame(() => {
      state.pendingFrame = null;
      ROLE_KEYS.forEach((k) => {
        const slot = state.cards[k];
        if (!slot) return;
        const buf = state.bodyBuffers[k];
        if (!buf) return;
        // Only repaint when content has changed
        if (slot.body.getAttribute("data-len") === String(buf.length)) return;
        slot.body.setAttribute("data-len", String(buf.length));
        slot.body.classList.remove("is-waiting");
        // Render text + caret if still thinking
        const isThinking = slot.pill.classList.contains("is-thinking");
        slot.body.innerHTML = esc(buf) + (isThinking ? '<span class="wr-cursor"></span>' : '');
      });
      // Synthesis streaming text (pre-finalization)
      if (state.synthBuffer) {
        const sb = $("#wr-synth-stream", state.backdrop);
        if (sb && sb.getAttribute("data-len") !== String(state.synthBuffer.length)) {
          sb.setAttribute("data-len", String(state.synthBuffer.length));
          sb.innerHTML = esc(state.synthBuffer) + '<span class="wr-cursor"></span>';
        }
      }
    });
  }

  function renderSynthesisFinal(synth) {
    if (!state || !synth) return;
    const root = state.backdrop;
    const synthBox = $("#wr-synth", root);
    if (synthBox) synthBox.classList.add("is-visible");

    const bullets = Array.isArray(synth.bullets) ? synth.bullets.slice(0, 3) : [];
    const list = $("#wr-synth-bullets", root);
    const stream = $("#wr-synth-stream", root);
    if (list && bullets.length) {
      list.innerHTML = "";
      bullets.forEach((b) => {
        const li = document.createElement("li");
        li.textContent = String(b || "");
        list.appendChild(li);
      });
      list.classList.add("is-visible");
      if (stream) stream.style.display = "none";
    }

    if (typeof synth.confidence !== "undefined" && synth.confidence != null) {
      const c = $("#wr-synth-conf", root);
      if (c) {
        const conf = typeof synth.confidence === "number"
          ? Math.round(synth.confidence * 100) + "% confidence"
          : String(synth.confidence);
        c.textContent = conf;
        c.hidden = false;
      }
    }

    if (synth.why) {
      const w = $("#wr-synth-why", root);
      if (w) {
        w.innerHTML = "<strong>Why</strong> " + esc(synth.why);
        w.hidden = false;
      }
    }
  }

  function attachJsonDetails(slot, result) {
    // Drop a collapsible JSON dump under the card body
    if (!slot || !result) return;
    if (slot.card.querySelector("details.wr-json")) return;
    const det = document.createElement("details");
    det.className = "wr-json";
    const sum = document.createElement("summary");
    sum.textContent = "Raw agent JSON";
    det.appendChild(sum);
    const pre = document.createElement("pre");
    try { pre.textContent = JSON.stringify(result, null, 2); }
    catch (_) { pre.textContent = String(result); }
    det.appendChild(pre);
    slot.card.appendChild(det);
  }

  function setPill(pill, text, cls) {
    if (!pill) return;
    pill.classList.remove("is-thinking", "is-done", "is-error");
    if (cls) pill.classList.add(cls);
    pill.textContent = text;
  }

  // ----------------------------------------------------------------
  // Non-streaming fallback (POST). Used when SSE is blocked or stalls.
  // ----------------------------------------------------------------
  function fallbackToPost(reason) {
    if (!state) return;
    if (state.offlineTimer) { clearTimeout(state.offlineTimer); state.offlineTimer = null; }
    if (state.synthStartTimer) { clearTimeout(state.synthStartTimer); state.synthStartTimer = null; }
    try { if (state.es) state.es.close(); } catch (_) {}
    state.es = null;

    // Mark all idle agents as "Thinking" so the user sees progress.
    ROLE_KEYS.forEach((k) => {
      const slot = state.cards[k];
      if (!slot) return;
      if (!slot.pill.classList.contains("is-done") && !slot.pill.classList.contains("is-error")) {
        setPill(slot.pill, "Thinking", "is-thinking");
      }
    });

    const doPost = window.apiPostWithRetry
      ? window.apiPostWithRetry("/war-room/" + encodeURIComponent(state.meetingId), { focus: state.focus || "" }, { category: "llm", label: "War Room", silent: true })
      : fetch("/api/v1/war-room/" + encodeURIComponent(state.meetingId), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ focus: state.focus || "" }),
        }).then((r) => {
          if (!r.ok) throw new Error("HTTP " + r.status);
          return r.json();
        });

    doPost.then((payload) => {
      if (!state) return;
      hydrateFromPayload(payload, /*fromCache*/ false);
      state.finalPayload = payload;
      saveCache(state.meetingId, payload);
    }).catch((err) => {
      if (!state) return;
      console.warn("[WarRoom] fallback failed:", reason, err);
      renderOffline();
    });
  }

  function renderOffline() {
    if (!state || !state.backdrop) return;
    const body = $(".wr-body", state.backdrop);
    if (!body) return;
    body.innerHTML =
      '<div class="wr-offline">' +
        '<h3>War Room offline</h3>' +
        '<p>The streaming agents could not be reached. Check the Anthropic + Kibana keys on the backend, then retry.</p>' +
        '<button type="button" class="btn primary" id="wr-retry">Retry</button>' +
      '</div>';
    const btn = body.querySelector("#wr-retry");
    if (btn) btn.addEventListener("click", rerun);
  }

  // ----------------------------------------------------------------
  // Footer actions
  // ----------------------------------------------------------------
  function rerun() {
    if (!state) return;
    const opts = { meetingId: state.meetingId, customerName: state.customerName, focus: state.focus };
    close();
    open(opts);
  }

  function synthesisAsText() {
    if (!state) return "";
    const root = state.backdrop;
    const items = root.querySelectorAll("#wr-synth-bullets li");
    if (items && items.length) {
      const lines = [];
      items.forEach((li, i) => lines.push((i + 1) + ". " + li.textContent.trim()));
      const why = root.querySelector("#wr-synth-why");
      if (why && !why.hidden) lines.push("", "Why: " + why.textContent.replace(/^Why\s*/i, "").trim());
      return lines.join("\n");
    }
    const stream = root.querySelector("#wr-synth-stream");
    return stream ? stream.textContent.trim() : "";
  }

  function copySynthesis() {
    const text = synthesisAsText();
    if (!text) { safeToast("No synthesis yet", "warn"); return; }
    try {
      navigator.clipboard.writeText(text).then(
        () => safeToast("Synthesis copied to clipboard", "ok"),
        () => safeToast("Copy failed", "bad")
      );
    } catch (_) {
      safeToast("Clipboard unavailable", "bad");
    }
  }

  function sendToSlack() {
    const text = synthesisAsText();
    if (!text) { safeToast("No synthesis yet", "warn"); return; }
    const payload = {
      meeting_id: state ? state.meetingId : null,
      customer_name: state ? state.customerName : null,
      text: text,
    };
    const promise = window.apiPostWithRetry
      ? window.apiPostWithRetry("/slack/send", payload, { category: "default", silent: true, label: "Slack" })
      : fetch("/api/v1/slack/send", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }).then((r) => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); });

    promise.then(
      () => safeToast("Sent to Slack", "ok"),
      (_err) => {
        // Soft failure: copy to clipboard instead.
        try {
          navigator.clipboard.writeText(text).then(
            () => safeToast("Slack unavailable - synthesis copied to clipboard", "warn"),
            () => safeToast("Slack unavailable", "warn")
          );
        } catch (_) {
          safeToast("Slack unavailable", "warn");
        }
      }
    );
  }

  // ----------------------------------------------------------------
  // Expose
  // ----------------------------------------------------------------
  window.WarRoom = {
    open: open,
    close: close,
    roles: ROLES.map((r) => ({ key: r.key, label: r.label, desc: r.desc })),
  };
})();
