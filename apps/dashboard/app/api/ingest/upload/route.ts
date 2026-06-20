import { NextRequest, NextResponse } from "next/server";
// eslint-disable-next-line no-restricted-imports -- @fs-exempt: ingest-infrastructure (file staging to state dir)
import { writeFile, mkdir } from "fs/promises";
import { join } from "path";
import { randomBytes } from "crypto";
import { AUGUR_STATE_DIR } from "@/lib/paths";

/**
 * POST /api/ingest/upload
 *
 * Receives file uploads from the dashboard drop zone / FAB modal.
 * Stages files to the ingest staging directory and returns job metadata.
 *
 * Note: This is a thin staging endpoint — it does NOT process files.
 * Processing happens when the agent calls ingest-process MCP tool.
 */
export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    const files = formData.getAll("files") as File[];

    if (files.length === 0) {
      return NextResponse.json(
        { success: false, error: "No files provided" },
        { status: 400 },
      );
    }

    const stagingBase = join(AUGUR_STATE_DIR, "ingest", "staging");

    const staged: Array<{
      jobId: string;
      name: string;
      path: string;
      size: number;
    }> = await Promise.all(files.map(async (file) => {
      const jobId = randomBytes(4).toString("hex");
      const jobDir = join(stagingBase, jobId);
      await mkdir(jobDir, { recursive: true });

      const buffer = Buffer.from(await file.arrayBuffer());
      const filePath = join(jobDir, file.name);
      await writeFile(filePath, buffer);

      return {
        jobId,
        name: file.name,
        path: filePath,
        size: buffer.length,
      };
    }));

    return NextResponse.json({
      success: true,
      staged,
      count: staged.length,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Upload failed";
    return NextResponse.json(
      { success: false, error: message },
      { status: 500 },
    );
  }
}
