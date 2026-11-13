# Pitchlist contracts — API, MCP tools, fixtures

Contract version: **1.0.0** (`CONTRACT_VERSION` in `contracts/schemas.py`).
**Frozen after task T2.** Changes need all three humans to agree; then bump `CONTRACT_VERSION`,
note it in `contracts/CHANGELOG.md` and update `CLAUDE.md` §5 in the same commit.

All model names below (`EntityRef`, `FounderReport`, ...) are the Pydantic models in
`contracts/schemas.py`. JSON field names are the model field names, unchanged.

## REST API — B implements, C consumes

| Method | Path | Body | Returns |
| --- | --- | --- | --- |
| POST | `/api/resolve` | `{name, kind}` | `EntityRef[]` |
| POST | `/api/founder/analyze` | `{company_id}` | `FounderReport` |
| POST | `/api/investor/check` | `{investor_id, company_id}` | `InvestorCheck` |
| POST | `/api/brief` | `{investor_id, company_id}` | `Brief` |
| POST | `/api/slush-prep` | `{company_id, investor_names: string[]}` | `{job_id}` |
| GET | `/api/jobs/{id}/stream` | — | SSE stream of `AgentEvent` |
| POST | `/api/chat` | `{company_id?, investor_id?, message}` | SSE stream of `AgentEvent` (type `step` = text chunks) |
| GET | `/api/health` | — | `{ok: true, contract_version}` |

- `kind` is `"company"` or `"investor"`.
- Errors: HTTP 4xx/5xx with `{error: string}`.
- CORS open for the frontend origin.

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

## MCP tools — B implements (thin wrappers over core)

`resolve_company`, `find_competitors`, `get_rounds`, `investor_profile`, `check_conflict`,
`rank_investors`, `investor_brief`.

Inputs are entity IDs (plus `name` for `resolve_company`); outputs are the contract models as JSON.

## Fixtures — `contracts/fixtures/`

- `raw/` — raw Cala responses (A records them; never hand-edited).
- `models/` — contract-model JSON built from raw (`company_<id>.json`, `rounds_<company_id>.json`,
  `portfolio_<investor_id>.json`, `founder_report_<company_id>.json`, ...).
- `FakeDataStore` reads `models/`. C's mock API serves `models/founder_report_*.json` etc.
