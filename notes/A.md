# Notes — Agent A (Data & infra)

Requests for other areas and "not yet checked against live <service>" lines go here (CLAUDE.md rules 2 and 12).

## Commitments from the contract review (1.1.0, 13 Nov)

TODO.md is owned by humans, so these extend my tasks here instead:

- **A2** also produces the mock fixtures listed in `contracts/api.md` → Fixtures: `index.json`,
  `resolve_*`, `investor_check_*`, `brief_*`, `agent_events_slush_prep.json`, `agent_events_chat.json`
  (samples: real Cala facts, placeholder ranking).
- **A8** `people(id)` and **A6** `company(id)` also work for investor IDs (B needs the investor's own
  people for BOARD conflicts).
- **A12** `co_investors()` on the real store returns `[]` (or a count computed from
  `investor_rounds()`) until the batch job (A15) fills the graph. It must not raise.
