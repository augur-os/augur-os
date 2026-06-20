import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import {
  BrowseCard,
  BrowseCardSkeleton,
  BrowseEmptyState,
  BrowseErrorState,
} from "@/components/shared/BrowseCard";
import type { BrowseItem, BrowseCategory } from "@/lib/browse/types";

// Mock next/navigation
const mockPush = jest.fn();
jest.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
    replace: jest.fn(),
    prefetch: jest.fn(),
    back: jest.fn(),
  }),
}));

// Mock fetch globally
const mockFetch = jest.fn(() =>
  Promise.resolve({
    ok: true,
    status: 200,
    json: () => Promise.resolve({}),
  }),
);
global.fetch = mockFetch as unknown as typeof fetch;

// Mock clipboard
const mockClipboard = {
  writeText: jest.fn(() => Promise.resolve()),
};
Object.defineProperty(navigator, "clipboard", {
  value: mockClipboard,
  writable: true,
});

/* ------------------------------------------------------------------ */
/*  Fixtures                                                           */
/* ------------------------------------------------------------------ */

const navigateItem: BrowseItem = {
  id: "skill-1",
  title: "Resume Builder",
  description: "Build and export professional resumes",
  icon: "FileText",
  typeBadge: "Skill",
  path: "/skills/resume-builder",
  primaryAction: {
    label: "Open",
    type: "navigate",
    target: "/career/resume-builder",
  },
};

const runMcpItem: BrowseItem = {
  id: "tool-1",
  title: "file-search",
  description: "Search for files by name or pattern",
  icon: "Search",
  typeBadge: "MCP Tool",
  primaryAction: {
    label: "Run",
    type: "run-mcp",
    target: "file-search",
  },
};

const copyItem: BrowseItem = {
  id: "route-1",
  title: "/api/browse/open",
  description: "Opens a file in the default editor",
  icon: "Route",
  typeBadge: "API Route",
  primaryAction: {
    label: "Copy",
    type: "copy",
    target: "/api/browse/open",
  },
};

const noPathItem: BrowseItem = {
  id: "agent-1",
  title: "Research Agent",
  description: "Autonomous research assistant",
  icon: "Bot",
  primaryAction: {
    label: "Configure",
    type: "configure",
    target: "/ai/agents/research",
  },
};

const mockCategory: BrowseCategory = {
  id: "skills",
  label: "Skills",
  icon: "Puzzle",
  devOnly: false,
};

/* ------------------------------------------------------------------ */
/*  BrowseCard tests                                                   */
/* ------------------------------------------------------------------ */

