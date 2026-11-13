# Notes — Agent B (Intelligence)

Requests for other areas and "not yet checked against live <service>" lines go here (CLAUDE.md rules 2 and 12).

## Contract review

- **B approves contracts 1.1.0** (commit 3559ed7, 13 Nov). All B review points are covered: competitor_ids, people()/company() for investor IDs, InvestorCheck.rounds scope, chat citations, [n] markers, score 0-100, co_investors() returning [].

## Pending live checks (rule 12)

- B2: `agent/llm.structured()` not yet checked against live Gemini (no GEMINI_API_KEY yet). Check: one call with a nested contract model as schema.
- B3: `core/competitors.find_competitors()` not yet checked against live Gemini. Check: Kelluu, Sensofusion, Stendr candidates → sensible picks + reasons, no invented IDs.

## B6 scoring decision (13 Nov, agreed with human)

- **Skip** = investors with a PORTFOLIO or BOARD conflict with a *direct* competitor (the 10–15 from B3).
- **Pitch pool** = investors in rounds of the *other* candidates (similar, not judged direct)
  ∪ `co_investors()` of the company's current investors (these are also warm paths); minus everyone on Skip.
- **Rank Pitch** by leads_in_space, rounds_in_space, recency of last lead, warm paths (weights dict at the top of `core/scoring.py`).
- **No special handling for big / state funds** (e.g. Tesi). One conflict = Skip, even if they back everyone. Don't add a softer label.
- **Current investors** of the company are left out of both Pitch and Skip (A's sample report does the same).

## Open: competitor backers without rounds (needs the humans — contract change)

- B6 finds Skip investors only through `rounds(competitor)`, because `DataStore` has no
  "who invested in company X" method (incoming `INVESTED_IN`). In the fixtures only 4 companies have
  `rounds_*.json` (Kelluu, Aavuus, Metaktik, Kova Labs). So Stendr's backers (Rainfall, Skyfall,
  Startuplab) never reach Skip, and **the counter-drone conflict demo (Sensofusion vs Stendr) shows no
  conflict**. A's sample report finds them via `graph.backers()` in build_fixtures.py.
- Proposal: add `async def backers(self, company_id: str) -> list[PortfolioLink]` to `DataStore`
  (incoming `INVESTED_IN`, sources kept); bump CONTRACT_VERSION to 1.2.0. B then adds the backers of
  each direct competitor to the pool (~3 lines). Needs all three humans to agree (rule 4).
- Smaller gap: `co_investors()` returns no sources, so warm-path `Reason`s have `sources=[]`.
