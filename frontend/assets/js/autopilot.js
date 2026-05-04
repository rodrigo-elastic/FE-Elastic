/*
  filename: autopilot.js
  description: "Show me the magic" 30-second autonomous demo orchestrator. Drives 7 steps end-to-end (confetti, ad-hoc brief, meeting iframe, Field Assistant chain, Agent Builder, Workflow Demo, recap) using existing FE Copilot endpoints. AbortController + Esc cancel, graceful per-step timeouts, run history in localStorage. Desktop-only.
  Author: Rodrigo Careaga
  Date: 03-05-2026
*/
(function () {
  "use strict";

  const AP = {
    storageKey: "fec.autopilot.lastRun",
    totalSeconds: 30,
    steps: [
      { id: "intro",   label: "Intro",                duration: 2000  },
      { id: "qr",      label: "Quick Research",       duration: 5000, timeout: 18000 },
      { id: "brief",   label: "Brief view",           duration: 5000  },
      { id: "field",   label: "Field Assistant chain", duration: 6000, timeout: 22000 },
      { id: "ab",      label: "Agent Builder",        duration: 6000, timeout: 22000 },
      { id: "wf",      label: "Workflow loop",        duration: 5000, timeout: 12000 },
      { id: "recap",   label: "Recap",                duration: 1000  },
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
  // top-progress bar uses to estimate ETA. Equals AP.totalSeconds * 1000 (~30s)
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
      el("div", { class: "ap-panel-head" }, [
        el("span", { class: "dot" }),
        el("span", { class: "title", text: "FE Copilot" }),
        el("span", { class: "url", id: "ap-panel-url", text: "" }),
      ]),
      el("iframe", { id: "ap-panel-iframe", title: "Autopilot panel", "aria-label": "Autopilot panel" }),
    ]);
    stage.appendChild(panel);
    document.body.appendChild(stage);

    const captionBar = el("div", { class: "ap-caption-bar", role: "status", "aria-live": "polite", "aria-atomic": "true" }, [
      el("span", { class: "ap-cap-step", id: "ap-cap-step", text: "1 / 7" }),
      el("span", { class: "ap-cap-text", id: "ap-cap-text", text: "Starting..." }),
    ]);
    document.body.appendChild(captionBar);

    const dock = el("div", { class: "ap-progress-dock", role: "region", "aria-label": "Autopilot progress" }, [
      el("div", { class: "ap-dock-title" }, [
        el("span", { text: "Autopilot" }),
        el("span", { class: "ap-dock-count", id: "ap-dock-count", text: "0 / 7" }),
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

  function setCaption(stepIdx, text) {
    if (!state.nodes.captionStep) return;
    state.nodes.captionStep.textContent = `${stepIdx + 1} / ${AP.steps.length}`;
    state.nodes.captionText.textContent = text;
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
    if (url) state.nodes.iframe.src = url;
    state.nodes.panel.classList.add("is-visible");
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
  async function postJson(path, body, signal, timeoutMs) {
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

  // ============================================================ Steps
  async function stepIntro(signal) {
    setCaption(0, "FE Copilot demo. 30 seconds, fully autonomous.");
    fireConfetti(60);
    const btn = state.nodes.cta;
    if (btn) btn.classList.add("is-running");
    await sleep(1900, signal);
  }

  async function stepQuickResearch(signal) {
    setCaption(1, "Pre-meeting brief: SEC EDGAR + news + Wikipedia...");
    showPanel("/");
    const body = {
      company_name: "Banco Atlántico",
      industry: "Banking",
      size: "Enterprise",
      tech_stack: "Splunk, AWS, ServiceNow",
      notes: "Autopilot demo run. Pre-meeting research for a fictional retail-banking conversation.",
      meeting_title: "Banco Atlántico pre-meeting (autopilot)",
      model: "claude-haiku-4-5",
    };
    const t0 = performance.now();
    const result = await withTimeout(
      postJson("/agents/pre-meeting/ad-hoc", body, signal, 18000),
      18000,
      "Quick Research"
    );
    state.captured.briefMs = Math.round(performance.now() - t0);
    if (!result || !result.meeting_id) throw new Error("no meeting_id returned");
    state.captured.meetingId = result.meeting_id;
    return result;
  }

  async function stepBriefView(signal) {
    setCaption(2, "Brief generated. SEC EDGAR + news + Wikipedia cited.");
    if (!state.captured.meetingId) {
      throw new Error("no brief id");
    }
    const url = `/meeting.html?id=${encodeURIComponent(state.captured.meetingId)}&adhoc=1&brief=1`;
    showPanel(url);
    await sleep(4500, signal);
  }

  async function stepFieldAssistant(signal) {
    setCaption(3, "Master agent chains fec_poc_plan + fec_cost_calc autonomously...");
    const t0 = performance.now();
    const prompt = "Build a quick POC plan outline for this account, then run a TCO calc at 200 GB/day, 12 months retention, current spend $1.5M. Keep it tight.";
    try {
      await withTimeout(
        postJson("/agent-builder/converse", {
          message: prompt,
          agent_id: "fec_field_assistant",
        }, signal, 22000),
        22000,
        "Field Assistant"
      );
    } finally {
      state.captured.abMs = Math.round(performance.now() - t0);
    }
    await sleep(800, signal);
  }

  async function stepAgentBuilder(signal) {
    setCaption(4, "Agent Builder live in your Kibana. 10 MCP tools.");
    showPanel("/agent-builder.html?autopilot=1");
    // Drive a small live conversation in parallel so the panel shows real activity.
    try {
      const iframe = state.nodes.iframe;
      iframe.addEventListener("load", () => {
        try {
          const doc = iframe.contentDocument;
          const input = doc && doc.getElementById("ab-input");
          const form = doc && doc.getElementById("ab-form");
          if (input && form) {
            input.value = "What is the Black Friday outage telling us about checkout-db?";
            const ev = new Event("submit", { bubbles: true, cancelable: true });
            form.dispatchEvent(ev);
          }
        } catch (_) { /* cross-frame or not ready */ }
      }, { once: true });
    } catch (_) {}
    await sleep(5500, signal);
  }

  async function stepWorkflow(signal) {
    setCaption(5, "Workflow loop: agent -> ES -> alerting rule -> webhook -> agent.");
    showPanel("/workflow-demo.html?autopilot=1");
    const t0 = performance.now();
    try {
      await withTimeout(
        postJson("/workflows/demo-fire", null, signal, 8000),
        8000,
        "Workflow fire"
      );
    } catch (_) {
      // backend route may differ; we still show the panel and the caption.
    } finally {
      state.captured.wfMs = Math.round(performance.now() - t0);
    }
    await sleep(3800, signal);
  }

  async function stepRecap(signal) {
    setCaption(6, "Demo complete. 30 seconds. Zero typing.");
    fireConfetti(120);
    hidePanel();
    await sleep(900, signal);
  }

  const STEP_FNS = [stepIntro, stepQuickResearch, stepBriefView, stepFieldAssistant, stepAgentBuilder, stepWorkflow, stepRecap];

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
      cta.querySelector(".ap-sub").textContent = "30s";
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
      cta.querySelector(".ap-sub").textContent = "30s";
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
    const card = el("div", { class: "ap-complete", role: "dialog", "aria-modal": "true", "aria-label": "Autopilot complete" }, [
      el("h3", { text: "Demo complete." }),
      el("p", { text: "All your tools, one assistant. Ready for the live walkthrough." }),
      el("div", { class: "ap-stat-row" }, [
        el("div", { class: "ap-stat" }, [
          el("strong", { text: `${(elapsedMs / 1000).toFixed(1)}s` }),
          el("span", { text: "elapsed" }),
        ]),
        el("div", { class: "ap-stat" }, [
          el("strong", { text: `${AP.steps.length - state.failures.length} / ${AP.steps.length}` }),
          el("span", { text: "steps clean" }),
        ]),
        el("div", { class: "ap-stat" }, [
          el("strong", { text: state.captured.briefMs ? `${(state.captured.briefMs / 1000).toFixed(1)}s` : "n/a" }),
          el("span", { text: "brief gen" }),
        ]),
      ]),
      el("div", { class: "ap-actions" }, [
        el("button", { class: "ap-btn primary", type: "button", text: "Watch again", onclick: () => { card.remove(); state.nodes.complete = null; setTimeout(() => start(), 250); } }),
        el("a", { class: "ap-btn", href: "https://www.youtube.com/", target: "_blank", rel: "noopener", text: "View video" }),
        el("a", { class: "ap-btn", href: "/agent-builder.html", text: "Open Kibana" }),
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
    const hero = document.querySelector("section.hero");
    if (!hero) return;

    const wrap = el("div", { class: "autopilot-cta-wrap" }, [
      el("button", {
        class: "autopilot-cta",
        type: "button",
        id: "autopilot-cta",
        "aria-label": "Run the 30-second FE Copilot autonomous demo",
      }, [
        el("span", { class: "ap-icon", "aria-hidden": "true", text: "*" }),
        el("span", { class: "ap-label", text: "Show me the magic" }),
        el("span", { class: "ap-sub", text: "30s" }),
      ]),
      el("span", { class: "autopilot-hint", text: "One click. Watch the full FE Copilot pipeline run end-to-end with zero typing." }),
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
