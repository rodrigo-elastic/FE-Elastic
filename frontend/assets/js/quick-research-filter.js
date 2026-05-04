/*
  filename: quick-research-filter.js
  description: Unified filter, search and group bar for /quick-research.html.
    Pulls records from /api/v1/calendar/events, /api/v1/meetings and /api/v1/briefs,
    normalizes them into a single record shape, then renders a single grouped list
    that the FE can filter by stage, range and search, and group by Customer / Stage
    / Date / None. Hides the legacy scattered sections (#calendar-list,
    Meetings on file, History) after hydration so judges only see one organized list.
  Author: Rodrigo Careaga
  Date: 04-05-2026
*/
(function () {
  "use strict";

  const STAGE_ORDER = ["scheduled", "pre", "post", "transcript", "other"];
  const STAGE_LABELS_KEY = {
    scheduled: "qr.records.group.scheduled",
    pre: "qr.records.group.pre",
    post: "qr.records.group.post",
    transcript: "qr.records.group.transcript",
    other: "qr.records.group.other",
  };
  const STAGE_LABELS_FALLBACK = {
    scheduled: "Scheduled",
    pre: "Pre-meeting",
    post: "Post-meeting",
    transcript: "Transcript",
    other: "Other",
  };
  const STAGE_PILL_CLASS = {
    scheduled: "upcoming",
    pre: "teal",
    post: "blue",
    transcript: "pink",
    other: "",
  };

  // Single source of truth for the most recent normalized records. Refresh
  // rebuilds this; render uses it directly so we never need a re-fetch on a
  // filter or group change.
  const STATE = {
    records: [],
    query: "",
    stage: "all",
    range: "all",
    group: "stage",
    view: "kanban",   // "kanban" (default) | "list"
    hydrated: false,
  };

  function loadViewPref() {
    try {
      const v = localStorage.getItem("fec.customers.view");
      if (v === "list" || v === "kanban") STATE.view = v;
    } catch (_e) { /* ignore */ }
  }
  function saveViewPref() {
    try { localStorage.setItem("fec.customers.view", STATE.view); } catch (_e) {}
  }

  function tr(key, fallback) {
    if (typeof window.t === "function") return window.t(key, fallback);
    return fallback || key;
  }

  function safeApiGet(path) {
    if (typeof window.apiGet !== "function") return Promise.reject(new Error("apiGet missing"));
    return window.apiGet(path).catch(() => null);
  }

  function htmlEscape(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function fmt(dateIso) {
    if (!dateIso) return "";
    try {
      const d = new Date(dateIso);
      if (isNaN(d.getTime())) return "";
      return d.toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
      });
    } catch (e) {
      return "";
    }
  }

  // -------------------------------------------------------------------------
  // Fetchers + normalizers
  // -------------------------------------------------------------------------

  async function fetchAll() {
    const [calendar, meetings, briefs] = await Promise.all([
      safeApiGet("/calendar/events"),
      safeApiGet("/meetings"),
      safeApiGet("/briefs"),
    ]);

    const calItems = (calendar && calendar.items) || [];
    const mtgItems = Array.isArray(meetings) ? meetings : [];
    const briefItems = (briefs && briefs.items) || [];

    // Build maps so we can mark which meetings already have a brief / post.
    const briefByMeeting = new Map();
    const postByMeeting = new Map();
    briefItems.forEach((b) => {
      const id = b.meeting_id || b.id;
      if (!id) return;
      if (b.type === "post_meeting") postByMeeting.set(id, b);
      else briefByMeeting.set(id, b);
    });

    const records = [];
    calItems.forEach((ev) => records.push(normalizeCalendar(ev)));
    mtgItems.forEach((m) => records.push(normalizeMeeting(m, briefByMeeting, postByMeeting)));

    // Briefs whose meeting_id we did NOT already render (ad-hoc briefs and
    // transcript-only post-meeting artifacts) become standalone history rows.
    const meetingIds = new Set(mtgItems.map((m) => m.id));
    briefItems.forEach((b) => {
      const id = b.meeting_id || b.id;
      if (!id || meetingIds.has(id)) return;
      records.push(normalizeBrief(b));
    });

    return sanitizeRecords(records);
  }

  // -------------------------------------------------------------------------
  // Sanitizer: drops system / orphan / internal records, keeps only the most
  // recent timestamp when duplicates share the same id, and warns in DevTools
  // so it is easy to verify how many records were filtered.
  // -------------------------------------------------------------------------
  function isSystemRecord(record) {
    const rawId = String(record.id || "");
    // Strip the "cal:" / "mtg:" / "brf:" prefix that normalize* adds so we
    // match the underlying meeting/event id consistently.
    const id = rawId.replace(/^(cal|mtg|brf):/, "");
    const cust = String(record.customer_name || "").trim();
    const cid = String(record.customer_id || "");
    const title = String(record.title || "");
    const systemPrefixes = ["orphan-demo-", "synthetic-", "_internal-", "demo-data-"];
    if (systemPrefixes.some((p) => id.startsWith(p) || cid.startsWith(p))) return true;
    if (/FE team weekly sync/i.test(title)) return true;
    // Calendar events that don't resolve to a real customer flag with
    // customer_id === "unknown" (see normalizeCalendar). Drop those: an
    // internal-only meeting or unresolved invite has no place on the Kanban.
    if (cid === "unknown") return true;
    if (!cust) return true;
    const lower = cust.toLowerCase();
    if (["unresolved", "n/a", "(unknown)"].includes(lower)) return true;
    if (/^(unknown|placeholder|test)\b/.test(lower)) return true;
    return false;
  }

  function sanitizeRecords(records) {
    const dropped = [];
    const kept = [];
    records.forEach((r) => {
      if (isSystemRecord(r)) {
        dropped.push(r);
        return;
      }
      kept.push(r);
    });

    // Dedupe by id, keeping the entry with the most recent timestamp.
    const byId = new Map();
    let dupes = 0;
    kept.forEach((r) => {
      const id = r.id;
      if (!id) return;
      const prev = byId.get(id);
      if (!prev) {
        byId.set(id, r);
        return;
      }
      dupes += 1;
      const ta = prev.timestamp_iso ? new Date(prev.timestamp_iso).getTime() : 0;
      const tb = r.timestamp_iso ? new Date(r.timestamp_iso).getTime() : 0;
      if (tb >= ta) byId.set(id, r);
    });

    const final = Array.from(byId.values());
    if (dropped.length || dupes) {
      try {
        // eslint-disable-next-line no-console
        console.warn(
          "[QRFilter] sanitize dropped=" + dropped.length + " duplicates=" + dupes + " kept=" + final.length
        );
      } catch (_e) { /* ignore */ }
    }
    return final;
  }

  function normalizeCalendar(ev) {
    const r = ev.resolution || {};
    const company = r.company || {};
    const start = (ev.start && ev.start.dateTime) || null;
    return {
      id: "cal:" + (ev.id || Math.random().toString(36).slice(2)),
      title: ev.summary || tr("qr.records.untitled", "(untitled event)"),
      customer_name: company.name || tr("qr.records.unknown_customer", "Unresolved"),
      customer_id: company.id || "unknown",
      industry: company.industry || "",
      stage: "scheduled",
      timestamp_iso: start,
      source: "calendar",
      attendees: (ev.attendees || []).map((a) => a.email).filter(Boolean),
      hangout_link: ev.hangout_link || null,
      brief_id: null,
      post_meeting_id: null,
      // The calendar inbox row in app.js ran Pre-meeting on click and pushed
      // to /meeting.html. We keep the join link as the row anchor; the action
      // buttons will offer the same "Pre-meeting" CTA as before.
      href: ev.hangout_link || null,
      _calendar_event: ev,
    };
  }

  function normalizeMeeting(m, briefMap, postMap) {
    const hasPost = postMap.has(m.id);
    const hasBrief = briefMap.has(m.id);
    let stage;
    let source;
    if (m.is_upcoming) {
      stage = "scheduled";
      source = "meeting";
    } else if (hasPost) {
      stage = "post";
      source = "post";
    } else if (hasBrief) {
      stage = "pre";
      source = "brief";
    } else {
      stage = "pre";
      source = "meeting";
    }
    return {
      id: "mtg:" + m.id,
      title: m.title || "(untitled)",
      customer_name: m.company_name || "(unknown)",
      customer_id: m.company_id || "unknown",
      industry: m.company_industry || "",
      stage,
      timestamp_iso: m.start_time || null,
      source,
      attendees: m.attendees || [],
      hangout_link: null,
      brief_id: hasBrief ? m.id : null,
      post_meeting_id: hasPost ? m.id : null,
      href: "/meeting.html?id=" + encodeURIComponent(m.id) + (hasPost ? "&post=1" : ""),
      _meeting: m,
      _is_upcoming: !!m.is_upcoming,
    };
  }

  function normalizeBrief(b) {
    const isPost = b.type === "post_meeting";
    const stage = isPost ? "post" : "pre";
    // Transcript-only artifacts come back with company_id starting with
    // "transcript-" - flag them as 'transcript' stage so the dedicated
    // group is meaningful.
    const isTranscript = String(b.company_id || "").startsWith("transcript-") && isPost;
    return {
      id: "brf:" + (b.meeting_id || b.id || Math.random().toString(36).slice(2)),
      title: b.headline || b.summary || (isPost ? "Post-meeting analysis" : "Pre-meeting brief"),
      customer_name: b.company_name || b.company_id || "(unknown)",
      customer_id: b.company_id || "unknown",
      industry: b.industry || "",
      stage: isTranscript ? "transcript" : stage,
      timestamp_iso: b.generated_at || null,
      source: isPost ? "post" : "brief",
      attendees: [],
      hangout_link: null,
      brief_id: !isPost ? b.meeting_id : null,
      post_meeting_id: isPost ? b.meeting_id : null,
      href: "/meeting.html?id=" + encodeURIComponent(b.meeting_id) + (isPost ? "&post=1" : ""),
      _brief: b,
    };
  }

  // -------------------------------------------------------------------------
  // Filter logic
  // -------------------------------------------------------------------------

  function inRange(record, range) {
    if (range === "all" || !range) return true;
    if (!record.timestamp_iso) return true;
    const days = range === "week" ? 7 : range === "month" ? 30 : range === "quarter" ? 90 : null;
    if (days == null) return true;
    const ts = new Date(record.timestamp_iso).getTime();
    if (isNaN(ts)) return true;
    const now = Date.now();
    const lo = now - days * 24 * 60 * 60 * 1000;
    const hi = now + days * 24 * 60 * 60 * 1000;
    return ts >= lo && ts <= hi;
  }

  function matchesQuery(record, q) {
    if (!q) return true;
    const haystacks = [
      record.title,
      record.customer_name,
      record.customer_id,
      record.industry,
      ...(record.attendees || []),
    ]
      .filter(Boolean)
      .map((s) => String(s).toLowerCase());
    return haystacks.some((s) => s.includes(q));
  }

  function applyFilters(records) {
    const q = (STATE.query || "").trim().toLowerCase();
    return records.filter((r) => {
      if (STATE.stage !== "all" && r.stage !== STATE.stage) return false;
      if (!inRange(r, STATE.range)) return false;
      if (!matchesQuery(r, q)) return false;
      return true;
    });
  }

  // -------------------------------------------------------------------------
  // Grouping
  // -------------------------------------------------------------------------

  function groupRecords(records, key) {
    if (key === "none") {
      const sorted = records.slice().sort(byTimeDesc);
      return [{ key: "all", label: "", count: sorted.length, items: sorted }];
    }
    if (key === "customer") {
      const map = new Map();
      records.forEach((r) => {
        const k = r.customer_name || tr("qr.records.unknown_customer", "Unresolved");
        if (!map.has(k)) map.set(k, []);
        map.get(k).push(r);
      });
      const groups = Array.from(map.entries())
        .map(([name, items]) => ({
          key: name,
          label: name,
          count: items.length,
          items: items.slice().sort(byTimeDesc),
        }))
        .sort((a, b) => a.label.localeCompare(b.label));
      return groups;
    }
    if (key === "date") {
      const buckets = {
        today: [],
        week: [],
        month: [],
        earlier: [],
      };
      const now = Date.now();
      const dayMs = 24 * 60 * 60 * 1000;
      records.forEach((r) => {
        if (!r.timestamp_iso) {
          buckets.earlier.push(r);
          return;
        }
        const ts = new Date(r.timestamp_iso).getTime();
        const diff = Math.abs(now - ts);
        if (diff <= dayMs) buckets.today.push(r);
        else if (diff <= 7 * dayMs) buckets.week.push(r);
        else if (diff <= 30 * dayMs) buckets.month.push(r);
        else buckets.earlier.push(r);
      });
      return [
        { key: "today", label: tr("qr.records.date.today", "Today"), items: buckets.today },
        { key: "week", label: tr("qr.records.date.week", "This week"), items: buckets.week },
        { key: "month", label: tr("qr.records.date.month", "This month"), items: buckets.month },
        { key: "earlier", label: tr("qr.records.date.earlier", "Earlier"), items: buckets.earlier },
      ]
        .map((g) => ({ ...g, count: g.items.length, items: g.items.slice().sort(byTimeDesc) }))
        .filter((g) => g.count > 0);
    }
    // stage (default)
    const map = new Map();
    STAGE_ORDER.forEach((s) => map.set(s, []));
    records.forEach((r) => {
      const k = map.has(r.stage) ? r.stage : "other";
      map.get(k).push(r);
    });
    return STAGE_ORDER.map((s) => ({
      key: s,
      label: tr(STAGE_LABELS_KEY[s], STAGE_LABELS_FALLBACK[s]),
      count: map.get(s).length,
      items: map.get(s).slice().sort(byTimeDesc),
    })).filter((g) => g.count > 0);
  }

  function byTimeDesc(a, b) {
    const ta = a.timestamp_iso ? new Date(a.timestamp_iso).getTime() : 0;
    const tb = b.timestamp_iso ? new Date(b.timestamp_iso).getTime() : 0;
    return tb - ta;
  }

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  function renderCard(record) {
    const stageKey = STAGE_ORDER.includes(record.stage) ? record.stage : "other";
    const pillClass = STAGE_PILL_CLASS[stageKey] || "";
    const stageLabel = tr(STAGE_LABELS_KEY[stageKey], STAGE_LABELS_FALLBACK[stageKey]);

    const li = document.createElement("li");
    li.className = "qr-rec " + (record._is_upcoming ? "upcoming" : "");
    li.dataset.stage = stageKey;

    const info = document.createElement("div");
    info.className = "info";

    const title = document.createElement("div");
    title.className = "title";
    title.textContent = record.title;

    const meta = document.createElement("div");
    meta.className = "meta";
    meta.innerHTML = [
      '<span class="pill ' + pillClass + '">' + htmlEscape(stageLabel) + "</span>",
      '<span class="dot">·</span>',
      "<span>" + htmlEscape(record.customer_name) + "</span>",
      record.industry ? '<span class="dot">·</span><span>' + htmlEscape(record.industry) + "</span>" : "",
      record.timestamp_iso ? '<span class="dot">·</span><span>' + htmlEscape(fmt(record.timestamp_iso)) + "</span>" : "",
    ].join("");

    info.appendChild(title);
    info.appendChild(meta);

    if ((record.attendees || []).length) {
      const ext = record.attendees.filter((a) => a && !String(a).endsWith("@elastic.co"));
      const attendeeMeta = document.createElement("div");
      attendeeMeta.className = "muted small qr-rec-attendees";
      attendeeMeta.textContent =
        ext.length > 0
          ? ext.slice(0, 3).join(", ") + (ext.length > 3 ? " +" + (ext.length - 3) : "")
          : "(internal only)";
      info.appendChild(attendeeMeta);
    }

    li.appendChild(info);

    const actions = document.createElement("div");
    actions.className = "actions";

    if (record.hangout_link) {
      const join = document.createElement("a");
      join.className = "btn ghost";
      join.href = record.hangout_link;
      join.target = "_blank";
      join.rel = "noopener";
      join.textContent = tr("qr.records.action.join", "Join");
      actions.appendChild(join);
    }

    if (record.href) {
      const open = document.createElement("a");
      open.className = "btn ghost";
      open.href = record.href;
      open.textContent = tr("btn.open", "Open");
      actions.appendChild(open);
    }

    if (stageKey === "scheduled") {
      // Trigger Pre-meeting agent via the same endpoint paths app.js uses.
      const cta = document.createElement("button");
      cta.type = "button";
      cta.className = "btn primary";
      cta.textContent = tr("btn.run.pre", "Run Pre-Meeting");
      cta.addEventListener("click", () => runPreMeeting(record, cta));
      actions.appendChild(cta);
    } else if (stageKey === "pre" && record._meeting && !record._is_upcoming) {
      const cta = document.createElement("button");
      cta.type = "button";
      cta.className = "btn";
      cta.textContent = tr("btn.run.post", "Run Post-Meeting");
      cta.addEventListener("click", () => runPostMeeting(record, cta));
      actions.appendChild(cta);
    }

    li.appendChild(actions);
    return li;
  }

  async function runPreMeeting(record, btn) {
    const labelHTML = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> ' + tr("qr.records.action.running", "Running...");
    try {
      const lang = typeof window.claudeLanguageName === "function" ? window.claudeLanguageName() : "English";
      if (record._meeting) {
        await window.apiPost(
          "/agents/pre-meeting/" + encodeURIComponent(record._meeting.id) + "?language=" + encodeURIComponent(lang),
          {}
        );
        if (typeof window.toast === "function") window.toast("Brief generated for " + record.customer_name, "ok");
        window.location.href = "/meeting.html?id=" + encodeURIComponent(record._meeting.id) + "&brief=1";
        return;
      }
      // Calendar source: ad-hoc.
      const ev = record._calendar_event || {};
      const company = (ev.resolution && ev.resolution.company) || {};
      const result = await window.apiPost("/agents/pre-meeting/ad-hoc", {
        company_name: company.name || record.customer_name,
        industry: company.industry || record.industry,
        size: company.size || "",
        tech_stack: ((company.tech_stack && company.tech_stack.observability) || []).join(", "),
        notes: 'Auto-prefilled from calendar event "' + (ev.summary || record.title) + '".',
        meeting_title: ev.summary || record.title,
        language: lang,
      });
      if (typeof window.toast === "function") window.toast("Brief generated for " + record.customer_name, "ok");
      window.location.href = "/meeting.html?id=" + encodeURIComponent(result.meeting_id) + "&adhoc=1";
    } catch (e) {
      if (typeof window.toast === "function") window.toast("Pre-Meeting failed: " + e.message, "bad");
      btn.disabled = false;
      btn.innerHTML = labelHTML;
    }
  }

  async function runPostMeeting(record, btn) {
    if (!record._meeting) return;
    const labelHTML = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> ' + tr("qr.records.action.running", "Running...");
    try {
      const lang = typeof window.claudeLanguageName === "function" ? window.claudeLanguageName() : "English";
      await window.apiPost(
        "/agents/post-meeting/" + encodeURIComponent(record._meeting.id) + "?language=" + encodeURIComponent(lang),
        {}
      );
      if (typeof window.toast === "function") window.toast("Post-meeting result for " + record.customer_name, "ok");
      window.location.href = "/meeting.html?id=" + encodeURIComponent(record._meeting.id) + "&post=1";
    } catch (e) {
      if (typeof window.toast === "function") window.toast("Post-Meeting failed: " + e.message, "bad");
      btn.disabled = false;
      btn.innerHTML = labelHTML;
    }
  }

  function renderGroups(groups, host) {
    host.innerHTML = "";
    groups.forEach((g) => {
      const wrap = document.createElement("section");
      wrap.className = "qr-group";
      wrap.dataset.groupKey = g.key;

      if (STATE.group !== "none") {
        const head = document.createElement("button");
        head.type = "button";
        head.className = "qr-group-head";
        head.setAttribute("aria-expanded", "true");
        head.innerHTML =
          '<span class="qr-group-caret" aria-hidden="true">' +
          '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>' +
          "</span>" +
          '<span class="qr-group-label">' +
          htmlEscape(g.label) +
          "</span>" +
          '<span class="qr-group-count">' +
          g.count +
          "</span>";
        head.addEventListener("click", () => {
          const open = head.getAttribute("aria-expanded") === "true";
          head.setAttribute("aria-expanded", String(!open));
          body.hidden = open;
          wrap.classList.toggle("is-collapsed", open);
        });
        wrap.appendChild(head);
      }

      const body = document.createElement("ul");
      body.className = "meetings qr-rec-list";
      g.items.forEach((r) => body.appendChild(renderCard(r)));
      wrap.appendChild(body);
      host.appendChild(wrap);
    });
  }

  function updateCounter(visible, total) {
    const el = document.getElementById("qr-fb-counter");
    if (!el) return;
    const tpl = tr("qr.filter.counter", "{visible} of {total} records");
    el.textContent = tpl.replace("{visible}", visible).replace("{total}", total);
  }

  function render() {
    const host = document.getElementById("qr-records-host");
    const empty = document.getElementById("qr-records-empty");
    if (!host) return;

    const filtered = applyFilters(STATE.records);
    updateCounter(filtered.length, STATE.records.length);

    if (!filtered.length) {
      host.innerHTML = "";
      if (empty) empty.hidden = false;
      return;
    }
    if (empty) empty.hidden = true;

    if (STATE.view === "kanban") {
      renderKanban(filtered, host);
    } else {
      const groups = groupRecords(filtered, STATE.group);
      renderGroups(groups, host);
    }
  }

  // Kanban: 4 columns (Scheduled, Pre-meeting, Post-meeting, Transcript)
  // plus an "Other" column when something does not fit, each column lists
  // records sorted by timestamp desc. Customer name is the headline; stage
  // pill is implied by column. Click drills into the same href the list
  // card uses.
  function renderKanban(records, host) {
    host.innerHTML = "";
    const board = document.createElement("div");
    board.className = "qr-kanban";
    const cols = ["scheduled", "pre", "post", "transcript", "other"];
    const map = new Map();
    cols.forEach((c) => map.set(c, []));
    records.forEach((r) => {
      const k = map.has(r.stage) ? r.stage : "other";
      map.get(k).push(r);
    });
    cols.forEach((c) => {
      const list = map.get(c).slice().sort(byTimeDesc);
      // Hide empty Other column to reduce noise.
      if (c === "other" && list.length === 0) return;
      const col = document.createElement("section");
      col.className = "qr-kan-col";
      col.dataset.stage = c;
      const head = document.createElement("header");
      head.className = "qr-kan-head";
      head.innerHTML =
        '<span class="qr-kan-title">' +
        htmlEscape(tr(STAGE_LABELS_KEY[c] || ("qr.records.group." + c), STAGE_LABELS_FALLBACK[c] || c)) +
        '</span><span class="qr-kan-count">' + list.length + '</span>';
      col.appendChild(head);
      const body = document.createElement("div");
      body.className = "qr-kan-body";
      if (!list.length) {
        const e = document.createElement("div");
        e.className = "qr-kan-empty";
        e.textContent = tr("qr.kanban.empty", "Nothing here");
        body.appendChild(e);
      } else {
        list.forEach((r) => body.appendChild(renderKanCard(r)));
      }
      col.appendChild(body);
      board.appendChild(col);
    });
    host.appendChild(board);
  }

  function renderKanCard(record) {
    const a = document.createElement("a");
    a.className = "qr-kan-card";
    a.href = record.href || "#";
    if (record.target) a.target = record.target;
    if (record.rel) a.rel = record.rel;
    const title = record.customer_name || record.title || tr("qr.records.untitled", "Untitled");
    const subtitle = record.title && record.title !== title ? record.title : (record.industry || "");
    const when = record.timestamp_iso ? new Date(record.timestamp_iso) : null;
    const whenStr = when && !isNaN(when.getTime()) ? when.toLocaleDateString(undefined, { month: "short", day: "numeric" }) : "";
    a.innerHTML =
      '<div class="qr-kan-card-title">' + htmlEscape(title) + '</div>' +
      (subtitle ? '<div class="qr-kan-card-sub">' + htmlEscape(subtitle) + '</div>' : '') +
      '<div class="qr-kan-card-meta">' +
      (whenStr ? '<span class="qr-kan-card-date">' + htmlEscape(whenStr) + '</span>' : '') +
      (record.attendees && record.attendees.length ? '<span class="qr-kan-card-att">' + record.attendees.length + '</span>' : '') +
      '</div>';
    return a;
  }

  // -------------------------------------------------------------------------
  // Wiring
  // -------------------------------------------------------------------------

  function debounce(fn, ms) {
    let timer = null;
    return function (...args) {
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => fn.apply(this, args), ms);
    };
  }

  function bindControls() {
    // View toggle (Kanban / List). Persists in localStorage.
    document.querySelectorAll('[data-qr-view]').forEach((btn) => {
      const v = btn.getAttribute("data-qr-view");
      if (v === STATE.view) btn.classList.add("is-active");
      btn.addEventListener("click", () => {
        if (STATE.view === v) return;
        STATE.view = v;
        saveViewPref();
        document.querySelectorAll('[data-qr-view]').forEach((b) => {
          b.classList.toggle("is-active", b.getAttribute("data-qr-view") === v);
          b.setAttribute("aria-pressed", String(b.getAttribute("data-qr-view") === v));
        });
        // The Group-by control is irrelevant in kanban mode (the columns
        // ARE the grouping). Disable it visually but keep the value so the
        // user's preference is preserved when switching back to list.
        const groupSel = document.getElementById("qr-fb-group");
        if (groupSel) {
          groupSel.disabled = v === "kanban";
        }
        render();
      });
    });

    const search = document.getElementById("qr-fb-search");
    const clear = document.querySelector(".qr-fb-search-clear");
    if (search) {
      const onChange = debounce(() => {
        STATE.query = search.value || "";
        if (clear) clear.hidden = !STATE.query;
        render();
      }, 150);
      search.addEventListener("input", onChange);
    }
    if (clear) {
      clear.addEventListener("click", () => {
        if (search) {
          search.value = "";
          STATE.query = "";
          search.focus();
        }
        clear.hidden = true;
        render();
      });
    }

    document.querySelectorAll('input[name="qr-stage"]').forEach((radio) => {
      radio.addEventListener("change", () => {
        if (radio.checked) {
          STATE.stage = radio.value;
          render();
        }
      });
    });

    const groupSel = document.getElementById("qr-fb-group");
    if (groupSel) {
      groupSel.value = STATE.group;
      groupSel.addEventListener("change", () => {
        STATE.group = groupSel.value || "stage";
        render();
      });
    }

    const rangeSel = document.getElementById("qr-fb-range");
    if (rangeSel) {
      rangeSel.value = STATE.range;
      rangeSel.addEventListener("change", () => {
        STATE.range = rangeSel.value || "all";
        render();
      });
    }
  }

  function hideLegacySections() {
    // The legacy scattered sections still get populated by app.js so the rest
    // of the page (stat tiles, history counts) keeps working. We just hide
    // their host <section> tags so the unified list is the only thing the FE
    // sees.
    [
      "calendar-list",
      "upcoming",
      "past",
      "history",
    ].forEach((id) => {
      const node = document.getElementById(id);
      if (!node) return;
      const section = node.closest("section");
      if (section) section.classList.add("qr-legacy-hidden");
    });
  }

  async function refresh() {
    try {
      STATE.records = await fetchAll();
      render();
    } catch (e) {
      // non-fatal; legacy sections remain visible if hydrate failed earlier.
    }
  }

  // Read persisted view preference before first render.
  loadViewPref();

  async function hydrate() {
    if (STATE.hydrated) return;
    STATE.hydrated = true;
    bindControls();
    hideLegacySections();
    await refresh();
  }

  // Public surface.
  window.QRFilter = { hydrate, refresh };

  // Auto-hydrate after app.js runs its initial loaders. We wait for the
  // window load event so the legacy data fetches finish first - that way if
  // QRFilter fails for any reason, the legacy sections are still populated as
  // a fallback before we hide them.
  function autoBoot() {
    setTimeout(hydrate, 250);
  }
  if (document.readyState === "complete") autoBoot();
  else window.addEventListener("load", autoBoot, { once: true });
})();
