import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type PulseMode = "quick" | "deep";

type ProbeResult = {
  endpoint: string;
  ok: boolean;
  status: number;
  latencyMs: number;
};

const QUICK_ENDPOINTS = [
  "/api/activity/summary",
  "/api/agents/available?mode=api",
];

const DEEP_ENDPOINTS = [
  "/api/activity/summary",
  "/api/agents/available?mode=api",
];

async function runProbe(
  origin: string,
  endpoint: string,
): Promise<ProbeResult> {
  const started = Date.now();
  try {
    const response = await fetch(`${origin}${endpoint}`, {
      method: "GET",
      cache: "no-store",
    });

    return {
      endpoint,
      ok: response.ok,
      status: response.status,
      latencyMs: Date.now() - started,
    };
  } catch {
    return {
      endpoint,
      ok: false,
      status: 0,
      latencyMs: Date.now() - started,
    };
  }
}

async function runMode(request: NextRequest, mode: PulseMode) {
  const origin = new URL(request.url).origin;
  const endpoints = mode === "quick" ? QUICK_ENDPOINTS : DEEP_ENDPOINTS;

  const probes = await Promise.all(
    endpoints.map((endpoint) => runProbe(origin, endpoint)),
  );

  const healthy = probes.filter((probe) => probe.ok).length;
  const avgLatency =
    probes.length > 0
      ? Math.round(
          probes.reduce((sum, probe) => sum + probe.latencyMs, 0) /
            probes.length,
        )
      : 0;

  return {
    success: true,
    mode,
    healthy,
    total: probes.length,
    avgLatency,
    probes,
    generatedAt: new Date().toISOString(),
  };
}

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const mode = (searchParams.get("mode") ?? "quick") as PulseMode;
    const normalized: PulseMode = mode === "deep" ? "deep" : "quick";

    return NextResponse.json(await runMode(request, normalized));
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json(
      { success: false, error: message },
      { status: 500 },
    );
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = (await request.json().catch(() => ({}))) as {
      mode?: PulseMode;
    };
    const mode = body.mode === "deep" ? "deep" : "quick";

    return NextResponse.json(await runMode(request, mode));
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json(
      { success: false, error: message },
      { status: 500 },
    );
  }
}
