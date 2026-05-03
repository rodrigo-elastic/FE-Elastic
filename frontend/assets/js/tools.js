/*
  filename: tools.js
  description: Frontend handlers for the seven FE technical tools (POC plan, SPL-to-ES|QL, compliance, cost calc, capacity planner, stack extract, code sample).
  Author: Rodrigo Careaga
  Date: 03-05-2026
*/
(async function init() {
  applyI18n();
  renderLangPicker(document.getElementById("lang-host"));
  await populatePocMeetings();
  bindAll();
})();

async function populatePocMeetings() {
  const select = document.getElementById("poc-meeting-id");
  if (!select) return;
  try {
    const meetings = await apiGet("/meetings");
    const past = meetings.filter((m) => !m.is_upcoming);
    if (!past.length) {
      select.appendChild(el("option", { value: "" }, "(no past meetings on file)"));
      return;
    }
    past.forEach((m) =>
      select.appendChild(el("option", { value: m.id }, `${m.company_name || m.company_id} — ${m.title}`))
    );
  } catch (e) {
    select.appendChild(el("option", { value: "" }, "(failed to load meetings)"));
  }
}

function bindAll() {
  bindToolForm("poc-form", "poc-status", "Generate POC plan", runPocPlan);
  bindToolForm("spl-form", "spl-status", "Convert to ES|QL", runSplConvert);
  bindToolForm("comp-form", "comp-status", "Map to Elastic controls", runCompliance);
  bindToolForm("cost-form", "cost-status", "Calculate TCO", runCostCalc);
  bindToolForm("cap-form", "cap-status", "Plan cluster", runCapacity);
  bindToolForm("stack-form", "stack-status", "Extract stack", runStackExtract);
  bindToolForm("code-form", "code-status", "Generate code", runCodeSample);
}

function bindToolForm(formId, statusId, label, runner) {
  const form = document.getElementById(formId);
  if (!form) return;
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const submit = form.querySelector('button[type="submit"]');
    const status = document.getElementById(statusId);
    const labelHTML = submit.innerHTML;
    submit.disabled = true;
    submit.innerHTML = '<span class="spinner"></span> Running...';
    status.textContent = "Calling Claude...";
    try {
      await runner();
      status.textContent = "";
    } catch (e) {
      toast(`Failed: ${e.message}`, "bad");
      status.textContent = "Failed; see toast.";
    } finally {
      submit.disabled = false;
      submit.innerHTML = labelHTML;
    }
  });
}

// ----------------------------------------------------------------- POC Plan

async function runPocPlan() {
  const meetingId = document.getElementById("poc-meeting-id").value;
  if (!meetingId) throw new Error("pick a meeting first");
  const model = document.getElementById("poc-model").value;
  const body = { language: claudeLanguageName(), model };
  const res = await apiPost(`/tools/poc-plan/${encodeURIComponent(meetingId)}`, body);
  renderPocPlan(res);
}

