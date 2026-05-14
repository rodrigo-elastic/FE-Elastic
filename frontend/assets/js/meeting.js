/*
  filename: meeting.js
  description: Per-meeting view. Tabs with fade, skeleton placeholders during agent runs, print button for the brief.
  Author: Rodrigo Careaga
  Date: 03-05-2026
*/
const meetingId = getQueryParam("id");
const showBrief = getQueryParam("brief") === "1";
const showPost = getQueryParam("post") === "1";
const isAdHoc = getQueryParam("adhoc") === "1";

let MEETING_DATA = null;

(async function init() {
  applyI18n();
  renderLangPicker(document.getElementById("lang-host"));
  if (!meetingId) {
    setText("meeting-title", "Missing meeting id");
    return;
  }
  try {
    MEETING_DATA = await apiGet(`/meetings/${meetingId}`);
  } catch (e) {
    setText("meeting-title", "Meeting not found");
    return;
  }

  const m = MEETING_DATA.meeting;
  const c = MEETING_DATA.company;
  setText("meeting-title", m.title);

  const meta = document.getElementById("meeting-meta");
  clear(meta);
  if (isAdHoc) meta.appendChild(el("span", { class: "pill pink" }, "Ad-hoc"));
  else meta.appendChild(el("span", { class: "pill " + (isUpcoming(m) ? "upcoming" : "past") }, isUpcoming(m) ? "Upcoming" : "Past"));
  meta.appendChild(textNode(" · "));
  meta.appendChild(el("strong", {}, c.name || "Unknown company"));
  if (c.industry) {
    meta.appendChild(textNode(" · "));
    meta.appendChild(textNode(`${c.industry}${c.size ? ", " + c.size : ""}`));
  }
  if (m.start_time) {
    meta.appendChild(textNode(" · "));
    meta.appendChild(textNode(fmtDate(m.start_time)));
  }

  setupTabs();
  renderContext();
  renderTranscript();
  await renderJourneyHeader(c.id);
  await maybeAutoLoad();
  bindActions();
  await mountAgentBuilderMinis();
})();

// ============================================================ Agent Builder mini embeds

// Lightweight base preamble used as a header on every tab. Tab-specific data
// (brief sections, post-meeting MEDDPICC, competitors, transcript turns) is
// appended below this in the per-tab preambles.
function buildBaseContext() {
  const c = MEETING_DATA.company || {};
  const m = MEETING_DATA.meeting || {};
  const stack = c.tech_stack || {};
  const lines = [
    `Meeting: ${m.title || "(untitled)"} · ${m.start_time ? fmtDate(m.start_time) : "no date"}`,
    `Company: ${c.name || "?"}${c.industry ? ` · ${c.industry}` : ""}${c.size ? `, ${c.size}` : ""}`,
  ];
  if (c.description) lines.push(`Description: ${c.description.slice(0, 240)}`);
  const stackParts = [];
  if (stack.observability?.length) stackParts.push(`obs=${stack.observability.slice(0, 4).join(", ")}`);
  if (stack.search?.length) stackParts.push(`search=${stack.search.slice(0, 4).join(", ")}`);
  if (stack.cloud?.length) stackParts.push(`cloud=${stack.cloud.slice(0, 4).join(", ")}`);
  if (stack.siem?.length) stackParts.push(`siem=${stack.siem.slice(0, 4).join(", ")}`);
  if (stackParts.length) lines.push(`Stack: ${stackParts.join(" · ")}`);
  return lines.join("\n");
}

function summariseBriefForPreamble(brief) {
  if (!brief || !brief.sections) return "";
  const blocks = [`### Pre-meeting brief`, `Headline: ${(brief.headline || "").slice(0, 240)}`];
  brief.sections.slice(0, 6).forEach((s) => {
    const bullets = (s.bullets || []).slice(0, 3).map((b) => "- " + String(b).slice(0, 200));
    if (bullets.length) blocks.push(`**${s.heading}**\n${bullets.join("\n")}`);
  });
  return blocks.join("\n");
}

function summarisePostForPreamble(post) {
  if (!post) return "";
  const blocks = [`### Post-meeting record`];
  if (post.summary) blocks.push(`Summary: ${String(post.summary).slice(0, 360)}`);
  if (Array.isArray(post.meddpicc_signals) && post.meddpicc_signals.length) {
    const items = post.meddpicc_signals.slice(0, 8).map((s) =>
      `- [${s.category || "?"}] "${String(s.quote || "").slice(0, 160)}"${s.note ? ` (${String(s.note).slice(0, 120)})` : ""}`
    );
    blocks.push(`**MEDDPICC signals captured (${post.meddpicc_signals.length} total):**\n${items.join("\n")}`);
  }
  if (Array.isArray(post.competitor_mentions) && post.competitor_mentions.length) {
    const items = post.competitor_mentions.map((c) =>
      `- ${c.competitor || "?"}: "${String(c.context || "").slice(0, 200)}"`
    );
    blocks.push(`**Competitor mentions in this meeting (${post.competitor_mentions.length}):**\n${items.join("\n")}`);
  } else {
    blocks.push("**Competitor mentions:** none detected by the post-meeting agent.");
  }
  if (Array.isArray(post.action_items) && post.action_items.length) {
    const items = post.action_items.slice(0, 6).map((a) =>
      `- ${a.title || "?"} (owner: ${a.owner_name || "?"}${a.due_date ? `, due ${a.due_date}` : ""})`
    );
    blocks.push(`**Action items (${post.action_items.length}):**\n${items.join("\n")}`);
  }
  return blocks.join("\n\n");
}

function summariseTranscriptForPreamble(turns, max = 8) {
  if (!turns || !turns.length) return "";
  const tail = turns.slice(-max).map((t) => `${t.speaker || "?"}: ${String(t.text || "").slice(0, 240)}`);
  return `### Last ${tail.length} transcript turns\n${tail.join("\n")}`;
}

function summariseContextForPreamble() {
  const news = (MEETING_DATA.news || []).slice(0, 4).map((n) => `- ${n.title || ""} (${n.source || ""}${n.published_at ? `, ${fmtDate(n.published_at)}` : ""})`);
  const tickets = (MEETING_DATA.tickets || []).slice(0, 4).map((t) => `- [${t.priority || "?"}] ${t.subject || ""} (${t.status || "?"})`);
  const lines = [];
  if (news.length) lines.push(`### Recent news\n${news.join("\n")}`);
  if (tickets.length) lines.push(`### Open tickets\n${tickets.join("\n")}`);
  return lines.join("\n\n");
}

async function loadMeetingArtifacts() {
  // Best-effort: pull brief + post records so per-tab preambles can include
  // them. Both are small JSON files; failures fall back to empty objects so
  // the chat still works without them.
  let brief = null, post = null;
  try { brief = await apiGet(`/briefs/${meetingId}`); } catch (_) {}
  if (brief && brief.exists === false) brief = null;
  try { post = await apiGet(`/briefs/${meetingId}/post`); } catch (_) {}
  if (post && post.exists === false) post = null;
  return { brief, post };
}

