/*
  filename: industries.js
  description: Renders the /industries.html catalog. Loads the 20 industries from /api/v1/industries, filters across name + summary + persona role + regulation + competitor id, and opens a detail modal that deep-links into /battlecards.html, /demo-data.html, and /tools.html so a Field Engineer can jump from "what industry am I selling into" to "show me the asset" in one click.
  Author: Rodrigo Careaga
  Date: 04-05-2026
*/
(function () {
  // ============================================================
  // Data + state
  // ============================================================
  const STATE = {
    items: [],
    filtered: [],
    activeId: null,
    debounceTimer: null,
  };

  // Map battlecard id ("battlecard-splunk") to a friendly competitor label.
  const COMPETITOR_LABELS = {
    "battlecard-splunk": "Splunk",
    "battlecard-datadog": "Datadog",
    "battlecard-sumologic": "Sumo Logic",
    "battlecard-microsoft-sentinel": "Microsoft Sentinel",
    "battlecard-chronicle": "Chronicle",
    "battlecard-qradar": "QRadar",
    "battlecard-exabeam": "Exabeam",
    "battlecard-grafana": "Grafana",
    "battlecard-graylog": "Graylog",
    "battlecard-honeycomb": "Honeycomb",
    "battlecard-loki": "Loki",
    "battlecard-new-relic": "New Relic",
    "battlecard-dynatrace": "Dynatrace",
    "battlecard-appdynamics": "AppDynamics",
    "battlecard-cribl": "Cribl",
    "battlecard-coveo": "Coveo",
    "battlecard-algolia": "Algolia",
    "battlecard-typesense": "Typesense",
    "battlecard-meilisearch": "Meilisearch",
    "battlecard-lucidworks": "Lucidworks",
    "battlecard-aws-opensearch": "AWS OpenSearch",
    "battlecard-pinecone": "Pinecone",
    "battlecard-weaviate": "Weaviate",
    "battlecard-milvus": "Milvus",
    "battlecard-crowdstrike": "CrowdStrike",
    "battlecard-sentinelone": "SentinelOne",
    "dragos": "Dragos",
    "wiz": "Wiz",
    "cisco-appd-splunk-bundle": "Cisco AppD + Splunk",
    "servicenow-itom": "ServiceNow ITOM",
    "splunk-cloud": "Splunk Cloud",
  };

  const SCENARIO_LABELS = {
    "black-friday": "Black Friday outage",
    "credstuff": "Credential stuffing",
    "noisy-microservice": "Noisy microservice",
    "gdpr-audit": "GDPR audit",
    "supply-chain": "Supply-chain attack",
    "fsi-banking-fraud": "FSI banking fraud",
    "healthcare-hipaa-audit": "Healthcare HIPAA audit",
    "gov-cdm-compliance": "Gov CDM compliance",
  };

  const TOOL_LABELS = {
    "fec_poc_plan": "POC plan",
    "fec_spl_to_esql": "SPL to ES|QL",
    "fec_compliance": "Compliance",
    "fec_stack_extract": "Stack extract",
    "fec_code_sample": "Code sample",
    "fec_cost_calc": "Cost calculator",
    "fec_capacity": "Capacity",
    "fec_knowledge_search": "Knowledge search",
    "fec_troubleshoot": "Troubleshoot",
    "fec_compare": "Compare",
    "fec_orchestrator": "Orchestrator",
    "fec_proposal": "Proposal",
  };

  // Lightweight inline icon set keyed by `icon` field on each industry. Falls back to a bullseye glyph.
  const ICONS = {
    bank: '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21h18"/><path d="M5 21V10"/><path d="M19 21V10"/><path d="M9 21v-7"/><path d="M15 21v-7"/><path d="M3 10 12 4l9 6"/></svg>',
    "shield-check": '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3 4 6v6c0 5 3.5 8.5 8 9 4.5-.5 8-4 8-9V6Z"/><path d="m9 12 2 2 4-4"/></svg>',
    "trending-up": '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 17 9 11 13 15 21 7"/><polyline points="14 7 21 7 21 14"/></svg>',
    landmark: '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21h18"/><path d="M3 10h18"/><path d="M5 21V10"/><path d="M19 21V10"/><path d="M9 21V10"/><path d="M15 21V10"/><path d="M12 3 3 8h18Z"/></svg>',
    building: '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 7h2"/><path d="M14 7h2"/><path d="M8 11h2"/><path d="M14 11h2"/><path d="M8 15h8"/><path d="M10 21v-3h4v3"/></svg>',
    stethoscope: '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 3v6a4 4 0 0 0 8 0V3"/><path d="M4 3h2"/><path d="M10 3h2"/><path d="M8 13v3a5 5 0 0 0 10 0v-2"/><circle cx="18" cy="11" r="2"/></svg>',
    "clipboard-check": '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="4" width="12" height="17" rx="2"/><path d="M9 4V2h6v2"/><path d="m9 13 2 2 4-4"/></svg>',
    "flask-conical": '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 3v6L4 19a2 2 0 0 0 2 3h12a2 2 0 0 0 2-3l-5-10V3"/><path d="M8 3h8"/><path d="M7 14h10"/></svg>',
    "shopping-cart": '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="21" r="1"/><circle cx="18" cy="21" r="1"/><path d="M3 3h2l3 12h12l2-8H6"/></svg>',
    store: '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9 5 4h14l2 5"/><path d="M3 9v11h18V9"/><path d="M3 9c0 1.7 1.3 3 3 3s3-1.3 3-3c0 1.7 1.3 3 3 3s3-1.3 3-3c0 1.7 1.3 3 3 3s3-1.3 3-3"/><path d="M9 20v-6h6v6"/></svg>',
    "radio-tower": '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 6c-2 2-2 6 0 8"/><path d="M19 6c2 2 2 6 0 8"/><path d="M8 8c-1 1-1 3 0 4"/><path d="M16 8c1 1 1 3 0 4"/><circle cx="12" cy="10" r="1.5"/><path d="m12 11 2 11h-4Z"/></svg>',
    "play-circle": '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><polygon points="10,8 16,12 10,16"/></svg>',
    cloud: '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 18a4 4 0 0 0 0-8 6 6 0 0 0-11.3 2A4 4 0 0 0 6 18Z"/></svg>',
    factory: '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21V10l5 4V10l5 4V8l8 5v8Z"/><path d="M7 17h2"/><path d="M12 17h2"/><path d="M17 17h2"/></svg>',
    beaker: '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 3v6L4 19a2 2 0 0 0 2 3h12a2 2 0 0 0 2-3l-5-10V3"/><path d="M7 3h10"/></svg>',
    zap: '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 4 14 11 14 10 22 20 10 13 10 13 2"/></svg>',
    truck: '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="1" y="6" width="14" height="11" rx="1"/><path d="M15 9h5l3 4v4h-8"/><circle cx="6" cy="19" r="2"/><circle cx="18" cy="19" r="2"/></svg>',
    plane: '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12h6l4-8h2l-2 8h6l3-3h2l-2 5 2 5h-2l-3-3h-6l2 8h-2l-4-8H2Z"/></svg>',
    car: '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 17H3v-5l2-5h14l2 5v5h-2"/><circle cx="7" cy="17" r="2"/><circle cx="17" cy="17" r="2"/><path d="M5 12h14"/></svg>',
    rocket: '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 4c4 0 6 2 6 6-1 6-6 10-6 10l-4-4S14 11 14 4Z"/><path d="M9 11 5 9 4 5l4 1 2 4Z"/><path d="M14 13l2 4-4 1Z"/><path d="M5 19c1-2 3-2 4 0"/></svg>',
    bullseye: '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.5"/></svg>',
  };

  function iconFor(name) {
    return ICONS[name] || ICONS.bullseye;
  }

  function competitorLabel(id) {
    return COMPETITOR_LABELS[id] || id;
  }
  function scenarioLabel(id) {
    return SCENARIO_LABELS[id] || id;
  }
  function toolLabel(id) {
    return TOOL_LABELS[id] || id;
  }

  function tx(key, fallback) {
    if (typeof window !== "undefined" && typeof window.t === "function") {
      const out = window.t(key, fallback);
      if (out) return out;
    }
    return fallback;
  }

  // ============================================================
  // Cards
  // ============================================================
  function buildCard(industry) {
    const card = el("article", {
      class: "ind-card",
      "data-id": industry.id,
      role: "button",
      tabindex: "0",
      "aria-label": industry.name,
    });
    const head = el("header", { class: "ind-card-head" });
    const iconWrap = el("span", { class: "ind-card-icon", "aria-hidden": "true" });
    iconWrap.innerHTML = iconFor(industry.icon);
    head.appendChild(iconWrap);
    head.appendChild(el("h3", { class: "ind-card-title" }, industry.name));
    card.appendChild(head);

    card.appendChild(el("p", { class: "ind-card-summary" }, industry.summary || ""));

    if (Array.isArray(industry.personas) && industry.personas.length) {
      const list = el("ul", { class: "ind-card-personas", "aria-label": "Top personas" });
      industry.personas.slice(0, 3).forEach((p) => {
        const li = el("li", { class: "ind-card-persona" }, [
          el("span", { class: "ind-card-persona-role" }, p.role),
          el("span", { class: "ind-card-persona-pain" }, p.pain),
        ]);
        list.appendChild(li);
      });
      card.appendChild(list);
    }

    if (Array.isArray(industry.regulations) && industry.regulations.length) {
      const chips = el("div", { class: "ind-chips", "aria-label": "Regulations" });
      industry.regulations.slice(0, 5).forEach((r) => {
        chips.appendChild(el("span", { class: "ind-chip ind-chip-reg" }, r));
      });
      if (industry.regulations.length > 5) {
        chips.appendChild(
          el("span", { class: "ind-chip ind-chip-more" }, "+" + (industry.regulations.length - 5))
        );
      }
      card.appendChild(chips);
    }

    const footer = el("footer", { class: "ind-card-footer" });
    const competitors = (industry.top_competitors || []).length;
    const scenarios = (industry.scenario_ids || []).length;
    const tools = (industry.tool_ids || []).length;
    footer.appendChild(
      el("span", { class: "ind-card-meta" }, [
        el("strong", null, String(competitors)),
        " ",
        tx("industries.card.competitors", "competitors"),
      ])
    );
    footer.appendChild(el("span", { class: "ind-card-sep", "aria-hidden": "true" }, "·"));
    footer.appendChild(
      el("span", { class: "ind-card-meta" }, [
        el("strong", null, String(scenarios)),
        " ",
        tx("industries.card.scenarios", "scenarios"),
      ])
    );
    footer.appendChild(el("span", { class: "ind-card-sep", "aria-hidden": "true" }, "·"));
    footer.appendChild(
      el("span", { class: "ind-card-meta" }, [
        el("strong", null, String(tools)),
        " ",
        tx("industries.card.tools", "tools"),
      ])
    );
    card.appendChild(footer);

    card.addEventListener("click", () => openModal(industry.id));
    card.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" || ev.key === " ") {
        ev.preventDefault();
        openModal(industry.id);
      }
    });
    return card;
  }

  function renderGrid(items) {
    const grid = document.getElementById("ind-grid");
    if (!grid) return;
    clear(grid);
    if (!items.length) {
      grid.appendChild(
        el("p", { class: "muted ind-empty" }, tx("industries.empty", "No industries match your filter."))
      );
      return;
    }
    items.forEach((it) => grid.appendChild(buildCard(it)));
    const counter = document.getElementById("ind-count");
    if (counter) {
      counter.textContent = items.length === STATE.items.length
        ? items.length + " " + tx("industries.shown.all", "industries")
        : items.length + " / " + STATE.items.length + " " + tx("industries.shown.filtered", "industries");
    }
  }

  // ============================================================
  // Search filter (debounced)
  // ============================================================
  function applyFilter(rawQuery) {
    const q = (rawQuery || "").trim().toLowerCase();
    if (!q) {
      STATE.filtered = STATE.items.slice();
      renderGrid(STATE.filtered);
      return;
    }
    STATE.filtered = STATE.items.filter((it) => {
      if ((it.name || "").toLowerCase().includes(q)) return true;
      if ((it.summary || "").toLowerCase().includes(q)) return true;
      if ((it.personas || []).some((p) => (p.role || "").toLowerCase().includes(q))) return true;
      if ((it.personas || []).some((p) => (p.pain || "").toLowerCase().includes(q))) return true;
      if ((it.regulations || []).some((r) => (r || "").toLowerCase().includes(q))) return true;
      if ((it.top_competitors || []).some((c) => (c || "").toLowerCase().includes(q))) return true;
      if ((it.top_competitors || []).some((c) => competitorLabel(c).toLowerCase().includes(q))) return true;
      return false;
    });
    renderGrid(STATE.filtered);
  }

  function bindSearch() {
    const input = document.getElementById("ind-search");
    if (!input) return;
    input.addEventListener("input", (ev) => {
      const value = ev.target.value || "";
      clearTimeout(STATE.debounceTimer);
      STATE.debounceTimer = setTimeout(() => applyFilter(value), 150);
    });
  }

  // ============================================================
  // Modal
  // ============================================================
  function competitorChip(id) {
    return el(
      "a",
      {
        class: "ind-chip ind-chip-link ind-chip-comp",
        href: "/battlecards.html?card=" + encodeURIComponent(id) + "#" + encodeURIComponent(id.replace(/^battlecard-/, "")),
        "data-deep-link": "battlecard",
      },
      competitorLabel(id)
    );
  }
  function scenarioChip(id) {
    return el(
      "a",
      {
        class: "ind-chip ind-chip-link ind-chip-scn",
        href: "/demo-data.html#" + encodeURIComponent(id),
        "data-deep-link": "scenario",
      },
      scenarioLabel(id)
    );
  }
  function toolChip(id) {
    return el(
      "a",
      {
        class: "ind-chip ind-chip-link ind-chip-tool",
        href: "/tools.html?run=" + encodeURIComponent(id),
        "data-deep-link": "tool",
      },
      toolLabel(id)
    );
  }

  function buildSection(title, children) {
    const section = el("section", { class: "ind-modal-section" }, [
      el("h4", { class: "ind-modal-section-title" }, title),
    ]);
    children.forEach((c) => section.appendChild(c));
    return section;
  }

  function renderModal(industry) {
    const titleNode = document.getElementById("ind-modal-title");
    const summaryNode = document.getElementById("ind-modal-summary");
    const iconNode = document.getElementById("ind-modal-icon");
    const body = document.getElementById("ind-modal-body");
    if (!titleNode || !body) return;
    titleNode.textContent = industry.name;
    if (summaryNode) summaryNode.textContent = industry.summary || "";
    if (iconNode) iconNode.innerHTML = iconFor(industry.icon);
    clear(body);

    // Personas
    if (Array.isArray(industry.personas) && industry.personas.length) {
      const list = el("ul", { class: "ind-personas-full", "aria-label": "Personas" });
      industry.personas.forEach((p) => {
        list.appendChild(
          el("li", { class: "ind-persona-row" }, [
            el("span", { class: "ind-persona-role" }, p.role),
            el("span", { class: "ind-persona-pain" }, p.pain),
          ])
        );
      });
      body.appendChild(buildSection(tx("industries.modal.personas", "Personas"), [list]));
    }

    // Regulations
    if (Array.isArray(industry.regulations) && industry.regulations.length) {
      const chips = el("div", { class: "ind-chips" });
      industry.regulations.forEach((r) => {
        chips.appendChild(el("span", { class: "ind-chip ind-chip-reg" }, r));
      });
      body.appendChild(buildSection(tx("industries.modal.regulations", "Regulations"), [chips]));
    }

    // Competitors (deep-link to /battlecards.html?card={id})
    if (Array.isArray(industry.top_competitors) && industry.top_competitors.length) {
      const chips = el("div", { class: "ind-chips" });
      industry.top_competitors.forEach((id) => chips.appendChild(competitorChip(id)));
      body.appendChild(buildSection(tx("industries.modal.competitors", "Top competitors"), [chips]));
    }

    // Scenarios (deep-link to /demo-data.html#{scenario_id})
    if (Array.isArray(industry.scenario_ids) && industry.scenario_ids.length) {
      const chips = el("div", { class: "ind-chips" });
      industry.scenario_ids.forEach((id) => chips.appendChild(scenarioChip(id)));
      body.appendChild(buildSection(tx("industries.modal.scenarios", "Demo scenarios"), [chips]));
    }

    // Tools (deep-link to /tools.html?run={tool_id})
    if (Array.isArray(industry.tool_ids) && industry.tool_ids.length) {
      const chips = el("div", { class: "ind-chips" });
      industry.tool_ids.forEach((id) => chips.appendChild(toolChip(id)));
      body.appendChild(buildSection(tx("industries.modal.tools", "FE Copilot tools"), [chips]));
    }

    // KPIs
    if (Array.isArray(industry.kpis) && industry.kpis.length) {
      const grid = el("div", { class: "ind-kpi-grid", "aria-label": "Key performance indicators" });
      industry.kpis.forEach((k) => {
        grid.appendChild(
          el("div", { class: "ind-kpi-cell" }, [
            el("div", { class: "ind-kpi-value" }, k.value),
            el("div", { class: "ind-kpi-metric" }, k.metric),
          ])
        );
      });
      body.appendChild(buildSection(tx("industries.modal.kpis", "KPIs Elastic moves"), [grid]));
    }

    // Wins / Loses callouts (honest)
    const callouts = el("div", { class: "ind-callout-row" });
    if (industry.elastic_wins_when) {
      callouts.appendChild(
        el("div", { class: "ind-callout ind-callout-wins" }, [
          el("div", { class: "ind-callout-lbl" }, tx("industries.modal.wins_when", "Elastic wins when")),
          el("p", { class: "ind-callout-text" }, industry.elastic_wins_when),
        ])
      );
    }
    if (industry.elastic_loses_when) {
      callouts.appendChild(
        el("div", { class: "ind-callout ind-callout-loses" }, [
          el("div", { class: "ind-callout-lbl" }, tx("industries.modal.loses_when", "Elastic loses when")),
          el("p", { class: "ind-callout-text" }, industry.elastic_loses_when),
        ])
      );
    }
    if (callouts.childElementCount) body.appendChild(callouts);
  }

  // Focus-trap helpers for the industries modal (WCAG 2.4.3 Focus Order, ARIA APG dialog pattern).
  let _indModalLastFocus = null;
  function _indFocusableInModal() {
    const modal = document.getElementById("ind-modal");
    if (!modal) return [];
    const sel = [
      "a[href]",
      "button:not([disabled])",
      "input:not([disabled]):not([type='hidden'])",
      "select:not([disabled])",
      "textarea:not([disabled])",
      "[tabindex]:not([tabindex='-1'])",
    ].join(",");
    return Array.from(modal.querySelectorAll(sel)).filter(
      (n) => !n.hasAttribute("hidden") && n.offsetParent !== null
    );
  }
  function _indModalKeyTrap(ev) {
    const modal = document.getElementById("ind-modal");
    if (!modal || modal.hidden) return;
    if (ev.key !== "Tab") return;
    const list = _indFocusableInModal();
    if (!list.length) return;
    const first = list[0];
    const last = list[list.length - 1];
    if (ev.shiftKey && document.activeElement === first) {
      ev.preventDefault();
      last.focus();
    } else if (!ev.shiftKey && document.activeElement === last) {
      ev.preventDefault();
      first.focus();
    }
  }

  function openModal(id) {
    const industry = STATE.items.find((it) => it.id === id);
    if (!industry) return;
    STATE.activeId = id;
    renderModal(industry);
    const modal = document.getElementById("ind-modal");
    if (!modal) return;
    // Remember the trigger so we can restore focus on close.
    _indModalLastFocus = document.activeElement;
    modal.hidden = false;
    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", _indModalKeyTrap);
    // Update URL so the modal is shareable.
    try {
      const url = new URL(location.href);
      url.searchParams.set("industry", id);
      history.replaceState(null, "", url.toString());
    } catch (_e) {
      /* ignore */
    }
    // Focus the close button so keyboard users can dismiss immediately.
    setTimeout(() => {
      const btn = modal.querySelector(".ind-modal-close");
      if (btn) btn.focus();
    }, 30);
  }

  function closeModal() {
    const modal = document.getElementById("ind-modal");
    if (!modal) return;
    modal.hidden = true;
    document.body.style.overflow = "";
    document.removeEventListener("keydown", _indModalKeyTrap);
    STATE.activeId = null;
    try {
      const url = new URL(location.href);
      url.searchParams.delete("industry");
      history.replaceState(null, "", url.toString());
    } catch (_e) {
      /* ignore */
    }
    // Restore focus to the trigger that opened the modal (WCAG 2.4.3).
    if (_indModalLastFocus && typeof _indModalLastFocus.focus === "function") {
      try { _indModalLastFocus.focus(); } catch (_e) { /* ignore */ }
    }
    _indModalLastFocus = null;
  }

  function bindModal() {
    const modal = document.getElementById("ind-modal");
    if (!modal) return;
    modal.addEventListener("click", (ev) => {
      const target = ev.target;
      if (target && target.matches && target.matches("[data-ind-close], [data-ind-close] *")) {
        closeModal();
      }
    });
    document.addEventListener("keydown", (ev) => {
      if (ev.key === "Escape" && !modal.hidden) {
        closeModal();
      }
    });
  }

  // ============================================================
  // Boot
  // ============================================================
  async function load() {
    try {
      const data = await apiGet("/industries");
      STATE.items = Array.isArray(data && data.items) ? data.items : [];
      STATE.filtered = STATE.items.slice();
      renderGrid(STATE.filtered);
      // Honor ?industry=<id> on first load (deep link from email, Slack, etc).
      const initial = getQueryParam("industry");
      if (initial) {
        const match = STATE.items.find((it) => it.id === initial);
        if (match) openModal(match.id);
      }
    } catch (e) {
      const grid = document.getElementById("ind-grid");
      if (grid) {
        clear(grid);
        grid.appendChild(
          el("p", { class: "muted" }, "Failed to load industries: " + (e && e.message ? e.message : "unknown error"))
        );
      }
    }
  }

  function init() {
    bindSearch();
    bindModal();
    load();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
