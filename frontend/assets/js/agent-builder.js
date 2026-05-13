/*
  filename: agent-builder.js
  description: Drives the Agent Builder workbench. Loads status + the agent roster from Kibana via the FastAPI passthrough, lets the user build new specialist agents (system prompt + tool picker) that get persisted server-side, and routes chat to whichever agent is selected in the sidebar. Conversation_id is keyed per agent in localStorage.
  Author: Rodrigo Careaga
  Date: 03-05-2026
*/
(function () {
  const STORAGE_PREFIX = "fec.agent_builder.conv.";
  const SELECTED_KEY = "fec.agent_builder.selected_agent";
  const MASTER_AGENT_ID = "fec_field_assistant";
  const USER_AGENT_PREFIX = "fec_user_";

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  // Suggested prompts per FEC tool. Used to build chips above the chat that reflect what the
  // currently selected agent can actually do. Keep these short and FE-flavored.
  const TOOL_PROMPTS = {
    fec_poc_plan: "Draft a 6 week POV plan for Banco Atlántico focused on SIEM consolidation",
    fec_spl_to_esql: "Translate this SPL to ES|QL: index=web | stats count by host",
    fec_compliance: "Map DORA and PCI DSS to Elastic native controls for a UK retail bank",
    fec_stack_extract: "Extract the tech stack from this transcript: 'we run Splunk Enterprise, Datadog APM, AWS, Kafka, Java services'",
    fec_code_sample: "Show a Python sample to bulk-index 1000 docs into Elastic with the official client",
    fec_cost_calc: "Calculate Elastic vs Splunk cost at 200 GB/day, 12 months retention, current spend $1.5M",
    fec_capacity: "Plan a cluster for 50000 EPS peak indexing and 5TB hot data",
    fec_knowledge_search: "How do I configure semantic_text with ELSER in Elasticsearch 8.15?",
    fec_troubleshoot: "I am seeing 429 too_many_requests on bulk indexing, what should I check?",
    fec_compare: "Compare Elastic vs Datadog for an e-commerce observability use case",
    fec_orchestrator: "Build a security POV for a fintech: compliance + cost + cluster sizing",
    fec_proposal: "Generate a one-page proposal for Banco Atlántico, include the 60 hour POV",
    fec_deploy_validator: "Validate this cluster: 3-node Elastic Cloud, security disabled, 80 shards on hot tier, no SLM",
    fec_pov_health: "How is this trial doing? Atlas Health, week 3 of 8, 12 GB/day, 1 dashboard, no SLOs, single user",
  };

  // Friendly labels for the tool picker. Falls back to the raw id when the tool is unknown locally.
  const TOOL_LABELS = {
    fec_poc_plan: "POC plan generator (Marta)",
    fec_spl_to_esql: "SPL to ES|QL (Diego)",
    fec_compliance: "Compliance mapper (Priya)",
    fec_stack_extract: "Tech stack extractor (Aiko)",
    fec_code_sample: "SDK code sample (Kenji)",
    fec_cost_calc: "TCO calculator",
    fec_capacity: "Cluster capacity planner",
    fec_knowledge_search: "Docs knowledge search (Mei)",
    fec_troubleshoot: "Troubleshooter (Ravi)",
    fec_compare: "Competitive comparison (Sloane)",
    fec_orchestrator: "Orchestrator (Auro)",
    fec_proposal: "One-page proposal (Carmen)",
    fec_deploy_validator: "Deployment validator (Astrid)",
    fec_pov_health: "POV health monitor (Lina)",
  };

  // Categorization for the modal tool picker. Four groups, rendered in this exact order:
  // Research, Compete, Sizing, Build. Tools without a mapping fall back to "Other".
  const TOOL_CATEGORIES = {
    fec_knowledge_search: "Research",
    fec_orchestrator:     "Research",
    fec_compare:          "Compete",
    fec_compliance:       "Compete",
    fec_proposal:         "Compete",
    fec_cost_calc:        "Sizing",
    fec_capacity:         "Sizing",
    fec_poc_plan:         "Sizing",
    fec_spl_to_esql:      "Build",
    fec_code_sample:      "Build",
    fec_stack_extract:    "Build",
    fec_troubleshoot:     "Build",
    fec_deploy_validator: "Sizing",
    fec_pov_health:       "Sizing",
  };

  // Display order + i18n keys for the four sections. Anything not in this list is grouped at the bottom under "Other".
  const CATEGORY_ORDER = ["Research", "Compete", "Sizing", "Build"];
  const CATEGORY_I18N = {
    Research: "ab.tool.section.research",
    Compete:  "ab.tool.section.compete",
    Sizing:   "ab.tool.section.sizing",
    Build:    "ab.tool.section.build",
  };

  // Recommended bundles. A click overwrites the current selection with the bundle's tool ids.
  // Each bundle reflects a real FE workflow. Hover the chip for the description.
  const TOOL_BUNDLES = [
    { id: "rfp",          i18n: "ab.tool.bundle.rfp",          label: "RFP",                tools: ["fec_knowledge_search", "fec_compare", "fec_compliance", "fec_proposal"], desc: "Drafts cited RFP answers with battlecard support" },
    { id: "migration",    i18n: "ab.tool.bundle.migration",    label: "Migration",          tools: ["fec_spl_to_esql", "fec_cost_calc", "fec_capacity", "fec_compliance", "fec_proposal"], desc: "Splunk or Datadog to Elastic, phased plan plus TCO" },
    { id: "sizing",       i18n: "ab.tool.bundle.sizing",       label: "Sizing",             tools: ["fec_capacity", "fec_cost_calc", "fec_poc_plan"], desc: "Cluster sizing plus 12-month TCO plus POV plan" },
    { id: "discovery",    i18n: "ab.tool.bundle.discovery",    label: "Discovery",          tools: ["fec_stack_extract", "fec_knowledge_search", "fec_compare"], desc: "Pull stack from a transcript, ask the docs, compare" },
    { id: "competitive",  i18n: "ab.tool.bundle.competitive",  label: "Competitive",        tools: ["fec_compare", "fec_cost_calc", "fec_proposal", "fec_knowledge_search"], desc: "Replace Splunk, Datadog, Dynatrace, OpenSearch, Algolia" },
    { id: "compliance",   i18n: "ab.tool.bundle.compliance",   label: "Compliance",         tools: ["fec_compliance", "fec_knowledge_search", "fec_proposal"], desc: "DORA, HIPAA, FedRAMP, PCI DSS mapped to Elastic" },
    { id: "pov_legacy",   i18n: "ab.tool.bundle.pov_legacy",   label: "POV (legacy)",       tools: ["fec_poc_plan", "fec_capacity", "fec_code_sample", "fec_knowledge_search"], desc: "Original POV bundle: end-to-end proof-of-value with code samples" },
    { id: "pov",          i18n: "ab.tool.bundle.pov",          label: "POV ops",            tools: ["fec_pov_health", "fec_poc_plan", "fec_capacity", "fec_compliance"], desc: "Run a weekly POV health check, plan the next step, size the cluster" },
    { id: "troubleshoot", i18n: "ab.tool.bundle.troubleshoot", label: "Troubleshoot",       tools: ["fec_troubleshoot", "fec_knowledge_search", "fec_code_sample"], desc: "Diagnose stack errors, ES|QL queries, code fixes" },
    { id: "renewal",      i18n: "ab.tool.bundle.renewal",      label: "Renewal defense",    tools: ["fec_compare", "fec_cost_calc", "fec_compliance", "fec_proposal"], desc: "Retention play with comp, ROI, compliance angle" },
    { id: "build",        i18n: "ab.tool.bundle.build",        label: "Build",              tools: ["fec_code_sample", "fec_stack_extract", "fec_knowledge_search", "fec_troubleshoot"], desc: "Hands-on integration: SDK samples, stack, fixes" },
    { id: "exec",         i18n: "ab.tool.bundle.exec",         label: "Exec briefing",      tools: ["fec_proposal", "fec_compare", "fec_cost_calc", "fec_orchestrator"], desc: "C-level pitch: proposal, comp, ROI orchestrated" },
    { id: "search",       i18n: "ab.tool.bundle.search",       label: "Search architect",   tools: ["fec_knowledge_search", "fec_code_sample", "fec_capacity", "fec_compare"], desc: "RAG, semantic_text, ELSER, hybrid retrieval" },
    { id: "platform",     i18n: "ab.tool.bundle.platform",     label: "Platform health",    tools: ["fec_deploy_validator", "fec_pov_health", "fec_capacity", "fec_troubleshoot", "fec_knowledge_search"], desc: "Audit a cluster, watch trial health, size it right, fix what is broken" },
    { id: "all",          i18n: "ab.tool.bundle.all",          label: "All fourteen",       tools: ["fec_poc_plan","fec_spl_to_esql","fec_compliance","fec_stack_extract","fec_code_sample","fec_cost_calc","fec_capacity","fec_knowledge_search","fec_troubleshoot","fec_compare","fec_orchestrator","fec_proposal","fec_deploy_validator","fec_pov_health"], desc: "Master generalist: pick everything" },
    { id: "clear",        i18n: "ab.tool.bundle.clear",        label: "Clear",              tools: [], desc: "Deselect all" },
  ];

  // Truncate a tool description to the first sentence or 110 chars, whichever is shorter.
  // Returns the trimmed string. Caller is responsible for putting the full text in title="...".
  function shortDescription(desc) {
    const raw = String(desc || "").trim();
    if (!raw) return "";
    // First sentence: stop at the first ". " followed by a capital, or first newline.
    let cut = raw.length;
    const firstNewline = raw.indexOf("\n");
    if (firstNewline > 0) cut = Math.min(cut, firstNewline);
    const firstPeriod = raw.search(/\.\s+[A-Z(]/);
    if (firstPeriod > 0) cut = Math.min(cut, firstPeriod + 1);
    if (cut > 110) cut = 110;
    let out = raw.slice(0, cut).trim();
    if (out.length < raw.length && !/[.!?]$/.test(out)) out += "...";
    return out;
  }

  const state = {
    inFlight: false,
    abortCtrl: null,
    kibanaUrl: null,
    agentId: localStorage.getItem(SELECTED_KEY) || MASTER_AGENT_ID,
    agents: [],
    tools: [],
    conversationId: null,
  };

  // ============================================================ Render helpers
  function el(tag, attrs = {}, children = []) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === "class") node.className = v;
      else if (k === "html") node.innerHTML = v;
      else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
      else if (v != null) node.setAttribute(k, v);
    }
    (Array.isArray(children) ? children : [children]).forEach((c) => {
      if (c == null) return;
      node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    });
    return node;
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  // Lightweight Markdown-ish renderer. Handles **bold**, `code`, ```fenced```, bullets, line breaks.
  // Robust markdown renderer: ATX headings, fenced code, inline code,
  // bold, italic, links, ul/ol, blockquote, hr, paragraphs. Mirrors the
  // implementation in agent-builder-mini.js.
  function renderMarkdown(text) {
    if (text == null) return "";
    let src = String(text);
    const codeBlocks = [];
    // Sentinel must survive trim/escapeHtml/paragraph wrapping. The previous
    // " CODE0 " (with surrounding spaces) lost its trailing space when the
    // paragraph builder trimmed each line, leaving a literal "CODE0" string
    // visible to the user. Use a unique multi-char marker that no plausible
    // user content contains and that won't be munged by trim() or escapeHtml.
    src = src.replace(/```([a-zA-Z0-9_+\-]*)\n?([\s\S]*?)```/g, (_, lang, code) => {
      const i = codeBlocks.length;
      codeBlocks.push({ lang: String(lang || "").trim(), code: String(code || "") });
      return "\n__FECBLOCK_" + i + "__\n";
    });
    src = escapeHtml(src);
    const lines = src.split(/\n/);
    const out = [];
    let i = 0;
    function flushPara(buf) { if (buf.length) out.push("<p>" + buf.join(" ") + "</p>"); }
    while (i < lines.length) {
      const ln = lines[i];
      if (/^\s*(?:-{3,}|\*{3,})\s*$/.test(ln)) { out.push("<hr>"); i++; continue; }
      const h = /^(\#{1,6})\s+(.+?)\s*#*\s*$/.exec(ln);
      if (h) { out.push("<h" + h[1].length + ">" + h[2] + "</h" + h[1].length + ">"); i++; continue; }
      if (/^>\s?/.test(ln)) {
        const buf = [];
        while (i < lines.length && /^>\s?/.test(lines[i])) { buf.push(lines[i].replace(/^>\s?/, "")); i++; }
        out.push("<blockquote>" + buf.join("<br>") + "</blockquote>");
        continue;
      }
      if (/^\s*[-*]\s+/.test(ln)) {
        const buf = [];
        while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) { buf.push("<li>" + lines[i].replace(/^\s*[-*]\s+/, "") + "</li>"); i++; }
        out.push("<ul>" + buf.join("") + "</ul>");
        continue;
      }
      if (/^\s*\d+\.\s+/.test(ln)) {
        const buf = [];
        while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) { buf.push("<li>" + lines[i].replace(/^\s*\d+\.\s+/, "") + "</li>"); i++; }
        out.push("<ol>" + buf.join("") + "</ol>");
        continue;
      }
      if (/^\s*$/.test(ln)) { i++; continue; }
      const buf = [];
      while (i < lines.length
             && !/^\s*$/.test(lines[i])
             && !/^(\#{1,6})\s+/.test(lines[i])
             && !/^\s*(?:-{3,}|\*{3,})\s*$/.test(lines[i])
             && !/^\s*[-*]\s+/.test(lines[i])
             && !/^\s*\d+\.\s+/.test(lines[i])
             && !/^>\s?/.test(lines[i])) {
        buf.push(lines[i].trim());
        i++;
      }
      flushPara(buf);
    }
    let html = out.join("\n");
    html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/__([^_]+)__/g, "<strong>$1</strong>");
    // Italic: leading boundary includes ">" (block pass wraps in <p>).
    html = html.replace(/(^|[\s(>])\*([^*\n]+)\*/g, "$1<em>$2</em>");
    html = html.replace(/(^|[\s(>])_([^_\n]+)_/g, "$1<em>$2</em>");
    html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
    html = html.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
    html = html.replace(/__FECBLOCK_(\d+)__/g, (_, n) => {
      const block = codeBlocks[+n] || { lang: "", code: "" };
      const cls = block.lang ? ' class="lang-' + escapeHtml(block.lang) + '"' : "";
      return "<pre><code" + cls + ">" + escapeHtml(block.code) + "</code></pre>";
    });
    return html;
  }

  // ============================================================ Status
  // W25C: when Kibana is unreachable (no API key or ngrok tunnel down) we
  // surface a friendly toast plus a red status pill instead of a silent empty
  // state. The page itself stays usable - the master agent and tool pickers
  // are local catalogues, so judges can still read the workbench.
  let _kibanaToastShown = false;
  async function loadStatus() {
    try {
      const s = await apiGet("/agent-builder/status");
      state.kibanaUrl = s.kibana_url || null;
      const pillStatus = $("#ab-pill-status");
      const pillTools = $("#ab-pill-tools");
      const pillKibana = $("#ab-pill-kibana");
      pillStatus.textContent = s.live ? "Live" : "Dry-run";
      pillStatus.classList.remove("ab-pill-muted");
      pillStatus.classList.add(s.live ? "ab-pill-ok" : "ab-pill-err");
      pillTools.textContent = `${(s.configured_tools || []).length} MCP tools`;
      pillTools.classList.remove("ab-pill-muted");
      pillTools.classList.add("ab-pill-ok");
      if (state.kibanaUrl) {
        pillKibana.href = state.kibanaUrl + "/app/agent_builder/agents";
        const sidebarBtn = $("#ab-sidebar-kibana");
        if (sidebarBtn) sidebarBtn.href = state.kibanaUrl + "/app/agent_builder/agents";
      } else {
        pillKibana.style.display = "none";
        const sidebarBtn = $("#ab-sidebar-kibana");
        if (sidebarBtn) sidebarBtn.style.display = "none";
      }
      if (!s.live && !_kibanaToastShown && typeof toast === "function") {
        _kibanaToastShown = true;
        toast(
          "Kibana not configured or unreachable. Agent Builder runs in dry-run mode; the master agent and tool catalogue are still browsable.",
          "warn"
        );
      }
    } catch (e) {
      const pillStatus = $("#ab-pill-status");
      pillStatus.textContent = "Status unavailable";
      pillStatus.classList.add("ab-pill-err");
      if (!_kibanaToastShown && typeof toast === "function") {
        _kibanaToastShown = true;
        const safe = (typeof sanitizeError === "function") ? sanitizeError(e) : (e && e.message) || "unknown";
        toast(
          "Kibana not reachable from FE Copilot backend (" + safe + "). The chat still works against the local master agent fallback.",
          "bad"
        );
      }
    }
  }

  // ============================================================ Sidebar (agents list)
  function getAgentToolIds(agent) {
    if (!agent || !agent.configuration) return [];
    const tools = agent.configuration.tools || [];
    const out = [];
    for (const block of tools) {
      const ids = (block && block.tool_ids) || [];
      ids.forEach((id) => {
        if (id && !out.includes(id)) out.push(id);
      });
    }
    return out;
  }

  function findAgent(id) {
    return state.agents.find((a) => a && a.id === id) || null;
  }

  function renderSidebar() {
    const list = $("#ab-sidebar-list");
    if (!list) return;
    list.innerHTML = "";
    if (!state.agents.length) {
      list.appendChild(el("div", { class: "ab-empty ab-empty-sm" }, "No agents yet."));
      return;
    }
    // Master agent first, then user agents alphabetically.
    const sorted = state.agents.slice().sort((a, b) => {
      const am = a.id === MASTER_AGENT_ID ? 0 : 1;
      const bm = b.id === MASTER_AGENT_ID ? 0 : 1;
      if (am !== bm) return am - bm;
      return (a.name || a.id).localeCompare(b.name || b.id);
    });
    sorted.forEach((agent) => {
      const isMaster = agent.id === MASTER_AGENT_ID;
      const isUser = agent.id && agent.id.startsWith(USER_AGENT_PREFIX);
      const toolIds = getAgentToolIds(agent);
      const card = el("div", {
        class: `ab-agent-card ${state.agentId === agent.id ? "is-active" : ""}`,
        role: "listitem",
        "data-agent-id": agent.id,
      });
      const head = el("div", { class: "ab-agent-head" });
      head.appendChild(el("span", { class: "ab-agent-name" }, agent.name || agent.id));
      if (isMaster) {
        head.appendChild(el("span", { class: "ab-agent-pill ab-agent-pill-master", "data-i18n": "ab.master_pill" }, t("ab.master_pill", "master")));
      }
      card.appendChild(head);
      const meta = el("div", { class: "ab-agent-meta" });
      meta.appendChild(el("span", { class: "ab-agent-tool-count" }, `${toolIds.length} tool${toolIds.length === 1 ? "" : "s"}`));
      meta.appendChild(el("span", { class: "ab-agent-id" }, agent.id));
      card.appendChild(meta);
      if (agent.description) {
        card.appendChild(el("div", { class: "ab-agent-desc" }, agent.description));
      }
      card.addEventListener("click", (ev) => {
        if (ev.target.closest(".ab-agent-trash")) return;
        selectAgent(agent.id);
      });
      if (isUser) {
        const trash = el(
          "button",
          {
            type: "button",
            class: "ab-agent-trash",
            title: t("ab.delete_confirm", "Delete this agent?"),
            "aria-label": "Delete agent",
          },
          "Trash"
        );
        trash.innerHTML =
          '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1.4 13.4a2 2 0 0 1-2 1.6H8.4a2 2 0 0 1-2-1.6L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2"/></svg>';
        trash.addEventListener("click", (ev) => {
          ev.stopPropagation();
          deleteAgent(agent);
        });
        card.appendChild(trash);
      }
      list.appendChild(card);
    });
  }

  function renderSuggestedChips() {
    const host = $("#ab-suggested");
    if (!host) return;
    host.innerHTML = "";
    const agent = findAgent(state.agentId);
    const toolIds = getAgentToolIds(agent);
    // Pick up to 6 chips that map to tools the selected agent has access to.
    const candidates = [];
    toolIds.forEach((tid) => {
      const prompt = TOOL_PROMPTS[tid];
      if (prompt) candidates.push({ tid, prompt });
    });
    if (!candidates.length) {
      // Fallback for agents we cannot introspect or that opted into all tools.
      Object.entries(TOOL_PROMPTS).slice(0, 4).forEach(([tid, prompt]) => candidates.push({ tid, prompt }));
    }
    const limit = Math.min(6, Math.max(4, candidates.length));
    candidates.slice(0, limit).forEach(({ tid, prompt }) => {
      const chip = el(
        "button",
        { type: "button", class: "ab-chip", "data-prompt": prompt, title: tid },
        TOOL_LABELS[tid] || tid
      );
      chip.addEventListener("click", () => {
        $("#ab-input").value = prompt;
        send(prompt);
      });
      host.appendChild(chip);
    });
  }

  // ============================================================ Selection + chat scaffold
  function conversationStorageKey(agentId) {
    return STORAGE_PREFIX + agentId;
  }
  // Per-agent transcript storage (questions + answers). Survives reload.
  function historyStorageKey(agentId) {
    return STORAGE_PREFIX + agentId + ".messages";
  }
  function loadHistory(agentId) {
    try {
      const raw = localStorage.getItem(historyStorageKey(agentId));
      const arr = raw ? JSON.parse(raw) : [];
      return Array.isArray(arr) ? arr : [];
    } catch (_e) { return []; }
  }
  function saveHistory(agentId, arr) {
    try { localStorage.setItem(historyStorageKey(agentId), JSON.stringify(arr)); } catch (_e) { /* quota or private */ }
  }

  function selectAgent(agentId) {
    if (!agentId || agentId === state.agentId && state.conversationId !== null) {
      // Same agent already selected and chat is initialized; no-op.
      if (agentId === state.agentId) return;
    }
    state.agentId = agentId;
    localStorage.setItem(SELECTED_KEY, agentId);
    state.conversationId = localStorage.getItem(conversationStorageKey(agentId)) || null;
    const pillAgent = $("#ab-pill-agent");
    if (pillAgent) pillAgent.textContent = `agent: ${agentId}`;
    $$(".ab-agent-card").forEach((c) => {
      c.classList.toggle("is-active", c.getAttribute("data-agent-id") === agentId);
    });
    renderSuggestedChips();
    const chat = $("#ab-chat");
    chat.innerHTML = "";
    const agent = findAgent(agentId);
    const friendly = agent ? (agent.name || agentId) : agentId;
    // Replay any persisted transcript for this agent first; if there is none,
    // fall back to the empty-state hint.
    const history = loadHistory(agentId);
    if (history.length) {
      history.forEach((m) => {
        if (m.role === "user") {
          renderUserMessage(m.text);
        } else if (m.role === "assistant") {
          const slot = renderLoading();
          slot.removeAttribute("data-loading");
          renderAssistantMessage(slot, { text: m.text || "", steps: m.steps, stats: m.stats });
        }
      });
    } else {
      chat.appendChild(
        el("div", { class: "ab-empty" }, `Talking to ${friendly}. Pick a chip above or type your own message.`)
      );
    }
  }

  // ============================================================ Chat rendering
  function renderUserMessage(text) {
    const chat = $("#ab-chat");
    chat.appendChild(
      el("div", { class: "ab-msg ab-msg-user" }, [
        el("div", { class: "ab-msg-role" }, "You"),
        el("div", { class: "ab-msg-body" }, text),
      ])
    );
    scrollChat();
  }

  function renderLoading() {
    const chat = $("#ab-chat");
    const node = el("div", { class: "ab-msg ab-msg-assistant", "data-loading": "1" }, [
      el("div", { class: "ab-msg-role" }, "FE Copilot"),
      el("div", { class: "ab-loader" }, "Thinking..."),
    ]);
    chat.appendChild(node);
    scrollChat();
    return node;
  }

  function renderSteps(steps) {
    if (!Array.isArray(steps) || steps.length === 0) return null;
    const wrap = el("div", { class: "ab-steps" });
    wrap.appendChild(el("div", { class: "ab-msg-role" }, `${steps.length} step${steps.length > 1 ? "s" : ""}`));
    steps.forEach((s, i) => {
      const stepDiv = el("div", { class: `ab-step ab-step-${s.type === "tool_call" ? "toolcall" : s.type}` });
      stepDiv.appendChild(el("span", { class: "ab-step-icon" }, String(i + 1)));
      const body = el("div", { class: "ab-step-body" });
      if (s.type === "tool_call") {
        body.appendChild(el("div", {}, [
          el("span", { class: "ab-step-name" }, s.tool_id || "tool"),
          document.createTextNode(" - call"),
        ]));
        if (s.params) {
          body.appendChild(el("pre", { class: "ab-step-detail" }, JSON.stringify(s.params, null, 2)));
        }
      } else if (s.type === "reasoning") {
        body.appendChild(el("div", {}, [el("span", { class: "ab-step-name" }, "reasoning")]));
        if (s.reasoning) {
          const r = typeof s.reasoning === "string" ? s.reasoning : JSON.stringify(s.reasoning, null, 2);
          body.appendChild(el("pre", { class: "ab-step-detail" }, r.slice(0, 1000)));
        }
      } else {
        body.appendChild(el("div", { class: "ab-step-name" }, s.type || "step"));
      }
      stepDiv.appendChild(body);
      wrap.appendChild(stepDiv);
    });
    return wrap;
  }

  function renderAssistantMessage(slot, payload) {
    slot.innerHTML = "";
    const role = el("div", { class: "ab-msg-role" }, "FE Copilot");
    const body = el("div", { class: "ab-msg-body", html: renderMarkdown(payload.text || "") });
    slot.appendChild(role);
    slot.appendChild(body);
    const steps = renderSteps(payload.steps);
    if (steps) slot.appendChild(steps);
    if (payload.stats) {
      const stats = `${payload.stats.input_tokens ?? "?"} in / ${payload.stats.output_tokens ?? "?"} out . ${payload.stats.ttft_ms ?? "?"}ms first token . model: ${payload.stats.model || "?"}`;
      slot.appendChild(el("div", { class: "ab-msg-stats" }, stats));
    }
    slot.removeAttribute("data-loading");
    scrollChat();
  }

  function renderError(slot, message) {
    slot.innerHTML = "";
    slot.appendChild(el("div", { class: "ab-msg-role" }, "Error"));
    slot.appendChild(el("div", { class: "ab-msg-body" }, message));
    slot.removeAttribute("data-loading");
  }

  function scrollChat() {
    const composer = document.querySelector(".ab-composer");
    if (composer) composer.scrollIntoView({ behavior: "smooth", block: "end" });
  }

  // ============================================================ Send
  // Long LLM calls (up to ~30s for converse). Esc cancels the in-flight
  // request via the per-send AbortController; the spinner is always cleared
  // in finally so the UI never gets stuck. Uses apiPostWithRetry when the
  // retry wrapper is loaded so a transient 502/503/504 retries 1s/2s/4s.
  async function send(text) {
    if (state.inFlight || !text || !text.trim()) return;
    state.inFlight = true;
    state.abortCtrl = new AbortController();
    const sendBtn = $("#ab-send");
    sendBtn.disabled = true;
    sendBtn.textContent = "Sending... (Esc to cancel)";

    renderUserMessage(text);
    // Persist the user turn before the LLM round-trip so a refresh mid-call
    // does not lose the question.
    const userTurn = { role: "user", text };
    const hist = loadHistory(state.agentId);
    hist.push(userTurn);
    saveHistory(state.agentId, hist);
    const slot = renderLoading();

    try {
      const body = { message: text, agent_id: state.agentId };
      if (state.conversationId) body.conversation_id = state.conversationId;
      const res = typeof window.apiPostWithRetry === "function"
        ? await window.apiPostWithRetry("/agent-builder/converse", body, {
            category: "llm",
            signal: state.abortCtrl.signal,
            silent: true,
            label: "Converse",
          })
        : await apiPost("/agent-builder/converse", body);
      if (res && res.conversation_id) {
        state.conversationId = res.conversation_id;
        localStorage.setItem(conversationStorageKey(state.agentId), state.conversationId);
      }
      const msg = (res && res.response && res.response.message) || res?.message || "(no response)";
      const stats = res
        ? {
            input_tokens: res.model_usage?.input_tokens,
            output_tokens: res.model_usage?.output_tokens,
            ttft_ms: res.time_to_first_token,
            model: res.model_usage?.model,
          }
        : null;
      renderAssistantMessage(slot, { text: msg, steps: res?.steps, stats });
      // Persist the assistant turn so the transcript survives reload.
      const histAfter = loadHistory(state.agentId);
      histAfter.push({ role: "assistant", text: msg, steps: res?.steps, stats });
      saveHistory(state.agentId, histAfter);
    } catch (e) {
      const cancelled = e && (e.name === "AbortError" || (state.abortCtrl && state.abortCtrl.signal.aborted));
      if (cancelled) {
        renderError(slot, "Cancelled");
      } else {
        const safe = (typeof sanitizeError === "function") ? sanitizeError(e) : (e && e.message) || String(e);
        renderError(slot, safe);
      }
    } finally {
      state.inFlight = false;
      state.abortCtrl = null;
      sendBtn.disabled = false;
      sendBtn.textContent = "Send";
      $("#ab-input").value = "";
      $("#ab-input").focus();
    }
  }

  // Esc-to-cancel: aborts the in-flight converse request so the spinner
  // clears immediately. Wired in init() with capture=false so the modal's
  // own Esc handler (which uses capture=true) still wins when the modal is
  // open.
  function cancelInflight() {
    if (state.inFlight && state.abortCtrl) {
      try { state.abortCtrl.abort(); } catch (_) { /* ignore */ }
    }
  }

  function reset() {
    state.conversationId = null;
    localStorage.removeItem(conversationStorageKey(state.agentId));
    localStorage.removeItem(historyStorageKey(state.agentId));
    const chat = $("#ab-chat");
    chat.innerHTML = "";
    chat.appendChild(
      el("div", { class: "ab-empty" }, "New thread started. Ask the selected agent anything.")
    );
  }

  // ============================================================ Roster + tools
  async function loadAgents(preferAgentId) {
    try {
      const res = await apiGet("/agent-builder/agents");
      const agents = (res && Array.isArray(res.agents)) ? res.agents : [];
      state.agents = agents;
      // If the selected agent disappeared (e.g., just deleted), fall back to master.
      const ids = agents.map((a) => a && a.id).filter(Boolean);
      const target = preferAgentId && ids.includes(preferAgentId)
        ? preferAgentId
        : ids.includes(state.agentId)
        ? state.agentId
        : MASTER_AGENT_ID;
      state.agentId = target;
      localStorage.setItem(SELECTED_KEY, target);
      renderSidebar();
      // Initial selection: hydrate conversation_id for this agent and render scaffolding.
      state.conversationId = localStorage.getItem(conversationStorageKey(target)) || null;
      const pillAgent = $("#ab-pill-agent");
      if (pillAgent) pillAgent.textContent = `agent: ${target}`;
      renderSuggestedChips();
    } catch (e) {
      const list = $("#ab-sidebar-list");
      if (list) {
        list.innerHTML = "";
        list.appendChild(el("div", { class: "ab-empty ab-empty-sm" }, "Could not load agents."));
      }
    }
  }

  async function loadTools() {
    try {
      const res = await apiGet("/agent-builder/tools");
      state.tools = (res && Array.isArray(res.tools)) ? res.tools : [];
    } catch (e) {
      state.tools = [];
    }
  }

  // ============================================================ Modal: create agent
  function slugify(name) {
    return String(name || "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "")
      .slice(0, 40);
  }

  function clearFieldErrors() {
    $$("#ab-modal-form .ab-field-error").forEach((n) => (n.textContent = ""));
    const status = $("#ab-f-status");
    if (status) {
      status.textContent = "";
      status.classList.remove("is-err");
    }
  }

  function setFieldError(name, message) {
    const node = document.querySelector(`#ab-modal-form [data-error-for="${name}"]`);
    if (node) node.textContent = message || "";
  }

  // ============================================================ Tool picker (modal)
  // The picker is rebuilt every time the modal opens. We keep tool meta in a closure-local
  // index so the live filter does not need to re-derive descriptions or categories per keystroke.
  let _pickerIndex = null;

  function buildToolPickerIndex() {
    // Index every fec_* tool from the live roster, plus any extras the API returned. Tools without
    // a category mapping land in "Other", which we render last. Each entry carries the id,
    // category, full description, and pre-truncated short description for the row.
    const tools = (state.tools || []).filter((tt) => tt && tt.id);
    const items = tools.map((tt) => {
      const id = tt.id;
      const category = TOOL_CATEGORIES[id] || "Other";
      const description = String(tt.description || "").trim();
      return {
        id,
        category,
        label: TOOL_LABELS[id] || id,
        description,
        short: shortDescription(description),
      };
    });
    // Group by category in CATEGORY_ORDER, alphabetical within each group, "Other" last.
    const sections = [];
    const seen = new Set();
    CATEGORY_ORDER.forEach((cat) => {
      const inCat = items.filter((it) => it.category === cat).sort((a, b) => a.id.localeCompare(b.id));
      if (inCat.length) {
        sections.push({ category: cat, i18n: CATEGORY_I18N[cat], items: inCat });
        inCat.forEach((it) => seen.add(it.id));
      }
    });
    const leftovers = items.filter((it) => !seen.has(it.id)).sort((a, b) => a.id.localeCompare(b.id));
    if (leftovers.length) {
      sections.push({ category: "Other", i18n: null, items: leftovers });
    }
    const byId = {};
    items.forEach((it) => { byId[it.id] = it; });
    return { sections, total: items.length, byId };
  }

  function getCheckedToolIds() {
    return $$('#ab-f-tools input[type="checkbox"]:checked').map((c) => c.value);
  }

  function setCheckedToolIds(ids) {
    const set = new Set(ids || []);
    $$('#ab-f-tools input[type="checkbox"]').forEach((cb) => {
      cb.checked = set.has(cb.value);
    });
    updateToolCounter();
    renderSelectedSummary();
  }

  function updateToolCounter() {
    const counter = $("#ab-f-tools-counter");
    if (!counter || !_pickerIndex) return;
    const checked = getCheckedToolIds().length;
    const total = _pickerIndex.total;
    const tmpl = t("ab.tool.counter", "{count} of {total} tools selected");
    counter.textContent = tmpl.replace("{count}", String(checked)).replace("{total}", String(total));
    renderSelectedSummary();
  }

  function applyToolFilter(query) {
    const q = String(query || "").trim().toLowerCase();
    const grid = $("#ab-f-tools");
    if (!grid) return;
    const rows = $$("#ab-f-tools .ab-tool-row");
    rows.forEach((row) => {
      if (!q) {
        row.classList.remove("is-hidden");
        return;
      }
      const id = row.getAttribute("data-tool-id") || "";
      const cat = row.getAttribute("data-tool-cat") || "";
      const desc = row.getAttribute("data-tool-desc") || "";
      const hit =
        id.toLowerCase().includes(q) ||
        cat.toLowerCase().includes(q) ||
        desc.toLowerCase().includes(q);
      row.classList.toggle("is-hidden", !hit);
    });
    // Hide entire sections that have no visible rows.
    $$("#ab-f-tools .ab-tool-section").forEach((sec) => {
      const visibleRows = sec.querySelectorAll(".ab-tool-row:not(.is-hidden)").length;
      sec.classList.toggle("is-hidden", visibleRows === 0);
    });
    // Show / hide the clear button.
    const clearBtn = $("#ab-f-tools-clear");
    if (clearBtn) clearBtn.hidden = !q;
  }

  function renderToolPicker() {
    const grid = $("#ab-f-tools");
    if (!grid) return;
    grid.innerHTML = "";
    _pickerIndex = buildToolPickerIndex();
    if (!_pickerIndex.total) {
      grid.appendChild(el("div", { class: "ab-empty-sm" }, "No tools available."));
      return;
    }
    _pickerIndex.sections.forEach((section) => {
      const sectionEl = el("div", { class: "ab-tool-section", "data-cat": section.category });
      const head = el("div", { class: "ab-tool-section-head" });
      const title = el("span", { class: "ab-tool-section-title" });
      const titleText = section.i18n ? t(section.i18n, section.category) : section.category;
      title.appendChild(document.createTextNode(titleText));
      title.appendChild(el("span", { class: "ab-tool-section-count" }, `${section.items.length}`));
      head.appendChild(title);
      const selectAll = el(
        "button",
        {
          type: "button",
          class: "ab-tool-section-select",
          "data-i18n": "ab.tool.select_all",
          title: t("ab.tool.select_all", "Select all"),
        },
        t("ab.tool.select_all", "Select all")
      );
      selectAll.addEventListener("click", (ev) => {
        ev.preventDefault();
        const checked = getCheckedToolIds();
        const merged = new Set(checked);
        section.items.forEach((it) => merged.add(it.id));
        setCheckedToolIds(Array.from(merged));
      });
      head.appendChild(selectAll);
      sectionEl.appendChild(head);
      const rows = el("div", { class: "ab-tool-section-rows" });
      section.items.forEach((it) => {
        const id = "tool-" + it.id;
        const row = el("label", {
          class: "ab-tool-row",
          for: id,
          "data-tool-id": it.id,
          "data-tool-cat": it.category,
          "data-tool-desc": it.description,
          title: it.description,
        });
        const cb = el("input", { type: "checkbox", id, value: it.id });
        cb.addEventListener("change", updateToolCounter);
        row.appendChild(cb);
        const main = el("div", { class: "ab-tool-row-main" });
        const top = el("div", { class: "ab-tool-row-top" });
        top.appendChild(el("span", { class: "ab-tool-row-id" }, it.id));
        top.appendChild(el("span", { class: "ab-tool-row-pill" }, it.category));
        main.appendChild(top);
        if (it.short) {
          main.appendChild(el("div", { class: "ab-tool-row-desc", title: it.description }, it.short));
        }
        row.appendChild(main);
        rows.appendChild(row);
      });
      sectionEl.appendChild(rows);
      grid.appendChild(sectionEl);
    });
    updateToolCounter();
  }

  function renderToolBundles() {
    const host = $("#ab-f-tools-bundles");
    if (!host) return;
    host.innerHTML = "";
    TOOL_BUNDLES.forEach((b) => {
      const tip = b.desc ? `${b.desc} (${b.tools.length} tools)` : b.tools.join(", ");
      const chip = el(
        "button",
        {
          type: "button",
          class: "ab-tool-bundle",
          "data-bundle": b.id,
          title: tip,
        },
        t(b.i18n, b.label)
      );
      chip.addEventListener("click", (ev) => {
        ev.preventDefault();
        setCheckedToolIds(b.tools);
        // Clear the search when applying a bundle so the user sees the selection right away.
        const search = $("#ab-f-tools-search");
        if (search) {
          search.value = "";
          applyToolFilter("");
        }
        renderSelectedSummary();
      });
      host.appendChild(chip);
    });
  }

  // ============================================================ Selected tools summary
  // A small panel below the picker that renders one chip per selected tool with
  // an x to remove. Updates live whenever a checkbox or bundle changes.
  function renderSelectedSummary() {
    const host = $("#ab-f-selected-summary");
    if (!host) return;
    const ids = getCheckedToolIds();
    host.innerHTML = "";
    if (!ids.length) {
      const empty = el("div", { class: "ab-selected-empty" }, t("ab.tool.selected_empty", "No tools selected. Pick a bundle above or check tools below."));
      host.appendChild(empty);
      return;
    }
    const head = el("div", { class: "ab-selected-head" }, [
      el("span", { class: "ab-selected-title", text: t("ab.tool.selected_title", "Selected for this agent") }),
      el("span", { class: "ab-selected-count", text: `${ids.length}` }),
    ]);
    host.appendChild(head);
    const list = el("div", { class: "ab-selected-list" });
    ids.forEach((id) => {
      const meta = (_pickerIndex.byId && _pickerIndex.byId[id]) || { id, category: "", description: "" };
      const cat = (meta.category || "").toLowerCase();
      const chip = el("span", { class: "ab-selected-chip", "data-cat": cat, title: meta.description || id }, [
        el("span", { class: "ab-selected-chip-cat" }, meta.category || ""),
        el("span", { class: "ab-selected-chip-id" }, id),
        el("button", {
          type: "button",
          class: "ab-selected-chip-remove",
          "aria-label": "Remove " + id,
          title: "Remove",
          onclick: () => {
            const cb = document.getElementById("tool-" + id);
            if (cb) { cb.checked = false; cb.dispatchEvent(new Event("change", { bubbles: true })); }
          },
          text: "x",
        }),
      ]);
      list.appendChild(chip);
    });
    host.appendChild(list);
  }

  // ============================================================ Modal focus trap (WCAG 2.4.3 / 2.1.2)
  // When the create-agent modal opens we (a) remember the element that triggered it so we can
  // restore focus on close, (b) move focus to the first input, and (c) trap Tab / Shift+Tab
  // inside the dialog. Esc-to-close is wired separately below.
  let _abModalLastFocus = null;
  function _abFocusableInModal() {
    const modal = $("#ab-modal");
    if (!modal) return [];
    const sel = [
      'a[href]',
      'button:not([disabled])',
      'input:not([disabled]):not([type="hidden"])',
      'select:not([disabled])',
      'textarea:not([disabled])',
      '[tabindex]:not([tabindex="-1"])',
    ].join(',');
    return Array.from(modal.querySelectorAll(sel)).filter((n) => {
      if (n.hasAttribute('disabled')) return false;
      if (n.getAttribute('aria-hidden') === 'true') return false;
      if (n.hidden) return false;
      // Skip elements inside elements that are display:none via [hidden].
      let p = n.parentElement;
      while (p && p !== modal) {
        if (p.hidden) return false;
        p = p.parentElement;
      }
      return true;
    });
  }
  function _abModalKeyTrap(ev) {
    if (ev.key !== 'Tab') return;
    const modal = $("#ab-modal");
    if (!modal || modal.hidden) return;
    const focusables = _abFocusableInModal();
    if (focusables.length === 0) {
      ev.preventDefault();
      return;
    }
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    const active = document.activeElement;
    if (ev.shiftKey) {
      if (active === first || !modal.contains(active)) {
        ev.preventDefault();
        last.focus();
      }
    } else {
      if (active === last || !modal.contains(active)) {
        ev.preventDefault();
        first.focus();
      }
    }
  }

  function openModal() {
    const modal = $("#ab-modal");
    if (!modal) return;
    // Remember the trigger so we can restore focus to it after close.
    _abModalLastFocus = (document.activeElement instanceof HTMLElement) ? document.activeElement : null;
    clearFieldErrors();
    $("#ab-f-name").value = "";
    $("#ab-f-slug").value = "";
    $("#ab-f-description").value = "";
    $("#ab-f-prompt").value = "";
    $("#ab-f-prompt-count").textContent = "0";
    // Build the categorized tool picker from the live roster + bundles.
    renderToolBundles();
    renderToolPicker();
    renderSelectedSummary();
    // Reset filter input.
    const search = $("#ab-f-tools-search");
    if (search) {
      search.value = "";
      applyToolFilter("");
    }
    modal.hidden = false;
    // Focus the first input (Name) so the form reads top-to-bottom for keyboard and AT users.
    // This satisfies WCAG 2.4.3 Focus Order for the dialog flow.
    setTimeout(() => {
      const target = $("#ab-f-name");
      if (target) target.focus();
    }, 30);
    // Activate the focus trap.
    document.addEventListener('keydown', _abModalKeyTrap, true);
  }

  function closeModal() {
    const modal = $("#ab-modal");
    if (modal) modal.hidden = true;
    document.removeEventListener('keydown', _abModalKeyTrap, true);
    // Restore focus to the element that opened the modal so screen-reader users do not lose
    // their place. WCAG 2.4.3 Focus Order.
    if (_abModalLastFocus && typeof _abModalLastFocus.focus === 'function') {
      try { _abModalLastFocus.focus({ preventScroll: true }); } catch (_) { try { _abModalLastFocus.focus(); } catch (__) {} }
    }
    _abModalLastFocus = null;
  }

  async function submitModal() {
    clearFieldErrors();
    const name = $("#ab-f-name").value.trim();
    const slugRaw = $("#ab-f-slug").value.trim().toLowerCase();
    const description = $("#ab-f-description").value.trim();
    const systemPrompt = $("#ab-f-prompt").value;
    const toolIds = $$('#ab-f-tools input[type="checkbox"]:checked').map((c) => c.value);

    let bad = false;
    if (name.length < 3 || name.length > 80) {
      setFieldError("name", "3 to 80 characters required.");
      bad = true;
    }
    if (!/^[a-z0-9_]{3,40}$/.test(slugRaw)) {
      setFieldError("slug", t("ab.errors.slug_invalid", "Slug must be lowercase letters, digits, underscore (3-40 chars)."));
      bad = true;
    }
    if (description.length < 10 || description.length > 400) {
      setFieldError("description", "10 to 400 characters required.");
      bad = true;
    }
    if (systemPrompt.length < 50 || systemPrompt.length > 8000) {
      setFieldError("system_prompt", "50 to 8000 characters required.");
      bad = true;
    }
    if (toolIds.length < 1 || toolIds.length > 12) {
      setFieldError("tool_ids", "Pick at least 1 tool (max 12).");
      bad = true;
    }
    if (bad) return;

    const status = $("#ab-f-status");
    const submit = $("#ab-f-submit");
    submit.disabled = true;
    status.textContent = "Creating in your Kibana cluster...";
    try {
      const res = await apiPost("/agent-builder/agents", {
        name,
        slug: slugRaw,
        description,
        system_prompt: systemPrompt,
        tool_ids: toolIds,
      });
      const newId = (res && res.agent_id) || (USER_AGENT_PREFIX + slugRaw);
      status.textContent = `Created ${newId}.`;
      closeModal();
      await loadAgents(newId);
      selectAgent(newId);
    } catch (e) {
      const safe = (typeof sanitizeError === "function") ? sanitizeError(e) : (e && e.message) || String(e);
      status.textContent = "Error: " + safe;
      status.classList.add("is-err");
    } finally {
      submit.disabled = false;
    }
  }

  async function deleteAgent(agent) {
    if (!agent || !agent.id) return;
    if (!agent.id.startsWith(USER_AGENT_PREFIX)) return;
    const msg = t("ab.delete_confirm", "Delete this agent? This removes it from your Kibana cluster.");
    if (!window.confirm(`${msg}\n\n${agent.name || agent.id}`)) return;
    try {
      const res = await fetch(`/api/v1/agent-builder/agents/${encodeURIComponent(agent.id)}`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
      });
      if (!res.ok) {
        let detail = String(res.status);
        try {
          const j = await res.json();
          if (j && j.detail) detail = j.detail;
        } catch (_) {}
        throw new Error(detail);
      }
      // If we just deleted the selected agent, fall back to master.
      const next = agent.id === state.agentId ? MASTER_AGENT_ID : state.agentId;
      await loadAgents(next);
      selectAgent(next);
    } catch (e) {
      const safe = (typeof sanitizeError === "function") ? sanitizeError(e) : (e && e.message) || String(e);
      window.alert("Could not delete agent: " + safe);
    }
  }

  // ============================================================ Wire up
  function init() {
    if (typeof applyI18n === "function") applyI18n();
    if (typeof renderLangPicker === "function") renderLangPicker(document.getElementById("lang-host"));

    loadStatus();
    Promise.all([loadAgents(state.agentId), loadTools()]).then(() => {
      // After both finish, re-render chips so the picker reflects the live tool roster.
      renderSuggestedChips();
      // Initial chat scaffolding for the persisted selected agent.
      const chat = $("#ab-chat");
      if (chat && !chat.children.length) {
        const agent = findAgent(state.agentId);
        const friendly = agent ? (agent.name || state.agentId) : state.agentId;
        chat.appendChild(
          el("div", { class: "ab-empty" }, `Talking to ${friendly}. Pick a chip above or type your own message.`)
        );
      }
    });

    $("#ab-form").addEventListener("submit", () => {
      const txt = $("#ab-input").value;
      send(txt);
    });
    $("#ab-input").addEventListener("keydown", (ev) => {
      if ((ev.metaKey || ev.ctrlKey) && ev.key === "Enter") {
        ev.preventDefault();
        send($("#ab-input").value);
      }
    });
    $("#ab-reset").addEventListener("click", reset);

    $("#ab-new-agent").addEventListener("click", openModal);
    $$("[data-ab-close]").forEach((b) => b.addEventListener("click", closeModal));
    $("#ab-modal-form").addEventListener("submit", (ev) => {
      ev.preventDefault();
      submitModal();
    });
    // Tool picker: live filter + clear button.
    const toolSearch = $("#ab-f-tools-search");
    if (toolSearch) {
      toolSearch.addEventListener("input", (ev) => applyToolFilter(ev.target.value));
    }
    const toolClear = $("#ab-f-tools-clear");
    if (toolClear) {
      toolClear.addEventListener("click", (ev) => {
        ev.preventDefault();
        if (toolSearch) {
          toolSearch.value = "";
          applyToolFilter("");
          toolSearch.focus();
        }
      });
    }
    // Auto-derive the slug as the user types the name, until they edit the slug manually.
    let slugDirty = false;
    const slugInput = $("#ab-f-slug");
    slugInput.addEventListener("input", () => { slugDirty = true; });
    $("#ab-f-name").addEventListener("input", (ev) => {
      if (!slugDirty) slugInput.value = slugify(ev.target.value);
    });
    const promptArea = $("#ab-f-prompt");
    promptArea.addEventListener("input", () => {
      $("#ab-f-prompt-count").textContent = String(promptArea.value.length);
    });
    // ESC clears the tool search if it has text, otherwise closes the modal.
    document.addEventListener("keydown", (ev) => {
      if (ev.key !== "Escape") return;
      const modal = $("#ab-modal");
      if (!modal || modal.hidden) return;
      const search = $("#ab-f-tools-search");
      if (search && search.value && document.activeElement === search) {
        search.value = "";
        applyToolFilter("");
        ev.preventDefault();
        return;
      }
      closeModal();
    });
    // Esc-to-cancel for the in-flight converse request. Only fires when the
    // modal is NOT open (the modal handler above owns Esc when it is) and
    // there is an outstanding LLM request. Keeps the spinner from getting
    // stuck on a slow LLM call - no need to wait for the 30s timeout.
    document.addEventListener("keydown", (ev) => {
      if (ev.key !== "Escape") return;
      const modal = $("#ab-modal");
      if (modal && !modal.hidden) return; // modal handler owns this key
      if (!state.inFlight) return;
      ev.preventDefault();
      cancelInflight();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
