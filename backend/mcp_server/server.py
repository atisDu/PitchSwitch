"""PitchSwitch MCP server (B15): the §5.4 tools for any MCP client (Claude Desktop, Cursor).

Thin by design: the tools are the functions in agent/tools.py, the same ones the Gemini agent
calls. Each takes entity IDs and returns contract models as JSON, sources attached.

    python -m mcp_server.server                stdio, for a client on this machine (no token)
    python -m mcp_server.server http           streamable HTTP on $MCP_HOST:$MCP_PORT/mcp
                                               (0.0.0.0:8001); needs MCP_TOKEN, see TokenGate
    python -m mcp_server.server setup [url]    print what to paste into Claude, Claude Code and
                                               Cursor to connect to the server at `url`

Reads the repo's .env like the API does (USE_FAKE_STORE, CALA_API_KEY, GEMINI_API_KEY, ...).

Behind a reverse proxy keep MCP_HOST=0.0.0.0: bound to 127.0.0.1 the SDK only accepts requests
whose Host header is localhost and answers the site's own hostname with 421.
"""

from __future__ import annotations

import asyncio
import functools
import json
import os
import secrets
import sys
from collections.abc import Callable
from urllib.parse import parse_qs

import uvicorn
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from starlette.responses import JSONResponse

from agent import tools
from agent.llm import LLMError
from data import DataError
from data.config import load_env

INSTRUCTIONS = """PitchSwitch tells a startup founder which investors to pitch and which to skip, \
from Cala's sourced data. An investor has a conflict when it backs a direct competitor of the \
company (or one of its people sits on that competitor's board).
Start with resolve_company (kind "company" or "investor") to turn names into IDs; every other \
tool takes those IDs. For "should I pitch fund X?" call check_conflict, or investor_brief for a \
cited one-page answer. For "who should I pitch?" call rank_investors.
Every fact carries `sources` (name, url, date, rank): cite them, and state nothing about \
funding, investors or dates that the tools did not return.
`lead_data: "unknown"` and `is_lead: null` mean Cala's round data does not say who led, not that \
the investor did not lead. investor_brief also draws on Cala's knowledge search, so it can name \
a lead or an amount that the round data lacks; that is more detail, not a contradiction.
Amounts are always the size of the whole round, never one investor's share. If you add anything \
from outside these tools (a web search, your own knowledge), say that it is not from PitchSwitch.
A tool that answers "still working" has not failed: call it again with the same arguments."""



# Clients give a tool call about a minute (Claude Desktop: 80 s), and the first question about a
# company nobody asked about before can take longer (Cala lookups, the judge, the brief). So a
# call that is not done in time says "call again", while its work goes on; the next identical
# call waits for that same work, or finds it finished and cached.
REPLY_WITHIN = 50.0  # seconds
_running: dict[str, asyncio.Task] = {}  # call -> its work, until the work ends


def _told(fn: Callable) -> Callable:
    """The tool, answering within REPLY_WITHIN, with the failures we expect (unknown ID, Cala or
    Gemini unavailable) told to the client in words. Without that the SDK treats them as crashes
    and withholds the reason."""

    @functools.wraps(fn)
    async def tool(*args, **kwargs):
        try:
            tools.check_ids(*(v for k, v in kwargs.items() if k.endswith("_id")))
        except DataError as exc:
            raise ToolError(str(exc)) from exc
        key = repr((fn.__name__, args, sorted(kwargs.items())))
        work = _running.get(key)
        if work is None:
            work = _running[key] = asyncio.ensure_future(fn(*args, **kwargs))
            # Forget it once done; reading the exception keeps an unclaimed failure quiet.
            work.add_done_callback(
                lambda t: (_running.pop(key, None), t.cancelled() or t.exception())
            )
        try:
            return await asyncio.wait_for(asyncio.shield(work), REPLY_WITHIN)
        except TimeoutError:
            raise ToolError(
                f"Still working: this is the first question about this company or investor, so "
                f"the data is being fetched and judged. Nothing failed. Call {fn.__name__} again "
                f"with the same arguments in about 30 seconds; calling again is safe and picks "
                f"up the same work."
            ) from None
        except (DataError, LLMError) as exc:
            raise ToolError(str(exc) or type(exc).__name__) from exc

    return tool


