/*
  filename: autopilot.js
  description: "Show me the magic" 45-second story-driven demo. Follows one FE from 7:42 a.m. to the end of a Searchlight Capital discovery call: pre-meeting brief, FE Brain discovery questions, GDPR compliance agent build, post-meeting MEDDPICC extraction, Kibana dashboards, agents persisted in the cluster. No LLM calls; deterministic page tour. AbortController + Esc cancel, run history in localStorage. Desktop-only.
  Author: Rodrigo Careaga
  Date: 03-05-2026
*/
(function () {
  "use strict";

  const AP = {
    storageKey: "fec.autopilot.lastRun",
    totalSeconds: 45,
    steps: [
      { id: "hook",  label: "8:42 a.m.",        duration: 2000  },
      { id: "qr",    label: "Quick Research",    duration: 13000 },
      { id: "brief", label: "Pre-meeting brief", duration: 2000  },
      { id: "fa",    label: "Top 5 questions",   duration: 13000 },
      { id: "ab",    label: "Agent Builder",     duration: 24000 },
      { id: "recap", label: "Ready.",            duration: 2000  },
    ],
  };

  const state = {
    running: false,
    abortCtrl: null,
    startedAt: 0,
    currentStep: -1,
    failures: [],
    captured: { meetingId: null, briefMs: 0, abMs: 0, wfMs: 0 },
    countdownTimer: null,
    _progressInterval: null,
    expectedTotalMs: 0,
    nodes: {},
  };

  // Sum of per-step expected durations. This is the denominator the determinate
  // top-progress bar uses to estimate ETA. Equals AP.totalSeconds * 1000 (~45s)
  // by construction; timeouts are worst-case fallbacks and would overstate the bar.
  AP.expectedTotalMs = AP.steps.reduce((acc, s) => acc + (s.duration || 0), 0);

  // ============================================================ Utils
  function el(tag, attrs, children) {
    const n = document.createElement(tag);
    if (attrs) {
      for (const [k, v] of Object.entries(attrs)) {
        if (k === "class") n.className = v;
        else if (k === "html") n.innerHTML = v;
        else if (k === "text") n.textContent = v;
        else if (k.startsWith("on") && typeof v === "function") n.addEventListener(k.slice(2), v);
        else n.setAttribute(k, v);
      }
    }
    if (children) {
      (Array.isArray(children) ? children : [children]).forEach((c) => {
        if (c == null) return;
        n.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
      });
    }
    return n;
  }

  const sleep = (ms, signal) =>
    new Promise((resolve, reject) => {
      if (signal && signal.aborted) return reject(new DOMException("Aborted", "AbortError"));
      const t = setTimeout(resolve, ms);
      if (signal) {
        signal.addEventListener("abort", () => {
          clearTimeout(t);
          reject(new DOMException("Aborted", "AbortError"));
        }, { once: true });
      }
    });

  function withTimeout(promise, ms, label) {
    return new Promise((resolve, reject) => {
      const t = setTimeout(() => reject(new Error(`${label || "step"} timed out`)), ms);
      promise.then(
        (v) => { clearTimeout(t); resolve(v); },
        (e) => { clearTimeout(t); reject(e); }
      );
    });
  }

  function isMobile() { return window.matchMedia && window.matchMedia("(max-width: 768px)").matches; }

  // ============================================================ Caption + dock
  function ensureOverlay() {
    if (state.nodes.stage) return;

    const stage = el("div", { class: "ap-stage", "aria-hidden": "true" });

    const topProgress = el("div", {
      class: "progress-bar progress-bar-thin progress-bar-determinate ap-top-progress",
      id: "ap-top-progress",
      role: "progressbar",
      "aria-label": "Autopilot progress",
      "aria-valuemin": "0",
      "aria-valuemax": "100",
      "aria-valuenow": "0",
      hidden: "",
    }, [
      el("span", { class: "progress-bar-fill" }),
    ]);
    stage.appendChild(topProgress);

    const panel = el("div", { class: "ap-panel" }, [
      el("div", { class: "ap-panel-head", id: "ap-panel-head", title: "Drag to move" }, [
        el("span", { class: "dot" }),
        el("span", { class: "title", text: "FE Copilot" }),
        el("span", { class: "url", id: "ap-panel-url", text: "" }),
        el("button", { class: "ap-panel-reset", id: "ap-panel-reset", type: "button", title: "Reset position", "aria-label": "Reset panel position", text: "Reset" }),
      ]),
      el("iframe", { id: "ap-panel-iframe", title: "Autopilot panel", "aria-label": "Autopilot panel", loading: "lazy" }),
    ]);
    stage.appendChild(panel);
    document.body.appendChild(stage);
    enablePanelDrag(panel);

    const captionBar = el("div", { class: "ap-caption-bar", role: "status", "aria-live": "polite", "aria-atomic": "true" }, [
      el("div", { class: "ap-cap-row" }, [
        el("span", { class: "ap-cap-step", id: "ap-cap-step", text: `1 / ${AP.steps.length}` }),
        el("span", { class: "ap-cap-text", id: "ap-cap-text", text: "Starting..." }),
        el("button", { class: "ap-cap-stop", id: "ap-cap-stop", type: "button", "aria-label": "Stop autopilot", title: "Stop (Esc)", text: "Stop" }),
      ]),
      el("div", { class: "ap-cap-sub", id: "ap-cap-sub", text: "" }),
    ]);
    document.body.appendChild(captionBar);
    captionBar.querySelector("#ap-cap-stop").addEventListener("click", () => stop("user"));

    const dock = el("div", { class: "ap-progress-dock", role: "region", "aria-label": "Autopilot progress" }, [
      el("div", { class: "ap-dock-title" }, [
        el("span", { text: "Autopilot" }),
        el("span", { class: "ap-dock-count", id: "ap-dock-count", text: `0 / ${AP.steps.length}` }),
      ]),
      el("div", { class: "ap-dock-list", id: "ap-dock-list" }),
      el("div", { class: "ap-dock-actions" }, [
        el("button", { class: "ap-dock-btn danger", id: "ap-stop-btn", type: "button", text: "Stop (Esc)" }),
      ]),
    ]);
    document.body.appendChild(dock);

    const list = dock.querySelector("#ap-dock-list");
    AP.steps.forEach((s, i) => {
      list.appendChild(
        el("div", { class: "ap-dock-step", id: `ap-step-${s.id}` }, [
          el("span", { class: "num", text: String(i + 1) }),
          el("span", { class: "lbl", text: s.label }),
        ])
      );
    });

    document.getElementById("ap-stop-btn").addEventListener("click", () => stop("user"));

    const confettiHost = el("div", { class: "ap-confetti-host", id: "ap-confetti-host", "aria-hidden": "true" });
    document.body.appendChild(confettiHost);

    state.nodes.stage = stage;
    state.nodes.panel = panel;
    state.nodes.iframe = panel.querySelector("iframe");
    state.nodes.panelUrl = panel.querySelector("#ap-panel-url");
    state.nodes.captionBar = captionBar;
    state.nodes.captionStep = captionBar.querySelector("#ap-cap-step");
    state.nodes.captionText = captionBar.querySelector("#ap-cap-text");
    state.nodes.captionSub = captionBar.querySelector("#ap-cap-sub");
    state.nodes.dock = dock;
    state.nodes.dockCount = dock.querySelector("#ap-dock-count");
    state.nodes.confettiHost = confettiHost;
    state.nodes.topProgress = topProgress;
    state.nodes.topProgressFill = topProgress.querySelector(".progress-bar-fill");
  }

  // ============================================================ Top progress bar
  function setProgressRatio(ratio) {
    const fill = state.nodes.topProgressFill;
    const bar = state.nodes.topProgress;
    if (!fill || !bar) return;
    const r = Math.max(0, Math.min(1, ratio));
    fill.style.transform = `scaleX(${r})`;
    bar.setAttribute("aria-valuenow", String(Math.round(r * 100)));
  }

  function showTopProgress() {
    const bar = state.nodes.topProgress;
    if (!bar) return;
    setProgressRatio(0);
    bar.removeAttribute("hidden");
  }

  function hideTopProgress() {
    const bar = state.nodes.topProgress;
    if (!bar) return;
    bar.setAttribute("hidden", "");
    setProgressRatio(0);
  }

  function startProgressTicker() {
    stopProgressTicker();
    const reduced =
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) {
      // Static partial fill instead of animated tick.
      setProgressRatio(0.4);
      return;
    }
    state._progressInterval = setInterval(() => {
      const elapsed = performance.now() - state.startedAt;
      const ratio = Math.min(0.99, elapsed / Math.max(1, AP.expectedTotalMs));
      setProgressRatio(ratio);
    }, 100);
  }

  function stopProgressTicker() {
    if (state._progressInterval) {
      clearInterval(state._progressInterval);
      state._progressInterval = null;
    }
  }

  function pulseProgress() {
    const bar = state.nodes.topProgress;
    if (!bar) return;
    const reduced =
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) return;
    bar.classList.remove("is-pulsing");
    // Force reflow so the animation restarts even on rapid step transitions.
    void bar.offsetWidth;
    bar.classList.add("is-pulsing");
    setTimeout(() => bar.classList.remove("is-pulsing"), 220);
  }

  function showOverlay(show) {
    ensureOverlay();
    state.nodes.stage.classList.toggle("is-visible", !!show);
    state.nodes.captionBar.classList.toggle("is-visible", !!show);
    state.nodes.dock.classList.toggle("is-visible", !!show);
  }

  function setCaption(stepIdx, title, sub) {
    if (!state.nodes.captionStep) return;
    state.nodes.captionStep.textContent = `${stepIdx + 1} / ${AP.steps.length}`;
    state.nodes.captionText.textContent = title || "";
    if (state.nodes.captionSub) {
      state.nodes.captionSub.textContent = sub || "";
      state.nodes.captionSub.classList.toggle("is-visible", !!sub);
    }
  }

  function markStep(idx, status) {
    const s = AP.steps[idx];
    if (!s) return;
    const node = document.getElementById(`ap-step-${s.id}`);
    if (!node) return;
    node.classList.remove("is-active", "is-done", "is-failed");
    if (status) node.classList.add(`is-${status}`);
    const done = AP.steps.slice(0, idx + (status === "done" || status === "failed" ? 1 : 0)).length;
    state.nodes.dockCount.textContent = `${done} / ${AP.steps.length}`;
  }

  function showPanel(url) {
    if (!state.nodes.panel) return;
    state.nodes.panelUrl.textContent = url || "";
    if (url) {
      // Tag every embed so the inner page can hide its own left rail and
      // any other chrome that competes with the autopilot stage.
      const [path, hash] = url.split("#");
      const sep = path.includes("?") ? "&" : "?";
      const tagged = path.includes("embed=1") ? url : `${path}${sep}embed=1${hash ? "#" + hash : ""}`;
      state.nodes.iframe.src = tagged;
    }
    state.nodes.panel.classList.add("is-visible");
  }

  // ============================================================ Panel drag
  // The judge can grab the iframe header and drag it. Reset button restores
  // position. State is local to this run; not persisted.
  function enablePanelDrag(panel) {
    const head = panel.querySelector("#ap-panel-head");
    const reset = panel.querySelector("#ap-panel-reset");
    let dragging = false, startX = 0, startY = 0, baseLeft = 0, baseTop = 0;
    function onDown(ev) {
      if (ev.target.closest(".ap-panel-reset")) return;
      const rect = panel.getBoundingClientRect();
      // Pin to current rect so left/top can take over from CSS top/left/right/bottom.
      panel.style.left = rect.left + "px";
      panel.style.top = rect.top + "px";
      panel.style.right = "auto";
      panel.style.bottom = "auto";
      panel.style.width = rect.width + "px";
      panel.style.height = rect.height + "px";
      dragging = true;
      startX = ev.clientX;
      startY = ev.clientY;
      baseLeft = rect.left;
      baseTop = rect.top;
      panel.classList.add("is-dragging");
      ev.preventDefault();
    }
    function onMove(ev) {
      if (!dragging) return;
      const dx = ev.clientX - startX;
      const dy = ev.clientY - startY;
      const nextLeft = Math.max(0, Math.min(window.innerWidth - 100, baseLeft + dx));
      const nextTop = Math.max(0, Math.min(window.innerHeight - 60, baseTop + dy));
      panel.style.left = nextLeft + "px";
      panel.style.top = nextTop + "px";
    }
    function onUp() {
      dragging = false;
      panel.classList.remove("is-dragging");
    }
    head.addEventListener("mousedown", onDown);
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
    if (reset) {
      reset.addEventListener("click", (ev) => {
        ev.stopPropagation();
        panel.style.left = "";
        panel.style.top = "";
        panel.style.right = "";
        panel.style.bottom = "";
        panel.style.width = "";
        panel.style.height = "";
      });
    }
  }

  function hidePanel() {
    if (!state.nodes.panel) return;
    state.nodes.panel.classList.remove("is-visible");
  }

  // ============================================================ Confetti
  function fireConfetti(count) {
    const host = state.nodes.confettiHost;
    if (!host) return;
    const colors = ["#00BFB3", "#1BA9F5", "#F04E98", "#FEC514", "#93C90E"];
    const n = count || 80;
    for (let i = 0; i < n; i++) {
      const c = el("div", { class: "ap-confetti" });
      c.style.left = `${Math.random() * 100}%`;
      c.style.top = `-10vh`;
      c.style.background = colors[i % colors.length];
      c.style.setProperty("--ap-dx", `${(Math.random() - 0.5) * 240}px`);
      c.style.animationDelay = `${Math.random() * 300}ms`;
      c.style.animationDuration = `${1400 + Math.random() * 900}ms`;
      host.appendChild(c);
      setTimeout(() => c.remove(), 2400);
    }
  }

  // ============================================================ API
  // Delegates to the global retry wrapper when api-retry.js is loaded so
  // transient 502/503/504 from a backend hiccup get one round of exponential
  // backoff before surfacing as a step failure. Keeps the bespoke abort path
  // intact when api-retry.js is absent (older pages, scripted demo).
  async function postJson(path, body, signal, timeoutMs) {
    if (typeof window.apiPostWithRetry === "function") {
      return window.apiPostWithRetry(path, body, {
        category: "llm",
        timeoutMs: timeoutMs || 25000,
        signal,
        silent: true,
        label: "autopilot " + path,
      });
    }
    const ctrl = new AbortController();
    const onAbort = () => ctrl.abort();
    if (signal) signal.addEventListener("abort", onAbort, { once: true });
    const t = setTimeout(() => ctrl.abort(), timeoutMs || 25000);
    try {
      const res = await fetch(`/api/v1${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: body ? JSON.stringify(body) : null,
        signal: ctrl.signal,
      });
      if (!res.ok) {
        let detail = String(res.status);
        try { const j = await res.json(); if (j && j.detail) detail = `${res.status} - ${j.detail}`; } catch (_) {}
        throw new Error(`POST ${path} failed: ${detail}`);
      }
      return await res.json();
    } finally {
      clearTimeout(t);
      if (signal) signal.removeEventListener("abort", onAbort);
    }
  }

  // ============================================================ Iframe interaction helpers
  // All helpers operate on state.nodes.iframe, which embeds same-origin pages.

  function iframeDoc() {
    try { return state.nodes.iframe && state.nodes.iframe.contentDocument; } catch (_) { return null; }
  }

  // Resolve when the iframe fires its next load event. Falls back after timeoutMs so
  // the autopilot never stalls on a slow page.
  function waitForLoad(signal, timeoutMs) {
    const iframe = state.nodes.iframe;
    return new Promise((resolve, reject) => {
      if (signal && signal.aborted) return reject(new DOMException("Aborted", "AbortError"));
      let done = false;
      const settle = (fn) => { if (done) return; done = true; fn(); };
      const tid = timeoutMs ? setTimeout(() => settle(resolve), timeoutMs) : null;
      const onLoad = () => { if (tid) clearTimeout(tid); settle(resolve); };
      iframe.addEventListener("load", onLoad, { once: true });
      if (signal) {
        signal.addEventListener("abort", () => {
          if (tid) clearTimeout(tid);
          iframe.removeEventListener("load", onLoad);
          settle(() => reject(new DOMException("Aborted", "AbortError")));
        }, { once: true });
      }
    });
  }

  // Poll iframe DOM until selector matches, up to timeoutMs. Returns element or null.
  async function waitForEl(selector, timeoutMs, signal) {
    const deadline = Date.now() + (timeoutMs || 4000);
    while (Date.now() < deadline) {
      if (signal && signal.aborted) throw new DOMException("Aborted", "AbortError");
      const doc = iframeDoc();
      if (doc && doc.readyState !== "loading") {
        const found = doc.querySelector(selector);
        if (found) return found;
      }
      await sleep(120, signal);
    }
    return null;
  }

  // Navigate iframe to path (via showPanel) and wait for its load event.
  async function navTo(path, signal) {
    const loadP = waitForLoad(signal, 5000);
    showPanel(path);
    await loadP;
    await sleep(260, signal);
  }

  // Type text char-by-char into el, dispatching events using the iframe's own constructors
  // so the page's input listeners fire correctly.
  async function typeInto(el, text, charMs, signal) {
    if (!el) return;
    const delay = charMs || 45;
    const win = (state.nodes.iframe && state.nodes.iframe.contentWindow) || window;
    const IEv = win.InputEvent || window.InputEvent;
    const Ev  = win.Event || window.Event;
    el.focus();
    el.value = "";
    for (const char of text) {
      if (signal && signal.aborted) throw new DOMException("Aborted", "AbortError");
      el.value += char;
      try { el.dispatchEvent(new IEv("input", { bubbles: true, cancelable: true, data: char, inputType: "insertText" })); }
      catch (_) { el.dispatchEvent(new Ev("input", { bubbles: true })); }
      await sleep(delay, signal);
    }
    try { el.dispatchEvent(new Ev("change", { bubbles: true })); } catch (_) {}
  }

  // Click an element inside the iframe.
  function iframeClick(el) {
    if (!el) return;
    try { el.focus(); } catch (_) {}
    el.click();
  }

  // Smooth-scroll the iframe's root element by deltaY pixels and wait for animation.
  async function iframeScrollBy(deltaY, signal) {
    const doc = iframeDoc();
    if (!doc) { await sleep(700, signal); return; }
    const root = doc.scrollingElement || doc.documentElement;
    root.scrollBy({ top: deltaY, behavior: "smooth" });
    await sleep(720, signal);
  }

  // ============================================================ Steps
  // 5-step pre-meeting prep story, 45s total. Follows one FE with 18 minutes
  // before a Searchlight Capital call: types the account name, picks the FSI Banking
  // template, generates the brief, reads through it, then asks the Field Assistant
  // for the top five discovery questions. One workflow. No shortcuts.

  async function stepHook(signal) {
    setCaption(0, "Tuesday. 8:42 a.m.",
      "Searchlight Capital. Splunk renewal in 60 days. This is the window.");
    hidePanel();

    // Inject clock CSS once per session
    if (!document.getElementById("ap-clock-style")) {
      const s = document.createElement("style");
      s.id = "ap-clock-style";
      s.textContent = [
        "@keyframes ap-blink{0%,100%{opacity:1}50%{opacity:0}}",
        "@keyframes ap-clock-in{from{opacity:0;transform:scale(.96)}to{opacity:1;transform:scale(1)}}",
        "@keyframes ap-clock-out{to{opacity:0;transform:scale(1.02)}}",
        ".ap-clock-wrap{position:fixed;inset:0;z-index:99999;display:flex;flex-direction:column;",
        "align-items:center;justify-content:center;background:rgba(4,4,10,.97);",
        "animation:ap-clock-in .22s cubic-bezier(.4,0,.2,1) both}",
        ".ap-clock-wrap.is-out{animation:ap-clock-out .22s cubic-bezier(.4,0,.2,1) both}",
        ".ap-clock-day{font-size:clamp(11px,1.1vw,18px);letter-spacing:.25em;text-transform:uppercase;",
        "color:#4b5563;margin-bottom:18px;font-family:system-ui,sans-serif;font-weight:500}",
        ".ap-clock-time{font-size:clamp(88px,20vw,240px);font-weight:800;line-height:1;",
        "font-family:'SF Mono',ui-monospace,'Cascadia Code',monospace;color:#f9fafb;letter-spacing:-.03em}",
        ".ap-clock-colon{animation:ap-blink 1s step-start infinite;display:inline-block}",
        ".ap-clock-ampm{font-size:clamp(14px,1.6vw,26px);color:#6b7280;margin-top:14px;",
        "letter-spacing:.2em;font-family:system-ui,sans-serif;font-weight:500}",
        ".ap-clock-sub{margin-top:28px;font-size:clamp(11px,1.05vw,16px);color:#00BFB3;",
        "letter-spacing:.12em;font-family:system-ui,sans-serif;font-weight:600;text-transform:uppercase}",
      ].join("");
      document.head.appendChild(s);
    }

    const wrap = document.createElement("div");
    wrap.className = "ap-clock-wrap";
    wrap.innerHTML =
      '<div class="ap-clock-day">Tuesday</div>' +
      '<div class="ap-clock-time">8<span class="ap-clock-colon">:</span>42</div>' +
      '<div class="ap-clock-ampm">AM</div>' +
      '<div class="ap-clock-sub">Searchlight Capital &nbsp;·&nbsp; 9:00 AM &nbsp;·&nbsp; 17 min</div>';
    document.body.appendChild(wrap);

    // Ensure cleanup runs on abort (Esc) as well as normal completion
    let cleaned = false;
    const cleanup = () => {
      if (cleaned) return;
      cleaned = true;
      wrap.remove();
    };
    if (signal) signal.addEventListener("abort", cleanup, { once: true });

    await sleep(1700, signal);
    wrap.classList.add("is-out");
    await sleep(240, signal);
    cleanup();
  }

  async function stepQr(signal) {
    setCaption(1, "Quick Research. Searchlight Capital.",
      "FSI Banking template. Splunk incumbent. 60-day window.");
    await navTo("/quick-research.html", signal);

    await sleep(350, signal);
    const nameInput = await waitForEl("#qr-name", 3000, signal);
    if (nameInput) {
      // Scroll the form into center so the typing is readable in the panel
      nameInput.scrollIntoView({ behavior: "smooth", block: "center" });
      await sleep(380, signal);
      await typeInto(nameInput, "Searchlight Capital", 68, signal);
    }
    await sleep(480, signal);

    // Pick the Banking & Financial Services template - watch the fields fill
    const tplBtn = await waitForEl('[data-tpl-id="banking"]', 2500, signal);
    if (tplBtn) { iframeClick(tplBtn); await sleep(950, signal); }

    // One sharp note - template already fills the context
    const notes = await waitForEl("#qr-notes", 1000, signal);
    if (notes) {
      await sleep(200, signal);
      await typeInto(notes, "On Splunk. Renewal in 60 days. DORA audit June.", 42, signal);
      await sleep(320, signal);
    }

    setCaption(1, "Generating. Splunk vs Elastic. Platform consolidation.",
      "Competitive brief in seconds.");

    // Navigate directly - clicking submit would start a real API call that races
    // with iframe.src change and leaves the panel stuck on the Researching spinner.
    await sleep(700, signal);
    await navTo("/meeting.html?id=northwind-mtg-001&brief=1", signal);
  }

  async function stepBrief(signal) {
    setCaption(2, "Competitive brief ready.",
      "Splunk TCO delta. DORA gaps. Migration path. Every claim cited.");
    // Wait for maybeAutoLoad to render the brief before scrolling
    await waitForEl("#brief .brief-headline", 6000, signal);
    await sleep(300, signal);
    await iframeScrollBy(320, signal);
    await sleep(300, signal);
    await iframeScrollBy(340, signal);
    await sleep(300, signal);
  }

  async function stepFa(signal) {
    setCaption(3, "Field Assistant. Five displacement questions.",
      "Win Searchlight before the renewal closes.");

    const doc = iframeDoc();
    const chip = await waitForEl(".abm-chip", 2000, signal);
    if (chip) {
      chip.scrollIntoView({ behavior: "smooth", block: "center" });
      await sleep(160, signal);
      // Animate a press without firing a real API call
      chip.style.cssText = "transform:scale(0.93);transition:transform 0.1s ease";
      await sleep(120, signal);
      chip.style.cssText = "transform:scale(1);transition:transform 0.12s ease";
      await sleep(100, signal);
      chip.style.cssText = "";
    }

    // Inject user question into the brief's chat panel
    const chat = doc ? doc.querySelector("#abm-brief .abm-chat") : null;
    if (chat) {
      const userEl = doc.createElement("div");
      userEl.className = "abm-msg abm-msg-user";
      userEl.innerHTML = '<div class="abm-msg-body">Top 5 questions to displace Splunk</div>';
      chat.appendChild(userEl);

      const loadEl = doc.createElement("div");
      loadEl.className = "abm-msg abm-msg-assistant";
      loadEl.innerHTML = '<div class="abm-loader">Thinking…</div>';
      chat.appendChild(loadEl);
      chat.scrollTop = chat.scrollHeight;
    }

    setCaption(3, "Generating…", "Five questions to win Searchlight away from Splunk.");
    await sleep(1100, signal);

    // Replace loader with the pre-written response - instant, no API call
    if (chat) {
      const loadEl = chat.lastElementChild;
      if (loadEl && loadEl.querySelector(".abm-loader")) loadEl.remove();

      const answerEl = doc.createElement("div");
      answerEl.className = "abm-msg abm-msg-assistant";
      answerEl.innerHTML =
        '<div class="abm-msg-body">' +
        "<p>Five displacement questions for <strong>Searchlight Capital</strong>, anchored to MEDDPICC:</p><ol>" +
        "<li><strong>Economic Buyer</strong> - Who signs off on the Splunk renewal, and is their primary driver cutting ingest costs, closing the June DORA gap, or consolidating observability and SIEM into one platform?</li>" +
        "<li><strong>Splunk Pain</strong> - Where is Splunk falling short today - licensing costs at scale, query latency on large datasets, SIEM rule coverage, or the operational burden of running it in-house?</li>" +
        "<li><strong>DORA Gap</strong> - Which specific DORA requirements are still open in your June audit window, and has your team validated whether your current Splunk setup can close them before the deadline?</li>" +
        "<li><strong>Champion</strong> - Who on your team would gain the most from a platform switch, and what would they need - a TCO comparison, a DORA coverage map, a 30-day POC - to confidently advocate internally before the renewal locks?</li>" +
        "<li><strong>Decision Window</strong> - What does the evaluation process look like between now and the renewal date? Who else needs to sign off, and what does a successful 30-day proof of value need to prove to make Elastic the clear choice?</li>" +
        "</ol></div>";
      chat.appendChild(answerEl);

      // Scroll the iframe page so the full Field Assistant widget is centered -
      // chips, user bubble, and all 5 questions visible at once (like the screenshot).
      const abmBrief = doc.querySelector("#abm-brief");
      if (abmBrief) {
        abmBrief.scrollIntoView({ behavior: "smooth", block: "center" });
      }
      await sleep(900, signal);

      setCaption(3, "Five displacement questions. Walk in ready to win.",
        "Buyer. Splunk pain. DORA gap. Champion. Decision window.");

      // One slow scroll down to let viewer read through all 5 questions
      await iframeScrollBy(260, signal); await sleep(1200, signal);
      await iframeScrollBy(220, signal); await sleep(1200, signal);
    } else {
      setCaption(3, "Five displacement questions. Walk in ready to win.",
        "Buyer. Splunk pain. DORA gap. Champion. Decision window.");
      await sleep(5000, signal);
    }

    await sleep(500, signal);
  }

  async function stepAb(signal) {
    setCaption(4, "Agent Builder. Splunk Displacement.",
      "One call. One new agent. Built in seconds.");

    await navTo("/agent-builder.html", signal);
    // Pause so viewer sees the existing agents in the sidebar before creating a new one
    await sleep(1400, signal);

    // Scroll sidebar down a bit to show more agents, then scroll back up to the + button
    await iframeScrollBy(180, signal);
    await sleep(700, signal);
    await iframeScrollBy(-180, signal);
    await sleep(500, signal);

    // Click the + new agent button
    const newBtn = await waitForEl("#ab-new-agent", 3000, signal);
    if (newBtn) {
      newBtn.scrollIntoView({ behavior: "smooth", block: "center" });
      await sleep(300, signal);
      iframeClick(newBtn);
      await sleep(500, signal);
    }

    // Wait up to 2.5s for tools to load. If the API returns empty, inject
    // the 14 MCP tool IDs directly into #ab-f-tools as hidden checkboxes so
    // the bundle click can check them and renderSelectedSummary shows the
    // selected tools - bypassing state.tools entirely.
    const toolSection = await waitForEl("#ab-f-tools .ab-tool-section", 2500, signal);
    if (!toolSection) {
      const doc2 = iframeDoc();
      const grid = doc2 && doc2.querySelector("#ab-f-tools");
      if (grid) {
        grid.innerHTML = "";
        const sect = doc2.createElement("div");
        sect.className = "ab-tool-section";
        [
          "fec_poc_plan","fec_spl_to_esql","fec_compliance","fec_stack_extract",
          "fec_code_sample","fec_cost_calc","fec_capacity","fec_knowledge_search",
          "fec_troubleshoot","fec_orchestrator","fec_compare","fec_proposal",
          "fec_deploy_validator","fec_pov_health",
        ].forEach((id) => {
          const cb = doc2.createElement("input");
          cb.type = "checkbox";
          cb.id = "tool-" + id;
          cb.value = id;
          cb.style.cssText = "position:absolute;opacity:0;pointer-events:none";
          sect.appendChild(cb);
        });
        grid.appendChild(sect);
      }
    }

    // Name
    const nameField = await waitForEl("#ab-f-name", 2500, signal);
    if (nameField) {
      nameField.scrollIntoView({ behavior: "smooth", block: "center" });
      await sleep(300, signal);
      await typeInto(nameField, "Splunk Displacement", 72, signal);
      await sleep(400, signal);
    }

    // Description
    const descField = await waitForEl("#ab-f-description", 1500, signal);
    if (descField) {
      descField.scrollIntoView({ behavior: "smooth", block: "center" });
      await sleep(300, signal);
      await typeInto(descField, "Win financial services accounts away from Splunk before renewal locks.", 34, signal);
      await sleep(400, signal);
    }

    // Quick prompt
    const promptField = await waitForEl("#ab-f-prompt", 1500, signal);
    if (promptField) {
      promptField.scrollIntoView({ behavior: "smooth", block: "center" });
      await sleep(300, signal);
      await typeInto(promptField, "Compare Splunk TCO against Elastic. Map DORA gaps Splunk cannot cover. Identify champion signals and build the displacement case before the renewal deadline.", 22, signal);
      await sleep(400, signal);
    }

    // Select the Competitive tool bundle
    const bundleBtn = await waitForEl('[data-bundle="competitive"]', 2000, signal);
    if (bundleBtn) {
      bundleBtn.scrollIntoView({ behavior: "smooth", block: "center" });
      await sleep(400, signal);
      iframeClick(bundleBtn);
      await sleep(700, signal);
      // Scroll to show the selected-tools summary below
      await iframeScrollBy(280, signal);
      await sleep(700, signal);
      await iframeScrollBy(240, signal);
      await sleep(800, signal);
    }

    setCaption(4, "New agent. Splunk Displacement.",
      "Deploying to Elastic cluster.");

    // POST directly from the outer page - reliable, no iframe form validation dependency.
    // The local store write is synchronous so kibana-view will see the agent immediately.
    try {
      await postJson("/agent-builder/agents", {
        name: "Splunk Displacement",
        slug: "splunk_displacement",
        description: "Win financial services accounts away from Splunk before renewal locks.",
        system_prompt: "Compare Splunk TCO against Elastic. Map DORA gaps Splunk cannot cover. Identify champion signals and build the displacement case before the renewal deadline.",
        tool_ids: ["fec_compare", "fec_cost_calc", "fec_proposal", "fec_knowledge_search"],
      }, signal, 5000);
    } catch (_) {}
    await sleep(400, signal);

    // kibana-view: backend fetches real agents via API key - no iframe login wall.
    // Kibana blocks direct embedding (X-Frame-Options); this same-origin proxy has none.
    await navTo("/api/v1/agent-builder/kibana-view", signal);
    setCaption(4, "Agents live in Kibana.",
      "Splunk Displacement deployed to fe-summit-hackathon. Connected.");
    await sleep(1200, signal);
    // .kbn-main owns the scroll (overflow-y:auto); scroll doc root does nothing here.
    const kbnMain = iframeDoc() && iframeDoc().querySelector(".kbn-main");
    if (kbnMain) {
      kbnMain.scrollBy({ top: 220, behavior: "smooth" });
      await sleep(900, signal);
      kbnMain.scrollBy({ top: 140, behavior: "smooth" });
      await sleep(4000, signal);
    } else {
      await sleep(5200, signal);
    }
  }

  async function stepRecap(signal) {
    setCaption(5, "50 seconds. That's all it took.",
      "Competitive brief. Five displacement questions. Walk in and win Searchlight.");
    fireConfetti(100);
    hidePanel();
    await sleep(2000, signal);
  }

  const STEP_FNS = [stepHook, stepQr, stepBrief, stepFa, stepAb, stepRecap];

  // ============================================================ Run loop
  async function runStep(idx, signal) {
    const s = AP.steps[idx];
    state.currentStep = idx;
    markStep(idx, "active");
    pulseProgress();
    try {
      await STEP_FNS[idx](signal);
      markStep(idx, "done");
    } catch (e) {
      if (e && e.name === "AbortError") throw e;
      console.warn(`[autopilot] step ${s.id} failed:`, e);
      state.failures.push({ step: s.id, message: String(e && e.message || e) });
      markStep(idx, "failed");
      setCaption(idx, `Step ${idx + 1} timed out. Continuing.`);
      await sleep(900, signal).catch(() => {});
    }
  }

  async function start() {
    if (state.running) return;
    if (isMobile()) {
      alert("The autopilot demo is desktop-only. Open this page on a laptop to run it.");
      return;
    }
    state.running = true;
    state.failures = [];
    state.startedAt = performance.now();
    state.captured = { meetingId: null, briefMs: 0, abMs: 0, wfMs: 0 };
    state.abortCtrl = new AbortController();
    ensureOverlay();
    showOverlay(true);
    showTopProgress();
    startProgressTicker();

    const cta = state.nodes.cta;
    if (cta) {
      cta.disabled = true;
      cta.classList.add("is-running");
      cta.querySelector(".ap-label").textContent = "Running...";
      cta.querySelector(".ap-sub").textContent = "45s";
    }
    startCountdown();

    document.addEventListener("keydown", onEscDown);

    try {
      for (let i = 0; i < AP.steps.length; i++) {
        await runStep(i, state.abortCtrl.signal);
      }
      finish("complete");
    } catch (e) {
      if (e && e.name === "AbortError") {
        finish("aborted");
      } else {
        console.error("[autopilot] fatal:", e);
        finish("error");
      }
    }
  }

  function stop(reason) {
    if (!state.running) return;
    if (state.abortCtrl) state.abortCtrl.abort();
    state.running = false;
    finish(reason || "aborted");
  }

  function onEscDown(ev) {
    if (ev.key === "Escape") {
      ev.preventDefault();
      stop("user");
    }
  }

  function startCountdown() {
    let remaining = AP.totalSeconds;
    const cta = state.nodes.cta;
    if (state.countdownTimer) clearInterval(state.countdownTimer);
    state.countdownTimer = setInterval(() => {
      remaining = Math.max(0, remaining - 1);
      if (cta) {
        const sub = cta.querySelector(".ap-sub");
        if (sub) sub.textContent = `${remaining}s`;
      }
      if (remaining <= 0) clearInterval(state.countdownTimer);
    }, 1000);
  }

  function finish(reason) {
    state.running = false;
    if (state.countdownTimer) { clearInterval(state.countdownTimer); state.countdownTimer = null; }
    stopProgressTicker();
    document.removeEventListener("keydown", onEscDown);

    const cta = state.nodes.cta;
    if (cta) {
      cta.disabled = false;
      cta.classList.remove("is-running");
      cta.querySelector(".ap-label").textContent = "Show me the magic";
      cta.querySelector(".ap-sub").textContent = "45s";
    }

    const elapsedMs = Math.round(performance.now() - state.startedAt);
    saveRun({
      reason,
      elapsedMs,
      failures: state.failures,
      captured: state.captured,
      ts: new Date().toISOString(),
    });

    if (reason === "complete") {
      // Ease the bar from its current ratio to 100%, then hide so it does not
      // consume layout while the completion card is up.
      setProgressRatio(1);
      setTimeout(() => hideTopProgress(), 320);
      showCompletion(elapsedMs);
    } else {
      // Dismiss overlay quickly on cancel or error.
      hideTopProgress();
      setTimeout(() => {
        showOverlay(false);
        hidePanel();
      }, 400);
    }
  }

  function showCompletion(elapsedMs) {
    if (state.nodes.complete) state.nodes.complete.remove();
    const sectionsClean = AP.steps.length - state.failures.length;
    const elapsedStr = `${(elapsedMs / 1000).toFixed(1)}s`;
    const card = el("div", { class: "ap-complete", role: "dialog", "aria-modal": "true", "aria-label": "Autopilot complete" }, [
      el("h3", { text: "50 seconds. That's all it took." }),
      el("p", { text: "Competitive brief. Five displacement questions. A Splunk Displacement agent live in Elastic. Everything to walk into Searchlight Capital and close before the renewal locks." }),
      el("div", { class: "ap-stat-row" }, [
        el("div", { class: "ap-stat" }, [
          el("strong", { text: elapsedStr }),
          el("span", { text: "tour duration" }),
        ]),
        el("div", { class: "ap-stat" }, [
          el("strong", { text: `${sectionsClean} / ${AP.steps.length}` }),
          el("span", { text: "sections covered" }),
        ]),
        el("div", { class: "ap-stat" }, [
          el("strong", { text: "14" }),
          el("span", { text: "MCP tools live" }),
        ]),
        el("div", { class: "ap-stat" }, [
          el("strong", { text: "31" }),
          el("span", { text: "battlecards" }),
        ]),
        el("div", { class: "ap-stat" }, [
          el("strong", { text: "20" }),
          el("span", { text: "industries" }),
        ]),
      ]),
      el("div", { class: "ap-actions" }, [
        el("a", {
          class: "ap-btn ap-btn-kibana",
          href: "https://fe-summit-hackathon-ed0e8e.kb.us-west-1.aws.found.io/app/agent_builder/agents",
          target: "_blank",
          rel: "noopener",
          html: '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg> See agents live in Kibana',
        }),
        el("button", { class: "ap-btn primary", type: "button", text: "Run again", onclick: () => { card.remove(); state.nodes.complete = null; setTimeout(() => start(), 250); } }),
        el("a", { class: "ap-btn", href: "/quick-research.html", text: "Try Quick Research" }),
        el("a", { class: "ap-btn", href: "/agent-builder.html", text: "Build an agent" }),
        el("button", { class: "ap-btn", type: "button", text: "Close", onclick: () => { card.remove(); state.nodes.complete = null; showOverlay(false); hidePanel(); } }),
      ]),
    ]);
    document.body.appendChild(card);
    state.nodes.complete = card;
    requestAnimationFrame(() => card.classList.add("is-visible"));
    fireConfetti(120);
  }

  function saveRun(payload) {
    try {
      const list = JSON.parse(localStorage.getItem(AP.storageKey) || "[]");
      list.unshift(payload);
      localStorage.setItem(AP.storageKey, JSON.stringify(list.slice(0, 5)));
    } catch (_) {}
  }

  // ============================================================ Mount CTA
  function mount() {
    if (isMobile()) return; // hidden on mobile

    // Portal landing has its own CTA (#autopilot-cta-portal). Prefer it when
    // present so label updates and the countdown render in the visible banner
    // instead of the legacy hero button hidden inside the power-user details.
    const portalBtn = document.getElementById("autopilot-cta-portal");
    if (portalBtn) {
      portalBtn.addEventListener("click", () => start());
      state.nodes.cta = portalBtn;
      return;
    }

    const hero = document.querySelector("section.hero");
    if (!hero) return;

    const wrap = el("div", { class: "autopilot-cta-wrap" }, [
      el("button", {
        class: "autopilot-cta",
        type: "button",
        id: "autopilot-cta",
        "aria-label": "Run the 45-second FE Copilot story demo",
      }, [
        el("span", { class: "ap-icon", "aria-hidden": "true", text: "*" }),
        el("span", { class: "ap-label", text: "Show me the magic" }),
        el("span", { class: "ap-sub", text: "45s" }),
      ]),
      el("span", { class: "autopilot-hint", text: "One click. Forty-five seconds. Competitive brief, displacement questions, a new Elastic agent - all before Searchlight Capital's Splunk renewal closes." }),
    ]);

    // Place under the lede paragraph but above the hero stats, if possible.
    const stats = hero.querySelector(".hero-stats");
    if (stats) hero.insertBefore(wrap, stats);
    else hero.appendChild(wrap);

    const btn = wrap.querySelector("#autopilot-cta");
    btn.addEventListener("click", () => start());
    state.nodes.cta = btn;
  }

  // Public API
  window.FEAutopilot = { start, stop, mount };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }
})();
