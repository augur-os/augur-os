import { buildBrowseCardModel, visibleCardMetadataRows } from "@/lib/browse/cardModel";
import type { BrowseItem, ViewMode } from "@/lib/browse/types";

function item(overrides: Partial<BrowseItem> = {}): BrowseItem {
  return {
    id: "item-1",
    title: "Item One",
    description: "A browse item",
    icon: "Box",
    path: "project-brain/capabilities/skills/item/SKILL.md",
    primaryAction: { label: "Open", type: "open-file", target: "project-brain/capabilities/skills/item/SKILL.md" },
    ...overrides,
  };
}

function modelFor(overrides: Partial<BrowseItem>, viewMode: ViewMode) {
  return buildBrowseCardModel(item(overrides), { viewMode });
}

describe("buildBrowseCardModel", () => {
  it("maps skill ownership, setup, master client, capability, and quality tier signals", () => {
    const source = item({
      id: "skill:shared:knowledge",
      title: "Knowledge",
      description: "Search and organize memory",
      hub: "workspace",
      icon: "Puzzle",
      metadata: {
        ownership: "augur",
        needsSetup: "true",
        masterClient: "codex",
        capabilityId: "knowledge-search",
        qualityTier: "B",
        qualityScore: "71.5",
      },
      actions: [{ id: "docs", label: "Docs", type: "navigate", target: "/browse/knowledge" }],
    });

    const model = buildBrowseCardModel(source, { viewMode: "skills" });

    expect(model).toMatchObject({
      id: "skill:shared:knowledge",
      title: "Knowledge",
      description: "Search and organize memory",
      icon: "Puzzle",
      path: "project-brain/capabilities/skills/item/SKILL.md",
      rawItem: source,
    });
    expect(model.badges).toEqual([
      { id: "ownership", label: "Managed", tone: "info" },
      { id: "client-codex", label: "Codex", tone: "neutral" },
      { id: "needs-setup", label: "needs setup", tone: "warning" },
      { id: "quality", label: "Quality B 71.5", tone: "success" },
      { id: "capability", label: "knowledge-search" },
    ]);
    expect(model.metadataRows).toEqual([
      { label: "Ownership", value: "Managed" },
      { label: "Client", value: "Codex" },
      { label: "Setup", value: "needs setup" },
      { label: "Quality", value: "Quality B 71.5" },
      { label: "Capability", value: "knowledge-search" },
    ]);
    expect(model.detailSections).toContainEqual({
      id: "skills",
      title: "Skill signals",
      rows: [
        { label: "Ownership", value: "Managed" },
        { label: "Client", value: "Codex" },
        { label: "Setup", value: "needs setup" },
        { label: "Quality", value: "Quality B 71.5" },
        { label: "Capability", value: "knowledge-search" },
      ],
    });
    expect(model.overflowActions).toEqual(expect.arrayContaining(source.actions!));
    expect(model.overflowActions).not.toBe(source.actions);
  });

  it("preserves helper-derived skill identity and state badges in the shared model", () => {
    const model = buildBrowseCardModel(
      item({
        id: "private-skill",
        title: "Private Skill",
        hub: "workspace",
        metadata: {
          enabled: "false",
          coverageIssueCount: "2",
          coverageLabel: "2 missing exports",
          coverageTone: "danger",
          coverageSummary: "Missing generated wrappers",
          updateAvailable: "true",
          mcpToolCount: "3",
          actionCount: "4",
          pageCount: "1",
          skillClients: "codex,gemini",
          masterClient: "claude",
          skillType: "workflow",
          vault_scope: "private",
          promotion_state: "private",
          ownership: "user",
        },
      }),
      { viewMode: "skills" },
    );

    expect(model.badges).toEqual(
      expect.arrayContaining([
        { id: "overlay-private", label: "Private", tone: "info" },
        { id: "ownership", label: "User", tone: "info" },
        { id: "client-codex", label: "Codex", tone: "neutral" },
        { id: "client-gemini", label: "Gemini", tone: "neutral" },
        { id: "skill-type", label: "workflow", tone: "neutral" },
        { id: "enabled", label: "disabled", tone: "neutral" },
        { id: "coverage", label: "2 missing exports", tone: "danger" },
        { id: "update", label: "update available", tone: "warning" },
        { id: "tools", label: "3 tools", tone: "neutral" },
        { id: "actions", label: "4 actions", tone: "neutral" },
        { id: "pages", label: "1 page", tone: "neutral" },
      ]),
    );
    expect(model.metadataRows).toEqual(
      expect.arrayContaining([
        { label: "Scope", value: "Private" },
        { label: "Ownership", value: "User" },
        { label: "Client", value: "Codex" },
        { label: "Client", value: "Gemini" },
        { label: "Skill type", value: "workflow" },
        { label: "State", value: "disabled" },
        { label: "Coverage", value: "2 missing exports" },
        { label: "Update", value: "update available" },
        { label: "Tools", value: "3 tools" },
        { label: "Actions", value: "4 actions" },
        { label: "Pages", value: "1 page" },
      ]),
    );
  });

  it("preserves skill taxonomy tags in the shared skill model", () => {
    const model = buildBrowseCardModel(
      item({
        id: "tagged-skill",
        title: "Tagged Skill",
        hub: "workspace",
        metadata: {
          ownership: "augur",
          skillClients: "codex",
          skillType: "domain",
          skillTags: "memory,search",
        },
      }),
      { viewMode: "skills" },
    );

    expect(model.badges).toEqual(
      expect.arrayContaining([
        { id: "skill-tag-memory", label: "memory", tone: "info" },
        { id: "skill-tag-search", label: "search", tone: "info" },
      ]),
    );
    expect(model.metadataRows).toEqual(
      expect.arrayContaining([
        { label: "Tag", value: "memory" },
        { label: "Tag", value: "search" },
      ]),
    );
  });

  // Rule 32 (ADR-813): demo runbooks ride the owning skill's card.
  it("surfaces a demos badge and row from skills-index demos metadata", () => {
    const model = buildBrowseCardModel(
      item({
        id: "skill:project-brain:ingest",
        title: "Ingest",
        hub: "brain",
        metadata: {
          ownership: "augur",
          demos:
            "Wiki Llm Cross Agent Ask|project-brain/capabilities/skills/ingest/demos/demo_01_wiki_llm_cross_agent_ask.md," +
            "Compound Dry Run|project-brain/capabilities/skills/ingest/demos/demo_04_compound_dry_run.md",
        },
      }),
      { viewMode: "skills" },
    );

    expect(model.badges).toEqual(
      expect.arrayContaining([{ id: "demos", label: "2 demos", tone: "info" }]),
    );
    expect(model.metadataRows).toEqual(
      expect.arrayContaining([{ label: "Demos", value: "2" }]),
    );
  });

  it("adds no demos badge when the skill has no demos metadata", () => {
    const model = buildBrowseCardModel(
      item({
        id: "skill:project-brain:knowledge",
        title: "Knowledge",
        hub: "brain",
        metadata: { ownership: "augur" },
      }),
      { viewMode: "skills" },
    );

    expect(model.badges.some((badge) => badge.id === "demos")).toBe(false);
    expect(model.metadataRows.some((row) => row.label === "Demos")).toBe(false);
  });

  it("maps command quality and KPI signals onto existing browse card metadata", () => {
    const model = modelFor(
      {
        id: "command:ask",
        title: "/ask",
        hub: "command",
        metadata: {
          qualityTier: "A",
          qualityScore: "88",
          docsScore: "80",
          wiringScore: "100",
          kpiStatus: "pass",
        },
      },
      "commands",
    );

    expect(model.badges).toEqual(
      expect.arrayContaining([
        { id: "quality", label: "Quality A 88", tone: "success" },
        { id: "kpi", label: "KPI ✓", tone: "success" },
      ]),
    );
    expect(model.metadataRows).toEqual(
      expect.arrayContaining([
        { label: "Quality", value: "Quality A 88" },
        { label: "Docs", value: "80" },
        { label: "Wiring", value: "100" },
        { label: "KPI", value: "pass" },
      ]),
    );
  });

  it("shows document sync and attachment badges", () => {
    const model = modelFor(
      {
        id: "architecture",
        title: "Architecture Overview",
        description: "Catalog summary used on cards.",
        path: "/cache/architecture.pdf",
        metadata: {
          provider: "google-drive",
          indexStatus: "source_changed",
          attachedBrainIds: "project-y,personal",
          catalogSummary: "Catalog summary used on cards.",
        },
      },
      "documents",
    );

    expect(model.description).toBe("Catalog summary used on cards.");
    expect(model.badges.map((badge) => badge.label)).toEqual(
      expect.arrayContaining(["Google Drive", "Source changed", "2 folders"]),
    );
    expect(model.detailSections.flatMap((section) => section.rows)).toEqual(
      expect.arrayContaining([
        { label: "Attached to", value: "project-y, personal" },
        { label: "Index status", value: "Source changed" },
      ]),
    );
  });

  it("preserves note type, tags, source, and enrichment signals on note cards", () => {
    jest.useFakeTimers().setSystemTime(Date.parse("2026-05-20T12:00:00Z"));
    try {
      const model = modelFor(
        {
          id: "note:url:karpathy",
          title: "Karpathy AI Maker",
          hub: "workspace",
          typeBadge: "url",
          tags: ["ai", "reading"],
          metadata: {
            noteType: "url",
            source_domain: "karpathy.ai",
            enrichment_status: "queued",
            modified: "2026-05-16T10:00:00Z",
          },
        },
        "notes",
      );

      expect(model.badges).toEqual(
        expect.arrayContaining([
          { id: "note-type-url", label: "URL", tone: "note-url", icon: "Link" },
          { id: "tag-ai", label: "ai", tone: "info" },
          { id: "tag-reading", label: "reading", tone: "info" },
          { id: "enrichment", label: "queued", tone: "warning" },
        ]),
      );
      expect(model.badges).not.toContainEqual({ id: "type", label: "url", tone: "neutral" });
      expect(model.metadataRows).toEqual(
        expect.arrayContaining([
          { label: "Type", value: "URL" },
          { label: "Source", value: "Website" },
          { label: "Source domain", value: "karpathy.ai" },
          { label: "Enrichment", value: "queued" },
          { label: "Modified", value: "4d ago" },
        ]),
      );
    } finally {
      jest.useRealTimers();
    }
  });

  it("uses normalized note classification for note card badges and rows", () => {
    const model = modelFor(
      {
        id: "note:url:github-project",
        title: "GitHub Project",
        hub: "workspace",
        typeBadge: "url",
        metadata: {
          noteType: "url",
          noteDomain: "projects",
          noteSource: "github",
          noteStatus: "evaluating",
          classificationConfidence: "high",
          source_domain: "github.com",
        },
      },
      "notes",
    );

    expect(model.badges.slice(0, 4).map((badge) => badge.label)).toEqual([
      "URL",
      "Project",
      "GitHub",
      "Evaluating",
    ]);
    expect(model.metadataRows).toEqual(
      expect.arrayContaining([
        { label: "Type", value: "URL" },
        { label: "Domain", value: "Project" },
        { label: "Source", value: "GitHub" },
        { label: "Status", value: "Evaluating" },
        { label: "Confidence", value: "high" },
        { label: "Source domain", value: "github.com" },
      ]),
    );
  });

  it("orders low-confidence note classification badges before needs-classification", () => {
    const model = modelFor(
      {
        id: "note:url:evaluating-project",
        title: "Evaluating Project URL",
        hub: "workspace",
        typeBadge: "url",
        metadata: {
          noteType: "url",
          noteDomain: "projects",
          noteSource: "github",
          noteStatus: "evaluating",
          classificationConfidence: "low",
          needsClassification: "true",
        },
      },
      "notes",
    );

    expect(model.badges.slice(0, 5).map((badge) => badge.label)).toEqual([
      "URL",
      "Project",
      "GitHub",
      "Evaluating",
      "Needs classification",
    ]);
  });

  it("keeps generic url records in notes view on common card slots without explicit note metadata", () => {
    const model = modelFor(
      {
        id: "archive:url:old",
        title: "Archived URL",
        hub: "workspace",
        typeBadge: "url",
        metadata: {
          source_domain: "github.com",
          url: "https://github.com/openai/codex",
        },
      },
      "notes",
    );

    expect(model.badges.some((badge) =>
      badge.id.startsWith("note-type-") ||
      badge.id.startsWith("note-domain-") ||
      badge.id.startsWith("note-source-") ||
      badge.id.startsWith("note-status-"),
    )).toBe(false);
    expect(model.badges).toContainEqual({ id: "type", label: "url", tone: "neutral" });
    expect(model.metadataRows).toEqual(
      expect.arrayContaining([
        { label: "Type", value: "url" },
        { label: "Source", value: "github.com" },
      ]),
    );
    expect(model.metadataRows).not.toContainEqual({ label: "Source domain", value: "github.com" });
  });

  it("does not classify generic notes-view records when needsClassification is false", () => {
    const model = modelFor(
      {
        id: "archive:url:false-needs-classification",
        title: "Archived URL",
        hub: "workspace",
        typeBadge: "url",
        metadata: {
          needsClassification: "false",
          url: "https://github.com/openai/codex",
        },
      },
      "notes",
    );

    expect(model.badges.some((badge) =>
      badge.id.startsWith("note-type-") ||
      badge.id.startsWith("note-domain-") ||
      badge.id.startsWith("note-source-") ||
      badge.id.startsWith("note-status-") ||
      badge.id === "note-needs-classification",
    )).toBe(false);
    expect(model.badges).toContainEqual({ id: "type", label: "url", tone: "neutral" });
  });

  it("keeps synthesized classification-only records generic without an explicit note marker", () => {
    const model = modelFor(
      {
        id: "archive:url:synthesized-classification",
        title: "Synthesized Classification URL",
        hub: "workspace",
        typeBadge: "url",
        metadata: {
          noteDomain: "projects",
          noteSource: "github",
          classificationConfidence: "high",
          url: "https://github.com/openai/codex",
        },
      },
      "notes",
    );

    expect(model.badges.some((badge) =>
      badge.id.startsWith("note-type-") ||
      badge.id.startsWith("note-domain-") ||
      badge.id.startsWith("note-source-") ||
      badge.id.startsWith("note-status-"),
    )).toBe(false);
    expect(model.badges).toContainEqual({ id: "type", label: "url", tone: "neutral" });
    expect(model.metadataRows).toEqual(
      expect.arrayContaining([
        { label: "Type", value: "url" },
      ]),
    );
    expect(model.metadataRows).not.toContainEqual({ label: "Type", value: "URL" });
  });

  it("preserves generic provenance separately from note classification source", () => {
    const model = modelFor(
      {
        id: "note:url:private-vault-project",
        title: "Private Vault Project",
        hub: "workspace",
        typeBadge: "url",
        metadata: {
          noteType: "url",
          noteDomain: "projects",
          noteSource: "github",
          noteStatus: "evaluating",
          source: "private-vault",
        },
      },
      "notes",
    );

    expect(model.metadataRows).toEqual(
      expect.arrayContaining([
        { label: "Source", value: "GitHub" },
        { label: "Provenance", value: "private-vault" },
      ]),
    );
  });

  it("preserves problem and skill tag signals on classified note cards", () => {
    const model = modelFor(
      {
        id: "note:url:problem-tagged-project",
        title: "Problem Tagged Project",
        hub: "workspace",
        typeBadge: "url",
        metadata: {
          noteType: "url",
          noteDomain: "projects",
          noteSource: "github",
          inventory_source: "ai-artifact-inventory",
          problem_tags: "unknown_source",
          problem_evidence: '[{"id":"unknown_source","reason":"Scanner warning: unknown_source"}]',
          skillTags: "memory,search",
        },
      },
      "notes",
    );

    expect(model.badges).toEqual(
      expect.arrayContaining([
        { id: "note-type-url", label: "URL", tone: "note-url", icon: "Link" },
        { id: "note-domain-projects", label: "Project", tone: "info" },
        { id: "note-source-github", label: "GitHub", tone: "info" },
        { id: "problem-unknown_source", label: "Unknown source", tone: "warning" },
        { id: "skill-tag-memory", label: "memory", tone: "info" },
        { id: "skill-tag-search", label: "search", tone: "info" },
      ]),
    );
    expect(model.metadataRows).toEqual(
      expect.arrayContaining([
        { label: "Type", value: "URL" },
        { label: "Domain", value: "Project" },
        { label: "Source", value: "GitHub" },
        { label: "Problems", value: "1" },
        { label: "Tag", value: "memory" },
        { label: "Tag", value: "search" },
      ]),
    );
  });

  it.each([
    ["url", "URL", "note-url", "Link"],
    ["file", "File", "note-file", "FileText"],
    ["thought", "Thought", "note-thought", "Lightbulb"],
    ["voice-memo", "Voice Memo", "note-voice-memo", "Mic"],
    ["meeting", "Meeting", "note-meeting", "Users"],
    ["image", "Image", "note-image", "Image"],
    ["prompt", "Prompt", "note-prompt", "MessageSquare"],
  ])(
    "emits a colored chip for note type %s (label=%s tone=%s icon=%s)",
    (rawType, label, tone, icon) => {
      const model = modelFor(
        {
          id: `note:${rawType}:sample`,
          title: `Sample ${label}`,
          hub: "workspace",
          metadata: { "x-augur-note-type": rawType },
        },
        "notes",
      );

      expect(model.badges).toContainEqual({
        id: `note-type-${rawType}`,
        label,
        tone,
        icon,
      });
    },
  );

  it("normalizes audio/voice aliases onto the voice-memo chip", () => {
    for (const alias of ["audio", "voice", "AUDIO"]) {
      const model = modelFor(
        {
          id: `note:audio:${alias}`,
          title: "Memo",
          hub: "workspace",
          metadata: { noteType: alias },
        },
        "notes",
      );
      expect(model.badges).toContainEqual({
        id: "note-type-voice-memo",
        label: "Voice Memo",
        tone: "note-voice-memo",
        icon: "Mic",
      });
    }
  });

  it("falls back to the generic neutral type badge when item has no note type", () => {
    const model = modelFor(
      {
        id: "wiki:concept:foo",
        title: "Foo",
        hub: "workspace",
        typeBadge: "Concept",
      },
      "wiki",
    );

    expect(model.badges).toContainEqual({ id: "type", label: "Concept", tone: "neutral" });
    expect(model.badges.some((badge) => badge.id.startsWith("note-type-"))).toBe(false);
  });

  it("preserves page tags for generic tagged browse cards", () => {
    const model = modelFor(
      {
        id: "wiki:concept:adaptive-loop",
        title: "Adaptive Loop",
        hub: "workspace",
        typeBadge: "Concept",
        tags: ["adaptive", "loop"],
        metadata: {
          pageTags: "maintenance,surfaces",
          vault_scope: "private",
          promotion_state: "private",
          modified: "2026-05-14T22:24:16Z",
        },
      },
      "wiki",
    );

    expect(model.badges).toEqual(
      expect.arrayContaining([
        { id: "type", label: "Concept", tone: "neutral" },
        { id: "overlay-private", label: "Private", tone: "info" },
        { id: "tag-maintenance", label: "maintenance", tone: "info" },
        { id: "tag-surfaces", label: "surfaces", tone: "info" },
      ]),
    );
    expect(model.metadataRows).toEqual(
      expect.arrayContaining([
        { label: "Type", value: "Concept" },
        { label: "Scope", value: "Private" },
        { label: "Tag", value: "maintenance" },
        { label: "Tag", value: "surfaces" },
      ]),
    );
  });

  it("surfaces wiki maintenance freshness on the current card model", () => {
    const model = modelFor(
      {
        id: "wiki:private:concepts/wiki-freshness",
        title: "Wiki Freshness",
        typeBadge: "Concept",
        metadata: {
          pageTags: "source-coverage",
          wikiMaintenanceState: "no-apply",
          wikiPendingSources: "2080",
          wikiSourceTotal: "2265",
          wikiLastReindexedAt: "2026-06-07T05:39:22.565188+00:00",
          wikiLastBatchQuality: "weak",
          wikiLastBatchReason:
            "258/300 low-signal sources; reindex refreshed Browse but no wiki pages were applied.",
        },
      },
      "wiki",
    );

    expect(model.badges).toEqual(
      expect.arrayContaining([
        { id: "wiki-maintenance", label: "no apply", tone: "warning" },
        { id: "wiki-pending", label: "2080 pending", tone: "neutral" },
        { id: "wiki-reindexed", label: "reindexed", tone: "success" },
        { id: "wiki-batch-quality", label: "batch weak", tone: "warning" },
      ]),
    );
    expect(model.metadataRows).toEqual(
      expect.arrayContaining([
        { label: "Maintenance", value: "No Apply" },
        { label: "Pending sources", value: "2080 / 2265" },
        { label: "Batch quality", value: "Weak" },
        {
          label: "Batch reason",
          value: "258/300 low-signal sources; reindex refreshed Browse but no wiki pages were applied.",
        },
      ]),
    );
  });

  it("suppresses placeholder RAG metadata on search-result cards", () => {
    const model = modelFor(
      {
        id: "rag:investor-pitch-2026-04-27",
        title: "investor pitch 2026 04 27",
        description: "Graph entity tier 2: investor-pitch-2026-04-27",
        hub: "rag",
        typeBadge: "rag",
        tags: ["rag"],
        metadata: {
          source: "investor-pitch-2026-04-27",
        },
      },
      "agent-profiles",
    );

    expect(model.badges).not.toContainEqual(
      expect.objectContaining({ label: "rag" }),
    );
    expect(model.metadataRows).not.toEqual(
      expect.arrayContaining([
        { label: "Type", value: "rag" },
        { label: "Tag", value: "rag" },
      ]),
    );
    expect(model.metadataRows).toContainEqual({
      label: "Source",
      value: "investor-pitch-2026-04-27",
    });
  });

  it("suppresses RAG placeholder type and tag rows", () => {
    const model = modelFor(
      {
        id: "rag:inbox:personal-ai-os",
        title: "2026 04 25 find top personal ai os",
        typeBadge: "rag",
        tags: ["rag"],
      },
      "agent-profiles",
    );

    expect(model.badges).not.toContainEqual(expect.objectContaining({ label: "rag" }));
    expect(model.metadataRows).not.toContainEqual({ label: "Type", value: "rag" });
    expect(model.metadataRows).not.toContainEqual({ label: "Tag", value: "rag" });
  });

  it("derives skill primary actions for disabled, low-quality, and dashboard skills", () => {
    expect(
      buildBrowseCardModel(
        item({ id: "disabled-skill", metadata: { enabled: "false" } }),
        { viewMode: "skills" },
      ).primaryAction,
    ).toEqual({
      label: "Enable",
      type: "run-mcp",
      target: "enable-skill:disabled-skill",
    });

    expect(
      buildBrowseCardModel(
        item({
          id: "low-quality-skill",
          metadata: { ownership: "augur", qualityTier: "D", qualityScore: "24" },
        }),
        { viewMode: "skills" },
      ).primaryAction,
    ).toEqual({
      label: "Improve",
      type: "run-action",
      target: "/harden low-quality-skill",
    });

    expect(
      buildBrowseCardModel(
        item({
          id: "dashboard-skill",
          metadata: { ownership: "augur", dashboardPath: "/workspace/dashboard-skill" },
        }),
        { viewMode: "skills" },
      ).primaryAction,
    ).toEqual({
      label: "Open",
      type: "navigate",
      target: "/workspace/dashboard-skill",
    });
  });

  it("derives skill overflow actions and deduplicates existing item actions", () => {
    const model = buildBrowseCardModel(
      item({
        id: "private-skill",
        title: "Private Skill",
        path: "/Users/example/Au-vault/private/skills/private-skill/SKILL.md",
        metadata: {
          ownership: "augur",
          dashboardPath: "/workspace/private-skill",
          vault_scope: "private",
          promotion_state: "private",
        },
        actions: [
          {
            id: "docs-private-skill",
            label: "Open docs",
            type: "navigate",
            target: "/browse/private-skill",
          },
          {
            id: "custom-open-page",
            label: "Open dashboard page",
            type: "navigate",
            target: "/workspace/private-skill",
          },
          {
            id: "custom-action",
            label: "Custom action",
            type: "run-action",
            target: "custom-action",
            args: { nested: { count: 1 } },
          },
        ],
      }),
      { viewMode: "skills" },
    );

    expect(model.overflowActions.map((action) => action.label)).toEqual([
      "Open File",
      "Reveal in Finder",
      "Copy Path",
      "Open docs",
      "Open dashboard page",
      "Configure",
      "Improve",
      "Sync/export",
      "Promote",
      "Disable",
      "Remove",
      "Custom action",
    ]);
    expect(model.overflowActions.filter((action) => action.label === "Open docs")).toHaveLength(1);
    expect(model.overflowActions.filter((action) => action.label === "Open dashboard page")).toHaveLength(1);
    expect(model.overflowActions).toContainEqual(expect.objectContaining({
      label: "Promote",
      type: "mcp-tool",
      target: "promote-browse-item",
    }));

    const customAction = model.overflowActions.find((action) => action.id === "custom-action");
    expect(customAction?.args).toEqual({ nested: { count: 1 } });
    expect(customAction?.args).not.toBe(model.rawItem.actions?.[2].args);
  });

  it("maps background routine cadence/status badges and next/last/token metadata", () => {
    const model = modelFor(
      {
        id: "routine:insight-scanner",
        title: "Insight Scanner",
        icon: undefined,
        metadata: {
          cadence: "every 30 minutes",
          status: "enabled",
          nextRun: "2026-05-17T08:00:00Z",
          lastRun: "2026-05-17T07:30:00Z",
          token_cost: "1200",
        },
      },
      "background-routines",
    );

    expect(model.icon).toBe("FileText");
    expect(model.badges).toEqual([
      { id: "cadence", label: "every 30 minutes" },
      { id: "status", label: "enabled", tone: "success" },
    ]);
    expect(model.metadataRows).toEqual([
      { label: "Cadence", value: "every 30 minutes" },
      { label: "Status", value: "enabled" },
      { label: "Next run", value: "2026-05-17T08:00:00Z" },
      { label: "Last run", value: "2026-05-17T07:30:00Z" },
      { label: "Tokens", value: "1200" },
    ]);
  });

  it("defensively copies primary and overflow action args", () => {
    const source = item({
      primaryAction: {
        label: "Run",
        type: "run-action",
        target: "run-skill",
        args: { mode: "source", nested: { count: 1 } },
      },
      actions: [
        {
          id: "configure",
          label: "Configure",
          type: "run-mcp",
          target: "configure-skill",
          args: { mode: "source", nested: { count: 1 } },
        },
      ],
    });

    const model = buildBrowseCardModel(source, { viewMode: "api-routes" });

    const configureAction = model.overflowActions.find((action) => action.id === "configure");
    expect(configureAction).toBeDefined();
    expect(configureAction).not.toBe(source.actions![0]);
    expect(configureAction?.args).not.toBe(source.actions![0].args);
    expect(model.primaryAction).not.toBe(source.primaryAction);
    expect(model.primaryAction.args).not.toBe(source.primaryAction.args);

    configureAction!.args!.mode = "model";
    (configureAction!.args!.nested as { count: number }).count = 2;
    model.primaryAction.args!.mode = "model";
    (model.primaryAction.args!.nested as { count: number }).count = 2;

    expect(source.actions![0].args).toEqual({ mode: "source", nested: { count: 1 } });
    expect(source.primaryAction.args).toEqual({ mode: "source", nested: { count: 1 } });
  });

  it("maps MCP server runtime, tier, clients, PID, and manifest metadata", () => {
    const model = modelFor(
      {
        id: "augur-apple",
        title: "augur-apple",
        typeBadge: "runtime",
        path: "config/system/mcp_servers.yaml",
        metadata: {
          runtimeStatus: "stale-running",
          tier: "runtime",
          clients: "codex,claude",
          pid: "202",
          manifestPath: "config/system/mcp_servers.yaml",
          bundle: "apple",
          command: "python -m augur_shared.bundle_server apple",
        },
      },
      "mcp-servers",
    );

    expect(model.badges).toEqual(
      expect.arrayContaining([
        { id: "runtimeStatus", label: "stale-running", tone: "warning" },
        { id: "tier", label: "runtime" },
        { id: "clients", label: "codex,claude" },
      ]),
    );
    expect(model.metadataRows).toEqual(
      expect.arrayContaining([
        { label: "Runtime", value: "stale-running" },
        { label: "Tier", value: "runtime" },
        { label: "Clients", value: "codex,claude" },
        { label: "PID", value: "202" },
        { label: "Manifest", value: "config/system/mcp_servers.yaml" },
        { label: "Bundle", value: "apple" },
      ]),
    );
  });

  it("maps API route method, hub, route, and source path metadata", () => {
    const model = modelFor(
      {
        id: "/api/browse/items",
        title: "/api/browse/items",
        hub: "dev",
        typeBadge: "GET, POST",
        path: "apps/dashboard/app/api/browse/items/route.ts",
        metadata: {
          method: "GET",
          route: "/api/browse/items",
          source_path: "apps/dashboard/app/api/browse/items/route.ts",
        },
      },
      "api-routes",
    );

    expect(model.badges).toEqual(
      expect.arrayContaining([
        { id: "methods", label: "GET" },
      ]),
    );
    expect(model.metadataRows).toEqual(
      expect.arrayContaining([
        { label: "Method", value: "GET" },
        { label: "Route", value: "/api/browse/items" },
        { label: "Source", value: "apps/dashboard/app/api/browse/items/route.ts" },
      ]),
    );
  });

});

