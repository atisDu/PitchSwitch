"""Manage Pitchlist on Verda through the Cloud API: the instance and the batch job.

    python deploy/verda.py status            # balance, our instance, its IP, the batch job
    python deploy/verda.py create            # CPU instance + our SSH key (idempotent)
    python deploy/verda.py delete            # delete the instance and its OS volume

    python deploy/verda.py batch-image       # push the backend image to Verda's registry
    python deploy/verda.py batch-create      # secrets + registry login + the batch-job deployment
    python deploy/verda.py batch-run         # trigger one run and wait for its result
    python deploy/verda.py batch-run <id>    # follow a job that is already queued
    python deploy/verda.py batch-delete      # remove the batch-job deployment

Needs in .env (or .env.verda), all from the Verda console -> Credentials:
  VERDA_CLIENT_ID, VERDA_CLIENT_SECRET        Cloud API credentials
  VERDA_REGISTRY_USER, VERDA_REGISTRY_SECRET  Container Registry credentials (batch-image/-create)
  VERDA_INFERENCE_KEY                         Inference API key (batch-run)
and a public SSH key at ~/.ssh/id_ed25519_pitchlist_verda.pub
(`ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_pitchlist_verda -N ""`).
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
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
    for name in (".env", ".env.verda"):
        path = ROOT / name
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.split(" #", 1)[0].strip())


def need(*names: str) -> list[str]:
    missing = [name for name in names if not os.environ.get(name)]
    if missing:
        raise SystemExit(f"missing in .env or .env.verda: {', '.join(missing)}")
    return [os.environ[name] for name in names]


def call(
    method: str,
    path: str,
    token: str | None = None,
    body: dict | None = None,
    ok=(),
    base=API,
    headers: dict | None = None,
):
    """One API call. Statuses listed in `ok` are returned as (status, text) instead of exiting."""
    request = urllib.request.Request(base + path, method=method)
    request.add_header("Content-Type", "application/json")
    for name, value in (headers or {}).items():
        request.add_header(name, value)
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(request, data=data, timeout=60) as reply:
            text = reply.read().decode()
    except urllib.error.HTTPError as error:
        detail = error.read().decode()[:400]
        if error.code in ok:
            return error.code, detail
        raise SystemExit(f"Verda {method} {path} -> {error.code}: {detail}") from None
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
    jobs = [job.get("name") for job in call("GET", "/job-deployments", token) or []]
    print("batch-job deployments:", jobs or "none")


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


# --- The batch job (task A16): the nightly crawl as a Verda serverless batch-job deployment ----

JOB = "pitchlist-batch"
REGISTRY = "vccr.io"
REGISTRY_CREDENTIALS = "pitchlist-vcr"
# What the job needs at run time. Values are stored as Verda secrets, not in the deployment.
JOB_SECRETS = {
    "CALA_API_KEY": "pitchlist-cala-api-key",
    "MONGODB_URI": "pitchlist-mongodb-uri",
}
JOB_PLAIN_ENV = {
    "CALA_BASE_URL": "https://api.cala.ai/v1",
    "MONGODB_DB": "pitchlist",
    "USE_FAKE_STORE": "false",
    "CALA_REQUIRE_CACHE": "true",
    "PORT": "8000",
}
SSH_KEY = Path.home() / ".ssh" / "id_ed25519_pitchlist_verda"


def image_name() -> str:
    """vccr.io/<project id>/pitchlist-backend:<git commit>. The project ID is in the user name."""
    (user,) = need("VERDA_REGISTRY_USER")
    project = user.removeprefix("vcr-").split("+", 1)[0]
    commit = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return f"{REGISTRY}/{project}/pitchlist-backend:{commit}"


def batch_image(token: str) -> None:
    """Tag the image the instance already built (linux/amd64) and push it to Verda's registry."""
    user, secret = need("VERDA_REGISTRY_USER", "VERDA_REGISTRY_SECRET")
    instance = our_instance(token)
    if not instance or not instance.get("ip"):
        raise SystemExit("no running instance to push from: run `create` and deploy/ship.sh first")
    image = image_name()
    project_registry = image.rsplit("/", 1)[0]
    script = (
        f"docker login {project_registry} -u '{user}' --password-stdin >/dev/null && "
        f"docker tag deploy-api {image} && docker push {image} | tail -2"
    )
    ssh = ["ssh", "-i", str(SSH_KEY), "-o", "BatchMode=yes", f"root@{instance['ip']}", script]
    subprocess.run(ssh, input=secret + "\n", text=True, check=True)
    print("pushed", image)


