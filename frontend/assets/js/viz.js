/*
  filename: viz.js
  description: Sales-framework visualizations as pure SVG/HTML, no chart libs. Top 3 (MEDDPICC Radar, Eisenhower Matrix, Force-Field) are polished; the other 4 are functional and lightweight.
  Author: Rodrigo Careaga
  Date: 03-05-2026
*/

const VIZ_PALETTE = {
  teal: "#00BFB3",
  pink: "#F04E98",
  blue: "#1BA9F5",
  yellow: "#FEC514",
  ink: "#E6E9EF",
  muted: "#8A93A2",
  border: "#2D3340",
};

const MEDDPICC_CATS = [
  "Metrics",
  "Economic Buyer",
  "Decision Criteria",
  "Decision Process",
  "Identify Pain",
  "Champion",
  "Competition",
];

const MEDDPICC_COLORS = {
  Metrics: VIZ_PALETTE.teal,
  "Economic Buyer": VIZ_PALETTE.yellow,
  "Decision Criteria": VIZ_PALETTE.blue,
  "Decision Process": VIZ_PALETTE.blue,
  "Identify Pain": VIZ_PALETTE.pink,
  Champion: VIZ_PALETTE.teal,
  Competition: VIZ_PALETTE.pink,
};

// ----------------------------------------------------------- 1. MEDDPICC Radar (top 3)

function renderMEDDPICCRadar(signals) {
  const scores = MEDDPICC_CATS.map((c) =>
    Math.min(3, (signals || []).filter((s) => s.category === c).length)
  );
  const maxScore = 3;
  const size = 320;
  const cx = size / 2;
  const cy = size / 2;
  const maxR = 110;

  const N = MEDDPICC_CATS.length;
  const angle = (i) => -Math.PI / 2 + (i / N) * 2 * Math.PI;

  const ringPoints = (r) =>
    MEDDPICC_CATS.map((_, i) => {
      const a = angle(i);
      return `${cx + r * Math.cos(a)},${cy + r * Math.sin(a)}`;
    }).join(" ");

  const polyPoints = scores
    .map((s, i) => {
      const r = (s / maxScore) * maxR;
      const a = angle(i);
      return `${cx + r * Math.cos(a)},${cy + r * Math.sin(a)}`;
    })
    .join(" ");

  // Score and labels
  const labels = MEDDPICC_CATS.map((c, i) => {
    const a = angle(i);
    const lr = maxR + 22;
    const lx = cx + lr * Math.cos(a);
    const ly = cy + lr * Math.sin(a);
    let anchor = "middle";
    if (lx < cx - 4) anchor = "end";
    else if (lx > cx + 4) anchor = "start";
    const short = c
      .split(" ")
      .map((w) => (w.length > 4 ? w[0] : w))
      .join(" ");
    return `<text x="${lx.toFixed(1)}" y="${ly.toFixed(1)}" text-anchor="${anchor}" dominant-baseline="middle" fill="${VIZ_PALETTE.muted}" font-size="10" font-weight="600" letter-spacing="0.04em">${short.toUpperCase()}</text>
            <text x="${lx.toFixed(1)}" y="${(ly + 12).toFixed(1)}" text-anchor="${anchor}" dominant-baseline="middle" fill="${MEDDPICC_COLORS[c]}" font-size="13" font-weight="700">${scores[i]}/${maxScore}</text>`;
  }).join("");

  const grid = [1, 2, 3]
    .map(
      (level) =>
        `<polygon points="${ringPoints((level / maxScore) * maxR)}" fill="none" stroke="${VIZ_PALETTE.border}" stroke-width="0.7" stroke-dasharray="2 3"/>`
    )
    .join("");

  const axes = MEDDPICC_CATS.map((_, i) => {
    const a = angle(i);
    const x2 = cx + maxR * Math.cos(a);
    const y2 = cy + maxR * Math.sin(a);
    return `<line x1="${cx}" y1="${cy}" x2="${x2.toFixed(1)}" y2="${y2.toFixed(1)}" stroke="${VIZ_PALETTE.border}" stroke-width="0.6"/>`;
  }).join("");

  const total = scores.reduce((a, b) => a + b, 0);
  const max = N * maxScore;

  const svg = `
    <svg class="radar" viewBox="0 0 ${size} ${size}" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <radialGradient id="radarFill" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stop-color="${VIZ_PALETTE.teal}" stop-opacity="0.55"/>
          <stop offset="100%" stop-color="${VIZ_PALETTE.blue}" stop-opacity="0.25"/>
        </radialGradient>
      </defs>
      ${grid}
      ${axes}
      <polygon points="${polyPoints}" fill="url(#radarFill)" stroke="${VIZ_PALETTE.teal}" stroke-width="2" stroke-linejoin="round"/>
      ${scores
        .map((s, i) => {
          const r = (s / maxScore) * maxR;
          const a = angle(i);
          const px = cx + r * Math.cos(a);
          const py = cy + r * Math.sin(a);
          return `<circle cx="${px.toFixed(1)}" cy="${py.toFixed(1)}" r="3.5" fill="${MEDDPICC_COLORS[MEDDPICC_CATS[i]]}" stroke="${VIZ_PALETTE.ink}" stroke-width="1"/>`;
        })
        .join("")}
      ${labels}
    </svg>
  `;

  const wrap = el("div", { class: "viz viz-radar" }, [
    el("div", { class: "viz-head" }, [
      el("h4", {}, "MEDDPICC Deal Health"),
      el("span", { class: "viz-score" }, [
        el("strong", {}, `${total}`),
        document.createTextNode(`/${max}`),
      ]),
    ]),
  ]);
  const svgWrap = el("div", { class: "viz-svg" });
  svgWrap.innerHTML = svg;
  wrap.appendChild(svgWrap);
  return wrap;
}

