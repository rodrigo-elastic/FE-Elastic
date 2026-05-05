# FE Copilot - Campy 30s trailer (Slack edition)

> Audience: peers in `#sko27fe-hackathon`, LinkedIn, optional Twitter. NOT the hackathon judges.
> Tone: self-aware infomercial gag for the first 3 seconds, then hard cut to the same proof beats as the serious 30s trailer.
> Length: 30 seconds plus or minus 1.
> Source: same Cam A wide / Cam B close-up footage already shot for `docs/video-script-v2.md`.
> Why this exists: the campy opener works for peers who already trust your craft. It signals "I had fun building this" without burning the submission opener.

---

## 1. Story arc (30s)

| Time | Beat | Mode |
|---|---|---|
| 0:00 to 0:03 | Infomercial slam | CAMPY |
| 0:03 to 0:04 | Hard cut, deadpan reset | TRANSITION |
| 0:04 to 0:13 | Autopilot reveal | SERIOUS |
| 0:13 to 0:23 | Three proofs (1300, 31, 13) | SERIOUS |
| 0:23 to 0:28 | CTA | SERIOUS |
| 0:28 to 0:30 | Tag (button-press recall) | LIGHT |

The campy mode lives at the head and the tail. The middle is the same crisp proof loop as the submission. That contrast is what makes the gag land instead of cringe.

---

## 2. Per-second shot list

```
0:00 ----------------------------------------------------------------
  CAM B close-up. Bright eyes, big smile, half-shrug.
  VO (Billy Mays voice, dial it to 9): "INTRODUCING THE ULTIMATE TOOL"
  Caption: "INTRODUCING"
  SFX: airy "whoosh" build

0:01 ----------------------------------------------------------------
  CAM B holds. Smile bigger. Hands wide.
  VO continues: "FOR THE FIELD ENGINEER!"
  Caption: "THE ULTIMATE TOOL"
  SFX: whoosh peaks

0:02 ----------------------------------------------------------------
  HARD CUT. Title card slam: "FE COPILOT" in Lochmara blue, white bg,
  pulses once on impact. Confetti from autopilot stage as overlay.
  Caption: "FE COPILOT"
  SFX: low boom + faint cartoon "WUMP" + sub-second sparkle

  Optional: tiny explosion .gif overlay corner (top right). Keep it
  small so it reads as wink, not aesthetic crime.

0:03 ----------------------------------------------------------------
  SCRATCH RECORD SFX. Smash cut to CAM A wide, deadpan face.
  VO (your normal voice, low energy): "OK actually,"
  Caption: "OK actually,"
  No music for half a beat. Pure tonal whiplash.

0:04 to 0:08 -------------------------------------------------------
  Continue CAM A wide. Open laptop in frame. Click "Show me the magic 45s"
  on the dashboard. Speed-ramped autopilot: 4 page transitions
  visible (Industries, Battlecards, FE Brain, Agent Builder), each
  ~1 second.
  VO: "we built FE Copilot."
  Caption: "we built FE Copilot."
  SFX: subtle cluster of soft ticks per page transition

0:08 to 0:13 -------------------------------------------------------
  Iframe stage continues at 3.5x. Customers Workspace slides in,
  then Demo Data, then Health.
  VO: "Six hours per FE per week back."
  Caption (lower third, big): "Six hours per FE per week back."
  SFX: clean piano hit on "Six"

0:13 to 0:17 -------------------------------------------------------
  CAM B medium. Three big stat cards animate in sequence.
  VO: "Thirteen MCP tools."
  Caption: "13 MCP tools"
  SFX: typewriter ding per number

0:17 to 0:20 -------------------------------------------------------
  Same shot, second card.
  VO: "Thirty one battlecards, sorted by marketshare."
  Caption: "31 battlecards"
  SFX: typewriter ding

0:20 to 0:23 -------------------------------------------------------
  Same shot, third card.
  VO: "Twenty industries. Eighty percent of customers."
  Caption: "20 industries"
  SFX: typewriter ding, then a longer hold

0:23 to 0:28 -------------------------------------------------------
  CAM B close-up, full eye contact. Slight smile.
  VO: "Take it home. github dot com slash rodrigo dash elastic
       slash F E dash Elastic."
  Caption (sticky lower third): "github.com/rodrigo-elastic/FE-Elastic"
  SFX: clean ambient bed

0:28 to 0:30 -------------------------------------------------------
  Tag: tiny button-press recall to the campy intro. CAM B holds,
  half-smile, raises one eyebrow.
  VO: "Now with Deployment Validator."
  Caption: "Now with Deployment Validator!"
  SFX: faint "as seen on TV" stinger

  Final frame: black with white text "Apache no. MIT." for 1 second.
```

Total spoken words: 50. Caption duration averages 3 seconds per card. Easy to read.

---

## 3. SFX sourcing

All royalty-free, pull from `freesound.org` or your editor's stock library.

