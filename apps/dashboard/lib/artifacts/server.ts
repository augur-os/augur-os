import { callMCPTool, MCPBridge } from "@/lib/mcp/MCPBridge";
import { normalizeArtifactSlug } from "@/lib/artifacts/slug";
import type { ArtifactEntry } from "@/lib/browse/pages-merge";

interface ArtifactsListResponse {
  artifacts?: ArtifactEntry[];
}

interface FileReadResponse {
  status?: string;
  content?: string;
  content_base64?: string;
  message?: string;
}

function parseToolJson<T>(tool: string, result: Awaited<ReturnType<typeof callMCPTool>>): T {
  if (result.isError) {
    throw new Error(MCPBridge.extractText(result) || `${tool} failed`);
  }
  return MCPBridge.parseJSON<T>(result);
}

async function listArtifacts(): Promise<ArtifactEntry[]> {
  const result = await callMCPTool("artifacts-list", {});
  const parsed = parseToolJson<ArtifactsListResponse>("artifacts-list", result);
  return Array.isArray(parsed.artifacts) ? parsed.artifacts : [];
}

export async function getArtifactBySlug(slug: string): Promise<ArtifactEntry | null> {
  const normalized = normalizeArtifactSlug(slug);
  if (!normalized) return null;
  const artifacts = await listArtifacts();
  return artifacts.find((artifact) => artifact.slug === normalized) ?? null;
}

export async function readArtifactHtml(path: string): Promise<string> {
  const result = await callMCPTool("file-read", {
    path,
    binary: true,
  });
  const parsed = parseToolJson<FileReadResponse>("file-read", result);
  if (parsed.status !== "success") {
    throw new Error(parsed.message || "Artifact file read failed");
  }
  if (parsed.content_base64) {
    return Buffer.from(parsed.content_base64, "base64").toString("utf8");
  }
  return parsed.content ?? "";
}
