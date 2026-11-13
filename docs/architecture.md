# Architecture

Status: draft (task C15), written 14 Nov while the real-data pass (B9–B10) and deployment (A16–A19)
are still in progress. Sections marked **planned** describe what isn't built yet.

## Overview

```mermaid
flowchart LR
  user([Founder / investor]) --> web[Next.js app<br/>frontend/]
  agent([Claude Desktop, Cursor]) -. planned .-> mcp[MCP server<br/>backend/mcp_server]
  web -- "/api/* (REST, SSE)" --> api[FastAPI<br/>backend/api]
  mcp -.-> core
  api --> core[core/<br/>competitors · conflict · scoring]
  core --> llm[Gemini<br/>agent/llm.py]
  core --> store[DataStore<br/>backend/data]
  store --> cache[(Cache<br/>Atlas or .cache/)]
  cache --> cala[(Cala REST API)]
  batch[Batch job<br/>batch/precompute_graph] --> store
  batch --> graph[(Investor graph<br/>Atlas or .cache/graph)]
  store --> graph
```

The web app and (soon) the MCP server call the same core functions. Every Cala call goes through
one client and one cache; everything above the data layer works on the shared contract models in
`contracts/schemas.py`, each fact carrying its `sources`.

## Founder mode, step by step

1. **Resolve.** `POST /api/resolve` → `DataStore.resolve()` → Cala entity search. Several firms
   share names (5 "Inventure"s), so the user always confirms which entity they mean. When Cala holds
   one firm under two IDs (a `Company` and an `Organization`), the store keeps the richer one and
   reads both.
2. **Candidates.** `candidate_competitors()` runs Cala `knowledge_query` by industry, Nordic and
   Baltic country and nearby stages (vector search over company descriptions is **planned**, A13).
3. **Judge.** `core/competitors.py` asks Gemini to sort the candidates into *direct competitors*,
   *same space* and *unrelated*, with a one-line reason each. It may only return candidate IDs; any
   other ID is dropped.
4. **Rounds and investors.** The store walks `PARTICIPATES_IN_FUNDING_ROUND` and `INVESTED_IN`
   edges for those companies. When Cala has backers but no round details, they come back as one
   undated round, so they still count.
5. **Conflicts.** `core/conflict.py`: an investor that backed a direct competitor (`PORTFOLIO`), or
   whose person sits on its board (`BOARD`), goes on **Skip**. Plain set logic; each conflict keeps
   the sources of the edges it rests on.
6. **Score.** `core/scoring.py`, deterministic, 0–100: leads in the space (35), rounds in the
   space (20), recency of the last lead (25), warm paths via co-investors of the company's current
   investors (20). The company's own investors are left out of both lists.
7. **Show.** The frontend renders the `FounderReport`: competitor chips the user can remove (then
   re-rank with `competitor_ids`), the Pitch list, and the Skip list with the conflict first.

**Investor mode** reuses steps 1–5 from the other side: the fund's portfolio against the startup's
competitors, plus who backed each rival and their round history (`InvestorCheck`).

## How we use each service

### Cala — the only source of facts

| Cala feature | Job in Pitchlist |
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
- **Vector search** over company descriptions for competitor candidates: **planned** (A13).

### Gemini — judgement and wording only

- `agent/llm.py` is the one entry point: structured JSON output validated against Pydantic models,
  temperature 0, retries. Model names come from `.env`; the competitor judge uses the smart tier
  (`GEMINI_MODEL_SMART`, falling back to `GEMINI_MODEL_FAST` when it is empty).
- Used today to judge competitors. **Planned:** writing one-page briefs from already-fetched,
  sourced facts (every sentence cites), and the tool-calling agent behind Slush prep and chat.

### Verda

- **Batch job** (`batch/precompute_graph.py`): crawls the investors that matter for our demo space,
  their portfolios and rounds, then derives co-investor counts and activity stats. Idempotent and
  resumable. Running it as a Verda batch job: **planned** (A16).
- **Embeddings** via the Verda Inference API for competitor vector search: **planned** (A13).
- **Hosting** of the API and MCP server on a Verda CPU instance (Docker): **planned** (A17); deploy
  notes will be in `deploy/verda.md` (A19).

## Frontend

Next.js (App Router) + TypeScript + Tailwind, in `frontend/`.

- `lib/types.ts` mirrors `contracts/schemas.py` field for field; `lib/api.ts` is the only code that
  calls the backend. The browser calls same-origin `/api/*`, which Next forwards to `API_URL` (with
  a 30-minute proxy timeout, because a report for a company Cala hasn't cached yet takes minutes).
- `mock/` serves the API from the recorded fixtures, so the UI was built before the backend existed;
  switching is one env var.
- Design follows `frontend/DESIGN.md`: editorial, monochrome, one green accent, a source badge on
  every claim.

## Contracts and fixtures

`contracts/` holds the shared models, the REST API description (`api.md`) and recorded Cala data.
The contracts were frozen after the first evening (version 1.1.0); changes need all three
workstreams to agree. `contracts/fixtures/raw/` holds raw Cala responses for the demo cases,
`models/` the contract models built from them, used by the fake store and the frontend mock.
