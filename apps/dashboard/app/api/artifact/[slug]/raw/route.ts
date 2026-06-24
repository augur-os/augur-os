import { NextResponse } from "next/server";
import { readArtifactHtmlBySlug } from "@/lib/artifacts/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(_req: Request, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const html = await readArtifactHtmlBySlug(slug);
  if (html === null) return NextResponse.json({ error: "Artifact not found" }, { status: 404 });
  return new NextResponse(html, {
    headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "private, max-age=60", "X-Content-Type-Options": "nosniff" },
  });
}
