/**
 * GET /api/blocks/catalog
 *
 * Exposes the generated block registry to dashboard clients that need to build
 * block picker/catalog UI without importing generated code directly.
 */

import { NextResponse } from "next/server";
import { BLOCK_LIST } from "@/lib/blocks/generated-block-registry";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(): Promise<Response> {
  return NextResponse.json(BLOCK_LIST);
}
