# Notes — Agent B (Intelligence)

Requests for other areas and "not yet checked against live <service>" lines go here (CLAUDE.md rules 2 and 12).

## Contract review

- **B approves contracts 1.1.0** (commit 3559ed7, 13 Nov). All B review points are covered: competitor_ids, people()/company() for investor IDs, InvestorCheck.rounds scope, chat citations, [n] markers, score 0-100, co_investors() returning [].

## Pending live checks (rule 12)

- B2: checked live 13 Nov (nested contract model as schema, ~3 s).
- B3: checked live 13 Nov. First prompt ("use only the descriptions") kept 0/9 on every model: Cala descriptions are too thin (Sensofusion = "Finnish defense technology company"). Prompt now lets Gemini add what it reliably knows about named companies; IDs still restricted to candidates. Sensofusion <-> Stendr judged counter-drone rivals; Kelluu gets none (no airship/ISR rival among its 9 candidates -> A11/A13 candidates).
- Models (human: "no flash, make it smart"): `gemini-4-hydrogen` for FAST and SMART in .env; the judge uses tier `smart`. Gemini 4 names (argon/carbon/hydrogen) don't say which is top; hydrogen has the largest output limit. Swap in .env if the ranking is known. `gemini-2.5-pro` is closed to new users.

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
