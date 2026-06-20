import { NextResponse } from "next/server";
import {
  callMCPTool,
  extractContextFromRequest,
  MCPBridge,
} from "@/lib/mcp/MCPBridge";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type PerformancePayload = {
  path?: unknown;
  metric?: unknown;
  duration?: unknown;
  timestamp?: unknown;
};

function toTrimmedString(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function parseDuration(value: unknown): number {
  if (typeof value === "number") {
    return value;
  }
  if (typeof value === "string" && value.trim().length > 0) {
    return Number(value);
  }
  return Number.NaN;
}

function parsePayload(body: PerformancePayload) {
  const path = toTrimmedString(body.path);
  const metric = toTrimmedString(body.metric);
  const duration = parseDuration(body.duration);
  const timestamp = toTrimmedString(body.timestamp);

  if (!path || !metric || !Number.isFinite(duration)) {
    throw new Error("path, metric, and numeric duration are required");
  }

  return {
    path,
    metric,
    duration,
    ...(timestamp ? { timestamp } : {}),
  };
}

export async function POST(req: Request) {
  try {
    const body = (await req.json().catch(() => ({}))) as PerformancePayload;
    const args = parsePayload(body);
    const mcpContext = extractContextFromRequest(req);
    const result = await callMCPTool(
      "save-performance-metric",
      args,
      mcpContext,
    );

    if (result.isError) {
      return NextResponse.json(
        {
          error:
            MCPBridge.extractText(result) || "Failed to save performance metric",
        },
        { status: 500 },
      );
    }

    const raw = MCPBridge.extractText(result).trim();
    if (!raw) {
      return NextResponse.json({ success: true });
    }

    try {
      return NextResponse.json(JSON.parse(raw));
    } catch {
      return NextResponse.json({ success: true, result: raw });
    }
  } catch (error) {
    const message =
      error instanceof Error
        ? error.message
        : "Invalid performance telemetry request";
    return NextResponse.json({ error: message }, { status: 400 });
  }
}
