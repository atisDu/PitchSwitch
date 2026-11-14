# TODO.md — Pitchlist

Rules: see `CLAUDE.md` → Coordination rules. One task = one short branch (`a/A3-cala-client`), commit titles start with the task ID (`[A3] ...`), merge to `main` as soon as the task's tests pass.
Tick your own box in a separate small commit. `Needs:` = tasks that must be merged to `main` first.
Checkpoints: **CP1** Fri night · **CP2** Sat ~15:00 (real data) · **CP3** Sat ~20:00 (founder mode end to end, HARD) · **CP4** Sat night · **CP5** Sun morning (freeze + submit).

---

## T — Together (Friday night, all three, ~1 h, before splitting)

- [x] **T1 Repo scaffold** — every clone runs `entire enable --agent <agent>` and checks `.git/hooks/post-commit` exists; layout from CLAUDE.md, empty folders with `__init__.py`, `backend/pyproject.toml`, `frontend/` Next.js init, `notes/A.md|B.md|C.md`, `.gitignore`, `.env.example`. *(A drives, others review)*
- [x] **T2 Contracts** — `contracts/schemas.py`, `contracts/api.md`, `contracts/CHANGELOG.md` exactly as CLAUDE.md §5. All three approve. **Frozen after merge.**
- [x] **T3 Pick demo cases** — 3 founder-mode companies + 2 investor-mode pairs, incl. one counter-drone set (Sensofusion / Stendr / Nordic Air Defence) for the conflict moment. Write them in `contracts/fixtures/README.md`.

---

## A — Data & infra

### CP1 — Friday night (unblocks B and C)
- [x] **A1 Raw fixtures** — script `backend/data/record_fixtures.py` that calls Cala for the T3 cases and saves raw JSON to `contracts/fixtures/raw/`. Needs: T1–T3. *(Contract files: fixture data only, approved by T2.)*
- [x] **A2 Model fixtures + FakeDataStore** — mappers raw → contract models into `contracts/fixtures/models/`; `fake_store.py` implementing `DataStore` from them; `get_store()` with `USE_FAKE_STORE`. Tests: every fake method returns valid models. Needs: A1.

### CP2 — Saturday until ~15:00 (real data)
- [x] **A3 Cala client** — `cala_client.py`: async httpx, `X-API-KEY`, retries/backoff, semaphore, timeouts, call log. Tests with mocked HTTP. Needs: T1.
- [x] **A4 Introspection map** — fetch introspection once per entity type (Company, Organization, FundingRound, Person), cache to `backend/data/introspection.json`; helper `fields_for(type)`. Needs: A3.
- [x] **A5 Parsers** — `parsers.py`: amount text → EUR, partial dates → ISO. Table-driven tests ("~€15M", "over $100M", "$12M", "Oct 2025", "2026"). Needs: T1.
- [x] **A6 Store: resolve + company** — `CalaDataStore.resolve()` (with investor type/description guard) and `.company()`. Tests on raw fixtures. Needs: A3, A4.
- [x] **A7 Store: rounds + investor_rounds** — via `PARTICIPATES_IN_FUNDING_ROUND` + round properties; `is_lead` from the investor edge; amount via A5. Needs: A6, A5.
- [x] **A8 Store: portfolio + people** — `INVESTED_IN` outgoing for investors; `IS_BOARD_MEMBER_OF` / `FOUNDED` / `IS_CEO_OF` / `WORKS_AT` incoming for companies. Needs: A6.
- [x] **A9 Store: sourced_answer** — `knowledge_search` → markdown + `Reason[]` built from `explainability` claims and `context` source URLs. Needs: A3.
- [x] **A10 Atlas cache** — `cache/atlas.py` wraps client calls (key, 24 h TTL, `CACHE_ONLY` mode); hit/miss in the call log. Needs: A3.
- [x] **A11 candidate_competitors v1** — `knowledge_query` on industry + Nordic/Baltic countries + adjacent stages, dedupe, exclude self. (Vector search comes in A13.) Needs: A6.
- [x] **A12 Switch-over** — `USE_FAKE_STORE=false` works end to end for one demo company; tell B. **= CP2.** Needs: A6–A11.

