/*
  filename: role-selector.js
  description: Persistent SA / CA / AE / All role selector. Lives in the
  topbar on every page that loads this script. Filters portal cards
  (data-role="sa,ca,ae") and tools-rail items by role: matching items
  stay full opacity, non-matching items dim to 0.35 (they remain
  clickable - the FE can always cross roles). The selected role is
  persisted in localStorage under `fec.role` so it survives page hops.
  Author: Rodrigo Careaga
  Date: 05-14-2026
*/
(function () {
  "use strict";

  const STORAGE_KEY = "fec.role";
  const ROLES = ["all", "sa", "ca", "ae"];
  const LABEL = { all: "All roles", sa: "SA - Pre-sales", ca: "CA - Post-sales", ae: "AE - Account Exec" };

  function loadRole() {
    try {
      const v = (localStorage.getItem(STORAGE_KEY) || "all").toLowerCase();
      return ROLES.includes(v) ? v : "all";
    } catch (_) {
      return "all";
    }
  }
  function saveRole(r) {
    try { localStorage.setItem(STORAGE_KEY, r); } catch (_) {}
  }

  // ============================================================ Filter pass
  function applyRole(role) {
    const active = (role || "all").toLowerCase();
    // Every node carrying `data-role` is a candidate. Value is a comma-separated
    // list of roles ("sa", "ca", "ae"). Nodes without `data-role` are not
    // touched - they show under every role.
    document.querySelectorAll("[data-role]").forEach((node) => {
      const tags = (node.getAttribute("data-role") || "")
        .toLowerCase()
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      const match = active === "all" || tags.includes(active) || tags.includes("all");
      node.classList.toggle("fec-role-dim", !match);
      // Move matching cards to the front of their parent grid so the FE
      // sees the role-relevant entry points first.
      if (match && active !== "all" && node.parentNode) {
        try { node.parentNode.prepend(node); } catch (_) {}
      }
    });
  }

  // ============================================================ Inject selector
  function injectStyles() {
    if (document.getElementById("fec-role-styles")) return;
    const s = document.createElement("style");
    s.id = "fec-role-styles";
    s.textContent = [
      ".fec-role-pill { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 999px; background: rgba(0,191,179,0.16); color: #006d66; border: 1px solid rgba(0,191,179,0.45); font-size: 11.5px; font-weight: 700; letter-spacing: 0.02em; cursor: pointer; position: relative; }",
      "[data-theme='dark'] .fec-role-pill { background: rgba(0,191,179,0.22); color: #aef6ee; }",
      ".fec-role-pill:hover { filter: brightness(1.05); }",
      ".fec-role-pill svg { opacity: 0.7; }",
      ".fec-role-menu { position: absolute; top: calc(100% + 6px); right: 0; min-width: 200px; background: var(--panel, #fff); border: 1px solid var(--border, #cbd5e1); border-radius: 8px; box-shadow: 0 6px 22px rgba(0,0,0,0.18); padding: 4px; z-index: 1000; }",
      ".fec-role-menu[hidden] { display: none; }",
      ".fec-role-opt { display: flex; align-items: center; gap: 8px; width: 100%; padding: 7px 10px; border: 0; background: transparent; color: var(--ink, #0f172a); font-size: 12.5px; cursor: pointer; border-radius: 6px; text-align: left; }",
      ".fec-role-opt:hover { background: var(--panel-2, rgba(0,0,0,0.05)); }",
      ".fec-role-opt.is-active { background: rgba(0,191,179,0.15); color: #006d66; font-weight: 700; }",
      "[data-theme='dark'] .fec-role-opt { color: #d4d9e0; }",
      "[data-theme='dark'] .fec-role-opt:hover { background: rgba(255,255,255,0.06); }",
      "[data-theme='dark'] .fec-role-opt.is-active { background: rgba(0,191,179,0.22); color: #aef6ee; }",
      ".fec-role-dim { opacity: 0.35; filter: grayscale(0.4); transition: opacity 180ms ease, filter 180ms ease; }",
      ".fec-role-dim:hover { opacity: 0.75; filter: grayscale(0); }",
    ].join("\n");
    document.head.appendChild(s);
  }

  function buildPill(role) {
    const pill = document.createElement("button");
    pill.type = "button";
    pill.className = "fec-role-pill";
    pill.setAttribute("aria-haspopup", "menu");
    pill.setAttribute("aria-expanded", "false");
    pill.id = "fec-role-pill";
    pill.title = "Filter the UI by your role. The selection persists across pages.";
    pill.innerHTML = `
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <circle cx="12" cy="8" r="4"/>
        <path d="M4 21v-2a4 4 0 0 1 4-4h8a4 4 0 0 1 4 4v2"/>
      </svg>
      <span id="fec-role-label">${LABEL[role] || LABEL.all}</span>
      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="6 9 12 15 18 9"/></svg>
    `;
    const menu = document.createElement("div");
    menu.className = "fec-role-menu";
    menu.id = "fec-role-menu";
    menu.setAttribute("role", "menu");
    menu.hidden = true;
    ROLES.forEach((r) => {
      const opt = document.createElement("button");
      opt.type = "button";
      opt.className = "fec-role-opt" + (r === role ? " is-active" : "");
      opt.setAttribute("data-role-value", r);
      opt.setAttribute("role", "menuitem");
      opt.textContent = LABEL[r];
      opt.addEventListener("click", (ev) => {
        ev.stopPropagation();
        setRole(r);
        menu.hidden = true;
        pill.setAttribute("aria-expanded", "false");
      });
      menu.appendChild(opt);
    });
    pill.appendChild(menu);
    pill.addEventListener("click", (ev) => {
      ev.stopPropagation();
      const open = !menu.hidden;
      menu.hidden = open;
      pill.setAttribute("aria-expanded", String(!open));
    });
    document.addEventListener("click", () => { menu.hidden = true; pill.setAttribute("aria-expanded", "false"); });
    return pill;
  }

  function setRole(role) {
    saveRole(role);
    const lbl = document.getElementById("fec-role-label");
    if (lbl) lbl.textContent = LABEL[role] || LABEL.all;
    document.querySelectorAll(".fec-role-opt").forEach((o) => {
      o.classList.toggle("is-active", o.getAttribute("data-role-value") === role);
    });
    applyRole(role);
    try {
      document.dispatchEvent(new CustomEvent("fec.role.changed", { detail: { role } }));
    } catch (_) {}
  }

  function mount() {
    injectStyles();
    const role = loadRole();
    // Find the topbar "right" section on any page that uses the standard
    // header. Prefer .topbar .right; fall back to .topbar; if neither
    // exists, do nothing - the dim CSS still applies for pages where
    // someone manually drops a [data-role] tag.
    const host = document.querySelector(".topbar .right") || document.querySelector(".topbar");
    if (host) {
      const pill = buildPill(role);
      host.insertBefore(pill, host.firstChild);
    }
    applyRole(role);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }

  window.FECRole = { get: loadRole, set: setRole, ROLES, LABEL };
})();
