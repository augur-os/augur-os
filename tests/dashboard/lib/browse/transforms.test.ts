// TODO_CLEANUP: This file is 817 lines — consider splitting into smaller modules
import {
  transformSkills,
  transformBlocks,
  transformPages,
  transformDocuments,
  transformMcpTools,
  transformVault,
  transformIntegrations,
  transformPrompts,
  transformCommands,
  transformAgents,
  transformAdrs,
  transformTests,
  transformApiRoutes,
  transformScripts,
  transformIndexEntry,
  dedupeSkillBrowseItems,
} from "@/lib/browse/transforms";
import { BROWSE_CATEGORIES } from "@/lib/browse/types";

/**
 * Shared assertion: every BrowseItem must have the required fields.
 */
function expectValidBrowseItem(item: Record<string, unknown>) {
  expect(item).toHaveProperty("id");
  expect(item).toHaveProperty("title");
  expect(item).toHaveProperty("description");
  expect(item).toHaveProperty("primaryAction");

  const action = item.primaryAction as Record<string, unknown>;
  expect(action).toHaveProperty("label");
  expect(action).toHaveProperty("type");
  expect(action).toHaveProperty("target");

  expect(typeof action.label).toBe("string");
  expect(typeof action.type).toBe("string");
  expect(typeof action.target).toBe("string");
}

