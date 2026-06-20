import type { BrowseCardAction, BrowseItem } from "./types";

const MEDIA_EXTENSIONS = new Set([
  ".m4a",
  ".mp3",
  ".mp4",
  ".wav",
  ".webm",
  ".aac",
  ".flac",
  ".mov",
]);

const DECK_EXTENSIONS = new Set([
  ".ppt",
  ".pptx",
  ".key",
  ".pdf",
  ".png",
  ".jpg",
  ".jpeg",
  ".webp",
]);

const MARKDOWN_EXTENSIONS = new Set([".md", ".mdx", ".markdown"]);
const APPROVED_ARTIFACT_CATEGORIES = new Set(["documents", "vault"]);

function firstString(...values: unknown[]): string | undefined {
  for (const value of values) {
    if (typeof value !== "string") continue;
    const text = value.trim();
    if (text) return text;
  }
  return undefined;
}

function extensionFor(path: string): string {
  const cleanPath = path.split(/[?#]/, 1)[0] || path;
  const fileName = cleanPath.replace(/\\/g, "/").split("/").pop() || cleanPath;
  const match = fileName.match(/(\.[^.]+)$/);
  return match ? match[1].toLowerCase() : "";
}

function metadataValue(item: BrowseItem, ...keys: string[]): string | undefined {
  for (const key of keys) {
    const direct = firstString((item as unknown as Record<string, unknown>)[key]);
    if (direct) return direct;
    const fromMetadata = firstString(item.metadata?.[key]);
    if (fromMetadata) return fromMetadata;
  }
  return undefined;
}

function sourcePathFor(item: BrowseItem): string | undefined {
  return firstString(
    item.metadata?.source_path,
    item.metadata?.sourcePath,
    item.metadata?.path,
    item.path,
  );
}

function isApprovedArtifactCategory(category: string | undefined): boolean {
  return Boolean(category && APPROVED_ARTIFACT_CATEGORIES.has(category));
}

function isLocalArtifactPath(sourcePath: string): boolean {
  if (/^[a-z][a-z0-9+.-]*:\/\//i.test(sourcePath)) return false;
  return Boolean(
    /^[a-zA-Z]:[\\/]/.test(sourcePath)
      || sourcePath.startsWith("/")
      || sourcePath.startsWith("./")
      || sourcePath.startsWith("../"),
  );
}

function isMediaArtifact(item: BrowseItem, sourcePath: string): boolean {
  const extension = extensionFor(sourcePath);
  if (MEDIA_EXTENSIONS.has(extension)) return true;

  const mediaKind = metadataValue(item, "media_kind")?.toLowerCase();
  if (mediaKind === "audio" || mediaKind === "video") return true;

  const mediaType = metadataValue(item, "media_type")?.toLowerCase();
  return Boolean(
    mediaType === "audio"
      || mediaType === "video"
      || mediaType?.startsWith("audio/")
      || mediaType?.startsWith("video/"),
  );
}

function isDeckArtifact(item: BrowseItem, sourcePath: string): boolean {
  const extension = extensionFor(sourcePath);
  if (MARKDOWN_EXTENSIONS.has(extension)) return false;
  if (DECK_EXTENSIONS.has(extension)) return true;

  const documentKind = metadataValue(
    item,
    "document_kind",
    "documentKind",
    "kind",
    "artifact_kind",
    "artifactKind",
  )?.toLowerCase();
  return Boolean(
    documentKind?.includes("slide")
      || documentKind?.includes("deck")
      || documentKind?.includes("presentation"),
  );
}

function mediaActions(sourcePath: string, title: string): BrowseCardAction[] {
  const args = { source_path: sourcePath, title };
  return [
    {
      id: "demo-run-transcript",
      label: "Transcript",
      icon: "Mic",
      type: "mcp-tool",
      target: "demo-run-transcript",
      args,
    },
    {
      id: "demo-run-meeting-memory",
      label: "Meeting Memory",
      icon: "ClipboardCheck",
      type: "mcp-tool",
      target: "demo-run-meeting-memory",
      args,
    },
    {
      id: "demo-run-ask-transcript",
      label: "Ask From Transcript",
      icon: "MessageSquare",
      type: "mcp-tool",
      target: "demo-run-ask-transcript",
      args,
    },
  ];
}

function promptActions(sourcePath: string, title: string): BrowseCardAction[] {
  return [
    {
      id: "demo-run-claude-value",
      label: "Claude Value",
      icon: "Sparkles",
      type: "mcp-tool",
      target: "demo-run-prompt",
      args: {
        source_path: sourcePath,
        title,
        client: "claude",
        prompt_kind: "judge-value",
      },
    },
    {
      id: "demo-run-gemini-design",
      label: "Gemini Design",
      icon: "Palette",
      type: "mcp-tool",
      target: "demo-run-prompt",
      args: {
        source_path: sourcePath,
        title,
        client: "gemini",
        prompt_kind: "design",
      },
    },
    {
      id: "demo-run-technical-depth",
      label: "Technical Depth",
      icon: "Presentation",
      type: "mcp-tool",
      target: "demo-run-prompt",
      args: {
        source_path: sourcePath,
        title,
        client: "claude",
        prompt_kind: "technical-depth",
      },
    },
  ];
}

function appendMissingActions(
  existingActions: BrowseCardAction[] | undefined,
  demoActions: BrowseCardAction[],
): BrowseCardAction[] {
  const merged = [...(existingActions || [])];
  const existingIds = new Set(merged.map((action) => action.id));
  for (const action of demoActions) {
    if (existingIds.has(action.id)) continue;
    merged.push(action);
    existingIds.add(action.id);
  }
  return merged;
}

export function withDemoRunActions(item: BrowseItem, category?: string): BrowseItem {
  if (!isApprovedArtifactCategory(category)) return item;

  const sourcePath = sourcePathFor(item);
  if (!sourcePath) return item;
  if (!isLocalArtifactPath(sourcePath)) return item;

  const title = item.title || sourcePath.split(/[\\/]/).pop() || sourcePath;
  const demoActions = isMediaArtifact(item, sourcePath)
    ? mediaActions(sourcePath, title)
    : isDeckArtifact(item, sourcePath)
      ? promptActions(sourcePath, title)
      : [];

  if (demoActions.length === 0) return item;

  return {
    ...item,
    actions: appendMissingActions(item.actions, demoActions),
  };
}
