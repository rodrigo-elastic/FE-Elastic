/*
  filename: dashboard-stats.js
  description: Hours-saved ROI hero widget. Calls /api/v1/stats/savings, paints the
    band, animates the headline counter on first paint, refreshes every 60s. Hides
    the band gracefully if the endpoint 404s or 500s.
  Author: Rodrigo Careaga
  Date: 04-05-2026
*/
(function () {
  "use strict";

  const REFRESH_MS = 60 * 1000;
  const ANIM_MS = 1200;
  const ENDPOINT = "/api/v1/stats/savings";

  const els = {};
  let firstPaint = true;

  function $(id) {
    return document.getElementById(id);
  }

  function easeOutCubic(t) {
    return 1 - Math.pow(1 - t, 3);
  }

  function _prefersReducedMotion() {
    return !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  }
  function animateNumber(node, from, to, durationMs) {
    if (!node) return;
    const decimals = to % 1 !== 0 ? 1 : 0;
    // WCAG 2.3.3 Animation from Interactions: render the final value
    // immediately when the user has requested reduced motion.
    if (_prefersReducedMotion()) {
      node.textContent = decimals ? to.toFixed(1) : Math.round(to).toString();
      return;
    }
    const start = performance.now();
    const delta = to - from;
    function frame(now) {
      const t = Math.min(1, (now - start) / durationMs);
      const v = from + delta * easeOutCubic(t);
      node.textContent = decimals ? v.toFixed(1) : Math.round(v).toString();
      if (t < 1) requestAnimationFrame(frame);
      else node.textContent = decimals ? to.toFixed(1) : Math.round(to).toString();
    }
    requestAnimationFrame(frame);
  }

  function setText(node, text) {
    if (node && typeof text !== "undefined" && text !== null) node.textContent = text;
  }

  function classifyDelta(deltaStr) {
    if (!deltaStr) return "zero";
    const m = String(deltaStr).match(/(-?\d+)/);
    if (!m) return "zero";
    const v = parseInt(m[1], 10);
    if (isNaN(v) || v === 0) return "zero";
    return v > 0 ? "positive" : "negative";
  }

  function paint(data) {
    if (!els.host) return;
    const tw = (data && data.this_week) || {};
    const top = (data && data.top_savings_tool) || {};

    // First paint animates from 0; subsequent updates only animate if value changed.
    const hours = typeof tw.hours_saved === "number" ? tw.hours_saved : 0;
    if (firstPaint) {
      animateNumber(els.hours, 0, hours, ANIM_MS);
      firstPaint = false;
    } else {
      const current = parseFloat(els.hours.textContent || "0");
      if (Math.abs(current - hours) > 0.05) {
        animateNumber(els.hours, current, hours, 600);
      }
    }

    setText(
      els.teamAvg,
      typeof data.team_average_per_fe_per_week === "number"
        ? data.team_average_per_fe_per_week.toFixed(1)
        : "0.0"
    );
    setText(els.topTool, top && top.id ? top.id : "(none)");
    setText(els.delta, tw.delta_vs_last_week || "+0%");

    if (els.deltaPill) {
      els.deltaPill.classList.remove("hs-delta-positive", "hs-delta-zero", "hs-delta-negative");
      els.deltaPill.classList.add("hs-delta-" + classifyDelta(tw.delta_vs_last_week));
    }

    if (els.foot) {
      if (data && data.seed) {
        const note = (window.t && window.t("savings.demo_note")) || "(demo data, audit log warming up)";
        els.foot.textContent = note;
        els.foot.hidden = false;
      } else {
        els.foot.hidden = true;
        els.foot.textContent = "";
      }
    }

    els.host.hidden = false;
  }

  async function fetchSavings() {
    // Use the retry wrapper when available so transient 502/503/504 from the
    // backend (cold-start, k8s rolling restart) do not collapse the band.
    // silent: true so we hide the band without spamming a toast on every miss.
    try {
      if (typeof window.apiGetWithRetry === "function") {
        return await window.apiGetWithRetry("/stats/savings", {
          category: "compute",
          cache: "no-store",
          silent: true,
          label: "savings",
        });
      }
      const res = await fetch(ENDPOINT, { cache: "no-store" });
      if (!res.ok) {
        if (els.host) els.host.hidden = true;
        return null;
      }
      return await res.json();
    } catch (e) {
      if (els.host) els.host.hidden = true;
      return null;
    }
  }

  async function tick() {
    const data = await fetchSavings();
    if (data) paint(data);
  }

  function init() {
    els.host = $("hero-savings");
    els.hours = $("hs-hours");
    els.teamAvg = $("hs-team-avg");
    els.topTool = $("hs-top-tool");
    els.delta = $("hs-delta");
    els.deltaPill = $("hs-delta-pill");
    els.foot = $("hs-foot");
    if (!els.host) return;
    tick();
    setInterval(tick, REFRESH_MS);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
