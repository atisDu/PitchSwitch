import type { NextConfig } from "next";

// The repo keeps one .env at the root (CLAUDE.md → Setup). Load it for API_URL
// unless the variable is already set; a missing file is fine.
if (!process.env.API_URL) {
  try {
    process.loadEnvFile("../.env");
  } catch {
    // no root .env; fall back to the default below
  }
}

const API_URL = (process.env.API_URL ?? "http://localhost:8000").split("#")[0].trim().replace(/\/+$/, "");
process.env.API_URL = API_URL;

const nextConfig: NextConfig = {
  cacheComponents: true,
  experimental: {
    // The /api/* rewrite gives up after 30 s by default. A cold founder report can take
    // many minutes (notes/B.md: Stendr cold = 213 Cala calls, 21 min), so allow 30 min.
    proxyTimeout: 30 * 60 * 1000,
  },
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  // Browser calls same-origin /api/*; this forwards them to B's server or C's mock
  // (no CORS, and switching backends is just API_URL).
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${API_URL}/api/:path*` },
      // The landing page is a static page built with the taste skill's kit (public/about.html,
      // public/assets/), outside the app's Tailwind layout so the two systems never mix. It is the
      // home page; the search form is at /start. /about stays for links already shared.
      { source: "/", destination: "/about.html" },
      { source: "/about", destination: "/about.html" },
    ];
  },
};

export default nextConfig;
