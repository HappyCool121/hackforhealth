import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  turbopack: { root: process.cwd() },
  async rewrites() {
    if (!process.env.API_INTERNAL_URL) return [];
    return [{ source: "/api/:path*", destination: `${process.env.API_INTERNAL_URL}/api/:path*` }];
  },
};

export default nextConfig;
