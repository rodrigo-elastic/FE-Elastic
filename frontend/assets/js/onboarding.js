/*
  filename: onboarding.js
  description: First-visit onboarding tour for FE Copilot. Shows a five-step guided overlay (autopilot
  CTA, FE Brain, Agent Builder, Demo Data, hours-saved widget) the first time a judge lands on the
  dashboard. Persists in localStorage so it only fires once. Keyboard accessible (Tab cycles within
  the card, Enter advances, Esc dismisses). Auto-attaches a "Replay tour" pill bottom-right after
  dismissal so judges can re-trigger it without clearing storage.
  Author: Rodrigo Careaga
  Date: 04-05-2026
*/
(function () {
  "use strict";

  if (window.FEOnboarding && window.FEOnboarding.__installed) return;

  const STORAGE_KEY = "fec.onboarding.seen";
  const DELAY_MS = 800;

  function t(key, fallback) {
    try {
      if (typeof window.t === "function") {
        const v = window.t(key);
        if (v && v !== key) return v;
      }
    } catch (_e) { /* i18n not ready */ }
    return fallback;
  }

  function hasSeen() {
    try { return localStorage.getItem(STORAGE_KEY) === "1"; } catch (_e) { return false; }
  }

  function markSeen() {
    try { localStorage.setItem(STORAGE_KEY, "1"); } catch (_e) { /* private mode */ }
  }

  function clearSeen() {
    try { localStorage.removeItem(STORAGE_KEY); } catch (_e) { /* private mode */ }
  }

  function isDashboard() {
    const p = location.pathname;
    return p === "/" || p === "/index.html" || /\/index\.html$/.test(p);
  }

  // -------------------------------------------------------------- step config
  // Each step lists primary + fallback selectors; first match wins. If nothing
  // resolves, the step is skipped silently.
  function getSteps() {
    return [
      {
        id: "autopilot",
        targets: [".autopilot-cta-wrap", "#autopilot-cta", ".autopilot-cta"],
        position: "below",
        title: t("onboard.step1.title", "Try the autopilot"),
        body: t(
          "onboard.step1.body",
          "One click runs the full FE Copilot pipeline in 45 seconds. No typing. Hit Esc anytime to stop."
        ),
      },
      {
        id: "fe-brain",
        targets: [
          '.tools-sidebar a[href="/fe-brain.html"]',
          'a[href="/fe-brain.html"]',
          ".tools-sidebar",
        ],
        position: "right",
        title: t("onboard.step2.title", "FE Brain"),
        body: t(
          "onboard.step2.body",
          "Cited answers in 10 seconds. Hybrid retrieval over 1300 Elastic doc chunks. Stop pinging Slack."
        ),
      },
      {
        id: "agent-builder",
        targets: [
          '.tools-sidebar a[href="/agent-builder.html"]',
          'a[href="/agent-builder.html"]',
          ".tools-sidebar",
        ],
        position: "right",
        title: t("onboard.step3.title", "Build agents in your Kibana"),
        body: t(
          "onboard.step3.body",
          "The master agent has 12 MCP tools. Build your own specialists from a modal. They persist in your cluster."
        ),
      },
      {
        id: "demo-data",
        targets: [
          '.tools-sidebar a[href="/demo-data.html"]',
          'a[href="/demo-data.html"]',
          ".tools-sidebar",
        ],
        position: "right",
        title: t("onboard.step4.title", "Customer-ready demos"),
        body: t(
          "onboard.step4.body",
          "Eight scenarios with paired FE and Customer dashboards. Atlas Eyewear-style demos in 15 seconds, not half a day."
        ),
      },
      {
        id: "hours-saved",
        targets: [".hero-savings", ".hero-stats"],
        position: "above",
        title: t("onboard.step5.title", "Six hours back, every week"),
        body: t(
          "onboard.step5.body",
          "Tracked from the audit log. Every tool call, agent run, and workflow fire counts toward the running total."
        ),
      },
    ];
  }

  // -------------------------------------------------------------- DOM helpers
  function el(tag, attrs, kids) {
    const n = document.createElement(tag);
    if (attrs) {
      for (const k in attrs) {
        if (k === "class") n.className = attrs[k];
        else if (k === "style") n.setAttribute("style", attrs[k]);
        else if (k.startsWith("on") && typeof attrs[k] === "function") {
          n.addEventListener(k.slice(2), attrs[k]);
        } else if (attrs[k] != null) {
          n.setAttribute(k, attrs[k]);
        }
      }
    }
    if (kids) {
      (Array.isArray(kids) ? kids : [kids]).forEach(function (c) {
        if (c == null) return;
        if (typeof c === "string") n.appendChild(document.createTextNode(c));
        else n.appendChild(c);
      });
    }
    return n;
  }

  function findTarget(selectors) {
    for (let i = 0; i < selectors.length; i++) {
      const s = selectors[i];
      try {
        const el = document.querySelector(s);
        if (el && el.offsetParent !== null) return { el, selector: s };
        if (el) return { el, selector: s }; // visible-or-not, accept
      } catch (_e) { /* invalid selector */ }
    }
    return null;
  }

  function rectOf(el) {
    const r = el.getBoundingClientRect();
    return {
      top: r.top,
      left: r.left,
      width: r.width,
      height: r.height,
    };
  }

  // -------------------------------------------------------------- state
  let state = {
    overlay: null,
    cutout: null,
    card: null,
    arrow: null,
    titleEl: null,
    bodyEl: null,
    counterEl: null,
    backBtn: null,
    nextBtn: null,
    skipBtn: null,
    shield: null,
    keyHandler: null,
    resizeHandler: null,
    scrollHandler: null,
    stepIdx: 0,
    steps: [],
    active: false,
  };

  function buildOverlay() {
    const overlay = el("div", { class: "fec-onboard-overlay", role: "dialog", "aria-modal": "true", "aria-label": "Product tour" });
    const shield = el("div", { class: "fec-onboard-shield" });
    const cutout = el("div", { class: "fec-onboard-cutout" });
    const card = el("div", { class: "fec-onboard-card", role: "document", tabindex: "-1" });

    const counter = el("div", { class: "fec-onboard-counter" });
    const title = el("h3", { class: "fec-onboard-title" });
    const body = el("p", { class: "fec-onboard-body" });
    const arrow = el("div", { class: "fec-onboard-arrow up" });

    const backBtn = el(
      "button",
      { type: "button", class: "fec-onboard-btn" },
      t("onboard.back", "Back")
    );
    const nextBtn = el(
      "button",
      { type: "button", class: "fec-onboard-btn primary" },
      t("onboard.next", "Next")
    );
    const skipBtn = el(
      "button",
      { type: "button", class: "fec-onboard-skip" },
      t("onboard.skip", "Skip tour")
    );

    const nav = el("div", { class: "fec-onboard-nav" }, [backBtn, nextBtn]);
    const actions = el("div", { class: "fec-onboard-actions" }, [skipBtn, nav]);

    card.appendChild(arrow);
    card.appendChild(counter);
    card.appendChild(title);
    card.appendChild(body);
    card.appendChild(actions);

    overlay.appendChild(shield);
    overlay.appendChild(cutout);
    overlay.appendChild(card);

    state.overlay = overlay;
    state.cutout = cutout;
    state.card = card;
    state.arrow = arrow;
    state.titleEl = title;
    state.bodyEl = body;
    state.counterEl = counter;
    state.backBtn = backBtn;
    state.nextBtn = nextBtn;
    state.skipBtn = skipBtn;
    state.shield = shield;

    backBtn.addEventListener("click", function () { goPrev(); });
    nextBtn.addEventListener("click", function () { goNext(); });
    skipBtn.addEventListener("click", function () { dismiss(true); });
    shield.addEventListener("click", function () {
      const ok = window.confirm(t("onboard.confirm_close", "Skip the tour? You can replay it later."));
      if (ok) dismiss(true);
    });

    return overlay;
  }

  function place(stepIdx) {
    const steps = state.steps;
    if (stepIdx < 0 || stepIdx >= steps.length) return;
    const s = steps[stepIdx];

    const found = findTarget(s.targets);
    if (!found) {
      // Skip the step quietly - move forward.
      const nextIdx = stepIdx + 1;
      if (nextIdx < steps.length) { state.stepIdx = nextIdx; place(nextIdx); }
      else { dismiss(true); }
      return;
    }

    const r = rectOf(found.el);
    const pad = 6;
    const top = r.top - pad + window.scrollY;
    const left = r.left - pad + window.scrollX;
    const w = r.width + pad * 2;
    const h = r.height + pad * 2;

    // Place cutout in absolute (page) coordinates; since the overlay is fixed,
    // we use viewport coordinates instead to stay aligned during scroll.
    state.cutout.style.top = (r.top - pad) + "px";
    state.cutout.style.left = (r.left - pad) + "px";
    state.cutout.style.width = w + "px";
    state.cutout.style.height = h + "px";

    // Card placement
    const cardW = 320;
    const cardEstH = 170; // estimate; the real height will adjust naturally
    const margin = 14;
    let cTop = 0;
    let cLeft = 0;
    let arrowDir = "up";

    const vw = window.innerWidth;
    const vh = window.innerHeight;

    function clampLeft(L) {
      return Math.max(8, Math.min(L, vw - cardW - 8));
    }
    function clampTop(T) {
      return Math.max(8, Math.min(T, vh - cardEstH - 8));
    }

    if (s.position === "below") {
      cTop = r.top + r.height + margin;
      cLeft = r.left + r.width / 2 - cardW / 2;
      arrowDir = "up";
      if (cTop + cardEstH > vh - 8) {
        cTop = r.top - margin - cardEstH;
        arrowDir = "down";
      }
    } else if (s.position === "above") {
      cTop = r.top - margin - cardEstH;
      cLeft = r.left + r.width / 2 - cardW / 2;
      arrowDir = "down";
      if (cTop < 8) {
        cTop = r.top + r.height + margin;
        arrowDir = "up";
      }
    } else if (s.position === "right") {
      cLeft = r.left + r.width + margin;
      cTop = r.top + r.height / 2 - cardEstH / 2;
      arrowDir = "left";
      if (cLeft + cardW > vw - 8) {
        cLeft = r.left - margin - cardW;
        arrowDir = "right";
      }
    } else if (s.position === "left") {
      cLeft = r.left - margin - cardW;
      cTop = r.top + r.height / 2 - cardEstH / 2;
      arrowDir = "right";
      if (cLeft < 8) {
        cLeft = r.left + r.width + margin;
        arrowDir = "left";
      }
    }

    cTop = clampTop(cTop);
    cLeft = clampLeft(cLeft);

    state.card.style.top = cTop + "px";
    state.card.style.left = cLeft + "px";

    // Arrow position: anchor to the side facing the target.
    state.arrow.className = "fec-onboard-arrow " + arrowDir;
    state.arrow.style.top = "";
    state.arrow.style.bottom = "";
    state.arrow.style.left = "";
    state.arrow.style.right = "";
    if (arrowDir === "up") {
      state.arrow.style.top = "-8px";
      const ax = (r.left + r.width / 2) - cLeft;
      state.arrow.style.left = Math.max(12, Math.min(cardW - 22, ax - 9)) + "px";
    } else if (arrowDir === "down") {
      state.arrow.style.bottom = "-8px";
      const ax = (r.left + r.width / 2) - cLeft;
      state.arrow.style.left = Math.max(12, Math.min(cardW - 22, ax - 9)) + "px";
    } else if (arrowDir === "left") {
      state.arrow.style.left = "-8px";
      const ay = (r.top + r.height / 2) - cTop;
      state.arrow.style.top = Math.max(12, Math.min(cardEstH - 22, ay - 9)) + "px";
    } else if (arrowDir === "right") {
      state.arrow.style.right = "-8px";
      const ay = (r.top + r.height / 2) - cTop;
      state.arrow.style.top = Math.max(12, Math.min(cardEstH - 22, ay - 9)) + "px";
    }

    // Content
    state.titleEl.textContent = s.title;
    state.bodyEl.textContent = s.body;
    state.counterEl.textContent = (stepIdx + 1) + " / " + steps.length;

    // Buttons
    state.backBtn.disabled = stepIdx === 0;
    const lastIdx = steps.length - 1;
    state.nextBtn.textContent = stepIdx === lastIdx
      ? t("onboard.got_it", "Got it")
      : t("onboard.next", "Next");

    // Scroll into view if needed
    if (r.top < 60 || r.top > vh - 100) {
      try { found.el.scrollIntoView({ behavior: "smooth", block: "center" }); } catch (_e) { /* */ }
    }
  }

  function goPrev() {
    if (state.stepIdx > 0) {
      state.stepIdx -= 1;
      place(state.stepIdx);
      focusCard();
    }
  }

  function goNext() {
    if (state.stepIdx < state.steps.length - 1) {
      state.stepIdx += 1;
      place(state.stepIdx);
      focusCard();
    } else {
      dismiss(true);
    }
  }

  function focusCard() {
    try {
      // Focus the primary action so Enter advances.
      if (state.nextBtn) state.nextBtn.focus();
    } catch (_e) { /* */ }
  }

  function trapTab(ev) {
    const focusables = [state.backBtn, state.skipBtn, state.nextBtn].filter(function (b) {
      return b && !b.disabled;
    });
    if (focusables.length === 0) return;
    const idx = focusables.indexOf(document.activeElement);
    if (ev.shiftKey) {
      if (idx <= 0) {
        ev.preventDefault();
        focusables[focusables.length - 1].focus();
      }
    } else {
      if (idx === focusables.length - 1) {
        ev.preventDefault();
        focusables[0].focus();
      }
    }
  }

  function onKey(ev) {
    if (!state.active) return;
    if (ev.key === "Escape") {
      ev.preventDefault();
      dismiss(true);
    } else if (ev.key === "Tab") {
      trapTab(ev);
    } else if (ev.key === "Enter") {
      // Only intercept if the focused element is one of our buttons; otherwise
      // let native behavior happen.
      if (document.activeElement === state.nextBtn) {
        ev.preventDefault();
        goNext();
      } else if (document.activeElement === state.backBtn) {
        ev.preventDefault();
        goPrev();
      } else if (document.activeElement === state.skipBtn) {
        ev.preventDefault();
        dismiss(true);
      }
    } else if (ev.key === "ArrowRight") {
      ev.preventDefault();
      goNext();
    } else if (ev.key === "ArrowLeft") {
      ev.preventDefault();
      goPrev();
    }
  }

  function start() {
    if (state.active) return;
    state.steps = getSteps();
    if (!state.steps.length) return;

    // Build (or rebuild) overlay
    if (state.overlay && state.overlay.parentNode) state.overlay.parentNode.removeChild(state.overlay);
    buildOverlay();
    document.body.appendChild(state.overlay);

    state.stepIdx = 0;
    state.active = true;

    place(state.stepIdx);
    focusCard();

    state.keyHandler = onKey;
    document.addEventListener("keydown", state.keyHandler, true);

    state.resizeHandler = function () { if (state.active) place(state.stepIdx); };
    state.scrollHandler = function () { if (state.active) place(state.stepIdx); };
    window.addEventListener("resize", state.resizeHandler);
    window.addEventListener("scroll", state.scrollHandler, true);
  }

  function teardown() {
    if (state.keyHandler) {
      document.removeEventListener("keydown", state.keyHandler, true);
      state.keyHandler = null;
    }
    if (state.resizeHandler) {
      window.removeEventListener("resize", state.resizeHandler);
      state.resizeHandler = null;
    }
    if (state.scrollHandler) {
      window.removeEventListener("scroll", state.scrollHandler, true);
      state.scrollHandler = null;
    }
    if (state.overlay && state.overlay.parentNode) {
      state.overlay.parentNode.removeChild(state.overlay);
    }
    state.overlay = null;
    state.active = false;
  }

  function dismiss(persist) {
    teardown();
    if (persist) markSeen();
    ensureReplayPill();
  }

  // -------------------------------------------------------------- replay pill
  function ensureReplayPill() {
    if (!hasSeen()) return; // only show after dismissal
    if (document.querySelector(".fec-onboard-replay")) return;
    if (!isDashboard()) return; // dashboard-only re-trigger

    const btn = el(
      "button",
      {
        type: "button",
        class: "fec-onboard-replay",
        "aria-label": t("onboard.replay", "Replay tour"),
        title: t("onboard.replay", "Replay tour"),
      }
    );
    btn.innerHTML =
      '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
      'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      '<path d="M3 12a9 9 0 1 0 3-6.7"/><polyline points="3 4 3 10 9 10"/></svg>' +
      '<span>' + t("onboard.replay", "Replay tour") + '</span>';

    btn.addEventListener("click", function () {
      // Re-clear so the start() call mounts fresh.
      clearSeen();
      // Remove the pill so it does not overlap the tour.
      if (btn.parentNode) btn.parentNode.removeChild(btn);
      start();
    });
    document.body.appendChild(btn);
  }

  // -------------------------------------------------------------- bootstrap
  function init() {
    // Always make the API available, even if we do not auto-start.
    window.FEOnboarding = {
      __installed: true,
      start: function () { clearSeen(); start(); },
      dismiss: function () { dismiss(true); },
      hasSeen: hasSeen,
    };

    if (hasSeen()) {
      ensureReplayPill();
      return;
    }

    if (!isDashboard()) return;

    // Let the page paint first, then start.
    setTimeout(function () {
      // Re-check in case another tab dismissed it in the meantime.
      if (hasSeen()) { ensureReplayPill(); return; }
      start();
    }, DELAY_MS);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init, { once: true });
  } else {
    init();
  }
})();
