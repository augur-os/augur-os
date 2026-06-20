import {
  aiItemActionsFor,
  directItemActionsFor,
  itemActionsFor,
  resolveDirectItemActionArgs,
  type AiItemAction,
} from "@/lib/browse/itemActions";

const byId = (category: string): Record<string, AiItemAction> =>
  Object.fromEntries(aiItemActionsFor(category).map((a) => [a.id, a]));

describe("itemActionsFor", () => {
  it("returns [] for unknown categories", () => {
    expect(itemActionsFor("not-a-category")).toEqual([]);
  });

  it("returns [] for undefined category", () => {
    expect(itemActionsFor(undefined)).toEqual([]);
    expect(aiItemActionsFor(undefined)).toEqual([]);
    expect(directItemActionsFor(undefined)).toEqual([]);
  });
});

describe("aiItemActionsFor — agent-profiles", () => {
  it("returns the four agent AI actions in order from the generated registry", () => {
    expect(aiItemActionsFor("agent-profiles").map((a) => a.id)).toEqual([
      "agent-follow-up",
      "agent-enhance",
      "agent-update",
      "agent-sweep",
    ]);
  });

  it("resolves templates with the item's name and path", () => {
    const item = { title: "dev-test", path: "plugins/agents/dev-test.md" };
    const a = byId("agent-profiles");
    expect(a["agent-enhance"].template(item)).toContain("dev-test");
    expect(a["agent-enhance"].template(item)).toContain("plugins/agents/dev-test.md");
  });

  it("missing path resolves to an empty string, not a synthetic plugin path", () => {
    const a = byId("agent-profiles");
    const prompt = a["agent-update"].template({ title: "advisor" });
    expect(prompt).toContain("advisor");
    expect(prompt).not.toContain("plugins/agents/advisor.md");
  });

  it("sweep prompt names the dependency surfaces and archives", () => {
    const p = byId("agent-profiles")["agent-sweep"].template({
      title: "dev-test",
      path: "plugins/agents/dev-test.md",
    });
    expect(p).toContain("registry.json");
    expect(p).toContain("capability_exposure");
    expect(p).toContain(".archive/");
    expect(p.toLowerCase()).toContain("do not hard-delete");
  });

  it("does not add an artifact problem chat draft action for arbitrary problem tags", () => {
    const actions = aiItemActionsFor("agent-profiles", {
      title: "Non-inventory item",
      path: "/repo/README.md",
      metadata: {
        problem_tags: "unknown_source",
      },
    });

    expect(actions.map((action) => action.id)).not.toContain("artifact-problem-chat");
  });

  it("does not add an artifact problem chat draft action for source path metadata alone", () => {
    const actions = aiItemActionsFor("agent-profiles", {
      title: "Source-backed non-inventory item",
      path: "/repo/README.md",
      metadata: {
        problem_tags: "unknown_source",
        source_path: "/repo/README.md",
      },
    });

    expect(actions.map((action) => action.id)).not.toContain("artifact-problem-chat");
  });

  it("adds an artifact problem chat draft action for inventory-backed problem metadata", () => {
    const actions = aiItemActionsFor("agent-profiles", {
      title: "Codex agent",
      path: "/repo/.codex/agents/dev.md",
      metadata: {
        inventory_source: "ai-artifact-inventory",
        problem_tags: "unknown_source",
        problem_evidence: '[{"id":"unknown_source","reason":"Scanner warning: unknown_source"}]',
      },
    });

    const action = actions.find((candidate) => candidate.id === "artifact-problem-chat");
    expect(action?.label).toBe("Send action items to chat");
    expect(action?.icon).toBe("MessageSquare");
    expect(action?.template({
      title: "Codex agent",
      path: "/repo/.codex/agents/dev.md",
      metadata: { problem_tags: "unknown_source" },
    })).toContain("Do not modify");
  });

  it("includes active folder context in artifact problem chat drafts", () => {
    const item = {
      title: "Codex agent",
      path: "/repo/.codex/agents/dev.md",
      metadata: {
        inventory_source: "ai-artifact-inventory",
        problem_tags: "unknown_source",
      },
    };
    const actions = aiItemActionsFor("agent-profiles", item, {
      activeFolderContext: {
        scope: "brain",
        label: "Augur project",
        brain_id: "project-augur",
        project_root: "~/Projects/Augur",
      },
    });

    const prompt = actions
      .find((candidate) => candidate.id === "artifact-problem-chat")
      ?.template(item) ?? "";

    expect(prompt).toContain("Context:");
    expect(prompt).toContain("Folder: Augur project");
    expect(prompt).toContain("Brain: project-augur");
    expect(prompt).toContain("Project root: ~/Projects/Augur");
  });

  it("does not duplicate the problem chat action when the generated registry already provides it", () => {
    jest.isolateModules(() => {
      jest.doMock("@/lib/browse/generated-item-actions", () => ({
        GENERATED_ITEM_ACTIONS: {
          "agent-profiles": [
            {
              id: "artifact-problem-chat",
              label: "Generated problem action",
              icon: "MessageSquare",
              kind: "ai",
              template: "Generated {title}",
            },
          ],
        },
      }));

      const { aiItemActionsFor: isolatedAiItemActionsFor } = require("@/lib/browse/itemActions") as typeof import("@/lib/browse/itemActions");
      const actions = isolatedAiItemActionsFor("agent-profiles", {
        title: "Codex agent",
        path: "/repo/.codex/agents/dev.md",
        metadata: {
          inventory_source: "ai-artifact-inventory",
          problem_tags: "unknown_source",
        },
      });

      expect(actions.filter((action) => action.id === "artifact-problem-chat")).toHaveLength(1);
      expect(actions.find((action) => action.id === "artifact-problem-chat")?.label).toBe("Generated problem action");
    });
  });
});

