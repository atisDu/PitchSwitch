# MCP demo: Pitchlist in Claude Desktop (task C13)

Goal: in the demo (step 7 of `docs/demo-script.md`), ask Claude Desktop *"Should Sensofusion pitch
Rainfall Ventures?"* and get a sourced answer through Pitchlist's MCP server.

Status, 14 Nov: **works in Claude Desktop** (checked by a person at the app, `notes/B.md`): the
server starts, lists its tools and answers the demo question with "skip, backs Stendr". Also checked
over stdio with the official MCP client: `check_conflict` for Rainfall Ventures × Sensofusion
returns the PORTFOLIO conflict via Stendr in about 2 s. Still open: Cala's own MCP server (step 3)
and a run on the demo laptop.

## 1. Before you start

- The repo is set up on the demo laptop: `.venv` with `pip install -e "backend[dev]"`, and the
  team's `.env` in the repo root (with `CALA_API_KEY`, `GEMINI_API_KEY`, `MONGODB_URI`).
- Claude Desktop is installed and signed in.
- Find the repo's absolute path: run `pwd` in the repo root. Below it is written `<repo>`.

## 2. Add Pitchlist to Claude Desktop (local, stdio)

Open Claude Desktop → Settings → Developer → **Edit Config**. That opens
`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS). Add Pitchlist under
`mcpServers` (keep any servers already there):

```json
{
  "mcpServers": {
    "pitchlist": {
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

Quit Claude Desktop completely (⌘Q) and open it again. In a new chat, the tools menu should list
**pitchlist** with seven tools: `resolve_company`, `find_competitors`, `get_rounds`,
`investor_profile`, `check_conflict`, `rank_investors`, `investor_brief`.

## 3. Add Cala's own MCP server (optional)

The plan (OVERVIEW.md) shows Pitchlist next to Cala's MCP server. Its connection details are not in
this repo; get them from Cala's docs or the mentors, add it as a second entry under `mcpServers`
(or under Settings → Connectors if it is a remote URL), and note it here:

- Cala MCP: _to fill in_

## 4. Test the demo question

**Turn web search off** in the chat first (or start the question with "Using only Pitchlist,").
In the first test Claude mixed its own web search into the answer: it named a co-lead our data
doesn't have and read the round size ("~$5M") as Rainfall's share.

Ask exactly: **"Using only Pitchlist, should Sensofusion pitch Rainfall Ventures?"**

What should happen (allow each tool call when Claude asks):

1. `resolve_company` for Sensofusion and for Rainfall Ventures (`kind: "investor"`).
2. `check_conflict` with both IDs → `PORTFOLIO` conflict: Rainfall backs **Stendr**, a direct
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
| No "pitchlist" in the tools menu | Check the JSON is valid and the path is absolute; quit Claude Desktop with ⌘Q (closing the window isn't enough). Logs: `~/Library/Logs/Claude/mcp*.log` |
| `No module named mcp_server` | The venv lacks the editable install: `<repo>/.venv/bin/pip install -e "<repo>/backend[dev]"` |
| Tools load but calls fail | `.env` missing or keys empty; run `cd <repo>/backend && ../.venv/bin/python -m data.smoke Sensofusion --real` to see which step fails |
| Very slow first answer | Nothing cached yet for that company; run the question once before the demo |
| Demo laptop has no repo | Use the deployed server instead (below) |

## Alternative: the deployed server (remote)

Once A17 deploys the stack, the same tools are served over streamable HTTP at
`https://<site>/mcp` (see `deploy/verda.md`). Add it in Claude Desktop under Settings → Connectors →
Add custom connector, with that URL. Note (from B15): the endpoint has **no authentication** yet,
so share the URL only for the demo.

Running the HTTP server locally: `cd backend && ../.venv/bin/python -m mcp_server.server http`
serves `http://localhost:8001/mcp`. That is the same port as the frontend mock (`npm run mock`), so
don't run both, or start the mock with `MOCK_PORT=8002`.