async function mountAgentBuilderMinis() {
  if (!window.AgentBuilderMini) return;
  const c = MEETING_DATA.company || {};
  const m = MEETING_DATA.meeting || {};
  const baseContext = buildBaseContext();
  const ctxLabel = `${c.name || "account"} · ${m.title?.slice(0, 28) || "meeting"}`;

  const { brief, post } = await loadMeetingArtifacts();
  const briefSummary = summariseBriefForPreamble(brief);
  const postSummary = summarisePostForPreamble(post);
  const transcriptSummary = summariseTranscriptForPreamble((MEETING_DATA.transcript || {}).turns || []);
  const contextExtras = summariseContextForPreamble();

  // Brief tab: pre-meeting prep. Includes the brief headline + section bullets
  // so questions about pain, signals, sources can be answered with grounded data.
  const briefHost = document.getElementById("abm-brief");
  if (briefHost) {
    const preamble = [
      baseContext,
      briefSummary,
      "Use this context to help me prepare for the meeting. Cite the brief where useful.",
    ].filter(Boolean).join("\n\n");
    AgentBuilderMini.mount(briefHost, {
      title: "Field Assistant · Pre-meeting",
      contextLabel: ctxLabel,
      contextPreamble: preamble,
      storageKey: `fec.ab.brief.v2.${meetingId}`,
      suggestions: [
        { label: "Top 5 questions to ask", prompt: "What are the top 5 discovery questions I should ask this account in the meeting? Anchor them to MEDDPICC and reference the pain points already captured in the brief above." },
        { label: "POV plan outline", prompt: "Sketch a 6-week Proof-of-Value plan tailored to this account, grounded in the pain points and signals from the brief." },
        { label: "Compliance angle", prompt: "Which regulations matter most for this customer (use the company industry above) and how does Elastic map to them?" },
        { label: "TCO at 200 GB/day", prompt: "Run a TCO comparison at 200 GB/day, 12 months retention, current spend $1.5M." },
        { label: "Ask the docs (FE Brain)", prompt: "Use fec_knowledge_search to ask the Elastic docs how Elastic ML jobs handle deployment regression detection, and cite the doc pages. Tie the answer back to this customer's pain points above." },
      ],
    });
  }

  // Post tab: includes the FULL post-meeting record (MEDDPICC, competitors,
  // action items, summary) so questions like "for each competitor mentioned"
  // can be answered without the assistant claiming it lacks the data.
  const postHost = document.getElementById("abm-post");
  if (postHost) {
    const preamble = [
      baseContext,
      postSummary || "_The post-meeting agent has not run yet, so no MEDDPICC, competitor or action-item data is available. Tell the user to run the post-meeting agent first._",
      "The meeting just ended. Help me action the items above. Use the FE Copilot tools where helpful (POC plan, SPL->ES|QL, cost calc, capacity, code sample, compliance, stack extract).",
    ].filter(Boolean).join("\n\n");
    AgentBuilderMini.mount(postHost, {
      title: "Field Assistant · Post-meeting",
      contextLabel: ctxLabel,
      contextPreamble: preamble,
      storageKey: `fec.ab.post.v2.${meetingId}`,
      suggestions: [
        { label: "POV plan from this meeting", prompt: `Build a Proof-of-Value plan based on the post-meeting record for meeting ${meetingId}. Use the fec_poc_plan tool.` },
        { label: "Cost + capacity follow-up", prompt: "If the customer's workload is 150 GB/day at peak 30k EPS, run both the cost calculator and the capacity planner so I can include them in the follow-up email." },
        { label: "Competitor counter-positioning", prompt: "Use the competitor-mentions list above. For each competitor named, give me a one-paragraph counter-positioning anchored on Elastic strengths and the customer's current pain points." },
        { label: "Translate any SPL discussed", prompt: "If the customer mentioned any SPL queries during the meeting (check the MEDDPICC signals and transcript context above), translate them to ES|QL using fec_spl_to_esql." },
        { label: "Ask the docs (FE Brain)", prompt: "Call fec_knowledge_search with the most technical objection from this meeting (read the post-meeting record above) and bring back a cited Elastic-docs answer I can paste into the follow-up email." },
      ],
    });
  }

  // Live tab: includes the last few transcript turns so "what should I say next"
  // works without the assistant asking the rep for the transcript.
  const liveHost = document.getElementById("abm-live");
  if (liveHost) {
    const preamble = [
      baseContext,
      transcriptSummary,
      postSummary,
      "The transcript turns above are the live conversation as it stands. Help me think on my feet. Be concise.",
    ].filter(Boolean).join("\n\n");
    AgentBuilderMini.mount(liveHost, {
      title: "Field Assistant · Live",
      contextLabel: ctxLabel,
      contextPreamble: preamble,
      storageKey: `fec.ab.live.v2.${meetingId}`,
      suggestions: [
        { label: "What should I say next?", prompt: "Given the last few transcript turns above, what is the strongest next question I can ask to advance the deal? Anchor to MEDDPICC." },
        { label: "Pull a battlecard", prompt: "If a competitor was mentioned in the transcript above, give me the 3-bullet counter for them. If multiple, do all of them." },
        { label: "Quick cost ballpark", prompt: "Give me a quick Elastic vs Splunk cost ballpark at 100 GB/day, 6 months. Use fec_cost_calc." },
        { label: "Ask the docs (FE Brain)", prompt: "Use fec_knowledge_search to find the official Elastic docs answer to whatever the customer just asked in the most recent transcript turn. Paste the cited snippet so I can read it back to them." },
      ],
    });
  }

  // Context tab: deeper account research. Uses news + tickets in addition to
  // the company profile so industry questions can pull from real signals.
  const ctxHost = document.getElementById("abm-context");
  if (ctxHost) {
    const preamble = [
      baseContext,
      contextExtras,
      "Use this thread to dig deeper into the account: industry trends, regulatory landscape, competitive context, technical fit.",
    ].filter(Boolean).join("\n\n");
    AgentBuilderMini.mount(ctxHost, {
      title: "Field Assistant · Context",
      contextLabel: ctxLabel,
      contextPreamble: preamble,
      storageKey: `fec.ab.context.v2.${meetingId}`,
      suggestions: [
        { label: "Industry trends", prompt: "What are the top 3 trends in this customer's industry (above) that should shape my Elastic pitch?" },
        { label: "Stack extraction", prompt: `Extract this customer's tech stack into canonical buckets given what we know. Use fec_stack_extract.` },
        { label: "Code sample", prompt: "Give me a Python code sample to bulk-index 1000 web logs into Elasticsearch using ES|QL semantics." },
        { label: "Ask the docs (FE Brain)", prompt: "Use fec_knowledge_search against the Elastic docs corpus to surface the canonical Elastic guidance for this customer's stack (see Stack above). Cite the doc pages so I can share them." },
      ],
    });
  }
}

// Pre-render the transcript inside the Live tab so source-↗ links from any
// signal/force/BANT chip can scroll-to-quote even before "Replay" is clicked.
function renderTranscript() {
  const host = document.getElementById("live");
  if (!host) return;
  if (!MEETING_DATA.transcript || !(MEETING_DATA.transcript.turns || []).length) {
    host.innerHTML = '<p class="muted">No transcript on file for this meeting.</p>';
    return;
  }
  clear(host);
  host.appendChild(
    el("p", { class: "muted small" }, "Source links from signals and forces scroll here. Click \"Replay\" above to layer in live alerts.")
  );
  MEETING_DATA.transcript.turns.forEach((turn, i) => {
    host.appendChild(
      el(
        "div",
        { class: "transcript-turn", "data-turn": String(i), "data-quote": turn.text },
        [el("div", { class: "speaker" }, turn.speaker), el("div", { class: "text" }, turn.text)]
      )
    );
  });
}