// ---------------------------------------------------------------------------
// transformSkills
// ---------------------------------------------------------------------------
describe("transformSkills", () => {
  it("returns an array of BrowseItems", () => {
    const result = transformSkills([
      { name: "test-skill", display_name: "Test Skill", description: "A skill", hub: "dev" },
    ]);
    expect(Array.isArray(result)).toBe(true);
    expect(result).toHaveLength(1);
    expectValidBrowseItem(result[0]);
  });

  it("sets primaryAction.type to navigate with correct target", () => {
    const result = transformSkills([
      { name: "test-skill", display_name: "Test Skill", description: "A skill", hub: "dev" },
    ]);
    expect(result[0].primaryAction.type).toBe("navigate");
    expect(result[0].primaryAction.target).toBe("/browse/test-skill");
  });

  it("preserves group and release metadata for skills", () => {
    const result = transformSkills([
      {
        name: "content",
        description: "Content workflow",
        hub: "business",
        group: "business",
        release: "r2",
      },
    ]);
    expect(result[0].metadata?.group).toBe("business");
    expect(result[0].metadata?.release).toBe("r2");
  });

  it("normalizes ownership, clients, type, tags, and docs metadata for skills", () => {
    const result = transformSkills([
      {
        name: "knowledge",
        description: "Knowledge workflow",
        hub: "workspace",
        ownership: "external",
        master: "codex",
        source: "global",
        plugin: "knowledge",
        group: "knowledge-base",
        release: "r2",
        category: "knowledge",
        skill_type: "domain",
        skill_clients: ["codex", "gemini"],
        tags: ["memory", "search"],
        upstream: { source: "github", path: "project-brain/capabilities/skills/knowledge" },
        has_docs: true,
      },
    ]);

    expect(result).toHaveLength(1);
    expect(result[0].metadata?.ownership).toBe("external");
    expect(result[0].metadata?.masterClient).toBe("codex");
    expect(result[0].metadata?.skillClients).toBe("codex,gemini");
    expect(result[0].metadata?.skillType).toBe("domain");
    expect(result[0].metadata?.skillTags).toBe("memory,search");
    expect(result[0].metadata?.hasDocs).toBe("true");
    expect(result[0].metadata?.source).toBe("global");
    expect(result[0].metadata?.upstreamSource).toBe("github");
    expect(result[0].metadata?.upstreamPath).toBe("project-brain/capabilities/skills/knowledge");
    expect(result[0].metadata?.category).toBe("knowledge");
    expect(result[0].metadata?.group).toBe("knowledge-base");
    expect(result[0].metadata?.release).toBe("r2");
    expect(result[0].metadata?.plugin).toBe("knowledge");
  });

  it("preserves user ownership for private-vault skills", () => {
    const result = transformSkills([
      {
        name: "books",
        description: "Personal library",
        hub: "workspace",
        ownership: "user",
        source: "private-vault",
      },
    ]);

    expect(result[0].metadata?.ownership).toBe("user");
    expect(result[0].metadata?.source).toBe("private-vault");
  });

  it("dedupes source and client projections into one canonical skill card", () => {
    const result = transformSkills([
      {
        name: "knowledge",
        display_name: "Knowledge",
        description: "Project source skill",
        source: "project-brain",
        source_root: "project-brain",
        ownership: "augur",
        skill_clients: ["augur"],
      },
      {
        name: "knowledge",
        display_name: "Knowledge",
        description: "Codex projection",
        source: "codex-local",
        source_root: "external-client",
        ownership: "external",
        skill_clients: ["codex"],
      },
    ] as any);

    expect(result).toHaveLength(1);
    expect(result[0].id).toBe("knowledge");
    expect(result[0].title).toBe("Knowledge");
    expect(result[0].description).toBe("Project source skill");
    expect(result[0].metadata).toMatchObject({
      ownership: "augur",
      source: "project-brain",
      sourceRoot: "project-brain",
      sourceScope: "project-brain",
    });
    expect(result[0].metadata?.skillClients?.split(",").sort()).toEqual(["augur", "codex"]);
  });

  it("dedupes indexed client skill projections behind the canonical skill card", () => {
    const items = [
      transformIndexEntry(
        {
          id: "skill:project-brain:knowledge",
          name: "knowledge",
          title: "knowledge",
          description: "Managed knowledge skill",
          source: "project-brain",
          source_root: "project-brain",
          metadata: {
            source_root: "project-brain",
            vault_scope: "shared",
            skillClients: "augur",
          },
        },
        "skills",
      ),
      transformIndexEntry(
        {
          id: "ai-artifact:project-augur:1d9c5967e34a3b89",
          name: "knowledge",
          title: "knowledge",
          description: "Claude projection",
          source: "claude",
          ownership: "external",
          source_path: "~/Projects/Augur/.claude/skills/knowledge/SKILL.md",
          metadata: {},
        },
        "skills",
      ),
    ];

    const result = dedupeSkillBrowseItems(items);

    expect(result).toHaveLength(1);
    expect(result[0].id).toBe("skill:project-brain:knowledge");
    expect(result[0].metadata).toMatchObject({
      sourceScope: "project-brain",
      sourceRoot: "project-brain",
      sourceRoots: "project-brain,external-client",
    });
  });

  it("dedupes opaque ai-artifact skill projections by title and path", () => {
    const items = [
      transformIndexEntry(
        {
          id: "skill:private-vault:apple-notes",
          title: "apple-notes",
          description: "Personal Apple Notes skill",
          source: "private-vault",
          source_path: "~/Projects/Au-vault/capabilities/skills/apple/apple-notes/SKILL.md",
          metadata: {
            source_root: "private-vault",
            skillClients: "vault",
          },
        },
        "skills",
      ),
      transformIndexEntry(
        {
          id: "ai-artifact:project-augur:2aae43ca998090ad",
          title: "apple-notes",
          description: "Codex projection",
          source: "codex-local",
          ownership: "external",
          source_path: "~/Projects/Augur/.codex/skills/apple-notes/SKILL.md",
          metadata: {
            source_root: "external-client",
            skill_clients: "codex",
          },
        },
        "skills",
      ),
    ];

    const result = dedupeSkillBrowseItems(items);

    expect(result).toHaveLength(1);
    expect(result[0].id).toBe("skill:private-vault:apple-notes");
    expect(result[0].metadata).toMatchObject({
      skillName: "apple-notes",
      sourceScope: "private-vault",
      sourceRoots: "private-vault,external-client",
    });
  });
});

// ---------------------------------------------------------------------------
// transformBlocks
// ---------------------------------------------------------------------------
describe("transformBlocks", () => {
  const input = [
    { id: "block-1", title: "Chart", type: "chart", icon: "BarChart", hub: "finance", skill: "dashboard", configSchema: {} },
  ];

  it("returns an array of BrowseItems", () => {
    const result = transformBlocks(input);
    expect(Array.isArray(result)).toBe(true);
    expect(result).toHaveLength(1);
    expectValidBrowseItem(result[0]);
  });

  it("sets primaryAction.type to navigate", () => {
    const result = transformBlocks(input);
    expect(result[0].primaryAction.type).toBe("navigate");
  });
});

