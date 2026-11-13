# Pitchlist — Project Overview

Nov 13, 2026 · @Atis Dubrovskis

## The idea

**Pitchlist tells you who's a fit and who has a conflict, from either side of the table.** It's a web app plus an MCP server, built on Cala's connected, sourced data on companies, funding rounds and investors.

**The problem.** Founders build investor lists from logo walls and gut feeling, then waste weeks on three kinds of investor who were never going to say yes:

- **Funds that don't lead.** They join rounds but rarely set the terms.
- **Funds that have gone quiet.** No new lead in 12+ months, and the fund is near the end of its life.
- **Funds with a conflict.** They already backed a direct competitor, so pitching them means handing your deck to a rival's board member.

Investors have the mirror problem. At Slush they meet 30+ startups in two days and need to know fast whether a startup competes with their portfolio and who has backed its rivals.

**Why Cala.** Spotting a conflict means walking the graph: company → competitors → rounds → investors → back to you. Web search can't do that reliably. Cala's connected, sourced data can, and every claim we show links to its source.

## Users and modes

One product with a toggle, "I'm raising / I'm investing," running on one engine. **Founder mode is the main product; investor mode is the flip.**

|  | Founder mode (main) | Investor mode (the flip) |
| --- | --- | --- |
| User | Seed or Series A founder about to raise, e.g. at Slush | Angel, VC associate or partner screening deals |
| Input | My company | My fund plus a startup that pitched me |
| Question | Who should I pitch, and who should I skip? | Is this a fit, does it conflict with my portfolio, and who backed its rivals? |
| Output | Ranked investor list, a "don't pitch" list with reasons, a one-page brief per investor | One-screen check: conflict flags, market map, round history |
| Slush use | Paste the investors you're meeting, get prep briefs | Paste a startup between meetings, get a 60-second check |

**Out of scope:** accounts, matching, messaging, anything that needs both sides active at once. It's not a marketplace.

## How it works

It's a fixed pipeline that calls Cala directly, so it's fast, gives the same answer every time, and can trace every claim to its source. The LLM is used in only two steps: judging who counts as a competitor, and writing the briefs. Every number comes from Cala, and the scoring is plain code.

**Founder mode**

1. **Resolve the company.** `entity_search` by name, confirm with the user if there's more than one match, then `retrieve_entity` for sector, stage, location and description.
2. **Find competitors.** `knowledge_query` for companies in the same sector, stage and region. *LLM step:* read the descriptions and keep 10–15 direct competitors, with a one-line reason for each.
3. **Pull their rounds.** One `knowledge_query` per competitor, in parallel: date, amount, investors, and whether each investor led. Cache everything.
4. **Check each investor's activity.** For the top investors, query their recent rounds: when they last led, in which sectors, at what stage.
5. **Score them** in code (see Scoring).
6. **Write the briefs.** *LLM step:* a one-page brief per investor, written only from the rows already fetched, with a source on every claim. Use `knowledge_search` (sourced prose) for small gaps.

**Investor mode** runs the same steps from the other side. Step 1 resolves the fund and the startup. Step 2 finds the startup's competitors. The fund's portfolio is then compared with that competitor set: any overlap is a conflict, and steps 3–4 build the market map and round history.

**Rule:** every data row keeps its Cala source link from fetch to UI, so any claim can show its source in one click.

## Architecture

&#91;embedded content: architecture · 2 entry points, 1 core, Cala underneath\]

The web app and the MCP server call the same core functions. Data flows from the data layer to scoring to the Gemini steps. Every Cala response is cached in Atlas, and a nightly Verda batch job precomputes the Nordic investor graph so demo lookups are instant.

### Stack

