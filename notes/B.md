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

## Resolved: competitor backers without rounds

- B6 only finds Skip investors through `rounds(competitor)`. Since A7, `rounds()` also returns one
  undated `Round` holding a company's backers when Cala has no round details (e.g. Stendr), so
  Stendr's backers reach Skip. No contract change needed; the 1.2.0 `backers()` idea is dropped.
  `test_eval.py::test_counter_drone_conflict` guards it.
- Open, minor: `co_investors()` returns no sources, so warm-path `Reason`s have `sources=[]`.
