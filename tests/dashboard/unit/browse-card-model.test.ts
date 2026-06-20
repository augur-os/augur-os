import { buildBrowseCardModel } from "@/lib/browse/cardModel";
import type { BrowseItem } from "@/lib/browse/types";

function agentItem(metadata: BrowseItem["metadata"]): BrowseItem {
  return {
    id: "developer",
    title: "developer",
    description: "Developer agent",
    hub: "dev",
    typeBadge: "agent",
    path: "plugins/agents/developer.md",
    primaryAction: {
      label: "Open",
      type: "open-file",
      target: "plugins/agents/developer.md",
    },
    metadata,
  };
}

describe("buildBrowseCardModel", () => {
  it("shows agent source and Codex projection models separately", () => {
    const card = buildBrowseCardModel(
      agentItem({
        type: "agent",
        master_client: "claude-code",
        source_model: "sonnet",
        source_tier: "standard",
        codex_model: "gpt-5.4",
        codex_profile_path: ".codex/agents/developer.md",
        codex_sync_status: "synced",
        mode: "act",
      }),
      { viewMode: "agent-profiles" },
    );

    expect(card.metadataRows).toEqual(
      expect.arrayContaining([
        { label: "Master", value: "claude-code" },
        { label: "Source model", value: "sonnet" },
        { label: "Source tier", value: "standard" },
        { label: "Codex model", value: "gpt-5.4" },
        { label: "Codex sync", value: "synced" },
        { label: "Codex profile", value: ".codex/agents/developer.md" },
      ]),
    );
    expect(card.metadataRows).not.toEqual(
      expect.arrayContaining([{ label: "Model", value: "sonnet" }]),
    );
    expect(card.badges).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ id: "agent-source-tier", label: "source standard" }),
        expect.objectContaining({ id: "agent-codex-model", label: "codex gpt-5.4" }),
      ]),
    );
  });

  it("shows problem badges on inventory-backed agent cards", () => {
    const card = buildBrowseCardModel(
      agentItem({
        inventory_source: "ai-artifact-inventory",
        problem_tags: "unknown_source,missing_mcp_config",
        problem_count: "2",
        problem_summary: "Unknown source",
      }),
      { viewMode: "agent-profiles" },
    );

    expect(card.badges).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ id: "problem-unknown_source", label: "Unknown source" }),
        expect.objectContaining({ id: "problem-missing_mcp_config", label: "Missing MCP config" }),
      ]),
    );
    expect(card.metadataRows).toEqual(
      expect.arrayContaining([{ label: "Problems", value: "2" }]),
    );
  });
});
