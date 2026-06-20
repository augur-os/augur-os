import { transformIndexEntry } from "@/lib/browse/transforms";
import { withDemoRunActions } from "@/lib/browse/demoRunActions";
import type { BrowseItem } from "@/lib/browse/types";

function makeItem(overrides: Partial<BrowseItem> = {}): BrowseItem {
  return {
    id: "item-1",
    title: "Demo Artifact",
    description: "Artifact",
    hub: "workspace",
    path: "C:/Demo/artifact.md",
    primaryAction: {
      label: "Open",
      type: "open-file",
      target: "C:/Demo/artifact.md",
    },
    ...overrides,
  };
}

describe("withDemoRunActions", () => {
  function labelsFor(item: BrowseItem): string[] | undefined {
    return withDemoRunActions(item, "documents").actions?.map((action) => action.label);
  }

  it("adds transcript actions to media artifacts", () => {
    const result = withDemoRunActions(
      makeItem({
        title: "Judges Meeting",
        path: "C:/Users/demo/Videos/judges-meeting.m4a",
      }),
      "documents",
    );

    expect(result.actions?.map((action) => action.label)).toEqual([
      "Transcript",
      "Meeting Memory",
      "Ask From Transcript",
    ]);
    expect(result.actions?.[0]).toMatchObject({
      id: "demo-run-transcript",
      label: "Transcript",
      type: "mcp-tool",
      target: "demo-run-transcript",
      args: {
        source_path: "C:/Users/demo/Videos/judges-meeting.m4a",
        title: "Judges Meeting",
      },
    });
  });

  it("uses metadata source_path and metadata path fallbacks for source paths", () => {
    const fromSourcePath = withDemoRunActions(
      makeItem({
        title: "Metadata Source",
        path: undefined,
        metadata: { source_path: "C:/Demo/source-path.mp3" },
      }),
      "documents",
    );
    const fromMetadataPath = withDemoRunActions(
      makeItem({
        title: "Metadata Path",
        path: undefined,
        metadata: { path: "C:/Demo/metadata-path.pptx" },
      }),
      "documents",
    );

    expect(fromSourcePath.actions?.[0]).toMatchObject({
      target: "demo-run-transcript",
      args: { source_path: "C:/Demo/source-path.mp3", title: "Metadata Source" },
    });
    expect(fromMetadataPath.actions?.[0]).toMatchObject({
      target: "demo-run-prompt",
      args: { source_path: "C:/Demo/metadata-path.pptx", title: "Metadata Path" },
    });
  });

  it("prefers canonical metadata source paths over item path", () => {
    const fromSnakeCase = withDemoRunActions(
      makeItem({
        title: "Canonical Source",
        path: "C:/Demo/wrong-item-path.mp3",
        metadata: { source_path: "C:/Demo/canonical-source.pptx" },
      }),
      "documents",
    );
    const fromCamelCase = withDemoRunActions(
      makeItem({
        title: "Camel Source",
        path: "C:/Demo/wrong-item-path.mp3",
        metadata: { sourcePath: "C:/Demo/camel-source.m4a" },
      }),
      "documents",
    );

    expect(fromSnakeCase.actions?.[0]).toMatchObject({
      target: "demo-run-prompt",
      args: { source_path: "C:/Demo/canonical-source.pptx", title: "Canonical Source" },
    });
    expect(fromCamelCase.actions?.[0]).toMatchObject({
      target: "demo-run-transcript",
      args: { source_path: "C:/Demo/camel-source.m4a", title: "Camel Source" },
    });
  });

  it("detects media from media_kind and exact or MIME media_type values", () => {
    expect(labelsFor(makeItem({ path: undefined, metadata: { source_path: "C:/Demo/no-extension", media_kind: "audio" } }))).toEqual([
      "Transcript",
      "Meeting Memory",
      "Ask From Transcript",
    ]);
    expect(labelsFor(makeItem({ path: undefined, metadata: { source_path: "C:/Demo/no-extension", media_type: "audio" } }))).toEqual([
      "Transcript",
      "Meeting Memory",
      "Ask From Transcript",
    ]);
    expect(labelsFor(makeItem({ path: undefined, metadata: { source_path: "C:/Demo/no-extension", media_type: "video/mp4" } }))).toEqual([
      "Transcript",
      "Meeting Memory",
      "Ask From Transcript",
    ]);
  });

  it("adds prompt actions to deck and slide artifacts", () => {
    const result = withDemoRunActions(
      makeItem({
        title: "Augur Demo",
        path: "C:/Demo/Augur Demo.pptx",
      }),
      "documents",
    );

    expect(result.actions?.map((action) => action.label)).toEqual([
      "Claude Value",
      "Gemini Design",
      "Technical Depth",
    ]);
    expect(result.actions?.[0]).toMatchObject({
      id: "demo-run-claude-value",
      label: "Claude Value",
      type: "mcp-tool",
      target: "demo-run-prompt",
      args: {
        source_path: "C:/Demo/Augur Demo.pptx",
        title: "Augur Demo",
        client: "claude",
        prompt_kind: "judge-value",
      },
    });
  });

  it("detects deck and slide artifacts from metadata kind values", () => {
    expect(labelsFor(makeItem({ path: undefined, metadata: { source_path: "C:/Demo/no-extension", document_kind: "slide deck" } }))).toEqual([
      "Claude Value",
      "Gemini Design",
      "Technical Depth",
    ]);
    expect(labelsFor(makeItem({ path: undefined, metadata: { source_path: "C:/Demo/no-extension", artifact_kind: "presentation" } }))).toEqual([
      "Claude Value",
      "Gemini Design",
      "Technical Depth",
    ]);
  });

  it("does not add demo actions to plain markdown notes", () => {
    const result = withDemoRunActions(
      makeItem({
        title: "Plain Note",
        path: "C:/Demo/plain-note.md",
        metadata: { document_kind: "note" },
      }),
      "documents",
    );

    expect(result.actions).toBeUndefined();
  });

  it("does not classify markdown as a deck even when metadata names slides or presentations", () => {
    expect(labelsFor(makeItem({
      path: "C:/Demo/slides.md",
      metadata: { document_kind: "presentation deck" },
    }))).toBeUndefined();
  });

  it("preserves existing actions and does not duplicate demo action ids", () => {
    const result = withDemoRunActions(
      makeItem({
        title: "Augur Demo",
        path: "C:/Demo/Augur Demo.pptx",
        actions: [
          { id: "open-folder", label: "Open Folder", icon: "FolderOpen", type: "open-file", target: "C:/Demo" },
          { id: "demo-run-claude-value", label: "Claude Value", icon: "Sparkles", type: "mcp-tool", target: "demo-run-prompt" },
        ],
      }),
      "documents",
    );

    expect(result.actions?.map((action) => action.id)).toEqual([
      "open-folder",
      "demo-run-claude-value",
      "demo-run-gemini-design",
      "demo-run-technical-depth",
    ]);
  });

  it("does not add demo actions outside approved Browse artifact categories", () => {
    expect(withDemoRunActions(
      makeItem({
        title: "Command Recording",
        path: "C:/Demo/command-recording.m4a",
      }),
      "commands",
    ).actions).toBeUndefined();
  });

  it("does not add demo actions for URL or synthetic source paths", () => {
    expect(withDemoRunActions(
      makeItem({
        title: "Remote Deck",
        path: "https://example.com/Augur%20Demo.pptx",
      }),
      "documents",
    ).actions).toBeUndefined();
    expect(withDemoRunActions(
      makeItem({
        title: "Archived Deck",
        path: "archive://demo/Augur Demo.pptx",
      }),
      "vault",
    ).actions).toBeUndefined();
  });
});

describe("transformIndexEntry demo run actions", () => {
  it("adds demo actions after existing document actions for index-backed media cards", () => {
    const result = transformIndexEntry(
      {
        id: "judges-meeting",
        title: "Judges Meeting",
        source_path: "C:/Users/demo/Videos/judges-meeting.m4a",
      },
      "documents",
    );

    expect(result.actions?.map((action) => action.id)).toContain("remove-C:/Users/demo/Videos/judges-meeting.m4a");
    expect(result.actions?.map((action) => action.id)).toEqual(expect.arrayContaining([
      "demo-run-transcript",
      "demo-run-meeting-memory",
      "demo-run-ask-transcript",
    ]));
  });

  it("does not add demo actions to non-document non-vault index categories", () => {
    const result = transformIndexEntry(
      {
        id: "demo-command",
        title: "Demo Command",
        source_path: "C:/Demo/Augur Demo.pptx",
      },
      "commands",
    );

    expect(result.actions?.map((action) => action.id)).not.toEqual(expect.arrayContaining([
      "demo-run-claude-value",
      "demo-run-gemini-design",
      "demo-run-technical-depth",
    ]));
  });
});
