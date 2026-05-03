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
  ];

  const TOOLS = [
    { id: "tool-poc", label: "POC plan", num: "01" },
    { id: "tool-spl", label: "SPL → ES|QL", num: "02" },
    { id: "tool-compliance", label: "Compliance", num: "03" },
    { id: "tool-cost", label: "Cost", num: "04" },
    { id: "tool-capacity", label: "Capacity", num: "05" },
    { id: "tool-stack", label: "Stack", num: "06" },
    { id: "tool-code", label: "Code", num: "07" },
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
  function isWorkflowPage() {
    return /\/workflow-demo(\.html)?$/.test(location.pathname);
  }
  function isDemoDataPage() {
    return /\/demo-data(\.html)?$/.test(location.pathname);
  }

  function ensureBodyClass() {
    document.body.classList.add("has-tools-rail");
  }

  function buildRail() {
    if (document.querySelector(".tools-sidebar")) return null; // legacy markup
    const aside = document.createElement("aside");
    aside.className = "tools-sidebar";
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
    if (p.id === "dashboard" && isDashboardPage()) a.classList.add("active");
    if (p.id === "agent-builder" && isAgentBuilderPage()) a.classList.add("active");
    if (p.id === "workflow" && isWorkflowPage()) a.classList.add("active");
    if (p.id === "demo-data" && isDemoDataPage()) a.classList.add("active");
    const ico = document.createElement("span");
    ico.className = "tools-nav-icon";
    ico.innerHTML = p.icon;
    a.appendChild(ico);
    a.appendChild(document.createTextNode(" " + p.label));
    return a;
  }

  function toolLink(t, onTools, currentHash) {
    const a = document.createElement("a");
    a.className = "tools-nav-pill";
    a.href = onTools ? "#" + t.id : "/tools.html#" + t.id;
    if (onTools && currentHash === "#" + t.id) a.classList.add("active");
    a.addEventListener("click", (ev) => {
      if (!onTools) return;
      const det = document.getElementById(t.id);
      if (det) {
        ev.preventDefault();
        det.setAttribute("open", "");
        document.querySelectorAll(".tools-nav-pill.active").forEach((p) => p.classList.remove("active"));
        a.classList.add("active");
        history.replaceState(null, "", "#" + t.id);
        setTimeout(() => det.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
      }
    });
    const num = document.createElement("span");
    num.className = "tools-nav-num";
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
    PAGES.forEach((p) => pagesNav.appendChild(pageLink(p)));
    // Tools as a top-level page entry too (acts as a quick jump to the tools page).
    const toolsHomeLink = document.createElement("a");
    toolsHomeLink.className = "tools-nav-pill page-link";
    toolsHomeLink.href = "/tools.html";
    if (onTools) toolsHomeLink.classList.add("active");
    toolsHomeLink.innerHTML =
      '<span class="tools-nav-icon"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3h.1a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8v.1a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z"/></svg></span> Tools';
    pagesNav.appendChild(toolsHomeLink);
    aside.appendChild(pagesNav);

    aside.appendChild(sectionLabel("FE Tools"));
    const toolsNav = document.createElement("nav");
    toolsNav.className = "tools-nav";
    toolsNav.id = "tools-nav";
    const currentHash = location.hash;
    TOOLS.forEach((t) => toolsNav.appendChild(toolLink(t, onTools, currentHash)));
    aside.appendChild(toolsNav);
  }

  function init() {
    ensureBodyClass();
    let aside = document.querySelector(".tools-sidebar");
    if (!aside) aside = buildRail();
    if (!aside) return;
    render(aside);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
