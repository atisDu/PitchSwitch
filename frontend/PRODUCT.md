# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Two audiences of equal weight, on either side of the same table:

- **Founders raising a round** (typically pre-seed to Series A), e.g. preparing for Slush. Their job:
  decide who to pitch and who to skip before spending weeks on investors who were never going to
  say yes, above all funds that already backed a direct competitor.
- **Investors** (angels, VC associates and partners) screening startups, e.g. between Slush
  meetings. Their job: within a minute, see whether a startup competes with their portfolio, who
  backed its rivals, and its round history.

## Product Purpose

PitchSwitch tells you who's a fit and who has a conflict, from either side of the table. It walks
Cala's graph from a company to its competitors, their funding rounds and the investors behind them,
then ranks investors to **Pitch** and lists investors to **Skip**, each claim with its source.
Success: a founder drops the funds that would hand their deck to a rival's backer and walks into
Slush with a ranked, sourced list; an investor gets a trustworthy conflict check in seconds.

## Positioning

- **Filters investors out.** It names who to skip (backed a direct competitor, or one of its
  people sits on that competitor's board), not only who matches.
- **The same conflict from both sides.** Founder mode and investor mode find the same fact from
  opposite directions in the graph ("the flip").
- **A source on every claim.** Facts come only from Cala; each carries a ranked (Primary, Filing,
  Press, Aggregator) and dated source one click away. Scoring is plain, deterministic code; the AI
  only judges which candidates are direct competitors, writes briefs from already-fetched facts,
  and orchestrates tools. It never invents numbers, dates or investors.
- **Agent-ready.** The same functions are an MCP server, so any agent (Claude Desktop, Claude Code,
  Cursor) can ask "should I pitch Fund X?" and get a sourced answer.

## Operating Context

- Built at Junction 2026 for Cala's "Make Unicorns Real" challenge; used around Slush, right after.
- Founder flow: enter your company → confirm which Cala entity it is (several firms share names) →
  report with competitors (removable, then re-rank), Pitch list, Skip list → per-investor brief.
- Investor flow: enter your fund and the startup that pitched you → verdict (conflict or none) →
  market map of the startup's rivals, who backed them and their rounds.
- Slush prep: paste the investors you're meeting (or add the Slush 2026 investors Cala names) → one
  cited brief per investor, streamed live.
- Follow-up questions in a chat panel scoped to the page; answers keep only cited sentences.
- Live at https://95-133-252-219.sslip.io (Verda); a cache-only mode freezes results for demos.

## Capabilities and Constraints

- Capabilities: founder report (competitors, Pitch, Skip, fit score 0–100 with a per-signal
  breakdown), investor check (verdict, market map), briefs, Slush prep, chat, MCP server, optional
  funding amount (founder's raise / investor's max check) compared with round sizes.
- Data is only as complete as Cala: lead investors are often unmarked, round amounts are often
  missing ("unknown" is a real, frequent answer), early-stage Nordic coverage varies, and one firm
  can appear under several Cala entities.
- Results change as Cala data refreshes and as more companies are looked up (vector search grows);
  this drift is intended. Uncached lookups take seconds to minutes; cached ones are fast.
- Angels (people who invest) are investors too and appear on the lists.
- Terminology: Pitch, Skip, conflict (`PORTFOLIO` or `BOARD`), direct competitor, fit score, lead
  data (known / partial / unknown), funding fit, brief, the flip, Slush prep.
- Undecided: business model, pricing, accounts and anything beyond the hackathon demo.

## Brand Commitments

- Name: **PitchSwitch** (earlier working name "Pitchlist", still used in code: the MCP server key
  and some internal names).
- Line: "Who's a fit, and who has a conflict, from either side of the table."
- Voice: plain and factual, says what it doesn't know (e.g. "Cala doesn't say who led"), never
  overstates a claim beyond its sources.
- Visual identity is recorded in `frontend/DESIGN.md`, not here.

## Evidence on Hand

- Live Cala data and sources for the demo companies (Sensofusion, Stendr, Kelluu, NestAI) and their
  investors, e.g. Sensofusion's Skip list of funds that backed its rivals; recorded samples in
  `contracts/fixtures/`.
- Investment trends across ~110 crawled Nordic and Baltic investors (A's investor graph in Atlas).
- **Absent, must not be fabricated:** testimonials, customer or user counts, founder quotes (user
  testing was not run), press, partnerships, pricing, performance or accuracy metrics.

## Product Principles

1. **Sourced or silent.** Every fact shown carries its source; what Cala doesn't know is said
   plainly, never filled in.
2. **Skip is as valuable as Pitch.** Telling someone who not to pitch is the core value, not a
   footnote.
3. **Both sides of the table.** Any conflict a founder sees, the investor can see from their side.
4. **Judgement is explainable.** Scores are plain code with a visible breakdown; the AI's role is
   bounded and labelled.
5. **Fast enough for Slush.** Answers must be usable between meetings; slow paths say what they are
   doing.
