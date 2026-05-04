/*
  filename: app.js
  description: Dashboard logic. Loads /info + /meetings + /audit + /briefs (history). Adds Quick Research, search filter, keyboard shortcut, audit footer.
  Author: Rodrigo Careaga
  Date: 03-05-2026
*/

let ALL_MEETINGS = [];

// Prefab industry templates for one-click prefill of the Quick Research form.
// The catalog also lives at /data/seed/industry_templates.json (kept in sync by hand).
// Tile UI strings (name, tagline) are i18n keyed; form-field copy stays English so the
// agent gets stable signal regardless of FE locale.
const INDUSTRY_TEMPLATES = [
  {
    id: "banking",
    accent: "blue",
    icon:
      '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M3 10l9-6 9 6"/><path d="M5 10v8"/><path d="M9 10v8"/><path d="M15 10v8"/><path d="M19 10v8"/><path d="M3 21h18"/></svg>',
    fields: {
      industry: "Banking & Financial Services",
      size: "10000+ employees",
      tech_stack:
        "Splunk for SIEM + observability, Datadog APM, Oracle + DB2 mainframe, Java/Kotlin microservices, Kafka, AWS + on-prem",
      notes:
        "Regulatory pressure from DORA, PCI DSS, SOX, FCA SYSC. Splunk renewal in 2027 ~$5M annual. Looking to consolidate SIEM + observability + search into one platform. Compliance audit in Q3.",
      model: "claude-sonnet-4-6",
    },
  },
  {
    id: "retail",
    accent: "pink",
    icon:
      '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><circle cx="9" cy="20" r="1.4"/><circle cx="17" cy="20" r="1.4"/><path d="M3 4h2.2l2.4 11.2a2 2 0 0 0 2 1.6h7.5a2 2 0 0 0 2-1.55L21 8H6"/></svg>',
    fields: {
      industry: "E-commerce & Retail",
      size: "1000-5000 employees",
      tech_stack:
        "Shopify Plus, Klaviyo, Datadog observability, Algolia search, AWS, Snowflake for analytics, microservices in Go and Node.js",
      notes:
        "Black Friday peak handling is critical. Cart abandonment > 30%. Looking for unified observability + search relevance + customer 360. Currently overspending on Datadog ($800k/year).",
      model: "claude-sonnet-4-6",
    },
  },
  {
    id: "healthcare",
    accent: "teal",
    icon:
      '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><path d="M20.8 11.5a4.6 4.6 0 0 0-7.8-3.3L12 9.2l-1-1A4.6 4.6 0 0 0 3.2 11.5c0 1.6.7 3 1.8 4.1L12 22l7-6.4c1.1-1.1 1.8-2.5 1.8-4.1z"/><path d="M12 11v5"/><path d="M9.5 13.5h5"/></svg>',
    fields: {
      industry: "Healthcare & Life Sciences",
      size: "5000-10000 employees",
      tech_stack:
        "Epic EHR, MuleSoft, Java + .NET, Splunk, Microsoft Sentinel for SOC, Azure-first cloud, FHIR APIs",
      notes:
        "HIPAA + HITRUST + GDPR (EU patients). 7-year retention mandates. SOC needs UEBA. Considering Elastic for SIEM consolidation; pilot needed before fiscal year end.",
      model: "claude-sonnet-4-6",
    },
  },
];

(async function init() {
  applyI18n();
  renderLangPicker(document.getElementById("lang-host"));
  bindKeyboard();
  bindEntryTabs();
  bindQuickResearch();
  renderQuickResearchTemplates();
  bindTranscriptUpload();
  await loadInfo();
  await loadCalendar();
  await loadMeetings();
  await loadHistory();
  await loadAudit();
})();

async function loadCalendar() {
  const host = document.getElementById("calendar-list");
  if (!host) return;
  try {
    const res = await apiGet("/calendar/events");
    setText("cal-count", `${res.count} upcoming`);
    clear(host);
    if (!res.items.length) {
      host.appendChild(el("li", { class: "muted empty" }, "No upcoming calendar events."));
      return;
    }
    res.items.forEach((ev) => host.appendChild(renderCalendarRow(ev)));
  } catch (e) {
    /* non-fatal */
  }
}

