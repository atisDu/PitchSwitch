# Demo script (task C16)

Draft, 14 Nov; **path checked on live data during C8** (B's API, `USE_FAKE_STORE=false`, Atlas
cache). **About 3 minutes.** One presenter talks, one drives the laptop.
Story: *three funds you'd naturally pitch already backed your direct rival*, found from both sides
of the table, with a source one click away.

## The path

| Step | Screen | Click / type |
| --- | --- | --- |
| 1 | Home | "I'm raising" → type **Sensofusion** → Find → pick **Sensofusion Oy** → **Find who to pitch** |
| 2 | Founder report | Competitor chips **MyDefence** and **Stendr**; hover **Stendr** to show the reason |
| 3 | Pitch list | Top card **Maki.vc** (fit 73): led defence pre-seeds this year; show one source badge |
| 4 | Skip list | **Startuplab, Rainfall Ventures, Skyfall Ventures**: "Backed your competitor Stendr"; click a source badge |
| 5 | Flip | On the **Rainfall Ventures** card: **Flip: see this from Rainfall Ventures's side** |
| 6 | Investor check | Verdict **Conflict.**: "Stendr is in your portfolio and competes with Sensofusion Oy" |
| 7 | Claude Desktop | Web search **off**; ask: *"Using only PitchSwitch, should Sensofusion pitch Rainfall Ventures?"* (asked once beforehand) (setup: `docs/mcp-demo.md`) |

Live on 14 Nov: founder report 3 s, flip 0.1 s (both cached). Direct URLs, if typing fails:

- Founder report: `/founder/202e9283-6455-486f-8868-03c7e0d0cf29`
- Investor check: `/check/0322aa66-c3c7-470c-a940-e6ec117d4051/202e9283-6455-486f-8868-03c7e0d0cf29`

The recorded sample data tells a different story (Stendr, Maki.vc backing Aavuus); it does **not**
hold live (`notes/B.md`, B9), so don't demo from the mock unless everything else fails.

## What to say

**0:00 · The hook (20 s).**
"Founders at Slush will spend this week pitching investors who were never going to say yes. The
worst ones already backed a competitor: you're handing your deck to a rival's board. PitchSwitch tells
you who to pitch, and who to skip."

**0:20 · Founder mode (60 s).** *Steps 1–4.*
"I'm Sensofusion, a Finnish counter-drone company. PitchSwitch finds my direct competitors in Cala's
graph (here's why Stendr counts), then every round they raised and every investor behind them."
"Who should I pitch? Maki.vc fits best: it led defence pre-seeds this year, and here's the source."
"And who should I skip? These three funds, Startuplab, Rainfall and Skyfall, all backed Stendr, my
direct rival. Pitch them and your deck lands with a competitor's investors. That's not a guess:
here's the source." *(Click the badge.)*

**1:20 · The flip (45 s).** *Steps 5–6.*
"Now flip the table. I'm the partner at Rainfall Ventures, and Sensofusion just pitched me between
meetings. Same graph, other direction: **Conflict**. Stendr is in my portfolio and competes with
Sensofusion. Below: every rival, who backed it, and their rounds. That's a 60-second check an
associate would otherwise spend an afternoon on."

**2:05 · The agent (35 s).** *Step 7.*
"PitchSwitch is also an MCP server. Any agent can ask it: 'Should Sensofusion pitch Rainfall
Ventures?'" *(Read the answer and its sources.)* "Same functions, same sources, through Claude."

**2:40 · The close (20 s).**
"Cala is the data layer for agents. PitchSwitch is the fundraising layer on top. Every claim you saw
links to its source, and founders can use it at Slush tomorrow."
*(If C9 produced a quote, end with it: "One founder told us: '…'.")*

## Why this path (for the judges' four criteria)

| Criterion | Where the demo shows it |
| --- | --- |
| Real need | A specific user (seed founder at Slush), a costly mistake (pitching a rival's backer) |
| Execution | One pipeline end to end, both directions, fast because it's cached |
| Originality | Filters investors *out*; the same conflict found from the founder and the investor side |
| Use of Cala | Multi-hop graph walk (company → competitor → round → investor → portfolio), source badges with rank and date, MCP on top |

## Pre-flight (Sunday morning)

- [ ] **Data still matches this script.** Run the path on the deployed API. Competitor judgements
      are stored in Atlas (B10), so they should not change; if Sensofusion's competitors or Skip list
      differ, update steps 2–6 and the lines above.
- [ ] **Cache warm.** Run the whole path once on the demo machine (A18), then set `CACHE_ONLY=true`
      so nothing waits on Cala during the demo.
- [ ] **Deployed URL works** (A17) and the laptop also runs it locally as a fallback.
- [ ] **Browser:** one window, zoom 125%, bookmarks bar hidden, notifications off, the two direct
      URLs above in a note.
- [ ] **Claude Desktop** configured with PitchSwitch (and Cala) MCP, following `docs/mcp-demo.md`
      (C13); the question tested once on the demo laptop.
- [ ] **Backup video** of the full path recorded and on the laptop desktop.
- [ ] Rehearsed twice with the whole team, timed.

## If something breaks

| Problem | Do this |
| --- | --- |
| Search or report slow (loading notice shows) | Keep talking over step 1; if it passes ~20 s, open the founder report by direct URL |
| API down | Switch to the local run on recorded data (`npm run mock` + `npm run dev`); the story is the same |
| MCP step fails | Skip it: "the same functions are exposed over MCP" and show the tool list instead |
| Everything fails | Play the backup video |

## Slides (outline)

Keep it to five; the product carries the demo.

1. **Title:** PitchSwitch. "Who's a fit, and who has a conflict, from either side of the table."
2. **Problem:** founders pitch funds that were never going to say yes: funds that don't lead, funds
   gone quiet, funds that backed a competitor. Investors at Slush screen 30+ startups in two days.
3. *(Live demo.)*
4. **How it works:** the graph walk (company → competitors → rounds → investors → portfolio), facts
   only from Cala, Gemini only judges competitors and writes, scoring is plain code; Atlas cache,
   Verda batch and hosting.
5. **Close:** "Cala is the data layer for agents; PitchSwitch is the fundraising layer on top." Team,
   the founder quote, the URL.