// ---------------------------------------------------------------------------
// knowledge Browse categories
// ---------------------------------------------------------------------------
describe("knowledge Browse categories", () => {
  it("places documents in the context journey before wiki", () => {
    const documents = BROWSE_CATEGORIES.find((category) => category.id === "documents");

    expect(documents).toMatchObject({
      label: "Documents",
      singularLabel: "Document",
      icon: "FolderOpen",
      devOnly: false,
      group: "content",
      journey_group: "context",
      journey_order: 2,
    });
  });

});

describe("transformIndexEntry for documents", () => {
  it("uses catalog summary for document descriptions", () => {
    const item = transformIndexEntry(
      {
        id: "architecture",
        title: "Architecture Overview",
        type: "document",
        source_path: "/cache/architecture.pdf",
        metadata: {
          catalogSummary: "Catalog summary used on cards.",
          provider: "google-drive",
          indexStatus: "source_changed",
          attachedBrainIds: "project-y,personal",
        },
      },
      "documents",
    );

    expect(item.description).toBe("Catalog summary used on cards.");
    expect(item.path).toBe("/cache/architecture.pdf");
    expect(item.metadata?.indexStatus).toBe("source_changed");
    expect(item.metadata?.attachedBrainIds).toBe("project-y,personal");
  });

  it("normalizes snake_case document catalog and attachment metadata", () => {
    const item = transformIndexEntry(
      {
        id: "shared-architecture",
        title: "Shared Architecture",
        type: "document",
        source_path: "/cache/shared-architecture.pdf",
        catalog_summary: "Snake case catalog summary.",
        metadata: {
          catalog_summary: "Snake case catalog summary.",
          provider: "sharepoint",
          index_status: "summary_stale",
          attached_brain_ids: "project-y,personal",
          remote_revision: "remote-2",
          indexed_revision: "remote-1",
        },
      },
      "documents",
    );

    expect(item.description).toBe("Snake case catalog summary.");
    expect(item.metadata).toMatchObject({
      catalogSummary: "Snake case catalog summary.",
      catalog_summary: "Snake case catalog summary.",
      provider: "sharepoint",
      indexStatus: "summary_stale",
      attachedBrainIds: "project-y,personal",
      remoteRevision: "remote-2",
      indexedRevision: "remote-1",
    });
  });
});

// ---------------------------------------------------------------------------
// transformPages
// ---------------------------------------------------------------------------
describe("transformPages", () => {
  const input = [{ label: "Pipeline", href: "/career/pipeline", hub: "career", icon: "GitBranch" }];

  it("returns an array of BrowseItems", () => {
    const result = transformPages(input);
    expect(Array.isArray(result)).toBe(true);
    expect(result).toHaveLength(1);
    expectValidBrowseItem(result[0]);
  });

  it("sets primaryAction.type to navigate", () => {
    const result = transformPages(input);
    expect(result[0].primaryAction.type).toBe("navigate");
  });

  it("passes indexed page source paths through to live Browse items", () => {
    const result = transformPages(input, [
      {
        route: "/career/pipeline",
        source_path: "/Users/me/Projects/Augur/project-brain/capabilities/skills/career/SKILL.md",
      },
    ]);

    expect(result[0].metadata?.sourcePath).toBe(
      "/Users/me/Projects/Augur/project-brain/capabilities/skills/career/SKILL.md",
    );
  });
});

// ---------------------------------------------------------------------------
// transformDocuments
// ---------------------------------------------------------------------------
describe("transformDocuments", () => {
  const input = [{ path: "/vault/doc.md", name: "My Doc", hub: "career" }];

  it("returns an array of BrowseItems", () => {
    const result = transformDocuments(input);
    expect(Array.isArray(result)).toBe(true);
    expect(result).toHaveLength(1);
    expectValidBrowseItem(result[0]);
  });

  it("sets primaryAction.type to open-file", () => {
    const result = transformDocuments(input);
    expect(result[0].primaryAction.type).toBe("open-file");
  });
});

