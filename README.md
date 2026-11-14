# PitchSwitch

**Who's a fit, and who has a conflict, from either side of the table.**
Built at Junction 2026 for Cala's "Make Unicorns Real" challenge.

Founders build investor lists from logo walls and gut feeling, then spend weeks pitching funds that
were never going to say yes, including funds that already backed a direct competitor. PitchSwitch
walks Cala's graph of companies, rounds and investors to answer two questions, with a source on
every claim:

- **Founder mode:** *Who should I pitch, and who should I skip?* Enter your company and get a ranked
  **Pitch** list and a **Skip** list of investors who backed a direct competitor or sit on its board.
- **Investor mode (the flip):** *Does this startup conflict with my portfolio, and who backed its
  rivals?* Enter your fund and a startup that pitched you.

- **Briefs:** a one-page brief on any investor for your company, every sentence citing its source.
- **Slush prep:** paste the investors you're meeting; an agent looks each one up and writes a brief.
- **Ask:** follow-up questions on any report, answered from Cala facts with citations.
- **MCP server:** the same tools for any agent, so Claude Desktop can answer "should I pitch Fund X?"
  ([docs/mcp-demo.md](docs/mcp-demo.md)).

**Live demo:** <https://95-133-252-219.sslip.io> (a Verda CPU instance; see `deploy/verda.md`).

## How it works

Company → competitors (Cala candidates, judged by Gemini) → their funding rounds → the investors
behind them → deterministic scoring. Facts come only from Cala; the LLM never invents numbers, dates
or investors. Details: [docs/architecture.md](docs/architecture.md).

## Run it

Requirements: Python 3.11+, Node 22.18+ (the frontend tests and mock run TypeScript directly).

```sh
# once per clone, from the repo root
python3 -m venv .venv && source .venv/bin/activate
pip install -e "backend[dev]"
(cd frontend && npm install)
cp .env.example .env            # fill in what you have; see below
```

**Frontend only, on recorded data** (no keys needed):

```sh
cd frontend
npm run mock                                 # mock API on :8001, serves contracts/fixtures/models
API_URL=http://localhost:8001 npm run dev    # app on http://localhost:3000
```

**Full stack:**

```sh
cd backend && uvicorn api.main:app --reload --env-file ../.env   # API on :8000
cd frontend && npm run dev                                       # reads API_URL from ../.env
```

With `USE_FAKE_STORE=true` (the default) the backend reads the recorded fixtures. Set it to `false`
and add `CALA_API_KEY` for live Cala data. Competitor judging needs `GEMINI_API_KEY`.

| Variable | What it's for |
| --- | --- |
| `CALA_API_KEY`, `CALA_BASE_URL` | Cala REST API |
| `GEMINI_API_KEY`, `GEMINI_MODEL_FAST`, `GEMINI_MODEL_SMART` | Competitor judging (and later briefs, agent) |
| `MONGODB_URI`, `MONGODB_DB` | Shared cache and precomputed graph in Atlas; empty = local files in `.cache/` |
| `VERDA_CLIENT_ID`, `VERDA_CLIENT_SECRET` | Verda Cloud API, for creating the instance (`deploy/verda.py`); never copied to the server |
| `VERDA_REGISTRY_USER`, `VERDA_REGISTRY_SECRET` | Verda Container Registry, for pushing the batch image |
| `VERDA_INFERENCE_KEY` | Triggers the serverless batch job |
| `USE_VECTOR_SEARCH`, `GEMINI_EMBED_MODEL` | `true` = competitor candidates also come from vector search over stored companies (on in production; embeddings from Gemini) |
| `VERDA_API_KEY`, `VERDA_EMBED_MODEL` | Not used (Verda's Inference API has no embeddings endpoint) |
| `CALA_PER_MINUTE` | Cala calls one process may make per minute (default 60; the key allows 100) |
| `CALA_REQUIRE_CACHE` | `true` = refuse to call Cala when the cache is unreachable (set on the server) |
| `USE_FAKE_STORE` | `true` = fixtures, `false` = live Cala |
| `CACHE_ONLY` | `true` = serve only from the cache, no Cala calls (demo safety net) |
| `API_URL` | Where the frontend sends `/api/*` |

**Checks:** `pytest backend/tests` and `ruff check backend contracts` (venv active);
`npm run build && npm run lint && npm test` in `frontend/`.

## Deployment (Verda)

One small **Verda CPU instance** hosts the whole product (frontend, API, MCP server) behind Caddy
with automatic HTTPS. The same image, pushed to Verda's Container Registry, runs as a **serverless
Verda batch job** every night (triggered by cron, billed only while it runs) to keep the investor
graph and the cache fresh. The workload is I/O (Cala, Gemini, Atlas), not compute, so there are no
GPUs or Verda Inference.

```sh
python deploy/verda.py create      # create the instance through Verda's Cloud API
deploy/ship.sh <ip>                # ship the current commit, write the server .env, start, nightly cron
python deploy/verda.py batch-run   # trigger the serverless batch job by hand (also: batch-logs)
python deploy/warm.py --check      # warm every page the demo can reach; fail if anything is slow
deploy/cache-only.sh <ip> on       # demo day: answer only from the cache, no live Cala calls
python deploy/verda.py delete      # after the hackathon
```

How we got there: Docker Compose checked locally → instance created via the API → shipped → Atlas
network access fixed (blocked at first, the server called Cala uncached, so it now runs with
`CALA_REQUIRE_CACHE=true`) → cache warmed → cache-only checked (the whole demo path: 50 calls in
22 s, none to Cala).

| Service | Use | Cost |
| --- | --- | --- |
| Verda CPU instance (4 vCPU, 16 GB, FIN-03, on demand) | Hosting (frontend, API, MCP) | EUR 0.044/h, about EUR 1 a day |
| Verda serverless batch job (CPU node) | Nightly investor crawl; under a minute when fresh, ~10 min full | Cents a night |
| Verda Container Registry | The backend image (~130 MB) | USD 0.20 per GB a month |
| MongoDB Atlas M0 | Cala response cache, investor graph, judgements, briefs | Free |
| Cala | ~1,500 calls over the weekend | Hackathon credits |
| Gemini | Competitor judging, briefs, agent | Hackathon key |
| Caddy + Let's Encrypt (`sslip.io`) | HTTPS | Free |

Full notes: [deploy/verda.md](deploy/verda.md).

## Repository

```text
contracts/   shared models (schemas.py), REST API (api.md), recorded Cala fixtures
backend/
  data/      Cala client, live and fake DataStore, parsers, fixture recorder
  cache/     Atlas / file cache of Cala responses, precomputed investor graph
  batch/     investor-graph batch job
  core/      competitors, conflicts, scoring
  agent/     Gemini wrapper, tools, agent loop (Slush prep, chat)
  api/       FastAPI routes
  mcp_server/  MCP server: the same tools for Claude Desktop, Cursor
frontend/    Next.js app, mock API (mock/), design reference (DESIGN.md)
docs/        architecture, demo script, MCP demo, user testing
deploy/      Docker images, compose with Caddy, Verda instance and batch job (verda.md)
```

The team works as three agents with fixed areas (data & infra, intelligence, product); see
[CLAUDE.md](CLAUDE.md) for the coordination rules and [OVERVIEW.md](OVERVIEW.md) for the full plan.