function renderCalendarRow(ev) {
  const r = ev.resolution || {};
  const company = r.company || {};
  const confLabels = { high: "high", medium: "med", low: "low", internal: "internal" };
  const confClass = { high: "ok", medium: "upcoming", low: "bad", internal: "" };
  const confLabel = confLabels[r.confidence] || r.confidence;
  const cssConf = confClass[r.confidence] || "";

  const externalAttendees = (ev.attendees || []).filter((a) => a.email && !a.email.endsWith("@elastic.co"));
  const internalCount = (ev.attendees || []).length - externalAttendees.length;

  const meta = el("div", { class: "meta" }, [
    el("span", { class: "pill " + cssConf }, `${company.name || "(unknown)"} · ${confLabel}`),
    el("span", { class: "dot" }, "·"),
    el("span", {}, fmtDate(ev.start && ev.start.dateTime)),
    el("span", { class: "dot" }, "·"),
    el("span", {}, `${externalAttendees.length} ext / ${internalCount} int`),
    r.consulting_present ? el("span", { class: "pill bad", style: "margin-left:8px" }, "consultants present") : null,
  ]);

  const reasoning = el("div", { class: "muted small", style: "margin-top:3px" }, "↳ " + (r.method || ""));

  const info = el("div", { class: "info" }, [
    el("div", { class: "title" }, ev.summary || "(no title)"),
    meta,
    reasoning,
  ]);

  const actions = el("div", { class: "actions" }, []);
  if (ev.hangout_link) {
    actions.appendChild(el("a", { class: "btn ghost", href: ev.hangout_link, target: "_blank", rel: "noopener" }, "Join"));
  }
  if (company && company.id && !String(company.id).startsWith("unknown-")) {
    const runLabel = "Pre-meeting";
    actions.appendChild(
      el(
        "button",
        {
          class: "btn primary",
          onclick: async (clickEv) => {
            const btn = clickEv.currentTarget;
            const labelHTML = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = '<span class="spinner"></span> Running...';
            try {
              const body = {
                company_name: company.name,
                industry: company.industry || "",
                size: company.size || "",
                tech_stack: ((company.tech_stack && company.tech_stack.observability) || []).join(", "),
                notes: `Auto-prefilled from calendar event "${ev.summary}".`,
                meeting_title: ev.summary,
                language: claudeLanguageName(),
              };
              const result = await apiPost("/agents/pre-meeting/ad-hoc", body);
              toast(`Brief generated for ${company.name}`, "ok");
              window.location.href = `/meeting.html?id=${encodeURIComponent(result.meeting_id)}&adhoc=1`;
            } catch (err) {
              toast(`Pre-Meeting failed: ${err.message}`, "bad");
            } finally {
              btn.disabled = false;
              btn.innerHTML = labelHTML;
            }
          },
        },
        runLabel
      )
    );
  }

  return el("li", {}, [info, actions]);
}

function bindEntryTabs() {
  const tabs = document.querySelectorAll(".entry-tab");
  tabs.forEach((t) =>
    t.addEventListener("click", () => {
      tabs.forEach((x) => x.classList.remove("active"));
      t.classList.add("active");
      const mode = t.dataset.mode;
      document.getElementById("entry-qr").hidden = mode !== "qr";
      document.getElementById("entry-tr").hidden = mode !== "tr";
    })
  );
}

