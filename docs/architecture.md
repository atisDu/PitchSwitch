# Architecture

Status: 14 Nov. Live at <https://95-133-252-219.sslip.io>. Everything below runs on live data
(including vector search, A13).

## Overview

```mermaid
flowchart LR
  user([Founder / investor]) --> web[Next.js app<br/>frontend/]
  agent([Claude Desktop, Cursor]) -- "MCP (stdio or /mcp)" --> mcp[MCP server<br/>backend/mcp_server]
  web -- "/api/* (REST, SSE)" --> api[FastAPI<br/>backend/api]
  api --> loop[Agent loop<br/>agent/gemini_agent.py]
  loop --> tools[Tools<br/>agent/tools.py]
  mcp --> tools
  tools --> core
  api --> core[core/<br/>competitors · conflict · scoring · briefs]
  core --> llm[Gemini<br/>agent/llm.py]
  core --> store[DataStore<br/>backend/data]
  store --> cache[(Cache<br/>Atlas or .cache/)]
  cache --> cala[(Cala REST API)]
  batch[Batch job<br/>batch/precompute_graph] --> store
  batch --> graph[(Investor graph<br/>Atlas or .cache/graph)]
  store --> graph
```

The web app, the agent and the MCP server call the same core functions. Every Cala call goes through
one client and one cache; everything above the data layer works on the shared contract models in
`contracts/schemas.py`, each fact carrying its `sources`.

## Founder mode, step by step

1. **Resolve.** `POST /api/resolve` → `DataStore.resolve()` → Cala entity search. Several firms
   share names (5 "Inventure"s), so the user always confirms which entity they mean. When Cala holds
   one firm under two IDs (a `Company` and an `Organization`), the store keeps the richer one and
   reads both.
2. **Candidates.** `candidate_competitors()` runs Cala `knowledge_query` by industry, Nordic and
   Baltic country and nearby stages, plus a "similar products" query and name lookups for rivals the
   industry tags miss, plus vector search: the stored companies closest in meaning (A13, on in
   production).
3. **Judge.** `core/competitors.py` asks Gemini to sort the candidates into *direct competitors*,
   *same space* and *unrelated*, with a one-line reason each. It may only return candidate IDs; any
   other ID is dropped.
4. **Rounds and investors.** The store walks `PARTICIPATES_IN_FUNDING_ROUND` and `INVESTED_IN`
   edges for those companies. When Cala has backers but no round details, they come back as one
   undated round, so they still count.
5. **Fresh funds** (`core/fresh.py`). A Cala search asks which VC firms closed a fund for the
   startup's sector this year or last; Gemini only copies firm names out of the cited claims, and
   each is resolved to a Cala investor. They join the Pitch pool with the claim as a reason.
6. **Portfolio X-ray** (`core/xray.py`). Every ranked investor's whole portfolio is judged against
   the startup, not only the ~30 candidates: Gemini screens the names, the flagged companies go
   through the regular judge. A direct rival found there is a hidden `PORTFOLIO` conflict; same-space
   holdings become a thesis reason and count half in the score. Verdicts are stored once per startup.
7. **Conflicts.** `core/conflict.py`: an investor that backed a direct competitor (`PORTFOLIO`), or
   whose person sits on its board (`BOARD`), goes on **Skip**. Plain set logic; each conflict keeps
   the sources of the edges it rests on. The partner named for each top investor (step 9) is checked
   against every rival's board too.
8. **Sanctions screen** (`core/sanctions.py`). Every ranked investor and up to five of its LPs are
   checked against Cala's sanctions records (by ID). A record is a `SANCTION` conflict → Skip; no
   record is stated as "screened: no sanctions record in Cala", never as "clean".
9. **Score.** `core/scoring.py`, deterministic, 0–100, seven signals: leads in the space (25),
   companies in the space (15, weighted by closeness), recency of the last lead (15), activity in
   the last 12 months (10, full for a fresh fund), warm paths via co-investors of the company's
   current investors (15), stage fit (10), Nordic or Baltic focus (10). Every card shows how its
   score adds up. For the top five, the partner for the space is named from sourced claims. The
   company's own investors are left out of both lists.
10. **Notes** (`core/notes.py`). Sourced lines about the direct competitors that belong to no one
    investor: grants they won (NATO DIANA, EDF, EIC, national programmes) and which attend Slush.
11. **Show.** The frontend renders the `FounderReport`: a one-line verdict, competitor chips the
    user can remove (then re-rank with `competitor_ids`) with the notes under them, the Skip list in
    brief, the Pitch list (fresh funds tagged, the partner to ask for), then the evidence for each
    Skip, hidden rivals and sanctions labelled.

**Investor mode** reuses steps 1–4, 7 and 8 from the other side: the fund's portfolio against the startup's
competitors, plus who backed each rival and their round history (`InvestorCheck`).

## How we use each service

### Cala — the only source of facts

| Cala feature | Job in PitchSwitch |
| --- | --- |
| Entity search | Resolve names to IDs; the user confirms between same-name entities |
| Entity introspection | Run once per entity type, cached in `backend/data/introspection.json`, so we only request fields that exist |
| Entity retrieval with relationship projections | The backbone: one retrieval per entity carries properties, rounds, investors and people |
| `knowledge_query` | Competitor candidates by industry, country and stage |
| `knowledge_search` | Sourced answers for gaps (e.g. who led a round); its claims and references become citations |
| Source metadata | Every claim in the UI shows a badge: rank (Primary, Filing, Press, Aggregator), date, link |

