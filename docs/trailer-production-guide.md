# Trailer production guide (serious + campy in one editing session)

> Cuts both 30-second trailers from the SAME 3-minute master in ~45 minutes of editor time. Same A-roll, same audio, two intros. One export pass.

You already have:
- `docs/video-script-v2.md` - the 3-minute submission master (the source footage for everything)
- `docs/demo-trailer-30s.md` - the serious 30s shot list (use for the LinkedIn / submission post)
- `docs/demo-trailer-campy-30s.md` - the campy 30s shot list (use for the Slack post)

This guide tells you exactly which clips to grab from the master, in what order, with what to overlay. Read top to bottom on the day you cut the trailers.

---

## Tools

- **DaVinci Resolve** (free) or **Final Cut Pro** or **Premiere Pro**. Anything with multi-camera sync, basic transitions, captions burn-in, and 9:16 export works.
- **Whisper-large** for caption transcription (already used for the 3-min). The trailer captions are short enough to type by hand if Whisper is unavailable.
- **freesound.org** for SFX. Pre-download the cues listed in each trailer doc.

---

## Step 0: prepare the master timeline

You should already have this from the 3-minute submission cut. Confirm:
- A single 3:00 timeline named `submission-master`.
- Cam A wide is the master video track (V1).
- Cam B close-up cuts overlaid on V2 at the 11 cut points.
- Shure mic on A1, Cam-source audio muted.
- Captions on V3, color grade applied, -16 LUFS audio mastered.

If anything is missing, finish the submission master first. Do NOT cut the trailer from raw footage.

---

## Step 1: extract the 5 clip blocks you need

Drop these 5 sub-clips into a separate bin called `trailer-clips`:

| Clip | Source time in 3:00 master | Length | What it is |
|---|---|---|---|
| HOOK | 0:00 to 0:08 | 8 s | "Every Field Engineer at Elastic loses six hours a week..." (Cam B) |
| AUTOPILOT_REEL | 0:18 to 1:00 | 42 s | Locked iframe stage with all 9 page transitions |
| FE_BRAIN_BEAT | 1:05 to 1:25 | 20 s | "Stop pinging Slack" plus citations panel |
| AGENT_BUILDER_BEAT | 1:25 to 1:50 | 25 s | "RFP Responder, Migration, Compliance" sidebar |
| CTA | 2:50 to 3:00 | 10 s | "Six hours back. github dot com..." (Cam B close-up) |

You will speed-ramp AUTOPILOT_REEL from 42s down to 8-12s in both trailers.

---

## Step 2: cut the SERIOUS 30s trailer

Create timeline `trailer-serious-30s`. Drag clips in this order:

| Trailer time | Clip | Treatment |
|---|---|---|
| 0:00 to 0:03 | HOOK first 3 seconds | Cam B close-up, native speed, "Field Engineers lose six hours every week. Six. Hours." |
| 0:03 to 0:15 | AUTOPILOT_REEL | Speed ramp to 350 percent so 42 s reads as 12 s. Add 4 page-transition captions (Industries, Battlecards, FE Brain, Agent Builder). |
| 0:15 to 0:23 | Static stat card overlays on top of AUTOPILOT_REEL final frame | Three big numeric overlays animate in: 1300 doc chunks (2.5s), 31 battlecards (2.5s), 13 MCP tools (3s). Type-on animation per number. |
| 0:23 to 0:30 | CTA full | Cam B close-up. "Six hours back. Take it home. github dot com slash rodrigo dash elastic slash F E dash Elastic." |

Total spoken words: 38. Music bed optional, soft pad under -22 dBFS.

Caption file at `docs/demo-trailer-30s.md` section 4 - copy that .srt verbatim.

---

## Step 3: cut the CAMPY 30s trailer

Duplicate `trailer-serious-30s`, rename `trailer-campy-30s`. Then make these surgical changes:

| Edit | Action |
|---|---|
| Replace 0:00 to 0:04 | New campy intro per `docs/demo-trailer-campy-30s.md` section 2: dub Billy-Mays voice over a CAM B 3-second clip (improvise: smile, hands wide, "INTRODUCING THE ULTIMATE TOOL FOR THE FIELD ENGINEER!"). Title slam at 0:02 with confetti overlay (grab 1 frame from the autopilot recap card). At 0:03 hard cut + record-scratch SFX, plus a deadpan VO line ("OK actually,") layered on the next clip. |
| Insert 0:28 to 0:30 tag | After the CTA, hold CAM B for 2 more seconds with the line "Now with Deployment Validator." plus an "as seen on TV" stinger. End on a black frame with white text "Apache no. MIT." |
| SFX layer | Add the cues from campy trailer doc section 3: whoosh build, boom, sparkle, scratch, typewriter dings, ambient bed, stinger. |