function bindTranscriptUpload() {
  const form = document.getElementById("tr-form");
  if (!form) return;
  const submit = document.getElementById("tr-submit");
  const statusEl = document.getElementById("tr-status");
  const fileInput = document.getElementById("tr-file");
  const textarea = document.getElementById("tr-text");
  const charCount = document.getElementById("tr-charcount");
  const sourceSel = document.getElementById("tr-source");

  const TR_MODEL_LABELS = {
    "claude-haiku-4-5": "Haiku 4.5",
    "claude-sonnet-4-6": "Sonnet 4.6",
    "claude-opus-4-7": "Opus 4.7",
    "": "Haiku 4.5 (default)",
  };

  function updateCharCount() {
    if (!charCount || !textarea) return;
    const n = (textarea.value || "").length;
    charCount.textContent = `${n.toLocaleString()} chars`;
    charCount.classList.toggle("ok", n >= 20);
    charCount.classList.toggle("bad", n > 0 && n < 20);
  }
  if (textarea) textarea.addEventListener("input", updateCharCount);
  updateCharCount();

  // Auto-fill textarea from file pick (also infer source from extension).
  if (fileInput) {
    fileInput.addEventListener("change", async () => {
      const f = fileInput.files && fileInput.files[0];
      if (!f) return;
      try {
        const text = await f.text();
        textarea.value = text;
        const ext = (f.name.split(".").pop() || "").toLowerCase();
        if (sourceSel) {
          if (ext === "vtt") sourceSel.value = "zoom";
          else if (ext === "txt" || ext === "srt") sourceSel.value = "manual";
        }
        updateCharCount();
        statusEl.textContent = `Loaded ${f.name} (${Math.round(text.length / 1024)} KB)`;
      } catch (e) {
        toast(`Could not read file: ${e.message}`, "bad");
      }
    });
  }

  // Drag-and-drop onto the textarea.
  if (textarea) {
    textarea.addEventListener("dragover", (e) => {
      e.preventDefault();
      textarea.classList.add("is-drop");
    });
    textarea.addEventListener("dragleave", () => textarea.classList.remove("is-drop"));
    textarea.addEventListener("drop", async (e) => {
      e.preventDefault();
      textarea.classList.remove("is-drop");
      const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
      if (!f) return;
      try {
        const text = await f.text();
        textarea.value = text;
        updateCharCount();
        statusEl.textContent = `Loaded ${f.name} (${Math.round(text.length / 1024)} KB)`;
      } catch (err) {
        toast(`Drop failed: ${err.message}`, "bad");
      }
    });
  }

  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const nameEl = document.getElementById("tr-name");
    const name = nameEl.value.trim();
    const title = document.getElementById("tr-title").value.trim();
    const source = sourceSel.value;
    const industry = document.getElementById("tr-industry").value.trim();
    const size = document.getElementById("tr-size").value.trim();
    const notes = document.getElementById("tr-notes").value.trim();
    const text = textarea.value;
    const model = document.getElementById("tr-model")?.value || "";

    if (!name) {
      toast("Company name is required", "bad");
      nameEl.focus();
      return;
    }
    if (!text || text.trim().length < 20) {
      toast("Transcript needs at least 20 characters", "bad");
      textarea.focus();
      return;
    }

    const labelHTML = submit.innerHTML;
    submit.disabled = true;
    submit.setAttribute("aria-busy", "true");
    submit.innerHTML = '<span class="spinner" aria-hidden="true"></span> <span>Analyzing...</span>';
    const modelLabel = TR_MODEL_LABELS[model] || model || "Haiku 4.5 (default)";
    statusEl.textContent = `Running post-meeting agent (${modelLabel})...`;

    try {
      const res = await apiPost("/agents/post-meeting/from-transcript", {
        company_name: name,
        meeting_title: title,
        industry,
        size,
        notes,
        transcript_text: text,
        transcript_source: source,
        language: claudeLanguageName(),
        model,
      });
      const mid = res && res.meeting_id;
      if (!mid) {
        throw new Error("Backend did not return a meeting_id");
      }
      toast(`Post-meeting analysis ready for ${name}`, "ok");
      statusEl.textContent = "Done. Opening meeting view...";
      window.location.href = `/meeting.html?id=${encodeURIComponent(mid)}&post=1&adhoc=1`;
    } catch (e) {
      const msg = (e && e.message) || "Unknown error";
      toast(`Analyze transcript failed: ${msg}`, "bad");
      statusEl.textContent = `Error: ${msg}`;
    } finally {
      submit.disabled = false;
      submit.removeAttribute("aria-busy");
      submit.innerHTML = labelHTML;
    }
  });
}

