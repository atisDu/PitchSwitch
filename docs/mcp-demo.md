# MCP demo: PitchSwitch in Claude Desktop (task C13)

Goal: in the demo (step 7 of `docs/demo-script.md`), ask Claude Desktop *"Should Sensofusion pitch
Skyfall Ventures?"* and get a sourced answer through PitchSwitch's MCP server.

Status, 14 Nov: PitchSwitch over stdio **works in Claude Desktop** (checked by a person at the app, `notes/B.md`): the
server starts, lists its tools and answers the demo question with "skip, backs Stendr". Also checked
over stdio with the official MCP client: `check_conflict` for Rainfall Ventures × Sensofusion
returns the PORTFOLIO conflict via Stendr in about 2 s. Left for demo day: run the question once on
the demo laptop (it warms the cache). The deployed `/mcp`
endpoint is **down** (502, see the last section).

## 1. Before you start

- The repo is set up on the demo laptop: `.venv` with `pip install -e "backend[dev]"`, and the
  team's `.env` in the repo root (with `CALA_API_KEY`, `GEMINI_API_KEY`, `MONGODB_URI`).
- Claude Desktop is installed and signed in.
- Find the repo's absolute path: run `pwd` in the repo root. Below it is written `<repo>`.

## 2. Add PitchSwitch to Claude Desktop (local, stdio)

Open Claude Desktop → Settings → Developer → **Edit Config**. That opens
`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS). Add PitchSwitch under
`mcpServers` (keep any servers already there):

```json
{
  "mcpServers": {
    "pitchswitch": {
      "command": "<repo>/.venv/bin/python",
      "args": ["-m", "mcp_server.server"],
      "env": { "USE_FAKE_STORE": "false" }
    }
  }
}
```

- **`mcpServers` must be a top-level key** of the file, next to (not inside) `preferences`. Pasted
  at the end of the file it can land inside `preferences`: the app then ignores it **without an
  error** and Claude answers from web search instead.
- `<repo>` must be the full path (no `~`). The server reads `.env` from the repo root by itself.
- `USE_FAKE_STORE: "false"` means live Cala data through the shared Atlas cache (fast once warm).
  Use `"true"` to run on the recorded fixtures with no keys (different data from the demo script).

The key (`pitchswitch`) is the name Claude Desktop shows for the server. An older config with the
key `pitchlist` (the earlier working name) still works; it only shows the old name.

Quit Claude Desktop completely (⌘Q) and open it again. In a new chat, the tools menu should list
**pitchswitch** with seven tools: `resolve_company`, `find_competitors`, `get_rounds`,
`investor_profile`, `check_conflict`, `rank_investors`, `investor_brief`.

## 3. Only PitchSwitch's MCP server

We provide our own MCP server for agents and don't use Cala's MCP server in the demo (team
decision, 14 Nov). PitchSwitch's tools already sit on top of Cala and return Cala's sources with
every answer, so an agent needs only `pitchswitch`.

## 4. Test the demo question

**Turn web search off** in the chat first (or start the question with "Using only PitchSwitch,").
In the first test Claude mixed its own web search into the answer: it named a co-lead our data
doesn't have and read the round size ("~$5M") as Rainfall's share.

Ask exactly: **"Using only PitchSwitch, should Sensofusion pitch Skyfall Ventures?"**
(Tested in Claude Desktop with Rainfall Ventures, which also backs Stendr; the demo now uses
Skyfall because it sits higher on the live Skip list.)

**Ask every demo question once before the demo.** A first question about a company nobody has asked
about can take a minute or two. Slow tools answer "Still working … call again" within 50 s instead
of timing out, and Claude retries; the retry joins the same work, and once done it's cached
(an 80 s brief came back in 0.2 s the second time).

What should happen (allow each tool call when Claude asks):

1. `resolve_company` for Sensofusion and for Skyfall Ventures (`kind: "investor"`).
2. `check_conflict` with both IDs → `PORTFOLIO` conflict: Skyfall backs **Stendr**, a direct
   competitor, with sources.
3. Claude answers "no, skip them" and cites the sources.

Good follow-ups if there is time: *"Who should Sensofusion pitch instead?"* (`rank_investors`;
Maki.vc should lead), *"Write me a one-page brief on Maki.vc for Sensofusion"* (`investor_brief`,
about 30 s).

Record the result here:

- Date / laptop:
- Tools called:
- Answer (first sentence):
- Time to answer:
- Problems:

## 5. If something goes wrong

| Symptom | Fix |
| --- | --- |
| Claude answers from the web, no tool calls | `mcpServers` ended up inside `preferences`: move it to the top level, then ⌘Q and reopen |
| No "pitchswitch" in the tools menu | Check the JSON is valid and the path is absolute; quit Claude Desktop with ⌘Q (closing the window isn't enough). Logs: `~/Library/Logs/Claude/mcp*.log` |
| `No module named mcp_server` | The venv lacks the editable install: `<repo>/.venv/bin/pip install -e "<repo>/backend[dev]"` |
| Tools load but calls fail | `.env` missing or keys empty; run `cd <repo>/backend && ../.venv/bin/python -m data.smoke Sensofusion --real` to see which step fails |
| Very slow first answer, or "Still working, call again" | Nothing cached yet for that company; let Claude retry, and run each demo question once before the demo |
| Demo laptop has no repo | Use the deployed server instead (below) |

## Alternative: the deployed server (remote)

The same tools are served over streamable HTTP at `https://95-133-252-219.sslip.io/mcp`
(see `deploy/verda.md`). **On 14 Nov it answered 502**: the `mcp` container isn't running, most
likely because the server's `.env` has no `MCP_TOKEN` (`notes/B.md`; A's fix). Until then, use the
local stdio setup above. Over HTTP the server **needs a token** (`MCP_TOKEN` in the server's
`.env`, 16+ characters): without it every request gets 401.

Get the ready-to-paste client setup from the repo (it reads `MCP_TOKEN` from `.env`):

```sh
cd <repo>/backend && ../.venv/bin/python -m mcp_server.server setup https://<site>
```

It prints the lines for Claude (custom connector URL, Settings → Connectors → Add custom connector),
Claude Code and Cursor. The token goes in an `Authorization: Bearer` header, or as `?key=<token>` in
the URL for clients that only take a URL (then it can show up in server logs; share that URL only
with the team). Checked with Claude Code over HTTP (header and URL key both connect, no token is
refused); Claude's custom-connector screen and Cursor are not tried yet.

Running the HTTP server locally: `MCP_TOKEN=<token> ../.venv/bin/python -m mcp_server.server http`
(from `backend/`) serves `http://localhost:8001/mcp`. That is the same port as the frontend mock
(`npm run mock`), so don't run both, or start the mock with `MOCK_PORT=8002`.
