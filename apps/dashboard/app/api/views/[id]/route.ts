/**
 * /api/views/[id] — Single view CRUD (get, update, delete)
 *
 * GET    /api/views/[id]   — get a view by ID
 * PUT    /api/views/[id]   — update a view (title, blocks, layout, etc.)
 * DELETE /api/views/[id]   — delete a view
 *
 * @fs-exempt: Views are dashboard-internal layout state, not plugin data.
 */

import { NextResponse } from "next/server";
import { ViewStorage } from "@/lib/blocks/view-storage";
import { parseHubViewId } from "@/lib/blocks/utils";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const storage = new ViewStorage();

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> },
): Promise<Response> {
  const { id } = await params;
  const view = storage.get(id) ?? (parseHubViewId(id) ? storage.getOrCreateHubOverview(id) : null);
  if (!view) {
    return NextResponse.json({ error: "View not found" }, { status: 404 });
  }
  return NextResponse.json(view);
}

export async function PUT(
  req: Request,
  { params }: { params: Promise<{ id: string }> },
): Promise<Response> {
  const { id } = await params;
  let body: Record<string, unknown>;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const updated = storage.update(id, body);
  if (!updated) {
    return NextResponse.json({ error: "View not found" }, { status: 404 });
  }
  return NextResponse.json(updated);
}

export async function DELETE(
  _req: Request,
  { params }: { params: Promise<{ id: string }> },
): Promise<Response> {
  const { id } = await params;
  const deleted = storage.delete(id);
  if (!deleted) {
    return NextResponse.json({ error: "View not found" }, { status: 404 });
  }
  return NextResponse.json({ success: true });
}
