/*
  filename: audit.js
  description: FE Copilot self-observability page logic. Fetches /api/v1/audit, aggregates the entries client-side (calls-over-time, tokens-by-model, top tools, per-agent rollup, recent fires), and renders pure SVG charts. 30s silent refresh, 60s sessionStorage cache.
  Author: Rodrigo Careaga
  Date: 03-05-2026
*/
(function () {
  "use strict";

  // ------------------------------------------------------------------
  // Constants
  // ------------------------------------------------------------------
  const CACHE_KEY = "fec_audit_cache_v1";
  const CACHE_TTL_MS = 60 * 1000;
  const REFRESH_MS = 30 * 1000;
  const WINDOW_DAYS = 7;
  const FETCH_LIMIT = 1000; // backend supports `limit`; cap to keep payload small

  // Filter state (search input + date range buttons).
  const SEARCH_DEBOUNCE_MS = 150;
  const RANGE_MS = {
    "1h": 60 * 60 * 1000,
    "24h": 24 * 60 * 60 * 1000,
    "7d": 7 * 24 * 60 * 60 * 1000,
    "all": null, // no cutoff
  };
  const state = {
    rawEntries: [],          // last fetched entries (parsed once)
    search: "",              // current search query (lowercased)
    range: "24h",            // current date range key
    rollupSort: { key: "calls", dir: "desc" },
    recentSort: { key: "ts", dir: "desc" },
  };

  // ------------------------------------------------------------------
  // Number / time helpers
  // ------------------------------------------------------------------
  function fmtInt(n) {
    if (n === null || n === undefined || Number.isNaN(n)) return "0";
    n = Math.round(Number(n) || 0);
    return n.toLocaleString("en-US");
  }
  function fmtCompact(n) {
    n = Number(n) || 0;
    const abs = Math.abs(n);
    if (abs >= 1e9) return (n / 1e9).toFixed(1).replace(/\.0$/, "") + "B";
    if (abs >= 1e6) return (n / 1e6).toFixed(1).replace(/\.0$/, "") + "M";
    if (abs >= 1e3) return (n / 1e3).toFixed(1).replace(/\.0$/, "") + "k";
    return String(Math.round(n));
  }
  function fmtPct(num, den) {
    if (!den) return "0%";
    return Math.round((num / den) * 100) + "%";
  }
  function parseTs(s) {
    if (!s) return null;
    const d = new Date(s);
    if (Number.isNaN(d.getTime())) return null;
    return d;
  }
  function fmtRelative(d) {
    if (!d) return "-";
    const now = Date.now();
    const ms = now - d.getTime();
    const sec = Math.round(ms / 1000);
    if (sec < 60) return sec + "s ago";
    const min = Math.round(sec / 60);
    if (min < 60) return min + "m ago";
    const hr = Math.round(min / 60);
    if (hr < 24) return hr + "h ago";
    const day = Math.round(hr / 24);
    return day + "d ago";
  }
  function fmtTime(d) {
    if (!d) return "-";
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    const hh = String(d.getHours()).padStart(2, "0");
    const mi = String(d.getMinutes()).padStart(2, "0");
    return `${yyyy}-${mm}-${dd} ${hh}:${mi}`;
  }
  function modelFamily(m) {
    if (!m) return "other";
    const s = String(m).toLowerCase();
    if (s.includes("haiku")) return "haiku";
    if (s.includes("sonnet")) return "sonnet";
    if (s.includes("opus")) return "opus";
    return "other";
  }
  function entryLabel(e) {
    if (!e) return "unknown";
    if (e.tool) return e.tool;
    if (e.agent) return e.agent;
    return "unknown";
  }

  // ------------------------------------------------------------------
  // Fetch with sessionStorage cache (60s)
  // ------------------------------------------------------------------
  async function fetchAudit({ force = false } = {}) {
    if (!force) {
      try {
        const raw = sessionStorage.getItem(CACHE_KEY);
        if (raw) {
          const cached = JSON.parse(raw);
          if (cached && cached.ts && Date.now() - cached.ts < CACHE_TTL_MS && cached.data) {
            return cached.data;
          }
        }
      } catch (_) { /* ignore cache errors */ }
    }
    const data = await apiGet(`/audit?limit=${FETCH_LIMIT}`);
    try {
      sessionStorage.setItem(CACHE_KEY, JSON.stringify({ ts: Date.now(), data: data }));
    } catch (_) { /* quota / private mode */ }
    return data;
  }

  // ------------------------------------------------------------------
  // Aggregation (client-side, runs over raw entries)
  // ------------------------------------------------------------------
  // Decorate the raw entries with a parsed Date once. Done up-front so the
  // search and date-range filters can run over the same shape.
  function decorateEntries(entries) {
    const out = [];
    for (const e of entries) {
      const d = parseTs(e.ts);
      if (!d) continue;
      out.push({ ...e, _d: d });
    }
    return out;
  }

  // Match an entry against the current search query. Searches across the
  // visible columns (tool, agent, model, mode). Empty query matches all.
  function matchesSearch(e, q) {
    if (!q) return true;
    const hay = [
      e.tool || "",
      e.agent || "",
      e.model || "",
      e.mode || "",
    ].join(" ").toLowerCase();
    return hay.indexOf(q) !== -1;
  }

  function aggregate(entries) {
    // Date-range cutoff is driven by state.range; the chart bucket axis
    // still uses WINDOW_DAYS so the "calls over time" view stays readable
    // when the user picks a smaller range.
    const rangeMs = RANGE_MS[state.range];
    const cutoff = rangeMs == null ? -Infinity : Date.now() - rangeMs;
    const q = state.search;
    const inWindow = [];
    for (const e of entries) {
      const d = e._d || parseTs(e.ts);
      if (!d) continue;
      if (d.getTime() < cutoff) continue;
      if (!matchesSearch(e, q)) continue;
      inWindow.push(e._d ? e : { ...e, _d: d });
    }

    // Hourly buckets across the window.
    const HOURS = WINDOW_DAYS * 24;
    const now = new Date();
    const bucketStart = new Date(
      now.getFullYear(), now.getMonth(), now.getDate(), now.getHours(), 0, 0, 0
    ).getTime() - (HOURS - 1) * 3600 * 1000;
    const bucketCounts = new Array(HOURS).fill(0);
    const bucketTokens = new Array(HOURS).fill(0);

    // Tokens by model (input/output).
    const byModel = { haiku: { input: 0, output: 0 }, sonnet: { input: 0, output: 0 }, opus: { input: 0, output: 0 }, other: { input: 0, output: 0 } };
    // Top labels (tool || agent) by call count.
    const topMap = new Map();
    // Top tools by total tokens consumed (used for the "top contributor" pill).
    const tokensByTool = new Map();
    // Per-agent rollup.
    const agentMap = new Map();
    // Mode counts. Fallback is a separate bucket because backend tags it
    // independently of live/mock when a Claude call falls back to a template.
    let liveCalls = 0;
    let mockCalls = 0;
    let fallbackCalls = 0;
    // Totals.
    let totalCalls = 0;
    let totalInput = 0;
    let totalOutput = 0;
    // Tokens this week (always 7d, ignores the range filter so the pill is stable).
    const weekCutoff = Date.now() - 7 * 24 * 3600 * 1000;
    let tokensThisWeek = 0;

    for (const e of inWindow) {
      totalCalls += 1;
      const inp = Number(e.input_tokens) || 0;
      const out = Number(e.output_tokens) || 0;
      totalInput += inp;
      totalOutput += out;

      const idx = Math.floor((e._d.getTime() - bucketStart) / (3600 * 1000));
      if (idx >= 0 && idx < HOURS) {
        bucketCounts[idx] += 1;
        bucketTokens[idx] += inp + out;
      }

      const fam = modelFamily(e.model);
      byModel[fam].input += inp;
      byModel[fam].output += out;

      const lbl = entryLabel(e);
      topMap.set(lbl, (topMap.get(lbl) || 0) + 1);

      // Track tokens-per-tool so we can surface the top contributor.
      const toolKey = e.tool || e.agent || "unknown";
      tokensByTool.set(toolKey, (tokensByTool.get(toolKey) || 0) + inp + out);

      const ag = e.agent || "unknown";
      let row = agentMap.get(ag);
      if (!row) {
        row = { agent: ag, calls: 0, total: 0, lastSeen: null };
        agentMap.set(ag, row);
      }
      row.calls += 1;
      row.total += inp + out;
      if (!row.lastSeen || e._d > row.lastSeen) row.lastSeen = e._d;

      const mode = (e.mode || "").toLowerCase();
      if (mode === "live") liveCalls += 1;
      else if (mode === "mock") mockCalls += 1;
      else if (mode === "fallback") fallbackCalls += 1;
    }

    // Tokens this week (independent of range filter for stable pill display).
    for (const e of entries) {
      const d = e._d || parseTs(e.ts);
      if (!d || d.getTime() < weekCutoff) continue;
      tokensThisWeek += (Number(e.input_tokens) || 0) + (Number(e.output_tokens) || 0);
    }

    const top = Array.from(topMap.entries())
      .map(([label, count]) => ({ label, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 10);

    const rollup = Array.from(agentMap.values())
      .map((r) => ({
        agent: r.agent,
        calls: r.calls,
        total: r.total,
        avg: r.calls ? Math.round(r.total / r.calls) : 0,
        lastSeen: r.lastSeen,
      }))
      .sort((a, b) => b.calls - a.calls);

    // Hand the full filtered window to the renderer so the user can sort and
    // browse, not just see the 10 most recent. The renderer caps the DOM size.
    const recent = inWindow.slice();

    const totalTokens = totalInput + totalOutput;
    const modeKnown = liveCalls + mockCalls + fallbackCalls;
    // mockPct retains the original semantics (mock vs known modes) for the
    // existing KPI card; the new pill row reports fallback rate separately.
    const mockPct = modeKnown ? mockCalls / modeKnown : 0;
    const fallbackPct = modeKnown ? fallbackCalls / modeKnown : 0;

    // Top contributor by tokens (used for the new pill).
    let topByTokens = null;
    for (const [tool, toks] of tokensByTool.entries()) {
      if (!topByTokens || toks > topByTokens.tokens) {
        topByTokens = { tool, tokens: toks };
      }
    }

    return {
      totals: { calls: totalCalls, input: totalInput, output: totalOutput, tokens: totalTokens, tokensThisWeek },
      modes: { live: liveCalls, mock: mockCalls, fallback: fallbackCalls, known: modeKnown, mockPct, fallbackPct },
      buckets: { start: bucketStart, hours: HOURS, counts: bucketCounts, tokens: bucketTokens },
      byModel,
      top,
      topByTokens,
      rollup,
      recent,
      windowEntries: inWindow.length,
    };
  }

  // ------------------------------------------------------------------
  // SVG helpers
  // ------------------------------------------------------------------
  const SVG_NS = "http://www.w3.org/2000/svg";
  function svgEl(tag, attrs) {
    const el = document.createElementNS(SVG_NS, tag);
    if (attrs) {
      for (const k in attrs) {
        if (attrs[k] === null || attrs[k] === undefined) continue;
        el.setAttribute(k, String(attrs[k]));
      }
    }
    return el;
  }
  function clearSvg(svg) {
    while (svg.firstChild) svg.removeChild(svg.firstChild);
  }
  function emptySvg(svg, w, h, msg) {
    clearSvg(svg);
    const t = svgEl("text", { x: w / 2, y: h / 2, class: "empty-text" });
    t.textContent = msg || "No data yet";
    svg.appendChild(t);
  }

  // ------------------------------------------------------------------
  // Chart 1: Calls over time (smooth area + line)
  // ------------------------------------------------------------------
  function renderCallsChart(svg, agg) {
    const W = 720, H = 220;
    const PAD = { top: 14, right: 14, bottom: 28, left: 40 };
    clearSvg(svg);

    const counts = agg.buckets.counts;
    const total = counts.reduce((a, b) => a + b, 0);
    if (!counts.length || total === 0) {
      emptySvg(svg, W, H, "No calls in the last 7d");
      return;
    }

    // Defs (gradients for area + stroke).
    const defs = svgEl("defs");
    const areaGrad = svgEl("linearGradient", { id: "line-area-grad", x1: 0, y1: 0, x2: 0, y2: 1 });
    areaGrad.appendChild(svgEl("stop", { offset: "0%", "stop-color": "#0077CC", "stop-opacity": "0.45" }));
    areaGrad.appendChild(svgEl("stop", { offset: "100%", "stop-color": "#0077CC", "stop-opacity": "0" }));
    defs.appendChild(areaGrad);
    const strokeGrad = svgEl("linearGradient", { id: "line-stroke-grad", x1: 0, y1: 0, x2: 1, y2: 0 });
    strokeGrad.appendChild(svgEl("stop", { offset: "0%", "stop-color": "#00BFB3" }));
    strokeGrad.appendChild(svgEl("stop", { offset: "100%", "stop-color": "#0077CC" }));
    defs.appendChild(strokeGrad);
    svg.appendChild(defs);

    const innerW = W - PAD.left - PAD.right;
    const innerH = H - PAD.top - PAD.bottom;
    const max = Math.max(...counts, 1);
    // Round y-axis up to a clean number.
    const yMax = niceCeil(max);

    // Y grid + labels (4 lines).
    const yTicks = 4;
    for (let i = 0; i <= yTicks; i++) {
      const y = PAD.top + (innerH * i) / yTicks;
      const v = Math.round(yMax - (yMax * i) / yTicks);
      svg.appendChild(svgEl("line", { class: "grid-line", x1: PAD.left, y1: y, x2: PAD.left + innerW, y2: y }));
      const t = svgEl("text", { class: "axis-text y", x: PAD.left - 6, y: y + 3 });
      t.textContent = String(v);
      svg.appendChild(t);
    }

    // X axis (day labels).
    const start = agg.buckets.start;
    const HOURS = agg.buckets.hours;
    for (let day = 0; day <= WINDOW_DAYS; day++) {
      const t = new Date(start + day * 24 * 3600 * 1000);
      const xPos = PAD.left + (innerW * (day * 24)) / HOURS;
      const lbl = (day === WINDOW_DAYS) ? "now" : `${t.getMonth() + 1}/${t.getDate()}`;
      const tx = svgEl("text", { class: "axis-text", x: xPos, y: H - 8, "text-anchor": "middle" });
      tx.textContent = lbl;
      svg.appendChild(tx);
    }

    // Build line path.
    const points = counts.map((c, i) => {
      const x = PAD.left + (innerW * i) / Math.max(HOURS - 1, 1);
      const y = PAD.top + innerH - (innerH * c) / yMax;
      return [x, y];
    });
    // Smoothed path with cardinal-ish curves (cheap monotone Bezier).
    const linePath = smoothPath(points);
    const areaPath = `${linePath} L ${points[points.length - 1][0]} ${PAD.top + innerH} L ${points[0][0]} ${PAD.top + innerH} Z`;

    svg.appendChild(svgEl("path", { class: "line-area", d: areaPath }));
    svg.appendChild(svgEl("path", { class: "line-stroke", d: linePath }));
    // Mark the latest point.
    const last = points[points.length - 1];
    svg.appendChild(svgEl("circle", { class: "line-dot", cx: last[0], cy: last[1], r: 3.5 }));

    // Update the off-screen text alternative.
    const alt = document.getElementById("chart-calls-alt");
    if (alt) {
      alt.textContent = `Calls per hour over the last ${WINDOW_DAYS} days. Peak ${max} calls per hour. ${total} calls total.`;
    }
  }

  function smoothPath(pts) {
    if (!pts.length) return "";
    if (pts.length === 1) return `M ${pts[0][0]} ${pts[0][1]}`;
    let d = `M ${pts[0][0]} ${pts[0][1]}`;
    for (let i = 1; i < pts.length; i++) {
      const [x0, y0] = pts[i - 1];
      const [x1, y1] = pts[i];
      const cx0 = x0 + (x1 - x0) / 2;
      const cy0 = y0;
      const cx1 = x0 + (x1 - x0) / 2;
      const cy1 = y1;
      d += ` C ${cx0} ${cy0}, ${cx1} ${cy1}, ${x1} ${y1}`;
    }
    return d;
  }

  function niceCeil(n) {
    if (n <= 1) return 1;
    const pow = Math.pow(10, Math.floor(Math.log10(n)));
    const norm = n / pow;
    let nice;
    if (norm <= 1) nice = 1;
    else if (norm <= 2) nice = 2;
    else if (norm <= 5) nice = 5;
    else nice = 10;
    return nice * pow;
  }

  // ------------------------------------------------------------------
  // Chart 2: Tokens by model (stacked bar input + output)
  // ------------------------------------------------------------------
  function renderModelsChart(svg, agg) {
    const W = 720, H = 220;
    const PAD = { top: 14, right: 16, bottom: 36, left: 56 };
    clearSvg(svg);

    const order = ["haiku", "sonnet", "opus", "other"];
    const data = order
      .map((k) => ({
        key: k,
        input: agg.byModel[k].input,
        output: agg.byModel[k].output,
        total: agg.byModel[k].input + agg.byModel[k].output,
      }))
      .filter((r) => r.total > 0);

    const legend = document.getElementById("legend-models");
    if (legend) {
      legend.innerHTML =
        '<span><span class="swatch haiku"></span>Haiku</span>' +
        '<span><span class="swatch sonnet"></span>Sonnet</span>' +
        '<span><span class="swatch opus"></span>Opus</span>' +
        '<span><span class="swatch input"></span>input (lighter) / output (solid)</span>';
    }

    if (!data.length) {
      emptySvg(svg, W, H, "No model usage yet");
      return;
    }

    const innerW = W - PAD.left - PAD.right;
    const innerH = H - PAD.top - PAD.bottom;
    const max = Math.max(...data.map((d) => d.total), 1);
    const yMax = niceCeil(max);
    const yTicks = 4;
    for (let i = 0; i <= yTicks; i++) {
      const y = PAD.top + (innerH * i) / yTicks;
      const v = Math.round(yMax - (yMax * i) / yTicks);
      svg.appendChild(svgEl("line", { class: "grid-line", x1: PAD.left, y1: y, x2: PAD.left + innerW, y2: y }));
      const t = svgEl("text", { class: "axis-text y", x: PAD.left - 6, y: y + 3 });
      t.textContent = fmtCompact(v);
      svg.appendChild(t);
    }

    const slot = innerW / data.length;
    const barW = Math.min(78, slot * 0.55);
    let altParts = [];
    data.forEach((row, i) => {
      const cx = PAD.left + slot * (i + 0.5);
      const x = cx - barW / 2;
      const totalH = (innerH * row.total) / yMax;
      const inputH = (innerH * row.input) / yMax;
      const outputH = totalH - inputH;
      const yTop = PAD.top + innerH - totalH;

      // Output (solid, on top).
      svg.appendChild(svgEl("rect", {
        class: `bar-${row.key} bar-output`,
        x: x, y: yTop, width: barW, height: Math.max(outputH, 0), rx: 2,
      }));
      // Input (lighter, below the output).
      svg.appendChild(svgEl("rect", {
        class: `bar-${row.key} bar-input`,
        x: x, y: yTop + outputH, width: barW, height: Math.max(inputH, 0), rx: 2,
      }));

      // Total label above bar.
      const lbl = svgEl("text", { class: "axis-text", x: cx, y: yTop - 4, "text-anchor": "middle" });
      lbl.textContent = fmtCompact(row.total);
      lbl.style.fill = "var(--ink-soft)";
      svg.appendChild(lbl);

      // X label below.
      const tx = svgEl("text", { class: "axis-text", x: cx, y: H - 18, "text-anchor": "middle" });
      tx.textContent = capitalize(row.key);
      svg.appendChild(tx);
      const tx2 = svgEl("text", { class: "axis-text", x: cx, y: H - 6, "text-anchor": "middle" });
      tx2.textContent = `in ${fmtCompact(row.input)} / out ${fmtCompact(row.output)}`;
      tx2.style.fontSize = "9px";
      svg.appendChild(tx2);

      altParts.push(`${capitalize(row.key)}: ${row.total} tokens (${row.input} input, ${row.output} output).`);
    });

    const alt = document.getElementById("chart-models-alt");
    if (alt) alt.textContent = `Tokens by model. ${altParts.join(" ")}`;
  }

  function capitalize(s) {
    if (!s) return "";
    return s.charAt(0).toUpperCase() + s.slice(1);
  }

  // ------------------------------------------------------------------
  // Chart 3: Top 10 agents/tools (horizontal bars)
  // ------------------------------------------------------------------
  function renderTopChart(svg, agg) {
    const W = 720, H = 320;
    const PAD = { top: 12, right: 56, bottom: 12, left: 180 };
    clearSvg(svg);

    const data = agg.top || [];
    if (!data.length) {
      emptySvg(svg, W, H, "No tool calls yet");
      return;
    }

    // Defs.
    const defs = svgEl("defs");
    const grad = svgEl("linearGradient", { id: "top-bar-grad", x1: 0, y1: 0, x2: 1, y2: 0 });
    grad.appendChild(svgEl("stop", { offset: "0%", "stop-color": "#0077CC" }));
    grad.appendChild(svgEl("stop", { offset: "100%", "stop-color": "#F04E98" }));
    defs.appendChild(grad);
    svg.appendChild(defs);

    const innerW = W - PAD.left - PAD.right;
    const innerH = H - PAD.top - PAD.bottom;
    const rowH = innerH / data.length;
    const barH = Math.min(rowH * 0.62, 22);
    const max = data[0].count || 1;

    data.forEach((d, i) => {
      const yMid = PAD.top + rowH * i + rowH / 2;
      const yTop = yMid - barH / 2;
      const w = (innerW * d.count) / max;
      // Background track.
      svg.appendChild(svgEl("rect", {
        x: PAD.left, y: yTop, width: innerW, height: barH, rx: 4,
        fill: "rgba(255,255,255,0.04)",
      }));
      svg.appendChild(svgEl("rect", {
        class: "top-bar",
        x: PAD.left, y: yTop, width: Math.max(w, 1), height: barH, rx: 4,
      }));
      const lbl = svgEl("text", {
        class: "top-label",
        x: PAD.left - 10, y: yMid + 4, "text-anchor": "end",
      });
      lbl.textContent = truncate(d.label, 26);
      svg.appendChild(lbl);
      const val = svgEl("text", {
        class: "top-value",
        x: W - 12, y: yMid + 4,
      });
      val.textContent = fmtInt(d.count);
      svg.appendChild(val);
    });

    const alt = document.getElementById("chart-top-alt");
    if (alt) {
      alt.textContent = "Top agents and tools by call count: " +
        data.map((d) => `${d.label} ${d.count}`).join(", ") + ".";
    }
  }
  function truncate(s, n) {
    if (!s) return "";
    return s.length > n ? s.slice(0, n - 1) + "..." : s;
  }

  // ------------------------------------------------------------------
  // Rollup table
  // ------------------------------------------------------------------
  // Generic comparator factory for table sort. Handles string/number/Date
  // and keeps a stable secondary sort by agent name when the primary keys tie.
  function compareBy(key, dir) {
    const m = dir === "asc" ? 1 : -1;
    return (a, b) => {
      const av = a[key];
      const bv = b[key];
      if (av instanceof Date || bv instanceof Date) {
        return ((av ? av.getTime() : 0) - (bv ? bv.getTime() : 0)) * m;
      }
      if (typeof av === "number" || typeof bv === "number") {
        return ((Number(av) || 0) - (Number(bv) || 0)) * m;
      }
      return String(av || "").localeCompare(String(bv || "")) * m;
    };
  }

  function applyHeaderSortState(tableId, sort) {
    const table = document.getElementById(tableId);
    if (!table) return;
    const ths = table.querySelectorAll(".audit-th-sort");
    ths.forEach((th) => {
      const k = th.getAttribute("data-sort");
      if (k === sort.key) {
        th.setAttribute("aria-sort", sort.dir === "asc" ? "ascending" : "descending");
        th.classList.add("is-sorted");
        th.classList.toggle("is-asc", sort.dir === "asc");
        th.classList.toggle("is-desc", sort.dir === "desc");
      } else {
        th.setAttribute("aria-sort", "none");
        th.classList.remove("is-sorted", "is-asc", "is-desc");
      }
    });
  }

  function renderRollup(agg) {
    const tbody = document.getElementById("audit-rollup-body");
    if (!tbody) return;
    applyHeaderSortState("audit-rollup", state.rollupSort);
    if (!agg.rollup.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="audit-empty">No agent activity in the current window.</td></tr>';
      return;
    }
    const sorted = agg.rollup.slice().sort(compareBy(state.rollupSort.key, state.rollupSort.dir));
    const rows = sorted.map((r) => {
      const initials = (r.agent || "?").split(/[_\s-]/).map((p) => p[0] || "").join("").slice(0, 2).toUpperCase() || "?";
      const last = r.lastSeen ? `${fmtRelative(r.lastSeen)}` : "-";
      const lastTitle = r.lastSeen ? fmtTime(r.lastSeen) : "";
      return `
        <tr>
          <td>
            <span class="agent-cell">
              <span class="agent-glyph" aria-hidden="true">${escapeHtml(initials)}</span>
              <span>${escapeHtml(r.agent || "unknown")}</span>
            </span>
          </td>
          <td class="num">${fmtInt(r.calls)}</td>
          <td class="num">${fmtInt(r.avg)}</td>
          <td class="num">${fmtInt(r.total)}</td>
          <td title="${escapeHtml(lastTitle)}">${escapeHtml(last)}</td>
        </tr>
      `;
    });
    tbody.innerHTML = rows.join("");
  }

  // ------------------------------------------------------------------
  // Recent fires (sortable table)
  // ------------------------------------------------------------------
  // Project a raw entry to a flat shape the comparator can act on.
  function recentRow(e) {
    const inp = Number(e.input_tokens) || 0;
    const out = Number(e.output_tokens) || 0;
    return {
      ts: e._d,
      agent: e.agent || "unknown",
      tool: e.tool || "",
      model: e.model || "",
      mode: (e.mode || "").toLowerCase(),
      tokens: inp + out,
      input: inp,
      output: out,
    };
  }

  function renderRecent(agg) {
    const tbody = document.getElementById("audit-recent-body");
    const meta = document.getElementById("audit-recent-meta");
    if (!tbody) return;
    applyHeaderSortState("audit-recent-table", state.recentSort);
    // We render the full set of in-window entries (filtered) so the user
    // can sort and browse, not just the 10 most recent. Cap the projection
    // at 200 rows below to keep the DOM light.
    const source = (agg && Array.isArray(agg.recent)) ? agg.recent : [];
    const allRows = source.map(recentRow);
    const sorted = allRows.slice().sort(compareBy(state.recentSort.key, state.recentSort.dir));
    const view = sorted.slice(0, 200);
    if (meta) {
      meta.textContent = `${fmtInt(allRows.length)} events in window, showing ${fmtInt(view.length)} (click any header to sort)`;
    }
    if (!view.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="audit-empty">No fires match the current filter.</td></tr>';
      return;
    }
    const rows = view.map((r) => {
      const ts = fmtTime(r.ts);
      const rel = fmtRelative(r.ts);
      const tool = r.tool ? `<span class="tool">${escapeHtml(r.tool)}</span>` : '<span class="muted">-</span>';
      const modeBadge = r.mode ? `<span class="mode ${escapeAttr(r.mode)}">${escapeHtml(r.mode)}</span>` : '<span class="muted">-</span>';
      const model = r.model ? `<span class="muted small">${escapeHtml(r.model)}</span>` : '<span class="muted">-</span>';
      return `
        <tr>
          <td class="audit-ts" title="${escapeAttr(ts)}">${escapeHtml(rel)}</td>
          <td><span class="agent">${escapeHtml(r.agent)}</span></td>
          <td>${tool}</td>
          <td>${model}</td>
          <td>${modeBadge}</td>
          <td class="num" title="${fmtInt(r.input)} in / ${fmtInt(r.output)} out">${fmtInt(r.tokens)}</td>
        </tr>
      `;
    });
    tbody.innerHTML = rows.join("");
  }

  // ------------------------------------------------------------------
  // KPIs + pill row
  // ------------------------------------------------------------------
  function rangeLabel() {
    switch (state.range) {
      case "1h": return "last hour";
      case "24h": return "last 24h";
      case "7d": return "last 7d";
      case "all": return "all time";
      default: return "window";
    }
  }

  function renderKpis(agg) {
    const t = agg.totals;
    const lbl = rangeLabel();
    setText("kpi-calls", fmtInt(t.calls));
    setText("kpi-calls-sub", `across all agents (${lbl})`);
    setText("kpi-tokens", fmtCompact(t.tokens));
    setText("kpi-tokens-sub", `${fmtInt(t.input)} in / ${fmtInt(t.output)} out`);
    setText("kpi-mock", agg.modes.known ? fmtPct(agg.modes.mock, agg.modes.known) : "0%");
    setText("kpi-mock-sub", agg.modes.known
      ? `${fmtInt(agg.modes.live)} live / ${fmtInt(agg.modes.mock)} mock / ${fmtInt(agg.modes.fallback)} fallback`
      : "no mode tag on entries");

    const status = document.getElementById("audit-pill-status");
    if (status) {
      status.innerHTML = '<span class="audit-dot live" aria-hidden="true"></span><span>Live</span>';
    }
    setText("audit-pill-calls", `${fmtInt(t.calls)} calls ${lbl}`);
    // Tokens-this-week pill always reads the 7d total so the figure does not
    // jump when the user switches the range filter to "Last hour".
    setText("audit-pill-tokens", `${fmtCompact(t.tokensThisWeek)} tokens last 7d`);
    setText("audit-pill-mock", agg.modes.known ? `${fmtPct(agg.modes.mock, agg.modes.known)} mock` : "0% mock");
    // Fallback rate pill: "X / Y calls fell back".
    setText("audit-pill-fallback", agg.modes.known
      ? `${fmtInt(agg.modes.fallback)} / ${fmtInt(agg.modes.known)} calls fell back`
      : "0 fallbacks");
    // Top contributor tool pill: which tool burned the most tokens.
    const top = agg.topByTokens;
    setText("audit-pill-top", top
      ? `top: ${top.tool} (${fmtCompact(top.tokens)} tok)`
      : "top: -");

    // Visible result count for the controls strip.
    setText("audit-result-count", `${fmtInt(t.calls)} of ${fmtInt(state.rawEntries.length)} entries`);
  }
  function renderError(err) {
    const status = document.getElementById("audit-pill-status");
    if (status) {
      status.innerHTML = '<span class="audit-dot error" aria-hidden="true"></span><span>Audit feed unavailable</span>';
    }
    setText("audit-pill-calls", "- calls");
    setText("audit-pill-tokens", "- tokens last 7d");
    setText("audit-pill-mock", "- % mock");
    setText("audit-pill-fallback", "- fallbacks");
    setText("audit-pill-top", "- top tool");
    const tbody = document.getElementById("audit-rollup-body");
    if (tbody) {
      const safe = (typeof sanitizeError === "function") ? sanitizeError(err) : String(err && err.message || err || "error");
      tbody.innerHTML = `<tr><td colspan="5" class="audit-empty">Could not load audit feed (${escapeHtml(safe)}).</td></tr>`;
    }
    const recentBody = document.getElementById("audit-recent-body");
    if (recentBody) {
      recentBody.innerHTML = '<tr><td colspan="6" class="audit-empty">Audit feed unreachable. Will retry shortly.</td></tr>';
    }
    setText("kpi-calls", "0");
    setText("kpi-tokens", "0");
    setText("kpi-mock", "0%");
    setText("audit-result-count", "0 of 0 entries");
  }

  // ------------------------------------------------------------------
  // DOM helpers
  // ------------------------------------------------------------------
  function setText(id, txt) {
    const el = document.getElementById(id);
    if (el) el.textContent = txt;
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

  // ------------------------------------------------------------------
  // Orchestration
  // ------------------------------------------------------------------
  let refreshTimer = null;

  // Pure render: aggregates state.rawEntries against the current filters and
  // paints every panel. Cheap enough to call on every keystroke (debounced).
  function rerender() {
    if (!state.rawEntries.length) return;
    const agg = aggregate(state.rawEntries);
    state.lastFiltered = agg.recent;

    renderKpis(agg);

    const callsSvg = document.getElementById("chart-calls");
    const modelsSvg = document.getElementById("chart-models");
    const topSvg = document.getElementById("chart-top");
    if (callsSvg) renderCallsChart(callsSvg, agg);
    if (modelsSvg) renderModelsChart(modelsSvg, agg);
    if (topSvg) renderTopChart(topSvg, agg);

    renderRollup(agg);
    renderRecent(agg);
  }

  async function load({ force = false, silent = false } = {}) {
    try {
      const data = await fetchAudit({ force });
      const entries = (data && Array.isArray(data.entries)) ? data.entries : [];
      state.rawEntries = decorateEntries(entries);
      rerender();
    } catch (err) {
      // On silent refresh, only log; on first load, render the error state.
      if (!silent) renderError(err);
      // eslint-disable-next-line no-console
      console.warn("[audit] load failed", err);
    }
  }

  function startAutoRefresh() {
    stopAutoRefresh();
    refreshTimer = setInterval(() => {
      if (document.hidden) return;
      load({ force: true, silent: true });
    }, REFRESH_MS);
  }
  function stopAutoRefresh() {
    if (refreshTimer) {
      clearInterval(refreshTimer);
      refreshTimer = null;
    }
  }

  // Rewrite the "Open in Kibana" pill href against the live Kibana base URL
  // returned by /api/v1/health. Without this, the static href "/app/dashboards#..."
  // resolves against the FE Copilot origin (localhost:8123) and 404s.
  // If Kibana is unreachable, the pill is hidden so we never link to nowhere.
  async function fixKibanaLink() {
    const a = document.getElementById("audit-pill-kibana");
    if (!a) return;
    try {
      const r = await fetch("/api/v1/health", { cache: "no-store" });
      if (!r.ok) throw new Error("health " + r.status);
      const j = await r.json();
      const base = j && j.kibana && j.kibana.url ? String(j.kibana.url).replace(/\/+$/, "") : "";
      if (base) {
        a.href = base + "/app/dashboards#/view/fec-audit-self-observability";
        a.hidden = false;
      } else {
        a.hidden = true;
      }
    } catch (_e) {
      a.hidden = true;
    }
  }

  // Lightweight debounce so the search box re-renders at most every 150 ms
  // while the user types. We render off the in-memory raw entries, no refetch.
  function debounce(fn, ms) {
    let t = null;
    return function debounced(...args) {
      if (t) clearTimeout(t);
      t = setTimeout(() => { t = null; fn.apply(this, args); }, ms);
    };
  }

  function bindControls() {
    // Search input.
    const search = document.getElementById("audit-search");
    if (search) {
      const onSearch = debounce(() => {
        state.search = String(search.value || "").trim().toLowerCase();
        rerender();
      }, SEARCH_DEBOUNCE_MS);
      search.addEventListener("input", onSearch);
      // Allow keyboard "Escape" to clear the filter quickly.
      search.addEventListener("keydown", (ev) => {
        if (ev.key === "Escape" && search.value) {
          search.value = "";
          state.search = "";
          rerender();
        }
      });
    }

    // Date range buttons.
    const rangeWrap = document.getElementById("audit-range");
    if (rangeWrap) {
      rangeWrap.addEventListener("click", (ev) => {
        const btn = ev.target.closest(".audit-range-btn");
        if (!btn) return;
        const r = btn.getAttribute("data-range");
        if (!r || !(r in RANGE_MS)) return;
        state.range = r;
        rangeWrap.querySelectorAll(".audit-range-btn").forEach((b) => {
          b.classList.toggle("is-active", b === btn);
          b.setAttribute("aria-pressed", b === btn ? "true" : "false");
        });
        rerender();
      });
      // Initialize aria-pressed.
      rangeWrap.querySelectorAll(".audit-range-btn").forEach((b) => {
        b.setAttribute("aria-pressed", b.classList.contains("is-active") ? "true" : "false");
      });
    }

    // Sortable table headers. The two tables share one delegated handler.
    function bindSort(tableId, sortState) {
      const table = document.getElementById(tableId);
      if (!table) return;
      table.addEventListener("click", (ev) => {
        const btn = ev.target.closest(".audit-sort-btn");
        if (!btn) return;
        const th = btn.closest(".audit-th-sort");
        if (!th) return;
        const key = th.getAttribute("data-sort");
        if (!key) return;
        // Toggle direction if same column; default to descending on first click
        // for numeric / timestamp columns and ascending for textual ones.
        if (sortState.key === key) {
          sortState.dir = sortState.dir === "asc" ? "desc" : "asc";
        } else {
          sortState.key = key;
          sortState.dir = (key === "agent" || key === "tool" || key === "model" || key === "mode") ? "asc" : "desc";
        }
        rerender();
      });
    }
    bindSort("audit-rollup", state.rollupSort);
    bindSort("audit-recent-table", state.recentSort);
  }

  function init() {
    bindControls();
    fixKibanaLink();
    load({ force: false, silent: false });
    startAutoRefresh();
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) load({ force: true, silent: true });
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