describe("BrowseCard", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders title and description", () => {
    render(<BrowseCard item={navigateItem} />);

    expect(screen.getByText("Resume Builder")).toBeInTheDocument();
    expect(
      screen.getByText("Build and export professional resumes"),
    ).toBeInTheDocument();
  });

  it("renders type badge", () => {
    render(<BrowseCard item={navigateItem} />);

    expect(screen.getByText("Skill")).toBeInTheDocument();
  });

  it("renders note type icons and metadata strips for notes", () => {
    render(
      <BrowseCard
        item={{
          ...navigateItem,
          id: "note:url:example",
          title: "Example article",
          typeBadge: "url",
          metadata: {
            "x-augur-note-type": "url",
            source_domain: "example.com",
            enrichment_status: "queued",
          },
        }}
      />,
    );

    expect(screen.getByTestId("browse-note-type-badge")).toHaveTextContent("URL");
    expect(screen.getByTestId("browse-note-metadata")).toHaveTextContent("example.com");
    expect(screen.getByTestId("browse-note-metadata")).toHaveTextContent("enrichment queued");
  });

  it.each([
    ["url", "enriched", "enriched", "enriched"],
    ["file", "pending", "pending", "enriching…"],
    ["url", "missing", undefined, "raw"],
  ])("renders %s enrichment status badge for %s status", (typeBadge, _statusName, enrichmentStatus, label) => {
    render(
      <BrowseCard
        item={{
          ...navigateItem,
          id: `note:${typeBadge}:${enrichmentStatus ?? "raw"}`,
          title: "Article note",
          typeBadge,
          metadata: enrichmentStatus
            ? {
                "x-augur-note-type": typeBadge,
                enrichment_status: enrichmentStatus,
              }
            : {
                "x-augur-note-type": typeBadge,
              },
        }}
      />,
    );

    expect(screen.getByTestId("browse-enrichment-status-badge")).toHaveTextContent(label);
  });

  it("renders sweep archive source metadata as a visible badge", () => {
    render(
      <BrowseCard
        item={{
          ...navigateItem,
          id: "sweep:docs:run:old.zip",
          title: "old.zip",
          description: "superseded",
          typeBadge: "docs-archive",
          metadata: {
            archive_source: "sweep",
            archive_mode: "docs-archive",
          },
        }}
      />,
    );

    expect(screen.getByText("archive_source=sweep")).toBeInTheDocument();
  });

  it("renders wiki tags instead of a misleading brain hub badge", () => {
    const wikiItem: BrowseItem = {
      id: "concepts/adaptive-ops-command-loop",
      title: "Adaptive Operations Command Loop",
      description: "Command-driven maintenance workflows.",

      icon: "NotebookTabs",
      typeBadge: "Concept",
      tags: [
        "auto-wiki-maintenance-cycle",
        "dev-loops-autonomous-cycles",
        "adaptive",
      ],
      metadata: {
        pageType: "concept",
        pageTags: "auto-wiki-maintenance-cycle,dev-loops-autonomous-cycles,adaptive",
      },
      primaryAction: {
        label: "Read Wiki",
        type: "open-file",
        target: "/wiki/concepts/adaptive-ops-command-loop.md",
      },
      actions: [
        {
          id: "reveal-concepts/adaptive-ops-command-loop",
          label: "Reveal Source",
          icon: "FolderOpen",
          type: "reveal-file",
          target: "/wiki/concepts/adaptive-ops-command-loop.md",
        },
        {
          id: "copy-path-concepts/adaptive-ops-command-loop",
          label: "Copy Path",
          icon: "Copy",
          type: "copy",
          target: "/wiki/concepts/adaptive-ops-command-loop.md",
        },
        {
          id: "copy-markdown-link-concepts/adaptive-ops-command-loop",
          label: "Copy Markdown Link",
          icon: "Link",
          type: "copy",
          target: "[[concepts/adaptive-ops-command-loop|Adaptive Operations Command Loop]]",
        },
        {
          id: "prepare-wiki-update-concepts/adaptive-ops-command-loop",
          label: "Prepare Wiki Update",
          icon: "RefreshCw",
          type: "mcp-tool",
          target: "wiki-update",
          args: { limit: 20 },
        },
      ],
    };

    render(<BrowseCard item={wikiItem} />);

    expect(screen.queryByText("brain")).not.toBeInTheDocument();
    expect(screen.getByText("Concept")).toBeInTheDocument();
    expect(screen.getAllByText("auto-wiki-maintenance-cycle").length).toBeGreaterThan(0);
    expect(screen.getAllByText("dev-loops-autonomous-cycles").length).toBeGreaterThan(0);
    expect(screen.getByTestId("browse-card-action")).toHaveTextContent("Read Wiki");
    expect(screen.queryByText("wiki")).not.toBeInTheDocument();
    expect(screen.queryByText("page")).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("browse-card-overflow"));
    expect(screen.getByRole("menuitem", { name: "Reveal Source" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Copy Path" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Copy Markdown Link" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Prepare Wiki Update" })).toBeInTheDocument();
  });

  it("recognizes non-concept wiki variants as wiki cards", () => {
    const wikiItem: BrowseItem = {
      id: "overview",
      title: "Wiki Overview",
      description: "Compiled overview.",

      icon: "NotebookTabs",
      typeBadge: "Overview",
      tags: ["source-coverage"],
      metadata: {
        pageType: "overview",
        pageTags: "source-coverage",
      },
      primaryAction: {
        label: "Read Wiki",
        type: "open-file",
        target: "/wiki/overview.md",
      },
    };

    render(<BrowseCard item={wikiItem} />);

    expect(screen.queryByText("brain")).not.toBeInTheDocument();
    expect(screen.getByText("Overview")).toBeInTheDocument();
    expect(screen.getAllByText("source-coverage").length).toBeGreaterThan(0);
  });

  it("renders wiki maintenance truth when a fresh reindex produced no apply", () => {
    const wikiItem: BrowseItem = {
      id: "concepts/wiki-freshness",
      title: "Wiki Freshness",
      description: "Maintenance status for the wiki surface.",
      icon: "NotebookTabs",
      typeBadge: "Concept",
      metadata: {
        pageType: "concept",
        wikiMaintenanceState: "no-apply",
        wikiMaintenanceVerdict: "structure_ok_compile_backlog",
        wikiPendingSources: "1812",
        wikiLastReindexedAt: "2026-06-07T03:35:00+00:00",
        wikiLastBatchQuality: "weak",
        wikiLastBatchReason:
          "19/20 low-signal sources; reindex refreshed Browse but no wiki pages were applied.",
      },
      primaryAction: {
        label: "Read Wiki",
        type: "open-file",
        target: "/wiki/concepts/wiki-freshness.md",
      },
    };

    render(<BrowseCard item={wikiItem} />);

    expect(screen.getByText("no apply")).toBeInTheDocument();
    expect(screen.getByText("1812 pending")).toBeInTheDocument();
    expect(screen.getByText("reindexed")).toBeInTheDocument();
  });

  it("reveals wiki source through the shared reveal action", async () => {
    const wikiItem: BrowseItem = {
      id: "concepts/adaptive-ops-command-loop",
      title: "Adaptive Operations Command Loop",
      description: "Command-driven maintenance workflows.",

      icon: "NotebookTabs",
      typeBadge: "Concept",
      path: "/wiki/concepts/adaptive-ops-command-loop.md",
      primaryAction: {
        label: "Read Wiki",
        type: "open-file",
        target: "/wiki/concepts/adaptive-ops-command-loop.md",
      },
      actions: [
        {
          id: "reveal-concepts/adaptive-ops-command-loop",
          label: "Reveal Source",
          icon: "FolderOpen",
          type: "reveal-file",
          target: "/wiki/concepts/adaptive-ops-command-loop.md",
        },
      ],
    };
    mockFetch
      .mockImplementationOnce(() =>
        Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ exists: true }),
        }),
      )
      .mockImplementationOnce(() =>
        Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ success: true }),
        }),
      );

    render(<BrowseCard item={wikiItem} />);
    fireEvent.click(screen.getByTestId("browse-card-overflow"));
    fireEvent.click(screen.getByRole("menuitem", { name: "Reveal Source" }));

    await waitFor(() => {
      expect(mockFetch).toHaveBeenNthCalledWith(
        2,
        "/api/mcp/tool",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            tool: "reveal-in-finder",
            args: { path: "/wiki/concepts/adaptive-ops-command-loop.md" },
          }),
        }),
      );
    });
  });

  it("runs wiki maintenance actions through MCP from the overflow menu", async () => {
    const wikiItem: BrowseItem = {
      id: "concepts/adaptive-ops-command-loop",
      title: "Adaptive Operations Command Loop",
      description: "Command-driven maintenance workflows.",

      icon: "NotebookTabs",
      typeBadge: "Concept",
      primaryAction: {
        label: "Read Wiki",
        type: "open-file",
        target: "/wiki/concepts/adaptive-ops-command-loop.md",
      },
      actions: [
        {
          id: "prepare-wiki-update-concepts/adaptive-ops-command-loop",
          label: "Prepare Wiki Update",
          icon: "RefreshCw",
          type: "mcp-tool",
          target: "wiki-update",
          args: { limit: 20 },
        },
      ],
    };
    mockFetch.mockImplementationOnce(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ success: true, message: "prepared" }),
      }),
    );

    render(<BrowseCard item={wikiItem} />);
    fireEvent.click(screen.getByTestId("browse-card-overflow"));
    fireEvent.click(screen.getByRole("menuitem", { name: "Prepare Wiki Update" }));

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        "/api/mcp/tool",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            tool: "wiki-update",
            args: { limit: 20 },
          }),
        }),
      );
    });
  });

  it("shows a more-actions trigger when path is present", () => {
    render(<BrowseCard item={navigateItem} />);

    expect(screen.getByTestId("browse-card-overflow")).toBeInTheDocument();
  });

  it("hides the overflow trigger when no path or secondary actions exist", () => {
    render(<BrowseCard item={noPathItem} />);

    expect(screen.queryByTestId("browse-card-overflow")).not.toBeInTheDocument();
  });

  it("navigates on navigate action click", () => {
    render(<BrowseCard item={navigateItem} />);

    fireEvent.click(screen.getByTestId("browse-card-action"));

    expect(mockPush).toHaveBeenCalledWith("/career/resume-builder");
  });

  it("calls onRunMcp on run-mcp action click", () => {
    const onRunMcp = jest.fn();
    render(<BrowseCard item={runMcpItem} onRunMcp={onRunMcp} />);

    fireEvent.click(screen.getByTestId("browse-card-action"));

    expect(onRunMcp).toHaveBeenCalledWith("file-search");
  });

  it("copies to clipboard on copy action click", () => {
    render(<BrowseCard item={copyItem} />);

    fireEvent.click(screen.getByTestId("browse-card-action"));

    expect(mockClipboard.writeText).toHaveBeenCalledWith("/api/browse/open");
  });

  it("calls fetch on reveal action click from the overflow menu", async () => {
    render(<BrowseCard item={navigateItem} />);

    fireEvent.click(screen.getByTestId("browse-card-overflow"));
    fireEvent.click(screen.getByRole("menuitem", { name: "Reveal in Finder" }));

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/mcp/tool",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          tool: "file-info",
          args: { path: "/skills/resume-builder" },
        }),
      }),
    );
  });

  it("does not duplicate the implicit reveal action when item actions already reveal the same path", () => {
    const itemWithExplicitReveal: BrowseItem = {
      ...navigateItem,
      id: "remote-access-overview",
      path: "/config/integrations/remote-access-overview.yaml",
      actions: [
        {
          id: "reveal-remote-access-overview",
          label: "Reveal Config",
          icon: "FolderOpen",
          type: "open-file",
          target: "/config/integrations/remote-access-overview.yaml",
        },
      ],
    };

    render(<BrowseCard item={itemWithExplicitReveal} />);

    fireEvent.click(screen.getByTestId("browse-card-overflow"));

    expect(screen.getByRole("menuitem", { name: "Reveal Config" })).toBeInTheDocument();
    expect(screen.queryByRole("menuitem", { name: "Reveal in Finder" })).not.toBeInTheDocument();
  });

  it("shows community badge for external ownership from install registry", () => {
    const externalItem: BrowseItem = {
      ...navigateItem,
      metadata: {
        ownership: "external",
        installMethod: "repo",
      },
    };

    render(<BrowseCard item={externalItem} />);

    expect(screen.getByText("Community")).toBeInTheDocument();
  });

  it("does not show community badge for adopted skills even with install metadata", () => {
    const adoptedItem: BrowseItem = {
      ...navigateItem,
      metadata: {
        ownership: "adopted",
        installMethod: "script",
      },
    };

    render(<BrowseCard item={adoptedItem} />);

    expect(screen.queryByText("Community")).not.toBeInTheDocument();
  });

  // ADR-748 Decision §3: prompt cards expose a source badge so user-authored
  // vault prompts are visually distinct from skill-shipped ones.
  it("renders a 'vault' source badge on vault-authored prompt cards", () => {
    render(
      <BrowseCard
        item={{
          ...navigateItem,
          id: "prompt:vault:morning-review",
          title: "Morning review",
          metadata: {
            ...navigateItem.metadata,
            prompt: "Summarise overnight items",
            source: "vault",
          },
        }}
      />,
    );
    expect(screen.getByText("vault")).toBeInTheDocument();
  });

  it("renders a 'skill' source badge on skill-shipped prompt cards", () => {
    render(
      <BrowseCard
        item={{
          ...navigateItem,
          id: "prompt:skill:digest",
          title: "Skill digest",
          metadata: {
            ...navigateItem.metadata,
            prompt: "Run the digest now",
            source: "skill",
          },
        }}
      />,
    );
    expect(screen.getByText("skill")).toBeInTheDocument();
  });

  it("does not render a source badge for non-prompt items even when metadata.source is set", () => {
    render(
      <BrowseCard
        item={{
          ...navigateItem,
          metadata: {
            ...navigateItem.metadata,
            source: "claude-local",
          },
        }}
      />,
    );
    expect(screen.queryByText("claude-local")).not.toBeInTheDocument();
  });
});

