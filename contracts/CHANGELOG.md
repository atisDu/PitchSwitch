# Contracts changelog

Every change to `contracts/` (schemas, API, fixtures format) is listed here, with the new
`CONTRACT_VERSION`. Fixture *data* written by Agent A (tasks A1, A2) is not a contract change.

## 1.1.0 — 2026-11-13

Review by B and C before the freeze (T2 not yet ticked). Changes to `schemas.py`:

- `InvestorScore.conflict: Conflict | None` → **`conflicts: list[Conflict] = []`** (an investor can
  conflict with several competitors). *Breaking rename.*
- `InvestorScore` gains `lead_data: "known" | "partial" | "unknown"` (default `"unknown"`) and
  `deals_last_12m: int | None`.
- `AgentEvent.type` gains **`"text"`** (answer chunks); `"step"` is now progress only.
- `AgentEvent` gains `investor_name`, `investor` (slush prep) and `citations` (chat).
- Comments only: `score` is 0–100; `pitch`/`skip` sorted by score, highest first;
  `InvestorCheck.rounds` covers the company and every competitor; `Brief.markdown` cites with
  `[n]`; `company()` and `people()` accept investor IDs; `co_investors()` may return `[]`.

Changes to `api.md`:

- `/api/founder/analyze` takes an optional `competitor_ids: string[]` (rank against exactly those).
- SSE wire format written down; slush-prep and chat event rules.
- Fixtures: full list of `models/` files A produces in A2, including samples for every mock route.

Considered and left out (can be added later without breaking anything): `country` on `EntityRef`,
the company's own investors on `FounderReport`, an error `code`.

## 1.0.0 — 2026-11-13

Initial contracts, copied from `CLAUDE.md` §5 (task T2):

- `schemas.py`: models (`Source`, `EntityRef`, `Company`, `RoundInvestor`, `Round`, `PortfolioLink`,
  `PersonLink`, `Competitor`, `Conflict`, `Reason`, `InvestorScore`, `FounderReport`,
  `InvestorCheck`, `Brief`, `AgentEvent`) and the `DataStore` protocol.
- `api.md`: REST API, MCP tools, fixtures layout.