// ----------------------------------------------------------- 2. Eisenhower Matrix (top 3)

function renderEisenhowerMatrix(actions) {
  const now = new Date();
  const urgency = (a) => {
    if (!a.due_date) return "low";
    const d = new Date(a.due_date);
    if (isNaN(d.getTime())) return "low";
    const days = (d - now) / (1000 * 60 * 60 * 24);
    if (days <= 7) return "high";
    if (days <= 30) return "med";
    return "low";
  };
  const importance = (a) => (a.impact || "med").toLowerCase();
  const high = (v) => v === "high";
  const lowMed = (v) => v === "low" || v === "med";

  const buckets = { do: [], schedule: [], delegate: [], drop: [] };
  (actions || []).forEach((a) => {
    const u = urgency(a);
    const i = importance(a);
    if (high(u) && high(i)) buckets.do.push(a);
    else if (!high(u) && high(i)) buckets.schedule.push(a);
    else if (high(u) && !high(i)) buckets.delegate.push(a);
    else if (lowMed(u) && lowMed(i)) {
      // tie-break: med+med leans Schedule, low+low → Drop
      if (i === "med" || u === "med") buckets.schedule.push(a);
      else buckets.drop.push(a);
    } else buckets.drop.push(a);
  });

  const card = (a) =>
    el("div", { class: "eis-card", title: a.description || "" }, [
      el("div", { class: "eis-title" }, a.title),
      el("div", { class: "eis-meta" }, [
        a.due_date ? el("span", { class: "eis-due" }, a.due_date) : null,
        el("span", { class: "eis-owner" }, (a.owner_name || "").split(" (")[0]),
      ]),
    ]);

  const quadrant = (key, label, sub, klass) =>
    el("div", { class: `eis-q ${klass}` }, [
      el("div", { class: "eis-q-head" }, [
        el("h5", {}, label),
        el("span", { class: "eis-count" }, `${buckets[key].length}`),
      ]),
      el("div", { class: "eis-q-sub" }, sub),
      el("div", { class: "eis-q-body" }, buckets[key].length ? buckets[key].map(card) : [el("div", { class: "eis-empty" }, "-")]),
    ]);

  const wrap = el("div", { class: "viz viz-eisenhower" }, [
    el("div", { class: "viz-head" }, [
      el("h4", {}, "Eisenhower Matrix"),
      el("span", { class: "viz-axis" }, "Urgent →"),
    ]),
    el("div", { class: "eis-grid" }, [
      // Top row: Important
      quadrant("schedule", "Schedule", "Important, not urgent", "q2"),
      quadrant("do", "Do now", "Important & urgent", "q1"),
      // Bottom row: Not important
      quadrant("drop", "Drop / defer", "Neither", "q4"),
      quadrant("delegate", "Delegate", "Urgent, not important", "q3"),
    ]),
    el("div", { class: "eis-yaxis" }, "Important ↑"),
  ]);
  return wrap;
}

