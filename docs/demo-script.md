# Demo script (task C16)

Draft, 14 Nov; path updated to the report's new layout (Skip first) and the server numbers B
checked after A's redeploy. **Run it once on the live site before rehearsing.**
**About 3 minutes.** One presenter talks, one drives the laptop.
Story: *nine funds you'd naturally pitch already backed one of your four direct rivals*, found from
both sides of the table, with a source one click away.

Reports grow as more companies get looked up (vector search; intended). **Recheck every line below
against the screen after the Sunday-morning freeze** (warm + cache-only, see Pre-flight).

## The path

| Step | Screen | Click / type |
| --- | --- | --- |
| 1 | Home | "I'm raising" → type **Sensofusion** → Find → pick **Sensofusion Oy** → **Find who to pitch** |
| 2 | Founder report | Four competitor chips: **MyDefence, Stendr, Frankenburg Technologies, Origin Robotics**; hover **Stendr** to show the reason |
| 3 | Report top | The verdict line under the name: **9 investors to skip**, 26 to pitch. Then the dark **Don't pitch these 9.** list: **Skyfall Ventures** is first, "backed Stendr" |
| 4 | Evidence, then Pitch | Click **Skyfall Ventures** in that list: it jumps to its card, "Backed your competitor Stendr"; click a source badge. Scroll up to **Who to pitch**: top card **Maki.vc** (fit 70), open breakdown |
| 5 | Flip | On the **Skyfall Ventures** card: **Flip: see this from Skyfall Ventures' side** |
| 6 | Investor check | Verdict **Conflict.**: "Stendr is in your portfolio and competes with Sensofusion Oy" |
| 7 | Claude Desktop | Web search **off**; ask: *"Using only PitchSwitch, should Sensofusion pitch Skyfall Ventures?"* (asked once beforehand; setup: `docs/mcp-demo.md`) |

**Live site: <https://95-133-252-219.sslip.io>.** Server numbers after A's redeploy (B, 14 Nov 17:40):
Pitch Maki.vc 69.5 (shown as 70), NATO Innovation Fund 38.5, Tesi 36.2; Skip starts with Skyfall
Ventures, then Change Ventures and Startuplab. Earlier checks: founder report 3.1 s,
Skyfall flip 1.0 s (7 sources), Skyfall brief 0.3 s ("Skip Skyfall Ventures because it backs
Stendr…", 13 citations). Skyfall is in the top 6 of Skip, so `deploy/warm.py` keeps its check and
brief cached. Direct URLs, if typing fails:

- Founder report: `/founder/202e9283-6455-486f-8868-03c7e0d0cf29`
- Investor check: `/check/9b65ed62-a126-4255-8339-44c59fbf0ad8/202e9283-6455-486f-8868-03c7e0d0cf29`

**On stage, say "Skyfall" and don't read out its description:** Cala's entry for it
(`9b65ed62`) describes "a Glasgow-based hospitality and tourism company", so its brief does too.
The conflict itself (backs Stendr, 7 sources) is right (`notes/B.md`).

Rainfall Ventures and Startuplab also backed Stendr and work the same way; Startuplab is #3 on Skip,
Rainfall further down (below warm.py's top 6). The recorded sample data tells a different story altogether;
don't demo from the mock unless everything else fails.

## What to say

**0:00 · The hook (20 s).**
"Founders at Slush will spend this week pitching investors who were never going to say yes. The
worst ones already backed a competitor: you're handing your deck to a rival's board. PitchSwitch tells
you who to pitch, and who to skip."

**0:20 · Founder mode (60 s).** *Steps 1–4.*
"I'm Sensofusion, a Finnish counter-drone company. PitchSwitch finds my direct competitors in Cala's
graph, four of them (here's why Stendr counts), then every round they raised and every investor
behind them."
"Before anything else, it tells me who to skip: nine funds that each backed one of my direct rivals.
Skyfall Ventures, for one, backed Stendr. Pitch them and your deck lands with a competitor's
investors. That's not a guess: here's the source." *(Click the badge.)*
"And who should I pitch? Maki.vc fits best, 70 out of 100: it led defence pre-seeds this year, and
here's how the score adds up."

**1:20 · The flip (45 s).** *Steps 5–6.*
"Now flip the table. I'm the partner at Skyfall Ventures, and Sensofusion just pitched me between
meetings. Same graph, other direction: **Conflict**. Stendr is in my portfolio and competes with
Sensofusion. Below: every rival, who backed it, and their rounds. That's a 60-second check an
associate would otherwise spend an afternoon on."

**2:05 · The agent (35 s).** *Step 7.*
"PitchSwitch is also an MCP server. Any agent can ask it: 'Should Sensofusion pitch Skyfall
Ventures?'" *(Read the answer and its sources.)* "Same functions, same sources, through Claude."

**2:40 · The close (20 s).**
"Cala is the data layer for agents. PitchSwitch is the fundraising layer on top. Every claim you saw
links to its source, and founders can use it at Slush tomorrow."

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
- [ ] **After every redeploy, warm again.** Stored briefs are rewritten when B's brief code changes
      (30–50 s each on first request), so run `warm.py` before any rehearsal.
- [ ] **Cache warm, then cache-only.** From the last rehearsal on, results must not drift (cached
      answers refresh after 24 h and the judge can change its mind; `notes/B.md`):
      `python deploy/warm.py --check`, then `deploy/cache-only.sh 95.133.252.219 on`, then
      `python deploy/warm.py --check` again (must pass). Rehearse in this mode. **In cache-only mode
      anything typed off-script fails at once**: stick to the path, or switch it off for Q&A
      (`deploy/cache-only.sh 95.133.252.219 off`).
- [ ] **Deployed URL works** (<https://95-133-252-219.sslip.io>) and the laptop also runs it locally as a fallback.
- [ ] **Browser:** one window, zoom 125%, bookmarks bar hidden, notifications off, the two direct
      URLs above in a note.
- [ ] **Claude Desktop** configured with the PitchSwitch MCP server, following `docs/mcp-demo.md`
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
   the URL.
