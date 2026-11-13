# Notes — Agent A (Data & infra)

Requests for other areas and "not yet checked against live <service>" lines go here (CLAUDE.md rules 2 and 12).

## Commitments from the contract review (1.1.0, 13 Nov)

TODO.md is owned by humans, so these extend my tasks here instead:

- **A2** also produces the mock fixtures listed in `contracts/api.md` → Fixtures: `index.json`,
  `resolve_*`, `investor_check_*`, `brief_*`, `agent_events_slush_prep.json`, `agent_events_chat.json`
  (samples: real Cala facts, placeholder ranking).
- **A8** `people(id)` and **A6** `company(id)` also work for investor IDs (B needs the investor's own
  people for BOARD conflicts).
- **A12** `co_investors()` on the real store returns `[]` (or a count computed from
  `investor_rounds()`) until the batch job (A15) fills the graph. It must not raise.

## What Cala's data looks like (found while recording fixtures, 13 Nov)

- **Rate limit: about 10 calls a minute** on our key (429 after that, no `Retry-After` header).
  The recorder waits 6.5 s between calls. The real store must cache hard and batch carefully.
- **`knowledge_query` and `knowledge_search` take 20–80 s each.** A combined query (several
  countries and stages at once) fails with "too complex"; one query per country works.
- **One firm can have several Cala IDs** (a `Company` and an `Organization`, or one per data
  source): two "Kelluu", two "Maki.vc", two "Gungnir Capital", two "Redstone". The fixture
  builder folds same-name entries into one (`index.json` → `aliases`). The real store needs the
  same step (A6).
- **Rounds live on `FundingRound` entities.** `transaction_value` is a number with
  `transaction_value_units`; the lead is `is_lead: true` on the investor's edge to the round.
  Only the lead is marked, so the others are "not lead" when a lead exists and "unknown" otherwise.
- **Demo cases that are thin in Cala:**
  - *Nordic Air Defence* has no company entity (only text answers: pre-seed, $4.2M, SNÖ Ventures).
    Stendr is the third founder-mode sample instead (agreed with the human).
  - *Sensofusion* has an entity but no rounds or investors.
  - *NestAI* has one investor edge and no rounds; `knowledge_search` knows its €100M round
    co-led by Tesi and Nokia. Gaps like this are what `sourced_answer()` is for.

## For B

- `data.NotFound` is raised by `company(id)` for an unknown ID. The list methods return `[]`.
- Founder mode: every investor found through a *direct* competitor's round is, by definition, a
  conflict. The sample reports therefore rank investors from the wider candidate pool (the
  "space") and put those tied to a direct competitor on the Skip list. Your scoring needs some
  such split or the Pitch list is always empty.

## For B and C: undated rounds (A7, 13 Nov)

Cala often links an investor to a company (`INVESTED_IN`) without any round. So that code walking
`rounds()` still finds those investors, `rounds(company_id)` ends with one extra `Round` when such
investors exist: id `"<company_id>:backers"`, no `label`, `date` or amount, `is_lead` unknown, with
the sources of those links. Both the fake and the real store do this (Stendr has only this one).
B: count it as "backs the company", not as a dated deal. C: show it as "Investors (round details
not known)" rather than an empty round row.

## Demo risk: Tesi -> NestAI is not in the graph (A8, 13 Nov)

The planned investor-mode demo ("Tesi backs both Kelluu and NestAI") only half exists in Cala's
graph: Tesi -> Kelluu is an `INVESTED_IN` link, but Tesi -> NestAI is not (NestAI's only graph
investor is PostScriptum Ventures). Cala's text answer does say Tesi and Nokia co-led NestAI's
EUR 100M round. So `portfolio(Tesi)` will not contain NestAI. The Tesi x NestAI check still shows
a conflict, through Kelluu as NestAI's competitor. To show "Tesi holds NestAI" itself, B has to
use `sourced_answer()`.

`portfolio()` on the real store is Cala's `INVESTED_IN` links only (one call). Deals that exist
only as rounds are in `investor_rounds()`.