server = MCPServer("pitchswitch", title="PitchSwitch", instructions=INSTRUCTIONS)
for _tool in tools.MCP_TOOLS:
    server.add_tool(_told(_tool))  # name, description and schema come from the function itself


# --- over HTTP: a shared token ------------------------------------------------------------------

MIN_TOKEN = 16  # characters; a short token on a public URL is no lock


class TokenGate:
    """ASGI wrapper for the HTTP transport: every request must carry the shared token, either as
    `Authorization: Bearer <token>` or as `?key=<token>` in the URL (for clients that only take a
    URL). stdio needs none: there the client starts the server on its own machine."""

    def __init__(self, app, token: str) -> None:
        self.app, self.token = app, token.encode()

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] == "http":
            auth = dict(scope["headers"]).get(b"authorization", b"")
            given = auth[7:].strip() if auth[:7].lower() == b"bearer " else b""
            given = given or parse_qs(scope["query_string"]).get(b"key", [b""])[0]
            if not secrets.compare_digest(given, self.token):
                denied = JSONResponse(
                    {"error": "PitchSwitch MCP: missing or wrong token. Send it as "
                     "'Authorization: Bearer <token>' or add ?key=<token> to the URL."},
                    status_code=401,
                )
                await denied(scope, receive, send)
                return
        await self.app(scope, receive, send)


def _token() -> str:
    token = os.environ.get("MCP_TOKEN", "").strip()
    if len(token) < MIN_TOKEN:
        sys.exit(
            f"MCP_TOKEN must be set (at least {MIN_TOKEN} characters) to serve MCP over HTTP: "
            "without it anyone with the URL could call the tools.\n"
            "Make one and put it in .env:\n"
            '  python -c "import secrets; print(\'MCP_TOKEN=\' + secrets.token_urlsafe(24))"'
        )
    return token


def setup(url: str, token: str) -> str:
    """What to paste into each client to connect it to the server at `url`."""
    url = url.rstrip("/")
    url = url if url.endswith("/mcp") else f"{url}/mcp"
    cursor = {"mcpServers": {"pitchswitch": {"url": url, "headers": {
        "Authorization": f"Bearer {token}"}}}}
    return f"""PitchSwitch MCP server: {url}

Claude (claude.ai or Claude Desktop): Settings > Connectors > Add custom connector, paste this URL
  {url}?key={token}

Claude Code:
  claude mcp add --transport http pitchswitch {url} --header "Authorization: Bearer {token}"

Cursor (.cursor/mcp.json) and other clients that take a URL and headers:
  {json.dumps(cursor)}

Then ask: "Using only PitchSwitch: should Sensofusion pitch Rainfall Ventures?"
The token is a password: share it only with people who may use the server."""


if __name__ == "__main__":
    load_env()
    mode = sys.argv[1] if len(sys.argv) > 1 else "stdio"
    if mode == "http":
        host, port = os.environ.get("MCP_HOST", "0.0.0.0"), int(os.environ.get("MCP_PORT", "8001"))
        gated = TokenGate(server.streamable_http_app(host=host), _token())
        uvicorn.run(gated, host=host, port=port)
    elif mode == "setup":
        site = os.environ.get("SITE_ADDRESS", "").strip()
        default = f"https://{site}" if site and not site.startswith(":") else "http://localhost:8001"
        print(setup(sys.argv[2] if len(sys.argv) > 2 else default, _token()))
    elif mode == "stdio":
        server.run("stdio")
    else:
        sys.exit(f"unknown mode {mode!r}: use no argument (stdio), 'http' or 'setup [url]'")
