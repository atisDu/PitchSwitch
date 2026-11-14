# Notes — Agent B (Intelligence)

Requests for other areas and "not yet checked against live <service>" lines go here (CLAUDE.md rules 2 and 12).

## Contract review

- **B approves contracts 1.1.0** (commit 3559ed7, 13 Nov). All B review points are covered: competitor_ids, people()/company() for investor IDs, InvestorCheck.rounds scope, chat citations, [n] markers, score 0-100, co_investors() returning [].

## Pending live checks (rule 12)

- B2: checked live 13 Nov (nested contract model as schema, ~3 s).
- B3: checked live 13 Nov. First prompt ("use only the descriptions") kept 0/9 on every model: Cala descriptions are too thin (Sensofusion = "Finnish defense technology company"). Prompt now lets Gemini add what it reliably knows about named companies; IDs still restricted to candidates. Sensofusion <-> Stendr judged counter-drone rivals; Kelluu gets none (no airship/ISR rival among its 9 candidates -> A11/A13 candidates).
- Models (human: "no flash, make it smart"): `gemini-4-hydrogen` for FAST and SMART in .env; the judge uses tier `smart`. Gemini 4 names (argon/carbon/hydrogen) don't say which is top; hydrogen has the largest output limit. Swap in .env if the ranking is known. `gemini-2.5-pro` is closed to new users.

## B6 scoring decision (13 Nov, agreed with human)

- **Skip** = investors with a PORTFOLIO or BOARD conflict with a *direct* competitor (the 10–15 from B3).
- **Pitch pool** = investors in rounds of the *other* candidates (similar, not judged direct)
  ∪ `co_investors()` of the company's current investors (these are also warm paths); minus everyone on Skip.
- **Rank Pitch** by leads_in_space, rounds_in_space, recency of last lead, warm paths (weights dict at the top of `core/scoring.py`).
- **No special handling for big / state funds** (e.g. Tesi). One conflict = Skip, even if they back everyone. Don't add a softer label.
- **Current investors** of the company are left out of both Pitch and Skip (A's sample report does the same).

## Resolved: competitor backers without rounds

- B6 only finds Skip investors through `rounds(competitor)`. Since A7, `rounds()` also returns one
  undated `Round` holding a company's backers when Cala has no round details (e.g. Stendr), so
  Stendr's backers reach Skip. No contract change needed; the 1.2.0 `backers()` idea is dropped.
  `test_eval.py::test_counter_drone_conflict` guards it.
- Open, minor: `co_investors()` returns no sources, so warm-path `Reason`s have `sources=[]`.

## B9 real-data pass: requests for A (13 Nov)

- **Sensofusion has no candidates on the real store → empty founder report (demo company!).**
  `resolve("Sensofusion")` → `5c699806` "Sensofusion Oyj": `industries=[]`, description "Finnish
  company founded in 2016 and headquartered in Vantaa." `candidate_competitors()` makes one
  `knowledge_query` and returns 0, so the judge gets nothing and Pitch/Skip are empty.
  Ask: a fallback when industries are empty, e.g. take the industry from the other entry of the
  firm (`202e9283` "Sensofusion Oy") or a sibling, query by the description text / a
  `knowledge_search` ("counter-drone companies in the Nordics"), or the A13 vector neighbours.
  Stendr (counter-drone, Norway) must come back as a candidate for the demo.
- **Stendr's real candidates are 30 generic SaaS companies, no defence at all** (CRM, dental
  SaaS, VAT refunds...). Stendr has industries SOFTWARE_AND_SERVICES, AEROSPACE_AND_DEFENSE,
  HARDWARE_AND_EQUIPMENT; the queries look like they use only the first. Ask: query the most
  specific industry (AEROSPACE_AND_DEFENSE over SOFTWARE_AND_SERVICES), or one query per industry
  and rank by how many industries match. The judge kept 0 of the 30, correctly.
