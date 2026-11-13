# Contracts changelog

Every change to `contracts/` (schemas, API, fixtures format) is listed here, with the new
`CONTRACT_VERSION`. Fixture *data* written by Agent A (tasks A1, A2) is not a contract change.

## 1.0.0 — 2026-11-13

Initial contracts, copied from `CLAUDE.md` §5 (task T2):

- `schemas.py`: models (`Source`, `EntityRef`, `Company`, `RoundInvestor`, `Round`, `PortfolioLink`,
  `PersonLink`, `Competitor`, `Conflict`, `Reason`, `InvestorScore`, `FounderReport`,
  `InvestorCheck`, `Brief`, `AgentEvent`) and the `DataStore` protocol.
- `api.md`: REST API, MCP tools, fixtures layout.
