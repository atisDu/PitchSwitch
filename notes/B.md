# Notes — Agent B (Intelligence)

Requests for other areas and "not yet checked against live <service>" lines go here (CLAUDE.md rules 2 and 12).

## Name: the company is PitchSwitch (human, 14 Nov)

- **The company's name is PitchSwitch.** "Pitchlist" in the code, the docs, `CLAUDE.md`,
  `OVERVIEW.md` and the notes below is the earlier working name for the same thing, not a second
  product.
- Renamed in B's area (14 Nov): the API title, the chat prompt, and the MCP server: it now
  reports itself as `pitchswitch` (title "PitchSwitch"). **Not renamed:** `MONGODB_DB=pitchlist`
  (A's; the shared cache lives there) and the package name in `backend/pyproject.toml`.
- **For C (`docs/mcp-demo.md`):** use `"pitchswitch"` as the key in the client config (line 28)
  and in the troubleshooting row (line 91), and "Using only PitchSwitch" in the demo question.
  The key is what Claude Desktop shows as the server's name. An old config with the key
  `"pitchlist"` still works; it only shows the old name.
- **For C:** README, `docs/` (demo script, MCP demo, pitch notes) and the UI say "Pitchlist".
- **For the humans:** `CLAUDE.md` and `OVERVIEW.md` say "Pitchlist"; say if the code-level names
  (MCP server name, API title) should change too. Renaming the MCP server means updating every
  client config that has it.

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
  {"mcpServers": {"pitchswitch": {
    "command": "<repo>/.venv/bin/python",
    "args": ["-m", "mcp_server.server"],
    "env": {"USE_FAKE_STORE": "false"}
  }}}
  ```

- **For A (A17, Docker):** the MCP server is its own process:
  `python -m mcp_server.server http` serves streamable HTTP on `$MCP_HOST:$MCP_PORT/mcp`
  (default `0.0.0.0:8001`); no arguments = stdio. It shares `.env` and the Atlas cache with the API.
  If you want `MCP_HOST` / `MCP_PORT` in `.env.example`, they are yours to add.

## B16 done: hardening (14 Nov)

- **One definition of "conflict".** Taking part in a direct competitor's round now counts inside
  `core/conflict.check_conflict` (before, only the founder report knew it), so the report, the
  investor check, briefs, chat and the MCP tools cannot disagree. Live: no demo result changed.
- **Briefs are kept** in the graph store (Atlas collection `briefs`, id
  `<store>:<investor_id>:<company_id>`): the same facts give the same brief with no Gemini call.
  Live: Rainfall × Sensofusion 41 s the first time, 0.4 s after; a slush-prep job reuses them.
  A brief is written again only when its facts change. To force a new one, delete its doc.
- **Timeouts and errors.** Gemini calls time out after 90 s (retried like other transient
  failures). Any unforeseen failure is `500 {error: "internal error (<type>)"}`; Gemini trouble is
  `503 {error: "Gemini is unavailable: ..."}`. A brief whose every sentence fails the citation
  check is a 503, not an empty page.
- **Weights unchanged.** Eval set 5/5 on the real store; live top-3 for Sensofusion and Stendr:
  Maki.vc 73, NATO Innovation Fund 49, ScaleWolf 45. Warm paths now show for Kelluu (17 pitch
  investors), none for Sensofusion / Stendr (no co-investor data for their backers).
- Checked over HTTP on the real store: founder/analyze 3-6 s for the three demo companies,
  investor/check 0.3 s, chat 11 s, slush prep (3 names) 73 s, stream replay instant.

### Requests / open

- **For A:** `company("nope")` (an ID that is not a UUID) raises `Upstream` with Cala's raw 422
  JSON, so the API answers 502 with that text. `NotFound` would give a clean 404.
- **For A (A18 pre-cache):** warm the demo's briefs too: one `POST /api/brief` per investor the
  demo opens (or one slush-prep job with their names) stores them; after that they need neither
  Cala nor Gemini.
- Not yet checked in Claude Desktop: the MCP server (C13; config in the B15 note above).

## MCP server verified (14 Nov)

- **Protocol, with the SDK's client, real store:** 14 checks each over stdio (started from another
  folder, like a desktop client) and streamable HTTP: all pass. All seven tools, both error cases.
- **As deployed:** bound to `0.0.0.0` it accepts requests under the site's hostname (Caddy's
  `/mcp`). Bound to `127.0.0.1` it answers a foreign Host with 421, so keep the default behind
  the proxy. **No auth:** anyone with the URL can call the tools (and spend Cala / Gemini credits).
- **A real LLM client (Claude Code, headless, only this server):** "Should I pitch Rainfall
  Ventures? Name two to pitch instead" -> resolve x2, investor_brief, rank_investors,
  check_conflict; answer in 27 s: skip Rainfall (backs Stendr), pitch Maki.vc and NATO Innovation
  Fund, with source URLs.
- Found by that run: the brief says Rainfall *led* Stendr's round (from Cala's knowledge search),
  while the round data has no lead for it (`lead_data: unknown`). Both are what Cala holds. The
  server instructions now say that "unknown" is not "did not lead"; asked again, the client
  reports it as unconfirmed instead of as a contradiction.
- Cala's own sources also disagree on that round's label ("Seed" in an aggregator's claim,
  "Pre-Seed" in Stendr's announcement); the brief repeats each with its source.
- **Still open: the Claude Desktop app itself** (C13). It is installed on B's machine with no MCP
  servers configured; the config block is in the B15 note. Needs a human to restart the app and ask.

## MCP server checked in Claude Desktop (14 Nov, human at the app)

- Works: the server starts, lists its tools and answers "should Sensofusion pitch Rainfall
  Ventures?" with "skip, backs Stendr". The B15 "not yet checked in Claude Desktop" line is closed.
- **Config trap:** `mcpServers` must be a top-level key of `claude_desktop_config.json`. Pasted at
  the end of the file it lands inside `preferences`, the app ignores it without an error and
  Claude answers from web search instead. Then quit the app fully and start it again.
- **For C (C13 demo):** Claude Desktop mixed its own web search into the answer (it named a
  co-lead our data does not have) and read the round's "~$5M" as Rainfall's share. The server
  instructions now say amounts are round sizes and outside facts must be labelled; for the demo,
  also turn web search off in the chat or start the question with "Using only Pitchlist".

## MCP: slow calls no longer time out in the client (14 Nov)

- Seen in Claude Desktop: "should ICEYE pitch Y Combinator?" -> `investor_brief` on a company
  nobody had asked about took over 80 s, the app gave up ("Device did not respond within 80s"),
  and only a retry worked.
- Now every MCP tool answers within 50 s. If the work is not done it replies "Still working ...
  call again with the same arguments" while the work goes on; the next identical call joins that
  same work (it never starts twice) or finds it finished. Live: an 80 s cold brief ran once and
  then came back in 0.2 s.
- **For C (C13, `docs/mcp-demo.md`):** a first question about a new company can still take a
  minute or two in total; for the demo, ask each demo question once beforehand so it is cached.

## MCP over HTTP needs a token (14 Nov, human: "it should need auth and easy setup")

- `python -m mcp_server.server http` now **refuses to start without `MCP_TOKEN`** (16+ characters)
  and answers 401 to any request without it. Accepted as `Authorization: Bearer <token>` or as
  `?key=<token>` in the URL (for clients that only take a URL). stdio is unchanged (no token).
- Checked live on a local port: no token 401, wrong token 401, token in URL 200, in header 200.
  With a real client (Claude Code over HTTP, real store): token in the header -> connected, 7
  tools, correct answer in 10 s; token in the URL -> the same in 8 s; no token -> the server shows
  as failed with "HTTP 401, missing or wrong token" and the client says how to fix it.
  **Not yet checked:** Claude's custom-connector screen and Cursor (need a human at the app),
  and the whole thing through Caddy on the deployed server (not deployed yet).
- **Easy setup:** `python -m mcp_server.server setup https://<site>` prints the ready-to-paste
  line for Claude (custom connector URL), Claude Code and Cursor.
- **For A (blocking the `mcp` container):** add `MCP_TOKEN` to `.env.example` and to the server's
  `.env` (`deploy/ship.sh` writes it): without it the `mcp` service exits at start and `/mcp`
  answers 502. Make one with
  `python -c "import secrets; print(secrets.token_urlsafe(24))"`. With `?key=` the token is in the
  URL, so it will show in Caddy's access log if that is on.
- **For C (`docs/mcp-demo.md`):** the remote option now needs the token; paste the output of the
  `setup` command.

## Demo warmed; what moved (14 Nov)

- Warmed on the real store (shared Atlas): the founder reports of Sensofusion, Stendr and Kelluu
  and the brief of every investor on their screens (top 10 Pitch + all of Skip): **39 briefs
  stored**, each now back in about a second (cold: 50-85 s). Eval set 5/5 live. Second pass:
  1974 Cala calls, 44 of them live, no rate-limit answer.
- **Sensofusion (the demo path) is unchanged:** MyDefence + Stendr; Pitch top Maki.vc, NATO
  Innovation Fund, ScaleWolf; Skip Skyfall, Startuplab, Rainfall.
- **Stendr was judged again** (its candidate list changed; 239 s): Weibel Scientific is now a
  third direct competitor, Skip is still empty, Pitch #3 is now Lifeline Ventures.
- **Kelluu's order moved:** BSV Ventures is now #2 (was #4). Most likely refreshed Cala data:
  cache entries expire after 24 h and 44 calls went to Cala live.
- So results drift while the cache keeps refreshing. For the demo, run with A's cache-only mode on
  (`deploy/cache-only.sh`) from the last rehearsal onwards, and rehearse on that.
- A person (angel) on a list opens a brief that fails: see "Angels stay on the lists" below.

## Angels stay on the lists (human, 14 Nov): requests for A and C

Decision: **people who invest (angels) stay on Pitch and Skip.** B's stopgap that removed them is
dropped. What is broken today: an angel's card opens a brief / investor check that answers 404.
Seen live on Kelluu: Tuomas Rasila (`c75cbef9-0ab0-5552-84f8-fc59bc63ea93`, type `Person`), #6 on
Pitch; `company(id)` answers "is not a company or an investor (Person)". The fixtures hold person
investors in rounds too, so the fake store has the same gap.

- **For A (store, real and fake): accept a person's ID wherever an investor's ID is accepted.**
  - `company(id)` returns a `Company` for a person: `type: "Person"`, name, description (what
    Cala says about them), `sources`. No schema change: `EntityRef.type` already allows it.
  - `investor_rounds(id)` and `portfolio(id)` return the person's own rounds and `INVESTED_IN`
    companies (or `[]`), and `people(id)` returns `[]`; none of them raises for a person.
  - With that, B's brief, investor check, chat and MCP tools work for angels with no change in
    B's code: they only call these four methods.
  - **Contract 1.1.1 is on main** (14 Nov; all three humans agreed): the wording in
    `contracts/schemas.py` and `contracts/api.md`, `CONTRACT_VERSION = "1.1.1"`, the changelog
    and `CLAUDE.md` §5. No model or signature changes.
  - **A: three of your tests are red on main until you follow** (accepted by the humans):
    `test_contracts.py::test_version` asserts "1.1.0", and two in `test_fake_store.py` compare
    `fixtures/models/index.json`, which holds `contract_version` (rebuild the fixtures index).
- **For C (frontend): an angel's card must not lead to an error.** When contract 1.1.1 is on
  main: `CONTRACT_VERSION` in `frontend/lib/types.ts` (and the mentions in the READMEs).
  - Until A's change is on `main`: when `investor.type === "Person"`, hide the brief link and the
    flip to the investor check, or show "No brief for individual investors yet" instead of the
    error state.
  - After it: nothing special is needed; a label such as "Angel" on those cards would help
    (`investor.type` is in every `InvestorScore`).
- **B, done (14 Nov, after A's change):** on the real store Tuomas Rasila x Kelluu works end to
  end: `company()` returns him as `Person`, he is #8 on Kelluu's Pitch (three more angels lower
  down), the conflict check answers, the brief came in 11 s with 10 citations. The eval set has
  an angel case (6/6 on fixtures and live).

## Stored judgements and briefs no longer overwrite each other (14 Nov)

- Found while checking angels: a machine with `USE_VECTOR_SEARCH` off sees other candidate lists
  than the server (Sensofusion 26 vs 28, Stendr 27 vs 30, Kelluu 24 vs 26). With one stored
  judgement per company, a founder report run from such a machine on the real store would have
  judged again and **replaced the server's judgement**, and its briefs the same way.
- Now: one stored judgement per candidate list and one stored brief per set of facts
  (`core/competitors.py`, `core/briefs.py`). The docs already in Atlas are still read. Checked on
  the real store with the server's setting: all three demo judgements read back in under a
  second, no Gemini call, nothing written.
- **Redeployed (14 Nov), checked on the server:** the three demo reports come back in 2-4 s from
  the stored judgements (Sensofusion: 4 competitors, 9 on Skip, as in C16's demo script); Tuomas
  Rasila x Kelluu check and brief answer (10 citations).
- **Everyone running the real store locally:** set `USE_VECTOR_SEARCH=true` in your `.env` to see
  what the server shows. Without it your reports differ from the demo (fewer competitors).

## Remote MCP checked through Caddy (14 Nov, after A17)

- With the MCP SDK's own client over HTTPS (`https://95-133-252-219.sslip.io/mcp`): token in the
  header and token as `?key=` both connect, 7 tools listed, `resolve_company` and
  `find_competitors` on Sensofusion answer (MyDefence, Stendr, Frankenburg, Origin Robotics),
  0.4-1.8 s. The demo question: Skyfall Ventures x Sensofusion -> PORTFOLIO conflict via Stendr,
  7 sources, 4.8 s. No token or a wrong one (header or `?key=`) -> 401 with the hint.
- **Claude Code 2.1.325 as the client** (`claude -p` with the server added): the header form
  exactly as `setup` prints it and the `?key=` URL both connect; "Using only PitchSwitch: should
  Sensofusion pitch Rainfall Ventures?" -> "No, skip: Rainfall backs Stendr, a direct competitor",
  with sources, 9-11 s.
- **Still not checked:** the custom-connector screen in claude.ai / Claude Desktop (needs a
  human at the app) and Cursor (not installed here). The server side is ready for both: with
  `?key=` the first request is already allowed, and it advertises no OAuth (all
  `/.well-known/oauth-*` paths and `/register` answer 404, the 401 carries no
  `WWW-Authenticate`). Cursor takes the same JSON as the `setup` output.

### For C (`docs/mcp-demo.md`, demo script)

- Setup text: paste what `python -m mcp_server.server setup https://95-133-252-219.sslip.io`
  prints (run from `backend/` with `MCP_TOKEN` set; it fills in the token). Put `<token>` in
  the docs, never the token itself: it is a password and the docs are public.
- Use the header form for Claude Code and Cursor, and the `?key=` URL only for the
  claude.ai / Claude Desktop connector, which has no header field.
- **Troubleshooting line worth adding:** with no token or a wrong one, Claude Code does not show
  our "missing or wrong token" message. After the 401 it tries OAuth by itself and reports
  "Dynamic Client Registration ... 404". That message means the token is missing or wrong;
  nothing is broken on the server.
- Expect an answer in about 10 s for the three demo companies (everything is stored); a company
  nobody asked about before can take a minute, and the tool then answers "Still working, call
  again", which the client does.
- **Rainfall x Sensofusion: fixed (058bb48, B).** The brief stated both "Stendr (Pre-Seed)" and
  "led the Seed round for Stendr (~$5M)". The brief prompt now uses the most specific fact for a
  round and leaves the other version out; it says "sources differ" only when two equally specific
  facts give different amounts or dates. Checked on the real store: Rainfall now says once "led
  Stendr's Seed round of ~$5 M in Apr 2026"; Maki.vc (demo #1 Pitch) has no false "sources
  differ"; Skyfall says it once, for Cardboard's amount.
- **Skyfall on stage (C16's MCP question), not new and not from B:** its brief says "Skyfall
  Ventures is a Glasgow-based hospitality and tourism company incorporated in 2013". That is
  what Cala's entity `9b65ed62` holds (its search snippet says "a venture capital firm
  headquartered in Glasgow"); the Oslo funds are separate entities (`8aa002e5` Fund II, `434eeb6f`
  Fund I). The conflict itself (backs Stendr, 7 sources) is right. Say "Skyfall" on stage, and
  don't read out its description.

### For A: redeploy, then warm

- The prompt is part of each stored brief's fingerprint, so **all stored briefs are written again**
  on first request after the redeploy (30-50 s each). Three are already stored under the new code
  (Rainfall, Maki.vc and Skyfall x Sensofusion). After the redeploy, run `python deploy/warm.py`
  (and `--check`) before any rehearsal.
- **Done (14 Nov):** A redeployed and warmed. On the server, the Rainfall brief gives Stendr's
  round once (as Seed), Maki.vc has no "sources differ", Skyfall has it once. `warm.py --check`:
  68 calls in 64 s, 0 failed, 0 slow. Remote MCP answers with the token (7 tools), 401 without.

## Replies to C's notes (14 Nov)

- **Malformed ID -> 404 (59d532e).** Anything that is not a Cala ID (a name, `not-a-real-id`,
  a broken link) now gets 404 `{"error": "No company or investor with that ID ('…'). IDs look
  like …; resolve_company finds one by name."}` on every route that takes an ID, before Cala is
  called. A well-formed but unknown ID already gave 404. MCP tools say the same in words, so a
  client that passes a name instead of an ID is told to call `resolve_company`.
- **Chat speed (2968bd8).** Tesi x NestAI "Who led NestAI's last round?" took 80 s because the
  agent asked Cala's search three near-identical questions (15-50 s each live). Now one search
  per question, kept short: same answer in 43 s cold, 9 s when that search is cached. Questions
  the other tools answer need no search ("Should I pitch Rainfall Ventures?": 23 s). A broad
  comparison ("Maki.vc vs Lifeline: defence deals") still takes ~95 s: the one Cala search
  alone is 68 s. Keep the elapsed-seconds display; for the demo, ask the chat question once in
  rehearsal so its search is cached.
- Both need A's redeploy to show on the server.
- **Angels by name (for A):** `/api/resolve` only passes on what `store.resolve(name,
  "investor")` returns, so people who invest have to come from the store (Cala entity search
  filtered to Person, kept when they have rounds or `INVESTED_IN`). Nothing in B needs to
  change for it; B checks Slush prep with "Tuomas Rasila" once it is on main.

## For C: "Prep every Slush 2026 investor" button (B17, b937720, 14 Nov)

- **API:** `POST /api/slush-prep` takes `all_slush_investors: true` (optional, default false).
  `investor_names` may then be empty; pasted names still run alongside. Without the flag and
  without names: 422. Contract stays **1.1.1** (additive, human decision): no version change in
  `frontend/lib/types.ts`; just add the optional field to the request in `frontend/lib/api.ts`.
- **What happens:** B asks Cala who attends Slush 2026 and adds those investors (live: 12 —
  Planet A Ventures, Revaia, Spintop Ventures, SSE Ventures, Tesi, Transition, Index Ventures,
  General Catalyst, Nefco, imec.Venture, Stephen Industries, EIC), duplicates of pasted names
  dropped, 25 at most. Each gets the same card as a pasted name: events carry `investor_name`
  as Cala writes it, then a `brief` or an `error` (e.g. "Transition" doesn't resolve to an
  investor in Cala: normal error card with your "Did you mean").
- **Stream:** two new `step` events without `investor_name` come first: "Finding the Slush 2026
  investors Cala knows of", then "Found 12 Slush 2026 investors in Cala; preparing 12". If
  Cala's list is unavailable, one `error` event without `investor_name` says so; pasted names
  still run.
- **UI wording:** it is the investors Cala's sources name, not everyone at Slush. Something like
  "Add the Slush 2026 investors Cala knows of (12)". Cold it takes a few minutes (12 briefs, 3 at
  a time, 30-40 s each); once warmed, seconds.
- **Not on the server until A redeploys.** Locally: run the backend from main.

## For C: score breakdown on every card (B17, 14 Nov)

- Each investor's **first reason** is now how its score adds up, e.g. Maki.vc on Sensofusion:
  "Score 73.3/100 = leads in this space 35/35 (2 led) + rounds in this space 13.3/20 (2) +
  recency 25/25 (last lead 2026-06-09) + warm paths 0/20 (0)", with the sources of the rounds
  counted. No contract change; it shows in the card, chat and MCP as it is.
- Investors only on the list as co-investors (no round in the space) get no breakdown: their
  score is just their warm paths, which the card lists already.
- It takes one of the 3 visible reason slots, so the last sourced fact moves behind "+ 1 more".
  If you'd rather style it (a small bar per signal, or under the score), it always starts with
  "Score " and the parts are split by " + ". Check the demo script if it reads out the reasons.
- On the server after A's next redeploy.

## Funding amount fields fixed (B21 contract, 14 Nov): for A and C

- **Contract (additive, stays 1.1.1):** `POST /api/founder/analyze` takes `target_amount_eur?`
  (the founder's raise), `POST /api/investor/check` takes `max_check_eur?` (the most the investor
  will put in). Responses gain `InvestorScore.funding_fit` / `InvestorCheck.funding_fit`:
  `FundingFit {verdict: "fits" | "too_small" | "too_large" | "unknown", text, sources}`, null
  unless an amount was sent. Rules: `contracts/api.md` ("Funding amount").
- **For C (C18, can start now):** add `FundingFit` and the two fields to `frontend/lib/types.ts`,
  the optional amount inputs (EUR), and the fit on the investor card / investor check (colour by
  `verdict`, `text` + source badges). Mock a `funding_fit` until B21 lands; the real API ignores
  the amounts until then and returns `funding_fit: null`.
- **For A (one command, one red test until then):** the sample fixtures now dump
  `"funding_fit": null`, so `test_fixtures_are_rebuilt_from_raw_without_changes` fails until you
  run `cd backend && python -m data.build_fixtures` and commit `contracts/fixtures/models/`.

## Scoring v2 (B18, 14 Nov): what changed, and for C

- **Signals now** (weights 30/20/15/15/20): leads (a round where Cala names no lead gives each
  of its n investors 1/n of a lead), companies in the space (not rounds; a company known only
  from an undated "backers" entry counts half), recency (only rounds in the space), activity
  (`deals_last_12m`, only for investors with a company in the space), warm paths. Ties: more
  active first, then wider in the space, then name. Eval set 6/6 on the real store.
- **Breakdown line** now has 5 parts, same format ("Score X/100 = ... + ... "; parts split by
  " + ", never inside a part), e.g. Maki.vc on Sensofusion: "Score 70.8/100 = leads 30/30
  (2 led) + companies here 13.3/20 (2) + recency 15/15 (last lead here 2026-06-09) + activity
  12.5/15 (5 in 12 mo) + warm paths 0/20 (0)".
- **For C, demo script (Sensofusion, live):** Pitch top 3 is Maki.vc 70.8, NATO Innovation
  Fund 39.2, Lifeline Ventures 34.2 (ScaleWolf and BSV dropped: their points were leads outside
  the space). **Skip order changed:** Skyfall Ventures is now #9 (was #3), Rainfall #6 (was #8);
  Skip scores are all 3.3-5.8 now. Point at Skyfall by name, not by position.
- **For C (C17, item f of the review):** the contract keeps Skip sorted by score, so label the
  Skip card's score "fit despite the conflict" (or hide it there). Sorting Skip by conflict
  strength would need a contract change.
- **Fixed (after B18): Kelluu's Skip flipping.** Cause: Cala's candidate list for Kelluu drifts
  by one company (Sensofusion vs Hyperion Robotics); each list had its own stored judgement, and
  re-judging made Gemini call Origin Robotics "direct" once and "same space" once, so its backers
  Change Ventures and Silicon Roundabout moved between Pitch and Skip. Now each candidate is
  judged once, ever (graph collection `verdicts`, one doc per company); a new list only sends its
  new candidates to Gemini. Old judgements were migrated with no Gemini call; the direct
  competitors of Sensofusion, Stendr and Kelluu are exactly what the server shows today, stable
  on either Kelluu list. Eval 6/6 live. Takes effect on the server after A's redeploy.
- **Still open:** Kelluu lists two "Maki.vc" (two Cala entities with the same name; so before B18).
- On the server after A's next redeploy; re-run `warm.py` after it.

## B19 scoring: closeness, stage fit, geography (for C and the demo script)

- Weights now: leads 25, companies here 15, recency 15, activity 10, warm paths 15, **stage fit 10**,
  **Nordic/Baltic 10**. The breakdown reason (first reason, parts split by " + ") shows the new parts,
  e.g. `stage fit 5/10 (5 of 10 rounds at Series A-Series B)`, `Nordic/Baltic 10/10 (Sweden)` or
  `(Helsinki, from its description)` when Cala has no country, `0/10 (country unknown)`.
- Closeness: each company in the space counts 0.75-1.25 by vector similarity to the startup (direct
  competitors 1.25); "companies here" reads `(2 companies, 2.3 weighted by closeness)`.
- Stage fit uses the investor's own labelled rounds from the store (same data as
  `investor_activity.rounds_by_stage`, but sourced); stage and geography count only for investors with
  a company in the space (like activity). No contract change.
- Live tops: Sensofusion Maki 69.6, Lifeline 36.3, NIF 35.5; Stendr Maki 65.6, Lifeline 42.9, NIF 30.4;
  Kelluu Maki 57.3, Lifeline 48.0, BSV 25.6. Sensofusion Skip: Skyfall is now #5 (13.1). Demo script:
  name investors, not positions. Eval 6/6 live. Needs A's redeploy + warm.

## B21 funding fit (for C, C18 already sends the fields)

- `target_amount_eur`: every InvestorScore gets `funding_fit`, comparing the raise with the middle half
  of the round sizes that investor joined (2x slack each way; grants left out). Live, Sensofusion
  at €3M: Maki "Joins rounds of €1.5M-€10M (17 rounds with amounts); your €3M raise fits"; NIF
  `too_small` ("€15M (1 round with amounts)"); about half the investors are `unknown` (no amounts in
  Cala). Sources = the rounds compared (at most 6).
- `max_check_eur`: InvestorCheck.funding_fit against the company's latest round with an amount, e.g.
  "Kelluu Oy's latest round (Series A) was €15M; your €2M check fits"; `too_large` under 10% of it.
- It is a flag only: it does not move the score (so nothing in the score breakdown). 0 or negative: 422.

## B20 warm paths (for A and C)

- Warm paths are now built from sourced evidence: a round both investors took part in, or a company
  in both portfolios (sources = those rounds and links, at most 6). `co_investors()` only picks who
  else to rank, so **A: no sources needed on co_investors() any more**.
- No known investor of the startup (Sensofusion): the funds that led a round in its space stand in,
  counted half: "Co-invested in 3 companies with Maki.vc, which led a round in your space (e.g. Egg
  White Company, IQM Quantum Computers)"; breakdown "warm paths 3.8/15 (1, through funds that lead
  here, counted half)". Sensofusion: 8 of 37 investors have one (was 0).
