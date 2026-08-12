export const dynamic = "force-dynamic";

function serviceUrl(name: "api" | "admin"): string {
  const value = name === "api"
    ? process.env.IMAGE2_API_INTERNAL_BASE_URL ?? "http://127.0.0.1:8000"
    : process.env.IMAGE2_ADMIN_API_BASE_URL ?? "http://127.0.0.1:8002";
  const parsed = new URL(value);
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    throw new Error("invalid internal service URL");
  }
  return parsed.toString().replace(/\/$/, "");
}

async function ready(name: "api" | "admin"): Promise<string> {
  const response = await fetch(`${serviceUrl(name)}/readyz`, {
    cache: "no-store",
    headers: { Accept: "application/json" },
    signal: AbortSignal.timeout(5_000),
  });
  if (!response.ok) throw new Error(`${name} is not ready`);
  const payload: unknown = await response.json();
  if (typeof payload !== "object" || payload === null || (payload as { status?: unknown }).status !== "ready") {
    throw new Error(`${name} returned an invalid readiness response`);
  }
  const state = (payload as { state?: unknown }).state;
  return typeof state === "string" ? state : "ready";
}

export async function GET(): Promise<Response> {
  try {
    const [api, admin] = await Promise.all([ready("api"), ready("admin")]);
    return Response.json(
      { status: "ready", components: { api, admin } },
      { headers: { "Cache-Control": "no-store" } },
    );
  } catch {
    return Response.json(
      { status: "unavailable" },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }
}