// ---------------------------------------------------------------------------
// transformMcpTools
// ---------------------------------------------------------------------------
describe("transformMcpTools", () => {
  const input = [{ id: "list-skills", title: "list-skills", hub: "system", enabled: true, category: "core" }];

  it("returns an array of BrowseItems", () => {
    const result = transformMcpTools(input);
    expect(Array.isArray(result)).toBe(true);
    expect(result).toHaveLength(1);
    expectValidBrowseItem(result[0]);
  });

  it("sets primaryAction.type to run-mcp", () => {
    const result = transformMcpTools(input);
    expect(result[0].primaryAction.type).toBe("run-mcp");
  });
});

// ---------------------------------------------------------------------------
// mcp-servers index transform
// ---------------------------------------------------------------------------
describe("transformIndexEntry for mcp-servers", () => {
  it("maps configured MCP servers to Browse items", () => {
    const result = transformIndexEntry(
      {
        id: "augur-gmail",
        title: "augur-gmail",
        name: "augur-gmail",
        description: "Gmail bundle",
        source_path: "/repo/config/system/mcp_servers.yaml",
        tier: "vault-tier",
        command: "python",
        args: "-m augur_shared.bundle_server gmail",
        bundle: "gmail",
        status: "configured",
      },
      "mcp-servers",
    );

    expectValidBrowseItem(result);
    expect(result.icon).toBe("Server");
    expect(result.typeBadge).toBe("vault-tier");
    expect(result.primaryAction).toEqual({
      label: "Open Manifest",
      type: "open-file",
      target: "/repo/config/system/mcp_servers.yaml",
    });
    expect(result.metadata).toEqual({
      tier: "vault-tier",
      command: "python",
      bundle: "gmail",
      status: "configured",
    });
  });

  it("maps metadata-shaped MCP server fields to Browse items", () => {
    const result = transformIndexEntry(
      {
        id: "augur-gmail",
        title: "augur-gmail",
        name: "augur-gmail",
        source_path: "/repo/config/system/mcp_servers.yaml",
        metadata: {
          tier: "vault-tier",
          command: "python",
          bundle: "gmail",
          status: "configured",
        },
      },
      "mcp-servers",
    );

    expect(result.description).toBe("python");
    expect(result.icon).toBe("Server");
    expect(result.typeBadge).toBe("vault-tier");
    expect(result.primaryAction).toEqual({
      label: "Open Manifest",
      type: "open-file",
      target: "/repo/config/system/mcp_servers.yaml",
    });
    expect(result.metadata).toEqual({
      tier: "vault-tier",
      command: "python",
      bundle: "gmail",
      status: "configured",
    });
  });

  it("preserves MCP server runtime observability metadata", () => {
    const result = transformIndexEntry(
      {
        id: "augur-apple",
        title: "augur-apple (stale runtime)",
        name: "augur-apple",
        description: "Running Augur MCP process not declared in config/system/mcp_servers.yaml",
        tier: "runtime",
        status: "stale-runtime",
        runtime_status: "stale-running",
        runtime_pids: "202",
        running_clients: "codex",
        runtime_process_count: 1,
        stale_runtime: true,
      },
      "mcp-servers",
    );

    expect(result.typeBadge).toBe("runtime");
    expect(result.metadata).toMatchObject({
      status: "stale-runtime",
      runtimeStatus: "stale-running",
      runtimePids: "202",
      runningClients: "codex",
      runtimeProcessCount: "1",
      staleRuntime: "true",
    });
  });
});

