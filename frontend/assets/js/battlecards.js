/*
  filename: battlecards.js
  description: Renders the /battlecards.html page. Loads the full battlecard set from /api/v1/battlecards (live from the fec-battlecards Elastic index, or the seed JSON when ES is unreachable). Two view modes driven by location.hash: (1) grid view (no hash) shows a responsive list of cards with client-side search; (2) full-screen detail view (#<slug>) renders the card as a one-page sales kit with hero strip, talking points, objections, and discovery questions on the left, and an embedded Field Assistant mini chat on the right scoped to that competitor (storage key fec.bc.<slug>). Sticky header offers Back to grid, Copy Markdown, Print, and Open in Drive actions. Browser back/forward navigates between modes.
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
    miniMounted: null, // slug currently mounted into the chat panel
    chatHandle: null,  // active BattlecardChat instance (for dispose on swap)
    lastFocus: null,
    vertical: "all",          // active vertical chip; "all" or one of the 4 keys
    industry: "all",          // selected industry id; "all" or one of the 20 ids
    mainsOnly: false,         // toggle defaults off so all 31 cards are visible by default
    searchQuery: "",          // last applied search string
    persona: (function () {
      try { return localStorage.getItem("fec.bc.persona") || "sa"; } catch (_) { return "sa"; }
    }()),                     // "sa" = Solution Architect | "ca" = Customer Architect
  };

  // Canonical 20 industry IDs aligned with W15A.
  const INDUSTRY_IDS = [
    "fsi-banking", "fsi-insurance", "fsi-capital-markets",
    "gov-federal", "gov-state-local",
    "healthcare-providers", "healthcare-payers", "pharma-life-sciences",
    "retail-ecommerce", "retail-brick-mortar",
    "telco", "media-streaming", "tech-saas",
    "mfg-discrete", "mfg-process",
    "energy-utilities", "transportation-logistics",
    "travel-hospitality", "automotive", "aerospace-defense",
  ];

  const VERTICAL_LABELS = {
    direct_search_vector: "Search / Vector",
    observability_logs: "Observability / Logs",
    ai_search_ecommerce: "AI Search / E-commerce",
    security_siem_xdr: "Security / SIEM",
  };

  const VERTICAL_I18N = {
    direct_search_vector: "bc.vert.direct_search_vector.short",
    observability_logs: "bc.vert.observability_logs.short",
    ai_search_ecommerce: "bc.vert.ai_search_ecommerce.short",
    security_siem_xdr: "bc.vert.security_siem_xdr.short",
  };

  // ---------------------------------------------------------------- community votes

  const VOTES_KEY = "fec.bc.votes";
  function _loadVotes() {
    try { return JSON.parse(localStorage.getItem(VOTES_KEY) || "{}"); } catch (_) { return {}; }
  }
  function _saveVotes(v) {
    try { localStorage.setItem(VOTES_KEY, JSON.stringify(v)); } catch (_) {}
  }
  function getVote(id) {
    const v = _loadVotes();
    return { up: v[id + ":up"] || 0, down: v[id + ":down"] || 0, mine: v[id + ":mine"] || null };
  }
  function castVote(id, dir) {
    const v = _loadVotes();
    const mine = v[id + ":mine"] || null;
    if (mine === dir) {
      v[id + ":" + dir] = Math.max(0, (v[id + ":" + dir] || 0) - 1);
      delete v[id + ":mine"];
    } else {
      if (mine) v[id + ":" + mine] = Math.max(0, (v[id + ":" + mine] || 0) - 1);
      v[id + ":" + dir] = (v[id + ":" + dir] || 0) + 1;
      v[id + ":mine"] = dir;
    }
    _saveVotes(v);
    return getVote(id);
  }

  function makeVoteRow(voteId, compact) {
    const vote = getVote(voteId);
    const row = el("div", { class: "bc-vote-row" + (compact ? " bc-vote-compact" : "") });
    let upBtn, downBtn, scoreEl;

    function refresh(v) {
      const net = v.up - v.down;
      upBtn.className = "bc-vote-btn up" + (v.mine === "up" ? " voted" : "");
      upBtn.textContent = "👍 " + v.up;
      downBtn.className = "bc-vote-btn down" + (v.mine === "down" ? " voted" : "");
      downBtn.textContent = "👎 " + v.down;
      scoreEl.textContent = net > 0 ? "+" + net : String(net);
      scoreEl.className = "bc-vote-score" + (net > 0 ? " positive" : net < 0 ? " negative" : "");
    }

    upBtn = el("button", { type: "button", class: "bc-vote-btn up" + (vote.mine === "up" ? " voted" : ""), title: "Helpful", "aria-label": "Mark as helpful" }, "👍 " + vote.up);
    downBtn = el("button", { type: "button", class: "bc-vote-btn down" + (vote.mine === "down" ? " voted" : ""), title: "Needs work", "aria-label": "Mark as needs work" }, "👎 " + vote.down);
    const net = vote.up - vote.down;
    scoreEl = el("span", { class: "bc-vote-score" + (net > 0 ? " positive" : net < 0 ? " negative" : "") }, net > 0 ? "+" + net : String(net));
    const label = el("span", { class: "bc-vote-label" }, "Community rating");

    upBtn.addEventListener("click", (e) => { e.stopPropagation(); refresh(castVote(voteId, "up")); });
    downBtn.addEventListener("click", (e) => { e.stopPropagation(); refresh(castVote(voteId, "down")); });

    row.appendChild(upBtn);
    row.appendChild(downBtn);
    row.appendChild(scoreEl);
    if (!compact) row.appendChild(label);
    return row;
  }

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

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function glyphFor(name) {
    if (!name) return "??";
    const trimmed = String(name).trim();
    if (!trimmed) return "??";
    const parts = trimmed.split(/\s+/).filter(Boolean);
    if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
    return trimmed.slice(0, 2).toUpperCase();
  }

  function slugOf(card) {
    if (!card) return "";
    return String(card.competitor_slug || (card.competitor || "")).toLowerCase().trim();
  }

  function findCard(slug) {
    const want = String(slug || "").toLowerCase().trim();
    if (!want) return null;
    return STATE.cards.find((c) => slugOf(c) === want) || null;
  }

  // Pull verbatim "When customers say..." quotes from the objections block.
  function customerQuotes(card, max) {
    const out = [];
    const objs = Array.isArray(card.common_objections) ? card.common_objections : [];
    for (const o of objs) {
      if (o && o.q && out.length < max) out.push(String(o.q));
    }
    if (!out.length && card.key_pain) out.push(String(card.key_pain));
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

  // -------------------------------------------------------------- grid view

  function verticalLabel(key) {
    if (!key) return "";
    if (window.t && typeof t === "function") {
      const i18nKey = VERTICAL_I18N[key];
      if (i18nKey) {
        const v = t(i18nKey);
        if (v && v !== i18nKey) return v;
      }
    }
    return VERTICAL_LABELS[key] || key;
  }

  function renderCard(card) {
    const slug = slugOf(card);
    const vertical = card.vertical || "";
    const root = el("a", {
      href: "#" + encodeURIComponent(slug),
      class: "bc-card" + (vertical ? " bc-card-v-" + vertical.replace(/_/g, "-") : ""),
      "data-slug": slug,
      "data-vertical": vertical,
      "data-main": card.is_main_competitor ? "1" : "0",
      "aria-label": `Open ${card.competitor || "competitor"} battlecard`,
    });

    const badges = el("div", { class: "bc-card-badges", "aria-hidden": "true" });
    if (vertical) {
      badges.appendChild(
        el("span", { class: "bc-vbadge bc-vbadge-" + vertical.replace(/_/g, "-") }, verticalLabel(vertical))
      );
    }
    if (card.is_main_competitor) {
      badges.appendChild(el("span", { class: "bc-vbadge bc-vbadge-main" }, "main"));
    }
    root.appendChild(badges);

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
        el("span", {}, `${(card.talking_points || []).length} talking points, ${(card.common_objections || []).length} objections`),
        el("span", { class: "bc-card-foot-cta" }, "Open"),
      ])
    );

    // The href takes care of routing. Only intercept to keep focus / smooth UX.
    root.addEventListener("click", (ev) => {
      // Allow modifier-clicks (cmd/ctrl) to behave normally so users can open in
      // a new tab if they really want a clean URL with the hash.
      if (ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey) return;
      ev.preventDefault();
      STATE.lastFocus = root;
      location.hash = "#" + encodeURIComponent(slug);
    });
    return root;
  }

  function tr(key, fallback) {
    if (window.t && typeof t === "function") {
      const v = t(key);
      if (v && v !== key) return v;
    }
    return fallback;
  }

  function renderList(cards) {
    const grid = $("#bc-grid");
    if (!grid) return;
    clear(grid);
    if (!cards.length) {
      const filtersActive = STATE.cards.length && (
        STATE.searchQuery || STATE.vertical !== "all" || STATE.industry !== "all" || STATE.mainsOnly
      );
      const headline = STATE.cards.length
        ? (filtersActive
            ? tr("bc.filter.no_match", "No battlecards match these filters.")
            : "No competitors match that search.")
        : "No battlecards loaded yet.";
      const sub = STATE.cards.length
        ? (filtersActive
            ? "Try clearing a filter or picking a different industry."
            : "Try a different name or clear the search.")
        : "The fec-battlecards index is empty and no seed file was found. Re-run the data seeder.";
      grid.appendChild(
        el("div", { class: "bc-empty" }, [
          el("strong", {}, headline),
          el("span", {}, sub),
        ])
      );
      return;
    }
    cards.forEach((c) => grid.appendChild(renderCard(c)));
  }

  function applyFilter(query) {
    if (typeof query === "string") STATE.searchQuery = query;
    const q = (STATE.searchQuery || "").toLowerCase().trim();
    const vertical = STATE.vertical || "all";
    const industry = STATE.industry || "all";
    const mainsOnly = !!STATE.mainsOnly;

    STATE.filtered = STATE.cards.filter((c) => {
      if (vertical !== "all" && (c.vertical || "") !== vertical) return false;
      if (industry !== "all") {
        const inds = Array.isArray(c.industries) ? c.industries : [];
        if (!inds.includes(industry)) return false;
      }
      if (mainsOnly && !c.is_main_competitor) return false;
      if (!q) return true;
      const hay = [
        c.competitor || "",
        c.competitor_slug || "",
        c.tagline || "",
        c.vertical || "",
        (Array.isArray(c.industries) ? c.industries.join(" ") : ""),
      ].join(" ").toLowerCase();
      return hay.includes(q);
    });

    const counter = $("#bc-result-count");
    if (counter) {
      const total = STATE.cards.length;
      const shown = STATE.filtered.length;
      const parts = [];
      if (q || vertical !== "all" || industry !== "all" || mainsOnly) {
        parts.push(`${shown} of ${total}`);
      }
      counter.textContent = parts.join(" ");
    }
    refreshChipCounts();
    renderList(STATE.filtered);
  }

  // Recompute the count badge on each chip. Counts respect the mains-only toggle
  // and the active industry filter (so the user sees the same population that
  // clicking the chip will produce) but ignore the search box, so the chips do
  // not flicker as the user types.
  function refreshChipCounts() {
    const mainsOnly = !!STATE.mainsOnly;
    const industry = STATE.industry || "all";
    const totals = { all: 0, direct_search_vector: 0, observability_logs: 0, ai_search_ecommerce: 0, security_siem_xdr: 0 };
    for (const c of STATE.cards) {
      if (mainsOnly && !c.is_main_competitor) continue;
      if (industry !== "all") {
        const inds = Array.isArray(c.industries) ? c.industries : [];
        if (!inds.includes(industry)) continue;
      }
      totals.all += 1;
      if (c.vertical && totals.hasOwnProperty(c.vertical)) totals[c.vertical] += 1;
    }
    document.querySelectorAll(".bc-chip-count").forEach((node) => {
      const key = node.getAttribute("data-count-for");
      if (key && totals.hasOwnProperty(key)) node.textContent = String(totals[key]);
    });
    // Sync the count pill in the hero meta to reflect the visible card count.
    const pillCount = $("#bc-pill-count");
    if (pillCount && Array.isArray(STATE.filtered)) {
      const shown = STATE.filtered.length;
      const total = STATE.cards.length;
      let label;
      if (shown === total) {
        label = total === 1 ? "1 card loaded" : `${total} cards loaded`;
      } else {
        label = `${shown} of ${total} cards`;
      }
      pillCount.textContent = label;
      pillCount.classList.remove("ab-pill-muted");
      pillCount.classList.add(shown > 0 ? "ab-pill-ok" : "ab-pill-err");
    }
    // Toggle visibility of the inline "Clear" button next to the dropdown.
    const clearBtn = $("#bc-industry-clear");
    if (clearBtn) clearBtn.hidden = (STATE.industry || "all") === "all";
  }

  function setVertical(key) {
    const next = key || "all";
    STATE.vertical = next;
    document.querySelectorAll(".bc-chip").forEach((btn) => {
      const isActive = (btn.getAttribute("data-vertical") || "all") === next;
      btn.classList.toggle("is-active", isActive);
      btn.setAttribute("aria-pressed", isActive ? "true" : "false");
    });
    applyFilter();
  }

  function setMainsOnly(on) {
    STATE.mainsOnly = !!on;
    applyFilter();
  }

  function setIndustry(value) {
    const next = value && INDUSTRY_IDS.indexOf(value) >= 0 ? value : "all";
    STATE.industry = next;
    const select = $("#bc-industry-select");
    if (select && select.value !== next) select.value = next;
    applyFilter();
  }

  // ------------------------------------------------------------ markdown

  function buildMarkdown(card) {
    const lines = [];
    const name = card.competitor || "Competitor";
    lines.push(`# Battlecard: Elastic vs ${name}`);
    lines.push("");
    if (card.tagline) {
      lines.push(`> ${card.tagline}`);
      lines.push("");
    }
    if (card.key_pain) {
      lines.push("## Customer pain");
      lines.push(card.key_pain);
      lines.push("");
    }
    const tps = Array.isArray(card.talking_points) ? card.talking_points : [];
    if (tps.length) {
      lines.push("## Talking points");
      tps.forEach((p, i) => {
        lines.push(`### ${i + 1}. ${p.angle || "Angle"}`);
        if (p.claim) lines.push(p.claim);
        if (p.proof) {
          lines.push("");
          lines.push(`**Proof:** ${p.proof}`);
        }
        lines.push("");
      });
    }
    const adv = Array.isArray(card.elastic_advantages) ? card.elastic_advantages : [];
    if (adv.length) {
      lines.push("## Elastic counter-positioning");
      adv.forEach((a) => lines.push(`- ${a}`));
      lines.push("");
    }
    const proofs = Array.isArray(card.proof_points) ? card.proof_points : [];
    if (proofs.length) {
      lines.push("## Proof points");
      proofs.forEach((p) => {
        lines.push(`- ${p.metric || ""}${p.source ? ` (source: ${p.source})` : ""}`);
      });
      lines.push("");
    }
    if (card.pricing_anchor) {
      lines.push("## Pricing anchor");
      lines.push(card.pricing_anchor);
      lines.push("");
    }
    const objs = (Array.isArray(card.objection_handlers) && card.objection_handlers.length
      ? card.objection_handlers
      : Array.isArray(card.common_objections) ? card.common_objections : []);
    if (objs.length) {
      lines.push("## Common objections");
      objs.forEach((o) => {
        lines.push(`**Q:** ${o.q || ""}`);
        lines.push(`**A:** ${o.a || ""}`);
        lines.push("");
      });
    }
    const gotchas = Array.isArray(card.gotchas) ? card.gotchas : [];
    if (gotchas.length) {
      lines.push("## Honest gotchas");
      gotchas.forEach((g) => lines.push(`- ${g}`));
      lines.push("");
    }
    const dq = Array.isArray(card.discovery_questions) ? card.discovery_questions : [];
    if (dq.length) {
      lines.push("## Discovery to confirm");
      dq.forEach((q, i) => lines.push(`${i + 1}. ${q}`));
      lines.push("");
    }
    if (card.clincher) {
      lines.push("## Clincher");
      lines.push(card.clincher);
      lines.push("");
    }
    if (card.vertical) {
      lines.push(`*Vertical: ${card.vertical}${card.is_main_competitor ? " (main competitor)" : ""}*`);
      lines.push("");
    }
    lines.push("Generated by FE Copilot Battlecards.");
    return lines.join("\n");
  }

  // -------------------------------------------------- clipboard / print

  async function copyToClipboard(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      try {
        await navigator.clipboard.writeText(text);
        return true;
      } catch (_) { /* fall through to legacy */ }
    }
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      const ok = document.execCommand("copy");
      document.body.removeChild(ta);
      return ok;
    } catch (_) {
      return false;
    }
  }

  function markdownToPrintHtml(card, markdown) {
    // Lightweight renderer: enough to print sections and headings cleanly.
    let html = escapeHtml(markdown);
    html = html.replace(/^### (.+)$/gm, "<h3>$1</h3>");
    html = html.replace(/^## (.+)$/gm, "<h2>$1</h2>");
    html = html.replace(/^# (.+)$/gm, "<h1>$1</h1>");
    html = html.replace(/^&gt; (.+)$/gm, "<blockquote>$1</blockquote>");
    html = html.replace(/^- (.+)$/gm, "<li>$1</li>");
    html = html.replace(/(?:<li>[\s\S]*?<\/li>\n?)+/g, (m) => `<ul>${m}</ul>`);
    html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/\n{2,}/g, "<br><br>");
    html = html.replace(/\n/g, "<br>");
    return html;
  }

  function printCard(card) {
    const markdown = buildMarkdown(card);
    const win = window.open("", "_blank", "width=900,height=1000");
    if (!win) return;
    const title = `Battlecard - Elastic vs ${card.competitor || "Competitor"}`;
    const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>${escapeHtml(title)}</title>
<style>
  body { font-family: -apple-system, Inter, system-ui, sans-serif; max-width: 760px; margin: 36px auto; padding: 0 24px; color: #1d2128; line-height: 1.55; background: #fff; }
  h1 { font-size: 24px; margin: 0 0 6px; color: #0077CC; }
  h2 { font-size: 16px; margin: 22px 0 8px; color: #1d2128; border-bottom: 1px solid #e1e4ea; padding-bottom: 4px; }
  h3 { font-size: 14px; margin: 14px 0 4px; color: #343741; }
  blockquote { margin: 0 0 14px; padding: 10px 14px; border-left: 3px solid #F04E98; color: #4b5160; font-style: italic; background: #faf3f7; }
  ul { padding-left: 20px; }
  li { margin-bottom: 4px; }
  strong { color: #1d2128; }
  .meta { color: #6a7075; font-size: 12px; margin-bottom: 18px; }
</style></head><body>
<h1>${escapeHtml(title)}</h1>
<div class="meta">FE Copilot Battlecards, ${new Date().toLocaleString()}</div>
<div>${markdownToPrintHtml(card, markdown)}</div>
<script>setTimeout(() => window.print(), 300);</script>
</body></html>`;
    win.document.open();
    win.document.write(html);
    win.document.close();
  }

  function flashBtn(btn, ok, doneLabel, failLabel, baseLabel) {
    if (!btn) return;
    const span = btn.querySelector("span");
    const original = baseLabel || (span ? span.textContent : btn.textContent);
    const label = ok ? doneLabel : failLabel;
    if (span) span.textContent = label;
    else btn.textContent = label;
    btn.classList.toggle("is-ok", !!ok);
    btn.classList.toggle("is-bad", !ok);
    setTimeout(() => {
      if (span) span.textContent = original;
      else btn.textContent = original;
      btn.classList.remove("is-ok", "is-bad");
    }, 1800);
  }

  // -------------------------------------------------- detail view render

  function buildPreamble(card) {
    const name = card.competitor || "Competitor";
    const lines = [];
    lines.push(`Context: I am preparing for a customer conversation where the competitor is ${name}.`);
    lines.push("Below is the full FE Copilot battlecard for this competitor. Use it as primary grounding when I ask follow-up questions.");
    lines.push("");
    lines.push(`## Competitor: ${name}`);
    if (card.tagline) lines.push(`Tagline: ${card.tagline}`);
    if (card.key_pain) {
      lines.push("");
      lines.push(`### Customer pain`);
      lines.push(card.key_pain);
    }
    const tps = Array.isArray(card.talking_points) ? card.talking_points : [];
    if (tps.length) {
      lines.push("");
      lines.push("### Talking points");
      tps.forEach((p, i) => {
        lines.push(`${i + 1}. ${p.angle || "Angle"}: ${p.claim || ""}`);
        if (p.proof) lines.push(`   Proof: ${p.proof}`);
      });
    }
    const adv = Array.isArray(card.elastic_advantages) ? card.elastic_advantages : [];
    if (adv.length) {
      lines.push("");
      lines.push("### Elastic counter-positioning");
      adv.forEach((a) => lines.push(`- ${a}`));
    }
    const proofs = Array.isArray(card.proof_points) ? card.proof_points : [];
    if (proofs.length) {
      lines.push("");
      lines.push("### Proof points");
      proofs.forEach((p) => {
        lines.push(`- ${p.metric || ""}${p.source ? " [source: " + p.source + "]" : ""}`);
      });
    }
    if (card.pricing_anchor) {
      lines.push("");
      lines.push("### Pricing anchor");
      lines.push(card.pricing_anchor);
    }
    const objs = (Array.isArray(card.objection_handlers) && card.objection_handlers.length
      ? card.objection_handlers
      : Array.isArray(card.common_objections) ? card.common_objections : []);
    if (objs.length) {
      lines.push("");
      lines.push("### Common objections");
      objs.forEach((o) => {
        lines.push(`Q: ${o.q || ""}`);
        lines.push(`A: ${o.a || ""}`);
      });
    }
    const gotchas = Array.isArray(card.gotchas) ? card.gotchas : [];
    if (gotchas.length) {
      lines.push("");
      lines.push("### Honest gotchas (where the competitor genuinely beats Elastic)");
      gotchas.forEach((g) => lines.push(`- ${g}`));
    }
    if (card.clincher) {
      lines.push("");
      lines.push(`### Clincher`);
      lines.push(card.clincher);
    }
    const dq = Array.isArray(card.discovery_questions) ? card.discovery_questions : [];
    if (dq.length) {
      lines.push("");
      lines.push("### Discovery questions");
      dq.forEach((q, i) => lines.push(`${i + 1}. ${q}`));
    }
    lines.push("");
    lines.push(`## Sloane competitor positioning (master-agent guidance)`);
    lines.push(`Sloane is the FE Copilot master agent. Treat the battlecard above as authoritative for ${name}-specific positioning. When the user asks for technical or pricing comparisons, prefer calling the fec_compare tool and the fec_knowledge_search tool. When the user asks Elastic-product questions, use fec_knowledge_search. Keep answers concise and tied to the customer pain and proof points listed above.`);
    return lines.join("\n");
  }

  function buildHero(card) {
    const name = card.competitor || "Competitor";
    const wrap = el("div", { class: "bc-hero" });
    wrap.appendChild(el("div", { class: "bc-hero-glyph", "aria-hidden": "true" }, glyphFor(name)));
    const block = el("div", { class: "bc-hero-text" });
    const eyebrow = el("div", { class: "bc-hero-eyebrow" }, "Battlecard");
    if (card.vertical) {
      eyebrow.appendChild(
        el("span", {
          class: "bc-vbadge bc-vbadge-" + String(card.vertical).replace(/_/g, "-"),
          style: "margin-left:10px",
        }, verticalLabel(card.vertical))
      );
    }
    if (card.is_main_competitor) {
      eyebrow.appendChild(
        el("span", { class: "bc-vbadge bc-vbadge-main", style: "margin-left:6px" }, "main")
      );
    }
    block.appendChild(eyebrow);
    block.appendChild(el("h1", { class: "bc-hero-title" }, [
      el("span", { class: "bc-hero-vs" }, "Elastic vs "),
      el("span", { class: "bc-hero-name" }, name),
    ]));
    if (card.tagline) {
      block.appendChild(el("p", { class: "bc-hero-tagline" }, card.tagline));
    }
    block.appendChild(el("div", { class: "bc-hero-stats" }, [
      el("span", { class: "bc-hero-stat" }, [
        el("strong", {}, String((card.talking_points || []).length)),
        el("em", {}, "talking points"),
      ]),
      el("span", { class: "bc-hero-stat" }, [
        el("strong", {}, String((card.common_objections || []).length)),
        el("em", {}, "objections"),
      ]),
      el("span", { class: "bc-hero-stat" }, [
        el("strong", {}, String((card.discovery_questions || []).length)),
        el("em", {}, "discovery Qs"),
      ]),
      el("span", { class: "bc-hero-stat" }, [
        el("strong", {}, String((card.elastic_advantages || []).length)),
        el("em", {}, "advantages"),
      ]),
    ]));
    wrap.appendChild(block);
    return wrap;
  }

  function buildContent(card) {
    const wrap = el("div", { class: "bc-content" });

    if (card.key_pain) {
      wrap.appendChild(
        el("div", { class: "bc-block bc-block-pain" }, [
          el("div", { class: "bc-block-lbl" }, "Customer pain"),
          el("p", { class: "bc-pain-body" }, card.key_pain),
        ])
      );
    }

    const tps = Array.isArray(card.talking_points) ? card.talking_points : [];
    if (tps.length) {
      const grid = el("div", { class: "bc-tp-grid" });
      tps.forEach((p, i) => {
        const tile = el("article", { class: "bc-tp-tile" });
        tile.appendChild(el("div", { class: "bc-tp-num" }, String(i + 1).padStart(2, "0")));
        tile.appendChild(el("div", { class: "bc-tp-angle-lg" }, p.angle || "Angle"));
        if (p.claim) tile.appendChild(el("p", { class: "bc-tp-claim-lg" }, p.claim));
        if (p.proof) {
          tile.appendChild(
            el("div", { class: "bc-tp-proof-lg" }, [
              el("span", { class: "bc-tp-proof-lbl" }, "PROOF"),
              el("code", { class: "bc-tp-proof-code" }, p.proof),
            ])
          );
        }
        tile.appendChild(makeVoteRow(slugOf(card) + ":tp:" + i, true));
        grid.appendChild(tile);
      });
      wrap.appendChild(
        el("section", { class: "bc-block" }, [
          el("div", { class: "bc-block-lbl" }, "Talking points"),
          grid,
        ])
      );
    }

    const adv = Array.isArray(card.elastic_advantages) ? card.elastic_advantages : [];
    if (adv.length) {
      wrap.appendChild(
        el("section", { class: "bc-block" }, [
          el("div", { class: "bc-block-lbl" }, "Elastic counter-positioning"),
          el("ul", { class: "bc-adv-list" }, adv.map((a) => el("li", {}, a))),
        ])
      );
    }

    // Proof points (new schema). Optional.
    const proofs = Array.isArray(card.proof_points) ? card.proof_points : [];
    if (proofs.length) {
      const list = el("ul", { class: "bc-proof-list" });
      proofs.forEach((p) => {
        const li = el("li", { class: "bc-proof-item" });
        li.appendChild(el("span", { class: "bc-proof-metric" }, p.metric || ""));
        if (p.source) li.appendChild(el("span", { class: "bc-proof-source" }, "source: " + p.source));
        list.appendChild(li);
      });
      wrap.appendChild(
        el("section", { class: "bc-block" }, [
          el("div", { class: "bc-block-lbl" }, "Proof points"),
          list,
        ])
      );
    }

    // Pricing anchor (new schema). Optional.
    if (card.pricing_anchor) {
      wrap.appendChild(
        el("section", { class: "bc-block bc-block-price" }, [
          el("div", { class: "bc-block-lbl" }, "Pricing anchor"),
          el("p", { class: "bc-pain-body" }, card.pricing_anchor),
        ])
      );
    }

    // Objections: prefer new objection_handlers, fall back to common_objections.
    const objs = (Array.isArray(card.objection_handlers) && card.objection_handlers.length
      ? card.objection_handlers
      : Array.isArray(card.common_objections) ? card.common_objections : []);
    if (objs.length) {
      const list = el("dl", { class: "bc-obj-grid" });
      objs.forEach((o) => {
        list.appendChild(el("dt", { class: "bc-obj-q-lg" }, '"' + (o.q || "") + '"'));
        list.appendChild(el("dd", { class: "bc-obj-a-lg" }, o.a || ""));
      });
      wrap.appendChild(
        el("section", { class: "bc-block" }, [
          el("div", { class: "bc-block-lbl" }, "Common objections"),
          list,
        ])
      );
    }

    // Gotchas (new schema). Optional. Honest limits, not weaknesses to hide.
    const gotchas = Array.isArray(card.gotchas) ? card.gotchas : [];
    if (gotchas.length) {
      wrap.appendChild(
        el("section", { class: "bc-block bc-block-gotchas" }, [
          el("div", { class: "bc-block-lbl" }, "Honest gotchas"),
          el("ul", { class: "bc-adv-list bc-gotcha-list" }, gotchas.map((g) => el("li", {}, g))),
        ])
      );
    }

    const dq = Array.isArray(card.discovery_questions) ? card.discovery_questions : [];
    if (dq.length) {
      const dqList = el("ol", { class: "bc-dq-list" });
      dq.forEach((q, i) => {
        const li = el("li", { class: "bc-dq-item" });
        li.appendChild(document.createTextNode(q));
        li.appendChild(makeVoteRow(slugOf(card) + ":dq:" + i, true));
        dqList.appendChild(li);
      });
      wrap.appendChild(
        el("section", { class: "bc-block bc-block-discovery" }, [
          el("div", { class: "bc-block-lbl" }, "Discovery questions"),
          dqList,
        ])
      );
    }

    // Clincher (new schema). Optional one-line closer.
    if (card.clincher) {
      wrap.appendChild(
        el("section", { class: "bc-block bc-block-clincher" }, [
          el("div", { class: "bc-block-lbl" }, "Clincher"),
          el("p", { class: "bc-clincher-body" }, card.clincher),
        ])
      );
    }

    return wrap;
  }

  function mountChat(card) {
    const slug = slugOf(card);
    const host = $("#bc-chat-host");
    if (!host) return;
    if (STATE.miniMounted === slug && STATE.chatHandle) return; // already mounted
    // Tear down any previous instance before remounting so listeners + DOM
    // do not leak when the FE swaps competitors.
    if (STATE.chatHandle && typeof STATE.chatHandle.dispose === "function") {
      try { STATE.chatHandle.dispose(); } catch (_) {}
      STATE.chatHandle = null;
    }
    if (!window.BattlecardChat || typeof BattlecardChat.mount !== "function") {
      host.innerHTML = "";
      host.appendChild(
        el("div", { class: "bc-chat-fallback" }, [
          el("strong", {}, "Specialist offline"),
          el("span", {}, "Could not load the embedded chat. The battlecard is still readable; reload the page to retry."),
        ])
      );
      STATE.miniMounted = slug;
      return;
    }
    try {
      STATE.chatHandle = BattlecardChat.mount(host, { card });
    } catch (e) {
      console.warn("battlecard-chat.mount", (e && e.message) || e);
      host.innerHTML = "";
      host.appendChild(
        el("div", { class: "bc-chat-fallback" }, [
          el("strong", {}, "Specialist offline"),
          el("span", {}, "The specialist chat could not start. The battlecard above is still ready to use."),
        ])
      );
    }
    STATE.miniMounted = slug;
  }

  function renderDetail(card) {
    const detail = $("#bc-detail");
    const grid = $("#bc-grid-view");
    const body = $("#bc-detail-body");
    const crumb = $("#bc-detail-crumb-name");
    if (!detail || !body) return;

    if (crumb) crumb.textContent = card.competitor || "Competitor";

    clear(body);

    // LEFT column: full battlecard rendered as a sales kit.
    const left = el("div", { class: "bc-detail-main" }, [
      buildHero(card),
      buildContent(card),
    ]);

    // RIGHT column: embedded Field Assistant chat host.
    const right = el("aside", { class: "bc-detail-chat", "aria-label": "Field Assistant chat scoped to " + (card.competitor || "competitor") }, [
      el("div", { class: "bc-chat-host", id: "bc-chat-host" }),
    ]);

    body.appendChild(left);
    body.appendChild(right);
    body.setAttribute("data-persona", STATE.persona);

    // Show / hide.
    if (grid) grid.hidden = true;
    detail.hidden = false;
    document.body.classList.add("bc-detail-open");

    // Update document title for a11y (announces the page change to screen readers).
    document.title = `Battlecard: Elastic vs ${card.competitor || "Competitor"} - FE Copilot`;

    // Mount the embedded chat. Reset slug tracker if the user navigated to a
    // different competitor while a previous mini was still in place.
    STATE.miniMounted = null;
    mountChat(card);

    // Scroll detail body to top so the user lands on the hero.
    window.scrollTo({ top: 0, behavior: "instant" in window ? "instant" : "auto" });

    // Move focus to the back button so keyboard users land in the new view.
    const backBtn = $("#bc-back-btn");
    if (backBtn) {
      try { backBtn.focus({ preventScroll: true }); } catch (_) { backBtn.focus(); }
    }
  }

  function showGrid() {
    const detail = $("#bc-detail");
    const grid = $("#bc-grid-view");
    if (detail) detail.hidden = true;
    if (grid) grid.hidden = false;
    document.body.classList.remove("bc-detail-open");
    document.title = "FE Copilot - Battlecards";
    STATE.activeSlug = null;
    // Dispose the specialist chat so listeners do not linger while the user
    // browses the grid. A subsequent renderDetail() remounts a fresh handle.
    if (STATE.chatHandle && typeof STATE.chatHandle.dispose === "function") {
      try { STATE.chatHandle.dispose(); } catch (_) {}
      STATE.chatHandle = null;
      STATE.miniMounted = null;
    }
    // Restore focus to the originating card if we still have it.
    if (STATE.lastFocus && document.body.contains(STATE.lastFocus)) {
      try { STATE.lastFocus.focus({ preventScroll: true }); } catch (_) { STATE.lastFocus.focus(); }
    }
    STATE.lastFocus = null;
  }

  function showNotFound(slug) {
    const detail = $("#bc-detail");
    const grid = $("#bc-grid-view");
    const body = $("#bc-detail-body");
    const crumb = $("#bc-detail-crumb-name");
    if (!detail || !body) return;
    if (crumb) crumb.textContent = "Not found";
    clear(body);
    body.appendChild(
      el("div", { class: "bc-detail-empty" }, [
        el("strong", {}, "No battlecard for that competitor."),
        el("span", {}, `We could not find a card matching "${slug}". Pick one from the grid.`),
        el("a", { href: "#", class: "bc-action-btn bc-action-primary", style: "margin-top:14px;display:inline-flex" }, "Back to grid"),
      ])
    );
    if (grid) grid.hidden = true;
    detail.hidden = false;
    document.body.classList.add("bc-detail-open");
    document.title = "Battlecard not found - FE Copilot";
  }

  // ------------------------------------------------------------- routing

  function routeFromHash() {
    const hash = decodeURIComponent((location.hash || "").replace(/^#/, "")).toLowerCase().trim();
    if (!hash) {
      showGrid();
      return;
    }
    if (!STATE.cards.length) {
      // Cards have not loaded yet. Defer; load() will re-route once data arrives.
      STATE.activeSlug = hash;
      return;
    }
    const card = findCard(hash);
    if (!card) {
      STATE.activeSlug = null;
      showNotFound(hash);
      return;
    }
    STATE.activeSlug = hash;
    renderDetail(card);
  }

  function bindRouting() {
    window.addEventListener("hashchange", routeFromHash);
  }

  // ------------------------------------------------- detail toolbar wire

  function bindDetailToolbar() {
    const back = $("#bc-back-btn");
    const crumbBack = $("#bc-detail-back-crumb");
    const copy = $("#bc-copy-btn");
    const print = $("#bc-print-btn");
    const drive = $("#bc-drive-btn");

    function activeCard() {
      if (!STATE.activeSlug) return null;
      return findCard(STATE.activeSlug);
    }

    function goBack(ev) {
      if (ev) ev.preventDefault();
      // Clearing the hash via History keeps a clean URL and triggers hashchange.
      if (location.hash) {
        history.pushState(null, "", location.pathname + location.search);
        showGrid();
      } else {
        showGrid();
      }
    }

    if (back) back.addEventListener("click", goBack);
    if (crumbBack) crumbBack.addEventListener("click", goBack);

    if (copy) copy.addEventListener("click", async () => {
      const card = activeCard();
      if (!card) return;
      const ok = await copyToClipboard(buildMarkdown(card));
      flashBtn(copy, ok, "Copied", "Failed", "Copy Markdown");
    });

    if (print) print.addEventListener("click", () => {
      const card = activeCard();
      if (!card) return;
      printCard(card);
    });

    if (drive) drive.addEventListener("click", () => {
      const card = activeCard();
      if (!card) return;
      // Open Drive inside the user gesture so the popup blocker stays happy.
      const win = window.open("https://docs.google.com/document/create?usp=openurl", "_blank");
      const md = buildMarkdown(card);
      copyToClipboard(md).then((ok) => {
        flashBtn(drive, ok, "Copied. Paste in Drive.", "Clipboard blocked", "Open in Drive");
        if (!ok && win) {
          // Fallback: surface the markdown in the new tab so the user can copy by hand.
          try {
            win.document.open();
            win.document.write(`<pre style="white-space:pre-wrap;font:14px monospace;padding:24px">${escapeHtml(md)}</pre>`);
            win.document.close();
          } catch (_) {}
        }
      });
    });
  }

  function bindSearch() {
    const input = $("#bc-search");
    if (input) {
      input.addEventListener("input", (ev) => applyFilter(ev.target.value || ""));
      input.addEventListener("keydown", (ev) => {
        if (ev.key === "Escape" && input.value) {
          input.value = "";
          applyFilter("");
        }
      });
    }
  }

  function bindVerticalFilter() {
    const row = $("#bc-chip-row");
    if (row) {
      row.addEventListener("click", (ev) => {
        const btn = ev.target.closest && ev.target.closest(".bc-chip");
        if (!btn) return;
        ev.preventDefault();
        setVertical(btn.getAttribute("data-vertical") || "all");
      });
    }
    const toggle = $("#bc-main-toggle");
    if (toggle) {
      toggle.addEventListener("change", () => setMainsOnly(toggle.checked));
    }
  }

  function bindIndustryFilter() {
    const select = $("#bc-industry-select");
    if (select) {
      select.addEventListener("change", () => setIndustry(select.value || "all"));
    }
    const clearBtn = $("#bc-industry-clear");
    if (clearBtn) {
      clearBtn.addEventListener("click", (ev) => {
        ev.preventDefault();
        setIndustry("all");
      });
    }
  }

  // ----------------------------------------------------------------- load

  async function load() {
    const grid = $("#bc-grid");
    try {
      const data = await apiGet("/battlecards");
      STATE.cards = Array.isArray(data && data.items) ? data.items : [];
      STATE.source = (data && data.source) || "seed";
      // Order by competitor importance / marketshare, GLOBALLY (not per
      // vertical). Lower rank = bigger / more strategic in Elastic
      // conversations. Tie breaker is is_main_competitor first, then
      // alphabetical. Ranks reflect a mix of (a) vendor revenue, (b)
      // frequency of head-to-head Elastic deals, and (c) deal-size impact.
      const IMPORTANCE = {
        // Top-of-mind giants (Splunk replacement, Datadog displacement,
        // CrowdStrike SIEM-side, AWS OpenSearch fork, MS Sentinel gov).
        "splunk": 1,
        "datadog": 2,
        "crowdstrike": 3,
        "aws-opensearch": 4,
        "microsoft sentinel": 5,
        "dynatrace": 6,
        "algolia": 7,
        "pinecone": 8,
        "sentinelone": 9,
        "wiz": 10,
        // Strong second tier.
        "grafana": 11,
        "new relic": 12,
        "coveo": 13,
        "sumo logic": 14,
        "chronicle": 15,
        "lucidworks": 16,
        "weaviate": 17,
        "milvus": 18,
        "typesense": 19,
        "meilisearch": 20,
        // Non-main but relevant in conversations.
        "appdynamics": 21,
        "splunk-cloud": 22,
        "cisco-bundle": 23,
        "qradar": 24,
        "cribl": 25,
        "servicenow-itom": 26,
        "exabeam": 27,
        "honeycomb": 28,
        "loki": 29,
        "graylog": 30,
        "dragos": 31,
      };
      const rankOf = (c) => {
        const slug = String(c.competitor_slug || c.competitor || "").toLowerCase();
        const r = IMPORTANCE[slug];
        return typeof r === "number" ? r : 999;
      };
      STATE.cards.sort((a, b) => {
        const am = a.is_main_competitor ? 0 : 1;
        const bm = b.is_main_competitor ? 0 : 1;
        if (am !== bm) return am - bm;
        const ar = rankOf(a);
        const br = rankOf(b);
        if (ar !== br) return ar - br;
        return String(a.competitor || "").localeCompare(String(b.competitor || ""));
      });
      setMeta(STATE.cards.length, STATE.source);
      applyFilter("");
      // Re-route now that data is available (handles deep-link to #slug).
      routeFromHash();
    } catch (err) {
      console.warn("battlecards.load", (err && err.message) || err);
      setMeta(0, "seed");
      if (grid) {
        clear(grid);
        const safe = (typeof sanitizeError === "function")
          ? sanitizeError(err)
          : (err && err.message) || "Network error, check that the backend is running.";
        grid.appendChild(
          el("div", { class: "bc-empty" }, [
            el("strong", {}, "Could not load battlecards."),
            el("span", {}, safe),
          ])
        );
      }
      if (typeof toast === "function") toast("Failed to load battlecards", "bad");
    }
  }

  function bindPersonaToggle() {
    const host = $("#bc-persona-toggle-host");
    if (!host) return;

    const wrap = el("div", {
      class: "bc-persona-toggle",
      role: "group",
      "aria-label": "View persona",
    });

    function makeBtn(value, icon, label, title) {
      return el("button", {
        type: "button",
        class: "bc-persona-btn" + (STATE.persona === value ? " active" : ""),
        "aria-pressed": STATE.persona === value ? "true" : "false",
        "data-persona": value,
        title,
      }, [el("span", { class: "bc-persona-icon" }, icon), " " + label]);
    }

    const saBtn = makeBtn("sa", "🎯", "Solution Architect", "Discovery questions, deal research, competitive strategy");
    const caBtn = makeBtn("ca", "⚙️", "Customer Architect", "Technical depth, proof, architecture - discovery questions hidden");

    function setPersona(p) {
      STATE.persona = p;
      try { localStorage.setItem("fec.bc.persona", p); } catch (_) {}
      saBtn.className = "bc-persona-btn" + (p === "sa" ? " active" : "");
      saBtn.setAttribute("aria-pressed", p === "sa" ? "true" : "false");
      caBtn.className = "bc-persona-btn" + (p === "ca" ? " active" : "");
      caBtn.setAttribute("aria-pressed", p === "ca" ? "true" : "false");
      const body = $("#bc-detail-body");
      if (body) body.setAttribute("data-persona", p);
    }

    saBtn.addEventListener("click", () => setPersona("sa"));
    caBtn.addEventListener("click", () => setPersona("ca"));

    wrap.appendChild(saBtn);
    wrap.appendChild(caBtn);
    host.appendChild(wrap);
  }

  function init() {
    bindSearch();
    bindVerticalFilter();
    bindIndustryFilter();
    bindPersonaToggle();
    bindRouting();
    bindDetailToolbar();
    routeFromHash(); // shows grid until data arrives or hash is empty
    load();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
