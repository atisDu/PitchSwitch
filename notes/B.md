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