// ---------------------------------------------------------------------------
// transformVault
// ---------------------------------------------------------------------------
describe("transformVault", () => {
  const input = [
    { id: "career/notes/readme", title: "readme", description: "career", hub: "career", path: "/vault/career/notes/readme.md", file_type: "md" },
  ];

  it("returns an array of BrowseItems", () => {
    const result = transformVault(input);
    expect(Array.isArray(result)).toBe(true);
    expect(result).toHaveLength(1);
    expectValidBrowseItem(result[0]);
  });

  it("sets primaryAction.type to open-file", () => {
    const result = transformVault(input);
    expect(result[0].primaryAction.type).toBe("open-file");
  });

  it("normalizes GitHub repository classification metadata for note cards", () => {
    const [result] = transformVault([
      {
        id: "vault:notes:codex",
        title: "Codex",
        description: "GitHub repo",
        hub: "workspace",
        path: "/vault/notes/codex.md",
        file_type: "md",
        metadata: {
          "x-augur-note-type": "url",
          canonical_url: "https://github.com/openai/codex",
        },
      },
    ]);

    expect(result.typeBadge).toBe("url");
    expect(result.metadata).toMatchObject({
      noteType: "url",
      noteDomain: "projects",
      noteSource: "github",
      noteStatus: "saved",
      classificationConfidence: "high",
      needsClassification: "false",
    });
  });

  it("marks generic web notes as low-confidence research", () => {
    const [result] = transformVault([
      {
        id: "vault:notes:generic",
        title: "Generic web page",
        description: "Generic",
        hub: "workspace",
        path: "/vault/notes/generic.md",
        file_type: "md",
        metadata: {
          "x-augur-note-type": "url",
          url: "https://example.net/random-page",
        },
      },
    ]);

    expect(result.metadata).toMatchObject({
      noteDomain: "research",
      noteSource: "website",
      classificationConfidence: "low",
      needsClassification: "true",
    });
    expect(result.metadata?.noteStatus).toBeUndefined();
  });

  it("keeps trusted frontmatter classification over URL classification", () => {
    const [result] = transformVault([
      {
        id: "vault:notes:curated",
        title: "Curated job",
        description: "Curated",
        hub: "workspace",
        path: "/vault/notes/curated.md",
        file_type: "md",
        metadata: {
          "x-augur-note-type": "url",
          "x-augur-domain": "jobs",
          "x-augur-source": "linkedin",
          "x-augur-status": "applied",
          "x-augur-classification-confidence": "high",
          url: "https://github.com/openai/codex",
        },
      },
    ]);

    expect(result.metadata).toMatchObject({
      noteDomain: "jobs",
      noteSource: "linkedin",
      noteStatus: "applied",
      classificationConfidence: "high",
    });
  });

  it("does not classify archive vault records without note signals", () => {
    const [result] = transformVault([
      {
        id: "sweep:docs:run:old.zip",
        title: "old.zip",
        description: "superseded",
        hub: "system",
        source_path: "/docs/.archive/old.zip",
        metadata: {
          journey_category: "archive",
          archive_source: "sweep",
          archive_mode: "docs-archive",
          recovery_hint: "Move the file out of .archive.",
        },
      },
    ]);

    expect(result.metadata?.noteDomain).toBeUndefined();
    expect(result.metadata?.noteSource).toBeUndefined();
    expect(result.metadata?.noteStatus).toBeUndefined();
    expect(result.metadata?.classificationConfidence).toBeUndefined();
    expect(result.metadata?.needsClassification).toBeUndefined();
  });

  it("does not classify URL-bearing archive vault records without explicit note classification", () => {
    const [result] = transformVault([
      {
        id: "sweep:docs:run:url-old.zip",
        title: "old-url.zip",
        description: "superseded URL archive",
        hub: "system",
        source_path: "/docs/.archive/old-url.zip",
        metadata: {
          journey_category: "archive",
          archive_source: "sweep",
          archive_mode: "docs-archive",
          url: "https://github.com/openai/codex",
        },
      },
    ]);

    expect(result.metadata?.noteDomain).toBeUndefined();
    expect(result.metadata?.noteSource).toBeUndefined();
    expect(result.metadata?.noteStatus).toBeUndefined();
    expect(result.metadata?.classificationConfidence).toBeUndefined();
    expect(result.metadata?.needsClassification).toBeUndefined();
  });

  it("does not classify inbox non-note vault records from URL metadata alone", () => {
    const [result] = transformVault([
      {
        id: "inbox:email-drop:codex",
        title: "Email drop",
        description: "Inbound email artifact",
        hub: "workspace",
        path: "/vault/inbox/email-drops/codex.md",
        file_type: "md",
        metadata: {
          journey_category: "inbox",
          source: "email-drop",
          source_domain: "github.com",
          url: "https://github.com/openai/codex",
        },
      },
    ]);

    expect(result.metadata?.noteDomain).toBeUndefined();
    expect(result.metadata?.noteSource).toBeUndefined();
    expect(result.metadata?.noteStatus).toBeUndefined();
    expect(result.metadata?.classificationConfidence).toBeUndefined();
    expect(result.metadata?.needsClassification).toBeUndefined();
  });

  it("carries noteState: inbox on inbox-tagged vault records regardless of URL metadata", () => {
    const [result] = transformVault([
      {
        id: "inbox:email-drop:codex",
        title: "Email drop",
        description: "Inbound email artifact",
        hub: "workspace",
        path: "/vault/inbox/email-drops/codex.md",
        file_type: "md",
        metadata: {
          journey_category: "inbox",
          source: "email-drop",
          source_domain: "github.com",
          url: "https://github.com/openai/codex",
        },
      },
    ]);

    expect(result.metadata?.noteState).toBe("inbox");
  });

  it("carries noteState: inbox on a plain inbox note (no URL signals)", () => {
    const [result] = transformVault([
      {
        id: "inbox:notes:quick-thought",
        title: "Quick thought",
        description: "A fleeting idea",
        hub: "workspace",
        path: "/vault/inbox/quick-thought.md",
        file_type: "md",
        metadata: {
          journey_category: "inbox",
        },
      },
    ]);

    expect(result.metadata?.noteState).toBe("inbox");
    // inbox note without explicit note type should still NOT get note classification
    expect(result.metadata?.noteDomain).toBeUndefined();
    expect(result.metadata?.noteSource).toBeUndefined();
  });

  it("carries noteState: inbox through the live transformIndexEntry vault path", () => {
    const item = transformIndexEntry(
      {
        id: "inbox:notes:quick-thought",
        title: "Quick thought",
        source_path: "/vault/inbox/quick-thought.md",
        metadata: { journey_category: "inbox" },
      },
      "vault",
    );

    expect(item.metadata?.noteState).toBe("inbox");
  });

  it("does not set noteState on non-inbox notes", () => {
    const [result] = transformVault([
      {
        id: "vault:notes:regular",
        title: "Regular note",
        description: "A saved note",
        hub: "workspace",
        path: "/vault/notes/regular.md",
        file_type: "md",
        metadata: {
          journey_category: "notes",
          "x-augur-note-type": "url",
          canonical_url: "https://example.com",
        },
      },
    ]);

    expect(result.metadata?.noteState).toBeUndefined();
  });

  it("does not classify inactive vault records from URL metadata alone", () => {
    const [result] = transformVault([
      {
        id: "vault:inactive:codex",
        title: "Inactive URL",
        description: "Inactive record",
        hub: "workspace",
        path: "/vault/notes/inactive-codex.md",
        file_type: "md",
        metadata: {
          inactive_scope: "true",
          url: "https://github.com/openai/codex",
        },
      },
    ]);

    expect(result.metadata?.noteDomain).toBeUndefined();
    expect(result.metadata?.noteSource).toBeUndefined();
    expect(result.metadata?.noteStatus).toBeUndefined();
    expect(result.metadata?.classificationConfidence).toBeUndefined();
    expect(result.metadata?.needsClassification).toBeUndefined();
  });

  it("preserves generic source metadata while adding note-specific source classification", () => {
    const [result] = transformVault([
      {
        id: "vault:notes:codex-source",
        title: "Codex",
        description: "GitHub repo",
        hub: "workspace",
        path: "/vault/notes/codex-source.md",
        file_type: "md",
        metadata: {
          source: "private-vault",
          "x-augur-note-type": "url",
          canonical_url: "https://github.com/openai/codex",
        },
      },
    ]);

    expect(result.metadata?.source).toBe("private-vault");
    expect(result.metadata?.noteSource).toBe("github");
    expect(result.metadata).toMatchObject({
      noteType: "url",
      noteDomain: "projects",
      noteStatus: "saved",
      classificationConfidence: "high",
      needsClassification: "false",
    });
  });

  it("preserves sweep archive metadata from vault archive entries", () => {
    const result = transformVault([
      {
        id: "sweep:docs:run:old.zip",
        title: "old.zip",
        description: "superseded",
        hub: "system",
        source_path: "/docs/.archive/old.zip",
        metadata: {
          journey_category: "archive",
          archive_source: "sweep",
          archive_mode: "docs-archive",
          recovery_hint: "Move the file out of .archive.",
        },
      },
    ]);

    expect(result[0].path).toBe("/docs/.archive/old.zip");
    expect(result[0].typeBadge).toBe("docs-archive");
    expect(result[0].metadata).toMatchObject({
      archive_source: "sweep",
      archive_mode: "docs-archive",
      recovery_hint: "Move the file out of .archive.",
    });
  });
});

