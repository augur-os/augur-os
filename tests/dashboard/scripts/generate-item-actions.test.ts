import {
  generateItemActionsSource,
  mergeCardActionSources,
  type SkillCardActionSource,
} from "@/scripts/generate-item-actions";
import type { UnifiedAction } from "@/lib/actions/actionsYamlSchema";
import fs from "fs";
import path from "path";

// ADR-807: the card baker now reads each skill's unified `augur/actions.yaml`
// (UnifiedAction[]) and merges card-surfaced actions on top of the Fork-1
// generic defaults (DEFAULT_CARD_ACTIONS). The old per-skill `browse-actions.yaml`
// doc shape and `mergeBrowseActionSources` were renamed to SkillCardActionSource
// / mergeCardActionSources.

function cardAction(overrides: Partial<UnifiedAction> & Pick<UnifiedAction, "id">): UnifiedAction {
  return {
    label: overrides.id,
    kind: "ai",
    dispatch: "oneshot",
    surfaces: ["card"],
    mcp_tool: null,
    template: `Do something with {title}`,
    icon: "RefreshCw",
    categories: [],
    args: {},
    when: {},
    confirm: null,
    modal: null,
    schedule: null,
    ...overrides,
  };
}

const ingestSource: SkillCardActionSource = {
  skillId: "ingest",
  filePath: "project-brain/capabilities/skills/ingest/augur/actions.yaml",
  actions: [
    cardAction({
      id: "wiki-custom-rescan",
      label: "Rescan",
      template: "Rescan {title}",
      categories: ["wiki"],
    }),
  ],
};

describe("mergeCardActionSources", () => {
  it("merges skill-owned card actions onto the generic category defaults", () => {
    const result = mergeCardActionSources([ingestSource], ["wiki", "synthetic-empty"]);

    expect(result.ok).toBe(true);
    if (result.ok) {
      // Skill action is appended after the seeded wiki defaults, in the same bucket.
      expect(result.registry.wiki.map((action) => action.id)).toContain("wiki-custom-rescan");
      expect(result.registry.wiki.map((action) => action.id)).toContain("wiki-update");

      // A category with no defaults and no skill action keeps the generic follow-up.
      expect(result.registry["synthetic-empty"].map((action) => action.id)).toEqual([
        "synthetic-empty-follow-up",
      ]);
      expect(result.registry["synthetic-empty"][0]).toMatchObject({
        icon: "MessageSquare",
        kind: "ai",
      });
    }
  });

  it("rejects a skill action whose id collides within the same category", () => {
    const duplicate: SkillCardActionSource = {
      skillId: "other",
      filePath: "project-brain/capabilities/skills/other/augur/actions.yaml",
      actions: [
        cardAction({
          id: "wiki-update", // collides with a DEFAULT_CARD_ACTIONS wiki action
          label: "Update again",
          template: "Update {title}",
          categories: ["wiki"],
        }),
      ],
    };

    const result = mergeCardActionSources([duplicate], ["wiki"]);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.errors.join("\n")).toContain("duplicate action id");
      expect(result.errors.join("\n")).toContain("wiki-update");
    }
  });
});

describe("generateItemActionsSource", () => {
  it("emits a deterministic typed registry module", () => {
    const result = mergeCardActionSources([ingestSource], ["wiki"]);
    expect(result.ok).toBe(true);
    if (!result.ok) return;

    const source = generateItemActionsSource(result.registry);

    expect(source).toContain("AUTO-GENERATED");
    expect(source).toContain("GENERATED_ITEM_ACTIONS");
    expect(source).toContain("wiki-custom-rescan");
    expect(source).not.toContain("undefined");
  });
});

describe("consumer startup paths", () => {
  it("generates the ignored registry before Jest and dev startup consume it", () => {
    const dashboardRoot = process.cwd();
    const packageJson = JSON.parse(
      fs.readFileSync(path.join(dashboardRoot, "package.json"), "utf8"),
    ) as { scripts: Record<string, string> };
    const startDev = fs.readFileSync(path.join(dashboardRoot, "scripts", "start-dev.sh"), "utf8");
    const startDevMjs = fs.readFileSync(path.join(dashboardRoot, "scripts", "start-dev.mjs"), "utf8");

    // pretest runs `ensure-generated`, the canonical chain that generates ALL the
    // gitignored registries (item-actions + block + tab/skill-nav) — needed because
    // a fresh CI clone has none of them. Verify the transitive contract.
    expect(packageJson.scripts.pretest).toContain("ensure-generated");
    expect(packageJson.scripts["ensure-generated"]).toContain("generate-item-actions");
    expect(packageJson.scripts.predev).toContain("generate-item-actions");
    expect(startDev).toContain("node scripts/dist/generate-item-actions.mjs");
    expect(startDevMjs).toContain("scripts/dist/generate-item-actions.mjs");
  });
});

describe("document + media card actions", () => {
  it("seeds the document and media actions with the right media-kind gating", () => {
    // ADR-807 moved document/media card actions into the Fork-1 generic defaults
    // (DEFAULT_CARD_ACTIONS.documents) rather than a per-skill YAML, so verify the
    // baked registry the baker produces.
    const result = mergeCardActionSources([], ["documents"]);
    expect(result.ok).toBe(true);
    if (!result.ok) return;

    const documents = result.registry.documents;
    const ids = documents.map((action) => action.id);

    // The core document + media actions are present (order-stable: defaults first).
    expect(ids).toEqual([
      "document-summary",
      "document-update-catalog-summary",
      "document-sweep",
      "document-reextract",
      "document-transcript",
      "document-image-describe",
      "document-image-ocr",
      "document-video-moments",
      "document-summarize",
      "document-index",
      "document-ask",
    ]);

    expect(documents.find((action) => action.id === "document-transcript")?.when).toMatchObject({
      mediaKinds: ["audio", "video"],
      fileExtensions: expect.arrayContaining(["m4a", "mp4", "webm"]),
    });
    expect(documents.find((action) => action.id === "document-image-describe")?.when).toEqual({
      mediaKinds: ["image"],
    });
  });
});
