/**
 * /api/views/[id]/blocks — Add a block to a view
 *
 * POST /api/views/[id]/blocks — add a BlockInstance to the view
 *
 * @fs-exempt: Views are dashboard-internal layout state, not plugin data.
 */

import { NextResponse } from "next/server";
import { ViewStorage } from "@/lib/blocks/view-storage";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const storage = new ViewStorage();

export async function POST(
  req: Request,
  { params }: { params: Promise<{ id: string }> },
): Promise<Response> {
  const { id } = await params;
  let block: { instanceId: string; blockId: string; config: Record<string, unknown>; position: { x: number; y: number; w: number; h: number } };
  try {
    block = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  if (!block.instanceId || !block.blockId) {
    return NextResponse.json(
      { error: "Missing required fields: instanceId, blockId" },
      { status: 400 },
    );
  }

  const view = storage.addBlock(id, block);
  if (!view) {
    return NextResponse.json({ error: "View not found" }, { status: 404 });
  }
  return NextResponse.json(view);
}
