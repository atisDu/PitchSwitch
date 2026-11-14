# Notes — Agent C (Product)

Requests for other areas and "not yet checked against live <service>" lines go here (CLAUDE.md rules 2 and 12).

## Contract 1.2.0 proposal (`DataStore.backers`, from B) — C's review, 13 Nov

> **Superseded:** the proposal was dropped. Since A7, `rounds()` returns one undated `Round` holding a
> company's backers when Cala has no round details, so no contract change is needed (see `notes/B.md`).
> Contract stays 1.1.0. Kept below for the record.

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

## C8: frontend on the real API (14 Nov)

Checked through the frontend's `/api` proxy against B's API (`USE_FAKE_STORE=false`, shared Atlas):
resolve, founder/analyze for Kelluu (6.8 s), Sensofusion (3.1 s), Stendr (3.3 s), and investor/check
for Rainfall × Sensofusion (0.1 s, PORTFOLIO conflict via Stendr), Tesi × NestAI (77 s cold, no
conflict live), Maki.vc × Stendr (0.05 s). All 200, shapes as the screens expect.

Frontend changes from this: Pitch list shows the top 10 with "Show all N" (live reports have 30–45);
`/api` proxy timeout raised to 30 min earlier (the 77 s check would have failed at 30 s). Demo script
moved to the live Sensofusion → Rainfall Ventures conflict.

For B / A (minor, not blocking):

- **Two names for one firm in the same session.** `resolve("Sensofusion")` returns `202e9283`
  "Sensofusion Oy", but Stendr's report lists the competitor as "Sensofusion **Oyj**" (the alias
  entry). Showing the main entry's name everywhere would avoid confusing the audience.
- **Warm paths are empty in every live report** (co_investors not filled yet; A15 done, so maybe
  the graph isn't loaded into the shared Atlas?). The UI hides the section when empty.
- **Cold investor checks take over a minute** (Tesi × NestAI: 77 s). Pre-cache every check the demo
  might flip to (A18). The demo's three (Rainfall Ventures, Startuplab, Skyfall × Sensofusion)
  are already cached (< 0.1 s); Tesi × NestAI is now cached too.
- brief, slush-prep and chat still serve A's samples (B11, B13, B14 open); C10–C12 build on those.

## For A: deployed MCP endpoint is down (14 Nov)

`POST https://95-133-252-219.sslip.io/mcp` answers **502** (Caddy can't reach the `mcp` service).
B's note says the MCP server refuses to start without `MCP_TOKEN` (16+ chars) in the server's
`.env`, and `deploy/ship.sh` needs to write it. Expected after the fix: 401 without the token,
200 with `Authorization: Bearer <token>`. The demo uses local stdio (`docs/mcp-demo.md`), so this
only blocks the remote option.