// Global handler the viz cards call. Switches to Live tab and scrolls/highlights
// the first transcript turn whose text overlaps the supplied quote.
window.openTranscriptAt = function (quote) {
  const liveTab = document.querySelector('.tab[data-tab="live"]');
  if (liveTab) liveTab.click();
  if (!quote) return;
  const needle = String(quote).toLowerCase().slice(0, 70).trim();
  setTimeout(() => {
    const turns = document.querySelectorAll("#live .transcript-turn");
    let target = null;
    for (const t of turns) {
      const haystack = (t.dataset.quote || "").toLowerCase();
      if (haystack.includes(needle) || needle.includes(haystack.slice(0, 60))) {
        target = t;
        break;
      }
    }
    if (target) {
      target.scrollIntoView({ behavior: "smooth", block: "center" });
      target.classList.add("highlight-flash");
      setTimeout(() => target.classList.remove("highlight-flash"), 2400);
    }
  }, 80);
};

async function renderJourneyHeader(companyId) {
  if (!companyId) return;
  try {
    const all = await apiGet("/meetings");
    const peers = all.filter((m) => m.company_id === companyId);
    if (peers.length < 2) return; // not enough touchpoints to draw a journey
    const host = document.getElementById("journey-host");
    if (host) {
      clear(host);
      host.appendChild(renderJourneyTimeline(peers, meetingId));
    }
  } catch (e) {
    /* ignore */
  }
}

function isUpcoming(m) {
  return new Date(m.start_time) > new Date();
}

// Per-bullet source linking. Tries to match a bullet's text against the news
// titles + ticket subjects in `sources`. When a confident match is found, the
// returned <a> opens the source URL directly; otherwise it scrolls to and
// flashes the Sources Used panel so the user can verify the dossier inputs.
function bulletSourceLink(bullet, sources) {
  if (!sources) return null;
  const text = String(bullet || "").toLowerCase();
  const wordsOf = (s) => String(s || "").toLowerCase().split(/[^a-z0-9$%]+/).filter((w) => w.length >= 4);
  const overlapScore = (a, b) => {
    const setB = new Set(wordsOf(b));
    let hits = 0;
    wordsOf(a).forEach((w) => {
      if (setB.has(w)) hits += 1;
    });
    return hits;
  };

  // News: pick the article with the highest word overlap if it has 2+ matches.
  let best = null;
  let bestScore = 1;
  (sources.news || []).forEach((n) => {
    const score = overlapScore(text, (n.title || "") + " " + (n.summary || ""));
    if (score > bestScore) {
      bestScore = score;
      best = { type: "news", item: n };
    }
  });
  if (best && best.item.url) {
    return el(
      "a",
      {
        class: "bullet-source",
        href: best.item.url,
        target: "_blank",
        rel: "noopener",
        title: `Source: ${best.item.source || "news"} · ${best.item.title || ""}`,
      },
      "↗"
    );
  }

  // Tickets: similar overlap test.
  let bestTicket = null;
  let ticketScore = 1;
  (sources.tickets || []).forEach((t) => {
    const score = overlapScore(text, (t.subject || "") + " " + (t.description || ""));
    if (score > ticketScore) {
      ticketScore = score;
      bestTicket = t;
    }
  });
  if (bestTicket) {
    return el(
      "a",
      {
        class: "bullet-source",
        href: "#sources-panel",
        title: `Source: support ticket [${bestTicket.priority}] ${bestTicket.subject}`,
        onclick: (ev) => {
          ev.preventDefault();
          scrollToSources();
        },
      },
      "↗"
    );
  }

  // Fallback: scroll to the Sources Used panel so the user can verify inputs.
  // Skip when there are no sources at all (would be a dead link).
  if (!sources.news?.length && !sources.tickets?.length && !sources.past_transcripts?.length && !sources.user_input) {
    return null;
  }
  return el(
    "a",
    {
      class: "bullet-source bullet-source-soft",
      href: "#sources-panel",
      title: "Verify against Sources used",
      onclick: (ev) => {
        ev.preventDefault();
        scrollToSources();
      },
    },
    "↗"
  );
}

function scrollToSources() {
  const panel = document.getElementById("sources-panel");
  if (!panel) return;
  panel.setAttribute("open", "");
  panel.scrollIntoView({ behavior: "smooth", block: "start" });
  panel.classList.add("highlight-flash");
  setTimeout(() => panel.classList.remove("highlight-flash"), 2400);
}

// ---------------------------------------------------- Salesforce sync panel

function renderSalesforcePanel(post) {
  const w = post.salesforce_writes || {};
  const acc = w.account || {};
  const opp = w.opportunity || {};
  const note = w.note || {};
  const meddpicc = w.meddpicc || {};
  const competitor = w.competitor || null;
  const dealHealth = w.deal_health || {};
  const slack = w.slack || null;
  const contentDoc = w.content_document || null;

  const sec = el("details", { class: "post-section sfdc-section sfdc-section-rich", open: "" });
  sec.appendChild(
    el("summary", {}, [
      el("h3", { class: "post-section-title blue" }, "Salesforce sync"),
      el("span", { class: "chevron" }, ""),
      el("span", { class: "count" }, "" + (post.salesforce_tasks || []).length),
    ])
  );

  // Header strip with deal health + key IDs
  const dealPct = dealHealth.deal_health_pct != null ? dealHealth.deal_health_pct : 0;
  const headerStrip = el("div", { class: "sfdc-strip" }, [
    el("div", { class: "sfdc-card" }, [
      el("div", { class: "sfdc-card-lbl" }, "Account"),
      el("div", { class: "sfdc-card-val" }, acc.Name || acc.Id || "?"),
      el("div", { class: "sfdc-card-id" }, acc.Id || ""),
      acc.Url ? el("a", { class: "sfdc-link", href: acc.Url, target: "_blank", rel: "noopener" }, "Open ↗") : null,
    ]),
    el("div", { class: "sfdc-card" }, [
      el("div", { class: "sfdc-card-lbl" }, "Opportunity"),
      el("div", { class: "sfdc-card-val" }, opp.Name || opp.Id || "?"),
      el("div", { class: "sfdc-card-id" }, `${opp.Id || ""} · ${opp.StageName || ""}${opp.Amount ? " · $" + opp.Amount.toLocaleString() : ""}`),
      opp.Url ? el("a", { class: "sfdc-link", href: opp.Url, target: "_blank", rel: "noopener" }, "Open ↗") : null,
    ]),
    el("div", { class: "sfdc-card sfdc-card-health" }, [
      el("div", { class: "sfdc-card-lbl" }, "Deal Health"),
      el("div", { class: "sfdc-card-val sfdc-pct" }, dealPct + "%"),
      el("div", { class: "sfdc-bar" }, [el("div", { class: "sfdc-bar-fill", style: `width:${dealPct}%` })]),
      el("div", { class: "sfdc-card-id" }, `${dealHealth.score || 0}/7 MEDDPICC categories`),
    ]),
  ]);
  sec.appendChild(headerStrip);

  // ContentNote
  if (note && note.note_id) {
    sec.appendChild(
      el("div", { class: "sfdc-row-block" }, [
        el("div", { class: "sfdc-lbl" }, "ContentNote created"),
        el("div", { class: "sfdc-row" }, [
          el("span", { class: "sfdc-id" }, note.note_id),
          el("span", { class: "muted small", style: "flex:1" }, " · linked to Opportunity"),
          el("a", { class: "sfdc-link", href: note.url, target: "_blank", rel: "noopener" }, "Open Note ↗"),
        ]),
      ])
    );
  }

  // MEDDPICC field updates
  if (meddpicc && meddpicc.fields_updated && meddpicc.fields_updated.length) {
    const block = el("div", { class: "sfdc-row-block" }, [
      el("div", { class: "sfdc-lbl" }, `MEDDPICC fields updated (${meddpicc.fields_updated.length})`),
    ]);
    const grid = el("div", { class: "sfdc-fields" });
    meddpicc.fields_updated.forEach((f) => {
      grid.appendChild(el("span", { class: "sfdc-field" }, f));
    });
    block.appendChild(grid);
    sec.appendChild(block);
  }

  // Competitor
  if (competitor) {
    sec.appendChild(
      el("div", { class: "sfdc-row-block" }, [
        el("div", { class: "sfdc-lbl" }, "Competitor tracking"),
        el("div", { class: "sfdc-row" }, [
          el("span", { class: "sfdc-comp-primary" }, "Primary: " + competitor.primary),
          competitor.others && competitor.others.length
            ? el("span", { class: "muted small" }, "Others: " + competitor.others.join(", "))
            : null,
        ]),
      ])
    );
  }

  // ContentDocument (PDF)
  if (contentDoc && contentDoc.content_document_id) {
    sec.appendChild(
      el("div", { class: "sfdc-row-block" }, [
        el("div", { class: "sfdc-lbl" }, "PDF archived as ContentDocument"),
        el("div", { class: "sfdc-row" }, [
          el("span", { class: "sfdc-id" }, contentDoc.content_document_id),
          el("a", { class: "sfdc-link", href: contentDoc.url, target: "_blank", rel: "noopener" }, "Open ↗"),
        ]),
      ])
    );
  }

  // Slack
  if (slack && slack.channel) {
    sec.appendChild(
      el("div", { class: "sfdc-row-block" }, [
        el("div", { class: "sfdc-lbl" }, "Slack post (SF Slack connector)"),
        el("div", { class: "sfdc-row" }, [
          el("span", { class: "sfdc-channel" }, slack.channel),
          el("span", { class: "muted small" }, " posted via Salesforce-Slack integration"),
        ]),
      ])
    );
  }

  // Tasks
  if (post.salesforce_tasks && post.salesforce_tasks.length) {
    const tasksWrap = el("div", { class: "sfdc-row-block" }, [
      el("div", { class: "sfdc-lbl" }, `Tasks pushed (${post.salesforce_tasks.length})`),
    ]);
    post.salesforce_tasks.forEach((t) => {
      tasksWrap.appendChild(
        el("div", { class: "sfdc-task" }, [
          el("span", { class: "sfdc-task-id" }, t.id),
          el("span", { class: "sfdc-task-subject" }, t.subject),
          el("a", { class: "sfdc-link", href: t.url, target: "_blank", rel: "noopener" }, "↗"),
        ])
      );
    });
    sec.appendChild(tasksWrap);
  }

  return sec;
}

