# FE Copilot launch announcements

Drafts for the FY27 SKO FE Summit hackathon submission. Three audiences, three voices.

Conventions:

- Plain hyphens only. No em or en dashes.
- Honest tone. The Slack and email read like a senior FE wrote them, not a launch agency.
- Placeholders in `[BRACKETS]` so Rodrigo can swap final URLs at send time.

---

## 1. Slack message (channel suggestion: `#fe-hackathon`)

> Audience: 800 Elastic FEs, internal channel. Casual, factual, no clickbait.
> Length budget: 300 words. Actual: 244 words.

```
:rocket: FE Copilot is locked for the FY27 SKO FE Summit hackathon

I just submitted FE Copilot, a small toolkit I have been hacking on for the
last few weeks. It tries to remove the boring half of our day so we can spend
more time actually engineering.

Three things make it different from the other 100 GPT wrappers we have all
seen:

- It is wired into the meeting itself. A Pre-Meeting agent writes the brief
  one hour before the call from real SEC EDGAR filings, the Live Companion
  whispers competitor and MEDDPICC alerts on every transcript turn, and the
  Post-Meeting agent does six Salesforce writes plus the follow-up email
  draft after one click. No swivel-chair.

- It runs on Haiku 4.5 by default at roughly two cents per full pipeline run,
  and you can swap any single agent up to Sonnet 4.6 or Opus 4.7 with one env
  var. So the FE who only needs the brief pays brief money. The FE who wants
  Opus reasoning on the post-meeting summary pays Opus money. Per agent.

- It ships with seven Field utilities chained over MCP inside Elastic Agent
  Builder: SPL to ES|QL, cost calc, compliance mapper, POV planner, capacity,
  stack extractor, code samples. The master agent picks the right tool from
  one prompt.

What I need now: two or three FE buddies willing to point this at a real
upcoming customer call (SMB, mid-market, public sector, any segment) and tell
me where it embarrasses itself. DM me.

Demo video: [LOOM_URL]
Repo: [GITHUB_URL]
3 minute walkthrough: `docs/demo-script.md`

Thanks to everyone who pressure-tested the talk tracks last week. :pray:
```

---

## 2. Email to FE Leadership Distribution List

> Audience: FE Directors, RVPs, FE Architects, FE Ops. Internal but skimmable
> for cross-post to LinkedIn after submission window closes.
> Length budget: 350 words. Actual: 312 words.

**To:** `fe-leadership@elastic.co` (DL placeholder)
**From:** Rodrigo Careaga
**Subject line, pick one for A/B:**

- A. FE Copilot: my FY27 SKO hackathon submission, looking for two pilots
- B. 15 hours per FE per week: my hackathon entry just shipped
- C. Three agents, seven tools, one pre-meeting flow (FY27 SKO submission)

---

Hi all,

**Why now.** The FY27 SKO FE Summit hackathon closes May 10. I submitted
FE Copilot this week because the prep tax on customer meetings has gotten
out of hand. Six meetings a day, thirty minutes of prep each, fifteen hours
a week, per FE. That is the gap I tried to close.

**What it does.** Three Claude agents wrap the meeting workflow end to end.
The Pre-Meeting agent reads SEC EDGAR filings, news, and Wikipedia, then
posts a structured brief plus a PDF to the FE Slack channel one hour before
the call. The Live Companion runs Haiku per transcript turn for competitor
and MEDDPICC alerts in real time. The Post-Meeting agent writes the summary,
captures action items with verbatim quotes, drafts the follow-up email, and
pushes six Salesforce writes (Opportunity MEDDPICC, ContentNote, Document
Link, Competitor, Deal Health, Slack post). Defaults to Haiku 4.5 at roughly
two cents per pipeline run; per-agent override to Sonnet 4.6 or Opus 4.7.

The seven Field utilities (SPL to ES|QL, cost calc, compliance, POV planner,
capacity, stack extractor, code samples) are exposed as MCP tools inside
Elastic Agent Builder, so a single prompt to the master agent chains them.

**Demo and repo.** Three minute video at [LOOM_URL]. Public repo at
[GITHUB_URL]. Synthetic data only, no customer data is used or stored.

**Ask.** I want two FE pilots in May. One mid-market, one enterprise, any
segment is fine. Pilot means: run FE Copilot against one upcoming real
customer call, give me thirty minutes of feedback, and let me iterate. Reply
to this thread or ping me on Slack.

Thanks for reading,
Rodrigo Careaga
Senior Customer Architect, Elastic
[CALENDLY_URL]

---

## 3. LinkedIn post (public)

> Public-friendly, no internal acronyms unexplained, no chest-beating.
> Length budget: 200 words. Actual: 165 words.

```
Six customer meetings a day. Thirty minutes of prep each. Fifteen hours a
week, per Field Engineer, gone before we open the laptop.

I spent the last month building FE Copilot, my entry for the Elastic FY27
SKO Field Engineering Summit hackathon. It is now submitted.

What it does:

- Writes the pre-meeting brief from real SEC EDGAR filings one hour before
  the call (PDF plus Slack post).
- Whispers competitor and MEDDPICC alerts on every transcript turn during
  the live conversation.
- Pushes the post-meeting summary, action items, follow-up email, and six
  Salesforce updates after one click.

Built on Anthropic Claude (Haiku 4.5 by default, Opus 4.7 for the heavier
reasoning) and Elastic Agent Builder with seven MCP tools chained by a
master agent. All synthetic data, no customer data touched.

Repo: [GITHUB_URL]
Demo: [LOOM_URL]

If you are an Elastic FE and want to pilot it, ping me.

#Elastic #FieldEngineering #AI #Hackathon #Anthropic
```
