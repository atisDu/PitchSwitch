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

**Live since 14 Nov:** a Verda serverless **batch-job deployment** named `pitchlist-batch`, on a
`CPU Node` (size 8). Each trigger starts one container from our backend image; it crawls the
investors around the demo companies and per Nordic and Baltic country, derives co-investor counts
and activity stats into Atlas, answers with the counts, and exits, which ends the billing. It is
safe to rerun: investors crawled in the last 24 hours are skipped and every Cala response is
cached.

How it was set up (all through Verda's API, in `deploy/verda.py`):

```sh
python deploy/verda.py batch-image     # tag the image built on the instance, push it to vccr.io
python deploy/verda.py batch-create    # 2 secrets, the registry login, the job deployment
python deploy/verda.py batch-run       # trigger one job and follow it to its result
python deploy/verda.py batch-logs      # the container's log
```

- **Image:** `vccr.io/<project>/pitchlist-backend:<commit>` in Verda's Container Registry, pushed
  from the instance (it is already built there for linux/amd64).
- **Command:** `python -m batch.job_server` (port 8000, health check `GET /health`): serves one
  request, runs the job, returns the result as JSON, exits 0 or 1.
- **Keys:** `CALA_API_KEY` and `MONGODB_URI` are Verda secrets referenced by the deployment; the
  other settings are plain environment variables.
- **Scaling:** at most 1 replica, 4-hour deadline, queued requests dropped after an hour.
- **Trigger:** `POST https://tasks.datacrunch.io/pitchlist-batch/run?per_minute=30` with an
  inference API key. The call returns a job ID at once; status and result are read with the
  `X-Inference-Id` header (`deploy/verda.py batch-run <id>` does it). Note the host: Verda's docs
  say `tasks.verda.com`, which does not resolve; the deployment reports the `datacrunch.io` name.
- **Schedule:** a cron job on the instance (installed by `ship.sh`) runs
  `deploy/run-batch.sh` at 03:00 UTC, which only sends that trigger.

First run, 14 Nov 10:04 UTC: status `Completed` in under a minute;
`{"crawl": {"found": 111, "skipped": 110, "failed": 1}, "derive": {"investors": 110,
"with_co_investors": 96}}`, no Cala calls because the morning's crawl was still fresh. The one
failure is a person listed as an investor (not a company or a fund), which the crawl skips.

After a code change that affects the job, run `batch-image` and `batch-create` again: the
deployment keeps using the image tag it was created with.

The same job runs anywhere without Verda: `python -m batch.precompute_graph all --per-minute 30`
(the first full crawl ran this way from a laptop: 106 investors crawled, 229 live Cala calls).

## Demo day: warm the cache, then go cache-only (task A18)

```sh
python deploy/warm.py --check                  # calls every page the demo can reach; fails if slow
deploy/cache-only.sh 95.133.252.219 on         # the server now answers only from the Atlas cache
python deploy/warm.py --check                  # prove it: must pass again
# ... demo ...
deploy/cache-only.sh 95.133.252.219 off        # back to normal
```

`warm.py` covers the founder reports of Sensofusion, Stendr and Kelluu, the investor check and
brief of the top 3 Pitch and up to 6 Skip investors of each, and the pairs Tesi x NestAI and
Maki.vc x Stendr: 50 calls.

Checked on the deployed server on 14 Nov:

| Run | Result |
| --- | --- |
| First pass (cold briefs) | 50 calls in 280 s, 0 failed; 9 briefs took 17-57 s to write |
| Second pass | 50 calls in 50 s, 0 failed |
| **With `CACHE_ONLY=true`** | **50 calls in 22 s, 0 failed, 0 slow, 0 requests to Cala** |
| A never-seen name with `CACHE_ONLY=true` | HTTP 502 "CACHE_ONLY is on and GET /entities is not cached", at once |

So the demo path needs no live Cala call. Anything typed that was never looked up before will
show an error in cache-only mode: stick to the script, or switch it off for questions.
Rerun `warm.py` after anything that changes the reports (new judgements, a new crawl).

## Costs (task A19)

| Service | What we use | Cost |
| --- | --- | --- |
| Verda CPU instance | `CPU.4V.16G.CC`, on demand, FIN-03 | EUR 0.044 an hour, about EUR 1.05 a day; EUR 0.05 spent by Saturday noon of a EUR 200 balance |
| Verda batch job (nightly crawl) | Serverless batch-job deployment on a CPU node; billed only while a job runs (under a minute when fresh, about ten for a full crawl) | Cents a night |
| Verda Container Registry | One backend image (~130 MB compressed) | USD 0.20 per GB a month |
| MongoDB Atlas | M0 free tier: ~800 cached Cala responses, 110 investors in the graph, judgements, briefs | Free (512 MB limit; we use a few MB) |
| Cala | About 1,500 calls over the weekend; the full crawl was 229 live calls | Hackathon credits (they ran out once on Saturday and were topped up) |
| Gemini | Competitor judging and briefs (B) | Hackathon key |
| HTTPS | Let's Encrypt through Caddy, `sslip.io` name | Free |

Cala's limit on our key is 100 calls a minute (10 until Saturday noon). One process uses at most
60 (`CALA_PER_MINUTE`).

## For the README (hand-over to C)

- **How Verda is used:** one small CPU instance hosts the whole product (frontend, API, MCP
  server) behind Caddy with automatic HTTPS; the same image, pushed to Verda's Container
  Registry, runs as a serverless batch job every night to keep the investor graph and the cache
  fresh. The instance is created and deleted through
  Verda's Cloud API (`deploy/verda.py`); a deploy is one command (`deploy/ship.sh <ip>`).
- **Why not GPUs or Verda Inference:** the workload is I/O, not compute, and Verda's Inference
  API has no embeddings endpoint.
- **Process, in order:** local Docker Compose check -> instance via API -> ship -> Atlas network
  access fixed (the server was blocked at first and called Cala uncached; we added
  `CALA_REQUIRE_CACHE`) -> warm -> cache-only check.

## Still open

- `VERDA_API_KEY` in `.env` is rejected by Verda and is not used anywhere; the working keys are
  `VERDA_CLIENT_ID`/`VERDA_CLIENT_SECRET`, `VERDA_REGISTRY_USER`/`VERDA_REGISTRY_SECRET` and
  `VERDA_INFERENCE_KEY`.
- Vector search (A13) is not built; competitor candidates come from Cala queries.
- After the hackathon: `python deploy/verda.py batch-delete` and `delete`, and rotate the keys.
