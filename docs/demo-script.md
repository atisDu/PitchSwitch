# Demo script (task C16)

Draft, 14 Nov. **About 3 minutes.** One presenter talks, one drives the laptop.
Story: *the best-fit fund in your space is the one you must not pitch*, found from both sides of
the table, with a source one click away.

## The path

| Step | Screen | Click / type |
| --- | --- | --- |
| 1 | Home | "I'm raising" → type **Stendr** → Find → (confirm Stendr, Norway, counter-drone) → **Find who to pitch** |
| 2 | Founder report | Point at the competitor chips; hover **Aavuus** to show the reason |
| 3 | Skip list | Top card: **Maki.vc**, "Backed your competitor Aavuus"; click the **Primary** source badge |
| 4 | Flip | On the Maki.vc card: **Flip: see this from Maki.vc's side** |
| 5 | Investor check | Verdict **Conflict.**: "Aavuus is in your portfolio and competes with Stendr"; scroll to the market map |
| 6 | Claude Desktop | Ask: *"Should Stendr pitch Maki.vc?"* (needs B15 + C13) |

Direct URLs, if typing fails (IDs from `contracts/fixtures/models/index.json`):

- Founder report: `/founder/3afdc63c-b992-4b25-b69d-807ab346352d`
- Investor check: `/check/415bc278-6ed1-4973-a684-07a8b8c5d855/3afdc63c-b992-4b25-b69d-807ab346352d`

## What to say

**0:00 · The hook (20 s).**
"Founders at Slush will spend this week pitching investors who were never going to say yes. The
worst ones already backed a competitor: you're handing your deck to a rival's board. Pitchlist tells
you who to pitch, and who to skip."

**0:20 · Founder mode (60 s).** *Steps 1–3.*
"I'm Stendr, a Norwegian counter-drone startup raising its next round. Pitchlist finds my competitors in
Cala's graph (here's why Aavuus counts), then every round they raised and every investor behind
them."
"Here's the twist. The fund that fits my space best is Maki.vc: it led two defence pre-seeds this
year. And it's at the top of my **Skip** list, because it backed my competitor Aavuus. That's not a
guess: here's the source." *(Click the badge.)*

**1:20 · The flip (45 s).** *Steps 4–5.*
"Now flip the table. I'm the partner at Maki.vc, and Stendr just pitched me between meetings. Same
startup, same graph, other direction: **Conflict**. Aavuus is in my portfolio and competes with
Stendr. Below: every rival, who backed it, and their rounds. That's a 60-second check an associate
would otherwise spend an afternoon on."

**2:05 · The agent (35 s).** *Step 6.*
"Pitchlist is also an MCP server. Any agent can ask it: 'Should Stendr pitch Maki.vc?'" *(Read the
answer and its sources.)* "Same functions, same sources, through Claude."

**2:40 · The close (20 s).**
"Cala is the data layer for agents. Pitchlist is the fundraising layer on top. Every claim you saw
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

- [ ] **Data is real and matches this script.** Run the path on B's API (C8). The recorded samples
      say Maki.vc backed Aavuus and tops Stendr's Skip list; check that live data says the same. If
      not, pick the strongest live conflict and rewrite steps 2–5 and the lines above.
      Known risk (`notes/B.md`, B9): Stendr's live competitor candidates came back as generic SaaS;
      A is fixing candidate search.
- [ ] **Cache warm.** Run the whole path once on the demo machine (A18), then set `CACHE_ONLY=true`
      so nothing waits on Cala during the demo.
- [ ] **Deployed URL works** (A17) and the laptop also runs it locally as a fallback.
- [ ] **Browser:** one window, zoom 125%, bookmarks bar hidden, notifications off, the two direct
      URLs above in a note.
- [ ] **Claude Desktop** configured with Cala + Pitchlist MCP (C13); the question tested once.
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

1. **Title:** Pitchlist. "Who's a fit, and who has a conflict, from either side of the table."
2. **Problem:** founders pitch funds that were never going to say yes: funds that don't lead, funds
   gone quiet, funds that backed a competitor. Investors at Slush screen 30+ startups in two days.
3. *(Live demo.)*
4. **How it works:** the graph walk (company → competitors → rounds → investors → portfolio), facts
   only from Cala, Gemini only judges competitors and writes, scoring is plain code; Atlas cache,
   Verda batch and hosting.
5. **Close:** "Cala is the data layer for agents; Pitchlist is the fundraising layer on top." Team,
   the founder quote, the URL.
