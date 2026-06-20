/**
 * /api/views/[id]/blocks/[instanceId] — Remove a block from a view
 *
 * DELETE /api/views/[id]/blocks/[instanceId]
 *
 * @fs-exempt: Views are dashboard-internal layout state, not plugin data.
 */

import { NextResponse } from "next/server";
import { ViewStorage } from "@/lib/blocks/view-storage";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const storage = new ViewStorage();

export async function DELETE(
  _req: Request,
  { params }: { params: Promise<{ id: string; instanceId: string }> },
): Promise<Response> {
  const { id, instanceId } = await params;
  const view = storage.removeBlock(id, instanceId);
  if (!view) {
    return NextResponse.json({ error: "View not found" }, { status: 404 });
  }
  return NextResponse.json(view);
}