function renderSalesforceTasksOnly(post) {
  const sec = el("details", { class: "post-section sfdc-section", open: "" });
  sec.appendChild(
    el("summary", {}, [
      el("h3", { class: "post-section-title blue" }, "Salesforce sync"),
      el("span", { class: "chevron" }, ""),
      el("span", { class: "count" }, "" + post.salesforce_tasks.length),
    ])
  );
  const acc = post.salesforce_account || {};
  if (acc.Id) {
    sec.appendChild(
      el("div", { class: "sfdc-account" }, [
        el("div", { class: "sfdc-lbl" }, "Account"),
        el("div", { class: "sfdc-row" }, [
          el("span", { class: "sfdc-id" }, acc.Id),
          el("span", { class: "muted small" }, ` · ${acc.Name || ""}`),
          el("a", { class: "sfdc-link", href: acc.Url, target: "_blank", rel: "noopener" }, "Open ↗"),
        ]),
      ])
    );
  }
  return sec;
}

async function loadBattlecards(competitors, host) {
  // Dedupe by lowercased competitor name; cap at 3 to keep the demo focused.
  const seen = new Set();
  const names = [];
  competitors.forEach((c) => {
    const key = (c.competitor || "").toLowerCase().trim();
    if (!key || seen.has(key)) return;
    seen.add(key);
    names.push(c.competitor);
  });
  const fetched = await Promise.all(
    names.slice(0, 3).map((n) =>
      apiGet(`/battlecards/by-competitor/${encodeURIComponent(n)}`).catch(() => null)
    )
  );
  const cards = fetched.filter(Boolean);
  if (!cards.length) return;
  clear(host);
  host.appendChild(
    el("div", { class: "battlecards-head" }, [
      el("h3", { class: "post-section-title pink" }, "Battlecards"),
      el("span", { class: "muted small" }, ` Auto-matched · ${cards.length} of ${names.length} competitor(s)`),
    ])
  );
  const grid = el("div", { class: "battlecards-grid" });
  cards.forEach((c) => grid.appendChild(renderBattlecard(c)));
  host.appendChild(grid);
}

function renderBattlecard(c) {
  const card = el("div", { class: "battlecard" });
  // Header
  card.appendChild(
    el("div", { class: "bc-head" }, [
      el("div", { class: "bc-name" }, "vs " + c.competitor),
      el("div", { class: "bc-tagline" }, c.tagline || ""),
    ])
  );
  if (c.key_pain) {
    card.appendChild(
      el("div", { class: "bc-pain" }, [
        el("span", { class: "bc-pain-lbl" }, "Customer pain"),
        document.createTextNode(c.key_pain),
      ])
    );
  }
  // Talking points (top 3, collapsible details for proof)
  if (c.talking_points && c.talking_points.length) {
    const tp = el("div", { class: "bc-section" }, [el("div", { class: "bc-section-lbl" }, "Talking points")]);
    c.talking_points.slice(0, 3).forEach((p, i) => {
      const det = el("details", { class: "bc-tp" });
      det.appendChild(
        el("summary", {}, [
          el("span", { class: "bc-tp-angle" }, p.angle),
          el("span", { class: "bc-tp-claim" }, p.claim),
          el("span", { class: "chevron bc-tp-chev" }, ""),
        ])
      );
      if (p.proof) det.appendChild(el("div", { class: "bc-tp-proof" }, p.proof));
      tp.appendChild(det);
    });
    card.appendChild(tp);
  }
  // Common objections
  if (c.common_objections && c.common_objections.length) {
    const obj = el("div", { class: "bc-section" }, [el("div", { class: "bc-section-lbl" }, "If they push back")]);
    c.common_objections.slice(0, 2).forEach((o) => {
      obj.appendChild(
        el("div", { class: "bc-obj" }, [
          el("div", { class: "bc-obj-q" }, '"' + o.q + '"'),
          el("div", { class: "bc-obj-a" }, o.a),
        ])
      );
    });
    card.appendChild(obj);
  }
  // Discovery questions (compact)
  if (c.discovery_questions && c.discovery_questions.length) {
    const dq = el("div", { class: "bc-section" }, [el("div", { class: "bc-section-lbl" }, "Discovery to confirm")]);
    const ul = el("ul", { class: "bc-dq" });
    c.discovery_questions.slice(0, 3).forEach((q) => ul.appendChild(el("li", {}, q)));
    dq.appendChild(ul);
    card.appendChild(dq);
  }
  return card;
}
function textNode(s) {
  return document.createTextNode(s);
}

function setupTabs() {
  const tabs = document.querySelectorAll(".tab");
  tabs.forEach((t) =>
    t.addEventListener("click", () => {
      // Mirror visual active state into aria-selected so AT users hear the
      // newly selected tab announced (WCAG 4.1.2 Name/Role/Value).
      tabs.forEach((x) => {
        x.classList.remove("active");
        x.setAttribute("aria-selected", "false");
      });
      t.classList.add("active");
      t.setAttribute("aria-selected", "true");
      const target = t.dataset.tab;
      ["brief", "post", "live", "context"].forEach((id) => {
        const panel = document.getElementById(`panel-${id}`);
        if (!panel) return;
        if (id === target) {
          panel.hidden = false;
          panel.classList.remove("fade-in");
          // force reflow so the animation re-runs
          void panel.offsetWidth;
          panel.classList.add("fade-in");
        } else {
          panel.hidden = true;
        }
      });
    })
  );
  if (showPost) document.querySelector('.tab[data-tab="post"]')?.click();
}

