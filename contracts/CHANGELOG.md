# Contracts changelog

Every change to `contracts/` (schemas, API, fixtures format) is listed here, with the new
`CONTRACT_VERSION`. Fixture *data* written by Agent A (tasks A1, A2) is not a contract change.

## 1.1.1 + optional funding amount — 2026-11-14 (no version bump: additive, human decision)

Fixed now so C can build the inputs (C18) while B builds the logic (B21). Existing requests and
responses are unchanged; `CONTRACT_VERSION` stays 1.1.1.

- Requests: `POST /api/founder/analyze` gains `target_amount_eur?: number`;
  `POST /api/investor/check` gains `max_check_eur?: number`.
- Models: new `FundingFit {verdict: "fits" | "too_small" | "too_large" | "unknown", text,
  sources}`; `InvestorScore.funding_fit` and `InvestorCheck.funding_fit`, both `FundingFit | None
  = None` (null unless the request gave an amount). Rules in `contracts/api.md`.
- To follow: C: `frontend/lib/types.ts` (`FundingFit`, the two fields), the inputs and the fit on
  cards (C18; mock a `funding_fit` until B21). A: nothing. B: B21.

## 1.1.1 + optional Slush flag — 2026-11-14 (no version bump: additive, human decision)

Slush prep can take every Slush 2026 investor Cala knows of. Existing requests work unchanged;
`CONTRACT_VERSION` stays 1.1.1. No model changes.

- `POST /api/slush-prep` gains `all_slush_investors?: boolean` (default false); `investor_names`
  becomes optional when it is true. B asks Cala's sourced answer who attends Slush 2026, adds
  those investors (named as Cala writes them) to the pasted ones, dedupes, caps at 25.
- Live (14 Nov): Cala names 12 (Planet A Ventures, Revaia, Spintop Ventures, SSE Ventures, Tesi,
  Transition, Index Ventures, General Catalyst, Nefco, imec.Venture, Stephen Industries, EIC).
- To follow: C: a "Prep every Slush 2026 investor" option on the Slush prep screen (and the
  field in `frontend/lib/api.ts`). A: nothing. B: done (API, agent, tests).

## 1.1.1 — 2026-11-14

People who invest (angels) are investors too. No model, field or signature changes.

- Data layer: `company(id)` also works for a person who invests (returns a `Company` with
  `type: "Person"`); `investor_rounds(id)`, `portfolio(id)` and `people(id)` accept such an ID
  and return `[]` when nothing is known instead of raising.
- Why: angels are in competitors' rounds, so they are on Pitch and Skip; their card opened a
  brief / investor check that answered 404 (live: Tuomas Rasila on Kelluu's Pitch list).
- To follow in each area: A: both stores, `backend/tests/data/test_contracts.py` (asserts the
  version), `fixtures/models/index.json` (`contract_version`). C: `frontend/lib/types.ts`
  (`CONTRACT_VERSION`), angel cards. B: an angel case in the eval set.

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
