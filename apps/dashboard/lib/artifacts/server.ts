import { MCPBridge } from "@/lib/mcp/connection";
import { callCoreTool } from "@/lib/mcp/helpers";
import { injectAugurBridge } from "@/lib/artifacts/injectBridge";
import type { ArtifactEntry } from "@/lib/browse/pages-merge";

export async function getArtifactBySlug(slug: string): Promise<ArtifactEntry | null> {
  const res = await callCoreTool("artifact-resolve", { slug });
  const data = MCPBridge.parseJSON<{ found?: boolean; path?: string } & Partial<ArtifactEntry>>(res);
  if (!data.found) return null;
  // Strip server-side fields before the object crosses to the client
  const { found: _found, path: _path, ...artifact } = data;
  return artifact as ArtifactEntry;
}

export async function readArtifactHtmlBySlug(slug: string): Promise<string | null> {
  const res = await callCoreTool("artifact-html", { slug });
  const data = MCPBridge.parseJSON<{ found?: boolean; content?: string }>(res);
  if (!data.found || typeof data.content !== "string") return null;
  return injectAugurBridge(data.content);
}
