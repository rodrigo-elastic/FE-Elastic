# FE Copilot demo video v8 (SKO May 2026 - AI B-roll + screen recording)

> 3:00 final cut. v8 adapts v7's script to a hybrid production format:
> **AI-generated B-roll** (Veo 3 / Sora) for the cold open and CTA - showing a stressed Solutions Architect in their morning routine, no on-camera speaking, cinematic close-ups.
> **Screen recording** for the entire demo (autopilot + feature tour).
> **AI voiceover** (ElevenLabs voice clone of you, OR Gemini TTS / Cartesia) over everything.
>
> You never appear on camera speaking. You record the screen, you record one voiceover take (or assemble it from a clone), and you cut it together. **De-risks the entire production.**

---

## Why this format wins

| Risk in v6/v7 | How v8 removes it |
|---|---|
| 8+ takes to nail the cold open delivery | Voice take is editable in 30 seconds, B-roll is generated |
| 50-second autopilot synchronization with your real face on camera | Screen rec timeline is just video editing - voice locks to screen, not to your mouth |
| Lighting / framing / mic / wardrobe consistency across cuts | Zero on-camera = zero variation |
| You sound tired by take 6 | AI voice is identical every render |
| Memorizing 600 words in keynote cadence | You read off a teleprompter, edit out breaths, done |

The trade-off: you lose ~5% on "authenticity" - judges may notice the AI voice - and gain ~25% on "polish + finished feel," which is the bigger rubric dimension. **Net win, especially for hackathon scoring where production quality is a stated criterion.**

**Critical rule**: never show an AI-generated face speaking on camera. Lip sync in 2026's models is detectable and judges will flag it. AI faces appear ONLY in non-speaking B-roll. Voiceover is always over screen recording or static frames.

---

## 1. Asset inventory

### AI-generated video clips (3 total, ~25 s combined)

| Clip ID | Length | Used in | Prompt |
|---|---|---|---|
| **AI-1: Stressed morning** | 8 s | B0 cold open | Detailed prompt below |
| **AI-2: Coffee + screen glance** | 5 s | B3 pivot transition (optional) | Detailed prompt below |
| **AI-3: Calm relief** | 6 s | B9 CTA | Detailed prompt below |

### Screen recordings (1 long take or 8 short clips, ~150 s combined)

Record at 1920×1080 minimum, 60 fps. Use `cmd+shift+5` on Mac with "Show Mouse Pointer" on. Hide all browser extensions. Cursor moves slowly and deliberately.

| Clip ID | Length | Content |
|---|---|---|
| **SR-1: Autopilot** | 50 s | Click "Show me the magic" → full autopilot run → completion card |
| **SR-2: FE Brain + Quick Research** | 15 s | Click FE Brain tab, click a chip, citations render. Then click Quick Research, type a company name. |
| **SR-3: Agent Builder + Kibana proof** | 18 s | Show 3 agent cards, scroll to "Splunk Displacement," click "View agent in Kibana," real Kibana tab opens with the agent. |
| **SR-4: Battlecards + Industries + Demo Data** | 17 s | Click Battlecards, pan grid. Click Industries. Click Demo Data, hover dashboard cards. |
| **SR-5: Workspace** | 13 s | Click Workspace, hover customer card, expand timeline. |
| **SR-6: Workflows + Slack** | 12 s | Click Workflow tab, YAML paints in. Cut to a Slack message screenshot. |

### Voiceover

One continuous voice file at 180 seconds, with these segments matched to the cuts above. ~400-600 spoken words depending on whether you keep autopilot narrated (v7) or silent (v6).

---

## 2. AI B-roll prompts (Veo 3 / Sora 2 ready)

Copy these exactly into your video model. Adjust gender / ethnicity / age to match the persona of "the FE" you want in the audience's head - generic enough to be relatable, specific enough to be cinematic.

### AI-1: Stressed morning (cold open, 8 s)

