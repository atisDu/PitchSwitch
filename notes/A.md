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

## Atlas cache: checked live (A10, 14 Nov)

- `MONGODB_URI` is set and the cache works on the real Atlas cluster: the cache tests pass
  against it, and `python -m data.smoke Kelluu --real` ran in 2 s with 0 Cala calls.
- **Everyone with `MONGODB_URI` in `.env` now shares one cache** (collection `cala_cache`, database
  `pitchlist`) and one precomputed investor graph. A company one person warmed is fast for all.
- **Upload what you cached locally before the URI arrived:** `python -m cache.sync` copies
  `.cache/cala/` and `.cache/graph/` into Atlas (never overwrites a newer copy, calls no Cala).
  B: your 213 Stendr calls are probably in your `.cache/cala/`; one `cache.sync` shares them.

## G2: the real store works (A12, 13 Nov)

`USE_FAKE_STORE=false` makes `get_store()` return `CalaDataStore` (live Cala). Checked end to end
on Kelluu: resolve, company, 24 candidates, rounds of Kelluu and four candidates, an investor's
portfolio / rounds / people, and a sourced answer. All valid contract models, lead flags and
sources intact.

- **Try it:** `python -m data.smoke Kelluu --real` (add `--verbose` to see every Cala call).
- **Speed:** the first run for a company took 135 s for 22 Cala calls (the limit is about 10 a
  minute). The same run again took 0 s and made no calls: every response is cached for 24 h, in
  MongoDB Atlas when `MONGODB_URI` is set, else in `.cache/cala/` on your machine.
  So **warm a company once before you need it fast** (`python -m data.smoke <name> --real`).
- **When Cala fails or rate-limits**, an expired cached answer is served instead of an error.
  With `CACHE_ONLY=true` nothing calls Cala at all; an uncached request raises `data.Upstream`.
- **Still empty on the real store:** `co_investors()` returns `[]` until the batch job (A15).
- **IDs:** the real store folds a firm's two Cala entries together only after `resolve()` saw
  them in this process. Use the ID that `resolve()` returns first.
- **Differences from the fake store:** real `portfolio()` is Cala's `INVESTED_IN` links only; the
  fixtures also added links seen in recorded rounds. Real candidates for Kelluu are 24, not 9
  (Estonia and others answer too).

## Reply to B's B9 requests: candidates for Sensofusion and Stendr (14 Nov)

Both fixed in `candidate_competitors()` on the real store and checked live:

- **Sensofusion: 0 -> 26 candidates**, first MyDefence, Frankenburg Technologies, **Stendr**.
- **Stendr: 30 generic SaaS -> 27 defence companies**, first **Sensofusion**, Frankenburg,
  MyDefence, Weibel Scientific. No SaaS.

What changed:

1. **A peers query comes first**: one `knowledge_query` asking Cala for companies with similar
   products. It finds rivals the industry tags miss, and its rows have good descriptions for the
   judge. Rows Cala gives no ID for are matched against the other answers, then looked up by name
   (at most 6 lookups; wrong-country lookalikes are rejected, so "Nordic Air Defence" does not
   become the UK shell company). Nordic Air Defence still has no entity, so it cannot appear.
2. **The industry queries use the tag the description confirms**, not the first tag
   (Stendr: AEROSPACE_AND_DEFENSE, not SOFTWARE_AND_SERVICES). With no tag at all, the industry is
   read from the description (Sensofusion: "defense technology company").
3. **`resolve("Sensofusion")` now returns `202e9283` "Sensofusion Oy"** (the entry that says what
   the firm does) instead of `5c699806` "Sensofusion Oyj". Both IDs work everywhere after
   `resolve()`; `company()` returns the more informative description of the two.

Order of the result: peers in Cala's order, then the industry lists (own country first, nearby
stages first). Cost: 8 queries per company the first time (7 of them shared with every other
company of the same industry and stage group), then cached in Atlas.

Not changed: the fixtures (fake store) still hold the 9 candidates recorded on Friday.

## Cala rate limit is now 100 calls a minute (14 Nov)

Cala raised our key from about 10 to 100 calls a minute (checked: 25 calls in 1.3 s, none
refused). The client now lets one process make 60 a minute (`CALA_PER_MINUTE` in `.env` changes
it), which leaves room for a second busy process on the same key; a refusal is still retried.
Cold runs are about six times faster than the timings written earlier in these notes. Pull to
get it: nothing to change in your code.