describe("wiki actions", () => {
  it("keeps review-first wiki actions on AI-guided surfaces", () => {
    expect(aiItemActionsFor("wiki").map((a) => a.id)).toEqual([
      "wiki-follow-up",
      "wiki-update",
      "wiki-dead-links",
      "wiki-enhance",
    ]);
    expect(directItemActionsFor("wiki")).toEqual([]);
  });

  it("resolves wiki AI templates with the page title and path", () => {
    const item = { title: "Reciprocal Rank Fusion", path: "vault/wiki/concepts/rrf.md" };
    const p = byId("wiki")["wiki-update"].template(item);
    expect(p).toContain("Reciprocal Rank Fusion");
    expect(p).toContain("vault/wiki/concepts/rrf.md");
    expect(p).toContain("wiki-update");
    expect(p).toContain("wiki-write");
  });

  it("keeps article enrichment AI-guided and hidden from non-article notes", () => {
    const urlNote = {
      id: "note:url:example",
      title: "Example article",
      path: "notes/example.md",
      typeBadge: "url",
      metadata: { "x-augur-note-type": "url" },
    };
    const thoughtNote = {
      id: "note:thought:example",
      title: "Loose thought",
      path: "notes/thought.md",
      typeBadge: "thought",
      metadata: { "x-augur-note-type": "thought" },
    };

    expect(aiItemActionsFor("notes", urlNote).map((a) => a.id)).toContain("note-enrich");
    expect(aiItemActionsFor("notes", thoughtNote).map((a) => a.id)).not.toContain("note-enrich");
    expect(directItemActionsFor("notes", urlNote).map((a) => a.id)).not.toContain("note-enrich");
  });

  it("resolves direct args placeholders from item metadata", () => {
    const action = {
      id: "test-direct",
      label: "Test direct",
      icon: "Search",
      kind: "direct" as const,
      tool: "test-tool",
      args: {
        note_path: "{path}",
        title: "{title}",
        owner: "{metadata.owner}",
      },
    };
    expect(resolveDirectItemActionArgs(action, {
      id: "n1",
      title: "Article note",
      path: "notes/article.md",
      metadata: { owner: "ingest" },
    })).toEqual({
      note_path: "notes/article.md",
      title: "Article note",
      owner: "ingest",
    });
  });
});