async function loadInfo() {
  const status = document.getElementById("status");
  const modelPill = document.getElementById("model-pill");
  try {
    await apiGet("/health");
    status.textContent = "Connected";
    status.classList.add("ok");
    const info = await apiGet("/info");
    modelPill.textContent = info.mock_mode
      ? "Mock mode (offline)"
      : `Default: ${prettyModel(info.models.default)}`;
    updateESPanel(info.elasticsearch);
    updateKibanaPanel(info.kibana);
  } catch (e) {
    status.textContent = "Backend offline";
    status.classList.add("bad");
  }
  bindESActions();
  bindKibanaActions();
}

function updateKibanaPanel(k) {
  const state = document.getElementById("kibana-state");
  const url = document.getElementById("kibana-url");
  if (!state) return;
  if (k && k.available) {
    state.textContent = "connected";
    state.className = "es-state es-up";
  } else {
    state.textContent = "offline";
    state.className = "es-state es-down";
  }
  if (url) url.textContent = (k && k.url) || "";
  if (k && k.discover) {
    const map = { "kibana-briefs": "briefs", "kibana-post": "post_meetings", "kibana-audit": "audit", "kibana-bc": "battlecards" };
    Object.entries(map).forEach(([id, key]) => {
      const a = document.getElementById(id);
      if (a) a.href = k.discover[key] || "#";
    });
  }
}

function bindKibanaActions() {
  const btn = document.getElementById("kibana-setup");
  if (!btn || btn._bound) return;
  btn._bound = true;
  btn.addEventListener("click", async () => {
    const old = btn.textContent;
    btn.textContent = "creating...";
    btn.disabled = true;
    try {
      const res = await apiPost("/kibana/setup", {});
      if (res.ok) {
        const created = (res.items || []).filter((i) => i.ok).length;
        toast(`Created ${created}/${(res.items || []).length} Kibana data views`, "ok");
      } else {
        toast(`Kibana setup failed: ${res.error || "unknown"}`, "bad");
      }
    } catch (e) {
      toast(`Kibana setup failed: ${e.message}`, "bad");
    } finally {
      btn.textContent = old;
      btn.disabled = false;
    }
  });
}

function updateESPanel(es) {
  const state = document.getElementById("es-state");
  const urlEl = document.getElementById("es-url");
  if (!state) return;
  if (es && es.available) {
    state.textContent = "connected";
    state.className = "es-state es-up";
  } else {
    state.textContent = "offline";
    state.className = "es-state es-down";
  }
  if (urlEl) urlEl.textContent = (es && es.url) || "";
}

function bindESActions() {
  const reindex = document.getElementById("es-reindex");
  const reconnect = document.getElementById("es-reconnect");
  if (reindex && !reindex._bound) {
    reindex._bound = true;
    reindex.addEventListener("click", async () => {
      const old = reindex.textContent;
      reindex.textContent = "indexing...";
      reindex.disabled = true;
      try {
        const res = await apiPost("/briefs/reindex", {});
        toast(`Reindexed ${res.indexed.briefs} briefs and ${res.indexed.post_meetings} post-meetings to ES`, "ok");
        await loadHistory();
      } catch (e) {
        toast(`Reindex failed: ${e.message}`, "bad");
      } finally {
        reindex.textContent = old;
        reindex.disabled = false;
      }
    });
  }
  if (reconnect && !reconnect._bound) {
    reconnect._bound = true;
    reconnect.addEventListener("click", async () => {
      const old = reconnect.textContent;
      reconnect.textContent = "reconnecting...";
      reconnect.disabled = true;
      try {
        const res = await apiPost("/elasticsearch/reconnect", {});
        updateESPanel(res);
        toast(res.available ? "Elasticsearch reconnected" : "Elasticsearch still offline", res.available ? "ok" : "bad");
      } catch (e) {
        toast(`Reconnect failed: ${e.message}`, "bad");
      } finally {
        reconnect.textContent = old;
        reconnect.disabled = false;
      }
    });
  }
}

