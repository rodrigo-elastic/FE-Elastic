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

  // Stage taxonomy. Quick Research is its own stage (first-call ad-hoc
   // brief, no scheduled meeting yet) and renders in a distinct violet so a
  // FE can tell it apart from a recurring pre-meeting brief at-a-glance.
  const STAGE_ORDER = ["quickresearch", "scheduled", "pre", "post", "transcript", "other"];
  const STAGE_LABELS_KEY = {
    quickresearch: "qr.records.group.quickresearch",
    scheduled: "qr.records.group.scheduled",
    pre: "qr.records.group.pre",
    post: "qr.records.group.post",
    transcript: "qr.records.group.transcript",
    other: "qr.records.group.other",
  };
  const STAGE_LABELS_FALLBACK = {
    quickresearch: "Quick Research (first call)",
    scheduled: "Scheduled",
    pre: "Pre-meeting",
    post: "Post-meeting",
    transcript: "Transcript",
    other: "Other",
  };
  const STAGE_PILL_CLASS = {
    quickresearch: "violet",
    scheduled: "upcoming",
    pre: "teal",
    post: "blue",
    transcript: "pink",
    other: "",
  };

  // Workspace mode: detected via body.workspace-page (set by workspace.html).
  // The new canonical view is "workspace" (one card per customer with a
  // horizontal timeline). Legacy /quick-research and /customers redirects fall
  // back to the kanban default. The stage filter switches from a single radio
  // (legacy) to multi-select checkboxes in workspace mode.
  function isWorkspaceMode() {
    try {
      return document.body && document.body.classList.contains("workspace-page");
    } catch (_e) {
      return false;
    }
  }

  // Single source of truth for the most recent normalized records. Refresh
  // rebuilds this; render uses it directly so we never need a re-fetch on a
  // filter or group change.
  const STATE = {
    records: [],
    query: "",
    stage: "all",
    // Multi-stage filter (workspace mode). All stages enabled by default;
    // unchecking a chip hides that color of dot from the timeline.
    stageMulti: { quickresearch: true, scheduled: true, pre: true, post: true, transcript: true, other: true },
    range: "all",
    group: "stage",
    // workspace.html boots into "workspace" view. Legacy callers (quick-research,
    // customers redirect) keep "kanban" as the default.
    view: isWorkspaceMode() ? "workspace" : "kanban",
    expandedCustomers: new Set(),
    hydrated: false,
  };

  function viewPrefKey() {
    return isWorkspaceMode() ? "fec.workspace.view" : "fec.customers.view";
  }
  function loadViewPref() {
    try {
      const v = localStorage.getItem(viewPrefKey());
      if (isWorkspaceMode()) {
        if (v === "list" || v === "workspace") STATE.view = v;
      } else if (v === "list" || v === "kanban") {
        STATE.view = v;
      }
    } catch (_e) { /* ignore */ }
  }
  function saveViewPref() {
    try { localStorage.setItem(viewPrefKey(), STATE.view); } catch (_e) {}
  }

  function tr(key, fallback) {
    if (typeof window.t === "function") return window.t(key, fallback);
    return fallback || key;
  }

  function safeApiGet(path) {
    // Prefer the retry wrapper when present: the QR view fans out three
    // parallel reads (calendar, meetings, briefs) and a single transient 503
    // used to blank one of the three columns. With apiGetWithRetry we
    // re-attempt 502/503/504 with 1s/2s/4s backoff. silent: true so a partial
    // failure renders as an empty group rather than three toasts.
    if (typeof window.apiGetWithRetry === "function") {
      return window.apiGetWithRetry(path, { category: "compute", silent: true, label: "QR " + path }).catch(() => null);
    }
    if (typeof window.apiGet !== "function") return Promise.reject(new Error("apiGet missing"));
    return window.apiGet(path).catch(() => null);
  }

  // Stable per-customer color so the same customer reads as the same color
  // across stages (Scheduled, Pre-meeting, Post-meeting, Transcript). Hash
  // the customer_id (or fallback to customer_name lowercased) into 0..9 and
  // let CSS map [data-customer-color] to a hue. 10 distinct hues is enough
  // to keep visually distinct tags for typical FE portfolios; collisions are
  // acceptable in larger lists since the customer name is also rendered.
  const CUSTOMER_COLOR_BUCKETS = 10;
  function customerColorIndex(record) {
    const seed = String(record.customer_id || record.customer_name || "").toLowerCase().trim();
    if (!seed) return 0;
    let h = 0;
    for (let i = 0; i < seed.length; i++) {
      h = (h * 31 + seed.charCodeAt(i)) | 0;
    }
    return Math.abs(h) % CUSTOMER_COLOR_BUCKETS;
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
    // Each normalize* may return null (defensive guard against malformed
    // payloads). Filter them before pushing instead of relying on the
    // sanitizer to drop null records.
    calItems.forEach((ev) => {
      const rec = normalizeCalendar(ev);
      if (rec) records.push(rec);
    });
    mtgItems.forEach((m) => {
      const rec = normalizeMeeting(m, briefByMeeting, postByMeeting);
      if (rec) records.push(rec);
    });

    // Briefs whose meeting_id we did NOT already render (ad-hoc briefs and
    // transcript-only post-meeting artifacts) become standalone history rows.
    const meetingIds = new Set(
      mtgItems
        .map((m) => (m && typeof m.id === "string" ? m.id : null))
        .filter(Boolean)
    );
    briefItems.forEach((b) => {
      if (!b || typeof b !== "object") return;
      const id = b.meeting_id || b.id;
      if (!id || meetingIds.has(id)) return;
      const rec = normalizeBrief(b);
      if (rec) records.push(rec);
    });

    return sanitizeRecords(records);
  }

  // -------------------------------------------------------------------------
  // Sanitizer: drops system / orphan / internal records, keeps only the most
  // recent timestamp when duplicates share the same id, and warns in DevTools
  // so it is easy to verify how many records were filtered.
  //
  // W25A audit hardening: in addition to system prefixes and unresolved
  // customers, also drops records whose id is missing/non-string, whose
  // timestamp is unparseable or pinned to 1970/9999, and whose stage is not
  // one of {scheduled, pre, post, transcript, other}. These guards protect
  // the Kanban from rendering garbage if a backend ever ships a malformed
  // payload.
  // -------------------------------------------------------------------------
  const VALID_STAGES = new Set(STAGE_ORDER);
  const PLACEHOLDER_NAMES = new Set([
    "unresolved",
    "n/a",
    "(unknown)",
    "unknown",
    "placeholder",
    "test",
  ]);

  function hasValidId(record) {
    if (!record) return false;
    const id = record.id;
    if (typeof id !== "string") return false;
    return id.trim().length > 0;
  }

  function hasValidTimestamp(record) {
    // Records without a timestamp are allowed (some briefs lack generated_at);
    // but if a timestamp IS provided, it must parse and not be the unix epoch
    // or year 9999 sentinel.
    if (!record.timestamp_iso) return true;
    const t = new Date(record.timestamp_iso);
    const ms = t.getTime();
    if (isNaN(ms)) return false;
    const year = t.getUTCFullYear();
    if (year <= 1970 || year >= 9999) return false;
    return true;
  }

  function isSystemRecord(record) {
    if (!record || typeof record !== "object") return true;
    const rawId = typeof record.id === "string" ? record.id : "";
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
    // customer_id === "unknown" OR a synthetic stem like "unknown-freemail"
    // (see normalizeCalendar). Drop both: an internal-only meeting or
    // unresolved invite has no place on the Kanban.
    if (!cid) return true;
    if (cid === "unknown") return true;
    if (cid.toLowerCase().startsWith("unknown-")) return true;
    // Tombstone customer name guards.
    if (!cust) return true;
    const lower = cust.toLowerCase();
    if (PLACEHOLDER_NAMES.has(lower)) return true;
    // Tighter than the original /^(unknown|placeholder|test)\b/. Drop only
    // exact matches to "unknown" or "placeholder" prefixes (still reserved
    // for system records). User-typed names like "Test Co" or "Testflight"
    // are legitimate and must not be filtered.
    if (/^(unknown|placeholder)\b/.test(lower)) return true;
    // Stage must be one of the known buckets.
    if (!VALID_STAGES.has(record.stage)) return true;
    // Title must be non-empty after trim.
    if (!title.trim()) return true;
    return false;
  }

  function sanitizeRecords(records) {
    const dropped = [];
    const kept = [];
    if (!Array.isArray(records)) return [];
    records.forEach((r) => {
      // First gate: id MUST be a non-empty string. Records without a stable
      // id cannot be deduped and must not enter the pipeline.
      if (!hasValidId(r)) {
        dropped.push(r);
        return;
      }
      // Second gate: timestamp parses (or is intentionally absent). Year
      // 1970/9999 sentinels and NaN are dropped instead of silently rendering
      // as "Jan 1 1970".
      if (!hasValidTimestamp(r)) {
        dropped.push(r);
        return;
      }
      // Third gate: customer / stage / title checks.
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

  // Coerce a raw attendees list (which may contain strings, objects with an
  // `email` field, or junk) into a clean array of email-like strings. Anything
  // that doesn't yield a string survives as an object so downstream code (the
  // attendee strip) can still inspect it; null / undefined entries are
  // dropped.
  function normalizeAttendees(raw) {
    if (!Array.isArray(raw)) return [];
    return raw
      .map((a) => {
        if (a == null) return null;
        if (typeof a === "string") return a;
        if (typeof a === "object" && typeof a.email === "string") return a.email;
        return null;
      })
      .filter((s) => typeof s === "string" && s.length > 0);
  }

  function normalizeCalendar(ev) {
    if (!ev || typeof ev !== "object") return null;
    const r = ev.resolution || {};
    const company = r.company || {};
    const start = (ev.start && ev.start.dateTime) || null;
    // Without a stable event id we cannot dedupe later, so drop the record
    // outright instead of inventing a random id that breaks dedup contracts.
    const evId = typeof ev.id === "string" && ev.id.trim() ? ev.id.trim() : null;
    if (!evId) return null;
    return {
      id: "cal:" + evId,
      title: (typeof ev.summary === "string" && ev.summary.trim())
        ? ev.summary
        : tr("qr.records.untitled", "(untitled event)"),
      customer_name: (typeof company.name === "string" && company.name.trim())
        ? company.name
        : tr("qr.records.unknown_customer", "Unresolved"),
      customer_id: (typeof company.id === "string" && company.id.trim()) ? company.id : "unknown",
      industry: (typeof company.industry === "string") ? company.industry : "",
      stage: "scheduled",
      timestamp_iso: start,
      source: "calendar",
      attendees: normalizeAttendees(ev.attendees),
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
    if (!m || typeof m !== "object") return null;
    // Meetings without an id cannot drive the Pre/Post agent calls (which
    // build URLs from m.id). Drop early instead of producing
    // /agents/post-meeting/null on click.
    const mtgId = typeof m.id === "string" && m.id.trim() ? m.id.trim() : null;
    if (!mtgId) return null;
    const hasPost = postMap && typeof postMap.has === "function" ? postMap.has(mtgId) : false;
    const hasBrief = briefMap && typeof briefMap.has === "function" ? briefMap.has(mtgId) : false;
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
      id: "mtg:" + mtgId,
      title: (typeof m.title === "string" && m.title.trim()) ? m.title : "(untitled)",
      customer_name: (typeof m.company_name === "string" && m.company_name.trim())
        ? m.company_name
        : "(unknown)",
      customer_id: (typeof m.company_id === "string" && m.company_id.trim()) ? m.company_id : "unknown",
      industry: (typeof m.company_industry === "string") ? m.company_industry : "",
      stage,
      timestamp_iso: m.start_time || null,
      source,
      attendees: normalizeAttendees(m.attendees),
      hangout_link: null,
      brief_id: hasBrief ? mtgId : null,
      post_meeting_id: hasPost ? mtgId : null,
      href: "/meeting.html?id=" + encodeURIComponent(mtgId) + (hasPost ? "&post=1" : ""),
      _meeting: m,
      _is_upcoming: !!m.is_upcoming,
    };
  }

  function normalizeBrief(b) {
    if (!b || typeof b !== "object") return null;
    // A brief without a stable meeting_id (or fallback id) cannot be opened
    // by /meeting.html?id=... and would generate /meeting.html?id=null on
    // click. Drop instead of inventing a random id.
    const briefKey = (typeof b.meeting_id === "string" && b.meeting_id.trim())
      ? b.meeting_id.trim()
      : ((typeof b.id === "string" && b.id.trim()) ? b.id.trim() : null);
    if (!briefKey) return null;
    const isPost = b.type === "post_meeting";
    // Quick Research: ad-hoc pre-meeting brief without a real scheduled
    // meeting. The backend marks these with `ad_hoc=true` and a meeting_id
    // starting with "ad-hoc-". We give them their own stage + colour so a
    // FE can see at-a-glance which entries are first-call discovery vs a
    // recurring brief on a known account.
    const isQuickResearch = !isPost && (b.ad_hoc === true ||
      String(b.meeting_id || b.id || "").startsWith("ad-hoc-"));
    let stage;
    if (isQuickResearch) stage = "quickresearch";
    else if (isPost) stage = "post";
    else stage = "pre";
    // Transcript-only artifacts come back with company_id starting with
    // "transcript-" - flag them as 'transcript' stage so the dedicated
    // group is meaningful.
    // The backend writes transcript-only artifacts with meeting_id starting
    // with "transcript-" while company_id stays the actual slugified customer.
    // Check both so transcript artifacts land in the dedicated Kanban column.
    const transcriptIdHit = String(b.meeting_id || b.id || "").startsWith("transcript-")
      || String(b.company_id || "").startsWith("transcript-");
    const isTranscript = transcriptIdHit && isPost;
    // Ad-hoc Quick Research briefs come back without company_id but with a
    // company_name. Slugify the name as a fallback id so the sanitizer's
    // "drop unknown customer" rule does not silently hide the user's own
    // briefs from the Customers Kanban.
    const slugFromName = (typeof b.company_name === "string" && b.company_name.trim())
      ? b.company_name.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "")
      : "";
    const resolvedCid = (typeof b.company_id === "string" && b.company_id.trim())
      ? b.company_id.trim()
      : (slugFromName || "unknown");
    return {
      id: "brf:" + briefKey,
      title: (typeof b.headline === "string" && b.headline.trim())
        ? b.headline
        : ((typeof b.summary === "string" && b.summary.trim())
          ? b.summary
          : (isPost ? "Post-meeting analysis" : "Pre-meeting brief")),
      customer_name: (typeof b.company_name === "string" && b.company_name.trim())
        ? b.company_name
        : ((typeof b.company_id === "string" && b.company_id.trim()) ? b.company_id : "(unknown)"),
      customer_id: resolvedCid,
      industry: (typeof b.industry === "string") ? b.industry : "",
      stage: isTranscript ? "transcript" : stage,
      timestamp_iso: b.generated_at || null,
      source: isPost ? "post" : "brief",
      attendees: [],
      hangout_link: null,
      brief_id: !isPost ? briefKey : null,
      post_meeting_id: isPost ? briefKey : null,
      href: "/meeting.html?id=" + encodeURIComponent(briefKey) + (isPost ? "&post=1" : ""),
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
    const useMulti = isWorkspaceMode();
    return records.filter((r) => {
      if (useMulti) {
        // In workspace mode, the stage filter is multi-select. A record is
        // shown if its stage chip is checked. Records with an unmapped stage
        // fall through the "other" bucket toggle.
        const k = STAGE_ORDER.includes(r.stage) ? r.stage : "other";
        if (!STATE.stageMulti[k]) return false;
      } else if (STATE.stage !== "all" && r.stage !== STATE.stage) {
        return false;
      }
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
    li.dataset.customerColor = String(customerColorIndex(record));

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
      const safe = (typeof window.sanitizeError === "function") ? window.sanitizeError(e) : (e && e.message) || "unknown error";
      if (typeof window.toast === "function") window.toast("Pre-Meeting failed: " + safe, "bad");
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
      const safe = (typeof window.sanitizeError === "function") ? window.sanitizeError(e) : (e && e.message) || "unknown error";
      if (typeof window.toast === "function") window.toast("Post-Meeting failed: " + safe, "bad");
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

    if (STATE.view === "workspace") {
      renderWorkspace(filtered, host);
    } else if (STATE.view === "kanban") {
      renderKanban(filtered, host);
    } else {
      // List view: in workspace mode, "Group by Customer" is the implicit
      // default (one section per customer, chronological); on legacy pages we
      // honor the user-selected STATE.group.
      const groupKey = isWorkspaceMode() ? "customer" : STATE.group;
      const groups = groupRecords(filtered, groupKey);
      renderGroups(groups, host);
    }
  }

  // -------------------------------------------------------------------------
  // Workspace view: one card per customer with a horizontal timeline.
  // Each artifact (brief, post-meeting, transcript, scheduled meeting) is a
  // dot positioned by date; color codes the stage. Click a dot to navigate to
  // the artifact. Click the card chrome to expand a chronological detail
  // panel beneath the timeline. -----------------------------------------
  function renderWorkspace(records, host) {
    host.innerHTML = "";
    if (!records.length) return;

    // Group by customer (stable id, fallback to name).
    const customerMap = new Map();
    records.forEach((r) => {
      const key = String(r.customer_id || r.customer_name || "_unresolved").toLowerCase();
      if (!customerMap.has(key)) {
        customerMap.set(key, {
          key,
          name: r.customer_name || tr("qr.records.unknown_customer", "Unresolved"),
          industry: r.industry || "",
          colorIdx: customerColorIndex(r),
          items: [],
        });
      }
      customerMap.get(key).items.push(r);
    });

    // Sort customers alphabetically; sort each customer's items by time asc
    // (oldest first, so the timeline reads left to right by default).
    const customers = Array.from(customerMap.values())
      .map((c) => ({
        ...c,
        items: c.items.slice().sort((a, b) => byTimeAsc(a, b)),
      }))
      .sort((a, b) => a.name.localeCompare(b.name));

    const grid = document.createElement("div");
    grid.className = "qr-customer-grid";
    customers.forEach((c) => grid.appendChild(renderCustomerCard(c)));
    host.appendChild(grid);
  }

  function byTimeAsc(a, b) {
    const ta = a.timestamp_iso ? new Date(a.timestamp_iso).getTime() : 0;
    const tb = b.timestamp_iso ? new Date(b.timestamp_iso).getTime() : 0;
    return ta - tb;
  }

  function stageDotI18n(stage) {
    if (stage === "scheduled") return tr("workspace.dot.scheduled", "Scheduled");
    if (stage === "pre") return tr("workspace.dot.brief", "Pre-meeting brief");
    if (stage === "post") return tr("workspace.dot.post", "Post-meeting summary");
    if (stage === "transcript") return tr("workspace.dot.transcript", "Transcript");
    return tr(STAGE_LABELS_KEY[stage] || "qr.records.group.other", STAGE_LABELS_FALLBACK[stage] || "Other");
  }

  function renderCustomerCard(customer) {
    const card = document.createElement("article");
    card.className = "qr-customer-card";
    card.dataset.customerColor = String(customer.colorIdx);

    // Header row: name + industry pill + counts summary.
    const head = document.createElement("header");
    head.className = "qr-customer-head";

    const tag = document.createElement("span");
    tag.className = "qr-customer-tag";
    tag.setAttribute("aria-hidden", "true");

    const name = document.createElement("h3");
    name.className = "qr-customer-name";
    name.textContent = customer.name;

    const industry = document.createElement("span");
    industry.className = "qr-customer-industry";
    industry.textContent = customer.industry || "";

    head.appendChild(tag);
    head.appendChild(name);
    if (customer.industry) head.appendChild(industry);

    // Right side: stacked counts so the FE knows what is in this card at a
    // glance without expanding it. Template: "{n} briefs . {m} post-meetings . {k} transcripts"
    const briefCount = customer.items.filter((r) => r.stage === "pre").length;
    const postCount = customer.items.filter((r) => r.stage === "post").length;
    const trCount = customer.items.filter((r) => r.stage === "transcript").length;
    const schedCount = customer.items.filter((r) => r.stage === "scheduled").length;

    const counts = document.createElement("span");
    counts.className = "qr-customer-counts";
    const tpl = tr(
      "workspace.card.counts",
      "{n} briefs . {m} post-meetings . {k} transcripts"
    );
    counts.textContent = tpl
      .replace("{n}", String(briefCount))
      .replace("{m}", String(postCount))
      .replace("{k}", String(trCount));
    head.appendChild(counts);

    card.appendChild(head);

    // Timeline: full-width strip with a horizontal axis and one dot per
    // artifact, positioned by date along the customer's min..max range.
    card.appendChild(renderTimeline(customer));

    // Footer mini-meta (totals + scheduled hint).
    const foot = document.createElement("div");
    foot.className = "qr-customer-foot";
    const total = customer.items.length;
    const totalLabel = tr("workspace.card.total", "{n} artifacts");
    const totalSpan = document.createElement("span");
    totalSpan.className = "qr-customer-foot-total";
    totalSpan.textContent = totalLabel.replace("{n}", String(total));
    foot.appendChild(totalSpan);

    if (schedCount > 0) {
      const schedSpan = document.createElement("span");
      schedSpan.className = "qr-customer-foot-sched";
      const schedTpl = tr("workspace.card.scheduled", "{n} scheduled");
      schedSpan.textContent = schedTpl.replace("{n}", String(schedCount));
      foot.appendChild(schedSpan);
    }

    const detailBtn = document.createElement("button");
    detailBtn.type = "button";
    detailBtn.className = "qr-customer-detail-toggle";
    detailBtn.setAttribute("aria-expanded", "false");
    detailBtn.textContent = tr("workspace.detail.show", "Show all artifacts");
    foot.appendChild(detailBtn);

    card.appendChild(foot);

    // Detail panel (hidden by default): full chronological list of every
    // artifact for the customer, descending so the most recent activity is on
    // top.
    const detail = document.createElement("div");
    detail.className = "qr-customer-detail";
    detail.hidden = true;
    detail.appendChild(renderDetailList(customer));
    card.appendChild(detail);

    function setExpanded(open) {
      detailBtn.setAttribute("aria-expanded", String(open));
      card.setAttribute("aria-expanded", String(open));
      detail.hidden = !open;
      detailBtn.textContent = open
        ? tr("workspace.detail.hide", "Hide artifacts")
        : tr("workspace.detail.show", "Show all artifacts");
      card.classList.toggle("is-expanded", open);
    }

    detailBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      const open = detailBtn.getAttribute("aria-expanded") === "true";
      setExpanded(!open);
    });

    card.addEventListener("click", (e) => {
      if (e.target.closest("a, button, .qr-customer-detail")) return;
      const open = detailBtn.getAttribute("aria-expanded") === "true";
      setExpanded(!open);
    });

    card.addEventListener("keydown", (e) => {
      if (e.target !== card) return;
      if (e.key !== "Enter" && e.key !== " ") return;
      e.preventDefault();
      const open = detailBtn.getAttribute("aria-expanded") === "true";
      setExpanded(!open);
    });

    card.tabIndex = 0;
    card.setAttribute("role", "button");
    card.setAttribute("aria-expanded", "false");

    return card;
  }

  function renderTimeline(customer) {
    const wrap = document.createElement("div");
    wrap.className = "qr-customer-timeline-wrap";

    const lbl = document.createElement("span");
    lbl.className = "qr-customer-timeline-label";
    lbl.textContent = tr("workspace.timeline.label", "Timeline");
    wrap.appendChild(lbl);

    const tl = document.createElement("div");
    tl.className = "qr-customer-timeline";
    tl.setAttribute("role", "list");

    // Compute date range (min..max). If only one timestamp exists, all dots
    // collapse to the right edge so the customer at least shows "something
    // happened recently" without dividing by zero.
    const stamps = customer.items
      .map((r) => (r.timestamp_iso ? new Date(r.timestamp_iso).getTime() : null))
      .filter((t) => t != null && !isNaN(t));
    let minT = stamps.length ? Math.min.apply(null, stamps) : 0;
    let maxT = stamps.length ? Math.max.apply(null, stamps) : 1;
    if (minT === maxT) {
      // Spread a single-dot range over a 1-day window so the dot lands at
      // the center rather than collapsing.
      maxT = minT + 24 * 60 * 60 * 1000;
    }
    const span = Math.max(1, maxT - minT);

    // Date axis labels (oldest left, newest right).
    const minLbl = document.createElement("span");
    minLbl.className = "qr-customer-timeline-axis qr-axis-min";
    minLbl.textContent = stamps.length ? new Date(minT).toLocaleDateString(undefined, { month: "short", day: "numeric" }) : "";
    tl.appendChild(minLbl);

    const maxLbl = document.createElement("span");
    maxLbl.className = "qr-customer-timeline-axis qr-axis-max";
    maxLbl.textContent = stamps.length ? new Date(maxT).toLocaleDateString(undefined, { month: "short", day: "numeric" }) : "";
    tl.appendChild(maxLbl);

    const track = document.createElement("div");
    track.className = "qr-customer-timeline-track";
    tl.appendChild(track);

    customer.items.forEach((r) => {
      const t = r.timestamp_iso ? new Date(r.timestamp_iso).getTime() : null;
      const pct = t == null || isNaN(t) ? 100 : ((t - minT) / span) * 100;
      const stageKey = STAGE_ORDER.includes(r.stage) ? r.stage : "other";

      const dot = document.createElement("a");
      dot.className = "qr-customer-dot";
      dot.dataset.stage = stageKey;
      dot.setAttribute("role", "listitem");
      dot.style.left = "calc(" + Math.max(0, Math.min(100, pct)).toFixed(2) + "% - 6px)";
      dot.href = r.href || "#";

      const tooltipParts = [stageDotI18n(stageKey), r.title];
      if (r.timestamp_iso) tooltipParts.push(fmt(r.timestamp_iso));
      const tooltip = tooltipParts.filter(Boolean).join(" - ");
      dot.title = tooltip;
      dot.setAttribute("aria-label", tooltip);

      // Tiny visual marker inside the dot (svg circle) to keep the hit target
      // tappable on mobile (40px hit pad via CSS).
      dot.innerHTML = '<span class="qr-customer-dot-mark" aria-hidden="true"></span>';
      track.appendChild(dot);
    });

    wrap.appendChild(tl);
    return wrap;
  }

  function renderDetailList(customer) {
    const ul = document.createElement("ul");
    ul.className = "qr-customer-detail-list";
    const sorted = customer.items.slice().sort(byTimeDesc);

    if (!sorted.length) {
      const li = document.createElement("li");
      li.className = "qr-customer-detail-empty";
      li.textContent = tr("workspace.detail.empty", "No artifacts yet for this customer.");
      ul.appendChild(li);
      return ul;
    }

    const heading = document.createElement("li");
    heading.className = "qr-customer-detail-heading";
    heading.textContent = tr("workspace.detail.title", "All artifacts");
    ul.appendChild(heading);

    sorted.forEach((r) => {
      const li = document.createElement("li");
      li.className = "qr-customer-detail-item";
      const stageKey = STAGE_ORDER.includes(r.stage) ? r.stage : "other";
      li.dataset.stage = stageKey;

      const stageLabel = stageDotI18n(stageKey);
      const dateStr = r.timestamp_iso ? fmt(r.timestamp_iso) : "";

      const a = document.createElement("a");
      a.className = "qr-customer-detail-link";
      a.href = r.href || "#";

      a.innerHTML =
        '<span class="qr-customer-detail-dot" data-stage="' + htmlEscape(stageKey) + '" aria-hidden="true"></span>' +
        '<span class="qr-customer-detail-stage">' + htmlEscape(stageLabel) + "</span>" +
        '<span class="qr-customer-detail-title">' + htmlEscape(r.title || "(untitled)") + "</span>" +
        (dateStr ? '<span class="qr-customer-detail-date">' + htmlEscape(dateStr) + "</span>" : "");
      li.appendChild(a);
      ul.appendChild(li);
    });
    return ul;
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
    a.dataset.customerColor = String(customerColorIndex(record));
    const title = record.customer_name || record.title || tr("qr.records.untitled", "Untitled");
    const subtitle = record.title && record.title !== title ? record.title : (record.industry || "");
    const when = record.timestamp_iso ? new Date(record.timestamp_iso) : null;
    const whenStr = when && !isNaN(when.getTime()) ? when.toLocaleDateString(undefined, { month: "short", day: "numeric" }) : "";
    a.innerHTML =
      '<div class="qr-kan-card-title"><span class="qr-kan-dot" aria-hidden="true"></span>' + htmlEscape(title) + '</div>' +
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
    const workspaceMode = isWorkspaceMode();

    // View toggle (Workspace/Kanban + List). Persists in localStorage.
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
        // The Group-by control is irrelevant in kanban / workspace mode (the
        // columns or customer cards ARE the grouping). Disable it visually
        // but keep the value so the user's preference is preserved when
        // switching back to list.
        const groupSel = document.getElementById("qr-fb-group");
        if (groupSel) {
          groupSel.disabled = v !== "list";
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

    if (workspaceMode) {
      // Multi-select chip filter (checkboxes). Toggling hides that color of
      // dot from every customer timeline.
      document.querySelectorAll('input[name="qr-stage-multi"]').forEach((cb) => {
        cb.addEventListener("change", () => {
          const k = cb.value;
          if (k in STATE.stageMulti) STATE.stageMulti[k] = !!cb.checked;
          render();
        });
      });
    } else {
      // Legacy single-select stage radio (kept so /quick-research and the
      // /customers redirect both keep working unchanged).
      document.querySelectorAll('input[name="qr-stage"]').forEach((radio) => {
        radio.addEventListener("change", () => {
          if (radio.checked) {
            STATE.stage = radio.value;
            render();
          }
        });
      });
    }

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
