import { buildSweepCandidates } from "@/lib/browse/sweepCandidates";
import type { BrowseItem } from "@/lib/browse/types";

describe("buildSweepCandidates for Browse documents", () => {
  it("builds docs archive targets for documents", () => {
    const result = buildSweepCandidates("documents", [
      {
        id: "doc-1",
        title: "Invoice",
        description: "",
        hub: "downloads",
        path: "~/Downloads/invoice.pdf",
        primaryAction: {
          label: "Open",
          type: "open-file",
          target: "~/Downloads/invoice.pdf",
        },
        metadata: {
          source_root: "downloads",
          fileType: "pdf",
        },
      } satisfies BrowseItem,
    ]);

    expect(result.source_tab).toBe("documents");
    expect(result.targets).toEqual([
      expect.objectContaining({
        kind: "docs",
        source_path: "~/Downloads/invoice.pdf",
        source_id: "doc-1",
        archive_mode: "docs-archive",
        title: "Invoice",
      }),
    ]);
    expect(result.unsupported).toEqual([]);
  });
});