async function loadMeetings() {
  try {
    ALL_MEETINGS = await apiGet("/meetings");
  } catch (e) {
    toast("Failed to load meetings", "bad");
    return;
  }

  const upcoming = ALL_MEETINGS.filter((m) => m.is_upcoming);
  const past = ALL_MEETINGS.filter((m) => !m.is_upcoming);
  const companyIds = new Set(ALL_MEETINGS.map((m) => m.company_id));

  setText("stat-companies", String(companyIds.size));
  setText("stat-upcoming", String(upcoming.length));
  setText("stat-past", String(past.length));
  setText("upcoming-count", `${upcoming.length}`);
  setText("past-count", `${past.length}`);
  setText("meetings-count", `${ALL_MEETINGS.length} total`);

  applyFilter("");
  bindFilter();
}

function applyFilter(query) {
  const q = (query || "").trim().toLowerCase();
  const matches = (m) =>
    !q ||
    [m.title, m.company_name, m.company_industry, m.id]
      .filter(Boolean)
      .some((s) => s.toLowerCase().includes(q));

  const upcoming = ALL_MEETINGS.filter((m) => m.is_upcoming && matches(m));
  const past = ALL_MEETINGS.filter((m) => !m.is_upcoming && matches(m));
  renderList(document.getElementById("upcoming"), upcoming, true);
  renderList(document.getElementById("past"), past, false);
}

function bindFilter() {
  const input = document.getElementById("meetings-search");
  if (!input) return;
  input.addEventListener("input", (e) => applyFilter(e.target.value));
}

function bindKeyboard() {
  window.addEventListener("keydown", (e) => {
    if (e.key === "/" && document.activeElement?.tagName !== "INPUT" && document.activeElement?.tagName !== "TEXTAREA") {
      e.preventDefault();
      document.getElementById("meetings-search")?.focus();
    }
  });
}

function bindQuickResearch() {
  const form = document.getElementById("qr-form");
  if (!form) return;
  const submit = document.getElementById("qr-submit");
  const statusEl = document.getElementById("qr-status");

  form.addEventListener("submit", async () => {
    const name = document.getElementById("qr-name").value.trim();
    if (!name) {
      toast("Company name is required", "bad");
      return;
    }
    const body = {
      company_name: name,
      industry: document.getElementById("qr-industry").value.trim(),
      size: document.getElementById("qr-size").value.trim(),
      tech_stack: document.getElementById("qr-stack").value.trim(),
      notes: document.getElementById("qr-notes").value.trim(),
      language: claudeLanguageName(),
      model: document.getElementById("qr-model")?.value || "",
    };

    const label = submit.innerHTML;
    submit.disabled = true;
    submit.innerHTML = '<span class="spinner"></span> Researching...';
    const MODEL_LABELS = {
      "claude-haiku-4-5": "Haiku 4.5",
      "claude-sonnet-4-6": "Sonnet 4.6",
      "claude-opus-4-7": "Opus 4.7",
      "": "Haiku 4.5 (default)",
    };
    const modelLabel = MODEL_LABELS[body.model] || body.model || "Haiku 4.5 (default)";
    statusEl.textContent = `Building dossier and calling Claude (${modelLabel})...`;
    try {
      const result = await apiPost("/agents/pre-meeting/ad-hoc", body);
      toast(`Brief generated for ${name}`, "ok");
      window.location.href = `/meeting.html?id=${encodeURIComponent(result.meeting_id)}&adhoc=1`;
    } catch (e) {
      toast(`Quick Research failed: ${e.message}`, "bad");
      statusEl.textContent = "";
    } finally {
      submit.disabled = false;
      submit.innerHTML = label;
    }
  });
}

function renderQuickResearchTemplates() {
  const row = document.getElementById("qr-templates-row");
  if (!row) return;
  row.innerHTML = "";
  INDUSTRY_TEMPLATES.forEach((tpl) => {
    const name = t(`tpl.${tpl.id}.name`, tpl.id);
    const tagline = t(`tpl.${tpl.id}.tagline`, "");
    const useLabel = t("tpl.use", "Use this template");

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = `qr-template qr-template-${tpl.accent}`;
    btn.setAttribute("role", "listitem");
    btn.setAttribute(
      "aria-label",
      `${useLabel}: ${name}. ${tagline}`.trim()
    );
    btn.dataset.tplId = tpl.id;

    btn.innerHTML = `
      <span class="qr-template-icon" aria-hidden="true">${tpl.icon}</span>
      <span class="qr-template-body">
        <span class="qr-template-name">${escapeHtml(name)}</span>
        <span class="qr-template-tagline">${escapeHtml(tagline)}</span>
      </span>
      <span class="qr-template-cta">
        <span class="qr-template-cta-label">${escapeHtml(useLabel)}</span>
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><polyline points="9 18 15 12 9 6"/></svg>
      </span>
    `;

    btn.addEventListener("click", () => applyIndustryTemplate(tpl));
    row.appendChild(btn);
  });
}

