# Otium — hackathon repo (project: Pitchlist)

Several people, each with their own coding agent, work in this repo at once. `AGENTS.md` points to this
file, so every agent (Claude Code, Codex, Gemini CLI, Cursor) reads the same instructions.

**Read this whole file before writing any code.** You are one of three agents:
**Agent A (Data & infra)**, **Agent B (Intelligence)** or **Agent C (Product)**.
**Your role is in `CLAUDE.local.md`** in the repo root. That file is gitignored, so each clone has its own. If the file is missing, or your human gave you no role, ask your human before doing anything.
Your tasks are in `TODO.md` under your letter. Follow the **Task loop** and the **Gates** below.
The full product write-up is in `OVERVIEW.md`.

> Setup for humans, once per clone: `echo "You are Agent B (Intelligence)." > CLAUDE.local.md`
> Then start each session with: `Read CLAUDE.md, CLAUDE.local.md and TODO.md, then continue with my next task.`

## Project

- **Theme:** Junction 2026 — Cala challenge "Make Unicorns Real": a product for founders/investors built on Cala's public data.
- **Idea:** Pitchlist — who's a fit, and who has a conflict, from either side of the table (details in §1).
- **Stack:** Python/FastAPI backend, Next.js frontend, Cala, Gemini, MongoDB Atlas, Verda (details in §3).
- **Setup (once per clone):** from the repo root, `python3 -m venv .venv && source .venv/bin/activate && pip install -e "backend[dev]"` (Python 3.11+; this also makes `contracts` importable), then `cd frontend && npm install`. Copy `.env.example` to `.env` and fill in what you have.
- **Run:** backend `uvicorn api.main:app --reload --env-file ../.env` from `backend/` (once B1 adds `api/main.py`); frontend `npm run dev` in `frontend/`.
- **Check:** `pytest backend/tests/<your folder>` and `ruff check backend contracts` from the repo root (venv active); `npm run build && npm run lint` in `frontend/`.

---

## Entire (session tracking)