/* ------------------------------------------------------------------ */
/*  BrowseCardSkeleton tests                                           */
/* ------------------------------------------------------------------ */

describe("BrowseCardSkeleton", () => {
  it("renders skeleton element", () => {
    render(<BrowseCardSkeleton />);
    expect(screen.getByTestId("browse-card-skeleton")).toBeInTheDocument();
  });
});

/* ------------------------------------------------------------------ */
/*  BrowseEmptyState tests                                             */
/* ------------------------------------------------------------------ */

describe("BrowseEmptyState", () => {
  it("shows 'No skills found' message", () => {
    render(<BrowseEmptyState category={mockCategory} />);

    expect(screen.getByText("No skills found")).toBeInTheDocument();
  });

  it("shows search hint when search is provided", () => {
    render(<BrowseEmptyState category={mockCategory} search="foobar" />);

    expect(
      screen.getByText("Try a different search term"),
    ).toBeInTheDocument();
  });

});

/* ------------------------------------------------------------------ */
/*  BrowseErrorState tests                                             */
/* ------------------------------------------------------------------ */

describe("BrowseErrorState", () => {
  it("shows error message", () => {
    render(<BrowseErrorState message="Failed to load skills" />);

    expect(screen.getByText("Failed to load skills")).toBeInTheDocument();
  });

  it("shows retry button and calls onRetry", () => {
    const onRetry = jest.fn();
    render(
      <BrowseErrorState message="Failed to load" onRetry={onRetry} />,
    );

    const retryButton = screen.getByTestId("browse-error-retry");
    expect(retryButton).toBeInTheDocument();

    fireEvent.click(retryButton);
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("hides retry button when onRetry is not provided", () => {
    render(<BrowseErrorState message="Error" />);

    expect(screen.queryByTestId("browse-error-retry")).not.toBeInTheDocument();
  });
});
