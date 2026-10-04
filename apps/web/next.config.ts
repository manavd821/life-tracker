import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Do not auto-generate AGENTS.md / CLAUDE.md into the repository.
  agentRules: false,
};

export default nextConfig;