async function maybeAutoLoad() {
  const looksLikeAdHocBrief = isAdHoc && !showPost;
  const looksLikeTranscript = meetingId.startsWith("transcript-") || showPost;

  if (!looksLikeTranscript) {
    try {
      const brief = await apiGet(`/briefs/${meetingId}`);
      if (brief && brief.exists !== false && brief.headline) renderBrief(brief);
    } catch (e) {
      /* network error; keep empty state */
    }
  }
  if (!looksLikeAdHocBrief) {
    try {
      const post = await apiGet(`/briefs/${meetingId}/post`);
      if (post && post.exists !== false && post.summary) renderPost(post);
    } catch (e) {
      /* network error; keep empty state */
    }
  }
}

function bindActions() {
  document.getElementById("run-pre")?.addEventListener("click", async (ev) => {
    const btn = ev.currentTarget;
    const labelHTML = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Running Pre-Meeting...';
    showSkeleton("brief");
    try {
      const model = encodeURIComponent(document.getElementById("pre-model")?.value || "");
      const lang = encodeURIComponent(claudeLanguageName());
      const brief = await apiPost(`/agents/pre-meeting/${meetingId}?language=${lang}&model=${model}`, {});
      renderBrief(brief);
      toast("Pre-Meeting brief generated", "ok");
    } catch (e) {
      const safe = (typeof sanitizeError === "function") ? sanitizeError(e) : (e && e.message) || "unknown error";
      toast(`Pre-Meeting failed: ${safe}`, "bad");
      document.getElementById("brief").innerHTML = '<p class="muted">Run again to retry.</p>';
    } finally {
      btn.disabled = false;
      btn.innerHTML = labelHTML;
    }
  });

  document.getElementById("run-post")?.addEventListener("click", async (ev) => {
    const btn = ev.currentTarget;
    const labelHTML = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Running Post-Meeting...';
    showSkeleton("post");
    try {
      const model = encodeURIComponent(document.getElementById("post-model")?.value || "");
      const lang = encodeURIComponent(claudeLanguageName());
      const result = await apiPost(`/agents/post-meeting/${meetingId}?language=${lang}&model=${model}`, {});
      renderPost(result);
      toast("Post-Meeting result generated", "ok");
    } catch (e) {
      const safe = (typeof sanitizeError === "function") ? sanitizeError(e) : (e && e.message) || "unknown error";
      toast(`Post-Meeting failed: ${safe}`, "bad");
      document.getElementById("post").innerHTML = '<p class="muted">Run again to retry.</p>';
    } finally {
      btn.disabled = false;
      btn.innerHTML = labelHTML;
    }
  });

  document.getElementById("create-slide")?.addEventListener("click", async (ev) => {
    const btn = ev.currentTarget;
    const labelHTML = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Generating…';
    try {
      const result = await apiPost(`/weekly-slides/from-meeting/${meetingId}`, {});
      const ch = result.slack_channel ? ` → ${result.slack_channel}` : "";
      toast(`Slide created${ch}`, "ok");
      const downloadHref = result.pptx_rel || result.pptx_url;
      if (downloadHref) {
        const link = document.createElement("a");
        link.href = downloadHref;
        link.download = result.slide_name || "slide.pptx";
        link.click();
      }
    } catch (e) {
      const safe = (typeof sanitizeError === "function") ? sanitizeError(e) : (e && e.message) || "error";
      toast(`Slide failed: ${safe}`, "bad");
    } finally {
      btn.disabled = false;
      btn.innerHTML = labelHTML;
    }
  });

  document.getElementById("create-dashboard")?.addEventListener("click", async (ev) => {
    const btn = ev.currentTarget;
    const labelHTML = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Building dashboard...';
    try {
      const result = await apiPost(`/kibana/dashboard/${meetingId}`, {});
      if (result && result.dashboard_url) {
        window.open(result.dashboard_url, "_blank", "noreferrer");
        toast(`Dashboard created with ${result.panels} panels - opening in Kibana`, "ok");
      } else {
        toast("Dashboard request returned no URL", "bad");
      }
    } catch (e) {
      const safe = (typeof sanitizeError === "function") ? sanitizeError(e) : (e && e.message) || "unknown error";
      toast(`Dashboard creation failed: ${safe}`, "bad");
    } finally {
      btn.disabled = false;
      btn.innerHTML = labelHTML;
    }
  });

  // Generate TAR (Technical Account Review): CA-facing technical health
  // review built from the post-meeting record. Result is rendered inline
  // via window.renderTAR (tar-widget.js). TAR REQUIRES a post-meeting
  // record on file - it summarises what came out of an actual call, not
  // the pre-meeting hypothesis. For ad-hoc meetings (Quick Research) the
  // button stays disabled with a tooltip explaining what to do first.
  (function setupTar() {
    const btn = document.getElementById("generate-tar");
    if (!btn) return;
    const isAdHoc = /^(ad-hoc-|transcript-)/.test(meetingId);

    function setDisabledWithHint(reason) {
      btn.disabled = true;
      btn.title = reason;
      btn.setAttribute("aria-disabled", "true");
      btn.style.opacity = "0.55";
      btn.style.cursor = "not-allowed";
    }
    function setEnabled() {
      btn.disabled = false;
      btn.removeAttribute("aria-disabled");
      btn.style.opacity = "";
      btn.style.cursor = "";
      btn.title = "Generate Technical Account Review for this account.";
    }

    // Ad-hoc Quick Research has no transcript, so TAR cannot run. Disable
    // the button upfront with a clear tooltip pointing the FE to the right
    // path. For real meetings the button stays clickable; if the post-meeting
    // record is missing the click handler below surfaces the same hint as
    // both a toast and an inline error note.
    if (isAdHoc) {
      setDisabledWithHint("TAR is built from a post-meeting record. Ad-hoc Quick Research has no transcript; paste one on the Quick Research Transcript analyzer to create the post-meeting first.");
    }

    btn.addEventListener("click", async (ev) => {
      if (btn.disabled) {
        // Surface the reason as a toast too so the FE sees it even on touch
        // devices where hovering the tooltip is not possible.
        toast(btn.title || "TAR not available yet", "bad");
        return;
      }
      const labelHTML = btn.innerHTML;
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner"></span> Generating TAR...';
      try {
        const opts = { category: "llm", timeoutMs: 90000, retries: 0, silent: true, label: "Generate TAR" };
        const result = typeof window.apiPostWithRetry === "function"
          ? await window.apiPostWithRetry(`/tar/from-meeting/${encodeURIComponent(meetingId)}`, {}, opts)
          : await apiPost(`/tar/from-meeting/${encodeURIComponent(meetingId)}`, {});
        const host = document.getElementById("abm-brief") || document.getElementById("brief");
        if (host && typeof window.renderTAR === "function") {
          const wrap = document.createElement("div");
          wrap.style.marginTop = "18px";
          host.appendChild(wrap);
          window.renderTAR(wrap, result);
          try { wrap.scrollIntoView({ behavior: "smooth", block: "start" }); } catch (_) {}
        }
        toast("TAR ready", "ok");
      } catch (e) {
        const safe = (typeof sanitizeError === "function") ? sanitizeError(e) : (e && e.message) || "unknown error";
        const friendly = /not.*found|404|no.*post.?meeting/i.test(safe)
          ? "TAR needs a post-meeting record first. Run Post-Meeting on the Post-meeting tab, then try again."
          : safe;
        toast(`TAR failed: ${friendly}`, "bad");
        // Also render the error inline near the button so the FE does not
        // miss it after the toast fades.
        const host = document.getElementById("brief");
        if (host) {
          const note = document.createElement("div");
          note.className = "muted small";
          note.style.cssText = "margin-top:10px; padding:8px 12px; border:1px solid var(--border, #2a2f3a); border-left:3px solid #F04E98; border-radius:6px;";
          note.textContent = friendly;
          host.appendChild(note);
        }
      } finally {
        setEnabled();
        btn.innerHTML = labelHTML;
      }
    });
  })();

  document.getElementById("run-live")?.addEventListener("click", async (ev) => {
    const btn = ev.currentTarget;
    const labelHTML = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Replaying...';
    try {
      await replayTranscript();
    } catch (e) {
      const safe = (typeof sanitizeError === "function") ? sanitizeError(e) : (e && e.message) || "unknown error";
      toast(`Live agent failed: ${safe}`, "bad");
    } finally {
      btn.disabled = false;
      btn.innerHTML = labelHTML;
    }
  });

  document.getElementById("print-brief")?.addEventListener("click", () => {
    document.body.classList.add("printing");
    window.print();
    setTimeout(() => document.body.classList.remove("printing"), 500);
  });
}

