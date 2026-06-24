import { NextResponse } from "next/server";
import { getArtifactBySlug } from "@/lib/artifacts/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(_req: Request, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const artifact = await getArtifactBySlug(slug);
  // Return 200 with found:false (not 404) for a missing artifact. A 404 here is an
  // expected state (unknown slug → graceful "Artifact not found" UI), but the browser
  // logs every non-2xx fetch as a console error on page load. The sole consumer reads
  // the `found` field, so a soft-404 keeps the UX and removes the console noise.
  if (!artifact) return NextResponse.json({ found: false });
  const { path: _omit, ...safe } = artifact;
  return NextResponse.json({ found: true, artifact: safe });
}