def batch_create(token: str) -> None:
    user, secret = need("VERDA_REGISTRY_USER", "VERDA_REGISTRY_SECRET")
    existing = {s.get("name") for s in call("GET", "/secrets", token) or []}
    for variable, secret_name in JOB_SECRETS.items():
        (value,) = need(variable)
        if secret_name in existing:
            call("DELETE", f"/secrets/{secret_name}", token, ok=(404,))
        call("POST", "/secrets", token, {"name": secret_name, "value": value})
        print("secret stored:", secret_name)

    known = {c.get("name") for c in call("GET", "/container-registry-credentials", token) or []}
    if REGISTRY_CREDENTIALS not in known:
        auth = base64.b64encode(f"{user}:{secret}".encode()).decode()
        config = json.dumps({"auths": {REGISTRY: {"auth": auth}}})
        body = {"name": REGISTRY_CREDENTIALS, "type": "custom", "docker_config_json": config}
        call("POST", "/container-registry-credentials", token, body)
        print("registry login stored:", REGISTRY_CREDENTIALS)

    env = [
        {"name": name, "value_or_reference_to_secret": value, "type": "plain"}
        for name, value in JOB_PLAIN_ENV.items()
    ] + [
        {"name": name, "value_or_reference_to_secret": secret_name, "type": "secret"}
        for name, secret_name in JOB_SECRETS.items()
    ]
    body = {
        "name": JOB,
        "container_registry_settings": {"credentials": {"name": REGISTRY_CREDENTIALS}},
        "containers": [
            {
                "image": image_name(),
                "exposed_port": 8000,
                "healthcheck": {"enabled": True, "port": 8000, "path": "/health"},
                "entrypoint_overrides": {
                    "enabled": True,
                    "entrypoint": ["python", "-m", "batch.job_server"],
                    "cmd": [],
                },
                "env": env,
            }
        ],
        # A CPU node is all the crawl needs: it waits on Cala and MongoDB, it does not compute.
        "compute": {"name": "CPU Node", "size": 8},
        "scaling": {
            "max_replica_count": 1,
            "queue_message_ttl_seconds": 3600,
            "deadline_seconds": 4 * 3600,
        },
    }
    if any(job.get("name") == JOB for job in call("GET", "/job-deployments", token) or []):
        call("DELETE", f"/job-deployments/{JOB}", token)
        print("replacing the existing deployment")
        time.sleep(5)
    created = call("POST", "/job-deployments", token, body)
    shown = {k: created.get(k) for k in ("name", "endpoint_base_url", "created_at") if k in created}
    print("batch-job deployment created:", shown or created)


def batch_endpoint(token: str) -> str:
    job = call("GET", f"/job-deployments/{JOB}", token)
    return (job.get("endpoint_base_url") or f"https://tasks.verda.com/{JOB}").rstrip("/")


def batch_run(token: str, job_id: str | None = None) -> None:
    """Trigger one job (or follow one already queued), polling until its replica has finished."""
    (key,) = need("VERDA_INFERENCE_KEY")
    host = batch_endpoint(token).rsplit("/", 1)[0]
    if job_id is None:
        print("triggering", f"{host}/{JOB}/run")
        started = call("POST", f"/{JOB}/run?per_minute=30", key, base=host)
        print("queued:", started)
        job_id = started["Id"]
    job = {"X-Inference-Id": job_id}
    last = None
    for _ in range(360):  # up to an hour
        state = call("GET", f"/status/{JOB}", key, base=host, ok=(404,), headers=job)
        status = state.get("Status") if isinstance(state, dict) else state
        if status != last:
            print(f"  {time.strftime('%H:%M:%S')} status: {status}")
            last = status
        if str(status).lower() not in ("queue", "queued", "pending", "running", "inference"):
            break
        time.sleep(10)
    print("result:", call("GET", f"/result/{JOB}", key, base=host, ok=(404, 425), headers=job))
    print("logs: python deploy/verda.py batch-logs")


def batch_logs(token: str) -> None:
    logs = call("GET", f"/job-deployments/{JOB}/logs", token, ok=(404,))
    print(json.dumps(logs, indent=1)[-3000:] if not isinstance(logs, str) else logs[-3000:])


def batch_delete(token: str) -> None:
    print("deleted:", call("DELETE", f"/job-deployments/{JOB}", token, ok=(404,)))


def main() -> int:
    commands = {
        "status": status,
        "create": create,
        "delete": delete,
        "batch-image": batch_image,
        "batch-create": batch_create,
        "batch-run": batch_run,
        "batch-logs": batch_logs,
        "batch-delete": batch_delete,
    }
    if len(sys.argv) < 2 or sys.argv[1] not in commands:
        print(__doc__)
        return 2
    if sys.argv[1] == "batch-run" and len(sys.argv) == 3:
        batch_run(login(), sys.argv[2])  # follow a job that is already queued
    else:
        commands[sys.argv[1]](login())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
