# Pitchlist contracts — API, MCP tools, fixtures

Contract version: **1.1.1** (`CONTRACT_VERSION` in `contracts/schemas.py`).
**Frozen after task T2.** Changes need all three humans to agree; then bump `CONTRACT_VERSION`,
note it in `contracts/CHANGELOG.md` and update `CLAUDE.md` §5 in the same commit.

All model names below (`EntityRef`, `FounderReport`, ...) are the Pydantic models in
`contracts/schemas.py`. JSON field names are the model field names, unchanged.

## REST API — B implements, C consumes

| Method | Path | Body | Returns |
| --- | --- | --- | --- |
| POST | `/api/resolve` | `{name, kind}` | `EntityRef[]` |
| POST | `/api/founder/analyze` | `{company_id, competitor_ids?: string[], target_amount_eur?: number}` | `FounderReport` |
| POST | `/api/investor/check` | `{investor_id, company_id, max_check_eur?: number}` | `InvestorCheck` |
| POST | `/api/brief` | `{investor_id, company_id}` | `Brief` |
| POST | `/api/slush-prep` | `{company_id, investor_names?: string[], all_slush_investors?: boolean}` | `{job_id}` |
| GET | `/api/jobs/{id}/stream` | — | SSE stream of `AgentEvent` |
| POST | `/api/chat` | `{company_id?, investor_id?, message}` | SSE stream of `AgentEvent` |
| GET | `/api/health` | — | `{ok: true, contract_version}` |

- `kind` is `"company"` or `"investor"`.
- Errors: HTTP 4xx/5xx with `{error: string}`.
- CORS open for the frontend origin.

### Rules the models can't express

- **Removing competitors (`competitor_ids`).** Without it, B finds the competitors itself. With it,
  B skips that step and ranks against exactly those company IDs. The frontend sends the IDs still
  shown after the user removed some (taken from the previous `FounderReport.competitors`).
- **Funding amount (optional, B21).** Euros, a positive number; leave the field out when the user
  gave none (then every `funding_fit` is `null`, as today).
  - `target_amount_eur` (founder mode): how much the founder wants to raise. Each `InvestorScore`
    gets a `funding_fit` comparing it with the sizes of the rounds that investor has joined:
    `fits`, `too_small` (smaller than the rounds they join), `too_large` (bigger), or `unknown`
    (Cala has no amounts for their rounds). Whether it also moves the score shows in the score
    breakdown (first reason).
  - `max_check_eur` (investor mode): the most the investor will put in. `InvestorCheck.funding_fit`
    compares it with the company's round sizes: `fits`, `too_small` (the company raises far less
    than this), `too_large` (its rounds are far bigger, so this would be a small share), or
    `unknown`.
  - Amounts in Cala are whole-round sizes, never one investor's share; `text` says what was
    compared, and `sources` are the rounds used. Out-of-range input (0, negative): 422.
- **Score.** `InvestorScore.score` is 0–100, higher = better fit. `pitch` and `skip` are each sorted
  by score, highest first. An investor with one or more `conflicts` is in `skip`, never in `pitch`.
- **Lead data.** `InvestorScore.lead_data` says how far `leads_in_space` can be trusted: `known`
  (every round in the space says who led), `partial` (some do), `unknown` (none do — show
  `rounds_in_space` instead and say so in the UI).
- **`InvestorCheck.rounds`** holds the rounds of `company` and of every competitor. Group them by
  `Round.company_id` to show who backed each rival.
- **Citations in briefs.** `Brief.markdown` cites with `[n]` markers; `n` is a 1-based index into
  `Brief.citations`.

### Streams (`/api/jobs/{id}/stream`, `/api/chat`)

- Wire format: one `data: <AgentEvent JSON>\n\n` per event. No named events (`event:` lines), no
  ids. The stream closes after the `done` event. `/api/chat` is a POST, so the frontend reads it
  with a streaming `fetch`, not `EventSource`.
- Event types:
  - `step` — a progress line in `message` (e.g. a tool call).
  - `text` — a chunk of the answer in `message`; append chunks in order.
  - `brief` — one finished brief in `brief`.
  - `error` — what failed, in `message`. The stream continues unless `done` follows.
  - `done` — end of the stream.
