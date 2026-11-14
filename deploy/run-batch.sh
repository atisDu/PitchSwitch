#!/bin/sh
# Trigger the nightly Verda batch job (crawl + derive). Installed in cron by deploy/ship.sh.
# The job runs in Verda's serverless batch product, not on this machine; this only starts it.
set -eu
ENV_FILE="${ENV_FILE:-/opt/pitchlist/src/.env}"
URL="${BATCH_URL:-https://tasks.datacrunch.io/pitchlist-batch/run?per_minute=30}"
KEY="$(grep '^VERDA_INFERENCE_KEY=' "$ENV_FILE" | cut -d= -f2-)"
[ -n "$KEY" ] || { echo "$(date -u +%FT%TZ) VERDA_INFERENCE_KEY missing in $ENV_FILE"; exit 1; }
echo "$(date -u +%FT%TZ) $(curl -s -m 60 -X POST -H "Authorization: Bearer $KEY" "$URL")"