describe("visibleCardMetadataRows", () => {
  it("drops rows whose value is already shown as a badge, keeping additive rows", () => {
    const model = modelFor(
      {
        typeBadge: "json",
        metadata: {
          source: "documents",
          modified: "2026-06-02T00:00:00.000Z",
        },
      },
      "notes",
    );

    // Type surfaces as a badge *and* a row in the model…
    expect(model.badges.map((badge) => badge.label)).toEqual(
      expect.arrayContaining(["json"]),
    );
    expect(model.metadataRows).toEqual(
      expect.arrayContaining([
        { label: "Type", value: "json" },
        { label: "Source", value: "documents" },
      ]),
    );

    // …but the card view hides the badge-duplicated rows and keeps the rest.
    const visible = visibleCardMetadataRows(model);
    const visibleValues = visible.map((row) => row.value);
    expect(visibleValues).not.toContain("json");
    expect(visible).toEqual(
      expect.arrayContaining([{ label: "Source", value: "documents" }]),
    );
    expect(visible.some((row) => row.label === "Modified")).toBe(true);
  });

  it("preserves the full metadataRows on the model for the detail panel", () => {
    const model = modelFor({ typeBadge: "doc" }, "notes");
    // Deduping is a render-layer concern; the model keeps every row.
    expect(model.metadataRows).toEqual(
      expect.arrayContaining([
        { label: "Type", value: "doc" },
      ]),
    );
  });

  // ---------------------------------------------------------------------------
  // Documents "Source" detail section (Task 5)
  // ---------------------------------------------------------------------------
  it("adds a Source detail section to a documents item that has canonical_url", () => {
    const model = buildBrowseCardModel(
      item({
        id: "doc:web:augur-readme",
        title: "Augur README",
        description: "Project README",
        metadata: {
          canonical_url: "https://github.com/augur-os/augur-os/blob/main/README.md",
          provider: "filesystem",
          indexStatus: "synced",
        },
        primaryAction: { label: "Open", type: "open-file", target: "/docs/README.md" },
      }),
      { viewMode: "documents" },
    );

    const sourceSection = model.detailSections.find((s) => s.id === "document-source");
    expect(sourceSection).toBeDefined();
    expect(sourceSection?.title).toBe("Source");
    expect(sourceSection?.rows).toEqual(
      expect.arrayContaining([
        { label: "Canonical URL", value: "https://github.com/augur-os/augur-os/blob/main/README.md" },
      ]),
    );
  });

  it("adds a Source detail section to a documents item that has source_url", () => {
    const model = buildBrowseCardModel(
      item({
        id: "doc:web:some-doc",
        title: "Some Doc",
        description: "An ingested document",
        metadata: {
          source_url: "https://example.com/doc.pdf",
          provider: "filesystem",
        },
        primaryAction: { label: "Open", type: "open-file", target: "/docs/some-doc.pdf" },
      }),
      { viewMode: "documents" },
    );

    const sourceSection = model.detailSections.find((s) => s.id === "document-source");
    expect(sourceSection).toBeDefined();
    expect(sourceSection?.rows).toEqual(
      expect.arrayContaining([
        { label: "Source URL", value: "https://example.com/doc.pdf" },
      ]),
    );
  });

  it("does NOT add a Source detail section to a documents item with no source metadata", () => {
    const model = buildBrowseCardModel(
      item({
        id: "doc:local:readme",
        title: "Local README",
        description: "Local file without source URL",
        metadata: {
          provider: "filesystem",
          indexStatus: "synced",
        },
        primaryAction: { label: "Open", type: "open-file", target: "/docs/README.md" },
      }),
      { viewMode: "documents" },
    );

    const sourceSection = model.detailSections.find((s) => s.id === "document-source");
    expect(sourceSection).toBeUndefined();
  });
});