// ----------------------------------------------------------- 3. Force-Field Analysis (top 3)

function renderForceField(signals, competitors) {
  const drivingCats = ["Champion", "Identify Pain", "Decision Criteria", "Metrics", "Economic Buyer", "Decision Process"];
  const driving = (signals || [])
    .filter((s) => drivingCats.includes(s.category))
    .map((s) => ({ label: s.category, detail: s.note || s.quote, quote: s.quote }));

  const restraining = [];
  (competitors || []).forEach((c) =>
    restraining.push({ label: c.competitor, detail: c.context, quote: c.context })
  );
  (signals || [])
    .filter((s) => s.category === "Competition")
    .forEach((s) => restraining.push({ label: "Competition", detail: s.note || s.quote, quote: s.quote }));

  const card = (f, side) => {
    const c = el("div", { class: `ff-card ff-card-${side}` });
    const row = el("div", { class: "ff-card-row" }, [
      el("span", { class: "ff-card-cat ff-card-cat-" + side }, f.label),
      f.quote
        ? el(
            "a",
            {
              class: "ff-card-source",
              href: "#",
              title: "Open in transcript",
              "data-quote": f.quote,
              onclick: (ev) => {
                ev.preventDefault();
                if (window.openTranscriptAt) window.openTranscriptAt(f.quote);
              },
            },
            "Source ↗"
          )
        : null,
    ]);
    c.appendChild(row);
    c.appendChild(el("div", { class: "ff-card-detail" }, f.detail || ""));
    return c;
  };

  const drivingCol = el("div", { class: "ff-col ff-col-driving" }, [
    el("div", { class: "ff-col-head ff-col-head-driving" }, [
      el("span", {}, "Driving"),
      el("span", { class: "ff-count" }, ` ${driving.length}`),
    ]),
    ...(driving.length ? driving.map((f) => card(f, "driving")) : [el("div", { class: "ff-empty" }, "No driving forces yet")]),
  ]);
  const restCol = el("div", { class: "ff-col ff-col-restraining" }, [
    el("div", { class: "ff-col-head ff-col-head-restraining" }, [
      el("span", {}, "Restraining"),
      el("span", { class: "ff-count" }, ` ${restraining.length}`),
    ]),
    ...(restraining.length ? restraining.map((f) => card(f, "restraining")) : [el("div", { class: "ff-empty" }, "No restraining forces yet")]),
  ]);
  const pillar = el("div", { class: "ff-pillar" }, [
    el("div", { class: "ff-pillar-line" }),
    el("div", { class: "ff-pillar-deal" }, "DEAL"),
    el("div", { class: "ff-pillar-line" }),
  ]);

  return el("div", { class: "viz viz-force" }, [
    el("div", { class: "viz-head" }, [
      el("h4", {}, "Force-Field Analysis"),
      el("span", { class: "viz-axis" }, `${driving.length} driving · ${restraining.length} restraining`),
    ]),
    el("div", { class: "ff-grid" }, [drivingCol, pillar, restCol]),
  ]);
}

// ----------------------------------------------------------- 4. Power-Interest Grid (functional)

