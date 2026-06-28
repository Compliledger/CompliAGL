import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Disable source maps in production to protect code
  productionBrowserSourceMaps: false,
};

export default nextConfig;
