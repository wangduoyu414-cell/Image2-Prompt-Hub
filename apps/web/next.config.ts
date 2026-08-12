import type { NextConfig } from "next";

function apiBaseUrl(): string {
  const configured = process.env.IMAGE2_API_INTERNAL_BASE_URL ?? "http://127.0.0.1:8000";
  const parsed = new URL(configured);
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    throw new Error("IMAGE2_API_INTERNAL_BASE_URL must use HTTP or HTTPS.");
  }
  return parsed.toString().replace(/\/$/, "");
}

function internalPreviewApiBaseUrl(): string {
  const configured = process.env.IMAGE2_INTERNAL_PREVIEW_API_BASE_URL ?? "http://127.0.0.1:8001";
  const parsed = new URL(configured);
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    throw new Error("IMAGE2_INTERNAL_PREVIEW_API_BASE_URL must use HTTP or HTTPS.");
  }
  return parsed.toString().replace(/\/$/, "");
}

function adminApiBaseUrl(): string {
  const configured = process.env.IMAGE2_ADMIN_API_BASE_URL ?? "http://127.0.0.1:8002";
  const parsed = new URL(configured);
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    throw new Error("IMAGE2_ADMIN_API_BASE_URL must use HTTP or HTTPS.");
  }
  return parsed.toString().replace(/\/$/, "");
}

const nextConfig: NextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/internal-preview-api/:path*",
        destination: `${internalPreviewApiBaseUrl()}/api/internal-preview/v1/:path*`,
      },
      {
        source: "/backend/:path*",
        destination: `${apiBaseUrl()}/api/v1/:path*`,
      },
      {
        source: "/backend-v2/:path*",
        destination: `${apiBaseUrl()}/api/v2/:path*`,
      },
      {
        source: "/admin-backend/:path*",
        destination: `${adminApiBaseUrl()}/api/admin/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
