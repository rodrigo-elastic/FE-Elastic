# FE Copilot demo video v6 (SKO May 2026 - conversational tour)

> 3:00 single take. v6 reverts to the 50-second silent autopilot (v4.1's runtime, which the user prefers) and rewrites every spoken beat to flow like one person telling a story to a colleague - not a feature tour with bullet points.
>
> v6's wager: the judges will reward a tour that **sounds like a real Solutions Architect explaining their workflow to another SA**, not a 30-second-spot voiceover. Sentences chain into each other. No isolated taglines. Every feature gets named in service of a problem the audience has lived.

---

## What changed vs v5

| Beat | v5 | v6 | Why |
|---|---|---|---|
| B2 Autopilot | 30 s, 2 narration lines | **50 s, fully silent** | User asked for 50 s back. The silence is the speaker. Trust it. |
| B3 Pivot | "Thirty seconds." | "Fifty seconds." + a real positioning line: this is the **go-to place** so SAs and CAs can stop juggling tabs between back-to-back customer meetings. | Names the value proposition out loud, not just shows it. |
| B5 Agent Builder close | "These agents don't live in this app. They live in your Kibana cluster." | Same line, but the next click is **literally "View agent in Kibana"** and the real Kibana tab opens - proving the connection in one click instead of describing it. | Reduces narration. Lets the demo prove the claim. |
| B6 New beat | Battlecards only | Battlecards + Industries + **Demo Data dashboards (FE story view AND customer-facing view, across many industries)** | Demo data is a real differentiator the v5 script never named. The dashboards-for-both-sides framing is the reusability story. |
| B7 Workspace | Brief / Transcript / Email / POV plan | Same artifacts, plus pre-meeting summaries and post-meeting summaries explicitly named, woven into the back-to-back-meetings problem the cold open set up. | The cold open's pain was switching context between customers. B7 is where the payoff line lands. |
| B8 Workflows | "The agent thinks. The workflow does." + coffee close | Same Exner framing, but now Workflows is named as the thing that **summarizes the last meetings, the jobs to be done, and pipes it to Slack** - so the FE doesn't have to dig through emails and Salesforce notes before every call. | The cold open's villain was tab-switching and email digging. Workflows is the answer. Close the loop. |
| Pacing | Staccato sentences, lots of single-line beats | Sentences chain into each other. Three or four conjunctions per beat. Reads like one human talking, not a teleprompter. | User feedback: less choppy, more conversational. |
| Total spoken | 353 words | 405 words | More speaking, less silence after the autopilot. The 50 s is preserved; the extra words come from B7 and B8. |

---

## 1. Story arc (v6 timing)

| Beat | Story role | Time | Energy |
|---|---|---|---|
| B0 Cold open | Frame: the back-to-back morning every SA/CA knows | 0:00 - 0:13 | Intimate, almost confessional |
| B1 Promise | Kulkarni + reveal | 0:13 - 0:30 | Quiet authority |
| B2 Autopilot | Silent demo | 0:30 - 1:20 | Hands flat. Eyes on screen. |
| B3 Pivot | Name what just happened, name the go-to-place positioning | 1:20 - 1:35 | Warm, conversational |
| B4 FE Brain + Quick Research | Knowledge proof, woven into "we have 14 customers in a single morning" | 1:35 - 1:50 | Punchy, conversational |
| B5 Agent Builder + Kibana proof | Click "View agent in Kibana" - the agent really exists | 1:50 - 2:08 | Generous, then proof |
| B6 Battlecards + Industries + Demo Data | The ammunition story, plus the dashboards-for-both-sides | 2:08 - 2:25 | Crisp |
| B7 Workspace + Pre/Post-meeting summaries | Where the back-to-back-meeting context lives | 2:25 - 2:38 | Warm, human |
| B8 Workflows + Weekly Forecast Slides + Slack | The automation layer that closes the loop | 2:38 - 2:50 | Slow, deliberate |
| B9 CTA | Hand the baton | 2:50 - 3:00 | Eye contact, half-smile |

50 s of silent autopilot is preserved. The CTA stays at 10 s because the motif is now distributed across the script (the back-to-back-meeting callback), not concentrated in the close.

---

## 2. The script

Square brackets are operator cues. Do NOT speak them. `[PAUSE]` means stop, breathe, hold.

### B0. Cold open (0:00 - 0:13)

```
[CAM B. Lean forward 2 cm. Quiet, almost confessional.]

It's Tuesday morning, eight forty-two,
and your customer call with Searchlight Capital is at nine.

You haven't read their last earnings,
you haven't priced the Splunk renewal sitting on their desk,
and you've got another customer call right after this one.

[PAUSE half a beat.]

Eighteen minutes.

[PAUSE one full beat. Hold the eye contact.]

Every Solutions Architect, every Customer Architect at Elastic, knows this morning.
```

**Why it works**: One run-on sentence, the way a person actually talks when they're describing a stressful morning. The "another customer call right after this one" is new in v6 - it plants the back-to-back-meetings problem that pays off in B7.

### B1. Promise (0:13 - 0:30)

```
[CUT to CAM A. Sit back. Smile lifts the eyes, not the mouth.]

We do this work by hand - every discovery, every Proof of Value -
and back in December, Ash Kulkarni said one line at re:Invent that stuck with me:

[PAUSE.]

"In the world of AI, it's all about context engineering."

[PAUSE half a beat.]

But you can't context-engineer anything in eighteen minutes,
not when you're between two customer calls.

[Click the "Show me the magic" button. Hand returns to the desk.]

So I built FE Copilot to do it for you. Watch.
```

**Why it works**: The Kulkarni quote is preserved verbatim. The line that follows ("you can't context-engineer anything in eighteen minutes, not when you're between two customer calls") binds the quote to the cold open's pain in one breath. "I built FE Copilot to do it for you" is warmer than "So I built FE Copilot. One click. Watch." - it puts the audience inside the value, not next to it.

### B2. Autopilot (0:30 - 1:20, 50 seconds, SILENT)

```
[CAM A locked wide. Hands flat on the desk, NOT on the keyboard.]
[The autopilot runs the full sequence: hook, quick-research, brief renders with AutoOps cluster signals, Field Assistant questions, Agent Builder creates "Splunk Displacement" live, recap card.]

[At 0:50 small confident nod when the brief renders.]
[At 1:05 small smile when the Field Assistant displacement questions appear.]
[At 1:12 lean slightly when "Splunk Displacement" lights up in the agent list.]
[At 1:18 lean back when the completion card lands. Let the silence breathe.]

[Do NOT speak. Do NOT touch the keyboard. The autopilot is the speaker.]
```

**Why it works**: 50 seconds of silence is the single most counterintuitive choice in the whole video, and it is exactly what makes it land. Every other demo has a voice over the top. Yours doesn't. The judge feels the difference in their gut. **Trust it. Do not break.**

### B3. Pivot (1:20 - 1:35)

```
[CUT to CAM B at 1:20. Smile lands first. One full beat of eye contact.]

Fifty seconds.

[PAUSE half a beat.]

A brief, a discovery plan, a Splunk TCO,
and a real agent built into Kibana - all of it, while you finished your coffee.

[Lean forward slightly. Conversational, not pitching.]

The idea is simple: this is meant to be the go-to place,
so a Solutions Architect can prep a discovery call for a new prospect
and a Customer Architect can walk into a back-to-back meeting already in sync
with what the customer needs - without flipping through twelve tabs
and a Salesforce note from three weeks ago.

Let me show you the moving parts.
```

**Why it works**: "Fifty seconds" is a single load-bearing word that does the work of a paragraph - it names what the audience just watched without explaining it. The "go-to place" line is the **positioning thesis** of the whole demo and v6 puts it in plain English, not slogan-speak. "Without flipping through twelve tabs and a Salesforce note from three weeks ago" is the line every CA in the audience nods at because they did exactly that an hour ago.

### B4. FE Brain + Quick Research (1:35 - 1:50)

```
[CUT to CAM A. Click FE Brain tab.]

When you don't know an answer, you usually ping #ask-elastic and wait -
sometimes thirty minutes, sometimes the rest of the day.

[Click a chip. Citations begin to render.]

Here, you ask, and ten seconds later you have the answer,
cited, grounded in Elastic's own docs and your customer's data -
no hallucinations, just thirteen hundred chunks of context, ready when you need it.

[Hold on the citation cards for one full beat.]

Quick research works the same way for a brand new prospect -
type the company name and you get an FSI banking research card with their pain,
their stack, their renewal window, ready before the call starts.

Context engineering, in your hands.
```

**Why it works**: One line ties FE Brain ("known customer, known question") to Quick Research ("new prospect, cold call") so both features land as **two faces of the same idea** instead of two separate features. The Kulkarni callback at the end ("context engineering, in your hands") rhymes with B1.

### B5. Agent Builder + Kibana proof (1:50 - 2:08)

```
[CUT to CAM A. Click Agent Builder tab.]

I didn't build agents to replace the Field Engineer -
I built three to stand next to you,
and the demo just built a fourth one live.

[Click through the three agent cards.]

RFP Responder. Migration Specialist. Compliance Pursuit.

[Scroll down. "Splunk Displacement" sits in the list - built 50 seconds ago.]

That one wasn't here a minute ago.

And here's the part most demos cannot prove:

[Click "View agent in Kibana." The real Kibana Agent Builder tab opens, the agent is there.]

These agents don't live in this app - they live in your Kibana cluster.
Your data, your tenant, your moat.
```

**Why it works**: "And the demo just built a fourth one live" is the seam between the autopilot and Agent Builder, said as one connected thought instead of two. The single click to "View agent in Kibana" replaces a sentence of explanation - the demo proves the claim instead of you asserting it. The "Your data, your tenant, your moat" triplet is the rule of three, used the way every great keynote uses it.

### B6. Battlecards + Industries + Demo Data (2:08 - 2:25)

```
[CUT to CAM A. Click Battlecards tab.]

When the customer says "Splunk," you have eight seconds before the room shifts -
and we have thirty-one battlecards ready, ranked by marketshare:
Splunk, Datadog, CrowdStrike, AWS OpenSearch.

[Click Industries tab. Then click Demo Data tab.]

Twenty industries. Eighty percent of the accounts you'll touch this year.
Each one ships with demo data, a story, and **two dashboards** -
one for the FE that explains the use case,
and one customer-facing version you can hand off in a discovery call -
so you're not building synthetic data the night before a demo.

[Hold on a dashboard for one beat.]

Whatever industry walks in the door, you're already standing on the answer.
```

**Why it works**: Demo Data was a major hidden feature in v5. v6 names it explicitly and frames it as "two dashboards per industry - one for you, one for the customer," which is the killer reusability story. The "Whatever industry walks in the door, you're already standing on the answer" line is the same balance image as v4 but now applies to industries, not just battlecards.

### B7. Workspace + Pre/Post-meeting summaries (2:25 - 2:38)

```
[CUT to CAM A. Click Workspace tab. Hover over a customer card.]

Workspace. Salesforce stays the system of record;
this is where the back-to-back-meeting reality lives.

One card per customer.
Pre-meeting brief, the live transcript, the post-meeting summary,
the follow-up email, the POV plan - all of it on a timeline.

[Hold for one beat. Click into a card.]

So when your nine o'clock ends and your nine-thirty starts,
you don't switch tabs - you switch cards.
```

**Why it works**: The cold open planted "another customer call right after this one." B7 pays it off with "you don't switch tabs - you switch cards." That bookend earns the rubric points without you ever calling out "look, a bookend." Pre-meeting and post-meeting summaries are now named explicitly, in the same breath as the artifact list.

### B8. Workflows + Weekly Forecast + Slack (2:38 - 2:50)

```
[CUT to CAM B. Slow the cadence by 15 percent.]

Here's the part most demos miss.

Reasoning lives in Agent Builder.
Deterministic actions live in Elastic Workflows.
The agent thinks; the workflow does.

[CUT to CAM A. Click Workflow tab. The YAML paints in.]

So when a transcript drops, the agent runs, Salesforce updates,
the weekly forecast slide is generated automatically,
and a summary of every action with this customer
lands in Slack before your next call starts -

so you walk in already in sync, instead of digging through emails and Salesforce notes.
```

**Why it works**: This is the densest beat in the script. v6 puts Workflows, Weekly Forecast Slides, AND the Slack-summary-before-the-next-call into one chained sentence - three features, one breath, all in service of the back-to-back-meeting villain from the cold open. "So you walk in already in sync, instead of digging through emails and Salesforce notes" is the line every judge will quote later because it names the daily indignity of an SA's job in fourteen words.

### B9. CTA (2:50 - 3:00)

```
[CUT to CAM B. Slight smile. Hold one full beat before speaking.]

Six hours a week, every FE, every week -

[PAUSE.]

that's what we just took back.

[PAUSE.]

MIT licensed. github dot com slash rodrigo dash elastic slash F E dash Elastic.

[PAUSE.]

Take it home.
Move pilots to real-world impact.

[Hold eye contact for 1 full second. Do NOT cut early.]
```

**Why it works**: The CTA is intentionally a touch shorter in v6 because the "took back" emotional weight is now distributed across B7 ("you don't switch tabs - you switch cards") and B8 ("instead of digging through emails and Salesforce notes"). The close doesn't have to do all the work alone.

---

## 3. Camera cut map (v6)

| Time | Cam | Hold | Beat |
|---|---|---|---|
| 0:00 - 0:13 | B | 13 s | Cold open |
| 0:13 - 0:30 | A | 17 s | Promise + Kulkarni |
| 0:30 - 1:20 | A | 50 s | Autopilot, silent |
| 1:20 - 1:35 | B | 15 s | Pivot + go-to-place positioning |
| 1:35 - 1:50 | A | 15 s | FE Brain + Quick Research |
| 1:50 - 2:08 | A | 18 s | Agent Builder + "View agent in Kibana" click |
| 2:08 - 2:25 | A | 17 s | Battlecards + Industries + Demo Data dashboards |
| 2:25 - 2:38 | A | 13 s | Workspace, pre/post summaries |
| 2:38 - 2:50 | A/B | 12 s | Workflows + Weekly Forecast + Slack |
| 2:50 - 3:00 | B | 10 s | CTA |

---

## 4. Pacing target

405 spoken words across 130 spoken seconds = **187 wpm**, brisk-but-not-rushed.
130 spoken + 50 silent = exactly 180 seconds. Three minutes on the nose.

If you find yourself running long, the safe trims (in order of preference):
1. Drop "RFP Responder. Migration Specialist. Compliance Pursuit." in B5 - the names are not the point; the live-built fourth agent is.
2. Drop "Splunk, Datadog, CrowdStrike, AWS OpenSearch" in B6 - the number 31 carries the weight.
3. Trim B6's "so you're not building synthetic data the night before a demo" - the line is great but it's saveable for Q&A.

Do NOT trim:
- The cold open (the entire video stands or falls on it)
- The 50-second silence (it's the differentiator)
- "View agent in Kibana" click (the proof point)
- "You don't switch tabs - you switch cards" (the bookend payoff)
- The CTA (the handoff)

---

## 5. Body language cues (only changed beats)

- **B3 (pivot)**: "Without flipping through twelve tabs and a Salesforce note from three weeks ago" - small head shake, half a smile. This is the line where the audience exhales and feels seen. Hold their gaze for one beat after the line. Don't rush past it.
- **B5 ("View agent in Kibana" click)**: When you click the button, do NOT look at the screen. Hold eye contact with the camera. The Kibana tab opens in your peripheral vision. The judge feels the confidence before they see the result.
- **B7 ("You don't switch tabs - you switch cards")**: Mirror the verb with your hand - small left-hand gesture on "switch tabs," small right-hand gesture on "switch cards." The two-handed beat lands the contrast better than tone alone.
- **B8 ("So you walk in already in sync...")**: Hand to chest height, palm up. This is the line you want the audience to remember. Treat it the way you treat "Take it home" in the CTA - same warmth, same eye contact.

---

## 6. The single sentence that summarizes v6

> v5 told the judge what FE Copilot does. v6 tells the judge what their Tuesday is going to feel like, in a voice that sounds like a Solutions Architect explaining their actual workflow to another Solutions Architect.

That voice is the entire competitive advantage of this submission. Every keynote-grade demo has it. Most hackathon demos don't. Drill the cold open, trust the silence, land the bookend, and you walk away with first place.

---

## 7. Thirty-second rehearsal (v6)

If you only have time for one practice run, drill the cold open and the bookend.

```
B0: "It's Tuesday morning, eight forty-two,
     and your customer call with Searchlight Capital is at nine.
     You haven't read their last earnings,
     you haven't priced the Splunk renewal sitting on their desk,
     and you've got another customer call right after this one.
     Eighteen minutes.
     Every Solutions Architect, every Customer Architect at Elastic, knows this morning."

B7: "So when your nine o'clock ends and your nine-thirty starts,
     you don't switch tabs - you switch cards."

B8: "So you walk in already in sync,
     instead of digging through emails and Salesforce notes."
```

If those three moments land, the take is locked. Everything else is supporting.
