import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Allow cross-origin requests from local network IPs in development
  allowedDevOrigins: ["192.168.0.107"],
};

export default nextConfig;
