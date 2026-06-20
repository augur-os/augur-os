import { randomBytes } from "crypto";
// eslint-disable-next-line no-restricted-imports -- @fs-exempt: chat attachment staging requires server-side file writes
import { mkdir, writeFile } from "fs/promises";
import { basename, join } from "path";
import { NextRequest, NextResponse } from "next/server";
import { AUGUR_STATE_DIR } from "@/lib/paths";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function POST(request: NextRequest) {
  const isRemote = request.headers.get("x-remote-user") === "true";
  if (isRemote) {
    return NextResponse.json(
      {
        error:
          "Chat file upload is not available for remote access. Upload files from a local Augur session instead.",
        code: "REMOTE_BLOCKED",
      },
      { status: 403 },
    );
  }

  try {
    const formData = await request.formData();
    const file = formData.get("file");

    if (!(file instanceof File)) {
      return NextResponse.json(
        { error: "No file provided" },
        { status: 400 },
      );
    }

    const safeName = basename(file.name || "attachment");
    const attachmentId = randomBytes(8).toString("hex");
    const stagingDir = join(AUGUR_STATE_DIR, "chat", "attachments", attachmentId);
    await mkdir(stagingDir, { recursive: true });

    const buffer = Buffer.from(await file.arrayBuffer());
    const stagedPath = join(stagingDir, safeName);
    await writeFile(stagedPath, buffer);

    return NextResponse.json({
      success: true,
      originalName: safeName,
      stagedPath,
      size: buffer.length,
      mimeType: file.type || "application/octet-stream",
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Upload failed";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
