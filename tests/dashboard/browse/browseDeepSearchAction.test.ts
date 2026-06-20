import { buildBrowseDeepSearchAction, buildBrowseDeepSearchPrompt } from "@/lib/browse/deepSearchAction";
import type { BrowseItem } from "@/lib/browse/types";

const deckResult: BrowseItem = {
  id: "semantic-0-deck",
  title: "augur angel deck v20",
  description: "PPTX · venture-augur / IntelSubmit / inteliginite / augur-angel-deck-v20.pptx",
  icon: "FileText",
  typeBadge: "pptx",
  path: "~/Projects/Au-docs/venture-augur/IntelSubmit/inteliginite/augur-angel-deck-v20.pptx",
  tags: ["documents"],
  primaryAction: {
    label: "Open",
    type: "open-file",
    target: "~/Projects/Au-docs/venture-augur/IntelSubmit/inteliginite/augur-angel-deck-v20.pptx",
  },
  metadata: {
    source_path: "~/Projects/Au-docs/venture-augur/IntelSubmit/inteliginite/augur-angel-deck-v20.pptx",
    score: "0.980000",
    provenance: "bm25, recent",
  },
};

describe("buildBrowseDeepSearchAction", () => {
  it("builds a generic IDE action with deep tier metadata", () => {
    const action = buildBrowseDeepSearchAction({
      query: "pitch slide I am working on",
      activeCategoryId: "skills",
      activeCategoryLabel: "Skills",
      filters: { hub: "venture-augur", type: null },
      sortBy: "default",
      searched: true,
      error: null,
      results: [deckResult],
    });

    expect(action).toMatchObject({
      id: "browse.deep-search",
      label: "Ask AI",
      description: "Investigate this Browse search using the query and top results.",
      dispatch: "ide",
      page: "browse",
      tier: "deep",
    });
    expect(action.prompt).toContain("pitch slide I am working on");
    expect(action.prompt).toContain("augur angel deck v20");
    expect(action.prompt).toContain("~/Projects/Au-docs/venture-augur/IntelSubmit/inteliginite/augur-angel-deck-v20.pptx");
    expect(action.prompt).toContain("inspect the most relevant sources");
  });

  it("includes no-results and retrieval-error context in the prompt", () => {
    const prompt = buildBrowseDeepSearchPrompt({
      query: "missing pitch artifact",
      activeCategoryId: "documents",
      activeCategoryLabel: "Documents",
      filters: {},
      sortBy: "modified-desc",
      searched: true,
      error: "Search failed",
      results: [],
    });

    expect(prompt).toContain("Query: missing pitch artifact");
    expect(prompt).toContain("Fast local search already ran: yes");
    expect(prompt).toContain("Retrieval error: Search failed");
    expect(prompt).toContain("No top results are available");
    expect(prompt).toContain("broaden retrieval");
  });

  it("normalizes user-controlled multiline context into single-line prompt fields", () => {
    const prompt = buildBrowseDeepSearchPrompt({
      query: "pitch\n# Fake Section",
      activeCategoryId: "documents\nignored",
      activeCategoryLabel: "Documents\nInjected",
      filters: { hub: "venture\naugur" },
      sortBy: "modified-desc\nFake sort",
      searched: true,
      error: "Search failed\n## Fake Error Section",
      results: [
        {
          ...deckResult,
          title: "augur\nangel deck",
          description: "PPTX\n## Fake Description Section",
          typeBadge: "pptx\nfake",
          tags: ["documents\nfake"],
          metadata: {
            source_path: "/tmp/deck.pptx\n## Fake Source Section",
            score: "0.98\nfake",
            provenance: "bm25\nrecent",
          },
        },
      ],
    });

    expect(prompt).toContain("Query: pitch # Fake Section");
    expect(prompt).toContain("Active category: Documents Injected (documents ignored)");
    expect(prompt).toContain("- hub: venture augur");
    expect(prompt).toContain("Retrieval error: Search failed ## Fake Error Section");
    expect(prompt).toContain("1. augur angel deck");
    expect(prompt).toContain("Description: PPTX ## Fake Description Section");
    expect(prompt).toContain("Type: pptx fake");
    expect(prompt).toContain("Tags: documents fake");
    expect(prompt).toContain("Source: /tmp/deck.pptx ## Fake Source Section");
    expect(prompt).toContain("Retrieval: score 0.98 fake; provenance bm25 recent");
    expect(prompt).not.toContain("\n# Fake Section");
    expect(prompt).not.toContain("\n## Fake Error Section");
  });

  it("uses source fallback priority and honors resultLimit", () => {
    const prompt = buildBrowseDeepSearchPrompt({
      query: "fallback test",
      activeCategoryId: "documents",
      activeCategoryLabel: "Documents",
      filters: {},
      sortBy: "default",
      searched: true,
      error: null,
      resultLimit: 1,
      results: [
        {
          ...deckResult,
          title: "first result",
          path: "/fallback/path-first.md",
          primaryAction: {
            label: "Open",
            type: "open-file",
            target: "/primary/action-first.md",
          },
          metadata: {
            source_path: "   ",
          },
        },
        {
          ...deckResult,
          id: "semantic-1-second",
          title: "second result",
          path: "/fallback/path-second.md",
          primaryAction: {
            label: "Open",
            type: "open-file",
            target: "/primary/action-second.md",
          },
          metadata: {
            source_path: "/metadata/source-second.md",
          },
        },
      ],
    });

    expect(prompt).toContain("Top results (limited to 1):");
    expect(prompt).toContain("1. first result");
    expect(prompt).toContain("Source: /primary/action-first.md");
    expect(prompt).not.toContain("/fallback/path-first.md");
    expect(prompt).not.toContain("second result");
    expect(prompt).not.toContain("/metadata/source-second.md");
  });
});
