import { ArtifactRouteClient } from "./ArtifactRouteClient";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export default async function ArtifactPage({
  params,
}: {
  params: Promise<{ slug: string }> | { slug: string };
}) {
  const { slug } = await params;
  return <ArtifactRouteClient slug={slug} />;
}
