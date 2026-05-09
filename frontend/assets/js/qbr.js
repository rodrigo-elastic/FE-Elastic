/*
  filename: qbr.js
  description: QBR generator UI. Loads accounts from /api/v1/qbr/accounts, exposes
  quarter picker, calls POST /api/v1/qbr/generate, renders the 3-section preview
  (Look Back / Current State / Look Forward), and surfaces the PPTX download link.
  Author: Rodrigo Careaga
  Date: 09-05-2026
*/
(function () {
  "use strict";

  const $ = (sel, root) => (root || document).querySelector(sel);

  function el(tag, attrs, children) {
    const n = document.createElement(tag);
    if (attrs) {
      for (const [k, v] of Object.entries(attrs)) {
        if (k === "class") n.className = v;
        else if (k === "style") n.setAttribute("style", v);
        else if (k === "html") n.innerHTML = v;
        else if (k === "text") n.textContent = v;
        else n.setAttribute(k, v);
      }
    }
    (Array.isArray(children) ? children : [children])
      .filter(Boolean)
      .forEach((c) => n.appendChild(typeof c === "string" ? document.createTextNode(c) : c));
    return n;
  }

  function toast(msg, kind) {
    if (typeof window.toast === "function") {
      window.toast(msg, kind);
      return;
    }
    console.log("[qbr]", kind || "info", msg);
  }

  function currentQuarter() {
    const now = new Date();
    const q = Math.floor(now.getMonth() / 3) + 1;
    return `Q${q} ${now.getFullYear()}`;
  }

  function quarterOptions() {
    const opts = [];
    const now = new Date();
    const year = now.getFullYear();
    for (const y of [year - 1, year]) {
      for (let q = 1; q <= 4; q++) opts.push(`Q${q} ${y}`);
    }
    return opts;
  }

  // ============================================================ Loading

  async function loadAccounts() {
    const sel = $("#qbr-account");
    if (!sel) return;
    try {
      const res = await fetch("/api/v1/qbr/accounts");
      const data = await res.json();
      const accounts = data.accounts || [];
      sel.innerHTML = "";
      if (!accounts.length) {
        sel.appendChild(el("option", { value: "" }, "(no accounts)"));
        return;
      }
      accounts.forEach((name) => sel.appendChild(el("option", { value: name }, name)));
    } catch (e) {
      console.warn("qbr: failed to load accounts", e);
      sel.innerHTML = "";
      sel.appendChild(el("option", { value: "" }, "(load failed)"));
    }
  }

  function populateQuarters() {
    const sel = $("#qbr-quarter");
    if (!sel) return;
    sel.innerHTML = "";
    const cur = currentQuarter();
    quarterOptions().forEach((q) => {
      const o = el("option", { value: q }, q);
      if (q === cur) o.setAttribute("selected", "selected");
      sel.appendChild(o);
    });
  }

  // ============================================================ Rendering

  function metricBox(label, value) {
    return el("div", { class: "qbr-metric" }, [
      el("div", { class: "qbr-metric-label" }, label || ""),
      el("div", { class: "qbr-metric-value" }, value || "-"),
    ]);
  }

  function bulletList(items) {
    return el(
      "ul",
      { class: "qbr-list" },
      (items || []).map((t) => el("li", {}, String(t)))
    );
  }

  function healthScoreBadge(score) {
    const n = Number(score) || 0;
    let color = "#3CB44B";
    if (n < 60) color = "#E84B37";
    else if (n < 80) color = "#F1A730";
    return el(
      "div",
      {
        class: "qbr-health",
        style: `display:flex;align-items:center;gap:14px;padding:14px 16px;border-radius:12px;background:#0f172a;border:1px solid var(--border, #1e293b);`,
      },
      [
        el(
          "div",
          {
            style: `font-size:36px;font-weight:700;color:${color};line-height:1;`,
          },
          String(n)
        ),
        el(
          "div",
          {},
          [
            el("div", { style: "font-size:11px;color:var(--muted,#64748b);text-transform:uppercase;letter-spacing:0.05em;" }, "Health Score"),
            el("div", { style: "font-size:13px;color:var(--ink,#e2e8f0);margin-top:2px;" }, "of 100"),
          ]
        ),
      ]
    );
  }

  function sectionCard(title, color, body) {
    const head = el(
      "div",
      {
        class: "qbr-section-head",
        style: `background:${color};color:white;padding:12px 18px;border-radius:8px 8px 0 0;font-weight:700;letter-spacing:0.02em;`,
      },
      title
    );
    return el(
      "div",
      {
        class: "qbr-section",
        style: "border:1px solid var(--border,#1e293b);border-radius:8px;background:var(--panel,#0b1220);overflow:hidden;",
      },
      [head, el("div", { class: "qbr-section-body", style: "padding:16px 18px;" }, body)]
    );
  }

  function renderQBR(content) {
    const host = $("#qbr-preview");
    if (!host) return;
    host.innerHTML = "";

    const meta = el(
      "div",
      { class: "qbr-meta", style: "display:flex;gap:14px;align-items:center;margin-bottom:18px;flex-wrap:wrap;" },
      [
        el("h2", { style: "margin:0;font-size:22px;" }, content.company_name || "(account)"),
        el(
          "span",
          {
            class: "qbr-quarter-badge",
            style: "padding:4px 10px;border-radius:999px;background:#0B64DD;color:white;font-size:12px;font-weight:600;",
          },
          content.quarter || ""
        ),
        content.use_case
          ? el("span", { class: "muted", style: "color:var(--muted,#64748b);font-size:13px;" }, content.use_case)
          : null,
        content.arr
          ? el("span", { class: "muted", style: "color:var(--muted,#64748b);font-size:13px;" }, `ARR: ${content.arr}`)
          : null,
      ]
    );
    host.appendChild(meta);

    // Look Back
    const kpis = (content.kpis || []).map((m) => metricBox(m.label, m.value));
    const lookBack = el("div", {}, [
      kpis.length
        ? el("div", { style: "display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-bottom:14px;" }, kpis)
        : null,
      el("h4", { style: "margin:8px 0 6px;color:#E84B37;font-size:13px;" }, "Technical Wins"),
      bulletList(content.technical_wins),
      el("h4", { style: "margin:14px 0 6px;color:#0F2D5C;font-size:13px;" }, "Business Outcomes"),
      bulletList(content.business_outcomes),
    ]);

    // Current State
    const currentState = el(
      "div",
      { style: "display:grid;grid-template-columns:200px 1fr;gap:18px;align-items:start;" },
      [
        el("div", {}, [
          healthScoreBadge(content.health_score),
          content.health_summary
            ? el("p", { class: "muted", style: "margin:10px 0 0;font-size:12px;color:var(--muted,#64748b);" }, content.health_summary)
            : null,
        ]),
        el("div", {}, [
          el("h4", { style: "margin:0 0 6px;color:#F1A730;font-size:13px;" }, "Feature Gaps"),
          bulletList(content.feature_gaps),
          el("h4", { style: "margin:14px 0 6px;color:#E84B37;font-size:13px;" }, "Optimization Recommendations"),
          bulletList(content.optimization_recs),
        ]),
      ]
    );

    // Look Forward
    const lookForward = el(
      "div",
      { style: "display:grid;grid-template-columns:repeat(3,1fr);gap:14px;" },
      [
        el("div", {}, [
          el("h4", { style: "margin:0 0 6px;color:#F1A730;font-size:13px;" }, "Expansion Opportunities"),
          bulletList(content.expansion_opportunities),
        ]),
        el("div", {}, [
          el("h4", { style: "margin:0 0 6px;color:#0F2D5C;font-size:13px;" }, "New Use Cases"),
          bulletList(content.new_use_cases),
        ]),
        el("div", {}, [
          el("h4", { style: "margin:0 0 6px;color:#00B4A2;font-size:13px;" }, "Roadmap Alignment"),
          bulletList(content.roadmap_items),
        ]),
      ]
    );

    host.appendChild(sectionCard("Look Back: Value Delivered", "#E84B37", lookBack));
    host.appendChild(el("div", { style: "height:14px;" }));
    host.appendChild(sectionCard("Current State: Deployment Health", "#0F2D5C", currentState));
    host.appendChild(el("div", { style: "height:14px;" }));
    host.appendChild(sectionCard("Look Forward: Strategic Roadmap", "#00B4A2", lookForward));

    if (content.next_steps && content.next_steps.length) {
      host.appendChild(el("div", { style: "height:14px;" }));
      host.appendChild(
        sectionCard(
          "Next Steps",
          "#0B64DD",
          bulletList(content.next_steps)
        )
      );
    }
  }

  // ============================================================ Generate

  async function onGenerate() {
    const accountSel = $("#qbr-account");
    const quarterSel = $("#qbr-quarter");
    const demoCb = $("#qbr-demo");
    const btn = $("#qbr-generate");
    const dlBtn = $("#qbr-download");
    if (!accountSel || !quarterSel || !btn) return;

    const company_name = accountSel.value;
    if (!company_name) {
      toast("Pick an account first", "bad");
      return;
    }

    const labelHTML = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Generating QBR...';

    try {
      const body = {
        company_id: company_name,
        quarter: quarterSel.value || "",
        demo: !!(demoCb && demoCb.checked),
      };
      const res = await fetch("/api/v1/qbr/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const txt = await res.text();
        throw new Error(`${res.status}: ${txt.slice(0, 200)}`);
      }
      const data = await res.json();
      renderQBR(data.content || {});
      toast("QBR generated", "ok");

      if (dlBtn) {
        const href = data.pptx_rel || data.pptx_url;
        if (href) {
          dlBtn.hidden = false;
          dlBtn.href = href;
          dlBtn.setAttribute("download", data.slide_name || "qbr.pptx");
        }
      }
    } catch (e) {
      console.warn("qbr: generate failed", e);
      toast(`QBR failed: ${(e && e.message) || "error"}`, "bad");
    } finally {
      btn.disabled = false;
      btn.innerHTML = labelHTML;
    }
  }

  // ============================================================ Init

  function init() {
    populateQuarters();
    loadAccounts();
    const btn = $("#qbr-generate");
    if (btn) btn.addEventListener("click", onGenerate);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
