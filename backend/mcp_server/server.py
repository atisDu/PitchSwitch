"""PitchSwitch MCP server (B15): the §5.4 tools for any MCP client (Claude Desktop, Cursor).

Thin by design: the tools are the functions in agent/tools.py, the same ones the Gemini agent
calls. Each takes entity IDs and returns contract models as JSON, sources attached.

    python -m mcp_server.server           stdio, for Claude Desktop / Cursor
    python -m mcp_server.server http      streamable HTTP on $MCP_HOST:$MCP_PORT/mcp (0.0.0.0:8001)

Reads the repo's .env like the API does (USE_FAKE_STORE, CALA_API_KEY, GEMINI_API_KEY, ...).

Behind a reverse proxy keep MCP_HOST=0.0.0.0: bound to 127.0.0.1 the SDK only accepts requests
whose Host header is localhost and answers the site's own hostname with 421.
ponytail: no auth; anyone who knows the URL can call the tools. Add a token check before this
is public for longer than a demo.
"""

from __future__ import annotations

import asyncio
import functools
import os
import sys
from collections.abc import Callable

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

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


if __name__ == "__main__":
    load_env()
    if "http" in sys.argv[1:]:
        host, port = os.environ.get("MCP_HOST", "0.0.0.0"), int(os.environ.get("MCP_PORT", "8001"))
        server.run("streamable-http", host=host, port=port)
    else:
        server.run("stdio")
