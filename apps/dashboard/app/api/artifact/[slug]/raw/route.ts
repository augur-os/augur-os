import { NextResponse } from "next/server";
import { getArtifactBySlug, readArtifactHtml } from "@/lib/artifacts/server";
import { injectAugurBridge } from "@/lib/artifacts/injectBridge";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(
  _request: Request,
  { params }: { params: { slug: string } },
) {
  const { slug } = await params;
  const artifact = await getArtifactBySlug(slug);
  if (!artifact) {
    return NextResponse.json({ error: "Artifact not found" }, { status: 404 });
  }

  try {
    const html = await readArtifactHtml(artifact.path);
    const withBridge = injectAugurBridge(html);
    return new NextResponse(withBridge, {
      headers: {
        "Content-Type": "text/html; charset=utf-8",
        "Cache-Control": "private, max-age=60",
        "X-Content-Type-Options": "nosniff",
      },
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Failed to read artifact";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