- Own investors: "Co-invested in 3 companies with your investor Tesi (e.g. ...)".
- Pairs the graph claims but Cala can't source are dropped (Kelluu: Lifeline Ventures AB lost "Tesi
  4x": the sourced rounds are on a separate "Lifeline Ventures" entity; 48.0 -> 40.5, still #2).
- Live: Sensofusion Maki 69.6, Lifeline 36.3, NIF 35.5, Tesi 35.4; Skip now starts with Skyfall.
  Stendr Maki 73.1; Kelluu Maki 57.3. Eval 6/6 live. Needs A's redeploy + warm.

## REQUEST for A (2026-11-14 17:00): redeploy + warm

Please redeploy the backend from current `main` and run `python deploy/warm.py` (then `--check`).
It brings B16 (stable competitors), B17, B18-B21 (scoring v2, new signals, funding fit, sourced warm
paths), the 404 for bad IDs, chat speed and the brief fix to the server. Competitor verdicts and
briefs are in Atlas already, so the demo reports stay at 2-4 s. B checks the site right after.

## Deployed site checked (2026-11-14 17:40, after A's redeploy): all OK

29/29 API checks + MCP (7 tools; token in header or ?key=; 401 without). Numbers ON THE SERVER (use
these in the demo script, not the local ones above):
- Sensofusion (3.2 s): Pitch Maki.vc 69.5, NATO Innovation Fund 38.5, Tesi 36.2, Lifeline Ventures AB
  35.4. Skip: Skyfall Ventures 16.9 (#1), Change Ventures 14.8, STARTUPLAB 14.8.
- Stendr (7.1 s): Maki.vc 72.2, Lifeline Ventures AB 43.5, NATO Innovation Fund 32.6.
- Kelluu (5.0 s): Maki.vc 57.3, Lifeline Ventures AB 40.5, BSV Ventures 25.6.
- Investor check Tesi x Kelluu with a EUR 2M check: "...latest round (Series A) was €15M; your €2M
  check fits". Briefs 0.5-1.2 s (stored). Slush prep with 2 names 6 s. Chat ~60 s cold: in the
  demo ask a question that was asked before (cached, ~10 s), or show it last.