function applyIndustryTemplate(tpl) {
  const f = tpl.fields || {};
  const industry = document.getElementById("qr-industry");
  const size = document.getElementById("qr-size");
  const stack = document.getElementById("qr-stack");
  const notes = document.getElementById("qr-notes");
  const model = document.getElementById("qr-model");
  const name = document.getElementById("qr-name");

  if (industry) industry.value = f.industry || "";
  if (size) size.value = f.size || "";
  if (stack) stack.value = f.tech_stack || "";
  if (notes) notes.value = f.notes || "";
  if (model && f.model) {
    const exists = Array.from(model.options).some((o) => o.value === f.model);
    model.value = exists ? f.model : "";
  }

  // Visually mark the active tile.
  document.querySelectorAll(".qr-template").forEach((el) => {
    el.classList.toggle("is-active", el.dataset.tplId === tpl.id);
  });

  // Focus the company-name input so the FE can keep typing.
  if (name) {
    name.focus();
    try {
      name.scrollIntoView({ behavior: "smooth", block: "center" });
    } catch (e) {
      /* old browsers */
    }
  }

  showTemplateAppliedPill(tpl);
}

function showTemplateAppliedPill(tpl) {
  const host = document.getElementById("qr-applied-host");
  if (!host) return;
  const name = t(`tpl.${tpl.id}.name`, tpl.id);
  const text = t("tpl.applied", "Template applied").replace("{name}", name);
  host.innerHTML = "";
  const pill = document.createElement("span");
  pill.className = `qr-applied-pill qr-applied-${tpl.accent}`;
  pill.innerHTML = `
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><polyline points="20 6 9 17 4 12"/></svg>
    <span>${escapeHtml(text)}</span>
  `;
  host.appendChild(pill);
  // Force a reflow so the fade-out transition triggers reliably.
  // eslint-disable-next-line no-unused-expressions
  pill.offsetHeight;
  pill.classList.add("is-show");
  clearTimeout(host._fadeTimer);
  host._fadeTimer = setTimeout(() => {
    pill.classList.remove("is-show");
    pill.classList.add("is-hide");
    setTimeout(() => {
      if (host.contains(pill)) host.removeChild(pill);
    }, 320);
  }, 2000);
}