describe("notes classification actions", () => {
  it("adds Ask Augur about this before generated note actions", () => {
    const note = {
      title: "OpenAI Codex",
      path: "/vault/notes/codex.md",
      typeBadge: "url",
      metadata: {
        noteType: "url",
        noteDomain: "projects",
        noteSource: "github",
        noteStatus: "evaluating",
        canonical_url: "https://github.com/openai/codex",
      },
    };

    const actions = aiItemActionsFor("notes", note);
    const noteAskIndex = actions.findIndex((action) => action.id === "note-ask-augur");
    const enrichIndex = actions.findIndex((action) => action.id === "note-enrich");
    const prompt = actions[0].template(note);

    expect(actions[0].id).toBe("note-ask-augur");
    expect(actions[0].label).toBe("Ask Augur about this");
    if (enrichIndex >= 0) {
      expect(noteAskIndex).toBeGreaterThanOrEqual(0);
      expect(noteAskIndex).toBeLessThan(enrichIndex);
    }
    expect(prompt).toContain("Review this repo or project");
    expect(prompt).toContain("Title: OpenAI Codex");
    expect(prompt).toContain("Path: /vault/notes/codex.md");
    expect(prompt).toContain("Source URL: https://github.com/openai/codex");
    expect(prompt).toContain("Domain: projects");
    expect(prompt).toContain("Source: github");
    expect(prompt).toContain("Status: evaluating");
  });

  it("uses the jobs instruction for LinkedIn job notes", () => {
    const note = {
      title: "Staff Engineer",
      path: "/vault/notes/staff-engineer.md",
      typeBadge: "url",
      metadata: {
        noteType: "url",
        noteDomain: "jobs",
        noteSource: "linkedin",
        noteStatus: "saved",
        url: "https://www.linkedin.com/jobs/view/123",
      },
    };

    const prompt = aiItemActionsFor("notes", note)[0].template(note);

    expect(prompt).toContain("Analyze this job");
    expect(prompt).toContain("Match it to my profile");
  });

  it("does not add the Ask Augur note action for non-note categories", () => {
    const item = {
      title: "OpenAI Codex",
      path: "/vault/notes/codex.md",
      metadata: {
        noteType: "url",
        noteDomain: "projects",
      },
    };

    expect(aiItemActionsFor("wiki", item).map((action) => action.id)).not.toContain("note-ask-augur");
  });

  it("does not add the Ask Augur note action without an item", () => {
    expect(aiItemActionsFor("notes").map((action) => action.id)).not.toContain("note-ask-augur");
  });

  it("does not add the Ask Augur note action for generic URL records in notes", () => {
    const item = {
      title: "OpenAI Codex",
      path: "/vault/sources/urls/openai-codex.md",
      typeBadge: "url",
      metadata: {
        source_domain: "github.com",
        url: "https://github.com/openai/codex",
      },
    };

    expect(aiItemActionsFor("notes", item).map((action) => action.id)).not.toContain("note-ask-augur");
  });

  it("does not add the Ask Augur note action for synthesized-only classification metadata", () => {
    const item = {
      title: "OpenAI Codex",
      path: "/vault/notes/codex.md",
      typeBadge: "url",
      metadata: {
        noteDomain: "projects",
        noteSource: "github",
        classificationConfidence: "high",
        url: "https://github.com/openai/codex",
      },
    };

    expect(aiItemActionsFor("notes", item).map((action) => action.id)).not.toContain("note-ask-augur");
  });

  it("keeps the inventory problem chat action appended without duplicating note chat", () => {
    const note = {
      title: "OpenAI Codex",
      path: "/vault/notes/codex.md",
      typeBadge: "url",
      metadata: {
        noteType: "url",
        noteDomain: "projects",
        inventory_source: "ai-artifact-inventory",
        problem_tags: "unknown_source",
      },
    };

    const actions = aiItemActionsFor("notes", note);
    const ids = actions.map((action) => action.id);

    expect(ids.filter((id) => id === "note-ask-augur")).toHaveLength(1);
    expect(ids.filter((id) => id === "artifact-problem-chat")).toHaveLength(1);
    expect(ids.at(-1)).toBe("artifact-problem-chat");
  });
});

