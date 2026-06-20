import type { NoteQueueItemData } from "@/features/browse/NoteQueueItem";

import { completeUrlIngestQueueItem } from "../../../apps/dashboard/app/(views)/browse/ingestUrlQueue";

describe("ingestUrlQueue", () => {
  test("completeUrlIngestQueueItem marks a matching item as saved", () => {
    const item: NoteQueueItemData = {
      jobId: "job-1",
      name: "Example URL",
      status: "pending",
      stage: "queued",
    };

    expect(
      completeUrlIngestQueueItem(item, "job-1", {
        success: true,
        path: "notes/2026-05-16-url-example.md",
        title: "Saved title",
      }),
    ).toEqual({
      jobId: "job-1",
      name: "Saved title",
      status: "completed",
      stage: "saved",
      destination: "notes/2026-05-16-url-example.md",
    });
  });

  test("completeUrlIngestQueueItem falls back to the notes zone when success omits a path", () => {
    const item: NoteQueueItemData = {
      jobId: "job-1",
      name: "Example URL",
      status: "pending",
      stage: "queued",
    };

    expect(
      completeUrlIngestQueueItem(item, "job-1", {
        success: true,
        title: "Saved title",
      }),
    ).toEqual({
      jobId: "job-1",
      name: "Saved title",
      status: "completed",
      stage: "saved",
      destination: "notes",
    });
  });

  test("completeUrlIngestQueueItem marks a matching item as failed", () => {
    const item: NoteQueueItemData = {
      jobId: "job-1",
      name: "Example URL",
      status: "pending",
      stage: "queued",
    };

    expect(
      completeUrlIngestQueueItem(item, "job-1", {
        success: false,
        error: "URL ingest failed",
      }),
    ).toEqual({
      jobId: "job-1",
      name: "Example URL",
      status: "failed",
      stage: "queued",
      error: "URL ingest failed",
    });
  });

  test("completeUrlIngestQueueItem leaves nonmatching items unchanged", () => {
    const item: NoteQueueItemData = {
      jobId: "job-1",
      name: "Example URL",
      status: "pending",
      stage: "queued",
    };

    expect(
      completeUrlIngestQueueItem(item, "job-2", {
        success: true,
        path: "sources/web/example",
        title: "Saved title",
      }),
    ).toEqual(item);
  });
});