function renderPowerInterestGrid(transcript, attendees) {
  const turns = (transcript && transcript.turns) || [];
  // Heuristic power scoring from speaker label keywords.
  const HIGH_POWER_KW = ["cto", "cio", "vp", "ceo", "head", "director", "md ", "(md", "chief"];
  const MED_POWER_KW = ["lead", "manager", "principal"];
  const counts = {};
  turns.forEach((t) => {
    const sp = (t.speaker || "").trim();
    counts[sp] = (counts[sp] || 0) + 1;
  });
  const speakers = Object.entries(counts).map(([name, n]) => ({ name, count: n }));
  // Add attendees that didn't speak
  (attendees || []).forEach((email) => {
    const guess = email.split("@")[0].replace(/\./g, " ");
    if (!speakers.find((s) => s.name.toLowerCase().includes(guess.split(" ")[0].toLowerCase()))) {
      speakers.push({ name: guess, count: 0 });
    }
  });

  const total = Math.max(1, ...speakers.map((s) => s.count));
  const classify = (s) => {
    const lower = s.name.toLowerCase();
    let power = "low";
    if (HIGH_POWER_KW.some((k) => lower.includes(k))) power = "high";
    else if (MED_POWER_KW.some((k) => lower.includes(k))) power = "med";
    const interest = s.count / total > 0.25 ? "high" : s.count > 0 ? "med" : "low";
    return { power, interest };
  };

  const buckets = { close: [], satisfy: [], inform: [], monitor: [] };
  speakers.forEach((s) => {
    const { power, interest } = classify(s);
    if (power === "high" && interest !== "low") buckets.close.push(s);
    else if (power === "high") buckets.satisfy.push(s);
    else if (interest !== "low") buckets.inform.push(s);
    else buckets.monitor.push(s);
  });

  const stake = (s) => el("span", { class: "pi-chip" }, s.name);

  const cell = (key, label, klass) =>
    el("div", { class: `pi-cell ${klass}` }, [
      el("div", { class: "pi-cell-label" }, label),
      el("div", { class: "pi-cell-body" }, buckets[key].length ? buckets[key].map(stake) : [el("span", { class: "pi-empty" }, "-")]),
    ]);

  return el("div", { class: "viz viz-pi" }, [
    el("div", { class: "viz-head" }, [el("h4", {}, "Power vs Interest")]),
    el("div", { class: "pi-grid" }, [
      cell("close", "Manage closely", "pi-hh"),
      cell("satisfy", "Keep satisfied", "pi-hl"),
      cell("inform", "Keep informed", "pi-lh"),
      cell("monitor", "Monitor", "pi-ll"),
    ]),
  ]);
}

// ----------------------------------------------------------- 5. BANT chips (functional)

function renderBANTChips(signals) {
  // Find first signal whose category + keyword filter matches; returns the matched
  // quote so the chip can link back to its source.
  const findSource = (cats, kws) => {
    const list = signals || [];
    for (const cat of cats) {
      for (const s of list) {
        if (s.category !== cat) continue;
        if (kws.length === 0) return s.quote;
        if (kws.some((k) => (s.quote || "").toLowerCase().includes(k))) return s.quote;
      }
    }
    return null;
  };

  const states = [
    {
      label: "Budget",
      icon: "$",
      source: findSource(["Metrics", "Economic Buyer"], ["million", "thousand", "dollar", "budget", "$"]) || findSource(["Economic Buyer"], []),
    },
    {
      label: "Authority",
      icon: "P",
      source: findSource(["Economic Buyer", "Champion"], []),
    },
    {
      label: "Need",
      icon: "!",
      source: findSource(["Identify Pain"], []),
    },
    {
      label: "Timeline",
      icon: "T",
      source: findSource(["Decision Process"], []),
    },
  ];

  const chip = (s) => {
    const node = el("div", { class: "bant-chip " + (s.source ? "on" : "off") }, [
      el("span", { class: "bant-icon" }, s.icon),
      el("div", { class: "bant-body" }, [
        el("div", { class: "bant-label" }, s.label),
        el("div", { class: "bant-state" }, s.source ? "captured" : "missing"),
      ]),
    ]);
    if (s.source) {
      const link = el(
        "a",
        {
          class: "bant-source",
          href: "#",
          title: "Open in transcript",
          onclick: (ev) => {
            ev.preventDefault();
            if (window.openTranscriptAt) window.openTranscriptAt(s.source);
          },
        },
        "↗"
      );
      node.appendChild(link);
    }
    return node;
  };

  return el("div", { class: "viz viz-bant" }, [
    el("div", { class: "viz-head" }, [el("h4", {}, "BANT")]),
    el("div", { class: "bant-row" }, states.map(chip)),
  ]);
}