- Cost seen: Stendr cold = 213 live Cala calls, 21 min (rounds of all 30 candidates + every
  investor's `investor_rounds`). B now feeds only judge-approved "same space" candidates into
  scoring (fewer calls), but the cache must be warm before the demo either way.
- **Shared Atlas cache, now (human agrees).** `MONGODB_URI` is empty everywhere, so every clone
  pays the cold cost again (Stendr: 213 calls, 21 min). Ask: create the Atlas cluster, give all
  three clones the same `MONGODB_URI`, do the pending A10 live check, and add a one-off import of
  local `.cache/cala/` files into Atlas (B's clone has 295 responses: Kelluu, Stendr, Sensofusion
  and their candidates' rounds) so the work already paid for isn't lost.

## B9 done: live results (14 Nov, Atlas cache, gemini-4-hydrogen)

Eval set (`test_eval.py`) passes on the real store, 5/5 incl. the live judge.

- **Sensofusion** (54 s warm): direct = MyDefence, Stendr, Frankenburg (+1). Skip 9: Stendr's
  backers Rainfall, Skyfall, Startuplab; Frankenburg's Skaala, NATO, Nova Founders, SMARTCAP;
  Origin Robotics' Silicon Roundabout, Change Ventures. Pitch top: Maki.vc 73 (2 defence pre-seed
  leads), NATO Innovation Fund 49, ScaleWolf 45.
- **Stendr** (101 s, 11 live calls): direct = Sensofusion, MyDefence, Weibel Scientific. **Skip is
  empty** (Cala has no backers for those three). Pitch top: Maki.vc 49, NIF 49, ScaleWolf 45.
- **Kelluu**: direct = Aispeco, Granta Autonomy. Skip 6 (ScaleWolf, Superhero Capital, ...).
  Pitch top: Maki.vc.

### For C (demo script, `docs/demo-script.md`)

- Beat 3 ("Stendr -> Maki.vc on Skip, backed Aavuus") does **not** happen live: the judge doesn't
  rate Aavuus a direct Stendr rival, so Maki.vc is Stendr's top **Pitch**, and Stendr's Skip is empty.
- Live, the conflict moment is **Sensofusion**: Skip shows Stendr's backers (Rainfall Ventures,
  Skyfall, Startuplab) with the PORTFOLIO conflict and sources; flip on Rainfall Ventures.
- The judge is not fully deterministic (same input, different same-space set between runs), so
  rehearse on the deployed process; B may persist judgements (open question to the humans).

## B10 done: founder mode end to end on the real store (14 Nov)

- `/api/founder/analyze` on live data (Atlas cache): Kelluu 2.8-3.9 s, Sensofusion 1.9-2.1 s,
  Stendr 2.0 s once judged; the first call per company judges (~30 s) and stores it.
- **Judgements persist** in the graph store (Atlas collection `judgements`, id
  `CalaDataStore:<company_id>`): same competitors after a restart and on every machine. A company
  is judged again only when its candidate list changes. To force a fresh judgement, delete its doc.
- Stored now: Sensofusion -> MyDefence, Stendr (Skip = Stendr's backers Rainfall, Skyfall,
  Startuplab); Stendr -> Sensofusion, MyDefence (Skip empty); Kelluu -> Aispeco, Granta (Skip 6).
- **For C (C8):** run the backend with `USE_FAKE_STORE=false` and point `API_URL` at it.

## B11 done: briefs (14 Nov)

- `/api/brief` runs on core: sourced facts from the store + Cala's sourced answer -> Gemini writes
  sentences citing fact numbers -> code renders `[n]` markers and drops any sentence that cites
  nothing valid or states a number its facts don't hold. Max 3 sources per fact (best rank first),
  2 facts per sentence. Uses the stored judgement, so "conflict" matches the founder report.
- Live (Sensofusion): Maki.vc -> "Pitch, no conflict" (26 citations); Rainfall Ventures -> "Skip,
  backs Stendr" (16 citations). ~20 s per brief once Cala's answer is cached (first: ~60 s).
- For C (C10): `Brief.markdown` uses `## ` headings and `[n]` markers after sentences.

## B12–B13 done: agent tools, agent loop, slush prep (14 Nov)

