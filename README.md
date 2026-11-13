# Pitchlist

**Who's a fit, and who has a conflict, from either side of the table.**
Built at Junction 2026 for Cala's "Make Unicorns Real" challenge.

Founders build investor lists from logo walls and gut feeling, then spend weeks pitching funds that
were never going to say yes, including funds that already backed a direct competitor. Pitchlist
walks Cala's graph of companies, rounds and investors to answer two questions, with a source on
every claim:

- **Founder mode:** *Who should I pitch, and who should I skip?* Enter your company and get a ranked
  **Pitch** list and a **Skip** list of investors who backed a direct competitor or sit on its board.
- **Investor mode (the flip):** *Does this startup conflict with my portfolio, and who backed its
  rivals?* Enter your fund and a startup that pitched you.

Coming next: a Slush prep agent (paste the investors you're meeting, get one sourced brief each) and
an MCP server, so any agent can ask "should I pitch Fund X?".

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
| `VERDA_API_KEY`, `VERDA_EMBED_MODEL` | Embeddings for competitor search (planned) |
| `USE_FAKE_STORE` | `true` = fixtures, `false` = live Cala |
| `CACHE_ONLY` | `true` = serve only from the cache, no Cala calls (demo safety net) |
| `API_URL` | Where the frontend sends `/api/*` |

**Checks:** `pytest backend/tests` and `ruff check backend contracts` (venv active);
`npm run build && npm run lint && npm test` in `frontend/`.

## Repository

```text
contracts/   shared models (schemas.py), REST API (api.md), recorded Cala fixtures
backend/
  data/      Cala client, live and fake DataStore, parsers, fixture recorder
  cache/     Atlas / file cache of Cala responses, precomputed investor graph
  batch/     investor-graph batch job
  core/      competitors, conflicts, scoring
  agent/     Gemini wrapper (agent loop coming)
  api/       FastAPI routes
frontend/    Next.js app, mock API (mock/), design reference (DESIGN.md)
docs/        architecture, user testing
deploy/      deployment (coming)
```

The team works as three agents with fixed areas (data & infra, intelligence, product); see
[CLAUDE.md](CLAUDE.md) for the coordination rules and [OVERVIEW.md](OVERVIEW.md) for the full plan.