Cala allows about 10 calls a minute on our key and uncached `knowledge_*` calls take 20–80 s, so
`data/cala_client.py` queues calls instead of failing, retries with backoff, shares identical
in-flight requests and logs every call (endpoint, time, cache hit) for credit tracking.

### MongoDB Atlas — cache and precomputed graph

- **Response cache** (`cache/atlas.py`): one document per distinct Cala request, fresh for 24 h.
  Expired entries are kept and served when Cala is unreachable and in `CACHE_ONLY` mode, so the demo
  runs with no calls to Cala. Without `MONGODB_URI` the same cache lives in files under `.cache/cala/`.
- **Investor graph** (`cache/graph.py`): `crawl_investors`, `investor_graph` (co-investor counts) and
  `investor_activity` (last lead, deals in 12 months) written by the batch job.
- **Judgements** (which candidates are direct competitors) are stored too, so a company gets the same
  competitors after a restart and on every machine, and reports load in 2–4 s once judged.
- **Vector search** (A13, `USE_VECTOR_SEARCH=true` in production): every company the app sees is
  embedded (Gemini `gemini-embedding-001`; Verda's Inference API has no embeddings endpoint) and
  stored; candidates include its nearest neighbours. The store grows as more companies are looked
  up, so reports get richer over time. That is intended (team decision, 14 Nov); cache-only mode
  freezes it for the demo.

### Gemini — judgement and wording only

- `agent/llm.py` is the one entry point: structured JSON output validated against Pydantic models,
  temperature 0, retries. Model names come from `.env`; the competitor judge uses the smart tier
  (`GEMINI_MODEL_SMART`, falling back to `GEMINI_MODEL_FAST` when it is empty).
- **Competitor judge** (`core/competitors.py`): sorts candidates; may only return candidate IDs.
- **Briefs** (`core/briefs.py`): Gemini writes sentences that cite numbered facts from the store and
  Cala's sourced answers; code renders the `[n]` markers and drops any sentence that cites nothing
  or states a number its facts don't hold.
- **Agent** (`agent/gemini_agent.py`): a function-calling loop over the same tools as the MCP server
  (at most 12 calls), behind Slush prep (one run per pasted investor, three at a time) and chat
  (scoped to the page's company or investor). Answers keep only cited sentences.

### Verda

- **Hosting:** the frontend, API and MCP server run on one Verda CPU instance with Docker Compose,
  Caddy in front (HTTPS via sslip.io; `/api` and event streams go straight to the backend, `/mcp` to
  the MCP server). **Live** on a Verda CPU instance (4 vCPU, 16 GB, FIN-03, about EUR 1 a day),
  created through Verda's Cloud API by `deploy/verda.py` and updated with `deploy/ship.sh`.
- **Batch job:** `batch/precompute_graph.py` crawls the investors around the demo space (portfolios,
  rounds) and derives co-investor counts and activity stats into Atlas; idempotent, resumable,
  rate-limited. It runs as a **Verda serverless batch job** (`pitchlist-batch`, CPU node): the
  backend image in Verda's Container Registry, started with `batch/job_server.py`; each trigger runs
  one container that crawls, derives, answers with the counts and exits, so billing stops. A cron
  job on the instance triggers it nightly (`deploy/run-batch.sh`). First run: completed in under a
  minute, 110 investors derived, 96 with co-investors.
- **Demo safety:** `deploy/warm.py` calls every page the demo can reach to fill the cache, then
  `deploy/cache-only.sh` makes the server answer only from it (whole demo path: 50 calls in 22 s,
  0 to Cala). A name never looked up before then fails at once instead of waiting on Cala.
- No GPUs, clusters or fine-tuning: the work is I/O (Cala, Gemini, Atlas), not compute.
- Cost: about EUR 1 a day for the instance; Atlas M0 is free. Details: `deploy/verda.md`.

## Frontend

Next.js (App Router) + TypeScript + Tailwind, in `frontend/`.

- `lib/types.ts` mirrors `contracts/schemas.py` field for field; `lib/api.ts` is the only code that
  calls the backend. The browser calls same-origin `/api/*`, which Next forwards to `API_URL` (with
  a 30-minute proxy timeout, because a report for a company Cala hasn't cached yet takes minutes).
- `mock/` serves the API from the recorded fixtures, so the UI was built before the backend existed;
  switching is one env var.
- Screens: home (mode toggle, entity confirm), founder report (competitor chips, Pitch and Skip),
  investor check (verdict, market map), brief (printable, numbered sources), Slush prep (live cards
  per investor) and an "Ask" chat panel on report, check and brief pages.
- Streams (`/api/jobs/{id}/stream`, `/api/chat`) are read with `fetch` and parsed in `lib/sse.ts`;
  small pure reducers (`lib/prep.ts`, `lib/chat.ts`) turn events into UI state and are unit-tested.
- Design follows `frontend/DESIGN.md` (the landing page's system, served at /): cool white, slate ink, one teal accent, a source badge on
  every claim.

## Contracts and fixtures

`contracts/` holds the shared models, the REST API description (`api.md`) and recorded Cala data.
The contracts were frozen after the first evening (1.1.0; 1.1.1 on 14 Nov added angels as investors,
wording only; 1.2.0 the same day added the `SANCTION` conflict and report notes); changes need all three
workstreams to agree. `contracts/fixtures/raw/` holds raw Cala responses for the demo cases,
`models/` the contract models built from them, used by the fake store and the frontend mock.