| Cue | Sound | Suggested file |
|---|---|---|
| 0:00 to 0:02 whoosh build | Cinematic riser | "whoosh-riser-3s" |
| 0:02 boom + cartoon wump | Low cinema boom layered with old-school cartoon thud | "boom-impact-1s" + "cartoon-wump" |
| 0:02 sparkle | Magic chime | "magic-sparkle" |
| 0:03 scratch record | Vinyl scratch | "record-scratch-classic" |
| 0:04 to 0:13 page ticks | Soft UI clicks | "ui-tap-soft" |
| 0:08 piano hit on "Six" | Piano single note (low) | "piano-low-c" |
| 0:13 to 0:23 typewriter dings | Typewriter bell | "typewriter-ding" |
| 0:23 to 0:28 ambient bed | Soft pad | "pad-warm" |
| 0:28 stinger | Old-school commercial outro | "as-seen-on-tv-stinger" |

Keep total music duck under -18 dBFS so the VO sits clean. Master to -16 LUFS like the submission video.

---

## 4. Caption file (.srt block)

Copy this verbatim into your editor.

```
1
00:00:00,000 --> 00:00:02,800
INTRODUCING
THE ULTIMATE TOOL
FOR THE FIELD ENGINEER!

2
00:00:02,800 --> 00:00:03,800
FE COPILOT

3
00:00:03,800 --> 00:00:04,800
OK actually,

4
00:00:04,800 --> 00:00:07,800
we built FE Copilot.

5
00:00:07,800 --> 00:00:13,000
Six hours per FE per week back.

6
00:00:13,000 --> 00:00:17,000
13 MCP tools.

7
00:00:17,000 --> 00:00:20,000
31 battlecards.

8
00:00:20,000 --> 00:00:23,000
20 industries.

9
00:00:23,000 --> 00:00:28,000
Take it home.
github.com/rodrigo-elastic/FE-Elastic

10
00:00:28,000 --> 00:00:30,000
Now with Deployment Validator.
Apache no. MIT.
```

---

## 5. 9:16 reframe note (Slack and LinkedIn vertical)

The submission is shot 16:9. For the campy 30s clip you ALSO want a 9:16 export so it reads on phones in Slack thumbnails and on LinkedIn mobile.

- 0:00 to 0:03 (campy intro): CAM B close-up reframes natively to portrait. No work needed.
- 0:03 to 0:13 (autopilot reveal): center-crop the iframe stage. The 13 MCP tool chips and the Customers Workspace timeline both keep their main signal in the center, so a vertical crop loses peripheral chrome but not the punchline.
- 0:13 to 0:23 (three proofs): full-frame stat cards. Reposition the lower-third caption to upper-third so the visual weight balances on phone.
- 0:23 to 0:28 (CTA): CAM B native portrait. URL caption stays sticky.
- 0:28 to 0:30 (tag): same.

Export both 16:9 and 9:16 in the same editing pass. Two timelines, same audio.

---

## 6. Posting copy (Slack first, LinkedIn second)

### Slack #sko27fe-hackathon

```
Just dropped my FY27 SKO Hackathon submission.

3 minutes of serious demo here: <gDrive serious link>
30 seconds of less serious demo here: <gDrive campy link>

FE Copilot. Twelve agents (now thirteen). Thirty one battlecards.
Twenty industries. Eight demo scenarios. Five languages.

The pitch: every FE loses six hours a week to prep, notes, follow up.
This claws those hours back. MIT, fork it, take it home.

github.com/rodrigo-elastic/FE-Elastic

Lo construí en 10 días. Feedback bienvenido en los dos idiomas.
```

### LinkedIn

```
For the FY27 SKO FE Summit Hackathon I built FE Copilot, a thirteen
MCP tool plus three agents stack that gives Field Engineers six hours
per week back. Calendar invite to sourced brief, live MEDDPICC
whisper, one click Salesforce sync, all wired into Elastic Cloud
Agent Builder.

Open source under MIT. Take it home, fork it, ship it.

github.com/rodrigo-elastic/FE-Elastic

Demo (3:00, serious): <gDrive link>
Trailer (0:30, less serious): <gDrive campy link>

Built solo in 10 days. Honest feedback welcome.
```

### Twitter / X (optional)

```
Built FE Copilot for FY27 SKO. 13 MCP tools, 3 agents, 31 battlecards.
Six hours per FE per week back.

Trailer: <gDrive campy link>
Demo: <gDrive serious link>
Repo: github.com/rodrigo-elastic/FE-Elastic

MIT. Fork it.
```

---

## 7. Production order

1. Cut the serious 3:00 first (per `docs/video-script-v2.md`). That is your A-roll for both versions.
2. Cut the serious 30s trailer second (per `docs/demo-trailer-30s.md`). 5 to 10 minutes work in your editor.
3. Cut the campy 30s third by cloning the serious 30s timeline and replacing 0:00 to 0:04 with the campy intro plus inserting the 0:28 to 0:30 tag. ~15 minutes of work.
4. Export all three at 1080p H.264, 10 Mbps. Plus 9:16 portrait export for the campy.
5. Upload the serious 3:00 to gDrive. Submit form. Then post the trailers in Slack + LinkedIn.

The campy version exists ONLY as a community signal that you are a person, not a sterile demo machine. Do not use it as the submission. Two takes ago I was very clear about why; do not negotiate with yourself at midnight.

---

## 8. One-line note for future you

If you watch this back in three months and cringe, that means you were trying. The cringe is the cost of personality. The submission video is sterile and serious for the judges; the trailer is yours.