function renderPocPlan(plan) {
  const host = document.getElementById("poc-result");
  clear(host);
  host.appendChild(el("div", { class: "brief-headline" }, plan.executive_summary || ""));

  // Success criteria
  if (plan.success_criteria?.length) {
    host.appendChild(el("h4", { class: "tool-section" }, "Success criteria"));
    const tbl = el("table", { class: "tool-table" });
    tbl.appendChild(el("thead", {}, [el("tr", {}, [
      el("th", {}, "Metric"), el("th", {}, "Target"), el("th", {}, "Source"),
    ])]));
    const tbody = el("tbody");
    plan.success_criteria.forEach((c) => {
      tbody.appendChild(
        el("tr", {}, [
          el("td", {}, c.metric),
          el("td", { class: "mono" }, c.target),
          el("td", { class: "muted small" }, `"${c.source_quote}"`),
        ])
      );
    });
    tbl.appendChild(tbody);
    host.appendChild(tbl);
  }

  // Phases
  if (plan.phases?.length) {
    host.appendChild(el("h4", { class: "tool-section" }, "Phases"));
    const grid = el("div", { class: "phases-grid" });
    plan.phases.forEach((p, i) => {
      const card = el("div", { class: "phase-card" });
      card.appendChild(
        el("div", { class: "phase-head" }, [
          el("span", { class: "phase-num" }, "P" + (i + 1)),
          el("div", {}, [
            el("div", { class: "phase-name" }, p.name),
            el("div", { class: "phase-weeks" }, p.weeks),
          ]),
        ])
      );
      const ul = el("ul", { class: "phase-list" });
      (p.activities || []).forEach((a) => ul.appendChild(el("li", {}, a)));
      card.appendChild(ul);
      if (p.deliverables?.length) {
        card.appendChild(el("div", { class: "phase-section-lbl" }, "Deliverables"));
        const dul = el("ul", { class: "phase-list phase-deliverables" });
        p.deliverables.forEach((d) => dul.appendChild(el("li", {}, d)));
        card.appendChild(dul);
      }
      const owners = p.technical_owners || {};
      if (owners.elastic?.length || owners.customer?.length) {
        card.appendChild(
          el("div", { class: "phase-owners" }, [
            el("span", { class: "phase-section-lbl" }, "Owners"),
            el("span", { class: "muted small" }, `Elastic: ${(owners.elastic || []).join(", ") || "-"} · Customer: ${(owners.customer || []).join(", ") || "-"}`),
          ])
        );
      }
      grid.appendChild(card);
    });
    host.appendChild(grid);
  }

  // Resources
  const r = plan.resource_requests || {};
  host.appendChild(el("h4", { class: "tool-section" }, "Resource requests"));
  host.appendChild(
    el("div", { class: "tool-pills" }, [
      el("span", { class: "tool-pill" }, `FE: ${r.fe_hours || "n/a"}`),
      el("span", { class: "tool-pill" }, `Customer: ${r.customer_hours || "n/a"}`),
      el("span", { class: "tool-pill" }, `Infra: ${r.infrastructure || "n/a"}`),
    ])
  );

  // Risks
  if (plan.risks?.length) {
    host.appendChild(el("h4", { class: "tool-section" }, "Risks"));
    const list = el("ul", { class: "risk-list" });
    plan.risks.forEach((r) => {
      list.appendChild(
        el("li", {}, [
          el("div", { class: "risk-desc" }, r.description),
          el("div", { class: "risk-mit muted small" }, "→ " + r.mitigation),
        ])
      );
    });
    host.appendChild(list);
  }
}

// ----------------------------------------------------------------- SPL → ES|QL

async function runSplConvert() {
  const spl = document.getElementById("spl-input").value.trim();
  if (!spl || spl.length < 5) throw new Error("paste an SPL query first");
  const model = document.getElementById("spl-model").value;
  const body = { spl, language: claudeLanguageName(), model };
  const res = await apiPost("/tools/spl-to-esql", body);
  const host = document.getElementById("spl-result");
  clear(host);
  host.appendChild(el("h4", { class: "tool-section" }, "ES|QL output"));
  host.appendChild(el("pre", { class: "code-block" }, res.esql));
  host.appendChild(el("h4", { class: "tool-section" }, "Explanation"));
  host.appendChild(el("p", {}, res.explanation));
  if (res.caveats?.length) {
    host.appendChild(el("h4", { class: "tool-section" }, "Caveats"));
    const ul = el("ul");
    res.caveats.forEach((c) => ul.appendChild(el("li", {}, c)));
    host.appendChild(ul);
  }
}

// ----------------------------------------------------------------- Compliance

async function runCompliance() {
  const regs = Array.from(document.querySelectorAll("#comp-regs input:checked")).map((c) => c.value);
  if (!regs.length) throw new Error("pick at least one regulation");
  if (regs.length > 6) throw new Error("max 6 regulations");
  const industry = document.getElementById("comp-industry").value.trim();
  const model = document.getElementById("comp-model").value;
  const body = { regulations: regs, industry, language: claudeLanguageName(), model };
  const res = await apiPost("/tools/compliance-mapping", body);

  const host = document.getElementById("comp-result");
  clear(host);
  (res.mappings || []).forEach((m) => {
    const card = el("div", { class: "comp-card" });
    card.appendChild(
      el("div", { class: "comp-head" }, [
        el("span", { class: "comp-reg" }, m.regulation),
        el("span", { class: "muted small" }, m.industry_note || ""),
      ])
    );
    const tbl = el("table", { class: "tool-table" });
    tbl.appendChild(el("thead", {}, [el("tr", {}, [
      el("th", {}, "Requirement"), el("th", {}, "Elastic control"), el("th", { style: "width:80px" }, "Native"),
    ])]));
    const tbody = el("tbody");
    (m.requirements || []).forEach((r) => {
      tbody.appendChild(
        el("tr", {}, [
          el("td", {}, r.requirement),
          el("td", { class: r.native ? "" : "muted" }, r.elastic_control),
          el("td", {}, [el("span", { class: "native-badge " + (r.native ? "yes" : "no") }, r.native ? "yes" : "gap")]),
        ])
      );
    });
    tbl.appendChild(tbody);
    card.appendChild(tbl);
    host.appendChild(card);
  });
}

