/*
  filename: command-palette.js
  description: Global Cmd+K / Ctrl+K command palette. Fuzzy-searches pages, tools,
               demo scenarios, recent meetings, and quick actions. Vanilla JS, no deps.
  Author: Rodrigo Careaga
  Date: 03-05-2026
*/
(function () {
  "use strict";
  if (window.__feCommandPaletteLoaded) return;
  window.__feCommandPaletteLoaded = true;

  /* ============================================================ Static index */
  var STATIC_COMMANDS = [
    // Pages (8)
    { type: "pages", icon: "🏠", label: "Dashboard",       sub: "/index.html",         href: "/index.html",         keywords: "home overview" },
    { type: "pages", icon: "🛠",  label: "Tools",           sub: "/tools.html",         href: "/tools.html",         keywords: "panels generators" },
    { type: "pages", icon: "🤖", label: "Agent Builder",   sub: "/agent-builder.html", href: "/agent-builder.html", keywords: "agents prompts" },
    { type: "pages", icon: "🧪", label: "Demo Data",       sub: "/demo-data.html",     href: "/demo-data.html",     keywords: "scenarios seed" },
    { type: "pages", icon: "🌊", label: "Workflow",        sub: "/workflow-demo.html", href: "/workflow-demo.html", keywords: "pipeline demo" },
    { type: "pages", icon: "🧠", label: "FE Brain",        sub: "/fe-brain.html",      href: "/fe-brain.html",      keywords: "knowledge docs rag" },
    { type: "pages", icon: "⚔",  label: "Battlecards",     sub: "/battlecards.html",   href: "/battlecards.html",   keywords: "competitive splunk" },
    { type: "pages", icon: "📜", label: "Audit",           sub: "/audit.html",         href: "/audit.html",         keywords: "log compliance" },

    // Tools (10)
    { type: "tools", icon: "📋", label: "POC Plan",                sub: "/tools.html#tool-poc",          href: "/tools.html#tool-poc",          keywords: "proof concept" },
    { type: "tools", icon: "🔁", label: "SPL to ES|QL",            sub: "/tools.html#tool-spl",          href: "/tools.html#tool-spl",          keywords: "splunk migration query" },
    { type: "tools", icon: "✅", label: "Compliance",              sub: "/tools.html#tool-compliance",   href: "/tools.html#tool-compliance",   keywords: "fca soc2 hipaa gdpr pci" },
    { type: "tools", icon: "💰", label: "Cost",                    sub: "/tools.html#tool-cost",         href: "/tools.html#tool-cost",         keywords: "tco pricing" },
    { type: "tools", icon: "📈", label: "Capacity",                sub: "/tools.html#tool-capacity",     href: "/tools.html#tool-capacity",     keywords: "cluster sizing nodes" },
    { type: "tools", icon: "📚", label: "Stack",                   sub: "/tools.html#tool-stack",        href: "/tools.html#tool-stack",        keywords: "tech extract" },
    { type: "tools", icon: "💻", label: "Code",                    sub: "/tools.html#tool-code",         href: "/tools.html#tool-code",         keywords: "samples snippets" },
    { type: "tools", icon: "🩺", label: "Troubleshoot",            sub: "/tools.html#tool-troubleshoot", href: "/tools.html#tool-troubleshoot", keywords: "diagnose error" },
    { type: "tools", icon: "🧠", label: "Knowledge (FE Brain)",    sub: "/fe-brain.html",                href: "/fe-brain.html",                keywords: "docs rag search" },
    { type: "tools", icon: "🎼", label: "Orchestrator",            sub: "/agent-builder.html",           href: "/agent-builder.html",           keywords: "router multi agent" },

    // Quick actions (4)
    { type: "actions", icon: "🚦", label: "Run smoke test",         sub: "Open runtime/integration_smoke output", action: "smoke",         keywords: "test integration runtime" },
    { type: "actions", icon: "🔄", label: "Re-sync Agent Builder",  sub: "POST /agent-builder/sync",              action: "ab-sync",       keywords: "agents reload refresh" },
    { type: "actions", icon: "🟦", label: "Open Kibana",            sub: "Open Kibana home in a new tab",         action: "kibana",        keywords: "elastic dashboards" },
    { type: "actions", icon: "⌨",  label: "Show keyboard shortcuts", sub: "View all keyboard hints",              action: "shortcuts",     keywords: "help hotkeys keys" }
  ];

  /* ============================================================ Constants */
  var CACHE_TTL_MS = 60 * 1000;
  var SECTION_ORDER = ["pages", "tools", "scenarios", "meetings", "actions"];
  var SECTION_TITLES = {
    pages:     "Pages",
    tools:     "Tools",
    scenarios: "Demo Scenarios",
    meetings:  "Recent Meetings",
    actions:   "Quick Actions"
  };

  /* ============================================================ State */
  var state = {
    open: false,
    query: "",
    selected: 0,
    flatResults: [],
    cache: { at: 0, scenarios: [], meetings: [] },
    fetchPromise: null,
    triggerEl: null,
    nodes: null
  };

  /* ============================================================ Utilities */
  function escapeHTML(s) {
    return String(s || "").replace(/[&<>"']/g, function (c) {
      return ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c];
    });
  }
  function el(tag, attrs, kids) {
    var n = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        if (k === "class") n.className = attrs[k];
        else if (k.indexOf("on") === 0 && typeof attrs[k] === "function") n.addEventListener(k.slice(2), attrs[k]);
        else if (attrs[k] != null) n.setAttribute(k, attrs[k]);
      });
    }
    (kids || []).forEach(function (c) {
      if (c == null) return;
      n.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    });
    return n;
  }
  function isTypingTarget(t) {
    if (!t) return false;
    if (t.isContentEditable) return true;
    var tag = (t.tagName || "").toLowerCase();
    if (tag === "input") {
      var type = (t.type || "text").toLowerCase();
      var typingTypes = ["text", "search", "email", "url", "password", "tel", "number"];
      return typingTypes.indexOf(type) !== -1;
    }
    return tag === "textarea" || tag === "select";
  }

  /* ============================================================ Fuzzy scoring */
  // exact > prefix > acronym > infix; ties broken by shorter labels.
  function score(item, q) {
    if (!q) return 1;
    var label = String(item.label || "").toLowerCase();
    var hay   = label + " " + String(item.sub || "").toLowerCase() + " " + String(item.keywords || "").toLowerCase();
    var query = q.toLowerCase().trim();
    if (!query) return 1;
    if (label === query) return 1000;
    if (label.indexOf(query) === 0) return 800 - label.length;
    var acr = label.split(/[^a-z0-9]+/).map(function (w) { return w[0] || ""; }).join("");
    if (acr && acr.indexOf(query) === 0) return 600 - label.length;
    if (label.indexOf(query) !== -1) return 400 - label.length;
    if (hay.indexOf(query) !== -1) return 200 - label.length;
    // multi-token AND match
    var toks = query.split(/\s+/).filter(Boolean);
    if (toks.length > 1 && toks.every(function (t) { return hay.indexOf(t) !== -1; })) return 100;
    return 0;
  }

  /* ============================================================ Data fetch */
  function getKibanaBase() {
    try {
      var meta = document.querySelector('meta[name="kibana-base"]');
      if (meta && meta.content) return meta.content.replace(/\/+$/, "");
    } catch (_) {}
    return "";
  }

  function fetchDynamic() {
    if (Date.now() - state.cache.at < CACHE_TTL_MS && (state.cache.scenarios.length || state.cache.meetings.length)) {
      return Promise.resolve();
    }
    if (state.fetchPromise) return state.fetchPromise;
    var safe = function (p) {
      return p.then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; });
    };
    state.fetchPromise = Promise.all([
      safe(fetch("/api/v1/demo-data/scenarios")),
      safe(fetch("/api/v1/meetings")),
      safe(fetch("/api/v1/briefs"))
    ]).then(function (out) {
      var scenariosRaw = (out[0] && (out[0].scenarios || out[0])) || [];
      var meetingsRaw  = out[1] || [];
      var briefsRaw    = (out[2] && (out[2].briefs || out[2])) || [];
      // scenarios
      state.cache.scenarios = (Array.isArray(scenariosRaw) ? scenariosRaw : []).slice(0, 5).map(function (s) {
        var dash = s.dashboard_url || s.dashboard_url_fe || "/demo-data.html#" + (s.id || "");
        return {
          type: "scenarios",
          icon: s.id === "credstuff" ? "🔐" : s.id === "ddos" ? "🌐" : s.id === "ransomware" ? "🛡" : "🧪",
          label: s.title || s.id || "Scenario",
          sub: s.id ? ("scenario: " + s.id) : "demo scenario",
          href: dash,
          keywords: (s.id || "") + " " + (s.description || "") + " " + ((s.indices || []).join(" "))
        };
      });
      // meetings: prefer /meetings, else recent briefs
      var rawMeetings = Array.isArray(meetingsRaw) ? meetingsRaw : [];
      if (!rawMeetings.length && Array.isArray(briefsRaw)) rawMeetings = briefsRaw;
      // sort: prefer most recent, exclude upcoming-only if mixed
      var sorted = rawMeetings.slice().sort(function (a, b) {
        var ad = Date.parse(a.starts_at || a.created_at || a.updated_at || a.date || 0) || 0;
        var bd = Date.parse(b.starts_at || b.created_at || b.updated_at || b.date || 0) || 0;
        return bd - ad;
      });
      state.cache.meetings = sorted.slice(0, 5).map(function (m) {
        var id = m.id || m.meeting_id || "";
        var company = m.company_name || m.company_id || m.account || "";
        var title = m.title || m.subject || "Meeting";
        var label = company ? (company + " - " + title) : title;
        return {
          type: "meetings",
          icon: "📞",
          label: label,
          sub: id ? ("/meeting.html?id=" + id) : "meeting",
          href: id ? ("/meeting.html?id=" + encodeURIComponent(id)) : "/meeting.html",
          keywords: (company + " " + title + " " + id).toLowerCase()
        };
      });
      state.cache.at = Date.now();
    }).catch(function () {
      // swallow; sections just stay empty
    }).then(function () {
      state.fetchPromise = null;
    });
    return state.fetchPromise;
  }

  /* ============================================================ Build / render */
  function getAllCommands() {
    return STATIC_COMMANDS.concat(state.cache.scenarios || []).concat(state.cache.meetings || []);
  }

  function computeResults() {
    var q = state.query.trim();
    var all = getAllCommands();
    var scored = all.map(function (it) { return { it: it, s: score(it, q) }; }).filter(function (x) { return x.s > 0; });
    if (!q) {
      // default ordering: keep section order, original order within section
      scored = all.map(function (it, i) { return { it: it, s: 1, i: i }; });
    }
    // group by section
    var groups = {};
    scored.forEach(function (x) {
      (groups[x.it.type] = groups[x.it.type] || []).push(x);
    });
    var ordered = [];
    SECTION_ORDER.forEach(function (sec) {
      var list = groups[sec] || [];
      list.sort(function (a, b) {
        if (b.s !== a.s) return b.s - a.s;
        return (a.i || 0) - (b.i || 0);
      });
      list.forEach(function (x) { ordered.push(x.it); });
    });
    return ordered;
  }

  function render() {
    var nodes = state.nodes;
    var list = nodes.results;
    list.innerHTML = "";
    var results = computeResults();
    state.flatResults = results;
    if (state.selected >= results.length) state.selected = Math.max(0, results.length - 1);

    // counter
    nodes.counter.textContent = results.length + (results.length === 1 ? " result" : " results");

    if (!results.length) {
      list.appendChild(el("div", { class: "cp-empty" }, [
        "No matches for ",
        el("strong", null, ["“" + (state.query || "") + "”"]),
        ".  Try \"compliance\", \"poc\", or a meeting."
      ]));
      return;
    }

    var lastSection = null;
    results.forEach(function (item, idx) {
      if (item.type !== lastSection) {
        list.appendChild(el("div", { class: "cp-section-title" }, [SECTION_TITLES[item.type] || item.type]));
        lastSection = item.type;
      }
      var row = el("div", {
        class: "cp-row" + (idx === state.selected ? " is-selected" : ""),
        role: "option",
        id: "cp-row-" + idx,
        "aria-selected": idx === state.selected ? "true" : "false",
        "data-idx": idx,
        tabindex: "-1"
      }, [
        el("span", { class: "cp-row-icon", "aria-hidden": "true" }, [String(item.icon || "")]),
        el("span", { class: "cp-row-text" }, [
          el("span", { class: "cp-row-label" }, [item.label || ""]),
          el("span", { class: "cp-row-sub" }, [item.sub || ""])
        ]),
        el("span", { class: "cp-tag cat-" + item.type }, [SECTION_TITLES[item.type] || item.type]),
        el("span", { class: "cp-row-arrow", "aria-hidden": "true" }, ["↵"])
      ]);
      row.addEventListener("mouseenter", function () { setSelected(idx, false); });
      row.addEventListener("click", function () { activate(idx); });
      list.appendChild(row);
    });

    // ensure selected visible
    var sel = list.querySelector(".cp-row.is-selected");
    if (sel && sel.scrollIntoView) sel.scrollIntoView({ block: "nearest" });
    nodes.input.setAttribute("aria-activedescendant", "cp-row-" + state.selected);
  }

  function setSelected(idx, scroll) {
    if (!state.flatResults.length) return;
    if (idx < 0) idx = state.flatResults.length - 1;
    if (idx >= state.flatResults.length) idx = 0;
    state.selected = idx;
    var rows = state.nodes.results.querySelectorAll(".cp-row");
    rows.forEach(function (r) {
      var i = parseInt(r.getAttribute("data-idx"), 10);
      var on = i === idx;
      r.classList.toggle("is-selected", on);
      r.setAttribute("aria-selected", on ? "true" : "false");
    });
    state.nodes.input.setAttribute("aria-activedescendant", "cp-row-" + idx);
    if (scroll !== false) {
      var sel = state.nodes.results.querySelector(".cp-row.is-selected");
      if (sel && sel.scrollIntoView) sel.scrollIntoView({ block: "nearest" });
    }
  }

  /* ============================================================ Activation */
  function activate(idx) {
    var item = state.flatResults[idx];
    if (!item) return;
    if (item.action) return runAction(item.action);
    var href = item.href;
    if (!href) return;
    close();
    if (/^https?:/i.test(href) || (item.target && item.target === "_blank")) {
      window.open(href, "_blank", "noopener");
    } else {
      window.location.href = href;
    }
  }

  function runAction(action) {
    if (action === "smoke") {
      close();
      window.open("/runtime/integration_smoke", "_blank", "noopener");
    } else if (action === "ab-sync") {
      var btn = state.nodes.input;
      btn.disabled = true;
      fetch("/api/v1/agent-builder/sync", { method: "POST", headers: { "Content-Type": "application/json" } })
        .then(function (r) { return r.ok ? r.json() : Promise.reject(r.status); })
        .then(function () { flashFooter("Agent Builder re-synced."); })
        .catch(function () { flashFooter("Run: curl -X POST /api/v1/agent-builder/sync"); })
        .then(function () { btn.disabled = false; });
    } else if (action === "kibana") {
      close();
      var base = getKibanaBase();
      window.open(base ? base + "/app/home" : "/api/v1/kibana/url?app=home", "_blank", "noopener");
    } else if (action === "shortcuts") {
      flashFooter("Cmd+K open  ·  Up/Down navigate  ·  Enter select  ·  Esc close  ·  Tab cycles focus");
    }
  }

  function flashFooter(msg) {
    var f = state.nodes.footHint;
    if (!f) return;
    var prev = f.textContent;
    f.textContent = msg;
    setTimeout(function () { if (f) f.textContent = prev; }, 3500);
  }

  /* ============================================================ DOM build */
  function build() {
    var backdrop = el("div", {
      class: "cp-backdrop",
      role: "presentation",
      hidden: ""
    });
    var modal = el("div", {
      class: "cp-modal",
      role: "dialog",
      "aria-modal": "true",
      "aria-label": "Command palette"
    });

    var input = el("input", {
      class: "cp-search-input",
      type: "text",
      autocomplete: "off",
      autocapitalize: "off",
      autocorrect: "off",
      spellcheck: "false",
      placeholder: "Search pages, tools, scenarios, meetings...",
      "aria-label": "Search commands",
      "aria-controls": "cp-results-list",
      role: "combobox",
      "aria-expanded": "true",
      "aria-autocomplete": "list"
    });
    var searchRow = el("div", { class: "cp-search-row" }, [
      el("span", { class: "cp-search-icon", "aria-hidden": "true" }, ["🔍"]),
      input,
      el("span", { class: "cp-kbd", "aria-hidden": "true" }, ["esc"])
    ]);

    var results = el("div", {
      class: "cp-results",
      id: "cp-results-list",
      role: "listbox",
      "aria-label": "Command results"
    });

    var counter = el("span", { class: "cp-counter", "aria-live": "polite" }, ["0 results"]);
    var footHint = el("span", { class: "cp-foot-hint" }, ["Tip: type to filter"]);
    var foot = el("div", { class: "cp-foot" }, [
      el("span", { class: "cp-foot-hints" }, [
        el("span", { class: "cp-foot-hint" }, [el("span", { class: "cp-kbd" }, ["↑↓"]), " navigate"]),
        el("span", { class: "cp-foot-hint" }, [el("span", { class: "cp-kbd" }, ["↵"]), " select"]),
        el("span", { class: "cp-foot-hint" }, [el("span", { class: "cp-kbd" }, ["esc"]), " close"]),
        footHint
      ]),
      counter
    ]);

    modal.appendChild(searchRow);
    modal.appendChild(results);
    modal.appendChild(foot);
    backdrop.appendChild(modal);

    backdrop.addEventListener("mousedown", function (e) {
      if (e.target === backdrop) close();
    });

    input.addEventListener("input", function () {
      state.query = input.value;
      state.selected = 0;
      render();
    });

    state.nodes = {
      backdrop: backdrop,
      modal: modal,
      input: input,
      results: results,
      counter: counter,
      footHint: footHint
    };
    document.body.appendChild(backdrop);
  }

  /* ============================================================ Open / close */
  function open() {
    if (state.open) return;
    if (!state.nodes) build();
    state.triggerEl = document.activeElement;
    state.open = true;
    state.query = "";
    state.selected = 0;
    state.nodes.input.value = "";
    state.nodes.backdrop.hidden = false;
    document.documentElement.classList.add("cp-open");
    document.body.style.overflow = "hidden";
    render();
    setTimeout(function () { state.nodes.input.focus(); }, 0);
    fetchDynamic().then(function () { if (state.open) render(); });
  }

  function close() {
    if (!state.open) return;
    state.open = false;
    state.nodes.backdrop.hidden = true;
    document.documentElement.classList.remove("cp-open");
    document.body.style.overflow = "";
    var t = state.triggerEl;
    state.triggerEl = null;
    if (t && typeof t.focus === "function") {
      try { t.focus(); } catch (_) {}
    }
  }

  /* ============================================================ Keyboard */
  function onGlobalKeydown(e) {
    var isCmdK = (e.key === "k" || e.key === "K") && (e.metaKey || e.ctrlKey) && !e.altKey;
    if (isCmdK) {
      if (state.open) { e.preventDefault(); close(); return; }
      if (isTypingTarget(e.target) && !(e.metaKey || e.ctrlKey)) return;
      e.preventDefault();
      open();
      return;
    }
    if (!state.open) return;
    if (e.key === "Escape") {
      e.preventDefault();
      close();
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelected(state.selected + 1, true);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelected(state.selected - 1, true);
    } else if (e.key === "Enter") {
      e.preventDefault();
      activate(state.selected);
    } else if (e.key === "Home") {
      e.preventDefault(); setSelected(0, true);
    } else if (e.key === "End") {
      e.preventDefault(); setSelected(state.flatResults.length - 1, true);
    } else if (e.key === "Tab") {
      // focus trap: input is the only focusable; cycle to it.
      e.preventDefault();
      state.nodes.input.focus();
    }
  }

  /* ============================================================ Init */
  function init() {
    document.addEventListener("keydown", onGlobalKeydown, true);
    // expose tiny API for ad-hoc invocation, e.g. from a header button.
    window.feCommandPalette = { open: open, close: close };
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
