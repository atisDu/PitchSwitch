# Notes — Agent C (Product)

Requests for other areas and "not yet checked against live <service>" lines go here (CLAUDE.md rules 2 and 12).

## Contract 1.2.0 proposal (`DataStore.backers`, from B) — C's review, 13 Nov

**C approves.** REST routes and response models don't change, so the frontend and mock need no
code changes; once A rebuilds the `founder_report_*` samples, Sensofusion's Skip list should show
Stendr's backers (Rainfall, Skyfall, Startuplab).

**One suggestion — return the investor, not just its ID.** With `-> list[PortfolioLink]`, each row
is `{investor_id, company: EntityRef, sources}`: `company` is always X itself and the backer arrives
as a bare ID. A Skip row needs `InvestorScore.investor: EntityRef`, so B would need one extra
`company(id)` per backer (Cala: ~10 calls/min, 20–80 s each). Either:

- **Preferred:** a new model `Backer { investor: EntityRef, company_id: str, sources: list[Source] = [] }`
  and `backers(company_id) -> list[Backer]` (same incoming `INVESTED_IN` edge, sources kept), or
- keep `PortfolioLink`, and A guarantees `company(id)` resolves every backer ID in fake and real stores.

**Questions for B:**

- `INVESTED_IN` has no dates, so conflicts found this way carry undated sources (badge shows rank
  only) and can't feed `last_lead_date` / `deals_last_12m`. Fine for the UI; just confirming.
- An investor found only via `backers()` (no rounds): still scored, with `lead_data: "unknown"`?
  Skip cards show the conflict first either way.

**C's follow-up when 1.2.0 lands:** bump `CONTRACT_VERSION` in `frontend/lib/types.ts`; mirror any new
model there (if `Backer` is added); make `frontend/mock/handlers.test.ts` read the version from
`index.json` instead of hard-coding it. C does not edit `contracts/`.
