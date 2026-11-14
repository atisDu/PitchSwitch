# Demo script (task C16)

Draft, 14 Nov; path updated to the report's layout (Skip first) and the deployed API's numbers
at contract 1.2.0 (B22 X-ray, B23 fresh funds, B24 notes, B25 sanctions screen). **Run it once on the live site before rehearsing.**
**About 3 minutes.** One presenter talks, one drives the laptop.
Story: *eleven funds you'd naturally pitch already backed a direct rival*, found from
both sides of the table, with a source one click away.

Reports grow as more companies get looked up (vector search; intended). **Recheck every line below
against the screen after the Sunday-morning freeze** (warm + cache-only, see Pre-flight).

## The path

| Step | Screen | Click / type |
| --- | --- | --- |
| 1 | Home | "I'm raising" → type **Sensofusion** → Find → pick **Sensofusion Oy** → **Find who to pitch** |
| 2 | Founder report | Four competitor chips: **MyDefence, Stendr, Frankenburg Technologies, Origin Robotics**; hover **Stendr** to show the reason. Below them, "Also about your competitors": Frankenburg's EDF grant, MyDefence's Innobooster (don't read out) |
| 3 | Report top | The verdict line under the name: **11 investors to skip**, 30 to pitch. Then the dark **Don't pitch these 11.** list: **BSV Ventures** first, "backed Zvook (a rival found in its portfolio)"; **Skyfall Ventures** second, "backed Stendr" |
| 4 | Evidence, then Pitch | Click **Skyfall Ventures** in that list: it jumps to its card, "Backed your competitor Stendr"; click a source badge. Scroll up to **Who to pitch**: top card **Maki.vc** (fit 70), open breakdown; below it, **Ask for: Paavo Räisänen** with its source |
| 5 | Flip | On the **Skyfall Ventures** card: **Flip: see this from Skyfall Ventures' side** |
| 6 | Investor check | Verdict **Conflict.**: "Stendr is in your portfolio and competes with Sensofusion Oy" |
| 7 | Claude Desktop | Web search **off**; ask: *"Using only PitchSwitch, should Sensofusion pitch Skyfall Ventures?"* (asked once beforehand; setup: `docs/mcp-demo.md`) |

**Checked 14 Nov evening:** steps 1-6 on the deployed API (C), step 7 in Claude Desktop (the team).
**Live site: <https://95-133-252-219.sslip.io>.** Deployed API at 1.2.0 (C, 14 Nov, evening):
Pitch Maki.vc 69.9 (shown as 70), NATO Innovation Fund 39.2, Tesi 35.7, Lifeline 35.6; Skip (11)
starts with BSV Ventures (Zvook, found by B22's portfolio X-ray, not a chip), then Skyfall
Ventures, Change Ventures, Startuplab. 0 sanctions hits; every investor carries the screened line. Earlier checks: founder report 3.1 s,
Skyfall flip 1.0 s (7 sources), Skyfall brief 0.3 s ("Skip Skyfall Ventures because it backs
Stendr…", 13 citations). Skyfall is in the top 6 of Skip, so `deploy/warm.py` keeps its check and
brief cached. Direct URLs, if typing fails:

- Founder report: `/founder/202e9283-6455-486f-8868-03c7e0d0cf29`
- Investor check: `/check/9b65ed62-a126-4255-8339-44c59fbf0ad8/202e9283-6455-486f-8868-03c7e0d0cf29`

**On stage, say "Skyfall" and don't read out its description:** Cala's entry for it
(`9b65ed62`) describes "a Glasgow-based hospitality and tourism company", so its brief does too.
The conflict itself (backs Stendr, 7 sources) is right (`notes/B.md`).

Rainfall Ventures and Startuplab also backed Stendr and work the same way; Startuplab is #4 on Skip,
Rainfall further down (below warm.py's top 6). The recorded sample data tells a different story altogether;
don't demo from the mock unless everything else fails.

## What to say

Deck: "PitchSwitch pitch" (Claude Slides; the speaker notes there are the same lines). Six slides
plus one backup; **the live demo runs 0:40-2:00**. Story spine: one conflict, two sides of the table.

| Time | Slide | Say |
| --- | --- | --- |
| 0:00-0:15 | 1 Cover | "Slush starts tomorrow. Founders will pitch investors who were never going to say yes; the worst already backed a direct competitor. PitchSwitch catches that, from both sides of the table." |
| 0:15-0:35 | 2 Two sides | "The founder hands a rival's investor their deck. The investor gets pitched by a company that competes with one they own. One fact in Cala's graph, read two ways. Let me show it." |
| 0:35-0:40 | 3 Live demo | "This is a real Finnish counter-drone startup." Switch to the browser. |
| 0:40-1:15 | *Live, steps 1-4* | Four direct rivals; "Don't pitch these 11"; BSV backs Zvook, a rival I never listed; click Skyfall, its card, the source badge. |
| 1:15-1:25 | *Live, step 4* | Maki.vc, 70 out of 100, open the breakdown, "ask for Paavo Räisänen". |
| 1:25-1:45 | *Live, steps 5-6* | Flip on Skyfall's card: "I'm the partner at Skyfall. Conflict: Stendr is in my portfolio and competes with Sensofusion." |
| 1:45-2:00 | *Live, step 7* | Claude Desktop, answer already open from the warm-up: "Same functions, same sources, through any agent." Back to slides. |
| 2:00-2:25 | 4 Why Cala | The four-hop walk (company, rivals, rounds, 41 investors, whole portfolios); search gives articles, Cala gives edges with IDs and a source on each; five firms called "Inventure". |
| 2:25-2:45 | 5 Trust | Gemini only picks from Cala's candidate IDs; code drops uncited sentences and numbers the facts don't hold; the score is plain code. One check everywhere: app, briefs, chat, MCP. |
| 2:45-3:00 | 6 Close | "Cala is the data layer for agents; PitchSwitch is the fundraising layer on top. Run your company, or flip any pitch, before your first Slush meeting." |

Step 7 is too tight to type live: ask the question during the warm-up and keep that answer open.

## Why this path (for the judges' four criteria)

| Criterion | Where the demo shows it |
| --- | --- |
| Real need | A specific user (seed founder at Slush), a costly mistake (pitching a rival's backer) |
| Execution | One pipeline end to end, both directions, fast because it's cached |
| Originality | Filters investors *out*; the same conflict found from the founder and the investor side |
| Use of Cala | Multi-hop graph walk (company → competitor → round → investor → whole portfolio), sanctions records by ID, sourced search for fresh funds and partners, source badges with rank and date, MCP on top |

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
4. **How it works:** the graph walk (company → competitors → rounds → investors → whole portfolio,
   plus a sanctions screen), facts
   only from Cala, Gemini only judges competitors and writes, scoring is plain code; Atlas cache,
   Verda batch and hosting.
5. **Close:** "Cala is the data layer for agents; PitchSwitch is the fundraising layer on top." Team,
   the URL.