function showSkeleton(target) {
  const host = document.getElementById(target);
  if (!host) return;
  clear(host);
  const skel = el("div", { class: "skeleton" });
  // Headline skeleton
  skel.appendChild(el("div", { class: "skel-line headline" }));
  // Several block skeletons
  for (let i = 0; i < 4; i++) {
    skel.appendChild(el("div", { class: "skel-block" }, [
      el("div", { class: "skel-line short" }),
      el("div", { class: "skel-line" }),
      el("div", { class: "skel-line" }),
      el("div", { class: "skel-line med" }),
    ]));
  }
  host.appendChild(skel);
}

function renderBrief(brief) {
  const host = document.getElementById("brief");
  clear(host);
  // Expose the full brief so the Pre-sales Playbook widget can detect vertical
  // (search vs observability) from the same data the agent used.
  try { window.__lastBrief = brief; } catch (_) { /* ignore */ }
  host.appendChild(el("div", { class: "brief-headline" }, brief.headline));

  const tools = el("div", { class: "section-tools" }, [
    el("button", { class: "btn-link", onclick: () => toggleAll("brief", true) }, "Expand all"),
    el("span", { class: "muted" }, " · "),
    el("button", { class: "btn-link", onclick: () => toggleAll("brief", false) }, "Collapse all"),
  ]);
  host.appendChild(tools);

  // Stash sources on the host so per-bullet matchers can find them.
  const sources = brief.sources_used || {};

  brief.sections.forEach((s) => {
    const sec = el("details", { class: "brief-section", open: "" });
    const summary = el("summary", {}, [
      el("h3", {}, s.heading),
      el("span", { class: "chevron" }, ""),
      el("span", { class: "count" }, `${s.bullets.length}`),
    ]);
    sec.appendChild(summary);
    const ul = el("ul");
    s.bullets.forEach((b) => {
      const li = el("li", {}, [el("span", { class: "bullet-text" }, b)]);
      const link = bulletSourceLink(b, sources);
      if (link) li.appendChild(link);
      ul.appendChild(li);
    });
    sec.appendChild(ul);
    host.appendChild(sec);
  });

  // Sources panel: every input the agent saw, with clickable links where available.
  const src = brief.sources_used;
  const hasAnySource = src && (src.news?.length || src.tickets?.length || src.past_transcripts?.length || src.user_input);
  if (hasAnySource) {
    const sources = el("details", { id: "sources-panel", class: "brief-section sources-section", open: "" });
    const sourceCount =
      (src.news || []).length +
      (src.tickets || []).length +
      (src.past_transcripts || []).length +
      (src.user_input ? 1 : 0);
    sources.appendChild(
      el("summary", {}, [
        el("h3", {}, "Sources used"),
        el("span", { class: "chevron" }, ""),
        el("span", { class: "count" }, `${sourceCount}`),
      ])
    );
    const wrap = el("div", { class: "sources-list" });
    if (src.user_input) {
      const ui = src.user_input;
      const block = el("div", { class: "sources-block" }, [
        el("div", { class: "sources-block-lbl" }, "User input (only this left the perimeter)"),
      ]);
      const fields = [
        ["Company", ui.company_name],
        ["Industry", ui.industry],
        ["Size", ui.size],
        ["Stack notes", ui.tech_stack_notes],
        ["Meeting title", ui.meeting_title],
        ["Notes", ui.notes],
      ];
      fields.forEach(([k, v]) => {
        if (!v) return;
        block.appendChild(
          el("div", { class: "sources-row" }, [
            el("span", { class: "ui-key" }, k),
            el("span", { class: "ui-val" }, v),
          ])
        );
      });
      wrap.appendChild(block);
    }
    if (src.news?.length) {
      const block = el("div", { class: "sources-block" }, [
        el("div", { class: "sources-block-lbl" }, "News"),
      ]);
      src.news.forEach((n) => {
        block.appendChild(
          el("div", { class: "sources-row" }, [
            el(
              "a",
              { class: "sources-link", href: n.url, target: "_blank", rel: "noopener" },
              `${n.title} ↗`
            ),
            el("span", { class: "muted small" }, ` ${n.source}${n.published_at ? " · " + fmtDate(n.published_at) : ""}`),
          ])
        );
      });
      wrap.appendChild(block);
    }
    if (src.tickets?.length) {
      const block = el("div", { class: "sources-block" }, [
        el("div", { class: "sources-block-lbl" }, "Tickets"),
      ]);
      src.tickets.forEach((t) => {
        block.appendChild(
          el("div", { class: "sources-row" }, [
            el("span", { class: `ticket-pri ticket-pri-${t.priority || "P3"}` }, t.priority || "P3"),
            el("span", {}, ` ${t.subject}`),
            el("span", { class: "muted small" }, ` · ${t.status || ""}`),
          ])
        );
      });
      wrap.appendChild(block);
    }
    if (src.past_transcripts?.length) {
      const block = el("div", { class: "sources-block" }, [
        el("div", { class: "sources-block-lbl" }, "Past meetings"),
      ]);
      src.past_transcripts.forEach((t) => {
        block.appendChild(
          el("div", { class: "sources-row" }, [
            el(
              "a",
              {
                class: "sources-link",
                href: "#",
                onclick: (ev) => {
                  ev.preventDefault();
                  window.location.href = `/meeting.html?id=${encodeURIComponent(t.meeting_id)}`;
                },
              },
              `${t.meeting_id} ↗`
            ),
            el("span", { class: "muted small" }, ` · ${t.turn_count} turns`),
          ])
        );
      });
      wrap.appendChild(block);
    }
    if (src.sec_filings?.length) {
      const block = el("div", { class: "sources-block" }, [
        el("div", { class: "sources-block-lbl" }, "SEC filings (live from data.sec.gov)"),
      ]);
      src.sec_filings.forEach((f) => {
        block.appendChild(
          el("div", { class: "sources-row" }, [
            el("span", { class: `ticket-pri ticket-pri-P2` }, f.form),
            el(
              "a",
              { class: "sources-link", href: f.url, target: "_blank", rel: "noopener" },
              `Filed ${f.filing_date}${f.description ? " · " + f.description.slice(0, 60) : ""} ↗`
            ),
            f.items ? el("span", { class: "muted small" }, ` items: ${f.items}`) : null,
          ])
        );
      });
      wrap.appendChild(block);
    }
    sources.appendChild(wrap);
    host.appendChild(sources);
  }

  const dl = document.getElementById("download-pdf");
  if (dl) {
    dl.href = `/api/v1/briefs/${meetingId}/artifact`;
    dl.hidden = false;
  }
  document.getElementById("print-brief")?.removeAttribute("hidden");
}

