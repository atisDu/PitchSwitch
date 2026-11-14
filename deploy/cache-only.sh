#!/bin/sh
# Turn cache-only mode on or off on the deployed server.
#
#   deploy/cache-only.sh <instance-ip> on      # demo: answer only from the Atlas cache, never call Cala
#   deploy/cache-only.sh <instance-ip> off     # normal: call Cala for anything not cached
#
# With it on, a request for data that was never cached gets a clear error instead of a slow
# live call. Warm the cache first:  python deploy/warm.py --check
set -eu

IP="${1:?usage: deploy/cache-only.sh <instance-ip> on|off}"
case "${2:-}" in
  on) VALUE=true ;;
  off) VALUE=false ;;
  *) echo "usage: deploy/cache-only.sh <instance-ip> on|off" >&2; exit 2 ;;
esac
KEY="${SSH_KEY:-$HOME/.ssh/id_ed25519_pitchlist_verda}"

ssh -i "$KEY" -o BatchMode=yes "root@$IP" "
  cd /opt/pitchlist/src &&
  if grep -q '^CACHE_ONLY=' .env; then sed -i 's/^CACHE_ONLY=.*/CACHE_ONLY=$VALUE/' .env; else echo 'CACHE_ONLY=$VALUE' >> .env; fi &&
  cd deploy && docker compose --env-file ../.env up -d api mcp 2>&1 | tail -2
"
echo "CACHE_ONLY=$VALUE on $IP (the API restarts in a few seconds)"
