# Deploying Pitchlist on Verda

Status (14 Nov): the images build and the whole stack runs locally with the commands below.
**Not yet deployed to Verda**: that needs Verda Cloud API credentials or an instance (see "What
is still needed").

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
- `deploy/docker-compose.yml` — `api`, `frontend`, `caddy`, and `mcp` (off until task B15).
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
- MCP server (once B15 lands): `docker compose --env-file ../.env --profile mcp up -d`.

Checked locally on 14 Nov: health, the home page, `/api/resolve`, a real-data founder report
(3–6 s on the warm Atlas cache) and the slush-prep event stream, all through Caddy.

## On a Verda CPU instance

1. In the Verda console create a **CPU instance** (2–4 vCPU, 8 GB is plenty), Ubuntu image, with
   your SSH key. Open ports 22, 80 and 443.
2. `ssh root@<ip>`, install Docker (`curl -fsSL https://get.docker.com | sh`).
3. Follow "Run it on any machine" above. Copy `.env` with `scp`, never through git.
4. In MongoDB Atlas → Network Access, allow the instance's IP (or `0.0.0.0/0`).
5. Share `https://<ip-with-dashes>.sslip.io` with the team; C sets it as the demo URL.

The instance can also be created through the API (`POST https://api.verda.com/v1/instances`
after an OAuth token from `/v1/oauth2/token`); that needs a Cloud API client ID and secret.

## The batch job on Verda (task A16)

The same backend image, started with a different command:

- **Image:** the backend image, pushed to a registry Verda can pull from.
- **Command:** `python -m batch.job_server` (port 8000, health check `GET /health`).
- **Environment:** the same variables as `.env` (`CALA_API_KEY`, `MONGODB_URI`, `MONGODB_DB`, ...).
- **Type:** batch job deployment, max concurrent jobs 1, deadline 4 hours.
- **Trigger** (once a night, or by hand):
  `curl -X POST "https://tasks.verda.com/<deployment-name>/run?per_minute=6"`

Each trigger starts one container. It crawls the investors around the demo companies and per
Nordic and Baltic country, derives co-investor counts and activity stats into Atlas, answers with
the counts, and exits (which ends the billing). It is safe to stop and rerun: investors crawled
in the last 24 hours are skipped and every Cala response is cached.

The same job runs anywhere without Verda: `python -m batch.precompute_graph all --per-minute 6`.

## What is still needed

- **Verda access.** `VERDA_API_KEY` in `.env` is rejected by Verda's Inference API and is not a
  Cloud API credential pair. To create the instance and the batch deployment we need either a
  Cloud API **client ID + secret** (console → Keys → Cloud API Credentials), or a person creating
  them in the console as above.
- **A registry for the batch image** (Verda Container Registry or GHCR).
- Costs and final URLs: filled in with task A19.
