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
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
};

export default nextConfig;
