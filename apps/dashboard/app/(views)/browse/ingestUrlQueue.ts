import type { NoteQueueItemData } from "@/features/browse/NoteQueueItem";

export interface UrlExtractResult {
  success: boolean;
  canonical_url?: string;
  title?: string;
  body?: string;
  content_hash?: string;
  error?: string;
}

export interface SaveUrlSourceResult {
  success: boolean;
  path?: string;
  sha256?: string;
  deduplicated?: boolean;
  canonical_url?: string;
  title?: string;
  error?: string;
}

export interface IngestUrlComposedResult {
  success: boolean;
  path?: string;
  title?: string;
  deduplicated?: boolean;
  error?: string;
}

export function completeUrlIngestQueueItem(
  item: NoteQueueItemData,
  jobId: string,
  result: IngestUrlComposedResult,
): NoteQueueItemData {
  if (item.jobId !== jobId) {
    return item;
  }

  if (result.success) {
    return {
      ...item,
      status: "completed",
      stage: result.deduplicated ? "deduplicated" : "saved",
      destination: result.path || "notes",
      name: result.title || item.name,
    };
  }

  return {
    ...item,
    status: "failed",
    error: result.error || "URL ingest failed",
  };
}