### CP3/CP4 — Saturday evening & night
- [x] **A13 Vector search** — embeddings via Verda Inference API (Gemini fallback), Atlas Vector Search index, merge into `candidate_competitors`. Needs: A11.
- [x] **A14 Batch job: crawl** — `batch/precompute_graph.py` part 1: list active Nordic/Baltic investors, fetch portfolios + rounds into Atlas. Idempotent, resumable. Needs: A7, A8, A10.
- [x] **A15 Batch job: derive** — part 2: `investor_graph` (co-investor counts), `investor_activity` (last lead, rounds per sector/stage). `co_investors()` reads it. Needs: A14.
- [x] **A16 Run batch on Verda** — package as a Verda batch job, run overnight, document in `deploy/verda.md`. Needs: A15.
- [x] **A17 Docker + deploy** — Dockerfile (API + MCP server), deploy to a Verda CPU instance with HTTPS; share URL. Needs: B10.

### CP5 — Sunday morning
- [x] **A18 Pre-cache demo** — warm the cache for all T3 cases; verify `CACHE_ONLY=true` runs the full demo offline. Needs: A10, A17.
- [x] **A19 Deploy notes** — finish `deploy/verda.md` (services used, why, costs, how to run). Hand to C for the README.

---

## B — Intelligence

### CP1–CP2 — Friday night & Saturday (on FakeDataStore)
- [x] **B1 API skeleton** — `api/main.py`: FastAPI app, CORS, `/api/health`, all routes from §5.3 returning fixture-based stub responses validated by the models. Needs: T2, A2.
- [x] **B2 Gemini wrapper** — `agent/llm.py`: one function for structured (JSON-schema) calls with retries + temperature 0; model names from env. Tests with a mocked client. Needs: T1.
- [x] **B3 find_competitors** — `core/competitors.py`: candidates → Gemini judge → 10–15 `Competitor`s; reject IDs not in the candidate list. Needs: A2, B2.
- [x] **B4 Conflict: portfolio** — `core/conflict.py` PORTFOLIO kind + tests on fixtures. Needs: A2.
- [x] **B5 Conflict: board** — BOARD kind via `people()` + tests. Needs: B4.
- [x] **B6 Scoring** — `core/scoring.py`: collect investors from competitors' rounds, compute signals, weights dict, conflict → skip, reasons with sources → `FounderReport`. Needs: B3, B4.
- [x] **B7 Wire founder + investor routes** — `/api/resolve`, `/api/founder/analyze`, `/api/investor/check` use core (still fake store). Needs: B1, B6, B5.
- [x] **B8 Eval set** — `backend/tests/core/test_eval.py`: Kelluu → NATO Innovation Fund appears as lead; Maki.vc shows defence pre-seed leads; counter-drone conflict detected; runs on fake + real store. Needs: B6.

### CP3 — Saturday ~20:00
- [x] **B9 Real-data pass** — run everything with `USE_FAKE_STORE=false`, fix mapping surprises (via notes to A), tune weights. Needs: A12, B8.
- [x] **B10 Founder mode end to end** — the API serves real `FounderReport`s for the 3 demo companies under ~10 s (cached). **= CP3 with C.** Needs: B9.

### CP4 — Saturday night
- [x] **B11 Briefs** — `core/briefs.py` + `/api/brief`: facts + `sourced_answer` claims → Gemini formats → `Brief` with citations; no uncited sentences. Needs: B10, A9.
- [x] **B12 Agent tools** — `agent/tools.py`: tool schemas for core functions + `sourced_answer`. Needs: B10.
- [x] **B13 Agent loop + slush-prep** — `agent/gemini_agent.py` function-calling loop (max 12 calls), job store in memory, `/api/slush-prep` + `/api/jobs/{id}/stream` SSE of `AgentEvent`s. Needs: B12, B11.
- [x] **B14 Chat** — `/api/chat` streaming over the same loop, scoped to the current company/investor. Needs: B13.
- [x] **B15 MCP server** — `mcp_server/server.py` with the §5.4 tools; tested in Claude Desktop alongside Cala MCP. Needs: B10.

### CP5 — Sunday morning
- [x] **B16 Hardening** — timeouts, friendly errors, response validation everywhere, prompt tightening, final weight tune on the eval set.

