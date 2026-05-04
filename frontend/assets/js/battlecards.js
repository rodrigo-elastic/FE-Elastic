/*
  filename: battlecards.js
  description: Renders the /battlecards.html page. Pulls the full battlecard set from /api/v1/battlecards (live from the fec-battlecards Elastic index, or the seed JSON when ES is unreachable), renders a responsive grid with a glyph + tagline + the customer-quote bullets and Elastic counter-positioning, and opens an accessible click-to-expand modal that shows talking-points, proof, objections, and discovery questions. Search input filters cards client-side by competitor name and tagline. Modal closes on Escape, scrim click, or close button. Empty state if the API returns zero cards.
  Author: Rodrigo Careaga
  Date: 03-05-2026
*/
(function () {
  const $ = (s, r) => (r || document).querySelector(s);

  const STATE = {
    cards: [],
    filtered: [],
    source: "seed",
    activeSlug: null,
    lastFocus: null,
  };

  // ---------------------------------------------------------------- helpers

  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    if (attrs) {
      for (const k of Object.keys(attrs)) {
        const v = attrs[k];
        if (v == null || v === false) continue;
        if (k === "class") node.className = v;
        else if (k === "html") node.innerHTML = v;
        else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
        else if (v === true) node.setAttribute(k, "");
        else node.setAttribute(k, v);
      }
    }
    if (children == null) return node;
    const arr = Array.isArray(children) ? children : [children];
    for (const c of arr) {
      if (c == null || c === false) continue;
      node.appendChild(typeof c === "string" || typeof c === "number"
        ? document.createTextNode(String(c))
        : c);
    }
    return node;
  }

  function clear(node) { while (node && node.firstChild) node.removeChild(node.firstChild); }

  function glyphFor(name) {
    if (!name) return "??";
    const trimmed = String(name).trim();
    if (!trimmed) return "??";
    const parts = trimmed.split(/\s+/).filter(Boolean);
    if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
    return trimmed.slice(0, 2).toUpperCase();
  }

  // Pull verbatim "When customers say..." quotes from the objections block.
  // If a card has no objections, fall back to the key_pain string.
  function customerQuotes(card, max) {
    const out = [];
    const objs = Array.isArray(card.common_objections) ? card.common_objections : [];
    for (const o of objs) {
      if (o && o.q && out.length < max) out.push(String(o.q));
    }
    if (!out.length && card.key_pain) out.push(String(card.key_pain));
    return out;
  }

  // Best-effort proof-point extractor: pulls from talking_points[].proof,
  // returns an array of {label, detail, href?} ready to render. Numeric and
  // customer-name fragments are surfaced as labels when we can find them.
  function proofPoints(card, max) {
    const out = [];
    const tps = Array.isArray(card.talking_points) ? card.talking_points : [];
    for (const tp of tps) {
      if (!tp || !tp.proof) continue;
      if (out.length >= max) break;
      out.push({ label: tp.angle || "Proof", detail: tp.proof });
    }
    return out;
  }

  // ----------------------------------------------------------------- header

  function setMeta(count, source) {
    const pillCount = $("#bc-pill-count");
    const pillSource = $("#bc-pill-source");
    if (pillCount) {
      pillCount.textContent = count === 1 ? "1 card loaded" : `${count} cards loaded`;
      pillCount.classList.remove("ab-pill-muted");
      pillCount.classList.add(count > 0 ? "ab-pill-ok" : "ab-pill-err");
    }
    if (pillSource) {
      pillSource.textContent = source === "es"
        ? "live from fec-battlecards"
        : "seed file (ES unavailable)";
      pillSource.classList.remove("ab-pill-muted");
      pillSource.classList.add(source === "es" ? "ab-pill-ok" : "ab-pill-muted");
    }
  }

  // -------------------------------------------------------------- list view

  function renderCard(card) {
    const root = el("button", {
      type: "button",
      class: "bc-card",
      "data-slug": card.competitor_slug || (card.competitor || "").toLowerCase(),
      "aria-label": `Open ${card.competitor || "competitor"} battlecard`,
    });

    root.appendChild(
      el("div", { class: "bc-card-head" }, [
        el("span", { class: "bc-card-glyph", "aria-hidden": "true" }, glyphFor(card.competitor)),
        el("div", {}, [
          el("h3", { class: "bc-card-title" }, "vs " + (card.competitor || "Unknown")),
          el("p", { class: "bc-card-tagline" }, card.tagline || ""),
        ]),
      ])
    );

    const quotes = customerQuotes(card, 3);
    if (quotes.length) {
      root.appendChild(
        el("div", { class: "bc-section" }, [
          el("div", { class: "bc-section-lbl" }, "When customers say"),
          el("div", { class: "bc-card-quotes" }, quotes.map((q) =>
            el("div", { class: "bc-quote" }, '"' + q + '"')
          )),
        ])
      );
    }

    const adv = Array.isArray(card.elastic_advantages) ? card.elastic_advantages.slice(0, 4) : [];
    if (adv.length) {
      root.appendChild(
        el("div", { class: "bc-section" }, [
          el("div", { class: "bc-section-lbl" }, "Elastic counter-positioning"),
          el("ul", { class: "bc-counter" }, adv.map((a) => el("li", {}, a))),
        ])
      );
    }

    root.appendChild(
      el("div", { class: "bc-card-foot" }, [
        el("span", {}, `${(card.talking_points || []).length} talking points - ${(card.common_objections || []).length} objections`),
        el("span", { class: "bc-card-foot-cta" }, "Open"),
      ])
    );

    root.addEventListener("click", () => openModal(card));
    return root;
  }

  function renderList(cards) {
    const grid = $("#bc-grid");
    if (!grid) return;
    clear(grid);
    if (!cards.length) {
      grid.appendChild(
        el("div", { class: "bc-empty" }, [
          el("strong", {}, STATE.cards.length ? "No competitors match that search." : "No battlecards loaded yet."),
          el("span", {}, STATE.cards.length
            ? "Try a different name or clear the search."
            : "The fec-battlecards index is empty and no seed file was found. Re-run the data seeder."),
        ])
      );
      return;
    }
    cards.forEach((c) => grid.appendChild(renderCard(c)));
  }

  function applyFilter(query) {
    const q = (query || "").toLowerCase().trim();
    if (!q) {
      STATE.filtered = STATE.cards.slice();
    } else {
      STATE.filtered = STATE.cards.filter((c) => {
        const hay = [
          c.competitor || "",
          c.competitor_slug || "",
          c.tagline || "",
        ].join(" ").toLowerCase();
        return hay.includes(q);
      });
    }
    const counter = $("#bc-result-count");
    if (counter) {
      if (!q) counter.textContent = "";
      else counter.textContent = `${STATE.filtered.length} of ${STATE.cards.length} match`;
    }
    renderList(STATE.filtered);
  }

  // --------------------------------------------------------------- modal

  function buildModalBody(card) {
    const wrap = document.createDocumentFragment();

    if (card.key_pain) {
      wrap.appendChild(
        el("div", { class: "bc-pain" }, [
          el("span", { class: "bc-pain-lbl" }, "Customer pain"),
          document.createTextNode(card.key_pain),
        ])
      );
    }

    const tps = Array.isArray(card.talking_points) ? card.talking_points : [];
    if (tps.length) {
      const sec = el("div", { class: "bc-section" }, [
        el("div", { class: "bc-section-lbl" }, "Talking points"),
      ]);
      tps.forEach((p, i) => {
        const det = el("details", { class: "bc-tp" });
        if (i === 0) det.setAttribute("open", "");
        det.appendChild(
          el("summary", {}, [
            el("span", { class: "bc-tp-angle" }, p.angle || ""),
            el("span", { class: "bc-tp-claim" }, p.claim || ""),
            el("span", { class: "chevron bc-tp-chev" }, ""),
          ])
        );
        if (p.proof) det.appendChild(el("div", { class: "bc-tp-proof" }, p.proof));
        sec.appendChild(det);
      });
      wrap.appendChild(sec);
    }

    const adv = Array.isArray(card.elastic_advantages) ? card.elastic_advantages : [];
    if (adv.length) {
      wrap.appendChild(
        el("div", { class: "bc-section" }, [
          el("div", { class: "bc-section-lbl" }, "Elastic counter-positioning"),
          el("ul", { class: "bc-counter" }, adv.map((a) => el("li", {}, a))),
        ])
      );
    }

    const proofs = proofPoints(card, 5);
    if (proofs.length) {
      wrap.appendChild(
        el("div", { class: "bc-section" }, [
          el("div", { class: "bc-section-lbl" }, "Proof points"),
          el("div", {}, proofs.map((p) =>
            el("div", { class: "bc-tp-proof" }, [
              el("strong", {}, p.label + ": "),
              document.createTextNode(p.detail),
            ])
          )),
        ])
      );
    }

    const objs = Array.isArray(card.common_objections) ? card.common_objections : [];
    if (objs.length) {
      const sec = el("details", { class: "bc-section", open: "" });
      sec.appendChild(el("summary", { class: "bc-section-lbl", style: "cursor:pointer; list-style:none;" }, "Watch out for"));
      objs.forEach((o) => {
        sec.appendChild(
          el("div", { class: "bc-obj" }, [
            el("div", { class: "bc-obj-q" }, '"' + (o.q || "") + '"'),
            el("div", { class: "bc-obj-a" }, o.a || ""),
          ])
        );
      });
      wrap.appendChild(sec);
    }

    const dq = Array.isArray(card.discovery_questions) ? card.discovery_questions : [];
    if (dq.length) {
      wrap.appendChild(
        el("div", { class: "bc-section" }, [
          el("div", { class: "bc-section-lbl" }, "Discovery to confirm"),
          el("ul", { class: "bc-dq" }, dq.map((q) => el("li", {}, q))),
        ])
      );
    }

    return wrap;
  }

  function openModal(card) {
    const modal = $("#bc-modal");
    if (!modal) return;
    STATE.activeSlug = card.competitor_slug || (card.competitor || "").toLowerCase();
    STATE.lastFocus = document.activeElement;

    const title = $("#bc-modal-title");
    const tagline = $("#bc-modal-tagline");
    const glyph = $("#bc-modal-glyph");
    const body = $("#bc-modal-body");
    if (title) title.textContent = "vs " + (card.competitor || "Competitor");
    if (tagline) tagline.textContent = card.tagline || "";
    if (glyph) glyph.textContent = glyphFor(card.competitor);
    if (body) {
      clear(body);
      body.appendChild(buildModalBody(card));
      body.scrollTop = 0;
    }

    modal.hidden = false;
    document.body.classList.add("bc-modal-open");

    // Focus the close button so Escape / Tab work as expected.
    const close = modal.querySelector(".bc-modal-close");
    if (close) close.focus();
  }

  function closeModal() {
    const modal = $("#bc-modal");
    if (!modal || modal.hidden) return;
    modal.hidden = true;
    document.body.classList.remove("bc-modal-open");
    STATE.activeSlug = null;
    if (STATE.lastFocus && typeof STATE.lastFocus.focus === "function") {
      try { STATE.lastFocus.focus(); } catch (_) { /* ignore */ }
    }
    STATE.lastFocus = null;
  }

  function bindModal() {
    const modal = $("#bc-modal");
    if (!modal) return;
    modal.addEventListener("click", (ev) => {
      const t = ev.target;
      if (!t) return;
      if (t.closest && t.closest("[data-bc-close]")) {
        ev.preventDefault();
        closeModal();
      }
    });
    document.addEventListener("keydown", (ev) => {
      if (ev.key === "Escape" && !modal.hidden) {
        ev.preventDefault();
        closeModal();
      }
    });
  }

  function bindSearch() {
    const input = $("#bc-search");
    if (!input) return;
    input.addEventListener("input", (ev) => applyFilter(ev.target.value || ""));
    input.addEventListener("keydown", (ev) => {
      if (ev.key === "Escape" && input.value) {
        input.value = "";
        applyFilter("");
      }
    });
  }

  // ----------------------------------------------------------------- load

  async function load() {
    const grid = $("#bc-grid");
    try {
      const data = await apiGet("/battlecards");
      STATE.cards = Array.isArray(data && data.items) ? data.items : [];
      STATE.source = (data && data.source) || "seed";
      // Stable alphabetical sort so the grid does not shuffle on reload.
      STATE.cards.sort((a, b) =>
        String(a.competitor || "").localeCompare(String(b.competitor || ""))
      );
      setMeta(STATE.cards.length, STATE.source);
      applyFilter("");
    } catch (err) {
      console.error("battlecards.load", err);
      setMeta(0, "seed");
      if (grid) {
        clear(grid);
        grid.appendChild(
          el("div", { class: "bc-empty" }, [
            el("strong", {}, "Could not load battlecards."),
            el("span", {}, (err && err.message) || "Network error - check that the backend is running."),
          ])
        );
      }
      if (typeof toast === "function") toast("Failed to load battlecards", "bad");
    }
  }

  function init() {
    bindModal();
    bindSearch();
    load();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
