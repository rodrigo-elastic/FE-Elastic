/*
  filename: presales-playbook.js
  description: Renders the SKO 2026 pre-sales framework cards on the meeting.html Brief tab. Prefers the account-specific playbook the Pre-Meeting agent produced (brief.presales_playbook); falls back to the generic Search 101 + Observability cards only when the agent did not emit one. Headings (Listen for / Say / Ask, Lead with the platform / Avoid the bake-off / Qualify hard) come from the slides; the body text on the agent-filled path is per-account.
  Author: Rodrigo Careaga
  Date: 05-13-2026
*/
(function () {
  "use strict";

  // Canonical headings per framework (order matters; the agent emits them in this order).
  const FRAMEWORK_META = {
    search: {
      label: "Search / AI retrieval",
      pillClass: "teal",
      title: "How to talk with customers (Search 101)",
      headings: ["Listen for", "Say", "Ask"],
      fallback: {
        "Listen for": "Inconsistent relevance. Scalability and performance issues. Difficulty measuring success.",
        "Say": "“This isn’t just search, it’s the retrieval layer for AI.” / “You control relevance, not the vendor.”",
        "Ask": "What happens today when search isn’t optimized?",
      },
    },
    observability: {
      label: "Observability / SIEM / APM",
      pillClass: "blue",
      title: "How NOT to sell (Observability)",
      headings: ["Lead with the platform", "Avoid the bake-off", "Qualify hard"],
      fallback: {
        "Lead with the platform": "Elastic is a platform. Do NOT start with standalone features like Metrics, APM, or Case Management.",
        "Avoid the bake-off": "Don’t let the deal become a price or feature bake-off. Anchor on platform consolidation and TCO.",
        "Qualify hard": "No owner. No pain. No timeline. No deal.",
      },
    },
  };

  function detectVerticalFromContent(text) {
    const haystack = String(text || "").toLowerCase();
    const obsHits = (haystack.match(/observability|siem|apm|datadog|splunk|sumo logic|grafana|new relic|dynatrace|metrics|tracing|on-call|sre/g) || []).length;
    const searchHits = (haystack.match(/search|relevance|elser|vector|semantic|retrieval|rag|recommendation|marketplace|catalog|opensearch/g) || []).length;
    if (searchHits > obsHits * 1.2) return "search";
    if (obsHits > searchHits * 1.2) return "observability";
    return "both";
  }

  function el(tag, attrs, children) {
    const n = document.createElement(tag);
    if (attrs) {
      for (const k of Object.keys(attrs)) {
        if (k === "class") n.className = attrs[k];
        else if (k === "html") n.innerHTML = attrs[k];
        else n.setAttribute(k, attrs[k]);
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

  // Build a card from a block emitted by the agent. The agent's items array
  // should match the framework's canonical heading order, but we re-key by
  // heading so any out-of-order emission still renders cleanly.
  function renderBlock(block, opts) {
    const fwk = block && block.framework;
    const meta = FRAMEWORK_META[fwk];
    if (!meta) return null;
    const itemsByHeading = {};
    (block.items || []).forEach((it) => {
      if (it && it.heading) itemsByHeading[it.heading] = it.body || "";
    });

    const wrap = el("div", { class: "psp-card psp-" + fwk });
    const head = el("div", { class: "psp-head" }, [
      el("span", { class: "psp-pill psp-pill-" + meta.pillClass }, meta.label),
      el("h3", { class: "psp-title" }, meta.title),
      opts && opts.agentFilled
        ? el("span", { class: "psp-agent-flag", title: "Filled by the Pre-Meeting agent from this account's dossier." }, "Account-specific")
        : el("span", { class: "psp-agent-flag psp-generic", title: "Generic framework text. Run the Pre-Meeting agent to fill these for this account." }, "Generic"),
    ]);
    wrap.appendChild(head);

    const cols = el("div", { class: "psp-cols" });
    meta.headings.forEach((h) => {
      const body = itemsByHeading[h] || (meta.fallback[h] || "");
      const col = el("div", { class: "psp-col" });
      col.appendChild(el("div", { class: "psp-col-head" }, h));
      col.appendChild(el("p", { class: "psp-col-body" }, body));
      cols.appendChild(col);
    });
    wrap.appendChild(cols);

    wrap.appendChild(
      el(
        "div",
        { class: "psp-foot" },
        "SKO 2026 enablement card. Surface this in the next 5 minutes of the call."
      )
    );
    return wrap;
  }

  // Build the "generic" fallback block for a framework when the agent did
  // not emit one, so the FE still sees the playbook structure.
  function makeGenericBlock(framework) {
    const meta = FRAMEWORK_META[framework];
    if (!meta) return null;
    return {
      framework,
      items: meta.headings.map((h) => ({ heading: h, body: meta.fallback[h] })),
    };
  }

  function render(brief) {
    const host = document.getElementById("presales-playbook");
    if (!host) return;
    host.innerHTML = "";

    const playbook = brief && brief.presales_playbook;
    const cards = [];
    if (playbook && playbook.primary && Array.isArray(playbook.primary.items) && playbook.primary.items.length) {
      cards.push({ block: playbook.primary, agentFilled: true });
      if (playbook.secondary && Array.isArray(playbook.secondary.items) && playbook.secondary.items.length) {
        cards.push({ block: playbook.secondary, agentFilled: true });
      }
    } else {
      // Fall back to heuristic vertical detection on the brief content.
      const blob = JSON.stringify(brief || {}) + " " + (brief && brief._dom ? brief._dom : "");
      const v = detectVerticalFromContent(blob);
      if (v === "search" || v === "both") cards.push({ block: makeGenericBlock("search"), agentFilled: false });
      if (v === "observability" || v === "both") cards.push({ block: makeGenericBlock("observability"), agentFilled: false });
    }

    if (!cards.length) return;
    const root = el("section", { class: "psp-root" });
    root.appendChild(el("div", { class: "psp-section-title" }, "Pre-sales playbook"));
    cards.forEach((c) => {
      const node = renderBlock(c.block, { agentFilled: c.agentFilled });
      if (node) root.appendChild(node);
    });
    host.appendChild(root);
  }

  function injectStyles() {
    if (document.getElementById("psp-styles")) return;
    const s = document.createElement("style");
    s.id = "psp-styles";
    s.textContent = [
      ".psp-root { margin-top: 18px; display: flex; flex-direction: column; gap: 14px; }",
      ".psp-section-title { font-size: 11px; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; color: var(--muted, #8a8f98); }",
      ".psp-card { border: 1px solid var(--border, #2a2f3a); border-radius: 12px; padding: 16px 18px; background: linear-gradient(180deg, var(--panel, #161a23) 0%, var(--panel-2, #11141c) 100%); }",
      ".psp-head { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; flex-wrap: wrap; }",
      ".psp-title { margin: 0; font-size: 15px; font-weight: 700; color: var(--ink, #e6e8eb); flex: 1; min-width: 220px; }",
      ".psp-pill { font-size: 11px; font-weight: 700; padding: 4px 10px; border-radius: 999px; color: #0a0d14; }",
      ".psp-pill-teal { background: #00BFB3; }",
      ".psp-pill-blue { background: #1BA9F5; }",
      ".psp-agent-flag { font-size: 10px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; padding: 3px 8px; border-radius: 999px; background: rgba(0, 191, 179, 0.15); color: #00BFB3; border: 1px solid rgba(0, 191, 179, 0.4); }",
      ".psp-agent-flag.psp-generic { background: rgba(138, 143, 152, 0.12); color: var(--muted, #8a8f98); border-color: var(--border, #2a2f3a); }",
      ".psp-cols { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }",
      "@media (max-width: 768px) { .psp-cols { grid-template-columns: 1fr; } }",
      ".psp-col { background: rgba(255,255,255,0.02); border: 1px solid var(--border-soft, #232733); border-radius: 8px; padding: 10px 12px; }",
      ".psp-col-head { font-size: 11px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: #00BFB3; margin-bottom: 8px; }",
      ".psp-observability .psp-col-head { color: #1BA9F5; }",
      ".psp-col-body { margin: 0; font-size: 13px; line-height: 1.5; color: var(--ink, #e6e8eb); }",
      ".psp-foot { margin-top: 12px; font-size: 11px; color: var(--muted, #8a8f98); font-style: italic; }",
    ].join("\n");
    document.head.appendChild(s);
  }

  injectStyles();
  window.renderPresalesPlaybook = render;

  // Auto-render once meeting.js stashes the brief on window.__lastBrief.
  let lastHash = null;
  const observer = new MutationObserver(() => {
    const briefHost = document.getElementById("brief");
    if (!briefHost) return;
    const hasBrief = briefHost.querySelector(".brief-headline, .brief-section, h1, h2, h3, ul, ol");
    if (hasBrief) {
      const brief = window.__lastBrief || { _dom: briefHost.textContent || "" };
      const hash = JSON.stringify(brief && brief.presales_playbook ? brief.presales_playbook : brief && brief.headline);
      if (hash !== lastHash) {
        lastHash = hash;
        render(brief);
      }
    } else {
      const host = document.getElementById("presales-playbook");
      if (host) host.innerHTML = "";
      lastHash = null;
    }
  });
  const arm = () => {
    const target = document.getElementById("brief");
    if (target) observer.observe(target, { childList: true, subtree: true });
  };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", arm);
  } else {
    arm();
  }
})();