### After CP5 — added 14 Nov
- [x] **B17 Slush option + score breakdown** — `/api/slush-prep` takes `all_slush_investors` (every Slush 2026 investor Cala names, optional field, contract stays 1.1.1); each investor's first reason is its score breakdown (points per signal). Details for C in `notes/B.md`.
- [x] **B18 Scoring v2: fair signals** — `core/scoring.py`, from the team's scoring review (14 Nov): (a) stop penalising missing lead data: Cala rarely marks the lead (23 of 28 Pitch investors can't earn the 35 lead points), so give partial credit or rescale over the signals that have data; (b) recency only from leads/rounds inside the space (now a lead in an unrelated company gives full recency: Gungnir, ScaleWolf); (c) count companies, not rounds (three rounds in one company ≠ three), and an undated "backers" entry counts less than a full round; (d) score activity: `deals_last_12m` is on the card but adds nothing; (e) break ties on activity or similarity, not by name (15 tie at 6.7, 5 at 31.7); (f) Skip: label its score "fit despite the conflict" or sort Skip by conflict strength. Keep the breakdown line in step. Rerun the eval set and check the demo script's numbers with C. Needs: B17.
- [x] **B19 Scoring v2: new signals** — (a) weight by closeness: a round in a direct competitor or a close peer (vector similarity, `company_vectors`) counts more than one in an adjacent company; (b) stage fit: the investor's usual stages (`investor_activity.rounds_by_stage`) against the startup's stage; (c) geography: a bonus for Nordic and Baltic funds. Uses data A already stores in Atlas; if the store doesn't expose it, ask A via `notes/B.md`. Needs: B18.
- [x] **B20 Warm paths that fire** — they never fire when the company has no known investors in Cala (Sensofusion). Fall back to co-investors of the funds that lead in the space (`investor_graph`), and attach sources (`co_investors()` has none today: ask A). Needs: B18.
- [x] **B21 Funding amount fit (optional)** — founder mode: an optional target amount the founder wants to raise; investor mode: an optional limit the investor will fund up to. Compare with the round sizes each investor has joined (`Round.amount_eur`; amounts are whole-round sizes, never one investor's share): a fit signal or flag on the card, with sources, nothing when unknown. Optional request fields on `/api/founder/analyze` and `/api/investor/check` (additive, like the Slush flag). Needs: B18.

---

## C — Product

### CP1 — Friday night
- [x] **C1 Frontend scaffold** — Next.js + TS + Tailwind, layout, `lib/types.ts` mirroring schemas, `lib/api.ts` client with `API_URL`. Needs: T1, T2.
- [x] **C2 Mock API** — `frontend/mock/` serving the §5.3 routes from `contracts/fixtures/models/` (incl. a fake SSE stream). Needs: A2, C1.

### CP2–CP3 — Saturday
- [x] **C3 Home + resolve** — mode toggle, input, `/api/resolve`, entity confirm list (name, type, description). Needs: C2.
- [x] **C4 Source badge component** — rank label + date + link; used everywhere. Needs: C1.
- [x] **C5 Founder report: competitors** — removable competitor chips with reason tooltips. Needs: C3.
- [x] **C6 Founder report: Pitch + Skip lists** — investor cards (score, leads in space, last lead, warm paths, reasons with badges); Skip list shows the conflict first. Needs: C5, C4.
- [x] **C7 Investor check screen** — conflicts, competitors + their backers, round history. Needs: C4.
- [x] **C8 Switch to real API** — point `API_URL` at B's server, fix integration issues (via notes to B). **= CP3 with B.** Needs: B10, C6.
- [ ] **C9 Founder testing** — show C6 to 3–5 founders at Junction; record feedback + one quote in `docs/user-testing.md`.

### CP4 — Saturday night
- [x] **C10 Brief page** — markdown render + citation list with badges. Needs: C8.
- [x] **C11 Slush prep** — paste investor names → `/api/slush-prep` → live SSE steps → brief cards. Needs: C10 (mock SSE until B13).
- [x] **C12 Chat panel** — streaming chat on report/brief pages. Needs: C8 (mock until B14).
- [x] **C13 MCP demo setup** — Claude Desktop config for Cala + Pitchlist MCP; test the "Should I pitch Fund X?" question; steps in `docs/mcp-demo.md`. Needs: B15.

### CP5 — Sunday morning
- [x] **C14 Polish** — loading / empty / error states, responsive check, copy pass.
- [x] **C15 README + docs** — `README.md` + `docs/`: setup, architecture, how Cala / Gemini / Atlas / Verda are used (from A19). Needs: A19.
- [ ] **C16 Demo + pitch** — demo script (founder conflict → flip to investor mode → MCP in Claude Desktop), slides, rehearse twice with the team, record a backup video.

### After CP5 — added 14 Nov
- [ ] **C17 Score transparency + Slush button** — show each investor's score breakdown (first reason, starts with "Score "; parts split by " + ") clearly on the card, e.g. a small bar per signal; Slush prep: a "Prep every Slush 2026 investor Cala knows of" option that sends `all_slush_investors: true` (names optional then). Wording and stream details in `notes/B.md`. Needs: B17.
- [x] **C18 Funding amount inputs** — optional "amount you want to raise" on the founder side and "most you will fund" on the investor side, sent to B's new optional fields; show the fit signal / flag on the cards. Needs: B21.
