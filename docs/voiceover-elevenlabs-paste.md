# Voiceover - copy-paste into ElevenLabs (or Cartesia / Gemini)

> Output for the v8 video script. Total target runtime: **180 seconds**.
> Every pause is encoded with `<break time="X.Xs"/>` and every emotional cue with `[tag]` (ElevenLabs v3 audio tags).
> Paste **the whole block in section 3** into one ElevenLabs Studio project. Tune the speed slider once at the end.

---

## 1. Quick start - which tool + which settings

### Recommended: ElevenLabs Studio (best for this script)
- **Model**: `eleven_v3` (supports `[tag]` audio cues + best emotion control)
- **Voice**: your voice clone (record 5 min of yourself reading any business text, upload as Instant Voice Clone). If you skip the clone, use `Brian` (warm authoritative male) or `Daniel` (calm professional male).
- **Settings panel** (right side of Studio):
  - Stability: **35**  (lower = more emotion, higher = more flat)
  - Similarity: **75**
  - Style: **20**
  - Speaker boost: **ON**
  - Speed: **1.00** (we'll tune at the end)

### Alternative 1 - Cartesia Sonic
- Voice: `Newsman` or `Calm Lady` clone
- Speed: 1.0
- Same `<break time="X.Xs"/>` tags work
- Audio tags do NOT work - strip them before pasting

### Alternative 2 - Google Gemini 2.5 TTS
- Voice: `Charon` (deep) or `Kore` (warm)
- Speed: 1.0
- Wrap script in `<speak>...</speak>` SSML
- `<break time="X.Xs"/>` works
- Audio tags do NOT work - strip them

### Alternative 3 - OpenAI `tts-1-hd`
- Voice: `onyx` or `echo`
- No SSML support - replace every `<break time="0.5s"/>` with two periods `..` and every `<break time="1s"/>` with three periods `...` and every `<break time="1.5s"/>` with `... ...`. The TTS will pause naturally.
- Strip audio tags.

---

## 2. Per-beat target lengths (for fine-tuning the speed slider)

After your first render, check each beat's actual duration vs target. If a beat runs over, increase Speed to 1.05-1.10. If it runs under, drop to 0.95.

| Beat | Target | Words | Notes |
|---|---|---|---|
| B0 Cold open | 13 s | 53 | Slow, hushed. Audio tag: `[hushed]`. Speed 0.95. |
| B1 Promise + Kulkarni | 17 s | 60 | Normal pace, but Kulkarni quote gets `[deeply]`. |
| B2 Autopilot narrated | 50 s | 95 | This is the longest beat. Speed 1.0. The two long breaks do the heavy lifting. |
| B3 Pivot | 15 s | 50 | Brisk warm. Speed 1.05. |
| B4 FE Brain + Quick Research | 15 s | 75 | Tight. Speed 1.05-1.10. |
| B5 Agent Builder | 18 s | 65 | Normal. Speed 1.0. |
| B6 Battlecards/Industries/Demo Data | 17 s | 70 | Brisk. Speed 1.05. |
| B7 Workspace + summaries | 13 s | 50 | Normal. Speed 1.0. |
| B8 Workflows + Slack | 12 s | 55 | Densest. Speed 1.10. |
| B9 CTA | 10 s | 40 | Slow, warm. Speed 0.95. `[smiles]` on "Take it home". |

**Total**: 613 words / 180 s. If your render comes in at 175 s, perfect. If 195 s, raise master speed to 1.08 globally.

---

## 3. THE SCRIPT - paste this entire block into ElevenLabs Studio

```
[hushed] It's Tuesday morning, eight forty-two, and your customer call with Searchlight Capital is at nine. <break time="0.4s"/> You haven't read their last earnings, you haven't priced the Splunk renewal sitting on their desk, and you've got another customer call right after this one. <break time="0.6s"/> Eighteen minutes. <break time="1.5s"/> Every Solutions Architect, every Customer Architect at Elastic, knows this morning. <break time="1s"/>

We do this work by hand - every discovery, every Proof of Value - and back in December, Ash Kulkarni said one line at re:Invent that stuck with me: <break time="0.8s"/> [deeply] "In the world of AI, it's all about context engineering." <break time="0.6s"/> But you can't context-engineer anything in eighteen minutes, not when you're between two customer calls. <break time="0.5s"/> So I built FE Copilot to do it for you. Watch. <break time="0.8s"/>

Watch what happens. <break time="0.4s"/> One click - and FE Copilot starts pulling the customer's context together. <break time="2s"/>

First, the brief comes in - their last earnings, their stack, the Splunk renewal on their desk, and the AutoOps cluster signals showing how their environment is actually running right now - all grounded in their data. <break time="2s"/>

Then the Field Assistant writes the discovery plan for you - five questions, sequenced - buyer, Splunk pain, DORA gap, champion, decision window. <break time="2.5s"/>

And while you're reading, it's building you the agent - Splunk Displacement, with the right tools selected, deployed straight into your Kibana cluster. <break time="2s"/>

[deeply] That agent did not exist a minute ago. <break time="1.2s"/>

That was fifty seconds. <break time="0.5s"/> The idea is simple: this is meant to be the go-to place, so a Solutions Architect can prep a discovery call for a new prospect and a Customer Architect can walk into a back-to-back meeting already in sync with what the customer needs - without flipping through twelve tabs and a Salesforce note from three weeks ago. <break time="0.4s"/> Let me show you the moving parts. <break time="0.6s"/>

When you don't know an answer, you usually ping #ask-elastic and wait - sometimes thirty minutes, sometimes the rest of the day. Here, you ask, and ten seconds later you have the answer, cited, grounded in Elastic's docs and your customer's data - no hallucinations, just thirteen hundred chunks of context, ready when you need it. <break time="0.4s"/> Quick research works the same way for a brand new prospect - type the company name and you get an FSI banking research card with their pain, their stack, their renewal window, ready before the call starts. <break time="0.4s"/> Context engineering, in your hands. <break time="0.6s"/>

I didn't build agents to replace the Field Engineer - I built three to stand next to you, and the demo just built a fourth one live. <break time="0.5s"/> RFP Responder. Migration Specialist. Compliance Pursuit. <break time="0.6s"/> That one wasn't here a minute ago. <break time="0.5s"/> And here's the part most demos cannot prove: <break time="0.8s"/> these agents don't live in this app - they live in your Kibana cluster. <break time="0.4s"/> [deeply] Your data, your tenant, your moat. <break time="0.8s"/>

When the customer says "Splunk," you have eight seconds before the room shifts - and we have thirty-one battlecards ready, ranked by marketshare: Splunk, Datadog, CrowdStrike, AWS OpenSearch. <break time="0.5s"/> Twenty industries. Eighty percent of the accounts you'll touch this year - each one ships with demo data, a story, and two dashboards: one for the FE that explains the use case, and one customer-facing version you can hand off in a discovery call. <break time="0.5s"/> Whatever industry walks in the door, you're already standing on the answer. <break time="0.6s"/>

Workspace. Salesforce stays the system of record; this is where the back-to-back-meeting reality lives. <break time="0.3s"/> One card per customer. Pre-meeting brief, the live transcript, the post-meeting summary, the follow-up email, the POV plan - all of it on a timeline. <break time="0.6s"/> So when your nine o'clock ends and your nine-thirty starts, you don't switch tabs - you switch cards. <break time="0.8s"/>

[serious] Here's the part most demos miss. <break time="0.5s"/> Reasoning lives in Agent Builder. Deterministic actions live in Elastic Workflows. The agent thinks; the workflow does. <break time="0.5s"/> So when a transcript drops, the agent runs, Salesforce updates, the weekly forecast slide is generated automatically, and a summary of every action with this customer lands in Slack before your next call starts - so you walk in already in sync, instead of digging through emails and Salesforce notes. <break time="0.8s"/>

Six hours a week, every FE, every week - <break time="0.6s"/> [deeply] that's what we just took back. <break time="0.8s"/> MIT licensed. github dot com slash rodrigo dash elastic slash F E dash Elastic. <break time="0.6s"/> [smiles] Take it home. <break time="0.5s"/> Move pilots to real-world impact.
```

---

## 4. ElevenLabs Studio - step by step

1. Go to **elevenlabs.io/app/studio** → "New Project."
2. Title: `FE Copilot SKO Demo`. Voice: your clone (or Brian). Model: `eleven_v3`.
3. Paste the entire block above into the editor. Studio auto-splits at the line breaks into "paragraphs" - each gets its own speed slider.
4. Click **Generate** to render the whole thing first at default 1.0 speed.
5. Listen back. Note any beat that runs over its target (use the table in section 2).
6. For overrunning beats, select that paragraph, drop the **Speed** slider to **1.05** or **1.10**. Re-render only that paragraph.
7. For underrunning beats, raise breaks: change `<break time="0.5s"/>` to `<break time="0.8s"/>`.
8. When you're within ±2 s of 180 total, click **Export** → MP3 320kbps. Done.

**Time to first usable render**: ~8 minutes. Iterating to perfect: ~30 minutes.

---

## 5. If ElevenLabs renders any line weirdly

Common fixes:

| Problem | Fix |
|---|---|
| Robot pronounces "FE" as "fee" not "F-E" | Replace `FE Copilot` with `F E Copilot` (with the space) |
| "MEDDPICC" stumbles | Already not in the script. Don't add it. |
| Reads URL as a sentence not a URL | The script already says "github dot com slash rodrigo dash elastic slash F E dash Elastic" - keep that exact spelling |
| `[deeply]` ignored in alternative tools | Just delete the tag, the line is still good |
| `<break time="2s"/>` makes a click | Lower to `<break time="1.8s"/>` and add a period before it |
| Voice sounds rushed in B8 | Add `<break time="0.3s"/>` between "Salesforce updates," and "the weekly forecast slide" |
| Voice mumbles "DORA" | Spell as `D O R A` |

---

## 6. After export - sync with the screen recording

1. Drop the MP3 into Final Cut / Premiere / DaVinci on the audio track.
2. Lock its start time at 0:00.
3. Drop your screen recordings on the video track. Slide them so the cuts line up with the natural beats in the voice.
4. The 50-second autopilot SR clip should start when the voice says "Watch what happens" and end after "That agent did not exist a minute ago."
5. The "View agent in Kibana" SR cut should hit when the voice says "these agents don't live in this app - they live in your Kibana cluster."

If your final cut comes in at 178-182 seconds, ship it. Don't chase perfection in the last 2 seconds.
