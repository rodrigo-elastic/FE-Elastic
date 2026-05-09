/*
  filename: tools-rail.js
  description: Persistent left rail with global FE Copilot navigation: Dashboard plus the seven technical tools. Injected on every page so the rail is always visible. Tool links open the matching collapsible panel on tools.html (smooth scroll) or cross-navigate from any other page.
  Author: Rodrigo Careaga
  Date: 03-05-2026
*/
(function () {
  // ============================================================
  // Theme bootstrap (runs before any rail render to avoid FOUC).
  // Order of precedence: localStorage.fec.theme -> prefers-color-scheme.
  // The data-theme attribute lives on <html> so deeply nested elements
  // (Vega charts, markdown blocks, iframes) inherit the right tokens.
  // ============================================================
  const THEME_KEY = "fec.theme";
  function readSystemTheme() {
    try {
      return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    } catch (_e) {
      return "dark";
    }
  }
  function readStoredTheme() {
    try { return localStorage.getItem(THEME_KEY); } catch (_e) { return null; }
  }
  function writeStoredTheme(value) {
    try { localStorage.setItem(THEME_KEY, value); } catch (_e) { /* private mode */ }
  }
  function applyTheme(theme) {
    const next = theme === "light" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    return next;
  }
  // Apply immediately so the first paint already matches the user choice.
  const __initialTheme = applyTheme(readStoredTheme() || readSystemTheme());

  const PAGES = [
    {
      id: "home",
      label: "Home",
      href: "/",
      icon:
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 11.5 12 4l9 7.5"/><path d="M5 10v10h14V10"/></svg>',
    },
    {
      id: "quick-research",
      label: "Quick Research",
      href: "/quick-research.html",
      icon:
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>',
    },
    {
      id: "workspace",
      label: "Workspace",
      href: "/workspace.html",
      icon:
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2"/><line x1="3" y1="10" x2="21" y2="10"/><circle cx="7" cy="14" r="1"/><circle cx="12" cy="14" r="1"/><circle cx="17" cy="14" r="1"/></svg>',
    },
    {
      id: "pov-health",
      label: "POV Health",
      href: "/pov-health.html",
      icon:
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12h4l2-5 4 10 2-5h6"/><circle cx="12" cy="12" r="9"/></svg>',
    },
    {
      id: "fe-brain",
      label: "FE Brain",
      href: "/fe-brain.html",
      icon:
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 4h10a2 2 0 0 1 2 2v10"/><path d="M5 4v14a2 2 0 0 0 2 2h7"/><path d="M5 4a2 2 0 0 0 2 2h10"/><circle cx="16.5" cy="17.5" r="3"/><path d="m21 22-2.4-2.4"/></svg>',
    },
    {
      id: "agent-builder",
      label: "Agent Builder",
      href: "/agent-builder.html",
      icon:
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v4"/><path d="M5 7h14l-1 13H6Z"/><circle cx="9" cy="13" r="1"/><circle cx="15" cy="13" r="1"/><path d="M9 17h6"/></svg>',
    },
    {
      id: "battlecards",
      label: "Battlecards",
      href: "/battlecards.html",
      icon:
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="13" height="15" rx="2"/><path d="M8 5V3h6v2"/><path d="M16 8h4a1 1 0 0 1 1 1v10a2 2 0 0 1-2 2h-3"/><path d="M7 10h5"/><path d="M7 14h5"/></svg>',
    },
    {
      id: "industries",
      label: "Industries",
      href: "/industries.html",
      icon:
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21h18"/><path d="M5 21V8l4-3 4 3v13"/><path d="M13 21V12l4-2 4 2v9"/><path d="M9 12h.01"/><path d="M9 16h.01"/><path d="M17 14h.01"/><path d="M17 18h.01"/></svg>',
    },
    {
      id: "demo-data",
      label: "Demo Data",
      href: "/demo-data.html",
      icon:
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v6c0 1.7 4 3 9 3s9-1.3 9-3V5"/><path d="M3 11v6c0 1.7 4 3 9 3s9-1.3 9-3v-6"/></svg>',
    },
    {
      id: "workflow",
      label: "Workflow",
      href: "/workflow-demo.html",
      icon:
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="5" cy="6" r="2"/><circle cx="19" cy="6" r="2"/><circle cx="12" cy="18" r="2"/><path d="M7 6h10"/><path d="M5 8v3a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8"/><path d="M12 13v3"/></svg>',
    },
    {
      id: "health",
      label: "Health",
      href: "/health.html",
      icon:
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12h4l2-5 4 10 2-5h6"/></svg>',
    },
    {
      id: "audit",
      label: "Audit",
      href: "/audit.html",
      icon:
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v18h18"/><path d="M7 15l4-5 3 3 5-7"/><circle cx="19" cy="6" r="1.4"/></svg>',
    },
  ];

  const TOOLS = [
    { id: "tool-poc", label: "POC plan", num: "01" },
    { id: "tool-spl", label: "SPL → ES|QL", num: "02" },
    { id: "tool-compliance", label: "Compliance", num: "03" },
    { id: "tool-cost", label: "Cost", num: "04" },
    { id: "tool-capacity", label: "Capacity", num: "05" },
    { id: "tool-stack", label: "Stack", num: "06" },
    { id: "tool-code", label: "Code", num: "07" },
    { id: "tool-troubleshoot", label: "Troubleshoot", num: "08" },
  ];

  function isToolsPage() {
    return /\/tools(\.html)?$/.test(location.pathname) || document.body.classList.contains("tools-page");
  }
  function isHomePage() {
    return location.pathname === "/" || /\/index(\.html)?$/.test(location.pathname);
  }
  function isQuickResearchPage() {
    return /\/quick-research(\.html)?$/.test(location.pathname) || document.body.classList.contains("quick-research-page");
  }
  function isCustomersPage() {
    return /\/customers(\.html)?$/.test(location.pathname) || document.body.classList.contains("customers-page");
  }
  function isWorkspacePage() {
    return /\/workspace(\.html)?$/.test(location.pathname) || document.body.classList.contains("workspace-page");
  }
  function isPovHealthPage() {
    return /\/pov-health(\.html)?$/.test(location.pathname) || document.body.classList.contains("pov-health-page");
  }
  function isAgentBuilderPage() {
    return /\/agent-builder(\.html)?$/.test(location.pathname) || document.body.classList.contains("agent-builder-page");
  }
  function isFeBrainPage() {
    return /\/fe-brain(\.html)?$/.test(location.pathname) || document.body.classList.contains("fe-brain-page");
  }
  function isWorkflowPage() {
    return /\/workflow-(demo|settings)(\.html)?$/.test(location.pathname) || document.body.classList.contains("workflow-page");
  }
  function isDemoDataPage() {
    return /\/demo-data(\.html)?$/.test(location.pathname);
  }
  function isIndustriesPage() {
    return /\/industries(\.html)?$/.test(location.pathname) || document.body.classList.contains("industries-page");
  }
  function isBattlecardsPage() {
    return /\/battlecards(\.html)?$/.test(location.pathname) || document.body.classList.contains("battlecards-page");
  }
  function isAuditPage() {
    return /\/audit(\.html)?$/.test(location.pathname) || document.body.classList.contains("audit-page");
  }
  function isHealthPage() {
    return /\/health(\.html)?$/.test(location.pathname) || document.body.classList.contains("health-page");
  }

  function ensureBodyClass() {
    document.body.classList.add("has-tools-rail");
  }

  function buildRail() {
    if (document.querySelector(".tools-sidebar")) return null; // legacy markup
    const aside = document.createElement("aside");
    aside.className = "tools-sidebar";
    aside.setAttribute("aria-label", "FE Copilot navigation");
    const topbar = document.querySelector(".topbar");
    if (topbar && topbar.parentNode) {
      topbar.parentNode.insertBefore(aside, topbar.nextSibling);
    } else {
      document.body.insertBefore(aside, document.body.firstChild);
    }
    return aside;
  }

  function sectionLabel(text) {
    const div = document.createElement("div");
    div.className = "tools-sidebar-lbl";
    div.textContent = text;
    return div;
  }

  function pageLink(p) {
    const a = document.createElement("a");
    a.className = "tools-nav-pill page-link";
    a.href = p.href;
    let isActive = false;
    if (p.id === "home" && isHomePage()) { a.classList.add("active"); isActive = true; }
    if (p.id === "quick-research" && isQuickResearchPage()) { a.classList.add("active"); isActive = true; }
    if (p.id === "workspace" && (isWorkspacePage() || isCustomersPage())) { a.classList.add("active"); isActive = true; }
    if (p.id === "pov-health" && isPovHealthPage()) { a.classList.add("active"); isActive = true; }
    if (p.id === "agent-builder" && isAgentBuilderPage()) { a.classList.add("active"); isActive = true; }
    if (p.id === "fe-brain" && isFeBrainPage()) { a.classList.add("active"); isActive = true; }
    if (p.id === "workflow" && isWorkflowPage()) { a.classList.add("active"); isActive = true; }
    if (p.id === "demo-data" && isDemoDataPage()) { a.classList.add("active"); isActive = true; }
    if (p.id === "industries" && isIndustriesPage()) { a.classList.add("active"); isActive = true; }
    if (p.id === "battlecards" && isBattlecardsPage()) { a.classList.add("active"); isActive = true; }
    if (p.id === "audit" && isAuditPage()) { a.classList.add("active"); isActive = true; }
    if (p.id === "health" && isHealthPage()) { a.classList.add("active"); isActive = true; }
    if (isActive) a.setAttribute("aria-current", "page");
    const ico = document.createElement("span");
    ico.className = "tools-nav-icon";
    ico.setAttribute("aria-hidden", "true");
    ico.innerHTML = p.icon;
    a.appendChild(ico);
    a.appendChild(document.createTextNode(" " + p.label));
    return a;
  }

  function toolLink(t, onTools, currentHash) {
    const a = document.createElement("a");
    a.className = "tools-nav-pill";
    a.href = onTools ? "#" + t.id : "/tools.html#" + t.id;
    a.setAttribute("aria-label", "Tool " + t.num + ": " + t.label);
    if (onTools && currentHash === "#" + t.id) {
      a.classList.add("active");
      a.setAttribute("aria-current", "true");
    }
    a.addEventListener("click", (ev) => {
      if (!onTools) return;
      const det = document.getElementById(t.id);
      if (det) {
        ev.preventDefault();
        det.setAttribute("open", "");
        document.querySelectorAll(".tools-nav-pill.active").forEach((p) => {
          p.classList.remove("active");
          p.removeAttribute("aria-current");
        });
        a.classList.add("active");
        a.setAttribute("aria-current", "true");
        history.replaceState(null, "", "#" + t.id);
        setTimeout(() => det.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
      }
    });
    const num = document.createElement("span");
    num.className = "tools-nav-num";
    num.setAttribute("aria-hidden", "true");
    num.textContent = t.num;
    a.appendChild(num);
    a.appendChild(document.createTextNode(" " + t.label));
    return a;
  }

  function render(aside) {
    aside.innerHTML = "";
    const onTools = isToolsPage();

    aside.appendChild(sectionLabel("Navigate"));
    const pagesNav = document.createElement("nav");
    pagesNav.className = "tools-nav";
    pagesNav.setAttribute("aria-label", "Primary navigation");
    PAGES.forEach((p) => pagesNav.appendChild(pageLink(p)));
    // Tools as a top-level page entry too (acts as a quick jump to the tools page).
    const toolsHomeLink = document.createElement("a");
    toolsHomeLink.className = "tools-nav-pill page-link";
    toolsHomeLink.href = "/tools.html";
    // POV Health has its own sidebar entry; do not double-highlight the generic Tools link there.
    if (onTools && !isPovHealthPage()) {
      toolsHomeLink.classList.add("active");
      toolsHomeLink.setAttribute("aria-current", "page");
    }
    toolsHomeLink.innerHTML =
      '<span class="tools-nav-icon" aria-hidden="true"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3h.1a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8v.1a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z"/></svg></span> Tools';
    pagesNav.appendChild(toolsHomeLink);
    aside.appendChild(pagesNav);
  }

  // ============================================================
  // Mobile hamburger toggle (surgical addition; desktop layout unchanged).
  // Injects a button into .topbar that toggles `.tools-sidebar.is-open`.
  // CSS hides the button above 768px, so the desktop UI is untouched.
  // ============================================================
  function buildSidebarToggle(aside) {
    if (document.querySelector(".sidebar-toggle")) return;
    const topbar = document.querySelector(".topbar");
    if (!topbar) return;

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "sidebar-toggle";
    btn.setAttribute("aria-label", "Open navigation menu");
    btn.setAttribute("aria-controls", "tools-sidebar");
    btn.setAttribute("aria-expanded", "false");
    btn.innerHTML =
      '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><line x1="4" y1="6" x2="20" y2="6"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="18" x2="20" y2="18"/></svg>';
    // Insert before the .right group so the toggle is left-of-center (next to the brand).
    const right = topbar.querySelector(".right");
    if (right && right.parentNode === topbar) {
      topbar.insertBefore(btn, right);
    } else {
      topbar.appendChild(btn);
    }
    if (!aside.id) aside.id = "tools-sidebar";

    // Scrim used to dim the page and capture outside taps.
    let scrim = document.querySelector(".sidebar-scrim");
    if (!scrim) {
      scrim = document.createElement("div");
      scrim.className = "sidebar-scrim";
      scrim.setAttribute("aria-hidden", "true");
      document.body.appendChild(scrim);
    }

    const mq = window.matchMedia("(max-width: 768px)");

    function setOpen(open) {
      aside.classList.toggle("is-open", !!open);
      scrim.classList.toggle("is-visible", !!open);
      btn.setAttribute("aria-expanded", open ? "true" : "false");
      btn.setAttribute(
        "aria-label",
        open ? "Close navigation menu" : "Open navigation menu"
      );
      // Lock body scroll while the off-canvas panel is visible.
      document.body.style.overflow = open ? "hidden" : "";
    }

    btn.addEventListener("click", function (ev) {
      ev.preventDefault();
      setOpen(!aside.classList.contains("is-open"));
    });

    scrim.addEventListener("click", function () {
      setOpen(false);
    });

    // Close when any rail link is tapped.
    aside.addEventListener("click", function (ev) {
      const target = ev.target.closest("a.tools-nav-pill");
      if (target && mq.matches) setOpen(false);
    });

    // Close on Escape.
    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape" && aside.classList.contains("is-open")) {
        setOpen(false);
        btn.focus();
      }
    });

    // Auto-close if the viewport widens past mobile while the panel is open.
    function handleMqChange(e) {
      if (!e.matches) setOpen(false);
    }
    if (typeof mq.addEventListener === "function") {
      mq.addEventListener("change", handleMqChange);
    } else if (typeof mq.addListener === "function") {
      mq.addListener(handleMqChange);
    }
  }

  // ============================================================
  // Theme toggle button (topbar right side).
  // We show the icon for the OPPOSITE state so the button reads as
  // "click to switch to X". The aria-label and title also update so
  // screen readers and tooltips stay accurate.
  // ============================================================
  const SUN_SVG =
    '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m4.93 19.07 1.41-1.41"/><path d="m17.66 6.34 1.41-1.41"/></svg>';
  const MOON_SVG =
    '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79Z"/></svg>';

  function themeI18n(key, fallback) {
    if (typeof window !== "undefined" && typeof window.t === "function") {
      const out = window.t(key, fallback);
      if (out) return out;
    }
    return fallback;
  }
  function describeToggle(theme) {
    // theme = current theme; the button switches to the OTHER one.
    if (theme === "dark") {
      return {
        icon: SUN_SVG,
        label: themeI18n("theme.toggle.toLight", "Switch to light theme"),
      };
    }
    return {
      icon: MOON_SVG,
      label: themeI18n("theme.toggle.toDark", "Switch to dark theme"),
    };
  }
  function refreshThemeToggleButton(btn) {
    const cur = document.documentElement.getAttribute("data-theme") || "dark";
    const meta = describeToggle(cur);
    btn.innerHTML = meta.icon;
    btn.setAttribute("aria-label", meta.label);
    btn.title = meta.label;
    btn.setAttribute("data-current-theme", cur);
    btn.setAttribute("aria-pressed", cur === "light" ? "true" : "false");
  }
  function buildThemeToggle() {
    if (document.querySelector(".theme-toggle")) return;
    const topbar = document.querySelector(".topbar");
    if (!topbar) return;
    const right = topbar.querySelector(".right");
    if (!right) return;

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "theme-toggle";
    refreshThemeToggleButton(btn);

    btn.addEventListener("click", function (ev) {
      ev.preventDefault();
      const cur = document.documentElement.getAttribute("data-theme") || "dark";
      const next = cur === "dark" ? "light" : "dark";
      applyTheme(next);
      writeStoredTheme(next);
      refreshThemeToggleButton(btn);
      // Notify other modules that may want to redraw (audit charts, etc.).
      try {
        window.dispatchEvent(new CustomEvent("fec:themechange", { detail: { theme: next } }));
      } catch (_e) { /* ignore */ }
    });

    // Insert before the language picker host, falling back to the end.
    const langHost = right.querySelector(".lang-host");
    if (langHost && langHost.parentNode === right) {
      right.insertBefore(btn, langHost);
    } else {
      right.appendChild(btn);
    }

    // Track OS preference: only follow it while the user has not set a manual choice.
    try {
      const mq = window.matchMedia("(prefers-color-scheme: dark)");
      const onChange = (e) => {
        if (readStoredTheme()) return; // user override wins
        applyTheme(e.matches ? "dark" : "light");
        refreshThemeToggleButton(btn);
      };
      if (typeof mq.addEventListener === "function") mq.addEventListener("change", onChange);
      else if (typeof mq.addListener === "function") mq.addListener(onChange);
    } catch (_e) { /* ignore */ }
  }

  function init() {
    // Embed mode: when this page is loaded inside the autopilot iframe (or any
    // other parent that adds ?embed=1), suppress the left rail entirely so it
    // does not cover the framed content.
    try {
      const params = new URLSearchParams(location.search);
      if (params.get("embed") === "1") {
        document.body.classList.add("is-embedded");
        // Also hide the topbar when embedded; the autopilot already shows
        // its own panel header and SKO/demo banners are not needed inside
        // the framed view.
        return;
      }
    } catch (_e) { /* ignore */ }
    ensureBodyClass();
    let aside = document.querySelector(".tools-sidebar");
    if (!aside) aside = buildRail();
    if (!aside) return;
    render(aside);
    buildSidebarToggle(aside);
    buildRailCollapseToggle(aside);
    buildThemeToggle();
  }

  // ============================================================
  // Desktop collapse toggle (icon-only rail). Persists in localStorage so the
  // user's preference survives navigation. Mobile path uses the off-canvas
  // hamburger from buildSidebarToggle and ignores the collapse state.
  // ============================================================
  function buildRailCollapseToggle(aside) {
    if (aside.querySelector(".tools-rail-collapse-btn")) return;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "tools-rail-collapse-btn";
    btn.setAttribute("aria-controls", aside.id || "tools-sidebar");
    btn.setAttribute("aria-pressed", "false");
    function applyState(collapsed) {
      aside.classList.toggle("is-collapsed", collapsed);
      document.body.classList.toggle("is-rail-collapsed", collapsed);
      btn.setAttribute("aria-pressed", collapsed ? "true" : "false");
      btn.setAttribute("aria-label", collapsed ? "Expand navigation" : "Collapse navigation");
      btn.setAttribute("title", collapsed ? "Expand navigation" : "Collapse navigation");
      btn.innerHTML = collapsed
        ? '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><polyline points="9 6 15 12 9 18"/></svg>'
        : '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><polyline points="15 6 9 12 15 18"/></svg>';
    }
    btn.addEventListener("click", function () {
      const next = !aside.classList.contains("is-collapsed");
      try { localStorage.setItem("fec.rail.collapsed", next ? "1" : "0"); } catch (_e) {}
      applyState(next);
    });
    aside.appendChild(btn);
    let initial = false;
    try { initial = localStorage.getItem("fec.rail.collapsed") === "1"; } catch (_e) {}
    applyState(initial);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