```
Cinematic close-up shot, 50mm lens, shallow depth of field, soft morning sunlight 
streaming through a window with white curtains. A male Solutions Architect in his 
early thirties sits at a wooden home-office desk wearing a charcoal grey crewneck. 
Slightly disheveled hair. A modern silver watch on his left wrist. He glances at 
the watch - the watch face clearly reads 8:42. He inhales slowly, exhales, runs a 
hand through his hair, looks at his MacBook screen with focused tension. The screen 
glows on his face. Slightly desaturated cinematic color grade, warm highlights, 
cool shadows. Subtle camera handheld. No music, ambient room tone. Realistic. 8 seconds.
```

**Notes**:
- The watch reading "8:42" must be visible - Veo 3 sometimes refuses watch text. If so, generate a wide shot of the watch first as a separate insert clip, then composite.
- Do NOT generate the FE speaking. Mouth closed throughout.

### AI-2: Coffee + screen glance (pivot transition, 5 s, optional)

```
Cinematic over-the-shoulder shot, 35mm lens, the same Solutions Architect seen from 
behind-left as he picks up a coffee mug, takes a sip, looks at his MacBook screen 
which is glowing with a colorful dashboard interface (out of focus background). 
His shoulders relax slightly. The morning light is brighter now, suggesting time 
has passed. Same warm-cool color grade. 5 seconds.
```

**Use case**: cuts between B2 (autopilot) and B3 (pivot) as a 1.5-second transition. Optional; can skip if tight on budget.

### AI-3: Calm relief (CTA, 6 s)

```
Cinematic medium close-up, 50mm lens, the same Solutions Architect leans back in 
his chair, half-smiles softly, eyes still on the screen. The room behind him is 
brighter - full daylight now. He nods to himself once, almost imperceptibly. 
Then he closes the laptop lid gently. The shot ends on his hand resting on the 
closed laptop. Same color grade. 6 seconds.
```

**Use case**: under the CTA voiceover. The "closes the laptop lid" beat lands on "Take it home."

---

## 3. The voiceover script (v8 = v7 verbatim, with pacing markers for AI TTS)

Use ElevenLabs (recommended - best emotion control), Cartesia, or Gemini TTS.

If using ElevenLabs voice clone:
- Record 5 minutes of yourself reading any business article. Upload as Voice Clone.
- Stability: 30%. Similarity: 75%. Style: 25%. Speaker boost: ON.
- Render the script below.

If using Gemini TTS:
- Voice: "Charon" (deeper, authoritative) or "Kore" (warmer).
- Use the `<speak>` SSML wrapper with explicit `<break time="0.5s"/>` tags at every PAUSE.