function escapeHtml(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

async function loadHistory() {
  try {
    const data = await apiGet("/briefs");
    const items = data.items || [];
    setText("stat-briefs", String(items.length));
    setText("history-count", `${items.length} artifact${items.length === 1 ? "" : "s"}`);
    const host = document.getElementById("history");
    clear(host);
    if (!items.length) {
      host.appendChild(el("li", { class: "muted" }, "No briefs generated yet. Use Quick Research above or run an agent on a meeting."));
      return;
    }
    items.slice(0, 12).forEach((it) => host.appendChild(renderHistoryRow(it)));
  } catch (e) {
    /* swallow; history is optional */
  }
}

async function loadAudit() {
  try {
    const data = await apiGet("/audit");
    const t = data.totals || { calls: 0, input_tokens: 0, output_tokens: 0 };
    setText("audit-calls", String(t.calls));
    setText("audit-in", t.input_tokens.toLocaleString());
    setText("audit-out", t.output_tokens.toLocaleString());
  } catch (e) {
    /* keep zeros */
  }
}

function prettyModel(id) {
  if (!id) return "unknown";
  if (id.includes("haiku")) return "Haiku 4.5";
  if (id.includes("sonnet")) return "Sonnet 4.6";
  if (id.includes("opus")) return "Opus 4.7";
  return id;
}

function renderList(host, items, isUpcoming) {
  clear(host);
  if (!items.length) {
    host.appendChild(el("li", { class: "muted empty" }, isUpcoming ? "No upcoming meetings match." : "No past meetings match."));
    return;
  }
  items.forEach((m) => host.appendChild(renderRow(m, isUpcoming)));
}

function renderRow(m, isUpcoming) {
  const pill = el(
    "span",
    { class: "pill " + (isUpcoming ? "upcoming" : "past") },
    isUpcoming ? "Upcoming" : "Past"
  );
  const info = el("div", { class: "info" }, [
    el("div", { class: "title" }, m.title),
    el("div", { class: "meta" }, [
      pill,
      el("span", { class: "dot" }, "·"),
      el("span", {}, m.company_name || ""),
      el("span", { class: "dot" }, "·"),
      el("span", {}, m.company_industry || ""),
      el("span", { class: "dot" }, "·"),
      el("span", {}, fmtDate(m.start_time)),
    ]),
  ]);

  const openBtn = el(
    "a",
    { class: "btn ghost", href: `/meeting.html?id=${encodeURIComponent(m.id)}` },
    "Open"
  );

  let actionBtn;
  if (isUpcoming) {
    const runLabel = "Run Pre-Meeting";
    actionBtn = el(
      "button",
      {
        class: "btn primary",
        onclick: async (ev) => {
          const btn = ev.currentTarget;
          const labelHTML = btn.innerHTML;
          btn.disabled = true;
          btn.innerHTML = '<span class="spinner"></span> Running...';
          try {
            await apiPost(`/agents/pre-meeting/${m.id}?language=${encodeURIComponent(claudeLanguageName())}`, {});
            toast(`Brief generated for ${m.company_name}`, "ok");
            window.location.href = `/meeting.html?id=${encodeURIComponent(m.id)}&brief=1`;
            return;
          } catch (e) {
            toast(`Pre-Meeting failed: ${e.message}`, "bad");
          } finally {
            btn.disabled = false;
            btn.innerHTML = labelHTML;
          }
        },
      },
      runLabel
    );
  } else {
    const runLabel = "Run Post-Meeting";
    actionBtn = el(
      "button",
      {
        class: "btn",
        onclick: async (ev) => {
          const btn = ev.currentTarget;
          const labelHTML = btn.innerHTML;
          btn.disabled = true;
          btn.innerHTML = '<span class="spinner"></span> Running...';
          try {
            await apiPost(`/agents/post-meeting/${m.id}?language=${encodeURIComponent(claudeLanguageName())}`, {});
            toast(`Post-meeting result for ${m.company_name}`, "ok");
            window.location.href = `/meeting.html?id=${encodeURIComponent(m.id)}&post=1`;
            return;
          } catch (e) {
            toast(`Post-Meeting failed: ${e.message}`, "bad");
          } finally {
            btn.disabled = false;
            btn.innerHTML = labelHTML;
          }
        },
      },
      runLabel
    );
  }

  return el("li", { class: isUpcoming ? "upcoming" : "past" }, [info, el("div", { class: "actions" }, [openBtn, actionBtn])]);
}

function renderHistoryRow(item) {
  const typeLabel = item.type === "post_meeting" ? "Post-meeting" : item.ad_hoc ? "Ad-hoc brief" : "Pre-meeting brief";
  const typeClass = item.type === "post_meeting" ? "blue" : item.ad_hoc ? "pink" : "teal";
  const headline = item.headline || item.summary || "(no headline)";

  const link = `/meeting.html?id=${encodeURIComponent(item.meeting_id)}${item.type === "post_meeting" ? "&post=1" : ""}`;
  return el("li", {}, [
    el("a", { class: "hist-link", href: link }, [
      el("span", { class: `pill ${typeClass}` }, typeLabel),
      el("span", { class: "hist-headline" }, headline),
      el("span", { class: "muted small" }, [
        el("span", {}, item.company_name || item.company_id || ""),
        el("span", { class: "dot" }, " · "),
        el("span", {}, fmtDate(item.generated_at)),
      ]),
    ]),
  ]);
}
