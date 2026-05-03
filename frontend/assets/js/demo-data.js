/*
  filename: demo-data.js
  description: Demo Data Generator page. Lists the 3 scenarios from /api/v1/demo-data/scenarios and seeds them on click.
  Author: Rodrigo Careaga
  Date: 03-05-2026
*/
(function () {
  const $ = (s) => document.querySelector(s);

  const SCENARIO_ICONS = {
    "black-friday-outage": "🛒",
    "credential-stuffing": "🔐",
    "noisy-microservice": "🚨",
  };

  function el(tag, attrs = {}, children = []) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === "class") node.className = v;
      else if (k === "html") node.innerHTML = v;
      else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
      else node.setAttribute(k, v);
    }
    (Array.isArray(children) ? children : [children]).forEach((c) => {
      if (c == null) return;
      node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    });
    return node;
  }

  async function loadScenarios() {
    const grid = $("#dd-grid");
    grid.innerHTML = "";
    try {
      const data = await apiGet("/demo-data/scenarios");
      (data.scenarios || []).forEach((s) => grid.appendChild(card(s)));
    } catch (e) {
      grid.innerHTML = `<p class="muted">Failed to load scenarios: ${e.message}</p>`;
    }
  }

  function card(scenario) {
    const root = el("div", { class: "dd-card", "data-scenario": scenario.id });
    root.appendChild(
      el("div", { class: "dd-card-head" }, [
        el("span", { class: "dd-icon" }, SCENARIO_ICONS[scenario.id] || "🧪"),
        el("h3", { class: "dd-title" }, scenario.title),
      ])
    );
    root.appendChild(el("p", { class: "dd-desc" }, scenario.description));
    const indicesList = (scenario.indices || []).join(" · ");
    root.appendChild(el("div", { class: "dd-indices muted small" }, indicesList ? `Indices: ${indicesList}` : ""));

    const status = el("div", { class: "dd-status" });
    const seedBtn = el("button", { class: "btn primary", type: "button" }, "Seed scenario");
    const openBtn = el("a", { class: "btn ghost", target: "_blank", rel: "noreferrer", href: "#" }, "Open dashboard");
    openBtn.style.display = "none";

    seedBtn.addEventListener("click", async () => {
      const labelHTML = seedBtn.innerHTML;
      seedBtn.disabled = true;
      seedBtn.innerHTML = '<span class="spinner"></span> Seeding...';
      status.textContent = "Indexing docs and creating Kibana dashboard...";
      status.className = "dd-status running";
      try {
        const r = await apiPost(`/demo-data/${scenario.id}/seed`, {});
        const counts = r.indices || {};
        const total = Object.values(counts).reduce((a, b) => a + (b || 0), 0);
        status.className = "dd-status ok";
        status.textContent = `Indexed ${total} docs across ${Object.keys(counts).length} indices.`;
        if (r.dashboard_url) {
          openBtn.href = r.dashboard_url;
          openBtn.style.display = "";
        }
        toast(`Seeded ${scenario.title}`, "ok");
      } catch (e) {
        status.className = "dd-status err";
        status.textContent = e.message || String(e);
        toast(`Seed failed: ${e.message}`, "bad");
      } finally {
        seedBtn.disabled = false;
        seedBtn.innerHTML = labelHTML;
      }
    });

    root.appendChild(el("div", { class: "dd-actions" }, [seedBtn, openBtn]));
    root.appendChild(status);
    return root;
  }

  function init() {
    loadScenarios();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
