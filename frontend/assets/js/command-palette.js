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
  // 12 pages match the persistent left rail in tools-rail.js; if a page is added
  // there, append the matching entry below so the palette never drifts.
  var STATIC_COMMANDS = [
    // Pages (12)
    { type: "pages", icon: "🏠", label: "Home",            sub: "/index.html",          href: "/index.html",          keywords: "home dashboard overview" },
    { type: "pages", icon: "🔎", label: "Quick Research",  sub: "/quick-research.html", href: "/quick-research.html", keywords: "brief account research pre meeting" },
    { type: "pages", icon: "👥", label: "Customers",       sub: "/customers.html",      href: "/customers.html",      keywords: "accounts companies opportunities" },
    { type: "pages", icon: "🧠", label: "FE Brain",        sub: "/fe-brain.html",       href: "/fe-brain.html",       keywords: "knowledge docs rag corpus" },
    { type: "pages", icon: "🤖", label: "Agent Builder",   sub: "/agent-builder.html",  href: "/agent-builder.html",  keywords: "agents prompts orchestrator" },
    { type: "pages", icon: "⚔",  label: "Battlecards",     sub: "/battlecards.html",    href: "/battlecards.html",    keywords: "competitive splunk datadog" },
    { type: "pages", icon: "🏭", label: "Industries",      sub: "/industries.html",     href: "/industries.html",     keywords: "vertical sector verticals" },
    { type: "pages", icon: "🧪", label: "Demo Data",       sub: "/demo-data.html",      href: "/demo-data.html",      keywords: "scenarios seed credstuff ddos ransomware" },
    { type: "pages", icon: "🌊", label: "Workflow",        sub: "/workflow-demo.html",  href: "/workflow-demo.html",  keywords: "pipeline demo orchestration" },
    { type: "pages", icon: "🩺", label: "Health",          sub: "/health.html",         href: "/health.html",         keywords: "status diagnostics uptime" },
    { type: "pages", icon: "📜", label: "Audit",           sub: "/audit.html",          href: "/audit.html",          keywords: "log compliance trail" },
    { type: "pages", icon: "🛠",  label: "Tools",           sub: "/tools.html",          href: "/tools.html",          keywords: "panels generators 12 tools" },

    // Tools (12) - matches tool-poc through tool-proposal anchors on /tools.html.
    { type: "tools", icon: "📋", label: "POC Plan",                sub: "/tools.html#tool-poc",          href: "/tools.html#tool-poc",          keywords: "proof concept pov" },
    { type: "tools", icon: "🔁", label: "SPL to ES|QL",            sub: "/tools.html#tool-spl",          href: "/tools.html#tool-spl",          keywords: "splunk migration query translation" },
    { type: "tools", icon: "✅", label: "Compliance",              sub: "/tools.html#tool-compliance",   href: "/tools.html#tool-compliance",   keywords: "fca soc2 hipaa gdpr pci dora" },
    { type: "tools", icon: "💰", label: "Cost",                    sub: "/tools.html#tool-cost",         href: "/tools.html#tool-cost",         keywords: "tco pricing splunk datadog" },
    { type: "tools", icon: "📈", label: "Capacity",                sub: "/tools.html#tool-capacity",     href: "/tools.html#tool-capacity",     keywords: "cluster sizing nodes shards" },
    { type: "tools", icon: "📚", label: "Stack",                   sub: "/tools.html#tool-stack",        href: "/tools.html#tool-stack",        keywords: "tech extract integrations" },
    { type: "tools", icon: "💻", label: "Code",                    sub: "/tools.html#tool-code",         href: "/tools.html#tool-code",         keywords: "samples snippets agent" },
    { type: "tools", icon: "🩺", label: "Troubleshoot",            sub: "/tools.html#tool-troubleshoot", href: "/tools.html#tool-troubleshoot", keywords: "diagnose error logs" },
    { type: "tools", icon: "🧠", label: "Knowledge (FE Brain)",    sub: "/tools.html#tool-knowledge",    href: "/tools.html#tool-knowledge",    keywords: "docs rag search corpus mei" },
    { type: "tools", icon: "🎯", label: "Compare (Sloane)",        sub: "/tools.html#tool-compare",      href: "/tools.html#tool-compare",      keywords: "competitive battlecard sloane" },
    { type: "tools", icon: "🎼", label: "Orchestrator (Auro)",     sub: "/tools.html#tool-orchestrator", href: "/tools.html#tool-orchestrator", keywords: "router multi agent auro" },
    { type: "tools", icon: "📝", label: "Proposal (Carmen)",       sub: "/tools.html#tool-proposal",     href: "/tools.html#tool-proposal",     keywords: "one pager carmen pursuit" },

    // Quick actions (4)
    { type: "actions", icon: "🚦", label: "Run smoke test",         sub: "Open runtime/integration_smoke output", action: "smoke",         keywords: "test integration runtime" },
    { type: "actions", icon: "🔄", label: "Re-sync Agent Builder",  sub: "POST /agent-builder/sync",              action: "ab-sync",       keywords: "agents reload refresh" },
    { type: "actions", icon: "🟦", label: "Open Kibana",            sub: "Open Kibana home in a new tab",         action: "kibana",        keywords: "elastic dashboards" },
    { type: "actions", icon: "⌨",  label: "Show keyboard shortcuts", sub: "View all keyboard hints",              action: "shortcuts",     keywords: "help hotkeys keys" }
  ];

  /* ============================================================ Constants */
  var CACHE_TTL_MS = 60 * 1000;
  var SECTION_ORDER = ["pages", "tools", "battlecards", "industries", "scenarios", "meetings", "actions"];
  var SECTION_TITLES = {
    pages:       "Pages",
    tools:       "Tools",
    battlecards: "Battlecards",
    industries:  "Industries",
    scenarios:   "Demo Scenarios",
    meetings:    "Recent Meetings",
    actions:     "Quick Actions"
  };

  /* ============================================================ State */
  var state = {
    open: false,
    query: "",
    selected: 0,
    flatResults: [],
    cache: { at: 0, scenarios: [], meetings: [], battlecards: [], industries: [] },
    fetchPromise: null,
    triggerEl: null,
    nodes: null,
    helpOpen: false,
    helpNodes: null
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
    if (Date.now() - state.cache.at < CACHE_TTL_MS && (
      state.cache.scenarios.length || state.cache.meetings.length ||
      state.cache.battlecards.length || state.cache.industries.length
    )) {
      return Promise.resolve();
    }
    if (state.fetchPromise) return state.fetchPromise;
    // Prefer the retry wrapper when present so a transient backend hiccup
    // does not blank the palette. silent: true so we never toast for the
    // background palette warm-up - the user has not asked for anything yet.
    var hasRetry = typeof window.apiGetWithRetry === "function";
    var fetchSafe;
    if (hasRetry) {
      fetchSafe = function (path) {
        return window
          .apiGetWithRetry(path, { category: "compute", silent: true, label: "palette " + path })
          .catch(function () { return null; });
      };
    } else {
      var safe = function (p) {
        return p.then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; });
      };
      fetchSafe = function (path) { return safe(fetch(path)); };
    }
    state.fetchPromise = Promise.all([
      fetchSafe("/api/v1/demo-data/scenarios"),
      fetchSafe("/api/v1/meetings"),
      fetchSafe("/api/v1/briefs"),
      fetchSafe("/api/v1/battlecards"),
      fetchSafe("/api/v1/industries")
    ]).then(function (out) {
      var scenariosRaw  = (out[0] && (out[0].scenarios || out[0])) || [];
      var meetingsRaw   = out[1] || [];
      var briefsRaw     = (out[2] && (out[2].briefs || out[2])) || [];
      var battleRaw     = (out[3] && (out[3].items || out[3])) || [];
      var industriesRaw = (out[4] && (out[4].items || out[4])) || [];
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
      // battlecards: each card becomes a quick jump to /battlecards.html#<slug>.
      state.cache.battlecards = (Array.isArray(battleRaw) ? battleRaw : []).map(function (c) {
        var slug = c.competitor_slug || (c.competitor || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
        var name = c.competitor || slug;
        var vertical = c.vertical || c.category || "";
        return {
          type: "battlecards",
          icon: "⚔",
          label: name,
          sub: vertical ? ("Battlecard - " + vertical) : "Battlecard",
          href: "/battlecards.html#" + encodeURIComponent(slug),
          keywords: (slug + " " + name + " " + vertical + " competitor").toLowerCase()
        };
      });
      // industries: each row becomes a quick jump to /industries.html?industry=<id>.
      state.cache.industries = (Array.isArray(industriesRaw) ? industriesRaw : []).map(function (it) {
        var id = it.id || "";
        var name = it.name || it.title || id;
        var summary = it.summary || it.tagline || "";
        return {
          type: "industries",
          icon: "🏭",
          label: name,
          sub: summary || ("Industry - " + id),
          href: id ? ("/industries.html?industry=" + encodeURIComponent(id)) : "/industries.html",
          keywords: (id + " " + name + " " + summary + " industry vertical").toLowerCase()
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
    return STATIC_COMMANDS
      .concat(state.cache.battlecards  || [])
      .concat(state.cache.industries   || [])
      .concat(state.cache.scenarios    || [])
      .concat(state.cache.meetings     || []);
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
      var syncPromise = typeof window.apiPostWithRetry === "function"
        ? window.apiPostWithRetry("/agent-builder/sync", null, { category: "workflow", silent: true, label: "ab-sync" })
        : fetch("/api/v1/agent-builder/sync", { method: "POST", headers: { "Content-Type": "application/json" } })
            .then(function (r) { return r.ok ? r.json() : Promise.reject(r.status); });
      syncPromise
        .then(function () { flashFooter("Agent Builder re-synced."); })
        .catch(function () { flashFooter("Run: curl -X POST /api/v1/agent-builder/sync"); })
        .then(function () { btn.disabled = false; });
    } else if (action === "kibana") {
      close();
      var base = getKibanaBase();
      window.open(base ? base + "/app/home" : "/api/v1/kibana/url?app=home", "_blank", "noopener");
    } else if (action === "shortcuts") {
      close();
      // Defer so the palette close animation completes before help opens.
      setTimeout(openHelp, 60);
    }
  }

  /* ============================================================ Keyboard help dialog */
  function tHelp(key, fallback) {
    try {
      if (typeof window.t === "function") {
        var v = window.t(key, fallback);
        if (v) return v;
      }
    } catch (_) {}
    return fallback;
  }
  function openHelp() {
    if (state.helpOpen) return;
    state.helpOpen = true;
    if (state.helpNodes) {
      state.helpNodes.backdrop.hidden = false;
      setTimeout(function () { state.helpNodes.close.focus(); }, 0);
      return;
    }
    var rows = [
      ["Cmd / Ctrl + K", tHelp("cp.help.row.open", "Open or close the command palette")],
      ["?",              tHelp("cp.help.row.help", "Show this keyboard shortcuts panel")],
      ["Esc",            tHelp("cp.help.row.esc", "Close the open palette, dialog, or autopilot")],
      ["Up / Down",      tHelp("cp.help.row.move", "Move the highlight in the palette result list")],
      ["Enter",          tHelp("cp.help.row.enter", "Activate the highlighted item")],
      ["Home / End",     tHelp("cp.help.row.homeend", "Jump to first or last result")],
      ["Tab",            tHelp("cp.help.row.tab", "Cycle focus inside the palette")],
      ["/",              tHelp("cp.help.row.slash", "Focus the page search field on Home")]
    ];
    var list = el("dl", { class: "cp-help-list" });
    rows.forEach(function (r) {
      list.appendChild(el("dt", { class: "cp-help-key" }, [el("span", { class: "cp-kbd" }, [r[0]])]));
      list.appendChild(el("dd", { class: "cp-help-desc" }, [r[1]]));
    });
    var closeBtn = el("button", {
      type: "button",
      class: "cp-help-close",
      "aria-label": tHelp("cp.help.close", "Close keyboard shortcuts")
    }, [tHelp("cp.help.close.label", "Close")]);
    closeBtn.addEventListener("click", closeHelp);
    var modal = el("div", {
      class: "cp-help-modal",
      role: "dialog",
      "aria-modal": "true",
      "aria-label": tHelp("cp.help.title", "Keyboard shortcuts")
    }, [
      el("h2", { class: "cp-help-title" }, [tHelp("cp.help.title", "Keyboard shortcuts")]),
      list,
      el("div", { class: "cp-help-foot" }, [closeBtn])
    ]);
    var backdrop = el("div", { class: "cp-help-backdrop", role: "presentation" }, [modal]);
    backdrop.addEventListener("mousedown", function (ev) {
      if (ev.target === backdrop) closeHelp();
    });
    document.body.appendChild(backdrop);
    state.helpNodes = { backdrop: backdrop, modal: modal, close: closeBtn };
    setTimeout(function () { closeBtn.focus(); }, 0);
  }
  function closeHelp() {
    if (!state.helpOpen) return;
    state.helpOpen = false;
    if (state.helpNodes && state.helpNodes.backdrop) {
      state.helpNodes.backdrop.hidden = true;
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
      if (state.open) { e.preventDefault(); e.stopPropagation(); close(); return; }
      e.preventDefault();
      e.stopPropagation();
      open();
      return;
    }
    // Help dialog shortcut: "?" anywhere outside a typing target opens shortcuts overlay.
    if (!state.open && !state.helpOpen && e.key === "?" && !e.metaKey && !e.ctrlKey && !e.altKey) {
      if (isTypingTarget(e.target)) return;
      e.preventDefault();
      e.stopPropagation();
      openHelp();
      return;
    }
    if (state.helpOpen && e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      closeHelp();
      return;
    }
    if (!state.open) return;
    if (e.key === "Escape") {
      // Stop propagation so other listeners (autopilot stop, modal close) do not also fire.
      e.preventDefault();
      e.stopPropagation();
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
