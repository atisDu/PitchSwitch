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

> **Resolved:** A's `ship.sh` sends `MCP_TOKEN` (ff8819a); `/mcp` answers 401 without the token and
> 200 with it, checked by A, B and C. `docs/mcp-demo.md` updated.

`POST https://95-133-252-219.sslip.io/mcp` answers **502** (Caddy can't reach the `mcp` service).
B's note says the MCP server refuses to start without `MCP_TOKEN` (16+ chars) in the server's
`.env`, and `deploy/ship.sh` needs to write it. Expected after the fix: 401 without the token,
200 with `Authorization: Bearer <token>`. The demo uses local stdio (`docs/mcp-demo.md`), so this
only blocks the remote option.

## Contract 1.1.1 (people who invest are investors): C approves (14 Nov)

**C's human approves** the branch `contract/1.1.1-people-as-investors` (9007f73): wording only,
`CONTRACT_VERSION` 1.1.1, no model or signature changes. With B's yes, A's human is the last vote
(rule 4); A merges it together with the store change.

C's follow-up once it is on main: `CONTRACT_VERSION` in `frontend/lib/types.ts`, and
`ANGEL_PAGES_READY = true` in `frontend/components/InvestorCard.tsx` (angel cards get their brief
and flip links back). The mock test now reads the version from `fixtures/models/index.json`, so
A's rebuild of the index won't turn it red.

## C9 (founder testing) dropped (14 Nov)

C's human decided not to run sessions with real founders. `docs/user-testing.md` stays as an unused
guide (marked "Not run"); the demo script no longer ends with a founder quote. C9 stays unticked in
TODO.md because it wasn't done; the humans can strike or tick it.

## Decision: agents use our MCP server only (14 Nov)

C's human: "we provide our own MCP, not use Cala's one for agents." Cala's MCP server is out of the
demo and the docs (`docs/mcp-demo.md` step 3 now says so). PitchSwitch's MCP tools already sit on
Cala and return its sources. `CLAUDE.md` §3 ("+ Cala MCP for the demo"), `TODO.md` C13 and
`OVERVIEW.md` still mention Cala's MCP; those are the humans' files.

C13 is ticked on that basis: the PitchSwitch MCP server is set up and was tested in Claude Desktop
by a person (`notes/B.md`, "MCP server checked in Claude Desktop"); `docs/mcp-demo.md` has the steps.

## For A / B: people can't be found by name (14 Nov, from testing Slush prep)

`/api/resolve` with `kind: "investor"` never returns a `Person`: "Tuomas Rasila" (an angel the store
accepts since 1.1.1, #10 on Sensofusion's Pitch) gives only companies (Tuomas Grönman Oy, a golf
company, RASILA LTD). So an angel pasted into Slush prep always ends in "Couldn't brief", and the
frontend's new "Did you mean" can't offer them either. Ask: let investor resolve also search people
who invest (Cala entity search filtered to Person, kept only if they have rounds or `INVESTED_IN`).

Also seen: Slush prep's agent sometimes fails "Lifeline" ("only non-investor companies matched")
and sometimes finds Lifeline Ventures. The frontend now recovers either way: a failed card offers
investor-like matches (searching "<name> Ventures" too) and writes the brief by ID via `/api/brief`.

## For B: from C's browser testing (14 Nov)

- **A malformed ID gives 502 with Cala's raw error** (`/api/founder/analyze`, `/investor/check`,
  `/brief` with `company_id: "not-a-real-id"` → `data source unavailable: Cala POST
  /entities/not-a-real-id failed (422): {…}`). It should be a 404 `{error: "No company or investor
  with that ID."}`. The frontend now shows "That link doesn't point to a company or investor in
  Cala" either way, with the raw text under "Technical details".
- **Chat can take ~100 s** ("Who led NestAI's last round?" on Tesi × NestAI: two `sourced_answer`
  calls). It answered correctly (Tesi and Nokia co-led the €100M round, 4 sources). The panel now
  shows elapsed seconds; anything that shortens the second Cala search helps.
