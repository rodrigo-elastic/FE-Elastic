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

  async function main() {
    const root = document.getElementById("map-root");
    const meetingId = qs("meeting_id");
    if (!meetingId) {
      root.innerHTML = "";
      root.appendChild(el("div", { class: "map-empty" }, "Missing ?meeting_id= in URL."));
      setStatus("No meeting");
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