| Layer | Choice | Why |
| --- | --- | --- |
| Data source | Cala (REST API + MCP) | Sourced graph of companies, rounds, investors and people; the core of the product |
| Agent / LLM | Gemini (provided keys): a Flash-tier model for the tool loop and competitor judging, a Pro-tier model for briefs only if quality needs it | Strong function calling, fast and cheap for multi-step loops |
| Database | MongoDB Atlas | Cala returns JSON, so cache it as documents keyed by entity ID; Atlas Vector Search finds the closest companies to yours (competitor candidates) |
| Embeddings | Open-weight embedding model on Verda Inference API (or Gemini embeddings as fallback) | Vectors for company descriptions |
| Precompute | Verda batch job, nightly | Crawls every active Nordic and Baltic investor's portfolio from Cala, builds the co-investor graph, activity stats and embeddings ahead of time |
| Hosting | Verda CPU instance | Runs the FastAPI backend and the MCP server; gives a believable path from demo to real users |
| Backend | Python, FastAPI, Pydantic, official MCP Python SDK | One language for data, scoring, agent and MCP |
| Frontend | Next.js + Tailwind | Fast to build, easy to deploy |
| Not used | Tiger Data, Verda GPU clusters, fine-tuning | No real need; forcing them in hurts focus (and Verda's "Fit" score) |

### How we use Cala

**Graph for structure, search for narrative, IDs everywhere.** Each Cala feature has one job:

| Cala feature | Its job in Pitchlist |
| --- | --- |
| `entity_search` | Resolve names to entity IDs; the user confirms when several match (there are 5 "Inventure"s) |
| `entity_introspection` | Run once per entity type at startup and cache which fields and relationships exist; never request fields blind |
| `entity_retrieval` with relationship projections | The backbone. `INVESTED_IN` for portfolios and conflicts, `PARTICIPATES_IN_FUNDING_ROUND` for rounds and `is_lead`, `IS_BOARD_MEMBER_OF` / `FOUNDED` / `WORKS_AT` for board-seat conflicts and warm paths |
| `knowledge_query` (dot-notation) | Discovery: candidate competitors and recent rounds by industry, country and stage. Its `entities[]` IDs feed straight into `entity_retrieval` (query first, then walk the graph) |
| `knowledge_search` | Fills gaps the graph is thin on (who led, how recently). Its `explainability` claims plus their references are shown as citations as-is, not rewritten by the LLM |
| Source metadata | Every claim shows a source badge built from `source_rank` (PRIMARY / FILING / PRESS / AGGREGATOR) and date; prefer primary sources when facts conflict |

**What this lets us show that web search can't:** conflicts several hops away (competitor → investor → partner → board seat), co-investor warm paths, and how reliable each claim is.

## Scoring

An investor's score is the sum of four signals, and a conflict overrides the score. All of it is plain code with readable reasons, and the weights are a first guess to tune on real data on Saturday.

| Signal | What it measures | Shown as |
| --- | --- | --- |
| Conflict | Backed a direct competitor (founder mode) or holds one (investor mode); or its partner sits on a competitor's board | Hard flag → "Don't pitch" list, with the competitor and a source |
| Leads in your space | Share of their rounds in your sector and stage where they led | "Led 4 of 6 fintech seeds" |
| Still active | Months since their last lead; number of new deals in the last 12 months | "Last lead: Mar 2026" |
| Warm path | Co-invested with your existing investors, or backs founders you know | "Co-invested with Inventure 3×" |

If Cala doesn't mark lead investors, "leads in your space" falls back to how often they appear in your space at all, and the UI says so.

## MCP tools

The web app and the MCP server call the same functions. Any agent (Claude Desktop, Cursor, ChatGPT) can ask "Should I pitch Fund X?", and the answer comes back sourced through our tools and Cala.

| Tool | Input | Returns |
| --- | --- | --- |
| `resolve_company` | name | Cala entity: ID, sector, stage, location |
| `find_competitors` | company ID | 10–15 direct competitors, with a reason each |
| `get_rounds` | company ID | Rounds: date, amount, investors, lead flag, source |
| `investor_profile` | investor ID | Recent leads, sectors, stages, last activity |
| `check_conflict` | investor ID + company ID | Conflict yes/no, the competitor(s), sources |
| `rank_investors` | company ID | Scored investor list plus the "don't pitch" list |
| `investor_brief` | investor ID + company ID | One-page sourced brief (markdown) |

**Stretch goal:** a follow-up chat on the results page ("What else has Fund X led in fintech this year?"), where an agent calls these tools plus Cala's own MCP.

## Implementation: three parallel workstreams

**Each person owns separate folders and works against shared contracts and fixtures, so nobody waits on anyone or edits the same file.** The contracts are written together on Friday night (about 1 hour) and then frozen.

### Rules

1. **Folder ownership.** You only commit inside your own folders. Need something changed elsewhere? Ask the owner.
2. **Contracts are frozen after Friday night.** `contracts/` changes only when all three agree; bump `CONTRACT_VERSION` and post in the team chat.
3. **Fixtures are the shared truth.** Real Cala responses recorded Friday night, saved as JSON in `contracts/fixtures/`. B builds against `FakeDataStore` (reads fixtures); C builds against a mock API that serves fixture-based responses.
4. **Branch per person, small PRs, merge often.** Since folders don't overlap, merges are trivial.
5. **Secrets.** `.env.example` is owned by A. Never commit keys (Cala, Gemini, Atlas, Verda).

### Repo layout and owners

```text
pitchlist/
  contracts/            ALL (frozen)  schemas.py, api.md, fixtures/*.json
  backend/
    data/               A   cala_client.py, store.py (DataStore), fake_store.py, parsers.py
    cache/              A   atlas.py, vector.py
    batch/              A   precompute_graph.py (Verda batch job)
    core/               B   competitors.py, conflict.py, scoring.py, briefs.py
    agent/              B   gemini_agent.py, tools.py, prompts/
    mcp_server/         B   server.py
    api/                B   main.py (FastAPI routes, thin)
    tests/              each person tests their own folder
  frontend/             C   Next.js app, mock/ (mock API)
  deploy/               A   Dockerfile, verda setup, .env.example
  docs/                 C   README, demo script, architecture notes
```

### Contract 1: data models (`contracts/schemas.py`)

Every fact carries its sources. Amounts stay as text (Cala returns "\~€15M"), with an optional parsed number.

```python
class Source(BaseModel): name: str; url: str | None; date: str | None; rank: Literal["PRIMARY","FILING","PRESS","AGGREGATOR","UNKNOWN"]
class EntityRef(BaseModel): id: str; name: str; type: str; description: str | None
class Company(EntityRef): industries: list[str]; stage: str | None; country: str | None; total_funding_text: str | None; sources: list[Source]
class RoundInvestor(BaseModel): investor: EntityRef; is_lead: bool | None
class Round(BaseModel): id: str; company_id: str; label: str | None; date: str | None; amount_text: str | None; amount_eur: float | None; investors: list[RoundInvestor]; sources: list[Source]
class PortfolioLink(BaseModel): investor_id: str; company: EntityRef; sources: list[Source]
class PersonLink(BaseModel): person: EntityRef; company_id: str; role: Literal["BOARD","FOUNDER","CEO","EMPLOYEE"]; sources: list[Source]
class Competitor(BaseModel): company: Company; reason: str; similarity: float | None
class Conflict(BaseModel): kind: Literal["PORTFOLIO","BOARD"]; competitor: EntityRef; via_person: EntityRef | None; sources: list[Source]
class Reason(BaseModel): text: str; sources: list[Source]
class InvestorScore(BaseModel): investor: EntityRef; score: float; conflict: Conflict | None; leads_in_space: int; rounds_in_space: int; last_lead_date: str | None; warm_paths: list[Reason]; reasons: list[Reason]
class FounderReport(BaseModel): company: Company; competitors: list[Competitor]; pitch: list[InvestorScore]; skip: list[InvestorScore]
class InvestorCheck(BaseModel): investor: EntityRef; company: Company; conflicts: list[Conflict]; competitors: list[Competitor]; rounds: list[Round]
class Brief(BaseModel): investor_id: str; company_id: str; markdown: str; citations: list[Source]
```

### Contract 2: data layer interface (A provides, B consumes)

```python
class DataStore(Protocol):
    def resolve(self, name: str, kind: Literal["company","investor"]) -> list[EntityRef]
    def company(self, id: str) -> Company
    def rounds(self, company_id: str) -> list[Round]
    def investor_rounds(self, investor_id: str) -> list[Round]
    def portfolio(self, investor_id: str) -> list[PortfolioLink]
    def people(self, company_id: str) -> list[PersonLink]
    def candidate_competitors(self, company: Company, k: int = 30) -> list[Company]   # vector search + knowledge_query
    def co_investors(self, investor_id: str) -> list[tuple[EntityRef, int]]         # from precomputed graph
    def sourced_answer(self, question: str) -> tuple[str, list[Source]]             # knowledge_search
```

### Contract 3: REST API (B provides, C consumes)

| Method | Path | Body | Returns |
| --- | --- | --- | --- |
| POST | `/api/resolve` | `{name, kind}` | `EntityRef[]` |
| POST | `/api/founder/analyze` | `{company_id}` | `FounderReport` |
| POST | `/api/investor/check` | `{investor_id, company_id}` | `InvestorCheck` |
| POST | `/api/brief` | `{investor_id, company_id}` | `Brief` |
| POST | `/api/slush-prep` | `{company_id, investor_names[]}` | `{job_id}` |
| GET | `/api/jobs/{id}/stream` | — | Server-sent events: agent steps, then `Brief[]` |
| POST | `/api/chat` | `{company_id?, investor_id?, message}` | Streamed text plus citations |

### Workstream A — Data & infra

**Owns:** `backend/data`, `backend/cache`, `backend/batch`, `deploy`. **Delivers:** a `DataStore` that returns contract models from real Cala data, fast and cached.

**Friday night (first, everyone depends on it)**

- [ ] Record fixtures: run 5 demo companies and \~10 investors through Cala; save raw responses to `contracts/fixtures/` (needs to include one counter-drone set, e.g. Sensofusion, Stendr, Nordic Air Defence)
- [ ] `fake_store.py`: `FakeDataStore` that returns contract models built from the fixtures, handed to B

**Saturday**

- [ ] `cala_client.py`: async REST client (`X-API-KEY`), retries, concurrency limit, logging of credit use
- [ ] `entity_introspection` once per entity type → a cached map of available fields and relationships
- [ ] `store.py`: real `DataStore`; every method maps Cala JSON → contract models, keeping `sources` (name, URL, date, `source_rank`)
- [ ] `parsers.py`: amount text ("\~€15M", "over $100M") → `amount_eur`; partial dates ("Oct 2025")
- [ ] Investor matching guard: check type and description (avoid the "Inflection" → Inflection AI mismatch)
- [ ] `cache/atlas.py`: cache every Cala response by entity ID plus query hash, with a 24 h TTL
- [ ] `cache/vector.py`: embed company descriptions (Verda Inference API); Atlas Vector Search index; `candidate_competitors()` = vector neighbours merged with a `knowledge_query` on industry + country + stage

**Saturday night**

- [ ] `batch/precompute_graph.py` as a Verda batch job: list active Nordic and Baltic investors → portfolios + rounds → store the co-investor edges, last-lead dates and embeddings in Atlas
- [ ] `co_investors()` reads the precomputed graph
- [ ] Deploy the backend + MCP server to a Verda CPU instance (Dockerfile, env vars, HTTPS)

**Sunday morning:** pre-cache the 3 demo companies, check the deploy is stable, write deploy notes for the docs.

### Workstream B — Intelligence

**Owns:** `backend/core`, `backend/agent`, `backend/mcp_server`, `backend/api`. **Delivers:** the logic and the API, built on `FakeDataStore` until A's real store is ready (swapping it in is one line).

**Saturday**

- [ ] `core/competitors.py`: Gemini (Flash-tier, structured JSON output) reads the candidates and returns 10–15 `Competitor`s, with a reason for each
- [ ] `core/conflict.py`: PORTFOLIO conflict (an investor's `portfolio()` intersects the competitor set); BOARD conflict (an investor's people are `BOARD` on a competitor, via `people()`)
- [ ] `core/scoring.py`: plain-code score from leads in your space, recency of last lead, and warm paths (`co_investors()` overlap with your current investors); conflict → the skip list. Every reason carries its sources
- [ ] `api/main.py`: FastAPI routes exactly per Contract 3; resolve, founder/analyze and investor/check first
- [ ] Eval set: 5 known cases (e.g. Kelluu → NATO Innovation Fund, Maki.vc defence leads) as tests, run on every change

**Saturday night**

- [ ] `core/briefs.py`: one `knowledge_search` per investor–company pair; keep its `explainability` claims and references as citations; Gemini only formats them into one page, adding no new facts
- [ ] `agent/gemini_agent.py`: function-calling loop over `agent/tools.py` (our core functions + Cala search); powers `/api/slush-prep` (plans the calls for a pasted investor list and streams each step) and `/api/chat`
- [ ] `mcp_server/server.py`: the MCP tools from the MCP tools section, each a thin wrapper over the core functions; test in Claude Desktop

**Sunday morning:** tune the scoring weights on real data, tighten the prompts, make sure every API response matches the contract (validate against the Pydantic models).

### Workstream C — Product

**Owns:** `frontend`, `docs`. **Delivers:** the app people use, the demo and the story. Builds against `frontend/mock/` (fixture-based responses in the Contract 3 shapes) until B's API is up; switching over is one env var (`API_URL`).

**Friday night**

- [ ] Next.js scaffold, mock API from fixtures, TypeScript types mirroring `contracts/schemas.py`

**Saturday**

- [ ] Home: "I'm raising / I'm investing" toggle; company (or fund + startup) input → `/api/resolve` → confirm the right entity
- [ ] Founder report: competitor chips (removable), a ranked **Pitch** list and a **Skip** list with the conflict reason up front
- [ ] Source badges on every claim: rank (Primary / Filing / Press / Aggregator) + date, with a click-through link
- [ ] Investor brief page (markdown + citations)
- [ ] Investor mode: one-screen check (conflicts, market map, round history)
- [ ] Show the founder report to 3–5 founders at Junction; write down one quote for the pitch

**Saturday night**

- [ ] Slush prep: paste investor names → live agent progress (server-sent events) → brief cards
- [ ] Follow-up chat panel
- [ ] Claude Desktop setup with Cala + Pitchlist MCP for the demo

**Sunday morning:** loading and empty states, the demo script and pitch slides, README (setup, architecture, how Verda is used: their judges require documented process), screen-record a backup demo video.

### Integration checkpoints

The three streams only meet at these points. Between them, everyone works alone on their own folders.

| When | What connects | Done when |
| --- | --- | --- |
| Fri night | All three: write the contracts, record fixtures, scaffold the repo | `contracts/` merged; B and C can run on fakes and mocks |
| Sat 11:00 | Cala workshop: ask the open questions | Answers noted; contracts adjusted only if a question forces it |
| Sat \~15:00 | A → B: real `DataStore` replaces the fake | B's eval set passes on live Cala data for 1 company |
| Sat \~20:00 | B → C: frontend points at the real API. **Hard checkpoint** | Founder mode works end to end on 3 demo companies with sources. If not, investor mode, the agent and MCP get cut down |
| Sat night | Investor mode, Slush prep agent, MCP, batch job | Each works on its own; then a joint smoke test |
| Sun morning | Feature freeze → deploy on Verda → pre-cache → rehearse twice → submit | Demo runs from the deployed URL; backup video recorded |

## Risks and open questions

| Risk | Fallback |
| --- | --- |
| Lead investors aren't marked in rounds | Use "first investor listed" or how often they appear; label it in the UI; lean on investor mode, which doesn't need leads |
| Thin coverage of early-stage Nordic companies | Pick demo companies Cala covers well; say clearly what the coverage limits are |
| Competitor matching is noisy | Show the reason for each competitor and let the user remove wrong ones before ranking |
| Slow pipeline (dozens of calls) | Run calls in parallel, cache, and pre-cache the demo companies |
| Data too weak for investor ranking altogether | Pivot the same engine to a "fresh money" lead finder (companies that just raised = buyers with budget) |

**Questions for the Cala mentors**

- [ ] How are funding rounds modelled: dates, amounts, lead vs. participant?
- [ ] Can we pull an investor's full portfolio in one query?
- [ ] How much early-stage European and Nordic coverage is there?
- [ ] Is there a "similar company" or "competitor" link in the graph?
- [ ] Rate limits, and how best to batch queries?

## Data check results (Fri 13 Nov)

**The idea is supported. The conflict check is the strongest part; the "leads in your space" score needs `knowledge_search` to fill the gaps.**

| Test | Result | What it means for us |
| --- | --- | --- |
| Company lookup (`entity_search`) | Swappie, Kelluu and Inventure all found. Several entities share a name (5 "Inventure"s) | Always let the user confirm which one |
| Graph edges (`entity_introspection`) | Company: `INVESTED_IN` (incoming), `PARTICIPATES_IN_FUNDING_ROUND`, `OPERATES_IN_INDUSTRY`. Round: `announcement_date`, `transaction_value`, `round_label` | The graph walk from company to investors to portfolio works |
| Investor portfolio | Inventure: 22 `INVESTED_IN` edges, each sourced, but no dates on them | Conflict check works; we get **when** they invested from rounds, not from this edge |
| Lead flag | Exists as `is_lead: true` on the investor's round edge, but it's sparse (Inventure has only 2 round edges) | Score leads from structured data where it exists, and fill gaps with `knowledge_search` |
| Rounds query (`knowledge_query`) | 15 Finnish rounds since 2025, with amounts and dates. Lead often "—"; amounts are approximate strings | Parse the text; don't treat amounts as exact |
| Competitors (`knowledge_query`, industry + country + stage) | 15 Nordic defence startups, each with description, stage, total funding and often investors | Good input for the LLM competitor filter |
| Sourced answer (`knowledge_search`) | Leads per round (e.g. DTCP led Six Robotics, NATO Innovation Fund led Kelluu), each linked to source articles | Ideal for briefs and for filling lead gaps |
| Entity errors | "Inflection" (the VC) was matched to Inflection AI | Check investor matches by type and description |

**Demo case found:** Tesi backs both Kelluu (ISR airships, Series A) and NestAI (defence AI). That's a live portfolio overlap to show in investor mode. Maki.vc keeps leading defence pre-seeds (Aavuus, Metaktik), which makes it a good "who to pitch" example.

## Demo and judging fit

**Demo (about 3 minutes), using a real startup exhibiting at Slush:**

1. **The hook:** "Founders waste months pitching investors who were never going to say yes. Pitchlist tells you who to skip."
2. **Founder mode:** enter the startup → ranked list → a well-known fund flagged "backed your competitor Acme," with the source one click away.
3. **The flip:** switch to that fund's view, enter the same startup → "Conflict: competes with your portfolio company Acme." The same fact, found from both directions in the graph.
4. **The agent:** ask Claude Desktop "Should I pitch Fund X?" → it answers through the Pitchlist MCP server, with sources.
5. **The close:** "Cala is the data layer for agents. Pitchlist is the fundraising layer on top. Founders can use it at Slush tomorrow."

| Criterion (25% each) | How we score |
| --- | --- |
| Real need | A specific user (a founder raising at Slush), a costly problem (wasted pitches, decks leaked to rivals' backers) |
| Execution | One narrow pipeline, finished end to end, pre-cached so the demo is fast |
| Originality | Filters investors *out* (who not to pitch) instead of matching them in; the two-sided conflict check |
| Use of Cala | Graph walks across several hops, sources on every claim, and an MCP layer built on top of Cala |
