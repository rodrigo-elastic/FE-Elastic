/*
  filename: tar-widget.js
  description: Technical Account Review (TAR) inline widget for the meeting view.
  Renders deployment health, feature gaps, prioritised recommendations, CA action
  items, and QBR-ready copy bullets. Self-contained - uses only inline styles
  that reference the same CSS variables as styles.css (dark Elastic theme).
  Author: Rodrigo Careaga
  Date: 09-05-2026
*/
(function () {
  "use strict";

  // --------------------------------------------------------- Palette constants
  const C = {
    navy:     "#0F2D5C",
    gold:     "#F1A730",
    red:      "#E84B37",
    teal:     "#00BFB3",
    green:    "#3CB44B",
    warning:  "#F1A730",
    critical: "#E84B37",
    healthy:  "#3CB44B",
    surface:  "var(--surface, #111217)",
    bg:       "var(--bg-page, #07080c)",
    border:   "var(--border, #2a2b30)",
    text:     "var(--fg, #d4d9e0)",
    muted:    "var(--text-muted, #8b919a)",
  };

  // --------------------------------------------------------- Style injection
  function injectStyles() {
    if (document.getElementById("tar-widget-styles")) return;
    const css = `
      .tar-widget { font-size: 13px; color: ${C.text}; border: 1px solid ${C.border}; border-radius: 8px; overflow: hidden; }
      .tar-section-header { display: flex; align-items: center; gap: 8px; padding: 9px 14px; font-weight: 700; font-size: 11px; letter-spacing: .05em; text-transform: uppercase; color: #fff; }
      .tar-body { padding: 14px; background: ${C.bg}; }
      .tar-row-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 0; }
      .tar-col { padding: 14px; background: ${C.bg}; }
      .tar-col + .tar-col { border-left: 1px solid ${C.border}; }
      .tar-health-score { font-size: 44px; font-weight: 800; line-height: 1; margin-bottom: 4px; }
      .tar-health-sub { font-size: 12px; color: ${C.muted}; margin-bottom: 10px; }
      .tar-health-summary { font-size: 12px; color: ${C.muted}; line-height: 1.5; }
      .tar-health-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 6px; }
      .tar-health-item { display: flex; align-items: flex-start; gap: 8px; font-size: 12px; line-height: 1.4; }
      .tar-dot { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; margin-top: 3px; }
      .tar-dot-healthy  { background: ${C.green}; }
      .tar-dot-warning  { background: ${C.warning}; }
      .tar-dot-critical { background: ${C.critical}; }
      .tar-health-area { font-weight: 600; color: ${C.text}; }
      .tar-health-detail { color: ${C.muted}; }
      .tar-divider { height: 1px; background: ${C.border}; }
      .tar-table { width: 100%; border-collapse: collapse; font-size: 12px; }
      .tar-table th { text-align: left; padding: 6px 8px; color: ${C.muted}; font-weight: 600; border-bottom: 1px solid ${C.border}; font-size: 11px; letter-spacing: .04em; }
      .tar-table td { padding: 7px 8px; border-bottom: 1px solid ${C.border}; vertical-align: top; line-height: 1.4; }
      .tar-table tr:last-child td { border-bottom: none; }
      .tar-pill { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 10px; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; }
      .tar-pill-enabled    { background: rgba(0,191,179,.18); color: #00BFB3; border: 1px solid rgba(0,191,179,.35); }
      .tar-pill-partial    { background: rgba(241,167,48,.18); color: ${C.gold}; border: 1px solid rgba(241,167,48,.35); }
      .tar-pill-not_enabled { background: rgba(232,75,55,.18); color: ${C.red}; border: 1px solid rgba(232,75,55,.35); }
      .tar-impact-High   { color: ${C.red}; font-weight: 700; }
      .tar-impact-Medium { color: ${C.gold}; font-weight: 700; }
      .tar-impact-Low    { color: ${C.muted}; font-weight: 600; }
      .tar-rec-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 7px; }
      .tar-rec-item { font-size: 12px; line-height: 1.5; color: ${C.text}; padding-left: 14px; position: relative; }
      .tar-rec-item::before { content: "•"; position: absolute; left: 0; color: ${C.red}; font-weight: 700; }
      .tar-action-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 7px; }
      .tar-action-item { font-size: 12px; line-height: 1.5; color: ${C.text}; padding-left: 14px; position: relative; }
      .tar-action-item::before { content: "→"; position: absolute; left: 0; color: ${C.teal}; font-weight: 700; }
      .tar-qbr-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 8px; }
      .tar-qbr-item { display: flex; align-items: flex-start; gap: 8px; font-size: 12px; line-height: 1.5; }
      .tar-qbr-text { flex: 1; color: ${C.text}; }
      .tar-copy-btn { flex-shrink: 0; padding: 2px 8px; border-radius: 4px; border: 1px solid ${C.border}; background: transparent; color: ${C.muted}; font-size: 10px; font-weight: 600; cursor: pointer; transition: color .15s, border-color .15s; }
      .tar-copy-btn:hover { color: ${C.teal}; border-color: ${C.teal}; }
      .tar-copy-btn.copied { color: ${C.green}; border-color: ${C.green}; }
      .tar-features-row { display: flex; flex-wrap: wrap; gap: 6px; padding: 0; margin: 0; list-style: none; }
      .tar-feature-chip { display: inline-flex; align-items: center; padding: 3px 10px; border-radius: 999px; font-size: 11px; font-weight: 600; background: rgba(0,191,179,.12); color: #00BFB3; border: 1px solid rgba(0,191,179,.25); }
      @media (max-width: 640px) { .tar-row-2 { grid-template-columns: 1fr; } .tar-col + .tar-col { border-left: none; border-top: 1px solid ${C.border}; } }
    `;
    const s = document.createElement("style");
    s.id = "tar-widget-styles";
    s.textContent = css;
    document.head.appendChild(s);
  }

  // --------------------------------------------------------- Small DOM helpers
  function h(tag, attrs, children) {
    const el = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        if (k === "class") el.className = attrs[k];
        else if (k === "style") el.style.cssText = attrs[k];
        else if (k === "textContent") el.textContent = attrs[k];
        else el.setAttribute(k, attrs[k]);
      });
    }
    if (children) {
      (Array.isArray(children) ? children : [children]).forEach(function (c) {
        if (c == null) return;
        if (typeof c === "string") el.appendChild(document.createTextNode(c));
        else el.appendChild(c);
      });
    }
    return el;
  }

  function sectionHeader(label, bgColor) {
    return h("div", { class: "tar-section-header", style: "background:" + bgColor }, [label]);
  }

  // --------------------------------------------------------- Health score color
  function scoreColor(score) {
    if (score >= 80) return C.green;
    if (score >= 60) return C.warning;
    return C.critical;
  }

  // --------------------------------------------------------- Dot for status
  function statusDot(status) {
    return h("span", { class: "tar-dot tar-dot-" + (status || "healthy") });
  }

  // --------------------------------------------------------- Render sections

  function renderHealthSection(tar) {
    const score = tar.health_score != null ? tar.health_score : 0;
    const color = scoreColor(score);

    // Left: score + summary
    const left = h("div", { class: "tar-col" }, [
      h("div", { class: "tar-health-score", style: "color:" + color }, String(score) + "/100"),
      h("div", { class: "tar-health-sub" }, "Deployment health score"),
      h("div", { class: "tar-health-summary" }, tar.health_summary || ""),
    ]);

    // Right: health item list
    const items = (tar.health_items || []).map(function (item) {
      return h("li", { class: "tar-health-item" }, [
        statusDot(item.status),
        h("div", {}, [
          h("span", { class: "tar-health-area" }, item.area + ": "),
          h("span", { class: "tar-health-detail" }, item.detail || ""),
        ]),
      ]);
    });
    const right = h("div", { class: "tar-col" }, [
      h("ul", { class: "tar-health-list" }, items.length ? items : [
        h("li", { class: "tar-health-item" }, [statusDot("healthy"), "No health items recorded."]),
      ]),
    ]);

    const row = h("div", { class: "tar-row-2" }, [left, right]);
    return row;
  }

  function renderFeatureGapsSection(tar) {
    const gaps = tar.feature_gaps || [];
    if (!gaps.length) {
      return h("div", { class: "tar-body" }, [
        h("p", { style: "color:" + C.muted + ";margin:0;font-size:12px" }, "No feature gaps identified."),
      ]);
    }
    const thead = h("thead", {}, [
      h("tr", {}, [
        h("th", {}, "Feature"),
        h("th", {}, "Status"),
        h("th", {}, "Impact"),
        h("th", {}, "Recommendation"),
      ]),
    ]);
    const rows = gaps.map(function (g) {
      return h("tr", {}, [
        h("td", { style: "font-weight:600;color:" + C.text }, g.feature || ""),
        h("td", {}, [h("span", { class: "tar-pill tar-pill-" + (g.status || "not_enabled") }, (g.status || "").replace(/_/g, " "))]),
        h("td", {}, [h("span", { class: "tar-impact-" + (g.impact || "Low") }, g.impact || "")]),
        h("td", { style: "color:" + C.muted }, g.recommendation || ""),
      ]);
    });
    const tbody = h("tbody", {}, rows);
    const table = h("table", { class: "tar-table" }, [thead, tbody]);
    return h("div", { class: "tar-body" }, [table]);
  }

  function renderRecommendations(tar) {
    const recs = tar.recommendations || [];
    if (!recs.length) {
      return h("div", { class: "tar-body" }, [
        h("p", { style: "color:" + C.muted + ";margin:0;font-size:12px" }, "No recommendations generated."),
      ]);
    }
    const items = recs.map(function (r) {
      return h("li", { class: "tar-rec-item" }, [r]);
    });
    return h("div", { class: "tar-body" }, [h("ul", { class: "tar-rec-list" }, items)]);
  }

  function renderCAActions(tar) {
    const actions = tar.ca_actions || [];
    if (!actions.length) {
      return h("div", { class: "tar-col", style: "border-right:1px solid " + C.border }, [
        h("p", { style: "color:" + C.muted + ";margin:0;font-size:12px" }, "No CA actions generated."),
      ]);
    }
    const items = actions.map(function (a) {
      return h("li", { class: "tar-action-item" }, [a]);
    });
    return h("div", { class: "tar-col" }, [
      h("ul", { class: "tar-action-list" }, items),
    ]);
  }

  function renderQBRFeed(tar) {
    const bullets = tar.qbr_bullets || [];
    if (!bullets.length) {
      return h("div", { class: "tar-col" }, [
        h("p", { style: "color:" + C.muted + ";margin:0;font-size:12px" }, "No QBR bullets generated."),
      ]);
    }
    const items = bullets.map(function (b) {
      const copyBtn = h("button", { class: "tar-copy-btn", title: "Copy to clipboard" }, ["Copy"]);
      copyBtn.addEventListener("click", function () {
        navigator.clipboard.writeText(b).then(function () {
          copyBtn.textContent = "Copied!";
          copyBtn.classList.add("copied");
          setTimeout(function () {
            copyBtn.textContent = "Copy";
            copyBtn.classList.remove("copied");
          }, 2000);
        }).catch(function () {
          // Fallback for browsers without clipboard API
          const ta = document.createElement("textarea");
          ta.value = b;
          ta.style.position = "fixed";
          ta.style.opacity = "0";
          document.body.appendChild(ta);
          ta.select();
          try { document.execCommand("copy"); } catch (_) {}
          document.body.removeChild(ta);
          copyBtn.textContent = "Copied!";
          copyBtn.classList.add("copied");
          setTimeout(function () {
            copyBtn.textContent = "Copy";
            copyBtn.classList.remove("copied");
          }, 2000);
        });
      });
      return h("li", { class: "tar-qbr-item" }, [
        h("span", { class: "tar-qbr-text" }, b),
        copyBtn,
      ]);
    });
    return h("div", { class: "tar-col" }, [
      h("ul", { class: "tar-qbr-list" }, items),
    ]);
  }

  function renderFeaturesEnabled(tar) {
    const features = tar.features_enabled || [];
    if (!features.length) return null;
    const chips = features.map(function (f) {
      return h("li", { class: "tar-feature-chip" }, [f]);
    });
    return h("div", { style: "padding:10px 14px 12px;background:" + C.bg }, [
      h("div", { style: "font-size:10px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;color:" + C.muted + ";margin-bottom:8px" }, "Currently enabled"),
      h("ul", { class: "tar-features-row" }, chips),
    ]);
  }

  // --------------------------------------------------------- Main render

  function renderTAR(container, tarData) {
    if (!container) return;
    injectStyles();

    const tar = tarData || {};

    const widget = h("div", { class: "tar-widget" });

    // Title header (navy)
    const titleRow = h("div", {
      class: "tar-section-header",
      style: "background:" + C.navy + ";padding:11px 14px;justify-content:space-between",
    }, [
      h("span", {}, "Technical Account Review"),
      tar.generated_at
        ? h("span", {
            style: "font-size:10px;font-weight:400;letter-spacing:0;text-transform:none;opacity:.7",
          }, [tar.company_name ? tar.company_name + " - " : "", fmtGenAt(tar.generated_at)])
        : null,
    ]);
    widget.appendChild(titleRow);

    // Health block
    widget.appendChild(renderHealthSection(tar));

    // Features enabled strip (teal-tinted)
    const featuresEl = renderFeaturesEnabled(tar);
    if (featuresEl) {
      widget.appendChild(h("div", { class: "tar-divider" }));
      widget.appendChild(featuresEl);
    }

    // Feature gaps (gold header)
    widget.appendChild(h("div", { class: "tar-divider" }));
    widget.appendChild(sectionHeader("Feature Gaps", C.gold));
    widget.appendChild(renderFeatureGapsSection(tar));

    // Priority recommendations (red header)
    widget.appendChild(h("div", { class: "tar-divider" }));
    widget.appendChild(sectionHeader("Priority Recommendations", C.red));
    widget.appendChild(renderRecommendations(tar));

    // Bottom split: CA Actions (teal) | QBR Feed (navy)
    widget.appendChild(h("div", { class: "tar-divider" }));

    const bottomHeaders = h("div", { class: "tar-row-2" }, [
      h("div", { class: "tar-section-header", style: "background:" + C.teal }, ["CA Action Items"]),
      h("div", { class: "tar-section-header", style: "background:" + C.navy }, ["QBR Feed"]),
    ]);
    widget.appendChild(bottomHeaders);

    const bottomContent = h("div", { class: "tar-row-2" }, [
      renderCAActions(tar),
      renderQBRFeed(tar),
    ]);
    widget.appendChild(bottomContent);

    container.appendChild(widget);
  }

  function fmtGenAt(iso) {
    try {
      const d = new Date(iso);
      if (isNaN(d.getTime())) return iso;
      return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })
        + " " + d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
    } catch (_) {
      return iso;
    }
  }

  // Expose on window so meeting.js can call it
  window.renderTAR = renderTAR;
})();