This repo uses [Entire](https://docs.entire.io). Git hooks attach each agent session to a commit as a **checkpoint** (stored in git refs, synced to `origin` on push). That lets everyone see why code exists and what other agents already tried.

- **Set this up once per clone:** `entire enable --agent <claude-code|codex|cursor|...>`. Git hooks are not cloned, so `entire status` shows "Enabled" even when nothing is being recorded. Check that `.git/hooks/post-commit` exists. If it doesn't, commits won't create checkpoints.
- For exact commands and flags, run `entire agent-help`; don't guess.
- **Before starting work**, see what others did: `entire checkpoint list`, `entire recap`, and `entire search "<topic>"`.
- **Before changing code you didn't write**, run `entire why <file>:<line>` or `entire checkpoint explain <sha>`.
- Don't commit `.entire/{tmp,metadata,logs}`; they are already gitignored. Don't edit `.claude/settings.json` hooks by hand.

---

## Coordination rules

The goal is to avoid merge conflicts. They come from long-lived branches and from several people editing the same files.

1. **One branch per task, kept short.** Branch from fresh `main` (`git pull --rebase` first). Name it `<letter>/<task-id>-<slug>`, e.g. `a/A3-cala-client`. Merge back as soon as the task's tests pass (aim for under an hour), then delete the branch. Commit title starts with the task ID: `[A3] Cala client: retries + concurrency limit`. No PR review is needed unless you touch someone else's area. Never force-push `main`.
2. **Stay in your own directory.** Only edit files in the area you own (table below). If you need a change in someone else's area, don't make it: write the request in `notes/<your letter>.md` and tell your human.
3. **Change shared files in small, separate commits.** Dependency manifests (`backend/pyproject.toml`, `frontend/package.json`), `.env.example`, `TODO.md` ticks: minimal edit, own commit, push right away. Don't bundle with feature work.
4. **Contracts are frozen after task T2.** `contracts/` (schemas, API, fixtures format) changes only when all three humans agree. Then bump `CONTRACT_VERSION`, note it in `contracts/CHANGELOG.md`, and update §5 of this file **in the same commit**. Exception: Agent A writes fixture data into `contracts/fixtures/` (tasks A1, A2).
5. **Give each agent its own worktree.** If one person runs several agents, put each in its own git worktree (`git worktree add ../otium-<task> -b <branch>`). Never run two agents in the same folder.
6. **Commit small and often, with clear messages.** Each commit becomes an Entire checkpoint. Write one line saying what changed and why.
7. **Resolve conflicts using intent.** Run `entire why <file>:<line>` on both sides to see what each change was for, then keep both behaviours. Ask a human if the two can't both be kept.
8. **Ask a human before broad refactors**, renaming shared files, or reformatting the whole repo.
9. **Don't add a dependency** if a few lines of code would do. Never commit secrets; put them in `.env`, which must be gitignored. Only Agent A adds variable *names* to `.env.example`.
10. **Keep sources attached and use IDs.** Every fact you pass on keeps its `sources: list[Source]`. Use Cala entity IDs, never names, as keys (Cala has 5 different "Inventure"s).
11. **If a task is unclear or blocked, stop and ask your human.** Don't guess across someone else's area.
12. **An empty key in `.env` doesn't block you.** Build against fakes: `FakeDataStore`, a mocked Gemini client in tests, the frontend mock. Add one line to `notes/<your letter>.md` saying "<task>: not yet checked against live <service>", and do that live check once the key arrives. Only stop if the task can't be done without the real service (A1 needs `CALA_API_KEY`).

### Task loop (every task, exactly like this)

```sh
# 1. Start: fresh main, then pick the task
git switch main && git pull --rebase
git fetch origin 'refs/entire/*:refs/entire/*'      # teammates' checkpoints
#    Next task = your first unchecked task in TODO.md whose `Needs:` are all [x] on main
#    and whose gate (table below) is open. If none is ready, tell your human what you're waiting for.
git switch -c b/B3-find-competitors                 # <letter>/<task-id>-<slug>

# 2. Work: only in your folders, small commits titled "[B3] ..."

# 3. Finish: once the definition of done (below) is met
git fetch origin && git rebase origin/main          # rerun your tests if anything new came in
git switch main && git pull --rebase
git merge --ff-only b/B3-find-competitors           # if it fails, main moved: go back to the branch and repeat step 3
git push origin main && git branch -d b/B3-find-competitors

# 4. Tick: your own TODO.md line only, in its own commit
git add TODO.md && git commit -m "[B3] done" && git push origin main
```

If a push is rejected: `git pull --rebase`, rerun your tests, push again. Never `--force`.
After ticking a task that opens a gate, **tell your human: "Gate Gx is open; tell the others to pull."**

### Gates (when the others can continue)

A gate is open when its task is ticked on `main`. To check: `git pull --rebase && grep -E '^- \[x\] \*\*A2 ' TODO.md` (replace A2 with the task that opens the gate).

| Gate | Opened by | Open when | Unblocks | While waiting |
| --- | --- | --- | --- | --- |
| **G0 Scaffold** | A (with all three) | T1 + T2 ticked | A1 (also needs T3), A3, A5 · B2 · C1, C4 | — |
| **G1 Fixtures** (CP1) | A | **A2** ticked: `contracts/fixtures/models/*.json` + `get_store()` returning `FakeDataStore` | B1, B3, B4 → rest of B on the fake store · C2 → C3, C5–C7 | A: only A1 → A2, nothing else first · B: B2 · C: C1, C4 |
| **G2 Real data** (CP2) | A | **A12** ticked: `USE_FAKE_STORE=false` works for one demo company | B9 | B: B8 and polish on the fake store · C: screens on the mock |
| **G3 Founder E2E** (CP3) | B | **B10** ticked: real `FounderReport`s for the 3 demo companies | C8 · A17 · B11–B15 | A: A13–A16 · C: C7, C9 on the mock |

### Definition of done (every task)

- Code only in your area; contracts untouched.
- Tests for the new code pass (`pytest backend/tests/<your folder>` or `npm run build && npm test` in `frontend/`); `ruff` / `eslint` clean.
- Returns or serves contract models; sources preserved.
- Task ticked in `TODO.md` (your own line only) in a separate small commit.

---

## Areas / owners

| Path | Owner |
| --- | --- |
| `contracts/` | ALL — frozen after T2 (`contracts/fixtures/` data: A) |
| `backend/data/`, `backend/cache/`, `backend/batch/`, `deploy/`, `.env.example` | **A** — Data & infra |
| `backend/core/`, `backend/agent/`, `backend/mcp_server/`, `backend/api/` | **B** — Intelligence |
| `frontend/`, `docs/`, `README.md` | **C** — Product |
| `backend/tests/<folder>/` | owner of that folder |
| `notes/A.md`, `notes/B.md`, `notes/C.md` | that agent only |
| `CLAUDE.md`, `OVERVIEW.md`, `TODO.md` | humans (agents only tick their own TODO line) |

### Repo layout

```text
Otium/
  CLAUDE.md (AGENTS.md → CLAUDE.md)   OVERVIEW.md   TODO.md   README.md (C)
  contracts/        schemas.py, api.md, CHANGELOG.md, fixtures/{raw,models}/*.json
  backend/
    pyproject.toml          shared manifest (rule 3)
    data/                   A  cala_client.py, store.py, fake_store.py, parsers.py, record_fixtures.py
    cache/                  A  atlas.py, vector.py
    batch/                  A  precompute_graph.py
    core/                   B  competitors.py, conflict.py, scoring.py, briefs.py
    agent/                  B  llm.py, gemini_agent.py, tools.py, prompts/
    mcp_server/             B  server.py
    api/                    B  main.py
    tests/                  data/ cache/ batch/ (A) · core/ agent/ mcp_server/ api/ (B)
  frontend/                 C  Next.js app, lib/types.ts, lib/api.ts, mock/
  deploy/                   A  Dockerfile, verda.md
  docs/                     C
  notes/                    A.md, B.md, C.md
```

---

## 1. What we are building

**Pitchlist** — "who's a fit, and who has a conflict, from either side of the table." Slush starts right after the hackathon.

- **Founder mode (main):** founder enters their company → we find its competitors in Cala → their funding rounds → the investors behind them → rank investors to **Pitch** and list investors to **Skip** (conflicts), each claim with a source.
- **Investor mode (the flip):** investor enters their fund + a startup → conflicts with their portfolio, the startup's competitors and who backed them, round history.
- **Slush prep agent:** paste the investors you're meeting → Gemini agent runs our tools → one sourced brief per investor.
- **MCP server:** the same functions exposed as MCP tools, so any agent (Claude Desktop, Cursor) can ask "should I pitch Fund X?".

Conflict = an investor backed a direct competitor (`PORTFOLIO`), or one of its people sits on a competitor's board (`BOARD`).

**Principle:** facts come only from Cala. Scoring is plain, deterministic code. The LLM (Gemini) only (1) judges which candidates are real competitors, (2) formats briefs from already-fetched sourced claims, (3) orchestrates tool calls in the agent/chat. The LLM never invents numbers, dates or investors.

---

## 2. Integration checkpoints

| When | What connects | Done when |
| --- | --- | --- |
| **CP1** Fri night | T1–T3 together, then A1–A2, B1, C1–C2 | `contracts/` merged; B and C run on fakes and mocks |
| Sat 11:00 | Cala workshop | Open questions answered |
| **CP2** Sat ~15:00 | A → B: real `DataStore` replaces the fake | B's eval set passes on live Cala data for 1 company |
| **CP3** Sat ~20:00 (HARD) | B → C: frontend points at the real API | Founder mode end to end on 3 demo companies with sources. If not: cut investor mode / agent / MCP down |
| **CP4** Sat night | Investor mode, Slush prep agent, MCP, batch job | Each works alone; then a joint smoke test |
| **CP5** Sun morning | Freeze → deploy on Verda → pre-cache → rehearse → submit | Demo runs from the deployed URL; backup video recorded |

---

## 3. Stack

| Layer | Choice |
| --- | --- |
| Data | Cala REST API (+ Cala MCP for the demo) |
| LLM / agent | Gemini (API key provided). Flash-tier model for tool loops and competitor judging; Pro-tier only for brief formatting if quality requires |
| DB | MongoDB Atlas (cache by entity ID, precomputed graph, Atlas Vector Search) |
| Embeddings | Open-weight embedding model via Verda Inference API; Gemini embeddings as fallback |
| Precompute | Verda batch job (nightly) |
| Hosting | Verda CPU instance (backend + MCP server, Docker) |
| Backend | Python 3.11+, FastAPI, Pydantic v2, httpx (async), official MCP Python SDK, pytest, ruff |
| Frontend | Next.js (App Router) + TypeScript + Tailwind |
| Not used | Tiger Data, GPU clusters, fine-tuning |

### Environment variables (`.env`, names owned by A)

```text
CALA_API_KEY=
CALA_BASE_URL=https://api.cala.ai/v1
GEMINI_API_KEY=
GEMINI_MODEL_FAST=          # Flash-tier model id
GEMINI_MODEL_SMART=         # Pro-tier model id (optional)
MONGODB_URI=
MONGODB_DB=pitchlist
VERDA_API_KEY=
VERDA_EMBED_MODEL=
USE_FAKE_STORE=true         # B and C develop on fixtures until the real store is ready (CP2)
CACHE_ONLY=false            # true = demo runs from the Atlas cache with no Cala calls
API_URL=http://localhost:8000   # frontend → backend; C's mock runs on another port
```

---

## 4. Cala — what we know (tested 13 Nov)

- REST base `https://api.cala.ai/v1`, header `X-API-KEY: <key>`, `Content-Type: application/json`. Keys at console.cala.ai/api-keys; hackathon credits with promo code `MAKEUNICORNSREAL` (Billing → Extra credits).
  Exact query params/paths for the entity endpoints: **verify at docs.cala.ai/api-reference** before coding.
- `POST /knowledge/query` `{"input": "..."}` → structured rows + `entities[]` (IDs). Natural language or dot-notation: `companies.industry=X.country=Finland.funding_stage=Seed OR Series A.return(name, description, funding_stage, total_funding).limit=15`. Numbers come back as approximate strings ("~€15M", "over $100M").
- `POST /knowledge/search` `{"input": "..."}` → markdown answer + `explainability[]` (claim → reference IDs) + `context[]` (reference ID → source URL). Best source for "who led which round".
- Entity search by name (fuzzy, filter by entity type), entity lookup by LEI/CIK/etc., entity retrieval by UUID with a projection body `{"properties": [...], "relationships": {"outgoing": {"REL": {"limit": N}}, "incoming": {...}}}`, entity introspection (which fields/relationships exist for that entity).
- **Company** relationships: outgoing `OPERATES_IN_INDUSTRY`, `PARTICIPATES_IN_FUNDING_ROUND` (role `ISSUER`), `HAS_DOMAIN_NAME`; incoming `INVESTED_IN`, `IS_BOARD_MEMBER_OF`, `FOUNDED`, `IS_CEO_OF`, `WORKS_AT`. Properties incl. `funding_stage`, `total_funding`, `founding_date`, `headquarters_address`, `description`.
- **Investor** (Organization) relationships: outgoing `INVESTED_IN` (portfolio, sourced, **no dates**), `PARTICIPATES_IN_FUNDING_ROUND` (role `INVESTOR`, sometimes `is_lead: true` — sparse).
- **FundingRound** properties: `round_label`, `announcement_date`, `transaction_value`, `transaction_value_units`, `instrument`.
- Every property/relationship carries `sources[]` with `name`, `document` (URL), `date`, `source_rank` (`PRIMARY` | `FILING` | `PRESS` | `AGGREGATOR`; may be missing → `UNKNOWN`).
- Industry tags are coarse (all defence → `AEROSPACE_AND_DEFENSE`) → competitors need vector search + LLM judging.
- Known mismatch: "Inflection" (VC) resolved to Inflection AI → always check type + description for investors.

Demo data: Kelluu (Series A, led by NATO Innovation Fund; also Keen Venture Partners, Gungnir Capital, Tesi). Maki.vc leads defence pre-seeds (Aavuus, Metaktik). Counter-drone set for a conflict demo: Sensofusion, Stendr, Nordic Air Defence.

---

## 5. Contracts (summary of `contracts/`; the files win if they differ)

### 5.1 Models — `contracts/schemas.py`

```python
from typing import Literal, Protocol
from pydantic import BaseModel

CONTRACT_VERSION = "1.1.0"

SourceRank = Literal["PRIMARY", "FILING", "PRESS", "AGGREGATOR", "UNKNOWN"]

class Source(BaseModel):
    name: str
    url: str | None = None
    date: str | None = None          # ISO date or partial ("2025-10")
    rank: SourceRank = "UNKNOWN"

class EntityRef(BaseModel):
    id: str                          # Cala UUID
    name: str
    type: str                        # Company | Organization | Person | FundingRound ...
    description: str | None = None

class Company(EntityRef):
    industries: list[str] = []
    stage: str | None = None
    country: str | None = None
    total_funding_text: str | None = None
    sources: list[Source] = []

class RoundInvestor(BaseModel):
    investor: EntityRef
    is_lead: bool | None = None      # None = unknown

class Round(BaseModel):
    id: str
    company_id: str
    label: str | None = None         # "Seed", "Series A" ...
    date: str | None = None
    amount_text: str | None = None
    amount_eur: float | None = None
    investors: list[RoundInvestor] = []
    sources: list[Source] = []

class PortfolioLink(BaseModel):
    investor_id: str
    company: EntityRef
    sources: list[Source] = []

class PersonLink(BaseModel):
    person: EntityRef
    company_id: str
    role: Literal["BOARD", "FOUNDER", "CEO", "EMPLOYEE"]
    sources: list[Source] = []

class Competitor(BaseModel):
    company: Company
    reason: str
    similarity: float | None = None

class Conflict(BaseModel):
    kind: Literal["PORTFOLIO", "BOARD"]
    competitor: EntityRef
    via_person: EntityRef | None = None
    sources: list[Source] = []

class Reason(BaseModel):
    text: str
    sources: list[Source] = []

class InvestorScore(BaseModel):
    investor: EntityRef
    score: float                     # 0-100, higher = better fit
    conflicts: list[Conflict] = []   # non-empty = this investor belongs in `skip`
    leads_in_space: int = 0
    rounds_in_space: int = 0
    lead_data: Literal["known", "partial", "unknown"] = "unknown"   # how far leads_in_space rests on is_lead
    last_lead_date: str | None = None
    deals_last_12m: int | None = None    # None = unknown
    warm_paths: list[Reason] = []
    reasons: list[Reason] = []

class FounderReport(BaseModel):
    company: Company
    competitors: list[Competitor]
    pitch: list[InvestorScore]       # no conflicts; sorted by score, highest first
    skip: list[InvestorScore]        # one or more conflicts; sorted by score, highest first

class InvestorCheck(BaseModel):
    investor: EntityRef
    company: Company
    conflicts: list[Conflict]
    competitors: list[Competitor]
    rounds: list[Round]              # rounds of `company` AND of every competitor; group by Round.company_id

class Brief(BaseModel):
    investor_id: str
    company_id: str
    markdown: str                    # cites with [n] markers: n is a 1-based index into `citations`
    citations: list[Source]

class AgentEvent(BaseModel):          # streamed by /api/jobs/{id}/stream and /api/chat
    type: Literal["step", "text", "brief", "error", "done"]   # step = progress, text = answer chunk
    message: str | None = None
    brief: Brief | None = None
    investor_name: str | None = None     # slush-prep: the pasted name this event belongs to
    investor: EntityRef | None = None    # slush-prep: the resolved investor, once known
    citations: list[Source] = []         # chat: sent on `done`; [n] in the text is a 1-based index into it
```

### 5.2 Data layer interface — A implements, B consumes

```python
class DataStore(Protocol):
    async def resolve(self, name: str, kind: Literal["company", "investor"]) -> list[EntityRef]: ...
    async def company(self, id: str) -> Company: ...
    async def rounds(self, company_id: str) -> list[Round]: ...
    async def investor_rounds(self, investor_id: str) -> list[Round]: ...
    async def portfolio(self, investor_id: str) -> list[PortfolioLink]: ...
    async def people(self, company_id: str) -> list[PersonLink]: ...
    async def candidate_competitors(self, company: Company, k: int = 30) -> list[Company]: ...
    async def co_investors(self, investor_id: str) -> list[tuple[EntityRef, int]]: ...
    async def sourced_answer(self, question: str) -> tuple[str, list[Reason]]: ...  # knowledge_search
```

`backend/data/__init__.py` exposes `get_store() -> DataStore`, returning `FakeDataStore` when `USE_FAKE_STORE=true`, else the real store. B only ever calls `get_store()`.

- `company(id)` works for any organisation ID, including an investor.
- `people(id)` also accepts an investor ID and returns that investor's own people (BOARD conflicts need this).
- `co_investors(id)` returns `[]` when nothing is known yet (the precomputed graph arrives after the real store); it never raises for that.

### 5.3 REST API — B implements, C consumes

| Method | Path | Body | Returns |
| --- | --- | --- | --- |
| POST | `/api/resolve` | `{name, kind}` | `EntityRef[]` |
| POST | `/api/founder/analyze` | `{company_id, competitor_ids?: string[]}` | `FounderReport` |
| POST | `/api/investor/check` | `{investor_id, company_id}` | `InvestorCheck` |
| POST | `/api/brief` | `{investor_id, company_id}` | `Brief` |
| POST | `/api/slush-prep` | `{company_id, investor_names: string[]}` | `{job_id}` |
| GET | `/api/jobs/{id}/stream` | — | SSE stream of `AgentEvent` |
| POST | `/api/chat` | `{company_id?, investor_id?, message}` | SSE stream of `AgentEvent` (type `text` = answer chunks) |
| GET | `/api/health` | — | `{ok: true, contract_version}` |

Errors: HTTP 4xx/5xx with `{error: string}`. CORS open for the frontend origin.

- `competitor_ids` (optional): if given, B skips competitor discovery and ranks against exactly those company IDs. The frontend sends the IDs still shown after the user removed some.
- Streams: one `data: <AgentEvent JSON>\n\n` per event, no named events; the stream closes after `done`. `/api/chat` is read with a streaming `fetch`.
- Slush prep: events about one pasted investor carry `investor_name` (as pasted) and, once resolved, `investor`. An unresolved or ambiguous name gets an `error` event with that `investor_name`.
- Chat: the answer arrives as `text` events; its sources arrive in `citations` on the `done` event.
- Full rules: `contracts/api.md`.

### 5.4 MCP tools — B implements (thin wrappers over core)

`resolve_company`, `find_competitors`, `get_rounds`, `investor_profile`, `check_conflict`, `rank_investors`, `investor_brief`. Inputs are entity IDs (plus `name` for `resolve_company`); outputs are the contract models as JSON.

### 5.5 Fixtures — `contracts/fixtures/`

- `raw/` — raw Cala responses (A records them; never hand-edited).
- `models/` — contract-model JSON built from raw (`company_<id>.json`, `rounds_<company_id>.json`, `portfolio_<investor_id>.json`, ...). The full file list is in `contracts/api.md`; `models/index.json` lists the demo cases and their IDs.
- `FakeDataStore` reads `models/`. C's mock API serves the sample responses A also produces in A2: `resolve_<kind>_<slug>.json`, `founder_report_<company_id>.json`, `investor_check_<investor_id>_<company_id>.json`, `brief_<investor_id>_<company_id>.json`, `agent_events_slush_prep.json`, `agent_events_chat.json`. They are real Cala facts in the right shape, but ranked by a placeholder until B's API replaces them at CP3.

---

## 6. Role briefs

### Agent A — Data & infra

You own the **only** code that talks to Cala, Atlas and Verda. Everything you return is a contract model with sources attached.

- `cala_client.py`: async httpx client, `X-API-KEY`, retries with backoff, concurrency limit (semaphore, start at 8), timeout, log every call (endpoint, ms, cache hit) for credit tracking.
- `store.py`: `CalaDataStore` implementing `DataStore`. Map Cala JSON → models in small, tested mapper functions (one per model). Use introspection results to request only existing fields.
- `parsers.py`: amount text → EUR float (handle ~, over, M/B/K, $ / € / £ with a fixed FX table), partial dates → ISO prefix. Unparseable → `None`, never raise.
- Investor resolution: filter to Organization/Company types; prefer descriptions mentioning venture/capital/fund/invest.
- `cache/atlas.py`: wrap every Cala call — key = endpoint + entity ID or hash of input; TTL 24 h; `CACHE_ONLY=true` mode for the demo (no network).
- `cache/vector.py`: embed `name + description`; Atlas Vector Search index; `candidate_competitors` = top-k vector neighbours ∪ `knowledge_query` on same industry + Nordic/Baltic countries + adjacent stages; dedupe by ID; exclude the company itself.
- `batch/precompute_graph.py`: Verda batch job — list active Nordic/Baltic investors, fetch portfolios and rounds, write `investor_graph` (co-investor counts), `investor_activity` (last lead, rounds per sector/stage) and embeddings to Atlas. Idempotent, resumable, logs progress.
- `deploy/`: Dockerfile for the backend (API + MCP server), run instructions for a Verda CPU instance in `deploy/verda.md`.

### Agent B — Intelligence

You own the logic. Develop on `FakeDataStore` (`USE_FAKE_STORE=true`); never call Cala directly — always `get_store()`.

- `core/competitors.py`: `find_competitors(company) -> list[Competitor]`. Get candidates from the store, ask Gemini (fast model, structured JSON output, temperature 0) to keep 10–15 direct competitors with a one-line reason each. Output may only contain candidate IDs (reject anything else).
- `core/conflict.py`: `check_conflict(investor_id, competitors) -> list[Conflict]`. PORTFOLIO = `portfolio(investor)` ∩ competitor IDs. BOARD = people of each competitor with role BOARD who are linked to the investor. Sources = union of the edges used.
- `core/scoring.py`: `rank_investors(company) -> FounderReport`. Investors = everyone in competitors' rounds. Signals: `leads_in_space`, `rounds_in_space`, recency of last lead, warm paths (`co_investors` overlap with the company's current investors). Any conflict → `skip`. Weights in one dict at the top of the file. Every number in `reasons` has sources.
- `core/briefs.py`: `investor_brief(investor_id, company_id) -> Brief`. Facts from store + `sourced_answer()`; Gemini only formats into one page; every sentence must map to a citation.
- `agent/`: Gemini function-calling loop over `tools.py` (core functions + `sourced_answer`). Max 12 tool calls per job, emits `AgentEvent`s. Powers slush-prep and chat.
- `mcp_server/server.py`: MCP tools from §5.4.
- `api/main.py`: routes exactly per §5.3, responses validated by the models, CORS, `/api/health`.
- Tests: `backend/tests/core/` with an eval set of known cases (TODO B8).

### Agent C — Product

You own what people see. Develop against `frontend/mock/` (fixture-based, same shapes as §5.3); switch to the real backend by setting `API_URL`.

- TypeScript types in `frontend/lib/types.ts` mirror `contracts/schemas.py` exactly (same field names).
- One API client module `frontend/lib/api.ts`; components never call `fetch` directly.
- Screens: Home (mode toggle + entity resolve/confirm), Founder report (competitor chips, Pitch list, Skip list with conflict reason first), Investor brief, Investor check, Slush prep (paste list → live agent steps → brief cards), Chat panel.
- Every claim shows a **source badge**: rank (Primary / Filing / Press / Aggregator), date, link.
- States: loading, empty, error for every screen. Fast, clean, no clutter.
- `docs/` + `README.md`: setup, architecture, how Cala/Gemini/Atlas/Verda are used, demo script, pitch notes. Verda's judges require the process to be documented.
