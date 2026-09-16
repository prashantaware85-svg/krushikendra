import { NextResponse } from "next/server";

/**
 * Frontend liveness probe.
 * GET /api/health -> { status: "ok", service: "krushi-seva-web", timestamp }
 * Dependency-free by design (never call the backend from here).
 */
export async function GET(): Promise<NextResponse> {
  return NextResponse.json(
    {
      status: "ok",
      service: "krushi-seva-web",
      timestamp: new Date().toISOString(),
    },
    { status: 200 },
  );
}