// ---------------------------------------------------------------------------
// transformIntegrations
// ---------------------------------------------------------------------------
describe("transformIntegrations", () => {
  const input = [
    { id: "career/google/Google Calendar", title: "Google Calendar", description: "Calendar sync", hub: "career", path: "/project-brain/capabilities/skills/google/SKILL.md", scope: "remote", status: "available" },
  ];

  it("returns an array of BrowseItems", () => {
    const result = transformIntegrations(input);
    expect(Array.isArray(result)).toBe(true);
    expect(result).toHaveLength(1);
    expectValidBrowseItem(result[0]);
  });

  it("sets primaryAction.type to run-action", () => {
    const result = transformIntegrations(input);
    expect(result[0].primaryAction.type).toBe("run-action");
  });
});

// ---------------------------------------------------------------------------
// transformPrompts
// ---------------------------------------------------------------------------
describe("transformPrompts", () => {
  const input = [
    { id: "career/reports/prompts/generate", title: "Generate", description: "Prompt for career", hub: "career", path: "/project-brain/capabilities/skills/reports/prompts/generate.md" },
  ];

  it("returns an array of BrowseItems", () => {
    const result = transformPrompts(input);
    expect(Array.isArray(result)).toBe(true);
    expect(result).toHaveLength(1);
    expectValidBrowseItem(result[0]);
  });

  it("sets primaryAction.type to open-file", () => {
    const result = transformPrompts(input);
    expect(result[0].primaryAction.type).toBe("open-file");
  });
});