// ----------------------------------------------------------------- Cost calc

async function runCostCalc() {
  const body = {
    ingest_gb_day: parseFloat(document.getElementById("cost-ingest").value) || 0,
    retention_months: parseInt(document.getElementById("cost-retention").value) || 12,
    hot_pct: parseFloat(document.getElementById("cost-hot").value) || 30,
    warm_pct: parseFloat(document.getElementById("cost-warm").value) || 30,
    frozen_pct: parseFloat(document.getElementById("cost-frozen").value) || 40,
  };
  const cur = parseFloat(document.getElementById("cost-current").value);
  if (!isNaN(cur) && cur > 0) body.current_spend_annual_usd = cur;

  const res = await apiPost("/tools/cost-calc", body);
  const host = document.getElementById("cost-result");
  clear(host);

  const fmt = (n) => "$" + Math.round(n).toLocaleString("en-US");
  const elastic = res.elastic || {};
  const splunk = res.splunk || {};
  const datadog = res.datadog || {};

  const max = Math.max(elastic.total_annual_usd || 0, splunk.total_annual_usd || 0, datadog.total_annual_usd || 0, 1);

  const bar = (label, val, color) => {
    const w = Math.max(8, (val / max) * 100);
    return el("div", { class: "bar-row" }, [
      el("div", { class: "bar-label" }, label),
      el("div", { class: "bar-track" }, [
        el("div", { class: "bar-fill bar-fill-" + color, style: `width:${w}%` }, null),
      ]),
      el("div", { class: "bar-val" }, fmt(val)),
    ]);
  };

  host.appendChild(el("h4", { class: "tool-section" }, "12-month TCO comparison"));
  host.appendChild(
    el("div", { class: "bar-chart" }, [
      bar("Elastic Cloud", elastic.total_annual_usd || 0, "primary"),
      bar("Splunk", splunk.total_annual_usd || 0, "pink"),
      bar("Datadog", datadog.total_annual_usd || 0, "yellow"),
    ])
  );

  if (res.savings_pct_vs_current != null) {
    const sign = res.savings_pct_vs_current >= 0 ? "saves" : "costs more by";
    const pct = Math.abs(res.savings_pct_vs_current).toFixed(1);
    host.appendChild(
      el("div", { class: "savings-callout" }, [
        el("strong", {}, `${sign} ${pct}%`),
        el("span", {}, ` vs current (${fmt(res.savings_vs_current || 0)} delta).`),
      ])
    );
  }

  // Elastic breakdown
  host.appendChild(el("h4", { class: "tool-section" }, "Elastic breakdown by tier"));
  const ebreak = el("div", { class: "tool-pills" }, [
    el("span", { class: "tool-pill" }, `Hot ${Math.round(elastic.hot_gb || 0).toLocaleString()} GB → ${fmt(elastic.hot_cost || 0)}/yr`),
    el("span", { class: "tool-pill" }, `Warm ${Math.round(elastic.warm_gb || 0).toLocaleString()} GB → ${fmt(elastic.warm_cost || 0)}/yr`),
    el("span", { class: "tool-pill" }, `Frozen ${Math.round(elastic.frozen_gb || 0).toLocaleString()} GB → ${fmt(elastic.frozen_cost || 0)}/yr`),
  ]);
  host.appendChild(ebreak);

  if (res.notes?.length) {
    host.appendChild(el("h4", { class: "tool-section" }, "Assumptions"));
    const ul = el("ul", { class: "muted small" });
    res.notes.forEach((n) => ul.appendChild(el("li", {}, n)));
    host.appendChild(ul);
  }
}

// ----------------------------------------------------------------- Capacity

