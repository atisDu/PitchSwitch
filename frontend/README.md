# Pitchlist frontend

Next.js (App Router) + TypeScript + Tailwind. Owner: Agent C.

```sh
npm install
npm run mock                                 # mock API on http://localhost:8001
API_URL=http://localhost:8001 npm run dev    # app on http://localhost:3000, talking to the mock
npm run build && npm run lint && npm test    # checks
```

Without `API_URL` set, the app reads it from the repo-root `.env` (default
`http://localhost:8000`, B's FastAPI server).

## How it fits together

- `lib/types.ts` mirrors `contracts/schemas.py` field for field (contract 1.1.0).
- `lib/api.ts` is the only code that calls the backend. The browser calls same-origin
  `/api/*`; `next.config.ts` forwards that to `API_URL`. Switching between the mock and the
  real API means changing `API_URL`, nothing else.
- `lib/sse.ts` parses the event streams (`/api/jobs/{id}/stream`, `/api/chat`).
- `components/SourceBadge.tsx` is the source badge that goes next to every claim.

## Mock API (`mock/`)

Serves the routes in `contracts/api.md` from `contracts/fixtures/models/` (A's fixtures), with
no dependencies (`node mock/server.ts`).

- Founder reports, investor checks, briefs and event streams are A's **samples**: real Cala facts
  with placeholder ranking. B's API replaces them at CP3 (task C8).
- Demo IDs are in `contracts/fixtures/models/index.json` (`founder_mode`, `investor_mode`,
  `briefs`). Alias IDs (two Cala entries for one firm) map to the same fixture.
- `/api/resolve` returns the recorded search for a demo name, else a fuzzy match over every
  entity in the fixtures.
- `competitor_ids` works roughly as B's will: removed competitors and their conflicts drop out.
- The slush-prep and chat streams replay the recorded events, whatever you paste or ask.
- Env: `MOCK_PORT` (8001), `MOCK_DELAY_MS` (400, JSON latency), `MOCK_STEP_MS` (350, gap between
  stream events). Add `?mock_error=503` to any request to test error states.