// ---------------------------------------------------------------------------
// transformCommands
// ---------------------------------------------------------------------------
describe("transformCommands", () => {
  const input = [
    { id: "/dev-build", title: "/dev-build", description: "Rebuild dashboard", hub: "dev", path: "/project-brain/capabilities/skills/platform-admin/commands/dev-build.md", category: "DEV" },
  ];

  it("returns an array of BrowseItems", () => {
    const result = transformCommands(input);
    expect(Array.isArray(result)).toBe(true);
    expect(result).toHaveLength(1);
    expectValidBrowseItem(result[0]);
  });

  it("sets primaryAction.type to copy", () => {
    const result = transformCommands(input);
    expect(result[0].primaryAction.type).toBe("copy");
  });
});

// ---------------------------------------------------------------------------
// transformAgents
// ---------------------------------------------------------------------------
describe("transformAgents", () => {
  const input = [
    { id: "config/agents/researcher", title: "Researcher", description: "Research agent", hub: "system", path: "/config/agents/researcher.yaml", tier: "medium", mode: "auto" },
  ];

  it("returns an array of BrowseItems", () => {
    const result = transformAgents(input);
    expect(Array.isArray(result)).toBe(true);
    expect(result).toHaveLength(1);
    expectValidBrowseItem(result[0]);
  });

  it("sets primaryAction.type to open-file", () => {
    const result = transformAgents(input);
    expect(result[0].primaryAction.type).toBe("open-file");
  });
});

