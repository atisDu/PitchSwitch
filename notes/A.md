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

## Vector search (A13): built, and switched ON on the server (14 Nov)

`USE_VECTOR_SEARCH=true` makes `candidate_competitors()` also add the stored companies closest in
meaning to the company (Gemini embeddings, Atlas Vector Search index `company_vectors_index`),
after the peers and before the industry lists. Default is off: nothing changes unless it is set.

Measured on live Atlas and Gemini for the three demo companies:

- **What it adds today: almost nothing.** Sensofusion +0, Stendr +0, Kelluu +1 (Sensofusion Oy).
  Only 28 companies are stored, the ones already in these three candidate lists. It can only
  find companies some earlier search has seen; it pays off as more spaces are searched.
- **Speed:** a warm search costs about 0.1 s more (0.11-0.35 s against 0.04-0.28 s). The first
  search in a new process costs 1.5-2 s more, once. A company's embedding is stored, so repeat
  searches make no Gemini call; a Gemini or index failure just leaves the candidates as they were.
- **Why it is off for the demo:** it changes Kelluu's candidate list, and B re-judges a company
  when its candidates change, so the competitors and Skip lists the demo script relies on could
  shift. Turn it on after the demo, or earlier only with a re-warm and a recheck of the script.
- Verda's Inference API has no embeddings endpoint, so `VERDA_EMBED_MODEL` is unused; the model
  is `GEMINI_EMBED_MODEL` (default `gemini-embedding-001`, 768 dimensions).

**Update, 14 Nov afternoon: the team switched it on.** `USE_VECTOR_SEARCH=true` is set on the
deployed server (`deploy/ship.sh` copies it from the local `.env`) and in A's `.env`. Checked on
the server right after: the founder reports of Sensofusion, Stendr and Kelluu are **unchanged**
(same competitors, same Skip lists, same top five on Pitch, same Pitch length), and
`python deploy/warm.py --check` passes (50 calls in 23 s, none slow). No vector errors in the
server log. B and C: to run with it locally, add `USE_VECTOR_SEARCH=true` to your `.env`; without
it your local runs behave as before. If a report ever looks different from the demo script,
setting it to `false` and redeploying puts the old candidate lists back.

## Contract 1.1.1 followed: people who invest work in both stores (14 Nov)

Reply to B's "Angels stay on the lists" and C's 1.1.1 note.

- **Real store:** `company(id)` returns a `Company` with `type: "Person"` for a person (name,
  Cala's description, sources); `investor_rounds(id)` and `portfolio(id)` return the person's
  rounds and `INVESTED_IN` companies; `people(id)` returns `[]`. A person Cala knows nothing
  about gives empty lists, never an error. Checked live on Tuomas Rasila
  (`c75cbef9-0ab0-5552-84f8-fc59bc63ea93`): Person, one Pre-Seed round (Kova Labs, 2026-11-04).
- **Fake store:** every investor that appears in a recorded round or as a backer now has a
  `company_<id>.json`, angels included, so `company(id)` works for every investor on the sample
  reports. Fixtures rebuilt; `index.json` says `contract_version: "1.1.1"`.
- **Still 404:** IDs that cannot invest (a funding round, a place, a product).
- **Tests:** the three that were red on `main` are green again; 7 new ones cover people.
- **Batch:** the crawl now stores angels too instead of counting them as failed.
- C: `ANGEL_PAGES_READY` can go to `true` once you have pulled. The deployed server has it.

## For C and B: the live demo reports changed at about 12:45 on 14 Nov (vector search)

**Decision (human, 14 Nov): vector search stays on and this drift is intended.** It is how
the team pictures the demo: the more companies get looked up, the richer each report becomes.
Nothing to fix. C: write the demo script against what the live site shows after the Sunday
morning freeze below, not against the old two-competitor version.

With `USE_VECTOR_SEARCH=true` on the server, the candidate lists of the three demo companies
changed, B's judge ran again for all three, and it chose more direct competitors than before:

| Company | Competitors before | Competitors now | Skip before | Skip now |
| --- | --- | --- | --- | --- |
| Sensofusion | MyDefence, Stendr | MyDefence, Stendr, Frankenburg Technologies, Origin Robotics | Rainfall, Startuplab, Skyfall | those three + Change Ventures, NATO, Nova Founders Capital, SMARTCAP, Silicon Roundabout, Skaala |
| Stendr | Sensofusion, MyDefence, Weibel | + Frankenburg, Origin Robotics | none | Change Ventures, NATO, Nova Founders Capital, SMARTCAP, Silicon Roundabout, Skaala |
| Kelluu | Aispeco, Granta | unchanged | 6 | unchanged (Pitch 47 -> 40) |

**The demo path still works**: Sensofusion's Skip still has Rainfall Ventures, Startuplab and
Skyfall, and the flip to Rainfall still shows the conflict. But `docs/demo-script.md` names two
competitor chips and three Skip funds, and there are now four and nine.

**Why:** vector search adds the stored companies closest in meaning, and the store grows whenever
anyone analyses a company it has not seen (28 companies this morning, 31 now: NestAI, C2GRID and
Unmanned Defense Systems were added). New neighbours change a candidate list; B re-judges on any
change; the judge does not always pick the same set (B9 already saw both of these outcomes for
Sensofusion). So **with vector search on, a demo report can change whenever someone looks up a
new company on the live site**, including during C9 founder testing.

**What freezes it:** `deploy/cache-only.sh 95.133.252.219 on`. In cache-only mode no new company
can be analysed, so the vector store cannot grow and no report changes. Run
`python deploy/warm.py --check` first, then check the script against what is on screen.
