/*
  filename: tools-rail.js
  description: Persistent left rail with global FE Copilot navigation: Dashboard plus the seven technical tools. Injected on every page so the rail is always visible. Tool links open the matching collapsible panel on tools.html (smooth scroll) or cross-navigate from any other page.
  Author: Rodrigo Careaga
  Date: 03-05-2026
*/
(function () {
  const PAGES = [
    {
      id: "dashboard",
      label: "Dashboard",
      href: "/",
      icon:
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 11.5 12 4l9 7.5"/><path d="M5 10v10h14V10"/></svg>',
    },
    {
      id: "agent-builder",
      label: "Agent Builder",
      href: "/agent-builder.html",
      icon:
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v4"/><path d="M5 7h14l-1 13H6Z"/><circle cx="9" cy="13" r="1"/><circle cx="15" cy="13" r="1"/><path d="M9 17h6"/></svg>',
    },
    {
      id: "fe-brain",
      label: "FE Brain",
      href: "/fe-brain.html",
      icon:
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 4h10a2 2 0 0 1 2 2v10"/><path d="M5 4v14a2 2 0 0 0 2 2h7"/><path d="M5 4a2 2 0 0 0 2 2h10"/><circle cx="16.5" cy="17.5" r="3"/><path d="m21 22-2.4-2.4"/></svg>',
    },
    {
      id: "workflow",
      label: "Workflow",
      href: "/workflow-demo.html",
      icon:
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="5" cy="6" r="2"/><circle cx="19" cy="6" r="2"/><circle cx="12" cy="18" r="2"/><path d="M7 6h10"/><path d="M5 8v3a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8"/><path d="M12 13v3"/></svg>',
    },
    {
      id: "demo-data",
      label: "Demo Data",
      href: "/demo-data.html",
      icon:
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v6c0 1.7 4 3 9 3s9-1.3 9-3V5"/><path d="M3 11v6c0 1.7 4 3 9 3s9-1.3 9-3v-6"/></svg>',
    },
    {
      id: "battlecards",
      label: "Battlecards",
      href: "/battlecards.html",
      icon:
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="13" height="15" rx="2"/><path d="M8 5V3h6v2"/><path d="M16 8h4a1 1 0 0 1 1 1v10a2 2 0 0 1-2 2h-3"/><path d="M7 10h5"/><path d="M7 14h5"/></svg>',
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
  function isDashboardPage() {
    return location.pathname === "/" || /\/index(\.html)?$/.test(location.pathname);
  }
  function isAgentBuilderPage() {
    return /\/agent-builder(\.html)?$/.test(location.pathname) || document.body.classList.contains("agent-builder-page");
  }
  function isFeBrainPage() {
    return /\/fe-brain(\.html)?$/.test(location.pathname) || document.body.classList.contains("fe-brain-page");
  }
  function isWorkflowPage() {
    return /\/workflow-demo(\.html)?$/.test(location.pathname);
  }
  function isDemoDataPage() {
    return /\/demo-data(\.html)?$/.test(location.pathname);
  }
  function isBattlecardsPage() {
    return /\/battlecards(\.html)?$/.test(location.pathname) || document.body.classList.contains("battlecards-page");
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
    if (p.id === "dashboard" && isDashboardPage()) { a.classList.add("active"); isActive = true; }
    if (p.id === "agent-builder" && isAgentBuilderPage()) { a.classList.add("active"); isActive = true; }
    if (p.id === "fe-brain" && isFeBrainPage()) { a.classList.add("active"); isActive = true; }
    if (p.id === "workflow" && isWorkflowPage()) { a.classList.add("active"); isActive = true; }
    if (p.id === "demo-data" && isDemoDataPage()) { a.classList.add("active"); isActive = true; }
    if (p.id === "battlecards" && isBattlecardsPage()) { a.classList.add("active"); isActive = true; }
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
    if (onTools) {
      toolsHomeLink.classList.add("active");
      toolsHomeLink.setAttribute("aria-current", "page");
    }
    toolsHomeLink.innerHTML =
      '<span class="tools-nav-icon" aria-hidden="true"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3h.1a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8v.1a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z"/></svg></span> Tools';
    pagesNav.appendChild(toolsHomeLink);
    aside.appendChild(pagesNav);

    aside.appendChild(sectionLabel("FE Tools"));
    const toolsNav = document.createElement("nav");
    toolsNav.className = "tools-nav";
    toolsNav.id = "tools-nav";
    toolsNav.setAttribute("aria-label", "FE technical tools");
    const currentHash = location.hash;
    TOOLS.forEach((t) => toolsNav.appendChild(toolLink(t, onTools, currentHash)));
    aside.appendChild(toolsNav);
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

  function init() {
    ensureBodyClass();
    let aside = document.querySelector(".tools-sidebar");
    if (!aside) aside = buildRail();
    if (!aside) return;
    render(aside);
    buildSidebarToggle(aside);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
