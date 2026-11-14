import type { Metadata } from "next";
import Link from "next/link";

// The MCP setup page. It lives at /agents, not /mcp: on the deployed site Caddy sends every /mcp*
// path to the MCP server itself (deploy/Caddyfile), so a page there would never load.

export const metadata: Metadata = {
  title: "Use PitchSwitch in your agent · PitchSwitch",
  description: "Connect PitchSwitch's MCP server to Claude, Claude Code or Cursor in three steps.",
};

// shortcut: the one deployed server, written out; read it from an env variable once there are more.
const MCP_URL = "https://95-133-252-219.sslip.io/mcp";

const TOOLS: [string, string][] = [
  ["resolve_company", "Finds a company or a fund by name"],
  ["find_competitors", "A company's direct competitors"],
  ["get_rounds", "A company's funding rounds and who backed them"],
  ["investor_profile", "A fund's rounds and portfolio"],
  ["check_conflict", "Whether a fund backed one of a company's competitors"],
  ["rank_investors", "The Pitch and Skip lists for a company"],
  ["investor_brief", "A one-page brief on a fund for a company"],
];

const CURSOR = JSON.stringify(
  { mcpServers: { pitchswitch: { url: MCP_URL, headers: { Authorization: "Bearer <token>" } } } },
  null,
  2,
);

function Code({ children }: { children: string }) {
  return (
    <pre className="mt-3 rounded-xl bg-press p-4 font-mono text-[13px] leading-relaxed whitespace-pre-wrap text-[#e6eef0] [overflow-wrap:anywhere]">
      <code>{children}</code>
    </pre>
  );
}

function Client({ name, how, children }: { name: string; how: string; children: string }) {
  return (
    <div className="grid min-w-0 gap-x-8 py-5 first:pt-0 last:pb-0 lg:grid-cols-[15rem_minmax(0,1fr)]">
      <div>
        <h3 className="font-medium">{name}</h3>
        <p className="mt-1 text-sm text-muted">{how}</p>
      </div>
      <div className="min-w-0 lg:[&>pre]:mt-0">
        <Code>{children}</Code>
      </div>
    </div>
  );
}

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <li className="window grid grid-cols-[2.5rem_minmax(0,1fr)] gap-x-4 p-5 md:grid-cols-[3.5rem_minmax(0,1fr)] md:p-8">
      <span className="display text-3xl text-accent md:text-4xl" aria-hidden="true">
        {n}
      </span>
      <div className="min-w-0">
        <h2 className="text-xl font-medium tracking-[-0.01em] md:text-2xl">{title}</h2>
        {children}
      </div>
    </li>
  );
}

export default function AgentsPage() {
  return (
    <div>
      <p className="inline-flex h-8 items-center rounded-full border border-line bg-white px-3 text-[13px] text-muted">
        MCP server
      </p>
      <h1 className="display mt-5 max-w-4xl text-5xl sm:text-6xl md:text-7xl">Ask PitchSwitch from your own agent</h1>
      <p className="mt-6 max-w-2xl text-lg leading-snug text-muted">
        The same checks as the app, as seven tools for Claude, Claude Code or Cursor. Ask &ldquo;Should we pitch this
        fund?&rdquo; in the middle of your work and get the answer with its sources.
      </p>

      <ol className="mt-12 grid gap-3">
        <Step n={1} title="Get an access token">
          <p className="mt-2 max-w-2xl text-muted">
            Ask the PitchSwitch team for one. It works like a password, so keep it out of shared files. Below it is
            written <code className="rounded bg-surface px-1 font-mono text-sm text-foreground">&lt;token&gt;</code>.
          </p>
        </Step>

        <Step n={2} title="Add the server to your client">
          <div className="mt-4 divide-y divide-line">
            <Client name="Claude or Claude Desktop" how="Settings → Connectors → Add custom connector, then paste:">
              {`${MCP_URL}?key=<token>`}
            </Client>
            <Client name="Claude Code" how="Run once in a terminal:">
              {`claude mcp add --transport http pitchswitch ${MCP_URL} --header "Authorization: Bearer <token>"`}
            </Client>
            <Client name="Cursor" how="Add to .cursor/mcp.json:">
              {CURSOR}
            </Client>
          </div>
        </Step>

        <Step n={3} title="Ask a question">
          <p className="mt-2 max-w-2xl text-muted">
            Start with &ldquo;Using only PitchSwitch&rdquo; so the agent doesn&apos;t mix in a web search:
          </p>
          <Code>{"Using only PitchSwitch: should <your company> pitch <the fund>?"}</Code>
          <p className="mt-3 max-w-2xl text-sm text-muted">
            The first question about a company nobody has asked about can take a minute. If the agent hears
            &ldquo;Still working, call again&rdquo;, it retries by itself.
          </p>
        </Step>
      </ol>

      <section className="mt-20" aria-labelledby="tools-heading">
        <h2 id="tools-heading" className="display text-4xl md:text-5xl">
          The seven tools
        </h2>
        <p className="mt-4 max-w-2xl text-muted">
          Each takes Cala IDs (find them with <span className="font-mono text-sm">resolve_company</span>) and returns
          the same data the app shows, sources included.
        </p>
        <dl className="window mt-8 divide-y divide-line px-5 md:px-8">
          {TOOLS.map(([name, what]) => (
            <div key={name} className="grid gap-1 py-4 sm:grid-cols-[14rem_minmax(0,1fr)] sm:gap-6">
              <dt className="font-mono text-sm">{name}</dt>
              <dd className="text-muted">{what}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="lit-ground mt-20 rounded-[20px] px-6 py-12 md:px-12 md:py-16" aria-label="Next step">
        <p className="display text-4xl md:text-5xl">Rather click than type?</p>
        <p className="mt-3 max-w-xl text-foreground/80">The app runs the same checks in the browser.</p>
        <Link href="/start" className="btn-primary mt-6">
          Run a check
        </Link>
      </section>
    </div>
  );
}
