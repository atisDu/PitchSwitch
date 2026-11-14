#!/bin/sh
# Ship the committed code to the Verda instance and (re)start the stack.
#
#   deploy/ship.sh <instance-ip>
#
# What it does, in order:
#   1. installs Docker on the instance if it is missing;
#   2. copies the code of the current git commit (git archive: no .git, no local files);
#   3. writes the server's .env from the local one: only the keys the server needs
#      (Cala, Gemini, MongoDB, and the key that triggers the batch job), plus USE_FAKE_STORE=false, CALA_REQUIRE_CACHE=true (never call
#      Cala when Atlas is unreachable) and SITE_ADDRESS for HTTPS;
#   4. builds and starts everything with Docker Compose;
#   5. installs a nightly cron job that triggers the Verda batch job (the investor crawl).
# Rerun it after new commits to update the deployment.
set -eu

IP="${1:?usage: deploy/ship.sh <instance-ip>}"
KEY="${SSH_KEY:-$HOME/.ssh/id_ed25519_pitchlist_verda}"
ROOT="$(git rev-parse --show-toplevel)"
SITE="$(echo "$IP" | tr . -).sslip.io"   # HTTPS without owning a domain
REMOTE=/opt/pitchlist

run() { ssh -i "$KEY" -o StrictHostKeyChecking=accept-new -o BatchMode=yes "root@$IP" "$@"; }

echo "1/4 Docker"
run 'command -v docker >/dev/null 2>&1 || (curl -fsSL https://get.docker.com | sh >/dev/null 2>&1)'
run 'docker --version'

echo "2/4 code ($(git -C "$ROOT" rev-parse --short HEAD))"
run "rm -rf $REMOTE/src && mkdir -p $REMOTE/src"
git -C "$ROOT" archive --format=tar HEAD | run "tar -x -C $REMOTE/src"

echo "3/4 server .env"
grep -E '^(CALA_|GEMINI_|MONGODB_|MCP_TOKEN=|CACHE_ONLY=|USE_VECTOR_SEARCH=|VERDA_INFERENCE_KEY=)' "$ROOT/.env" | run "umask 077; cat > $REMOTE/src/.env"
run "printf 'USE_FAKE_STORE=false\nCALA_REQUIRE_CACHE=true\nSITE_ADDRESS=%s\n' '$SITE' >> $REMOTE/src/.env"

echo "4/4 build and start"
run "cd $REMOTE/src/deploy && docker compose --env-file ../.env up -d --build 2>&1 | tail -8"

# Nightly at 03:00 UTC: trigger the Verda batch job that refreshes the investor graph and the
# cache (task A16; the deployment itself is created by `python deploy/verda.py batch-create`).
CRON="0 3 * * * $REMOTE/src/deploy/run-batch.sh >> /var/log/pitchlist-batch.log 2>&1"
printf '%s\n' "$CRON" | run "cat > /tmp/pitchlist.cron && (crontab -l 2>/dev/null | grep -v -e precompute_graph -e run-batch; cat /tmp/pitchlist.cron) | crontab - && rm /tmp/pitchlist.cron"

echo "deployed: https://$SITE"
