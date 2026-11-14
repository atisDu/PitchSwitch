# MCP demo: PitchSwitch in Claude Desktop (task C13)

Goal: in the demo (step 7 of `docs/demo-script.md`), ask Claude Desktop *"Should Sensofusion pitch
Skyfall Ventures?"* and get a sourced answer through PitchSwitch's MCP server.

Status, 14 Nov: PitchSwitch over stdio **works in Claude Desktop** (checked by a person at the app, `notes/B.md`): the
server starts, lists its tools and answers the demo question with "skip, backs Stendr". Also checked
over stdio with the official MCP client: `check_conflict` for Rainfall Ventures × Sensofusion
returns the PORTFOLIO conflict via Stendr in about 2 s. Left for demo day: run the question once on
the demo laptop (it warms the cache). The deployed server's `/mcp` endpoint also works (token
required; last section).

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

The same tools are served over streamable HTTP at **`https://95-133-252-219.sslip.io/mcp`**, behind a
token (`MCP_TOKEN`): 401 without it, 200 with it. Checked on 14 Nov through the live site with the
MCP SDK client and with Claude Code (`notes/B.md`): 7 tools, the demo question answers with the
Stendr conflict in about 10 s.

**Get the token from a teammate privately**, like the other keys; it is a password. These docs
write it as `<token>`; never paste the real one into the repo. Then print the ready-to-paste setup
(run from `backend/` on a machine whose `.env` has `MCP_TOKEN`; it fills the token in):

```sh
../.venv/bin/python -m mcp_server.server setup https://95-133-252-219.sslip.io
```

Which form to use:

- **Claude Code and Cursor:** the header form (`Authorization: Bearer <token>`), as `setup` prints it.
- **Claude Desktop / claude.ai custom connector** (Settings → Connectors → Add custom connector):
  that screen has no header field, so use the URL form
  `https://95-133-252-219.sslip.io/mcp?key=<token>`. Not tried at the app yet.

| Symptom | Meaning |
| --- | --- |
| Claude Code says "Dynamic Client Registration … 404" | The token is missing or wrong. After the 401 Claude Code tries OAuth by itself, which our server doesn't offer; nothing is broken on the server |
| "Still working, call again" | A company nobody asked about before; the client retries and the work finishes (up to a minute). The three demo companies answer in about 10 s |
| 401 "missing or wrong token" (other clients) | As it says: check the header or `?key=` |

Running the HTTP server locally: `MCP_TOKEN=<token> ../.venv/bin/python -m mcp_server.server http`
(from `backend/`) serves `http://localhost:8001/mcp`. That is the same port as the frontend mock
(`npm run mock`), so don't run both, or start the mock with `MOCK_PORT=8002`.