- **Slush prep:** every event about one pasted investor carries `investor_name` (the name exactly
  as pasted) and, once resolved, `investor`. A name that doesn't resolve, or matches several
  entities that can't be told apart, gets an `error` event with that `investor_name`.
  `all_slush_investors: true` (default false) adds every investor that Cala's sourced answer says
  attends Slush 2026 (a few dozen at most: what Cala's sources name, not the whole event); their
  events carry the name as Cala writes it in `investor_name`. Pasted names stay; duplicates are
  dropped; at most 25 investors in all. `investor_names` may then be empty (without the flag it
  needs at least one name: else 422). If Cala's list is unavailable, one `error` event without
  `investor_name` says so and the pasted names still run.
- **Chat:** the answer arrives as `text` events. Its sources arrive in `citations` on the `done`
  event; `[n]` in the text is a 1-based index into that list.

## Data layer interface — A implements, B consumes

`DataStore` (a `Protocol` in `contracts/schemas.py`):

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

`backend/data/__init__.py` exposes `get_store() -> DataStore`, returning `FakeDataStore` when
`USE_FAKE_STORE=true`, else the real store. B only ever calls `get_store()`.

- `company(id)` works for any organisation ID, including an investor, and for a **person who
  invests** (an angel): it then returns a `Company` with `type: "Person"`.
- `investor_rounds(id)`, `portfolio(id)` and `people(id)` accept such a person's ID as well and
  return that person's rounds and companies, or `[]` when nothing is known. They never raise
  for a person. Angels appear on Pitch and Skip like any other investor, so the brief and the
  investor check must work for them.
- `people(id)` also accepts an investor ID and returns that investor's own people (then
  `PersonLink.company_id` is the investor ID). BOARD conflicts need this: a competitor's `BOARD`
  person who is also one of the investor's people.
- `co_investors(id)` returns `[]` when nothing is known yet (the precomputed graph arrives with the
  batch job, after the real store). It never raises for that.

## MCP tools — B implements (thin wrappers over core)

`resolve_company`, `find_competitors`, `get_rounds`, `investor_profile`, `check_conflict`,
`rank_investors`, `investor_brief`.

Inputs are entity IDs (plus `name` for `resolve_company`); outputs are the contract models as JSON.

## Fixtures — `contracts/fixtures/`

- `README.md` — the demo cases (task T3).
- `raw/` — raw Cala responses (A records them; never hand-edited).
- `models/` — contract-model JSON built from raw. `FakeDataStore` reads it; C's mock API serves it.
  A produces all of these in task A2:

| File | Content | Used by |
| --- | --- | --- |
| `index.json` | The demo cases: names, IDs and which files exist | everyone |
| `resolve_<kind>_<slug>.json` | `EntityRef[]` (`slug` = name lowercased, non-alphanumerics → `-`) | fake store, mock `/api/resolve` |
| `company_<id>.json` | `Company` | fake store |
| `rounds_<company_id>.json` | `Round[]` | fake store |
| `investor_rounds_<investor_id>.json` | `Round[]` | fake store |
| `portfolio_<investor_id>.json` | `PortfolioLink[]` | fake store |
| `people_<id>.json` | `PersonLink[]` | fake store |
| `candidates_<company_id>.json` | `Company[]` | fake store |
| `co_investors_<investor_id>.json` | `[EntityRef, count][]` | fake store |
| `sourced_answer_<slug>.json` | `{markdown, reasons: Reason[]}` | fake store |
| `founder_report_<company_id>.json` | `FounderReport` | mock `/api/founder/analyze` |
| `investor_check_<investor_id>_<company_id>.json` | `InvestorCheck` | mock `/api/investor/check` |
| `brief_<investor_id>_<company_id>.json` | `Brief` | mock `/api/brief` |
| `agent_events_slush_prep.json` | `AgentEvent[]` in stream order | mock `/api/jobs/{id}/stream` |
| `agent_events_chat.json` | `AgentEvent[]` in stream order | mock `/api/chat` |

  The last five are **samples**: real Cala facts in the right shape, but ranked and worded by a
  simple placeholder, not by B's scoring. They exist so the frontend can be built; B's API replaces
  them at CP3.
