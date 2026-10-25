import type { NextConfig } from "next";

const worker = (process.env.WORKER_URL || "http://localhost:8000").replace(/\/$/, "");

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
  // The bundled snapshot is read from disk at runtime for offline demo mode.
  outputFileTracingIncludes: {
    "/**": ["./demo-data/**"],
  },
  async rewrites() {
    // Checked after public files: demo media bundled in public/media wins,
    // everything else (live frames, videos, uploads) is proxied to the worker.
    return [
      { source: "/media/:path*", destination: `${worker}/media/:path*` },
      { source: "/worker/:path*", destination: `${worker}/:path*` },
    ];
  },
};

export default nextConfig;