// ----------------------------------------------------------- 6. Customer Journey Timeline (functional)

function renderJourneyTimeline(meetings, currentId) {
  const sorted = [...(meetings || [])].sort((a, b) => new Date(a.start_time) - new Date(b.start_time));
  if (!sorted.length) return el("div", {});
  const now = new Date();

  const points = sorted.map((m) => ({
    id: m.id,
    title: m.title,
    date: new Date(m.start_time),
    upcoming: new Date(m.start_time) > now,
    current: m.id === currentId,
  }));

  const minD = points[0].date.getTime();
  const maxD = points[points.length - 1].date.getTime();
  const span = Math.max(1, maxD - minD);

  const dotsHtml = points
    .map((p) => {
      const x = ((p.date.getTime() - minD) / span) * 100;
      const cls =
        "jt-dot " +
        (p.current ? "jt-current " : "") +
        (p.upcoming ? "jt-upcoming" : "jt-past");
      const labelClass = "jt-label" + (p.current ? " jt-label-current" : "");
      const dateLabel = p.date.toLocaleDateString();
      return `
        <div class="jt-marker" style="left: ${x.toFixed(1)}%">
          <div class="${cls}" title="${escapeHtml(p.title)} (${dateLabel})"></div>
          <div class="${labelClass}">${escapeHtml(dateLabel)}</div>
        </div>`;
    })
    .join("");

  const wrap = el("div", { class: "viz viz-journey" });
  wrap.innerHTML = `
    <div class="viz-head"><h4>Customer journey</h4><span class="viz-axis">${points.length} touchpoints</span></div>
    <div class="jt-track">
      <div class="jt-line"></div>
      ${dotsHtml}
    </div>
  `;
  return wrap;
}

// ----------------------------------------------------------- 7. Deal Velocity Funnel (functional)

function renderVelocityFunnel(signals) {
  const cats = (signals || []).map((s) => s.category);
  const has = (c) => cats.includes(c);
  const score = [
    { stage: "Discovery", on: has("Identify Pain") || has("Champion") },
    { stage: "Qualification", on: has("Metrics") && has("Decision Criteria") },
    { stage: "Evaluation", on: has("Decision Process") },
    { stage: "Negotiation", on: has("Economic Buyer") && has("Competition") },
    { stage: "Close", on: cats.length >= 6 },
  ];
  const stages = score.map((s) => s.on);
  // Find current stage = last "on" stage that has all preceding stages on (simple)
  let current = -1;
  for (let i = 0; i < stages.length; i++) {
    if (stages[i]) current = i;
    else break;
  }

  const segs = score
    .map(
      (s, i) =>
        `<div class="vf-step ${i <= current ? "vf-on" : ""} ${i === current ? "vf-current" : ""}">
          <div class="vf-bar"></div>
          <div class="vf-label">${s.stage}</div>
        </div>`
    )
    .join("");

  const wrap = el("div", { class: "viz viz-funnel" });
  wrap.innerHTML = `
    <div class="viz-head"><h4>Deal velocity</h4><span class="viz-axis">${current + 1}/${score.length}</span></div>
    <div class="vf-row">${segs}</div>
  `;
  return wrap;
}

// ----------------------------------------------------------- helpers

function escapeHtml(str) {
  return String(str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