describe("document media item actions", () => {
  it("adds a document catalog summary follow-up prompt with MCP write-back instructions", () => {
    const deck = {
      id: "document:deck",
      title: "Investor Deck",
      path: "/cache/project-y/deck.pdf",
      metadata: {
        source_id: "project-y-drive",
        source_relative_path: "deck.pdf",
        remote_id: "google-drive:file:deck",
        provider: "google-drive",
        attachedBrainIds: "project-y",
        remoteRevision: "drive-revision-42",
      },
    };

    const action = aiItemActionsFor("documents", deck).find((candidate) => candidate.id === "document-update-catalog-summary");

    expect(action).toBeDefined();
    const prompt = action!.template(deck);
    expect(prompt).toContain("upsert-document-catalog-summary");
    expect(prompt).toContain("project-y-drive");
    expect(prompt).toContain("deck.pdf");
    expect(prompt).toContain("google-drive:file:deck");
    expect(prompt).toContain("google-drive");
    expect(prompt).toContain("project-y");
    expect(prompt).toContain("drive-revision-42");
    expect(prompt).toContain("two-to-four-line summary");
    expect(prompt).toContain("let me revise it");
    expect(prompt).toContain("summary_status=human");
    expect(prompt).toContain("summary_generated_from_revision=drive-revision-42");
  });

  it("does not add the project catalog summary prompt for personal filesystem documents", () => {
    const personalPdf = {
      id: "document:tax",
      title: "Tax Form",
      path: "~/Downloads/tax.pdf",
      metadata: {
        source_id: "downloads",
        source_relative_path: "tax.pdf",
        provider: "filesystem",
        attachedBrainIds: "personal",
      },
    };

    expect(aiItemActionsFor("documents", personalPdf).map((action) => action.id)).not.toContain(
      "document-update-catalog-summary",
    );
  });

  it("shows transcript only for audio and video files", () => {
    const audio = {
      title: "Meeting",
      path: "~/Downloads/meeting.m4a",
      metadata: { media_kind: "audio", file_ext: "m4a" },
    };
    const pdf = {
      title: "Deck",
      path: "~/Downloads/deck.pdf",
      metadata: { file_ext: "pdf" },
    };

    expect(aiItemActionsFor("documents", audio).map((a) => a.id)).toContain("document-transcript");
    expect(aiItemActionsFor("documents", pdf).map((a) => a.id)).not.toContain("document-transcript");
  });

  it("shows image prompts only for image files", () => {
    const image = {
      title: "Scan",
      path: "~/Desktop/scan.png",
      metadata: { media_kind: "image", file_ext: "png" },
    };

    expect(aiItemActionsFor("documents", image).map((a) => a.id)).toEqual(
      expect.arrayContaining(["document-image-describe", "document-image-ocr"]),
    );
  });

  it("documents offline failure behavior in media action prompts", () => {
    const audio = {
      title: "Meeting",
      path: "~/Downloads/meeting.m4a",
      metadata: { media_kind: "audio", file_ext: "m4a" },
    };
    const image = {
      title: "Scan",
      path: "~/Desktop/scan.png",
      metadata: { media_kind: "image", file_ext: "png" },
    };
    const audioPrompt = Object.fromEntries(aiItemActionsFor("documents", audio).map((a) => [a.id, a]))[
      "document-transcript"
    ].template(audio);
    const imagePrompt = Object.fromEntries(aiItemActionsFor("documents", image).map((a) => [a.id, a]))[
      "document-image-ocr"
    ].template(image);

    expect(audioPrompt).toContain("offline mode");
    expect(audioPrompt).toContain("configured local transcription backend");
    expect(audioPrompt).toContain("leave the source file unchanged");
    expect(imagePrompt).toContain("local OCR");
    expect(imagePrompt).toContain("leave the file unchanged");
  });
});
