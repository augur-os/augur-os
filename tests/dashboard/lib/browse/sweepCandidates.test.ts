import { buildSweepCandidates } from "@/lib/browse/sweepCandidates";
import type { BrowseItem } from "@/lib/browse/types";

function item(partial: Partial<BrowseItem>): BrowseItem {
  return {
    id: partial.id || "id",
    title: partial.title || "Title",
    description: partial.description || "",
    hub: partial.hub || "system",
    icon: partial.icon,
    path: partial.path,
    tags: partial.tags,
    primaryAction: partial.primaryAction || { label: "Open", type: "open-file", target: "" },
    actions: partial.actions,
    metadata: partial.metadata,
  };
}

describe("buildSweepCandidates", () => {
  it("maps sources to docs archive candidates without inventing paths", () => {
    const out = buildSweepCandidates("sources", [
      item({
        id: "doc1",
        title: "Deck",
        path: "/Users/me/Projects/Au-docs/venture/deck.pdf",
        metadata: { format: "pdf" },
      }),
    ]);

    expect(out).toMatchObject({ source_tab: "sources", unsupported: [] });
    expect(out.targets).toEqual([
      {
        kind: "docs",
        source_id: "doc1",
        archive_mode: "docs-archive",
        source_path: "/Users/me/Projects/Au-docs/venture/deck.pdf",
        title: "Deck",
        metadata: { format: "pdf" },
      },
    ]);
  });

  it("maps vault and project-brain source cards to git-aware source-card candidates", () => {
    const out = buildSweepCandidates("sources", [
      item({
        id: "source:private",
        title: "Private source",
        path: "/Users/me/Projects/Au-vault/sources/web/private.md",
        metadata: {
          journey_category: "sources",
          source_root: "private-vault",
          vault_root: "private-vault",
        },
      }),
      item({
        id: "source:shared",
        title: "Shared source",
        path: "/Users/me/Projects/Augur/project-brain/knowledge/sources/README.md",
        metadata: {
          journey_category: "sources",
          source_root: "project-brain",
          vault_root: "project-brain",
        },
      }),
    ]);

    expect(out).toMatchObject({ source_tab: "sources", unsupported: [] });
    expect(out.targets).toEqual([
      {
        kind: "source-cards",
        source_id: "source:private",
        archive_mode: "git-aware",
        source_path: "/Users/me/Projects/Au-vault/sources/web/private.md",
        title: "Private source",
        metadata: {
          journey_category: "sources",
          source_root: "private-vault",
          vault_root: "private-vault",
        },
      },
      {
        kind: "source-cards",
        source_id: "source:shared",
        archive_mode: "git-aware",
        source_path: "/Users/me/Projects/Augur/project-brain/knowledge/sources/README.md",
        title: "Shared source",
        metadata: {
          journey_category: "sources",
          source_root: "project-brain",
          vault_root: "project-brain",
        },
      },
    ]);
  });

  it("maps notes to git-aware vault-note candidates using metadata paths first", () => {
    const out = buildSweepCandidates("notes", [
      item({
        id: "note1",
        title: "Old note",
        path: "/browse/display/path",
        metadata: { source_path: "/Users/me/Projects/Au-vault/notes/old.md" },
      }),
    ]);

    expect(out.targets[0]).toMatchObject({
      kind: "vault-notes",
      archive_mode: "git-aware",
      source_id: "note1",
      source_path: "/Users/me/Projects/Au-vault/notes/old.md",
    });
  });

  it("maps live pages to git-aware targets and generated or saved artifacts to docs archive", () => {
    const out = buildSweepCandidates("pages", [
      item({
        id: "live:/workspace/inbox",
        title: "Inbox",
        path: "/workspace/inbox",
        metadata: {
          kind: "live",
          sourcePath: "/Users/me/Projects/Augur/project-brain/capabilities/skills/ingest/SKILL.md",
        },
      }),
      item({
        id: "artifact:a",
        title: "Generated Artifact",
        path: "/Users/me/Projects/Au-docs/generated-report.html",
        metadata: { kind: "generated", filePath: "/Users/me/Projects/Au-docs/generated-report.html" },
      }),
      item({
        id: "artifact:b",
        title: "Saved Artifact",
        path: "/Users/me/Projects/Au-docs/saved-report.html",
        metadata: { kind: "saved" },
      }),
    ]);

    expect(out.targets.map((target) => target.kind)).toEqual([
      "pages-live",
      "pages-artifacts",
      "pages-artifacts",
    ]);
    expect(out.targets.map((target) => target.archive_mode)).toEqual([
      "git-aware",
      "docs-archive",
      "docs-archive",
    ]);
  });

  it("refuses relative live page source paths instead of forwarding them to the backend", () => {
    const out = buildSweepCandidates("pages", [
      item({
        id: "live:/workspace/inbox",
        title: "Inbox",
        path: "/workspace/inbox",
        metadata: {
          kind: "live",
          sourcePath: "project-brain/capabilities/skills/ingest/SKILL.md",
        },
      }),
    ]);

    expect(out.targets).toEqual([]);
    expect(out.unsupported).toEqual([
      {
        id: "live:/workspace/inbox",
        title: "Inbox",
        reason: "relative_page_source_path",
      },
    ]);
  });

  it("collects unsupported entries with machine-readable reasons", () => {
    const out = buildSweepCandidates("pages", [
      item({
        id: "live-missing",
        title: "Missing live source",
        path: "/workspace/inbox",
        metadata: { kind: "live" },
      }),
      item({
        id: "unknown-kind",
        title: "Unknown page kind",
        path: "/Users/me/Projects/Au-docs/report.html",
        metadata: { kind: "preview" },
      }),
    ]);

    expect(out.targets).toEqual([]);
    expect(out.unsupported).toEqual([
      {
        id: "live-missing",
        title: "Missing live source",
        reason: "missing_page_source_path",
      },
      {
        id: "unknown-kind",
        title: "Unknown page kind",
        reason: "unsupported_page_kind",
      },
    ]);
  });
});
