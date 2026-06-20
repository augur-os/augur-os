import {
  buildActionPaletteStream,
  buildBrowseTopResults,
  buildBrowseResultStream,
  buildStandardTopResults,
  buildStandardResultStream,
  dedupeTools,
  rankFileResult,
  rankKnowledgeResult,
  scoreActionLikeItem,
  sortBrowseItems,
  sortToolsByRelevance,
} from "@/features/components/chat/panelRanking";

describe("panelRanking", () => {
  it("prefers exact and prefix action matches over description matches", () => {
    expect(scoreActionLikeItem("analyze page", "", "analyze page")).toBeGreaterThan(
      scoreActionLikeItem("page helper", "analyze page here", "analyze page"),
    );
    expect(scoreActionLikeItem("analyze page now", "", "analyze")).toBeGreaterThan(
      scoreActionLikeItem("page analyzer", "", "analyze"),
    );
  });

  it("dedupes tools by case-insensitive name", () => {
    const tools = dedupeTools([
      { name: "browse-index", description: "first" },
      { name: "Browse-Index", description: "second" },
      { name: "search-memory", description: "third" },
    ]);

    expect(tools).toHaveLength(2);
    expect(tools.map((tool) => tool.name)).toEqual([
      "browse-index",
      "search-memory",
    ]);
  });

  it("sorts tools by preferred segment and search relevance", () => {
    const sorted = sortToolsByRelevance(
      [
        { name: "generic-tool", description: "knowledge helper" },
        { name: "knowledge-search", description: "search documents" },
        { name: "memory-search", description: "search memory" },
      ],
      "search",
      ["knowledge"],
    );

    expect(sorted[0]?.name).toBe("knowledge-search");
    expect(sorted[1]?.name).toBe("memory-search");
  });

  it("boosts browse results that match the selected skill", () => {
    const sorted = sortBrowseItems(
      [
        {
          id: "other",
          title: "Health notes",
          description: "docs",
          hub: "life",
        },
        {
          id: "knowledge",
          title: "Knowledge actions",
          description: "docs",
          hub: "workspace",
          metadata: { skill: "knowledge" },
        },
      ],
      "knowledge",
      "knowledge",
    );

    expect(sorted[0]?.id).toBe("knowledge");
  });

  it("builds browse top results across categories with selected-skill bias", () => {
    const top = buildBrowseTopResults(
      {
        skills: [
          { id: "finance", title: "Finance", description: "hub", hub: "career" },
        ],
        vault: [],
        wiki: [],
        documents: [],
        actions: [
          {
            id: "knowledge.search",
            title: "Knowledge Search",
            description: "search the knowledge skill",
            hub: "workspace",
            metadata: { skill: "knowledge" },
          },
        ],
      },
      "knowledge",
      "knowledge",
      2,
    );

    expect(top[0]?.category).toBe("actions");
    expect(top[0]?.item.title).toBe("Knowledge Search");
  });

  it("ranks knowledge title matches above snippet-only matches", () => {
    const titleScore = rankKnowledgeResult(
      {
        title: "Sleep",
        snippet: "recovery patterns",
        source: "knowledge",
        filePath: "/tmp/sleep.md",
      },
      "sleep",
    );
    const snippetScore = rankKnowledgeResult(
      {
        title: "Recovery",
        snippet: "sleep notes",
        source: "knowledge",
        filePath: "/tmp/recovery.md",
      },
      "sleep",
    );

    expect(titleScore).toBeGreaterThan(snippetScore);
  });

  it("ranks file name matches above path-only matches", () => {
    const nameScore = rankFileResult(
      { name: "report.md", relativePath: "vault/reports/report.md" },
      "report",
    );
    const pathScore = rankFileResult(
      { name: "summary.md", relativePath: "vault/reports/report-summary.md" },
      "report",
    );

    expect(nameScore).toBeGreaterThan(pathScore);
  });

  it("builds standard top results with knowledge ahead of weaker file matches", () => {
    const top = buildStandardTopResults(
      {
        knowledge: [
          {
            title: "Sleep",
            snippet: "deep sleep notes",
            source: "knowledge",
            filePath: "/tmp/sleep.md",
          },
        ],
        files: [
          {
            name: "summary.md",
            relativePath: "vault/sleep-summary.md",
          },
        ],
        logs: [],
      },
      "sleep",
      2,
    );

    expect(top[0]?.category).toBe("knowledge");
    expect((top[0]?.item as { title: string }).title).toBe("Sleep");
  });

  it("builds a single browse result stream with actions ahead of weaker document matches", () => {
    const stream = buildBrowseResultStream(
      {
        skills: [],
        vault: [],
        wiki: [],
        documents: [
          {
            id: "doc-1",
            title: "Knowledge Overview",
            description: "reference docs",
            hub: "workspace",
          },
        ],
        actions: [
          {
            id: "knowledge.search",
            title: "Knowledge Search",
            description: "search the knowledge index",
            hub: "workspace",
            metadata: { skill: "knowledge" },
          },
        ],
      },
      "knowledge",
      "knowledge",
    );

    expect(stream[0]?.category).toBe("actions");
    expect(stream[1]?.category).toBe("documents");
  });

  it("demotes generic browse titles below stronger named matches", () => {
    const stream = buildBrowseResultStream(
      {
        skills: [],
        vault: [],
        wiki: [],
        documents: [],
        actions: [
          {
            id: "knowledge.overview",
            title: "Knowledge Overview",
            description: "generic entry point for the knowledge skill",
            hub: "workspace",
            metadata: { skill: "knowledge" },
          },
          {
            id: "knowledge.search",
            title: "Knowledge Search",
            description: "search the knowledge skill",
            hub: "workspace",
            metadata: { skill: "knowledge" },
          },
        ],
      },
      "knowledge",
      "knowledge",
    );

    expect(stream[0]?.item.title).toBe("Knowledge Search");
    expect(stream[1]?.item.title).toBe("Knowledge Overview");
  });

  it("builds a single standard result stream without losing lower-ranked file items", () => {
    const stream = buildStandardResultStream(
      {
        knowledge: [
          {
            title: "Sleep",
            snippet: "deep sleep notes",
            source: "knowledge",
            filePath: "/tmp/sleep.md",
          },
        ],
        files: [
          {
            name: "sleep-summary.md",
            relativePath: "vault/sleep-summary.md",
          },
        ],
        logs: [
          {
            name: "sleep.log",
            relativePath: "logs/sleep.log",
          },
        ],
      },
      "sleep",
    );

    expect(stream.map((item) => item.category)).toEqual([
      "knowledge",
      "files",
      "logs",
    ]);
  });

  it("demotes generic knowledge note titles below stronger named results", () => {
    const stream = buildStandardResultStream(
      {
        knowledge: [
          {
            title: "Sleep Notes",
            snippet: "generic sleep notes",
            source: "knowledge",
            filePath: "/tmp/sleep-notes.md",
          },
          {
            title: "Sleep Protocol",
            snippet: "specific recovery protocol",
            source: "knowledge",
            filePath: "/tmp/sleep-protocol.md",
          },
        ],
        files: [],
        logs: [],
      },
      "sleep",
    );

    expect((stream[0]?.item as { title: string }).title).toBe("Sleep Protocol");
    expect((stream[1]?.item as { title: string }).title).toBe("Sleep Notes");
  });

  it("demotes generic file names below stronger named file matches", () => {
    const stream = buildStandardResultStream(
      {
        knowledge: [],
        files: [
          {
            name: "sleep-notes.md",
            relativePath: "vault/sleep-notes.md",
          },
          {
            name: "sleep-protocol.md",
            relativePath: "vault/sleep-protocol.md",
          },
        ],
        logs: [],
      },
      "sleep",
    );

    expect((stream[0]?.item as { name: string }).name).toBe("sleep-protocol.md");
    expect((stream[1]?.item as { name: string }).name).toBe("sleep-notes.md");
  });

  it("builds a mixed action stream with skill actions ahead of strong named tools", () => {
    const stream = buildActionPaletteStream(
      {
        showAnalyzePage: false,
        pendingInsightCount: 0,
        skillActions: [
          {
            id: "knowledge.search",
            label: "Knowledge Search",
            description: "search the knowledge skill",
          },
        ],
        pageTools: [
          {
            name: "knowledge-index",
            description: "inspect the knowledge index",
          },
        ],
        prompts: [
          {
            id: "prompt-1",
            title: "Knowledge Prompt",
            description: "prompt for knowledge",
            hub: "workspace",
          },
        ],
        workflows: [],
      },
      "knowledge",
    );

    expect(stream[0]?.category).toBe("skill-action");
    expect(stream.some((item) => item.category === "tool")).toBe(true);
    expect(stream.some((item) => item.category === "prompt")).toBe(true);
  });

  it("drops weak generic tools when stronger action matches exist", () => {
    const stream = buildActionPaletteStream(
      {
        showAnalyzePage: false,
        pendingInsightCount: 0,
        skillActions: [
          {
            id: "knowledge.search",
            label: "Knowledge Search",
            description: "search the knowledge skill",
          },
        ],
        pageTools: [
          {
            name: "generic-tool",
            description: "generic knowledge helper",
          },
        ],
        prompts: [
          {
            id: "prompt-1",
            title: "Knowledge Prompt",
            description: "prompt for knowledge",
            hub: "workspace",
          },
        ],
        workflows: [],
      },
      "knowledge",
    );

    expect(stream.some((item) => item.category === "tool")).toBe(false);
    expect(stream.map((item) => item.category)).toEqual([
      "skill-action",
      "prompt",
    ]);
  });

  it("keeps strongly named tools even when stronger actions also exist", () => {
    const stream = buildActionPaletteStream(
      {
        showAnalyzePage: false,
        pendingInsightCount: 0,
        skillActions: [
          {
            id: "knowledge.search",
            label: "Knowledge Search",
            description: "search the knowledge skill",
          },
        ],
        pageTools: [
          {
            name: "knowledge-index",
            description: "inspect the knowledge index",
          },
        ],
        prompts: [],
        workflows: [],
      },
      "knowledge",
    );

    expect(stream.some((item) => item.category === "tool")).toBe(true);
    expect(stream[0]?.category).toBe("skill-action");
  });
});
