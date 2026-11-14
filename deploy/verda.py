"""Create, inspect or delete the Pitchlist instance on Verda through the Cloud API.

    python deploy/verda.py status            # balance, our instance, its IP
    python deploy/verda.py create            # CPU instance + our SSH key (idempotent)
    python deploy/verda.py delete            # delete the instance and its OS volume

Needs VERDA_CLIENT_ID and VERDA_CLIENT_SECRET in .env (console -> Keys -> Cloud API
Credentials) and a public SSH key at ~/.ssh/id_ed25519_pitchlist_verda.pub
(`ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_pitchlist_verda -N ""`).
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.verda.com/v1"
ROOT = Path(__file__).resolve().parents[1]
HOSTNAME = "pitchlist"
KEY_NAME = "pitchlist-deploy"
PUBLIC_KEY = Path.home() / ".ssh" / "id_ed25519_pitchlist_verda.pub"

# On 14 Nov the only CPU type available on demand was the confidential-computing one in FIN-03
# (EUR 0.049/h); it only boots the image below. Plain CPU types were spot-only, and a spot
# instance can be evicted mid-demo.
INSTANCE_TYPE = os.environ.get("VERDA_INSTANCE_TYPE", "CPU.4V.16G.CC")
IMAGE = os.environ.get("VERDA_IMAGE", "26.04.cuda13.2.cc")
LOCATION = os.environ.get("VERDA_LOCATION", "FIN-03")


def load_env() -> None:
    for line in (ROOT / ".env").read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.split(" #", 1)[0].strip())


def call(method: str, path: str, token: str | None = None, body: dict | None = None):
    request = urllib.request.Request(API + path, method=method)
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(request, data=data, timeout=60) as reply:
            text = reply.read().decode()
    except urllib.error.HTTPError as error:
        raise SystemExit(f"Verda {method} {path} -> {error.code}: {error.read().decode()[:400]}")
    try:
        return json.loads(text) if text else None
    except ValueError:
        return text.strip().strip('"')


def login() -> str:
    load_env()
    client_id, secret = os.environ.get("VERDA_CLIENT_ID"), os.environ.get("VERDA_CLIENT_SECRET")
    if not client_id or not secret:
        raise SystemExit("VERDA_CLIENT_ID / VERDA_CLIENT_SECRET are missing from .env")
    body = {"grant_type": "client_credentials", "client_id": client_id, "client_secret": secret}
    return call("POST", "/oauth2/token", body=body)["access_token"]


def our_instance(token: str) -> dict | None:
    for instance in call("GET", "/instances", token) or []:
        if instance.get("hostname") == HOSTNAME:
            return instance
    return None


def status(token: str) -> None:
    balance = call("GET", "/balance", token)
    print(f"balance: {balance['amount']} {balance['currency']}")
    instance = our_instance(token)
    if not instance:
        print("instance: none")
        return
    fields = ("id", "hostname", "status", "ip", "instance_type", "location", "price_per_hour")
    print("instance:", {key: instance.get(key) for key in fields})


def create(token: str) -> None:
    instance = our_instance(token)
    if instance:
        print(f"already there: {instance.get('status')} at {instance.get('ip')}")
        return
    public_key = PUBLIC_KEY.read_text().strip()
    keys = call("GET", "/ssh-keys", token) or []
    key_id = next((k["id"] for k in keys if k.get("name") == KEY_NAME), None)
    if key_id is None:
        key_id = call("POST", "/ssh-keys", token, {"name": KEY_NAME, "key": public_key})
        key_id = key_id["id"] if isinstance(key_id, dict) else key_id
        print("registered SSH key", KEY_NAME)
    body = {
        "hostname": HOSTNAME,
        "description": "Pitchlist: frontend, API and MCP server (Junction 2026)",
        "instance_type": INSTANCE_TYPE,
        "image": IMAGE,
        "location_code": LOCATION,
        "ssh_key_ids": [key_id],
        "os_volume": {"name": "pitchlist-os", "size": 60},
        "contract": "PAY_AS_YOU_GO",
    }
    created = call("POST", "/instances", token, body)
    print("create requested:", created)
    for _ in range(90):  # up to 15 minutes
        instance = our_instance(token)
        state = (instance or {}).get("status")
        print(f"  status: {state}  ip: {(instance or {}).get('ip')}")
        if state == "running" and instance.get("ip"):
            return
        time.sleep(10)
    raise SystemExit("the instance did not reach 'running' in 15 minutes")


def delete(token: str) -> None:
    instance = our_instance(token)
    if not instance:
        print("nothing to delete")
        return
    body = {"action": "delete", "id": [instance["id"]], "delete_permanently": True}
    print("delete requested:", call("PUT", "/instances", token, body))


def main() -> int:
    commands = {"status": status, "create": create, "delete": delete}
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        print(__doc__)
        return 2
    commands[sys.argv[1]](login())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
