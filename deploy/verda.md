# Deploying Pitchlist on Verda

**Live since 14 Nov: https://95-133-252-219.sslip.io** (frontend, `/api/*`, MCP server at `/mcp`).

- Verda CPU instance `pitchlist`: `CPU.4V.16G.CC` (4 vCPU, 16 GB), location FIN-03, Ubuntu 26.04,
  about EUR 0.044 an hour (roughly EUR 1 a day). Created through the Cloud API by `deploy/verda.py`.
- HTTPS certificate from Let's Encrypt, obtained by Caddy for the `sslip.io` name of the IP.
- Checked on the server: health, home page, resolve, a real-data founder report in 3.9 s.

Update the deployment after new commits on `main`:

```sh
deploy/ship.sh 95.133.252.219
```

## What runs where

| Piece | Where | Why |
| --- | --- | --- |
| Frontend (Next.js), backend API, MCP server | One **Verda CPU instance**, Docker Compose, Caddy in front | One small always-on machine is enough: the work is I/O (Cala, Gemini, Atlas), not compute. |
| Nightly investor crawl (`batch.precompute_graph`) | A **Verda batch job** (serverless container that exits when done) | Runs for an hour or two, then costs nothing. Keeps the investor graph and the cache fresh. |
| Cache of Cala responses, investor graph, judgements | **MongoDB Atlas** (free M0) | Shared by the server, the batch job and every laptop. |
| Facts | **Cala** | The only source of data. |
| Competitor judging, briefs, agent | **Gemini** | Only wording and judgement; never numbers. |

Not used on Verda: GPUs, clusters, fine-tuning. Verda's Inference API has no embeddings
endpoint (`POST /v1/embeddings` returns 404), so vector search (A13) would use Gemini embeddings.

## The files

- `deploy/Dockerfile` — backend image (API and MCP server). No keys inside.
- `deploy/frontend.Dockerfile` — frontend image.
- `deploy/docker-compose.yml` — `api`, `mcp`, `frontend` and `caddy`.
- `deploy/Caddyfile` — `/api/*` goes to the backend (streams unbuffered, 30-minute timeout),
  `/mcp*` to the MCP server, everything else to the frontend.
- `.dockerignore` (repo root) — keeps `.env`, `.git`, caches and `node_modules` out of images.

## Run it on any machine with Docker (also the local check)

```sh
git clone git@github.com:atisDu/Otium.git && cd Otium
# put the team's .env in the repo root (see .env.example); on a server set:
#   USE_FAKE_STORE=false
#   SITE_ADDRESS=<public-ip-with-dashes>.sslip.io      # HTTPS without owning a domain
cd deploy
docker compose --env-file ../.env up -d --build
curl http://localhost/api/health        # {"ok":true,"contract_version":"1.1.0"}
```

- Without `SITE_ADDRESS` the site is served over plain HTTP on port 80.
- With `SITE_ADDRESS=203-0-113-7.sslip.io` (the instance's IP, dashes instead of dots) Caddy gets
  a Let's Encrypt certificate by itself. Ports 80 and 443 must be open on the instance.
- Update after a `git pull`: the same `up -d --build` command.
- Logs: `docker compose --env-file ../.env logs -f api`. Stop: `docker compose ... down`.
- MCP server for agents (Claude Desktop, Cursor): `https://<site>/mcp` (streamable HTTP).

Checked locally on 14 Nov: health, the home page, `/api/resolve`, a real-data founder report
(3–6 s on the warm Atlas cache) and the slush-prep event stream, all through Caddy.

## On a Verda CPU instance

How the live instance was made; repeat these to rebuild it from nothing.

```sh
# once: Cloud API credentials in .env (VERDA_CLIENT_ID, VERDA_CLIENT_SECRET) and a deploy key
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_pitchlist_verda -N ""
python deploy/verda.py create      # registers the key, orders the instance, waits until it runs
python deploy/verda.py status      # balance, IP, price
deploy/ship.sh <ip>                # Docker, code, server .env, compose up, nightly cron
python deploy/verda.py delete      # when the hackathon is over
```

- `deploy/verda.py` picks `CPU.4V.16G.CC` in FIN-03: on 14 Nov it was the only CPU type available
  on demand (plain CPU types were spot-only, and a spot instance can be evicted mid-demo). It only
  boots the `26.04.cuda13.2.cc` image.
- `deploy/ship.sh` copies the code of the current commit with `git archive` (no `.git`, no local
  files) and writes the server's `.env` from the local one with only what the server needs: the
  Cala, Gemini and MongoDB settings, plus `USE_FAKE_STORE=false`, `CALA_REQUIRE_CACHE=true` and
  `SITE_ADDRESS`. Verda credentials never leave the laptop.
- **MongoDB Atlas must allow the instance's IP** (Network Access). When it did not, every cache
  lookup timed out and the server called Cala uncached (about 150 calls) until we stopped it.
  `CALA_REQUIRE_CACHE=true` now makes the server refuse to call Cala without its cache.
- The instance is on the public internet and the API has no login: bots probed it within
  minutes. Fine for a demo; do not leave it up afterwards.

## The batch job on Verda (task A16)

The same backend image, started with a different command:

- **Image:** the backend image, pushed to a registry Verda can pull from.
- **Command:** `python -m batch.job_server` (port 8000, health check `GET /health`).
- **Environment:** the same variables as `.env` (`CALA_API_KEY`, `MONGODB_URI`, `MONGODB_DB`, ...).
- **Type:** batch job deployment, max concurrent jobs 1, deadline 4 hours.
- **Trigger** (once a night, or by hand):
  `curl -X POST "https://tasks.verda.com/<deployment-name>/run?per_minute=30"`

Each trigger starts one container. It crawls the investors around the demo companies and per
Nordic and Baltic country, derives co-investor counts and activity stats into Atlas, answers with
the counts, and exits (which ends the billing). It is safe to stop and rerun: investors crawled
in the last 24 hours are skipped and every Cala response is cached.

The same job runs anywhere without Verda: `python -m batch.precompute_graph all --per-minute 30`.

### What actually runs today

The crawl first ran from a laptop on 14 Nov (112 investors found, 106 crawled, 229 live Cala
calls, 45 minutes at 6 calls a minute), then derive wrote 110 investors to Atlas, 96 of them with
co-investors. On the instance, `ship.sh` installs a **nightly cron job** (03:00 UTC) that runs the
same job in the backend image:

```sh
docker compose --env-file ../.env run --rm -T api python -m batch.precompute_graph all --per-minute 30
```

The serverless batch-job deployment described above is ready in code (`batch/job_server.py`) but
not created yet: it needs the image in a registry Verda can pull from.

## Still open

- Create the serverless batch-job deployment (push the image to a registry first).
- `VERDA_API_KEY` in `.env` is rejected by Verda's Inference API; it is not used anywhere.
- Costs and the final write-up for the README: task A19.
