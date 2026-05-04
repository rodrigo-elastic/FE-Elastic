# Autopilot ("Show me the magic")

The autopilot is the hero one-click demo for FE Copilot. The judge clicks a single
button on the homepage and watches the entire pipeline run end-to-end without the
presenter typing anything. Designed for the hackathon stage.

## What the user sees

1. Big rounded gradient button on the hero ("Show me the magic", 30s pill).
2. Click. The button locks, a countdown ticks, the page dims into a stage with a
   glassmorphic caption bar at the top, a 7-step progress dock on the right, and
   a panel showing live UI in an iframe.
3. Seven steps run in order:
   1. **Intro (0 to 2s)** confetti and the first caption.
   2. **Quick Research (2 to 7s)** real `POST /agents/pre-meeting/ad-hoc` for
      Banco Atlántico on Haiku 4.5. Spinner shown until the brief lands.
   3. **Brief view (7 to 12s)** loads `/meeting.html?id=<returned>&adhoc=1` in
      the panel iframe so judges see the rendered brief.
   4. **Field Assistant (12 to 18s)** real `POST /agent-builder/converse` with
      a chained prompt that triggers `fec_poc_plan` and `fec_cost_calc`.
   5. **Agent Builder (18 to 24s)** opens `/agent-builder.html` in the panel
      and auto-types a prompt about the Black Friday outage to show tool calls.
   6. **Workflow loop (24 to 29s)** opens `/workflow-demo.html` in the panel
      and fires `POST /workflows/demo-fire` to demonstrate the agent to ES to
      alerting rule to webhook to agent loop.
   7. **Recap (29 to 30s)** confetti, "Demo complete" card with stats and three
      actions: Watch again, View video, Open Kibana.

## Files owned by the autopilot

- `frontend/assets/js/autopilot.js` orchestration script (vanilla JS, IIFE,
  exposes `window.FEAutopilot`).
- `frontend/assets/css/autopilot.css` overlay, dock, caption bar, completion
  card, confetti, and CTA styling.
- `frontend/index.html` adds the CSS link, the script tag, and mounts the
  hero CTA into `section.hero` programmatically.
- `docs/autopilot.md` this document.

The autopilot does **not** modify any backend code, env, or non-listed file. It
drives endpoints that already exist:

- `POST /api/v1/agents/pre-meeting/ad-hoc`
- `POST /api/v1/agent-builder/converse`
- `POST /api/v1/workflows/demo-fire`

## Cost per run

Each autopilot run executes two real LLM calls:

| Call | Model | Approx cost |
| --- | --- | --- |
| Pre-meeting ad-hoc brief (Banco Atlántico) | Haiku 4.5 | $0.03 to $0.05 |
| Field Assistant chained POC plan plus TCO calc | Haiku 4.5 (server default) | $0.02 to $0.05 |

Total expected cost: **$0.05 to $0.10 per autopilot run**. The script never
calls `/tools/*` directly and uses small, focused inputs so the worst-case is
capped well below ten cents. The Workflow `demo-fire` step indexes a tiny
synthetic transcript and only triggers downstream LLM work once the alerting
rule fires (out of scope for the 30s stage demo).

## Cancellation and timeouts

- **Esc** cancels at any step and dismisses the overlay.
- **Stop button** in the progress dock has the same effect.
- Each step has a hard ceiling (15 to 22 seconds depending on which network
  call is in flight). On timeout the dock marks the step as failed and the
  caption shows "Step X timed out. Continuing." then advances.
- Cancellation uses a single `AbortController` shared across all in-flight
  fetches so no zombie requests linger.

## Persistence

The five most recent runs are saved to `localStorage` under
`fec.autopilot.lastRun` with the elapsed time, captured meeting id, per-call
durations, the reason it stopped, and any failures. The "Watch again" button
on the completion card simply re-runs `start()`.

## Accessibility

- Caption bar has `role="status"` plus `aria-live="polite"` and
  `aria-atomic="true"` so screen readers narrate each step.
- Progress dock is `role="region"` with `aria-label="Autopilot progress"`.
- Stop button is keyboard-reachable; Esc is the documented shortcut.
- Completion card is `role="dialog"` with `aria-modal="true"`.
- All animations honour `prefers-reduced-motion`.

## Mobile

The autopilot button and overlay are **hidden on viewports at or below 768px**.
The 30-second run is desktop-only by design (it requires multiple iframes and
a side dock). On mobile, clicking the equivalent JS entry point shows an
alert directing the user to a laptop. This is documented behaviour, not a bug.

## Triggering programmatically

```js
window.FEAutopilot.start();   // start the run
window.FEAutopilot.stop();    // cancel a running demo
```

This is useful for cue cards, slash-command shortcuts, or Cypress tests.

## Failure modes tested

- **Backend offline** the ad-hoc brief fetch aborts after 18 seconds, the dock
  marks step 2 as failed, the caption shows "timed out, continuing", and the
  remaining steps still play their captions and panels (Agent Builder and
  Workflow steps degrade gracefully because they do not depend on the brief id
  beyond step 3).
- **Agent Builder not live** the `/converse` POST returns 409. The autopilot
  catches the error, marks step 4 as failed, advances. No popup is shown.
- **User hits Esc** AbortController cancels in-flight fetches, the overlay
  dismisses inside 400ms, and the run is saved with `reason: "user"`.
- **Mobile click** the alert fires and `start()` returns immediately without
  mutating state.

## Design intent

This is the single biggest demo moment for the hackathon. Judges watching a
presenter type get bored. Judges watching an autonomous run see the entire
product story (multi-source research, master agent chaining, MCP tools, the
ES alerting loop) in 30 seconds with zero typing. That is the moment that
wins primer lugar.