- `agent/tools.py`: the §5.4 tools (+ `sourced_answer`) as "IDs in, contract models out"
  functions, shared by the agent and the MCP server. The stored judgement now lives in
  `core/competitors.stored_judgement`, so routes, agent and MCP agree on direct competitors.
- `agent/gemini_agent.py`: Gemini function-calling loop (forced tool calls, max 12 per run, then
  only the closing tool). Tool results reach Gemini as numbered facts; IDs it did not get from a
  tool are refused.
- **Slush prep is live** (`/api/slush-prep` + `/api/jobs/{id}/stream`): one agent run per pasted
  name (look up → pick the investor → brief, or give up with a reason), 3 names at a time.
  Live on Sensofusion: Maki.vc → pitch (29 citations), Rainfall Ventures → skip (backs Stendr),
  Inventure → pitch, "Nonexistent Capital" → error. 89 s for the four (briefs ~20-60 s each).
- **For C (C11):**
  - Events of different investors **interleave** (they run in parallel); group by `investor_name`.
  - The first event is a `step` without `investor_name` ("Finding <company>'s direct competitors").
  - Per investor: `step` (looking up) → `step` with `investor` (found) → `brief`; or `step` → `error`.
  - The job starts at the POST; opening the stream again replays it from the start (safe with
    React's double effect / reconnects). Max 25 names per job (422 above); blank and repeated
    names are dropped.
  - Briefs are not cached: the same investor costs ~20 s again on the next job.

## B14 done: chat (14 Nov)

- `/api/chat` runs the same agent loop, scoped to `company_id` / `investor_id` when given.
  `step` events while tools run, then the whole answer as `text` events (one per sentence, sent
  together at the end: the answer is checked before it is shown), then `done` with `citations`.
- Every sentence must cite a fact a tool returned; a sentence that cites none, or states a number
  its facts don't hold, is dropped. Sentences resting only on computed facts (fit score, rank,
  "no conflict found") carry no `[n]` marker.
- Live (Sensofusion): "Should I pitch Rainfall Ventures?" → no, backs Stendr [1][2][3], 17 s;
  "top 3 investors to pitch and why?" → Maki.vc, NIF, ScaleWolf with 14 citations, 15 s;
  "Who led Kelluu's Series A?" → NIF, €15M, 2026-04-14, 6 s. Off-topic → a fixed "no sourced
  facts" line.
- For C (C12): no chat history in the contract, so each message stands alone; send
  `company_id` / `investor_id` of the page so "my company" / "this investor" resolve.

## B15 done: MCP server (14 Nov)

- `backend/mcp_server/server.py`: the seven §5.4 tools, the same functions the Gemini agent
  calls (`agent/tools.py`). `resolve_company` takes an optional `kind` ("company" default,
  "investor") so a client can also turn "Fund X" into an ID; `rank_investors` takes an optional
  `limit` (default 10) for the Pitch list.
- Checked with the SDK's own client over stdio on live data (Sensofusion): all seven tools answer;
  Rainfall Ventures → PORTFOLIO conflict via Stendr; unknown IDs come back as readable tool errors.
  Result sizes: check_conflict 1 kB, investor_brief 4 kB (~30 s), rank_investors 67 kB,
  investor_profile up to 85 kB (Tesi).
- **Not yet checked in Claude Desktop** (needs a human at the app; C13). Config for it, with the
  repo's venv (the editable install makes the module importable from any folder; `.env` is read
  from the repo root):

  ```json
  {"mcpServers": {"pitchlist": {
    "command": "<repo>/.venv/bin/python",
    "args": ["-m", "mcp_server.server"],
    "env": {"USE_FAKE_STORE": "false"}
  }}}
  ```

- **For A (A17, Docker):** the MCP server is its own process:
  `python -m mcp_server.server http` serves streamable HTTP on `$MCP_HOST:$MCP_PORT/mcp`
  (default `0.0.0.0:8001`); no arguments = stdio. It shares `.env` and the Atlas cache with the API.
  If you want `MCP_HOST` / `MCP_PORT` in `.env.example`, they are yours to add.
