/*
  filename: weekly-slides.js
  description: FE Copilot - Weekly Customer Status Slides controller.
  Author: Rodrigo Careaga
  Date: 09-05-2026
*/
(function () {
  "use strict";

  // ------------------------------------------------------------------ State

  var _weekStart = _thisWeekMonday();
  var _loading = false;

  function _thisWeekMonday() {
    var d = new Date();
    var day = d.getDay(); // 0=Sun
    var diff = day === 0 ? -6 : 1 - day;
    d.setDate(d.getDate() + diff);
    d.setHours(0, 0, 0, 0);
    return d;
  }

  function _addDays(d, n) {
    var r = new Date(d);
    r.setDate(r.getDate() + n);
    return r;
  }

  function _isoDate(d) {
    return d.getFullYear() + "-" +
      String(d.getMonth() + 1).padStart(2, "0") + "-" +
      String(d.getDate()).padStart(2, "0");
  }

  function _fmtDate(d) {
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  }

  // ------------------------------------------------------------------ Week nav

  function _updateWeekLabel() {
    var sun = _addDays(_weekStart, 6);
    var el = document.getElementById("ws-week-label");
    if (el) el.textContent = "Week of " + _fmtDate(_weekStart) + " - " + _fmtDate(sun);
  }

  // ------------------------------------------------------------------ Escape

  function esc(s) {
    return String(s || "")
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  // ------------------------------------------------------------------ Slide rendering

  function _tempClass(t) {
    if (!t) return "stable";
    return t.toLowerCase();
  }

  function _renderFooterIcons(slide) {
    var items = [
      {
        label: "[Salesforce]",
        href: slide.salesforce_url || "#",
        img: "/assets/img/salesforce-logo.svg",
        fallback: "SF",
      },
      { label: "[Consumption]", href: "#", img: null, fallback: "&#9193;" },
      { label: "[Contacts]",    href: "#", img: null, fallback: "&#128100;" },
      { label: "[LinkedIn]",    href: "#", img: null, fallback: "in" },
      { label: "[Org chart]",   href: "#", img: null, fallback: "&#128101;" },
      { label: "[GDrive]",      href: "#", img: null, fallback: "&#128196;" },
      { label: "",              href: "#",
        img: "/assets/img/elastic/glyph-cluster-color.svg", fallback: "E" },
    ];

    return items.map(function (item) {
      var iconHtml = item.img
        ? '<img class="ws-foot-icon" src="' + esc(item.img) + '" alt="" onerror="this.style.display=\'none\'" />'
        : '<div class="ws-foot-icon-placeholder">' + item.fallback + '</div>';
      return (
        '<a class="ws-foot-item" href="' + esc(item.href) + '" target="_blank" rel="noopener">' +
        iconHtml +
        (item.label ? '<span>' + esc(item.label) + '</span>' : '') +
        '</a>'
      );
    }).join("");
  }

  function _renderRenewals(renewals) {
    if (!renewals || !renewals.length) {
      return '<div style="color:#999;font-style:italic;font-size:11px;">No renewals on record.</div>';
    }
    return renewals.map(function (r) {
      return (
        '<div class="ws-renewal">' +
        '<div class="ws-renewal-label">- ' + esc(r.label) + (r.amount ? " - " + esc(r.amount) : "") + (r.date ? ", " + esc(r.date) : "") + "</div>" +
        (r.notes ? '<div class="ws-renewal-sub">- ' + esc(r.notes) + "</div>" : "") +
        (r.risk ? '<div class="ws-renewal-sub">- Risk: ' + esc(r.risk) + "</div>" : "") +
        "</div>"
      );
    }).join("");
  }

  function _renderCases(cases) {
    if (!cases || !cases.length) {
      return '<div style="color:#999;font-style:italic;font-size:11px;">No open cases.</div>';
    }
    return cases.map(function (c) {
      return '<div class="ws-case">- ' + esc(c) + "</div>";
    }).join("");
  }

  function _renderActions(current, upcoming) {
    var html = "";
    if (current && current.length) {
      html += '<div class="ws-actions-sub">Current Actions</div><ul>';
      html += current.map(function (a) { return "<li>" + esc(a) + "</li>"; }).join("");
      html += "</ul>";
    }
    if (upcoming && upcoming.length) {
      html += '<div class="ws-actions-sub">Upcoming actions</div><ul>';
      html += upcoming.map(function (a) { return "<li>" + esc(a) + "</li>"; }).join("");
      html += "</ul>";
    }
    if (!html) html = '<div style="color:#999;font-style:italic;font-size:11px;">No actions recorded.</div>';
    return html;
  }

  function _renderSlide(slide) {
    var temp = _tempClass(slide.temperature);
    var arr = slide.arr || "";
    var cloudArr = slide.cloud_arr || "";

    return (
      '<div class="ws-slide">' +

      /* ── Header ── */
      '<div class="ws-slide-hdr">' +

      /* Logo + ARR */
      '<div class="ws-hdr-logo">' +
      '<div class="ws-logo-box">Company logo</div>' +
      '<div class="ws-arr-pills">' +
      (arr ? '<div class="ws-arr-pill">ARR: <span>' + esc(arr) + "</span></div>" : '<div class="ws-arr-pill">ARR: <span>-</span></div>') +
      '<div class="ws-arr-pill">Cloud ARR: <span>' + esc(cloudArr || "-") + "</span></div>" +
      "</div>" +
      "</div>" +

      /* Company title */
      '<div class="ws-hdr-title">' +
      '<h2>' + esc(slide.company_name) + "</h2>" +
      '<h3>' + esc(slide.use_case || "") + "</h3>" +
      '<div class="ws-hdr-updated"><em>Updated: ' + esc(slide.updated || "") + "</em></div>" +
      "</div>" +

      /* Meta pills + temperature */
      '<div class="ws-hdr-meta">' +
      '<div class="ws-meta-pills-wrap">' +
      '<div class="ws-meta-pill">Training/Services: <span>' + esc(slide.training_services || "-") + "</span></div>" +
      '<div class="ws-meta-pill">Renewable Base: <span>' + esc(slide.renewable_base || "-") + "</span></div>" +
      '<div class="ws-meta-pill">Open N&amp;E: <span>' + esc(slide.open_ne || "-") + "</span></div>" +
      "</div>" +
      '<div class="ws-temp-box">' +
      '<div class="ws-temp-hdr">Potential / Temperature</div>' +
      '<div class="ws-temp-body">' +
      '<div class="ws-temp-arrow">&#11015;</div>' +
      '<div class="ws-temp-btns">' +
      '<button class="ws-temp-btn churn' + (temp === "churn" ? " active" : "") + '" title="' + esc(temp === "churn" ? slide.temperature_reason : "") + '">Churn</button>' +
      '<button class="ws-temp-btn stable' + (temp === "stable" ? " active" : "") + '" title="' + esc(temp === "stable" ? slide.temperature_reason : "") + '">Stable</button>' +
      '<button class="ws-temp-btn growth' + (temp === "growth" ? " active" : "") + '" title="' + esc(temp === "growth" ? slide.temperature_reason : "") + '">Growth</button>' +
      "</div></div></div>" +
      "</div>" +

      "</div>" + /* end .ws-slide-hdr */

      /* ── Body row (4 cols) ── */
      '<div class="ws-slide-body">' +

      /* Actions */
      '<div class="ws-section">' +
      '<div class="ws-section-hdr hdr-red">Current and upcoming actions</div>' +
      '<div class="ws-section-body">' + _renderActions(slide.current_actions, slide.upcoming_actions) + "</div>" +
      "</div>" +

      /* Renewals */
      '<div class="ws-section">' +
      '<div class="ws-section-hdr hdr-navy">Renewals</div>' +
      '<div class="ws-section-body">' + _renderRenewals(slide.renewals) + "</div>" +
      "</div>" +

      /* Cases */
      '<div class="ws-section">' +
      '<div class="ws-section-hdr hdr-orange">Cases</div>' +
      '<div class="ws-section-body">' + _renderCases(slide.cases) + "</div>" +
      "</div>" +

      /* Consumption */
      '<div class="ws-section">' +
      '<div class="ws-section-hdr hdr-teal" style="text-decoration:underline;">Consumption</div>' +
      '<div class="ws-section-body">' +
      '<div class="ws-wow"><em>WoW:</em> <span class="ws-wow-pill">' + esc(slide.wow_pct || "N/A") + "</span></div>" +
      "<p>" + esc(slide.consumption || "") + "</p>" +
      "</div>" +
      "</div>" +

      "</div>" + /* end .ws-slide-body */

      /* ── Bottom row (2 cols) ── */
      '<div class="ws-slide-btm">' +

      /* Feature Adoption */
      '<div class="ws-section">' +
      '<div class="ws-section-hdr hdr-red">Feature Adoption</div>' +
      '<div class="ws-section-body"><ul>' +
      (slide.feature_adoption && slide.feature_adoption.length
        ? slide.feature_adoption.map(function (f) { return "<li>" + esc(f) + "</li>"; }).join("")
        : '<li style="color:#999;font-style:italic;">No data</li>') +
      "</ul></div></div>" +

      /* Risks/Notes/Top of mind */
      '<div class="ws-section">' +
      '<div class="ws-section-hdr hdr-gold">Risks / Notes / Top of mind</div>' +
      '<div class="ws-section-body"><ul>' +
      (slide.risks_notes && slide.risks_notes.length
        ? slide.risks_notes.map(function (r) { return "<li>" + esc(r) + "</li>"; }).join("")
        : '<li style="color:#999;font-style:italic;">None noted.</li>') +
      "</ul></div></div>" +

      "</div>" + /* end .ws-slide-btm */

      /* ── Footer icons ── */
      '<div class="ws-slide-footer">' + _renderFooterIcons(slide) + "</div>" +

      /* Meeting count badge */
      '<div class="ws-meeting-badge">' +
      (slide.meeting_count > 1
        ? slide.meeting_count + " meetings this week"
        : "1 meeting this week") +
      "</div>" +

      "</div>" /* end .ws-slide */
    );
  }

  // ------------------------------------------------------------------ Generate

  function generate() {
    if (_loading) return;
    _loading = true;

    var container = document.getElementById("ws-slides-container");
    var meta = document.getElementById("ws-meta");
    var printBtn = document.getElementById("ws-print");
    var demoMode = document.getElementById("ws-demo-mode");
    var demo = demoMode && demoMode.checked;

    if (container) {
      container.innerHTML = '<div class="ws-empty"><span class="ws-spinner"></span>Generating slides with Claude...</div>';
    }
    if (meta) meta.textContent = "";
    if (printBtn) printBtn.style.display = "none";

    var qs = "?week_start=" + _isoDate(_weekStart) + (demo ? "&demo=true" : "");
    apiGet("/weekly-slides" + qs)
      .then(function (data) {
        _loading = false;
        if (!data.slides || !data.slides.length) {
          if (container) {
            container.innerHTML =
              '<div class="ws-empty">' +
              "No meetings found for this week." +
              (demo ? "" : ' Try <strong>Demo mode</strong> to include all historical meetings.') +
              "</div>";
          }
          return;
        }
        var html = '<div class="ws-slides-list">';
        data.slides.forEach(function (slide) { html += _renderSlide(slide); });
        html += "</div>";
        if (container) container.innerHTML = html;
        if (meta) {
          meta.textContent =
            data.companies + " customer" + (data.companies !== 1 ? "s" : "") +
            " · " + data.meetings + " meeting" + (data.meetings !== 1 ? "s" : "") +
            (data.demo ? " · demo mode" : "");
        }
        if (printBtn) printBtn.style.display = "";
      })
      .catch(function (err) {
        _loading = false;
        if (container) {
          container.innerHTML =
            '<div class="ws-empty">Failed to generate slides: ' +
            esc((err && err.message) || "unknown error") + "</div>";
        }
      });
  }

  // ------------------------------------------------------------------ Init

  function init() {
    _updateWeekLabel();

    document.getElementById("ws-prev").addEventListener("click", function () {
      _weekStart = _addDays(_weekStart, -7);
      _updateWeekLabel();
    });
    document.getElementById("ws-next").addEventListener("click", function () {
      _weekStart = _addDays(_weekStart, 7);
      _updateWeekLabel();
    });
    document.getElementById("ws-generate").addEventListener("click", generate);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
