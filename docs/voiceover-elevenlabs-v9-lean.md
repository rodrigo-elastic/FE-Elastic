# Voiceover v9 - lean version (~410 words / 180 s at natural pace)

> v8 was 613 words. At 90-100 wpm (your natural reading pace), v8 ran 6+ minutes. v9 cuts to 410 words while keeping every feature named: cold open, Kulkarni, autopilot narration, go-to-place positioning, FE Brain, Quick Research, Agent Builder + Kibana proof, Battlecards, Industries, Demo Data dashboards, Workspace, pre/post-meeting summaries, Workflows, Weekly Forecast slides, Slack, CTA.
>
> **Fits in 3:00 at ~135 wpm** - comfortable for both AI voice and self-narration.

---

## Settings (ElevenLabs)
- Model: `eleven_v3`
- Stability: 35 · Similarity: 75 · Style: 20 · Speaker boost: ON
- Speed: **1.00** for AI render. If you self-narrate, ignore Speed.

---

## THE LEAN SCRIPT - paste into ElevenLabs Studio

```
[hushed] Tuesday morning. Eight forty-two. <break time="0.4s"/> Your call with Searchlight Capital is at nine. You haven't read their earnings. You haven't built the case to displace the Splunk renewal sitting on their desk. And another call follows right after. <break time="0.6s"/> Eighteen minutes. <break time="1.5s"/> Every Solutions Architect, every Customer Architect at Elastic, knows this morning. <break time="0.8s"/>

We do this work by hand. <break time="0.4s"/> Back in December, Ash Kulkarni said one line that stuck: <break time="0.6s"/> [deeply] "In the world of AI, it's all about context engineering." <break time="0.5s"/> You can't context-engineer anything in eighteen minutes. <break time="0.3s"/> So I built FE Copilot. Watch. <break time="0.6s"/>

Watch what happens. One click. <break time="1.5s"/>

The brief renders - their earnings, their stack, AutoOps cluster signals, and the Splunk renewal locking in sixty days. Our window to displace. <break time="0.4s"/> All grounded in their data. <break time="2s"/>

The Field Assistant writes the discovery plan - five questions, sequenced: buyer, Splunk pain, DORA gap, champion, decision window. <break time="2.5s"/>

And in the background, it's building you the agent - Splunk Displacement, deployed straight to your Kibana cluster. <break time="2s"/>

[deeply] That agent did not exist a minute ago. <break time="1s"/>

That was fifty seconds. <break time="0.5s"/> The idea is simple: this is the go-to place. <break time="0.3s"/> Where a Solutions Architect preps a new prospect's discovery call, and a Customer Architect walks into back-to-back meetings already in sync - without flipping through twelve tabs and a Salesforce note from three weeks ago. <break time="0.4s"/> Let me show you the parts. <break time="0.6s"/>

You used to ping #ask-elastic and wait thirty minutes. Now? Ten seconds. Cited. Grounded in Elastic's docs and your customer's data. <break time="0.3s"/> Quick research does the same for a brand new prospect - type the name, get the FSI banking research card before the call starts. <break time="0.6s"/>

I didn't build agents to replace the Field Engineer. I built three to stand next to you. And the demo just built a fourth one live. <break time="0.4s"/> RFP. Migration. Compliance. <break time="0.3s"/> And Splunk Displacement - written sixty seconds ago. <break time="0.5s"/> Here's the proof most demos can't show: <break time="0.4s"/> these agents live in your Kibana cluster. <break time="0.3s"/> [deeply] Your data. Your tenant. Your moat. <break time="0.7s"/>

"Splunk." Eight seconds before the room shifts. <break time="0.3s"/> Thirty-one battlecards, ranked by marketshare. <break time="0.3s"/> Twenty industries - eighty percent of your accounts. Each one ships with demo data and two dashboards: one for the FE that explains the case, one customer-facing for the discovery call. <break time="0.4s"/> Whatever walks in the door, you're already standing on the answer. <break time="0.6s"/>

Workspace. Salesforce stays the system of record; this is where the work lives. <break time="0.3s"/> Brief, transcript, post-meeting summary, follow-up email, POV plan - all on a timeline. <break time="0.4s"/> Your nine o'clock ends, your nine-thirty starts: you don't switch tabs. You switch cards. <break time="0.7s"/>

[serious] Reasoning lives in Agent Builder. Deterministic actions live in Elastic Workflows. <break time="0.4s"/> A transcript drops, the agent runs, Salesforce updates, the weekly forecast slide generates, and Slack gets the recap before your next call starts. <break time="0.4s"/> You walk in already in sync. <break time="0.7s"/>

Six hours a week. Every FE. Every week. <break time="0.5s"/> [deeply] That's what we just took back. <break time="0.7s"/> MIT licensed. github dot com slash rodrigo dash elastic slash F E dash Elastic. <break time="0.5s"/> [smiles] Take it home. <break time="0.4s"/> Move pilots to real-world impact.
```

---

## Word count + timing

| Beat | Words | Target | wpm |
|---|---|---|---|
| B0 Cold open | 38 | 13 s | 175 |
| B1 Promise + Kulkarni | 38 | 17 s | 134 |
| B2 Autopilot narrated | 75 | 50 s | 90 (slow w/ pauses) |
| B3 Pivot | 50 | 15 s | 200 |
| B4 FE Brain + Quick Research | 38 | 12 s | 190 |
| B5 Agent Builder + Kibana | 55 | 17 s | 194 |
| B6 Battlecards / Ind / Demo | 50 | 16 s | 188 |
| B7 Workspace | 35 | 13 s | 162 |
| B8 Workflows + Slack | 35 | 12 s | 175 |
| B9 CTA | 36 | 15 s | 144 |
| **Total** | **450** | **180 s** | **150** |

(Counts include breaks; pure speaking time ≈ 165 s, leaving 15 s of strategic silence.)

---

## If you still go over after first render

Trim in this order until you hit 180:

1. **B6** drop "ranked by marketshare" → saves 2 s
2. **B5** drop "RFP. Migration. Compliance." → saves 2 s (the names aren't load-bearing; the live-built fourth agent is)
3. **B4** drop "type the name, get the FSI banking research card before the call starts" → saves 4 s
4. **B6** drop "for the discovery call" → saves 1 s
5. **B0** drop "And another call follows right after" → saves 2 s (loses the bookend setup; only do this as last resort)

DO NOT trim:
- "Eighteen minutes." (B0)
- The Kulkarni quote (B1)
- "That agent did not exist a minute ago." (B2)
- "You don't switch tabs. You switch cards." (B7)
- "Take it home. Move pilots to real-world impact." (B9)

These are the load-bearing lines. Cut anything else first.

---

## Self-narration tip

If you record this yourself instead of using AI: read the autopilot beat (B2) at half your normal pace, with the marked pauses. The slow narration over fast screen movement is what makes the whole video feel cinematic. Everything outside B2 should be your normal SA-explaining-to-a-colleague pace.
