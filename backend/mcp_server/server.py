"""Pitchlist MCP server (B15): the §5.4 tools for any MCP client (Claude Desktop, Cursor).

Thin by design: the tools are the functions in agent/tools.py, the same ones the Gemini agent
calls. Each takes entity IDs and returns contract models as JSON, sources attached.

    python -m mcp_server.server           stdio, for Claude Desktop / Cursor
    python -m mcp_server.server http      streamable HTTP on $MCP_HOST:$MCP_PORT/mcp (0.0.0.0:8001)

Reads the repo's .env like the API does (USE_FAKE_STORE, CALA_API_KEY, GEMINI_API_KEY, ...).
"""

from __future__ import annotations

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

INSTRUCTIONS = """Pitchlist tells a startup founder which investors to pitch and which to skip, \
from Cala's sourced data. An investor has a conflict when it backs a direct competitor of the \
company (or one of its people sits on that competitor's board).
Start with resolve_company (kind "company" or "investor") to turn names into IDs; every other \
tool takes those IDs. For "should I pitch fund X?" call check_conflict, or investor_brief for a \
cited one-page answer. For "who should I pitch?" call rank_investors.
Every fact carries `sources` (name, url, date, rank): cite them, and state nothing about \
funding, investors or dates that the tools did not return."""



def _told(fn: Callable) -> Callable:
    """The tool, with the failures we expect (unknown ID, Cala or Gemini unavailable) told to the
    client in words. Without this the SDK treats them as crashes and withholds the reason."""

    @functools.wraps(fn)
    async def tool(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except (DataError, LLMError) as exc:
            raise ToolError(str(exc) or type(exc).__name__) from exc

    return tool


server = MCPServer("pitchlist", instructions=INSTRUCTIONS)
for _tool in tools.MCP_TOOLS:
    server.add_tool(_told(_tool))  # name, description and schema come from the function itself


if __name__ == "__main__":
    load_env()
    if "http" in sys.argv[1:]:
        host, port = os.environ.get("MCP_HOST", "0.0.0.0"), int(os.environ.get("MCP_PORT", "8001"))
        server.run("streamable-http", host=host, port=port)
    else:
        server.run("stdio")