Everything else stays the same as the serious trailer. The proof beats and CTA are identical.

---

## Step 4: 9:16 portrait reframe (campy only)

The campy version is destined for Slack and LinkedIn mobile, both vertical-friendly.

Duplicate `trailer-campy-30s` as `trailer-campy-30s-portrait`.
- Change the timeline aspect ratio to 1080x1920.
- Apply a "transform: scale 175 percent" to every CAM A wide clip so the iframe stage centers vertically. Reposition captions to upper third.
- CAM B clips are already framed for portrait; just enable a "smart center" auto-reframe.

Same audio, same SFX. ~10 minutes of work.

---

## Step 5: export pass (4 outputs)

Export ALL of these in one session:

| File | Spec | Use |
|---|---|---|
| `FE-Copilot-FY27-SKO-Hackathon-RodrigoCareaga.mp4` | 1080p H.264, 10 Mbps, 16:9, captions burned in | Submission form |
| `FE-Copilot-trailer-serious-30s.mp4` | 1080p H.264, 8 Mbps, 16:9 | LinkedIn, Twitter |
| `FE-Copilot-trailer-campy-30s.mp4` | 1080p H.264, 8 Mbps, 16:9 | Slack, LinkedIn |
| `FE-Copilot-trailer-campy-30s-portrait.mp4` | 1080x1920, 8 Mbps, 9:16 | Slack mobile, LinkedIn mobile, Twitter |

Audio target: -16 LUFS integrated for all four. The campy version may peak louder during the explosion SFX; clip the boom at -3 dBFS so it does not distort.

---

## Step 6: upload + share order

1. **Submission form** first. Upload `FE-Copilot-FY27-SKO-Hackathon-RodrigoCareaga.mp4` to gDrive, share "anyone at Elastic with the link can view", paste the link into the submission form. **Submit before May 10, 23:59 ET.**
2. **`docs/submission.md`**: paste the gDrive link in the "Demo URL" field.
3. **Slack #sko27fe-hackathon** (after the form is submitted): post both trailers with the copy from `docs/demo-trailer-campy-30s.md` section 6. Lead with the campy.
4. **LinkedIn** (later that day or next morning): post copy from same doc. Lead with the serious.
5. **Twitter / X** (optional, same day): use the short copy.

The order matters. The submission form is the gate; everything else is buzz-building.

---

## Step 7: the 60-second sanity check before submitting

1. Watch the submission video back at 1.5x speed end to end. Catch any audio dropouts or visual jank.
2. Open the gDrive link in an incognito window. Confirm "anyone at Elastic" can play it without sign-in friction.
3. Submit the form. Take a screenshot of the confirmation page.
4. Tail `docs/submission-readiness.md` section 9 to mark the 18 checklist items completed.

You are ready.

---

## Common pitfalls (read once, then do not worry about them)

| Pitfall | Mitigation |
|---|---|
| Campy intro lands cringe instead of fun | The deadpan "OK actually" cut at 0:03 is the safety net. If it still feels cringe to you, drop the campy trailer and keep only the serious one. The campy is optional. |
| Captions overflow on phone | Keep each line <= 32 characters, max 2 lines per cue. The .srt files in the trailer docs already respect this. |
| 9:16 crop loses the iframe content | Pre-render the iframe stage at 800x1600 in the autopilot before your final shoot, so the portrait crop does not lose context. |
| Audio peak distortion on the boom SFX | Clip the explosion SFX at -3 dBFS or apply a brick-wall limiter. |
| YouTube auto-cc replaces your captions | Burn the captions into the video (do not rely on platform auto-caption). |
| File size too large for Slack | Slack caps at 100 MB. 1080p H.264 at 8 Mbps for 30s = ~30 MB. You are fine. |

---

## Time budget

- Step 0 (master ready): pre-existing
- Step 1 (extract clips): 5 minutes
- Step 2 (serious trailer): 15 minutes
- Step 3 (campy trailer): 15 minutes
- Step 4 (9:16 reframe): 10 minutes
- Step 5 (export): 10 minutes (overnight or while you do something else)

**Total active editing: ~45 minutes**. Export pass can run while you draft the submission form copy.
