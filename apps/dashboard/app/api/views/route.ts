/**
 * /api/views — View CRUD (list + create)
 *
 * GET  /api/views         — list all views
 * POST /api/views         — create a new view
 *
 * Views are dashboard-internal state (grid layouts, block positions)
 * stored in AUGUR_STATE_DIR/views/ as YAML files.
 * @fs-exempt: Views are dashboard-internal layout state, not plugin data.
 */

import { NextResponse } from "next/server";
import { ViewStorage } from "@/lib/blocks/view-storage";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const storage = new ViewStorage();

export async function GET(): Promise<Response> {
  const views = storage.list();
  return NextResponse.json(views);
}

export async function POST(req: Request): Promise<Response> {
  let body: { id?: string; title?: string; pinned?: boolean; icon?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json(
      { error: "Invalid JSON body" },
      { status: 400 },
    );
  }

  if (!body.title || typeof body.title !== "string") {
    return NextResponse.json(
      { error: "Missing required field: title" },
      { status: 400 },
    );
  }

  const view = storage.create({
    id: body.id,
    title: body.title,
    pinned: body.pinned,
    icon: body.icon,
  });
  return NextResponse.json(view, { status: 201 });
}