async function runCapacity() {
  const body = {
    peak_indexing_eps: parseInt(document.getElementById("cap-eps").value) || 0,
    hot_data_gb: parseInt(document.getElementById("cap-hot").value) || 0,
    warm_data_gb: parseInt(document.getElementById("cap-warm").value) || 0,
    replicas: parseInt(document.getElementById("cap-replicas").value) || 1,
    peak_qps: parseInt(document.getElementById("cap-qps").value) || 100,
  };
  const res = await apiPost("/tools/capacity", body);
  const host = document.getElementById("cap-result");
  clear(host);

  host.appendChild(el("h4", { class: "tool-section" }, "Recommended cluster topology"));
  const grid = el("div", { class: "phases-grid" });
  const tier = (label, info, klass) => {
    const card = el("div", { class: "phase-card cap-tier " + (klass || "") });
    card.appendChild(el("div", { class: "phase-name" }, label));
    Object.entries(info || {}).forEach(([k, v]) => {
      card.appendChild(
        el("div", { class: "muted small" }, [
          el("span", {}, k.replace(/_/g, " ") + ": "),
          el("strong", { style: "color: var(--ink)" }, String(v)),
        ])
      );
    });
    return card;
  };
  grid.appendChild(tier("Hot tier", res.hot, "tier-hot"));
  grid.appendChild(tier("Warm tier", res.warm, "tier-warm"));
  grid.appendChild(tier("Frozen tier", res.frozen, "tier-frozen"));
  grid.appendChild(tier("Master", res.master, ""));
  grid.appendChild(tier("Kibana", res.kibana, ""));
  host.appendChild(grid);

  if (res.rationale?.length) {
    host.appendChild(el("h4", { class: "tool-section" }, "Rationale"));
    const ul = el("ul", { class: "muted small" });
    res.rationale.forEach((r) => ul.appendChild(el("li", {}, r)));
    host.appendChild(ul);
  }
}

// ----------------------------------------------------------------- Stack extract

async function runStackExtract() {
  const text = document.getElementById("stack-input").value;
  if (!text || text.trim().length < 20) throw new Error("text too short (min 20 chars)");
  const model = document.getElementById("stack-model").value;
  const body = { text, language: claudeLanguageName(), model };
  const res = await apiPost("/tools/stack-extract", body);

  const host = document.getElementById("stack-result");
  clear(host);
  const buckets = [
    ["observability", "Observability", "teal"],
    ["search", "Search", "blue"],
    ["cloud", "Cloud", "yellow"],
    ["data", "Data", "primary"],
    ["languages", "Languages", "pink"],
    ["frameworks", "Frameworks", "muted"],
  ];
  const grid = el("div", { class: "stack-grid" });
  buckets.forEach(([key, label, klass]) => {
    const items = res[key] || [];
    const card = el("div", { class: "stack-bucket stack-" + klass });
    card.appendChild(el("div", { class: "stack-head" }, [el("span", {}, label), el("span", { class: "muted small" }, "" + items.length)]));
    if (!items.length) card.appendChild(el("div", { class: "muted small" }, "—"));
    items.forEach((it) => {
      card.appendChild(
        el("div", { class: "stack-item", title: it.evidence || "" }, [
          el("span", { class: "stack-name" }, it.name),
          el("span", { class: "muted small" }, " ↳ " + (it.evidence || "")),
        ])
      );
    });
    grid.appendChild(card);
  });
  host.appendChild(grid);
}

// ----------------------------------------------------------------- Code sample

async function runCodeSample() {
  const language = document.getElementById("code-lang").value;
  const useCase = document.getElementById("code-usecase").value;
  const model = document.getElementById("code-model").value;
  const body = { language, use_case: useCase, response_language: claudeLanguageName(), model };
  const res = await apiPost("/tools/code-sample", body);

  const host = document.getElementById("code-result");
  clear(host);
  host.appendChild(el("h4", { class: "tool-section" }, res.title || `${language} sample`));
  host.appendChild(el("p", {}, res.explanation || ""));
  if (res.prerequisites?.length) {
    host.appendChild(el("h4", { class: "tool-section" }, "Prerequisites"));
    const ul = el("ul", { class: "muted small" });
    res.prerequisites.forEach((p) => ul.appendChild(el("li", {}, [el("code", {}, p)])));
    host.appendChild(ul);
  }
  host.appendChild(el("pre", { class: "code-block" }, res.code || ""));
  // Copy button
  const copyBtn = el(
    "button",
    {
      class: "btn ghost",
      onclick: async () => {
        try {
          await navigator.clipboard.writeText(res.code || "");
          toast("Code copied to clipboard", "ok");
        } catch (e) {
          toast("Copy failed", "bad");
        }
      },
    },
    "Copy code"
  );
  host.appendChild(copyBtn);
}