function toggleAll(panelId, open) {
  document.querySelectorAll(`#${panelId} details`).forEach((d) => {
    if (open) d.setAttribute("open", "");
    else d.removeAttribute("open");
  });
}

function renderPost(post) {
  const host = document.getElementById("post");
  clear(host);

  host.appendChild(el("div", { class: "brief-headline" }, post.summary));

  // Deal-health row: MEDDPICC radar + (BANT + Funnel)
  const healthRow = el("div", { class: "health-row" }, [
    renderMEDDPICCRadar(post.meddpicc_signals || []),
    el("div", { class: "health-right" }, [
      renderBANTChips(post.meddpicc_signals || []),
      renderVelocityFunnel(post.meddpicc_signals || []),
    ]),
  ]);
  host.appendChild(healthRow);

  // Force-Field Analysis (executive snapshot)
  host.appendChild(renderForceField(post.meddpicc_signals || [], post.competitor_mentions || []));

  const tools = el("div", { class: "section-tools", style: "display:flex;align-items:center;" }, [
    el("button", { class: "btn-link", onclick: () => toggleAll("post", true) }, "Expand all"),
    el("span", { class: "muted" }, " · "),
    el("button", { class: "btn-link", onclick: () => toggleAll("post", false) }, "Collapse all"),
  ]);
  host.appendChild(tools);

  // Inject open-tasks badge styles once
  if (!document.getElementById("fec-open-tasks-style")) {
    const s = document.createElement("style");
    s.id = "fec-open-tasks-style";
    s.textContent = ".open-tasks-badge { display: inline-flex; align-items: center; padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 600; background: rgba(250, 203, 61, 0.18); color: #FACB3D; border: 1px solid rgba(250, 203, 61, 0.4); margin-left: 6px; }";
    document.head.appendChild(s);
  }

  // Action items section: List view (checkboxes) as default; Matrix as alternate.
  const actionsSec = el("details", { class: "post-section", open: "" });
  const countEl = el("span", { class: "count" }, `${(post.action_items || []).length}`);
  const openBadgeEl = post.open_tasks_count > 0
    ? el("span", { class: "open-tasks-badge" }, `${post.open_tasks_count} open`)
    : null;
  actionsSec.appendChild(
    el("summary", {}, [
      el("h3", { class: "post-section-title teal" }, "Action items"),
      el("span", { class: "chevron" }, ""),
      countEl,
      ...(openBadgeEl ? [openBadgeEl] : []),
    ])
  );

  // Toggle group - List is default
  const toolbar = el("div", { class: "actions-toolbar" }, [
    el("div", { class: "toggle-group" }, [
      el("button", { "data-view": "matrix" }, "Matrix"),
      el("button", { class: "active", "data-view": "list" }, "List"),
    ]),
  ]);
  actionsSec.appendChild(toolbar);

  const matrixHost = el("div", { class: "actions-matrix-host", style: "display:none" });
  matrixHost.appendChild(renderEisenhowerMatrix(post.action_items || []));
  actionsSec.appendChild(matrixHost);

  const list = el("ul", { class: "actions-list" });

  function updateDoneCount() {
    const done = list.querySelectorAll("li.done").length;
    const total = post.action_items.length;
    countEl.textContent = done > 0 ? `${done}/${total}` : `${total}`;

    if (openBadgeEl) {
      const openCount = list.querySelectorAll(".action-check:not(:checked)").length;
      if (openCount > 0) {
        openBadgeEl.textContent = `${openCount} open`;
        openBadgeEl.style.display = "";
      } else {
        openBadgeEl.style.display = "none";
      }
    }

    // All-done celebration
    const wrapper = list.parentElement;
    if (done === total && total > 0) {
      wrapper.classList.add("all-done");

      let toastEl = wrapper.querySelector("#fec-allDone-toast");
      if (!toastEl) {
        toastEl = el("div", { id: "fec-allDone-toast" }, "All items complete!");
        wrapper.appendChild(toastEl);
      }
      toastEl.textContent = "All items complete!";
      toastEl.classList.add("visible");
      clearTimeout(toastEl._hideTimer);
      toastEl._hideTimer = setTimeout(() => toastEl.classList.remove("visible"), 3000);
    } else {
      wrapper.classList.remove("all-done");
    }
  }

  post.action_items.forEach((a, idx) => {
    const isDone = !!a.completed;
    const li = el("li", { class: isDone ? "done" : "", tabindex: "0" });

    // Checkbox checkpoint
    const checkbox = el("input", { type: "checkbox", class: "action-check", title: isDone ? "Mark incomplete" : "Mark complete" });
    checkbox.checked = isDone;
    checkbox.addEventListener("change", async () => {
      const done = checkbox.checked;
      li.classList.toggle("done", done);
      checkbox.disabled = true;
      try {
        await apiPatch(`/briefs/${meetingId}/action-items/${idx}`, { completed: done });
        updateDoneCount();
      } catch (e) {
        checkbox.checked = !done;
        li.classList.toggle("done", !done);
        toast(sanitizeError(e), "error");
      }
      checkbox.disabled = false;
    });
    li.appendChild(el("div", { class: "ai-check-col" }, [checkbox]));

    const head = el("div", { class: "head" }, [
      el("span", { class: "title" }, a.title),
      el("div", { class: "head-right" }, [
        a.impact ? el("span", { class: `impact impact-${a.impact}` }, a.impact) : null,
        a.due_date ? el("span", { class: "due" }, "Due " + a.due_date) : null,
      ]),
    ]);
    const ownerLine = el("div", { class: "owner" }, `${a.owner_name}${a.owner_email ? " · " + a.owner_email : ""}`);
    const desc = el("div", { class: "desc" }, a.description);
    const quoteRow = el("div", { class: "quote-row" }, [
      el("div", { class: "quote" }, `"${a.source_quote}"`),
      el(
        "a",
        {
          class: "item-source",
          href: "#",
          title: "Open in transcript",
          onclick: (ev) => {
            ev.preventDefault();
            if (window.openTranscriptAt) window.openTranscriptAt(a.source_quote);
          },
        },
        "Source ↗"
      ),
    ]);
    li.appendChild(head);
    li.appendChild(ownerLine);
    li.appendChild(desc);
    li.appendChild(quoteRow);
    list.appendChild(li);
  });
  actionsSec.appendChild(list);
  updateDoneCount();

  // Keyboard shortcut: press "d" to check off the first unchecked action item
  function onActionKeydown(e) {
    if (e.key !== "d") return;
    const tag = (document.activeElement || {}).tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
    const firstUnchecked = list.querySelector(".action-check:not(:checked)");
    if (firstUnchecked) firstUnchecked.click();
  }
  document.addEventListener("keydown", onActionKeydown);

  // Wire up matrix/list toggle
  toolbar.querySelectorAll("button").forEach((b) =>
    b.addEventListener("click", () => {
      toolbar.querySelectorAll("button").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      const view = b.dataset.view;
      matrixHost.style.display = view === "matrix" ? "" : "none";
      list.style.display = view === "list" ? "" : "none";
    })
  );

  host.appendChild(actionsSec);

  // MEDDPICC signals (collapsible)
  const meddSec = el("details", { class: "post-section", open: "" });
  meddSec.appendChild(
    el("summary", {}, [
      el("h3", { class: "post-section-title blue" }, "MEDDPICC signals"),
      el("span", { class: "chevron" }, ""),
      el("span", { class: "count" }, `${post.meddpicc_signals.length}`),
    ])
  );
  const grid = el("div", { class: "meddpicc-grid" });
  post.meddpicc_signals.forEach((s) => {
    const head = el("div", { class: "item-head" }, [
      el("span", { class: "cat" }, s.category),
      el(
        "a",
        {
          class: "item-source",
          href: "#",
          title: "Open in transcript",
          onclick: (ev) => {
            ev.preventDefault();
            if (window.openTranscriptAt) window.openTranscriptAt(s.quote);
          },
        },
        "Source ↗"
      ),
    ]);
    grid.appendChild(
      el("div", { class: "item", "data-cat": s.category }, [
        head,
        el("div", { class: "quote" }, `"${s.quote}"`),
        s.note ? el("div", { class: "note" }, s.note) : null,
      ])
    );
  });
  meddSec.appendChild(grid);
  host.appendChild(meddSec);

  // Competitors (collapsible) + auto battlecards
  if (post.competitor_mentions && post.competitor_mentions.length) {
    const compSec = el("details", { class: "post-section", open: "" });
    compSec.appendChild(
      el("summary", {}, [
        el("h3", { class: "post-section-title pink" }, "Competitor mentions"),
        el("span", { class: "chevron" }, ""),
        el("span", { class: "count" }, `${post.competitor_mentions.length}`),
      ])
    );
    // Battlecards container appears below the grid; populated async.
    const cardsHost = el("div", { class: "battlecards-host" });
    loadBattlecards(post.competitor_mentions, cardsHost);
    const cgrid = el("div", { class: "meddpicc-grid" });
    post.competitor_mentions.forEach((c) => {
      const head = el("div", { class: "item-head" }, [
        el("span", { class: "cat" }, c.competitor),
        el(
          "a",
          {
            class: "item-source",
            href: "#",
            title: "Open in transcript",
            onclick: (ev) => {
              ev.preventDefault();
              if (window.openTranscriptAt) window.openTranscriptAt(c.context);
            },
          },
          "Source ↗"
        ),
      ]);
      cgrid.appendChild(
        el("div", { class: "item", "data-cat": "Competition" }, [head, el("div", { class: "quote" }, c.context)])
      );
    });
    compSec.appendChild(cgrid);
    compSec.appendChild(cardsHost);
    host.appendChild(compSec);
  }

  // Power-Interest Grid (stakeholders) - collapsible
  const piSec = el("details", { class: "post-section", open: "" });
  piSec.appendChild(
    el("summary", {}, [
      el("h3", { class: "post-section-title blue" }, "Stakeholders"),
      el("span", { class: "chevron" }, ""),
    ])
  );
  piSec.appendChild(
    renderPowerInterestGrid(MEETING_DATA.transcript, (MEETING_DATA.meeting || {}).attendees || [])
  );
  host.appendChild(piSec);

  // Email draft (collapsible)
  const emailSec = el("details", { class: "post-section", open: "" });
  emailSec.appendChild(
    el("summary", {}, [
      el("h3", { class: "post-section-title yellow" }, "Follow-up email draft"),
      el("span", { class: "chevron" }, ""),
    ])
  );
  emailSec.appendChild(
    el("div", { class: "email-draft" }, [
      el("div", { class: "subject" }, [
        el("span", { class: "lbl" }, "Subject"),
        document.createTextNode(post.follow_up_email.subject),
      ]),
      document.createTextNode(post.follow_up_email.body_markdown),
    ])
  );
  host.appendChild(emailSec);

  if (post.salesforce_writes) {
    host.appendChild(renderSalesforcePanel(post));
  } else if (post.salesforce_tasks && post.salesforce_tasks.length) {
    // Backwards compatibility for older briefs without the extended writes.
    host.appendChild(renderSalesforceTasksOnly(post));
  } else if (post.salesforce_task_ids && post.salesforce_task_ids.length) {
    host.appendChild(
      el("div", { class: "muted small", style: "margin-top:14px" },
        `Pushed ${post.salesforce_task_ids.length} task(s) to the Salesforce mock.`)
    );
  }
}