// ---------------------------------------------------------------------------
// transformAdrs
// ---------------------------------------------------------------------------
describe("transformAdrs", () => {
  const input = [
    { id: "adr-414", title: "ADR-414: Browse Expansion", description: "Expand browse", hub: "core", path: "/tmp/test-brain/decisions/adrs/ADR-414.md", status: "Implemented", date: "2026-03-14", adr_number: "414" },
  ];

  it("returns an array of BrowseItems", () => {
    const result = transformAdrs(input);
    expect(Array.isArray(result)).toBe(true);
    expect(result).toHaveLength(1);
    expectValidBrowseItem(result[0]);
  });

  it("sets primaryAction.type to open-file for live ADRs", () => {
    const result = transformAdrs(input);
    expect(result[0].primaryAction.type).toBe("open-file");
    expect(result[0].metadata?.archived).toBeUndefined();
  });

  // ADR-608 Phase 2: archived ADRs need an extract step before opening.
  it("uses extract-and-open-adr for archived entries", () => {
    const result = transformAdrs([
      {
        id: "adr-042",
        title: "ADR-042: Hitchhiker",
        description: "",
        hub: "core",
        path: "archive://ADR-042",
        status: "Implemented",
        date: "2025-02-02",
        adr_number: "042",
        archived: true,
      },
    ]);
    expect(result[0].primaryAction.type).toBe("extract-and-open-adr");
    expect(result[0].primaryAction.target).toBe("ADR-042");
    expect(result[0].metadata?.archived).toBe("true");
  });

  it("normalises bare numeric adr_number to padded ADR-NNN target", () => {
    const result = transformAdrs([
      {
        id: "adr-7",
        title: "ADR-7: Tiny",
        description: "",
        hub: "core",
        path: "archive://ADR-007",
        status: "Implemented",
        date: "2025-01-01",
        adr_number: "7",
        archived: true,
      },
    ]);
    expect(result[0].primaryAction.target).toBe("ADR-007");
  });

  // ADR-642: live entries that come straight from the central JSON index have
  // no on-disk path; they surface with an index://ADR-NNN synthetic path and
  // must use extract-and-open-adr to render the JSON entry inline.
  it("uses extract-and-open-adr for live entries with index:// path", () => {
    const result = transformAdrs([
      {
        id: "adr-471",
        title: "ADR-471: Project Framework",
        description: "Project framework",
        hub: "core",
        path: "index://ADR-471",
        status: "Accepted",
        date: "2026-03-22",
        adr_number: "471",
        archived: false,
      },
    ]);
    expect(result[0].primaryAction.type).toBe("extract-and-open-adr");
    expect(result[0].primaryAction.target).toBe("ADR-471");
    expect(result[0].metadata?.archived).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// transformTests
// ---------------------------------------------------------------------------
describe("transformTests", () => {
  const input = [
    { id: "dev/browse/tests/test.py", title: "test_browse", description: "pytest test", hub: "dev", path: "/tests/test_browse.py", test_type: "pytest" },
  ];

  it("returns an array of BrowseItems", () => {
    const result = transformTests(input);
    expect(Array.isArray(result)).toBe(true);
    expect(result).toHaveLength(1);
    expectValidBrowseItem(result[0]);
  });

  it("sets primaryAction.type to run-action", () => {
    const result = transformTests(input);
    expect(result[0].primaryAction.type).toBe("run-action");
  });
});

// ---------------------------------------------------------------------------
// transformApiRoutes
// ---------------------------------------------------------------------------
describe("transformApiRoutes", () => {
  const input = [
    { id: "/api/browse/vault", title: "/api/browse/vault", description: "GET endpoint", hub: "system", path: "/apps/dashboard/app/api/browse/vault/route.ts", methods: ["GET"] },
  ];

  it("returns an array of BrowseItems", () => {
    const result = transformApiRoutes(input);
    expect(Array.isArray(result)).toBe(true);
    expect(result).toHaveLength(1);
    expectValidBrowseItem(result[0]);
  });

  it("sets primaryAction.type to run-action", () => {
    const result = transformApiRoutes(input);
    expect(result[0].primaryAction.type).toBe("run-action");
  });
});

// ---------------------------------------------------------------------------
// transformScripts
// ---------------------------------------------------------------------------
describe("transformScripts", () => {
  const input = [
    { id: "admin/scripts/scan.py", title: "scan", description: "Python script", hub: "admin", path: "/plugins/admin/scripts/scan.py", language: "Python" },
  ];

  it("returns an array of BrowseItems", () => {
    const result = transformScripts(input);
    expect(Array.isArray(result)).toBe(true);
    expect(result).toHaveLength(1);
    expectValidBrowseItem(result[0]);
  });

  it("sets primaryAction.type to run-mcp", () => {
    const result = transformScripts(input);
    expect(result[0].primaryAction.type).toBe("run-mcp");
  });
});
