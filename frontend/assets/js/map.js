/*
  filename: map.js
  description: Mutual Action Plan UI. Fetches /map/{meeting_id}, renders left
  grid (workstreams + editable milestones) and right narrative (goal,
  stakeholders, risks, cadence). Saves row edits via PUT, emails the rendered
  plan, downloads the PDF, and supports a regenerate path.
  Author: Rodrigo Careaga
  Date: 05-13-2026
*/
(function () {
  const STATUSES = ["not_started", "in_progress", "blocked", "done"];
  const STATUS_LABEL = {
    not_started: "Not started",
    in_progress: "In progress",
    blocked: "Blocked",
    done: "Done",
  };
  const LS_PREFIX = "fec.map.draft.";

  function qs(name) {
    return new URLSearchParams(window.location.search).get(name);
  }

  function statusPill(s) {
    return el("span", { class: "map-pill " + (s === "active" ? "active" : "draft") }, s || "draft");
  }

  function setStatus(text) {
    const s = document.getElementById("status");
    if (s) s.textContent = text;
  }

  function lsDraftKey(meetingId) { return LS_PREFIX + meetingId; }

  function rememberEdit(meetingId, milestoneId, patch) {
    try {
      const k = lsDraftKey(meetingId);
      const raw = localStorage.getItem(k);
      const obj = raw ? JSON.parse(raw) : {};
      obj[milestoneId] = Object.assign({}, obj[milestoneId] || {}, patch, { ts: Date.now() });
      localStorage.setItem(k, JSON.stringify(obj));
    } catch (e) { /* ignore */ }
  }

  function clearEdit(meetingId, milestoneId) {
    try {
      const k = lsDraftKey(meetingId);
      const raw = localStorage.getItem(k);
      if (!raw) return;
      const obj = JSON.parse(raw);
      delete obj[milestoneId];
      localStorage.setItem(k, JSON.stringify(obj));
    } catch (e) { /* ignore */ }
  }

  // ============================================================ rendering =============

  function renderMilestoneRow(meetingId, m, onSaved) {
    const tr = el("tr", { class: "map-row", "data-mid": m.id });
    const dateInput = el("input", { type: "date", value: m.date || "" });
    const ownerE = el("input", { type: "text", value: m.owner_elastic || "" });
    const ownerC = el("input", { type: "text", value: m.owner_customer || "" });
    const blockerInput = el("input", { type: "text", value: m.blocker_note || "" });
    const statusSel = el("select");
    STATUSES.forEach(s => {
      const o = el("option", { value: s }, STATUS_LABEL[s]);
      if (s === m.status) o.selected = true;
      statusSel.appendChild(o);
    });
    statusSel.className = "status-" + (m.status || "not_started");

    const titleCell = el("td", null, m.title || "(milestone)");
    const dateCell = el("td"); dateCell.appendChild(dateInput);
    const ownerECell = el("td"); ownerECell.appendChild(ownerE);
    const ownerCCell = el("td"); ownerCCell.appendChild(ownerC);
    const statusCell = el("td"); statusCell.appendChild(statusSel);
    const blockerCell = el("td"); blockerCell.appendChild(blockerInput);

    tr.appendChild(titleCell);
    tr.appendChild(dateCell);
    tr.appendChild(ownerECell);
    tr.appendChild(ownerCCell);
    tr.appendChild(statusCell);
    tr.appendChild(blockerCell);

    let saveTimer = null;
    function schedule() {
      const patch = {
        date: dateInput.value,
        owner_elastic: ownerE.value,
        owner_customer: ownerC.value,
        status: statusSel.value,
        blocker_note: blockerInput.value,
      };
      rememberEdit(meetingId, m.id, patch);
      statusSel.className = "status-" + (statusSel.value || "not_started");
      if (saveTimer) clearTimeout(saveTimer);
      saveTimer = setTimeout(async () => {
        try {
          await apiPut(`/map/${encodeURIComponent(meetingId)}/milestone/${encodeURIComponent(m.id)}`, patch);
          tr.classList.remove("map-row-saved");
          void tr.offsetWidth; // restart animation
          tr.classList.add("map-row-saved");
          clearEdit(meetingId, m.id);
          if (typeof onSaved === "function") onSaved();
        } catch (err) {
          toast("Save failed: " + sanitizeError(err), "warn");
        }
      }, 450);
    }
    [dateInput, ownerE, ownerC, blockerInput].forEach(i => i.addEventListener("input", schedule));
    statusSel.addEventListener("change", schedule);
    return tr;
  }

  function renderLeft(record) {
    const plan = record.plan || {};
    const wrap = el("section", { class: "map-panel" });
    const meta = el("div", { class: "map-meta" });
    meta.appendChild(el("div", null, [el("strong", null, "Company: "), record.company_name || "(unknown)"]));
    meta.appendChild(el("div", null, [el("strong", null, "Target close: "), plan.target_close_date || "-"]));
    if (plan.deal_value_usd) meta.appendChild(el("div", null, [el("strong", null, "Deal value: "), "$" + Number(plan.deal_value_usd).toLocaleString()]));
    meta.appendChild(el("div", null, [el("strong", null, "Last update: "), (record.updated_at || "").slice(0, 19).replace("T", " ")]));
    meta.appendChild(statusPill(record.status));
    wrap.appendChild(meta);

    wrap.appendChild(el("div", { class: "map-section-h" }, "Workstreams"));
    (plan.workstreams || []).forEach(w => {
      const node = el("div", { class: "map-ws" });
      node.appendChild(el("div", { class: "map-ws-title" }, w.title || "(workstream)"));
      node.appendChild(el("div", null, w.description || ""));
      const m = el("div", { class: "map-ws-meta" });
      m.appendChild(el("span", null, "Elastic: " + (w.owner_elastic || "-")));
      m.appendChild(el("span", null, "Customer: " + (w.owner_customer || "-")));
      m.appendChild(el("span", null, "Status: " + STATUS_LABEL[w.status] || w.status || "-"));
      node.appendChild(m);
      wrap.appendChild(node);
    });

    wrap.appendChild(el("div", { class: "map-section-h" }, "Milestones (edit any row to save)"));
    const table = el("table", { class: "map-grid" });
    const thead = el("thead");
    const trh = el("tr");
    ["Title", "Date", "Elastic owner", "Customer owner", "Status", "Blocker if missed"].forEach(h => trh.appendChild(el("th", null, h)));
    thead.appendChild(trh);
    table.appendChild(thead);
    const tbody = el("tbody");
    (plan.milestones || []).forEach(m => tbody.appendChild(renderMilestoneRow(record.meeting_id, m, () => {
      // bump last-update display
      const now = new Date().toISOString().slice(0, 19).replace("T", " ");
      const labels = wrap.querySelectorAll(".map-meta div");
      // (no-op visual; the saved animation is enough confirmation)
      void now; void labels;
    })));
    table.appendChild(tbody);
    wrap.appendChild(table);
    return wrap;
  }

  function renderRight(record, ctx) {
    const plan = record.plan || {};
    const wrap = el("section", { class: "map-panel" });

    const actions = el("div", { class: "map-actions" });
    const regen = el("button", { class: "btn ghost", type: "button" }, "Re-generate");
    const email = el("button", { class: "btn ghost", type: "button" }, "Email to champion");
    const pdf = el("button", { class: "btn ghost", type: "button" }, "Download PDF");
    const handover = el("a", { class: "btn ghost", href: `/customer-health.html?meeting_id=${encodeURIComponent(record.meeting_id)}` }, "Share with CA");
    [regen, email, pdf, handover].forEach(a => actions.appendChild(a));
    wrap.appendChild(actions);

    regen.addEventListener("click", async () => {
      if (!confirm("Re-generate this MAP from the source dossier? Inline edits will be replaced.")) return;
      regen.disabled = true; regen.textContent = "Re-generating...";
      try {
        const rec = await apiPost(`/map/from-meeting/${encodeURIComponent(record.meeting_id)}`, { regenerate: true });
        toast("MAP regenerated", "ok");
        ctx.setRecord(rec);
      } catch (err) {
        toast("Regenerate failed: " + sanitizeError(err), "warn");
      } finally {
        regen.disabled = false; regen.textContent = "Re-generate";
      }
    });

    email.addEventListener("click", async () => {
      const cust = prompt("Customer champion email (leave empty to skip):", "");
      const sa = prompt("SA email (leave empty to skip):", "");
      if (!cust && !sa) { toast("No recipients provided", "warn"); return; }
      try {
        const r = await apiPost(`/map/${encodeURIComponent(record.meeting_id)}/share`, { customer_email: cust || "", sa_email: sa || "" });
        toast("Shared: " + (r.results || []).map(x => x.to + (x.ok ? " ok" : " failed")).join(", "), "ok");
      } catch (err) {
        toast("Share failed: " + sanitizeError(err), "warn");
      }
    });

    pdf.addEventListener("click", async () => {
      try {
        const r = await apiPost(`/map/${encodeURIComponent(record.meeting_id)}/pdf`, {});
        if (r && r.artifact_url) window.open(r.artifact_url, "_blank", "noopener");
        else toast("PDF rendered to " + (r.artifact_path || "disk"), "ok");
      } catch (err) {
        toast("PDF failed: " + sanitizeError(err), "warn");
      }
    });

    wrap.appendChild(el("div", { class: "map-section-h" }, "Goal"));
    wrap.appendChild(el("p", null, plan.goal || "(no goal yet)"));
    if (plan.success_metric) wrap.appendChild(el("p", null, [el("strong", null, "Success metric: "), plan.success_metric]));

    wrap.appendChild(el("div", { class: "map-section-h" }, "Stakeholders"));
    (plan.stakeholders || []).forEach(s => {
      const n = el("div", { class: "map-stakeholder" });
      n.appendChild(el("div", { class: "nm" }, s.name || "(unnamed)"));
      n.appendChild(el("div", { class: "rl" }, [s.role, s.title, s.stance].filter(Boolean).join(" - ")));
      if (s.notes) n.appendChild(el("div", null, s.notes));
      wrap.appendChild(n);
    });

    wrap.appendChild(el("div", { class: "map-section-h" }, "Risks"));
    (plan.risks || []).forEach(r => {
      const n = el("div", { class: "map-risk" });
      n.appendChild(el("div", null, [el("span", { class: "sev-" + (r.severity || "medium") }, "[" + (r.severity || "medium") + "] "), el("span", { class: "ttl" }, r.title || "")]));
      if (r.description) n.appendChild(el("div", null, r.description));
      if (r.mitigation) n.appendChild(el("div", null, [el("em", null, "Mitigation: "), r.mitigation]));
      wrap.appendChild(n);
    });

    const cadence = plan.cadence || {};
    wrap.appendChild(el("div", { class: "map-section-h" }, "Communication cadence"));
    wrap.appendChild(el("p", null, [el("strong", null, "Weekly sync: "), cadence.weekly_sync || "-"]));
    wrap.appendChild(el("p", null, [el("strong", null, "MAP review: "), cadence.map_review_cadence || "-"]));
    wrap.appendChild(el("p", null, [el("strong", null, "Escalation: "), cadence.escalation_path || "-"]));
    return wrap;
  }

  function renderEmpty(meetingId) {
    const wrap = el("div", { class: "map-empty" });
    wrap.appendChild(el("p", null, "No Mutual Action Plan exists for this meeting yet."));
    const btn = el("button", { class: "btn primary", type: "button" }, "Generate MAP");
    wrap.appendChild(btn);
    btn.addEventListener("click", async () => {
      btn.disabled = true; btn.textContent = "Generating (25-40s)...";
      try {
        const rec = await apiPostWithRetry(`/map/from-meeting/${encodeURIComponent(meetingId)}`, {}, { category: "llm" });
        ctxRef.setRecord(rec);
      } catch (err) {
        toast("Generate failed: " + sanitizeError(err), "warn");
        btn.disabled = false; btn.textContent = "Generate MAP";
      }
    });
    return wrap;
  }

  // ============================================================ bootstrap ============

  const ctxRef = { setRecord: null };

  // Universal Elastic Mutual Action Plan template. Used when /map.html is
  // loaded without a ?meeting_id= - the FE gets a ready-to-edit 90-day
  // plan covering the canonical Elastic deal motion (POV, security, legal,
  // commercial, executive, go-live). Dates are anchored on today + offset
  // days so the timeline always reads as "next 90 days".
  function buildUniversalTemplate() {
    const today = new Date();
    const iso = (offsetDays) => {
      const d = new Date(today.getTime() + offsetDays * 86400000);
      return d.toISOString().slice(0, 10);
    };
    return {
      meeting_id: "universal-template",
      company_id: "elastic-universal-template",
      company_name: "[Customer Name]",
      ad_hoc: true,
      generated_at: today.toISOString(),
      updated_at: today.toISOString(),
      status: "draft",
      plan: {
        goal: {
          outcome: "Land an Elastic deployment that replaces or augments the customer's current observability / search / security stack inside 90 days, with measurable ROI vs the incumbent.",
          target_close_date: iso(90),
          success_metric: "Signed contract for Elastic Cloud, with the POV's primary KPI hit (e.g. ingest cost down >=30% vs incumbent, or search relevance up >=20%, or MTTR down >=40%).",
        },
        target_close_date: iso(90),
        deal_value_usd: null,
        success_metric: "Signed contract for Elastic Cloud, with the POV's primary KPI hit (e.g. ingest cost down >=30% vs incumbent, or search relevance up >=20%, or MTTR down >=40%).",
        stakeholders: [
          { role: "Economic Buyer", name: "[VP / CIO / CTO]", alignment: "neutral", note: "Owns the budget. Needs to see TCO vs incumbent and the strategic narrative." },
          { role: "Technical Evaluator", name: "[Lead Architect / SRE Lead]", alignment: "neutral", note: "Owns the POV success criteria. Drives the hands-on validation." },
          { role: "Champion", name: "[Engineering Manager / Platform Lead]", alignment: "aligned", note: "Day-to-day advocate. The person who replies on Slack." },
          { role: "Procurement", name: "[Procurement / Vendor Mgmt]", alignment: "neutral", note: "Owns the commercial paperwork and vendor onboarding." },
          { role: "Security / Compliance", name: "[CISO Office]", alignment: "neutral", note: "Owns the infosec questionnaire, DPIA, and any regulatory mapping." },
          { role: "Legal", name: "[Legal Counsel]", alignment: "neutral", note: "MSA / DPA review." },
        ],
        workstreams: [
          { name: "POV / Technical Evaluation", owner_elastic: "Solutions Architect", owner_customer: "Lead Architect", outcome: "POV success criteria met on the live cluster." },
          { name: "Security & Compliance Review", owner_elastic: "Field Compliance Architect", owner_customer: "CISO Office", outcome: "Infosec questionnaire returned and risk items resolved." },
          { name: "Commercial & TCO", owner_elastic: "Pricing Architect + AE", owner_customer: "Procurement + Economic Buyer", outcome: "Signed proposal with agreed pricing model and term." },
          { name: "Executive Alignment", owner_elastic: "AE + Sales Director", owner_customer: "Economic Buyer", outcome: "Executive sponsor signed off on the project." },
          { name: "Legal", owner_elastic: "Deal Desk", owner_customer: "Legal Counsel", outcome: "MSA / DPA / order form executed." },
          { name: "Go-live Readiness", owner_elastic: "CA (post-handover)", owner_customer: "Platform Lead", outcome: "Production environment deployed, runbooks in place." },
        ],
        milestones: [
          { id: "ms-01", title: "Joint Kickoff: MAP signed by both sides", date: iso(3), owner_elastic: "SA", owner_customer: "Champion", status: "not_started", blocker_note: "If kickoff slips, every downstream date slips one-for-one." },
          { id: "ms-02", title: "POV Success Criteria signed off", date: iso(10), owner_elastic: "SA", owner_customer: "Technical Evaluator", status: "not_started", blocker_note: "Without explicit criteria the POV cannot be declared a win." },
          { id: "ms-03", title: "Procurement looped in, vendor preference confirmed", date: iso(15), owner_elastic: "AE", owner_customer: "Procurement", status: "not_started", blocker_note: "Late procurement engagement adds 3-6 weeks to close." },
          { id: "ms-04", title: "Security questionnaire / DPIA submitted", date: iso(20), owner_elastic: "Field Compliance Architect", owner_customer: "CISO Office", status: "not_started", blocker_note: "Infosec is the most common deal blocker for regulated customers." },
          { id: "ms-05", title: "POV environment provisioned, data ingest live", date: iso(25), owner_elastic: "SA", owner_customer: "Lead Architect", status: "not_started", blocker_note: "If data is not flowing by week 4 the POV cannot finish in 90 days." },
          { id: "ms-06", title: "Mid-POV review with the Economic Buyer", date: iso(45), owner_elastic: "SA + AE", owner_customer: "Champion + Economic Buyer", status: "not_started", blocker_note: "First exec-level signal of momentum or risk." },
          { id: "ms-07", title: "POV success criteria validated", date: iso(60), owner_elastic: "SA", owner_customer: "Technical Evaluator", status: "not_started", blocker_note: "Validation evidence (dashboards, screenshots, queries) captured in the deal record." },
          { id: "ms-08", title: "Commercial proposal delivered + reviewed", date: iso(65), owner_elastic: "AE", owner_customer: "Economic Buyer", status: "not_started", blocker_note: "TCO vs incumbent must be explicit." },
          { id: "ms-09", title: "Legal review (MSA / DPA / order form)", date: iso(75), owner_elastic: "Deal Desk", owner_customer: "Legal Counsel", status: "not_started", blocker_note: "Common slip: redlines on data residency or audit logging." },
          { id: "ms-10", title: "Executive review and approval", date: iso(82), owner_elastic: "Sales Director", owner_customer: "Economic Buyer", status: "not_started", blocker_note: "If the Economic Buyer has not been re-engaged since the mid-POV, expect delays." },
          { id: "ms-11", title: "Contract signature", date: iso(88), owner_elastic: "AE", owner_customer: "Economic Buyer", status: "not_started", blocker_note: "Hard date; downstream go-live planning depends on this." },
          { id: "ms-12", title: "Go-live + handover to CA", date: iso(90), owner_elastic: "SA -> CA", owner_customer: "Platform Lead", status: "not_started", blocker_note: "First production workload onboarded; CA owns from here." },
        ],
        risks: [
          { description: "Competing project consumes Champion's bandwidth.", mitigation: "Confirm weekly time commitment at kickoff." },
          { description: "Budget freeze or fiscal-year cutoff before close date.", mitigation: "Confirm fiscal calendar with Procurement in week 1." },
          { description: "Security questionnaire stretches over 30 days.", mitigation: "Start in parallel with the POV, not after." },
          { description: "Existing incumbent contract has auto-renewal lock-in.", mitigation: "Identify cancellation window in week 1; brief AE." },
          { description: "Holiday seasonality eats the executive-review window.", mitigation: "Anchor exec review off-cycle from public holidays." },
        ],
        cadence: {
          weekly_sync: "Weekly 30-min sync, Champion + SA + AE (Tuesdays).",
          map_review: "Bi-weekly MAP review with all named stakeholders.",
          escalation_path: "Champion -> SA -> Sales Director on Elastic side; Champion -> Economic Buyer on customer side.",
        },
      },
    };
  }

  async function main() {
    const root = document.getElementById("map-root");
    const meetingId = qs("meeting_id");
    if (!meetingId) {
      // No meeting picked: load a universal Elastic template so the FE can
      // see the canonical 90-day plan, edit it, and save against a real
      // meeting later. The "Save / generate" CTAs in the right panel handle
      // the transition from template to persisted MAP.
      root.innerHTML = "";
      setStatus("Universal template");
      const banner = el("div", {
        class: "map-empty",
        style: "background: linear-gradient(180deg, rgba(124,58,237,0.12) 0%, rgba(11,100,221,0.06) 100%); border:1px solid rgba(124,58,237,0.35); padding:14px 18px; border-radius:10px; margin-bottom:18px;",
      }, [
        el("div", { style: "font-size:13px; font-weight:700; color:#7C3AED; letter-spacing:0.04em; text-transform:uppercase; margin-bottom:4px;" }, "Universal template"),
        el("div", { style: "font-size:14px; color:var(--ink); line-height:1.45;" },
          "You are looking at the canonical Elastic 90-day Mutual Action Plan template. Edit any milestone inline, then open /map.html?meeting_id=<id> to attach this plan to a real meeting and persist it. To generate an account-specific MAP from a brief, open the meeting page and click Generate MAP."),
      ]);
      const tpl = buildUniversalTemplate();
      const layout = el("div", { class: "map-layout" });
      layout.appendChild(renderLeft(tpl));
      layout.appendChild(renderRight(tpl, ctxRef));
      root.appendChild(banner);
      root.appendChild(layout);
      return;
    }
    setStatus("Loading...");
    function setRecord(rec) {
      root.innerHTML = "";
      if (!rec || rec.exists === false) {
        root.appendChild(renderEmpty(meetingId));
        setStatus("Not generated");
        return;
      }
      const layout = el("div", { class: "map-layout" });
      layout.appendChild(renderLeft(rec));
      layout.appendChild(renderRight(rec, ctxRef));
      root.appendChild(layout);
      setStatus("Ready");
    }
    ctxRef.setRecord = setRecord;
    try {
      const rec = await apiGet(`/map/${encodeURIComponent(meetingId)}`);
      setRecord(rec);
    } catch (err) {
      toast("Load failed: " + sanitizeError(err), "warn");
      setStatus("Error");
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", main);
  } else {
    main();
  }
})();
