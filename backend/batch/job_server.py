"""Run the precompute job as a Verda batch job (task A16).

A Verda batch-job deployment starts one container per job, sends it the HTTP request that
triggered the job, and expects the process to exit when the work is done. So this serves:

    GET  /health   -> 200 (Verda's health check)
    any other request -> runs crawl + derive, answers with the counts as JSON, then exits
                         (exit code 0 on success, 1 on failure)

    python -m batch.job_server        # listens on PORT (default 8000)

Trigger a run:  curl -X POST https://tasks.verda.com/<deployment-name>/run
Optional query: ?max_investors=150&per_minute=6&seeds=Kelluu,Stendr&step=all|crawl|derive
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

log = logging.getLogger("batch.job")


async def run_job(options: dict[str, str]) -> dict:
    """Crawl and derive with the given options. Returns the counts of both steps."""
    from batch.precompute_graph import crawl, derive
    from cache.graph import default_graph

    step = options.get("step", "all")
    graph = default_graph()
    result: dict = {}
    store = None
    try:
        if step in ("crawl", "all"):
            os.environ["USE_FAKE_STORE"] = "false"
            from data import get_store

            store = get_store()
            if options.get("per_minute"):
                store.cala.per_minute = int(options["per_minute"])
            result["crawl"] = await crawl(
                store,
                graph,
                seeds=options["seeds"].split(",") if options.get("seeds") else None,
                max_investors=int(options.get("max_investors", 150)),
            )
            result["cala"] = store.cala.stats()
        if step in ("derive", "all"):
            result["derive"] = await derive(graph)
    finally:
        if store is not None:
            await store.aclose()
        if hasattr(graph, "aclose"):
            await graph.aclose()
    return result


class _Handler(BaseHTTPRequestHandler):
    exit_code: int | None = None  # set once the single job has finished

    def _send(self, status: int, body: dict) -> None:
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _handle(self) -> None:
        url = urlparse(self.path)
        if url.path.rstrip("/") in ("/health", ""):
            self._send(200, {"ok": True})
            return
        options = {key: values[-1] for key, values in parse_qs(url.query).items()}
        try:
            result = asyncio.run(run_job(options))
            self._send(200, {"ok": True, **result})
            type(self).exit_code = 0
        except Exception as exc:  # report the failure to the caller, then exit non-zero
            log.exception("job failed")
            self._send(500, {"ok": False, "error": str(exc)})
            type(self).exit_code = 1
        threading.Thread(target=self.server.shutdown, daemon=True).start()

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = _handle

    def log_message(self, format: str, *args) -> None:  # route access logs through logging
        log.info("%s %s", self.address_string(), format % args)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("data.cala").setLevel(logging.WARNING)
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), _Handler)
    log.info("batch job server on port %d: waiting for one job", port)
    server.serve_forever()
    server.server_close()
    return _Handler.exit_code or 0


if __name__ == "__main__":
    sys.exit(main())