async function replayTranscript() {
  const host = document.getElementById("live");
  clear(host);
  const transcript = MEETING_DATA.transcript;
  if (!transcript || !transcript.turns || !transcript.turns.length) {
    host.appendChild(el("p", { class: "muted" }, "No transcript on file for this meeting."));
    return;
  }

  for (let i = 0; i < transcript.turns.length; i++) {
    const turn = transcript.turns[i];
    const turnNode = el("div", { class: "transcript-turn" }, [
      el("div", { class: "speaker" }, turn.speaker),
      el("div", { class: "text" }, turn.text),
    ]);
    host.appendChild(turnNode);

    let result;
    try {
      const model = encodeURIComponent(document.getElementById("live-model")?.value || "");
      const lang = encodeURIComponent(claudeLanguageName());
      result = await apiPost(`/agents/live-meeting/${meetingId}/turn/${i}?language=${lang}&model=${model}`, {});
    } catch (e) {
      continue;
    }
    if (result && result.alerts && result.alerts.length) {
      turnNode.classList.add("alerted");
      result.alerts.forEach((a) => {
        const row = el("div", { class: `alert-row ${a.severity}` }, [
          el("div", { class: "type" }, a.type),
          el("div", { class: "body" }, [
            el("div", { class: "msg" }, a.message),
            el("div", { class: "sug" }, a.suggested_response),
          ]),
        ]);
        host.appendChild(row);
      });
    }
    await new Promise((r) => setTimeout(r, 60));
  }
}

function renderContext() {
  const host = document.getElementById("context");
  clear(host);

  const c = MEETING_DATA.company;
  host.appendChild(
    el("div", { class: "context-block" }, [
      el("h3", {}, "Company"),
      el("div", {}, c.description || "No description on file."),
      el(
        "div",
        { class: "muted small", style: "margin-top:8px" },
        `Stack: observability=${(c.tech_stack && c.tech_stack.observability || []).join(", ") || "n/a"} · search=${(c.tech_stack && c.tech_stack.search || []).join(", ") || "n/a"} · cloud=${(c.tech_stack && c.tech_stack.cloud || []).join(", ") || "n/a"}`
      ),
    ])
  );

  if (MEETING_DATA.news && MEETING_DATA.news.length) {
    const block = el("div", { class: "context-block" }, [el("h3", {}, "Recent news")]);
    MEETING_DATA.news.forEach((n) => {
      block.appendChild(
        el("div", { style: "margin-bottom:10px" }, [
          el(
            "a",
            { class: "sources-link", href: n.url, target: "_blank", rel: "noopener" },
            `${n.title} ↗`
          ),
          el("div", { class: "muted small" }, `${n.source} · ${fmtDate(n.published_at)}`),
          n.summary ? el("div", { class: "small", style: "margin-top:3px" }, n.summary) : null,
        ])
      );
    });
    host.appendChild(block);
  }

  if (MEETING_DATA.tickets && MEETING_DATA.tickets.length) {
    const block = el("div", { class: "context-block" }, [el("h3", {}, "Tickets")]);
    MEETING_DATA.tickets.forEach((t) => {
      block.appendChild(
        el("div", { style: "margin-bottom:8px" }, [
          el("div", {}, `[${t.priority}] [${t.status}] ${t.subject}`),
          el("div", { class: "muted small" }, t.description),
        ])
      );
    });
    host.appendChild(block);
  }
}
