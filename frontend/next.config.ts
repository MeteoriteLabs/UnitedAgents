import type { NextConfig } from "next";

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8001';

const nextConfig: NextConfig = {
  allowedDevOrigins: ['*'],
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${BACKEND_URL}/api/:path*`,
      },
      {
        source: '/skill/:path*',
        destination: `${BACKEND_URL}/skill/:path*`,
      },
      {
        source: '/skill.md',
        destination: `${BACKEND_URL}/skill.md`,
      },
      {
        source: '/heartbeat.md',
        destination: `${BACKEND_URL}/heartbeat.md`,
      },
      {
        source: '/llms.txt',
        destination: `${BACKEND_URL}/llms.txt`,
      },
      {
        source: '/health',
        destination: `${BACKEND_URL}/health`,
      },
      {
        source: '/docs',
        destination: `${BACKEND_URL}/docs`,
      },
      {
        source: '/openapi.json',
        destination: `${BACKEND_URL}/openapi.json`,
      },
    ];
  },
};

export default nextConfig;