### Pacing markers used below
- `[BREAK 0.5s]` - half-beat pause
- `[BREAK 1s]` - full beat pause
- `[BREAK 1.5s]` - long pause (the cold open's "Eighteen minutes" gets this)
- `[SLOW]` - drop pace 15% for the next sentence
- `[WARM]` - soften tone, slight smile in voice (CTA only)

---

### B0. Cold open (0:00 - 0:13) - over AI-1 (Stressed morning)

```
[VISUAL: AI-1 plays, watch close-up at 0:04 marker]

It's Tuesday morning, eight forty-two,
and your customer call with Searchlight Capital is at nine.
[BREAK 0.5s]
You haven't read their last earnings,
you haven't priced the Splunk renewal sitting on their desk,
and you've got another customer call right after this one.

[BREAK 0.5s]

Eighteen minutes.

[BREAK 1.5s]

Every Solutions Architect, every Customer Architect at Elastic, knows this morning.
```

### B1. Promise + Kulkarni (0:13 - 0:30) - over screen recording of FE Copilot dashboard idle

```
[VISUAL: Cut to SR - FE Copilot home dashboard, cursor hovers near "Show me the magic" button]

We do this work by hand - every discovery, every Proof of Value -
and back in December, Ash Kulkarni said one line at re:Invent that stuck with me:
[BREAK 1s]
"In the world of AI, it's all about context engineering."
[BREAK 0.5s]
But you can't context-engineer anything in eighteen minutes,
not when you're between two customer calls.

[VISUAL: Cursor clicks "Show me the magic." Autopilot fires.]

So I built FE Copilot to do it for you. Watch.
```

### B2. Autopilot narrated (0:30 - 1:20) - over SR-1

```
[VISUAL: SR-1 - autopilot runs the full 50-second sequence]

Watch what happens.
One click - and FE Copilot starts pulling the customer's context together.

[BREAK 0.5s - brief renders]

First, the brief comes in -
their last earnings, their stack, the Splunk renewal on their desk,
and the AutoOps cluster signals showing how their environment is actually running right now -
all grounded in their data.

[BREAK 0.5s - Field Assistant renders]

Then the Field Assistant writes the discovery plan for you -
five questions, sequenced -
buyer, Splunk pain, DORA gap, champion, decision window.

[BREAK 1s - let the questions sit]

And while you're reading, it's building you the agent -
Splunk Displacement,
with the right tools selected, deployed straight into your Kibana cluster.

[BREAK 1s - completion card lands]

[SLOW] That agent did not exist a minute ago.
```

### B3. Pivot (1:20 - 1:35) - over AI-2 (optional) then SR home dashboard

```
[VISUAL: AI-2 plays for 1.5 s, cuts to SR home view]

That was fifty seconds.

[BREAK 0.5s]

The idea is simple: this is meant to be the go-to place,
so a Solutions Architect can prep a discovery call for a new prospect
and a Customer Architect can walk into a back-to-back meeting already in sync
with what the customer needs -
without flipping through twelve tabs and a Salesforce note from three weeks ago.

Let me show you the moving parts.
```

### B4. FE Brain + Quick Research (1:35 - 1:50) - over SR-2

```
[VISUAL: SR-2]

When you don't know an answer, you usually ping #ask-elastic and wait -
sometimes thirty minutes, sometimes the rest of the day.
Here, you ask, and ten seconds later you have the answer,
cited, grounded in Elastic's docs and your customer's data -
no hallucinations, just thirteen hundred chunks of context, ready when you need it.

Quick research works the same way for a brand new prospect -
type the company name and you get an FSI banking research card with their pain,
their stack, their renewal window, ready before the call starts.

Context engineering, in your hands.
```

### B5. Agent Builder + "View agent in Kibana" (1:50 - 2:08) - over SR-3

```
[VISUAL: SR-3 - agent cards visible]

I didn't build agents to replace the Field Engineer -
I built three to stand next to you, and the demo just built a fourth one live.

[BREAK 0.5s]

RFP Responder. Migration Specialist. Compliance Pursuit.

[VISUAL: scroll, "Splunk Displacement" appears]

That one wasn't here a minute ago.

[BREAK 0.5s]

And here's the part most demos cannot prove:

[VISUAL: click "View agent in Kibana" - real Kibana tab opens]

These agents don't live in this app - they live in your Kibana cluster.
Your data, your tenant, your moat.
```

### B6. Battlecards + Industries + Demo Data (2:08 - 2:25) - over SR-4

```
[VISUAL: SR-4]

When the customer says "Splunk," you have eight seconds before the room shifts -
and we have thirty-one battlecards ready, ranked by marketshare:
Splunk, Datadog, CrowdStrike, AWS OpenSearch.

Twenty industries. Eighty percent of the accounts you'll touch this year -
each one ships with demo data, a story, and two dashboards:
one for the FE that explains the use case,
and one customer-facing version you can hand off in a discovery call.

[BREAK 0.5s]

Whatever industry walks in the door, you're already standing on the answer.
```

### B7. Workspace + Pre/Post-meeting summaries (2:25 - 2:38) - over SR-5

```
[VISUAL: SR-5]

Workspace. Salesforce stays the system of record;
this is where the back-to-back-meeting reality lives.
One card per customer.
Pre-meeting brief, the live transcript, the post-meeting summary,
the follow-up email, the POV plan - all of it on a timeline.

[BREAK 0.5s]

So when your nine o'clock ends and your nine-thirty starts,
you don't switch tabs - you switch cards.
```

### B8. Workflows + Weekly Forecast + Slack (2:38 - 2:50) - over SR-6

```
[VISUAL: SR-6 - YAML, then Slack screenshot]

[SLOW] Here's the part most demos miss.

Reasoning lives in Agent Builder.
Deterministic actions live in Elastic Workflows.
The agent thinks; the workflow does.

So when a transcript drops, the agent runs, Salesforce updates,
the weekly forecast slide is generated automatically,
and a summary of every action with this customer
lands in Slack before your next call starts -
so you walk in already in sync, instead of digging through emails and Salesforce notes.
```

### B9. CTA (2:50 - 3:00) - over AI-3 (Calm relief)

```
[VISUAL: AI-3 plays]

[WARM] Six hours a week, every FE, every week -

[BREAK 0.5s]

that's what we just took back.

[BREAK 0.5s]

[VISUAL: AI-3 ends on closed laptop. Cut to title card with URL.]

MIT licensed.
github dot com slash rodrigo dash elastic slash F E dash Elastic.

[BREAK 0.5s]

Take it home.
Move pilots to real-world impact.
```

---

## 4. Production sequence (the day-of plan)

If you're producing this in one sitting, do it in this order:

1. **Generate all 3 AI clips first** (AI-1, AI-2, AI-3). Veo 3 / Sora can take 5-15 minutes per render. Queue all three immediately. Pick the best take from 2-3 generations of each.
2. **Record screen captures** while waiting on AI renders. Do SR-1 (autopilot) first since it's the longest and most fragile. Re-record any clip where the cursor pauses awkwardly.
3. **Generate voiceover** last, AFTER you have final SR-1 timing locked. The voiceover pacing for B2 must match the actual autopilot run - don't render the voice until you know the screen recording is final.
4. **Assemble in Final Cut / Premiere / DaVinci**:
   - Drop voiceover on the bottom track. Lock it to 180 s exactly.
   - Drop AI clips in B0, optional B3, and B9.
   - Drop screen recordings in B1, B2, B3-B8.
   - Add subtle background music: any free royalty-free "tech ambient" loop at -28 dB. Cut music out completely on B0 and B9 (let voice + ambient room tone breathe).
   - Add captions/subtitles. Most judging panels watch with sound off at first. Captions are required.
5. **Export at 1080p 60fps, H.264, ~20 Mbps.** YouTube/Vimeo deliverable.

Total production time, end-to-end: 4-6 hours including iteration. Compare that to v6/v7 which need ~10 hours of recording + retake + edit time.

---

## 5. Voice coaching for the AI clone (if using ElevenLabs)

When you record the 5-minute clone source:

- Read **as if you're explaining to a smart colleague** at a coffee shop. Not presenting on stage.
- The AI clones your **emotional baseline**. If your source recording is energetic, every line will be energetic. Read with the same calm-but-engaged tone you want in the final video.
- Include a few sentences that match the hardest beats: read a sentence with a long pause, read a sentence quietly, read a sentence with a small smile. The clone uses this range.

If your render comes back flat, regenerate with Stability dropped to 20% - it'll add more variation but also more risk of weirdness. 30% is the sweet spot.

---

## 6. The single sentence that summarizes v8

> v6 bet on your performance. v7 bet on your pacing. v8 bets on your edit - and that's the bet a hackathon judge actually rewards, because the rubric explicitly weights production quality and you're now competing on that axis with a studio-grade toolkit, not a webcam.

---

## 7. What to keep ready for the live Q&A

Even though you don't appear on camera, the live Q&A after the submission video is on you in person. Keep these three lines memorized - they're the ones the AI voice can't deliver as warmly as you can:

1. "I built FE Copilot because every Tuesday morning, I lived this exact scene."
2. "The agents don't live in the app - they live in your Kibana cluster, on your data, in your tenant."
3. "Move pilots to real-world impact."

Three lines. Drill them. Everything else, the video did for you.
