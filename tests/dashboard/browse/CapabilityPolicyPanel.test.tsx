/**
 * @jest-environment jsdom
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import type { BrowseCategory, BrowseItem } from "@/lib/browse/types";
import { BrowseContentGrid } from "@/app/(views)/browse/BrowseContentGrid";
import { CapabilityPolicyPanel } from "@/app/(views)/browse/CapabilityPolicyPanel";

const draftPolicy = jest.fn();
const applyDraft = jest.fn();
const clearDraft = jest.fn();
const mockPush = jest.fn();

jest.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
    replace: jest.fn(),
    prefetch: jest.fn(),
    back: jest.fn(),
  }),
}));

let mockPolicyState: {
  draft: unknown;
  loading: boolean;
  error: string | null;
};

function makeDraft(capabilityId = "skill:geo-audit") {
  return {
    ok: true,
    capability_ids: [capabilityId],
    diff: "Reviewed policy diff",
    impact: {
      removed_from: {
        [capabilityId]: ["codex"],
      },
    },
  };
}

function makeNoopDraft(capabilityId = "skill:geo-audit") {
  return {
    ok: true,
    capability_ids: [capabilityId],
    diff: "",
    impact: {
      removed_from: {},
      added_to: {},
      gemini_delta: 0,
      opencode_delta: 0,
    },
  };
}

jest.mock("@/lib/browse/useCapabilityPolicy", () => ({
  useCapabilityPolicy: () => ({
    draft: mockPolicyState.draft,
    loading: mockPolicyState.loading,
    error: mockPolicyState.error,
    draftPolicy,
    applyDraft,
    clearDraft,
  }),
}));

const geoAuditItem: BrowseItem = {
  id: "geo-audit",
  title: "Geo Audit",
  description: "Review geospatial capability exposure",
  hub: "dev",
  icon: "Globe",
  primaryAction: {
    label: "Open",
    type: "navigate",
    target: "/browse/geo-audit",
  },
  metadata: {
    capabilityId: "skill:geo-audit",
    ownerKind: "external",
    management: "unmanaged",
    classificationStatus: "approved",
    primarySurface: "skill",
    currentExposure: "claude,codex",
  },
};

const calendarItem: BrowseItem = {
  ...geoAuditItem,
  id: "calendar-sync",
  title: "Calendar Sync",
  metadata: {
    capabilityId: "skill:calendar-sync",
    ownerKind: "external",
    management: "unmanaged",
    classificationStatus: "approved",
    primarySurface: "skill",
    currentExposure: "claude,codex",
  },
};

const generatedMcpItem: BrowseItem = {
  ...geoAuditItem,
  id: "tool:generated-runner",
  title: "Generated Runner",
  metadata: {
    capabilityId: "mcp-tool:generated-runner",
    ownerKind: "augur",
    management: "generated",
    classificationStatus: "approved",
    primarySurface: "mcp",
    currentExposure: "claude,codex,gemini",
  },
};

const cursorExposureItem: BrowseItem = {
  ...geoAuditItem,
  id: "tool:cursor-runner",
  title: "Cursor Runner",
  metadata: {
    capabilityId: "mcp-tool:cursor-runner",
    ownerKind: "augur",
    management: "generated",
    classificationStatus: "approved",
    primarySurface: "mcp",
    currentExposure: "claude,codex,cursor",
  },
};

const unclassifiedExternalItem: BrowseItem = {
  ...geoAuditItem,
  id: "geo-unclassified",
  title: "Geo Unclassified",
  metadata: {
    ...geoAuditItem.metadata,
    capabilityId: "skill:geo-unclassified",
    classificationStatus: "unclassified",
  },
};

const collisionMetadataItem: BrowseItem = {
  ...geoAuditItem,
  id: "geo-collision",
  title: "Geo Collision",
  metadata: {
    capabilityId: "skill:geo-collision",
    ownerKind: "external",
    scope: "shared",
    capabilityScope: "global",
    management: "manual",
    capabilityManagement: "unmanaged",
    primarySurface: "skill",
    preferredClient: "claude",
    exportTo: "claude",
    classificationStatus: "approved",
    currentExposure: "claude,codex",
    drift: "duplicate,unexpected_client",
    sourcePaths: "~/.claude/skills/geo-collision/SKILL.md",
  },
};

const mcpToolsCategory: BrowseCategory = {
  id: "mcp-tools",
  label: "MCP Tools",
  singularLabel: "Tool",
  icon: "Wrench",
  devOnly: true,
  group: "dev",
};

const capabilityToolItem: BrowseItem = {
  id: "tool:geo-audit-runner",
  title: "Geo Audit Runner",
  description: "Run geo audit MCP checks",
  hub: "dev",
  icon: "Wrench",
  primaryAction: {
    label: "Run",
    type: "run-mcp",
    target: "geo-audit-runner",
  },
  metadata: {
    capabilityId: "tool:geo-audit-runner",
    ownerKind: "augur",
    management: "generated",
    scope: "project",
    currentExposure: "claude,gemini",
    drift: "missing_expected_export",
  },
};

const externalCapabilityToolItem: BrowseItem = {
  ...capabilityToolItem,
  id: "tool:external-runner",
  title: "External Runner",
  metadata: {
    capabilityId: "tool:external-runner",
    ownerKind: "external",
    management: "unmanaged",
    scope: "global",
    currentExposure: "claude,codex",
  },
};

const externalCliItem: BrowseItem = {
  ...geoAuditItem,
  id: "cli-gh",
  title: "GitHub CLI",
  metadata: {
    capabilityId: "cli:gh",
    ownerKind: "external",
    management: "unmanaged",
    classificationStatus: "unclassified",
    primarySurface: "cli",
    currentExposure: "browse,shell",
  },
};

describe("CapabilityPolicyPanel", () => {
  beforeEach(() => {
    draftPolicy.mockReset();
    applyDraft.mockReset();
    clearDraft.mockReset();
    mockPush.mockReset();
    mockPolicyState = {
      draft: null,
      loading: false,
      error: null,
    };
  });

  it("does not enable apply before a reviewed draft exists", () => {
    render(
      <CapabilityPolicyPanel
        item={geoAuditItem}
        onClose={jest.fn()}
        onApplied={jest.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "Apply policy change" })).toBeDisabled();
  });

  it("renders above dashboard chrome as a blocking policy drawer", () => {
    render(
      <CapabilityPolicyPanel
        item={geoAuditItem}
        onClose={jest.fn()}
        onApplied={jest.fn()}
      />,
    );

    expect(screen.getByLabelText("Capability policy review")).toHaveClass("z-[90]");
  });

  it("portals the blocking drawer to the document body", async () => {
    render(
      <CapabilityPolicyPanel
        item={geoAuditItem}
        onClose={jest.fn()}
        onApplied={jest.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByLabelText("Capability policy review").parentElement).toBe(document.body);
    });
  });

  it("drafts a keep-only-in-Claude policy, shows impact, and applies the reviewed draft", async () => {
    const onApplied = jest.fn();
    const draft = makeDraft();
    draftPolicy.mockResolvedValue(draft);
    applyDraft.mockResolvedValue({ ok: true });

    render(
      <CapabilityPolicyPanel
        item={geoAuditItem}
        onClose={jest.fn()}
        onApplied={onApplied}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Keep only in Claude" }));

    await waitFor(() => {
      expect(draftPolicy).toHaveBeenCalledWith({
        action: "keep_only_in_client",
        capabilityIds: ["skill:geo-audit"],
        params: { target_client: "claude" },
      });
    });

    await waitFor(() => {
      expect(screen.getByText("Removed from codex")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Apply policy change" }));

    await waitFor(() => {
      expect(applyDraft).toHaveBeenCalledWith(draft);
      expect(onApplied).toHaveBeenCalled();
    });
  });

  it("shows a reviewed no-op draft before allowing apply", async () => {
    draftPolicy.mockResolvedValue(makeNoopDraft());

    render(
      <CapabilityPolicyPanel
        item={geoAuditItem}
        onClose={jest.fn()}
        onApplied={jest.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Keep only in Claude" }));

    await waitFor(() => {
      expect(screen.getByText("No client exposure changes.")).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: "Apply policy change" })).toBeEnabled();
  });

  it("drafts a keep-only-in-Codex policy with Codex params", async () => {
    draftPolicy.mockResolvedValue(makeDraft());

    render(
      <CapabilityPolicyPanel
        item={geoAuditItem}
        onClose={jest.fn()}
        onApplied={jest.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Keep only in Codex" }));

    await waitFor(() => {
      expect(draftPolicy).toHaveBeenCalledWith({
        action: "keep_only_in_client",
        capabilityIds: ["skill:geo-audit"],
        params: { target_client: "codex" },
      });
    });
  });

  it("drafts a block-from-Gemini policy for current Gemini exposure", async () => {
    draftPolicy.mockResolvedValue(makeDraft("mcp-tool:generated-runner"));

    render(
      <CapabilityPolicyPanel
        item={generatedMcpItem}
        onClose={jest.fn()}
        onApplied={jest.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Block from Gemini" }));

    await waitFor(() => {
      expect(draftPolicy).toHaveBeenCalledWith({
        action: "block_from_clients",
        capabilityIds: ["mcp-tool:generated-runner"],
        params: { clients: ["gemini"] },
      });
    });
  });

  it("drafts approval for the current multi-client exposure", async () => {
    draftPolicy.mockResolvedValue(makeDraft("mcp-tool:generated-runner"));

    render(
      <CapabilityPolicyPanel
        item={generatedMcpItem}
        onClose={jest.fn()}
        onApplied={jest.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Approve current clients" }));

    await waitFor(() => {
      expect(draftPolicy).toHaveBeenCalledWith({
        action: "approve_multi_client",
        capabilityIds: ["mcp-tool:generated-runner"],
        params: { clients: ["claude", "codex", "gemini"] },
      });
    });
  });

  it("drafts approval for current non-AI runtime exposure", async () => {
    draftPolicy.mockResolvedValue(makeNoopDraft("cli:gh"));

    render(
      <CapabilityPolicyPanel
        item={externalCliItem}
        onClose={jest.fn()}
        onApplied={jest.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Approve current exposure" }));

    await waitFor(() => {
      expect(draftPolicy).toHaveBeenCalledWith({
        action: "approve_current_exposure",
        capabilityIds: ["cli:gh"],
        params: {},
      });
    });
  });

  it("preserves Cursor in current-client approval and exposes a Cursor block action", async () => {
    draftPolicy.mockResolvedValue(makeDraft("mcp-tool:cursor-runner"));

    render(
      <CapabilityPolicyPanel
        item={cursorExposureItem}
        onClose={jest.fn()}
        onApplied={jest.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Block from Cursor" }));

    await waitFor(() => {
      expect(draftPolicy).toHaveBeenCalledWith({
        action: "block_from_clients",
        capabilityIds: ["mcp-tool:cursor-runner"],
        params: { clients: ["cursor"] },
      });
    });

    fireEvent.click(screen.getByRole("button", { name: "Approve current clients" }));

    await waitFor(() => {
      expect(draftPolicy).toHaveBeenLastCalledWith({
        action: "approve_multi_client",
        capabilityIds: ["mcp-tool:cursor-runner"],
        params: { clients: ["claude", "codex", "cursor"] },
      });
    });
  });

  it("enables move-to-CLI only for Augur generated MCP items and disables it for external unmanaged skills", () => {
    const { rerender } = render(
      <CapabilityPolicyPanel
        item={generatedMcpItem}
        onClose={jest.fn()}
        onApplied={jest.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "Move to CLI only" })).toBeEnabled();

    rerender(
      <CapabilityPolicyPanel
        item={geoAuditItem}
        onClose={jest.fn()}
        onApplied={jest.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "Move to CLI only" })).toBeDisabled();
  });

  it("drafts external management and classification actions", async () => {
    draftPolicy.mockResolvedValue(makeDraft());

    render(
      <CapabilityPolicyPanel
        item={geoAuditItem}
        onClose={jest.fn()}
        onApplied={jest.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Mark external unmanaged" }));

    await waitFor(() => {
      expect(draftPolicy).toHaveBeenCalledWith({
        action: "mark_external_unmanaged",
        capabilityIds: ["skill:geo-audit"],
        params: {},
      });
    });

    fireEvent.click(screen.getByRole("button", { name: "Adopt under Augur policy" }));

    await waitFor(() => {
      expect(draftPolicy).toHaveBeenCalledWith({
        action: "adopt_under_augur_policy",
        capabilityIds: ["skill:geo-audit"],
        params: {},
      });
    });

    fireEvent.click(screen.getByRole("button", { name: "Leave unclassified" }));

    await waitFor(() => {
      expect(draftPolicy).toHaveBeenLastCalledWith({
        action: "leave_unclassified",
        capabilityIds: ["skill:geo-audit"],
        params: {},
      });
    });
  });

  it("does not offer leave-unclassified for already unclassified items", () => {
    render(
      <CapabilityPolicyPanel
        item={unclassifiedExternalItem}
        onClose={jest.fn()}
        onApplied={jest.fn()}
      />,
    );

    expect(screen.queryByRole("button", { name: "Leave unclassified" })).not.toBeInTheDocument();
  });

  it("shows policy details using capability metadata when row metadata keys collide", () => {
    render(
      <CapabilityPolicyPanel
        item={collisionMetadataItem}
        onClose={jest.fn()}
        onApplied={jest.fn()}
      />,
    );

    expect(screen.getByText("Management")).toBeInTheDocument();
    expect(screen.getByText("unmanaged")).toBeInTheDocument();
    expect(screen.getByText("Policy scope")).toBeInTheDocument();
    expect(screen.getByText("global")).toBeInTheDocument();
    expect(screen.getByText("Surface")).toBeInTheDocument();
    expect(screen.getByText("skill")).toBeInTheDocument();
    expect(screen.getByText("Preferred client")).toBeInTheDocument();
    expect(screen.getAllByText("claude").length).toBeGreaterThan(0);
    expect(screen.getByText("Expected export")).toBeInTheDocument();
    expect(screen.getByText("Drift")).toBeInTheDocument();
    // ADR-734 C6: drift renders as per-dimension badges (CapabilityDriftBadge),
    // not a comma-joined string. `unexpected_client` shows its human label.
    const driftBadge = screen.getByTestId("capability-drift-badge");
    expect(driftBadge).toHaveTextContent("duplicate");
    expect(driftBadge).toHaveTextContent("unexpected client");
    expect(screen.getByText("Source paths")).toBeInTheDocument();
    expect(screen.getByText("~/.claude/skills/geo-collision/SKILL.md")).toBeInTheDocument();
  });

  it("clears a stale reviewed draft after a later draft attempt fails", async () => {
    const draft = makeDraft();
    draftPolicy.mockResolvedValueOnce(draft);
    draftPolicy.mockRejectedValueOnce(new Error("draft failed"));
    applyDraft.mockResolvedValue({ ok: true });

    render(
      <CapabilityPolicyPanel
        item={geoAuditItem}
        onClose={jest.fn()}
        onApplied={jest.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Keep only in Claude" }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Apply policy change" })).toBeEnabled();
    });

    fireEvent.click(screen.getByRole("button", { name: "Keep only in Claude" }));

    await waitFor(() => {
      expect(screen.getByText("draft failed")).toBeInTheDocument();
    });

    expect(screen.getByRole("button", { name: "Apply policy change" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Apply policy change" }));

    expect(applyDraft).not.toHaveBeenCalled();
  });

  it("does not apply a previous draft after rerendering with a different capability item", async () => {
    const draft = makeDraft();
    draftPolicy.mockResolvedValue(draft);
    applyDraft.mockResolvedValue({ ok: true });

    const { rerender } = render(
      <CapabilityPolicyPanel
        item={geoAuditItem}
        onClose={jest.fn()}
        onApplied={jest.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Keep only in Claude" }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Apply policy change" })).toBeEnabled();
    });

    rerender(
      <CapabilityPolicyPanel
        item={calendarItem}
        onClose={jest.fn()}
        onApplied={jest.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "Apply policy change" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Apply policy change" }));

    expect(applyDraft).not.toHaveBeenCalled();
  });
});

describe("BrowseContentGrid capability policy wiring", () => {
  function renderGrid(overrides: Partial<React.ComponentProps<typeof BrowseContentGrid>> = {}) {
    const props: React.ComponentProps<typeof BrowseContentGrid> = {
      effectiveViewMode: "mcp-tools",
      activeCategory: mcpToolsCategory,
      sorted: [capabilityToolItem],
      pinnedItems: [],
      semanticResultsActive: false,
      semanticResults: [],
      semanticLoading: false,
      loading: false,
      error: null,
      refetch: jest.fn(),
      notIndexed: false,
      visibleCount: 20,
      onLoadMore: jest.fn(),
      pageSize: 20,
      selectedSkill: null,
      selectedSchedule: null,
      hubFilter: null,
      search: "",
      onRunMcp: jest.fn(),
      onSelectSkill: jest.fn(),
      onSelectCapability: jest.fn(),
      onSelectScheduledExecution: jest.fn(),
      isPinned: jest.fn(() => false),
      onTogglePin: jest.fn(),
      ...overrides,
    };
    render(<BrowseContentGrid {...props} />);
    return props;
  }

  it("preserves non-skill card primary action and opens policy from a separate control", async () => {
    const onRunMcp = jest.fn();
    const onSelectCapability = jest.fn();

    renderGrid({ onRunMcp, onSelectCapability });

    fireEvent.click(screen.getByRole("button", { name: "Run" }));

    await waitFor(() => {
      expect(onRunMcp).toHaveBeenCalledWith("geo-audit-runner");
    });
    expect(onSelectCapability).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Review policy for Geo Audit Runner" }));

    expect(onSelectCapability).toHaveBeenCalledWith(capabilityToolItem);
  });

  it("summarizes capability ownership, management, scope, and drift above the grid", () => {
    renderGrid({ sorted: [capabilityToolItem, externalCapabilityToolItem] });

    expect(screen.getByText("Capability inventory")).toBeInTheDocument();
    expect(screen.getByText("Total: 2")).toBeInTheDocument();
    expect(screen.getByText("Augur: 1")).toBeInTheDocument();
    expect(screen.getByText("External: 1")).toBeInTheDocument();
    expect(screen.getByText("Generated: 1")).toBeInTheDocument();
    expect(screen.getByText("Unmanaged: 1")).toBeInTheDocument();
    expect(screen.getByText("Project: 1")).toBeInTheDocument();
    expect(screen.getByText("Global: 1")).toBeInTheDocument();
    expect(screen.getByText("Drift: 1")).toBeInTheDocument();
    expect(screen.getByText("Exposure Claude: 2")).toBeInTheDocument();
    expect(screen.getByText("Exposure Codex: 1")).toBeInTheDocument();
    expect(screen.getByText("Exposure Gemini: 1")).toBeInTheDocument();
  });

  it("keeps a visible zero-drift signal when the capability inventory is clean", () => {
    renderGrid({ sorted: [externalCapabilityToolItem] });

    expect(screen.getByText("Capability inventory")).toBeInTheDocument();
    expect(screen.getByText("Drift: 0")).toBeInTheDocument();
    expect(screen.getByText("Exposure Claude: 1")).toBeInTheDocument();
    expect(screen.getByText("Exposure Codex: 1")).toBeInTheDocument();
  });
});
