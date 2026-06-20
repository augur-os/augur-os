// TODO_CLEANUP: This file is 856 lines — consider splitting into smaller modules
/**
 * @jest-environment jsdom
 */
import { act, renderHook, waitFor } from "@testing-library/react";
import React from "react";
import { hydrateRoot } from "react-dom/client";
import { renderToString } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { mcpCall } from "@/lib/mcp/client";
import { toast } from "sonner";

const mockUseMcpQuery = jest.fn();
const mockUseSearchParams = jest.fn(() => new URLSearchParams());
const mockUseModeStore = jest.fn();
const mockReplace = jest.fn();
const mockRunCliExecPrompt = jest.fn();
const mockOpenChat = jest.fn();
const mockPluginTabRegistry: Record<string, any> = {};

jest.mock("@/lib/mcp/useMcpQuery", () => ({
  useMcpQuery: (...args: unknown[]) => mockUseMcpQuery(...args),
}));

jest.mock("@/lib/mcp/client", () => ({ mcpCall: jest.fn() }));

jest.mock("@/lib/stores/modeStore", () => ({
  useModeStore: (selector: (state: { mode: string }) => unknown) =>
    mockUseModeStore(selector),
}));

jest.mock("@/lib/browse/cliExecClient", () => ({
  runCliExecPrompt: (...args: unknown[]) => mockRunCliExecPrompt(...args),
}));

jest.mock("@/lib/stores/chatStore", () => ({
  useChatStore: (selector: (state: { openChat: typeof mockOpenChat }) => unknown) =>
    selector({ openChat: mockOpenChat }),
}));

jest.mock("sonner", () => ({
  toast: {
    loading: jest.fn(() => "toast-1"),
    success: jest.fn(),
    error: jest.fn(),
  },
}));

jest.mock("@/lib/browse/useSkillDetail", () => ({
  useSkillDetail: () => ({
    detail: null,
    loading: false,
  }),
}));

jest.mock("@/lib/browse/useScheduledExecutionDetail", () => ({
  useScheduledExecutionDetail: () => ({
    detail: {
      id: "codex:update-agents-md",
      title: "Update AGENTS.md",
      source: "codex",
    },
    loading: false,
    error: null,
  }),
}));

jest.mock("@/lib/tabs/registry", () => ({
  coreTabRegistry: {},
  getCompleteRegistry: () => mockPluginTabRegistry,
}));

jest.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: mockReplace,
    push: jest.fn(),
    prefetch: jest.fn(),
    back: jest.fn(),
  }),
  useSearchParams: () => mockUseSearchParams(),
}));

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: queryClient }, children);
  };
}

describe("useBrowseState", () => {
  beforeEach(() => {
    mockReplace.mockReset();
    mockOpenChat.mockReset();
    mockRunCliExecPrompt.mockReset();
    localStorage.clear();
    for (const key of Object.keys(mockPluginTabRegistry)) {
      delete mockPluginTabRegistry[key];
    }
    mockUseSearchParams.mockReturnValue(new URLSearchParams());
    (mcpCall as jest.Mock).mockReset();
    (toast.loading as jest.Mock).mockClear();
    (toast.success as jest.Mock).mockClear();
    (toast.error as jest.Mock).mockClear();
    mockUseModeStore.mockImplementation((selector: (state: { mode: string }) => unknown) =>
      selector({ mode: "operation" }),
    );
    mockUseMcpQuery.mockImplementation((_key: unknown, tool: string) => {
      if (tool === "pin-list") {
        return { data: { pins: [] }, loading: false, error: null, refetch: jest.fn() };
      }
      if (tool === "brain-discovery") {
        return { data: {}, loading: false, error: null, refetch: jest.fn() };
      }
      if (tool === "brain-active-context") {
        return {
          data: {
            success: true,
            context: { scope: "all", label: "All Brains" },
            options: [{ id: "all", scope: "all", label: "All Brains", state: "ready" }],
          },
          loading: false,
          error: null,
          refetch: jest.fn(),
        };
      }
      return {
        data: {
          items: [
            {
              id: "public-skill",
              title: "Public Skill",
              description: "Visible skill",
              hub: "life",
              type: "skills",
              metadata: { ownership: "augur" },
            },
            {
              id: "r2-skill",
              title: "R2 Skill",
              description: "Deferred but visible skill",
              hub: "system",
              type: "skills",
              metadata: { ownership: "augur", group: "augur_admin", release: "r2" },
            },
          ],
        },
        loading: false,
        error: null,
        refetch: jest.fn(),
      };
    });
    mockRunCliExecPrompt.mockResolvedValue({ answer: "ok" });
  });

  it("keeps non-mvp skills visible in operation mode", async () => {
    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.filtered.map((item) => item.id)).toEqual(
        expect.arrayContaining(["public-skill", "r2-skill"]),
      );
      expect(result.current.filtered).toHaveLength(2);
    });
  });

  it("keeps non-mvp skills visible in development mode too", async () => {
    mockUseModeStore.mockImplementation((selector: (state: { mode: string }) => unknown) =>
      selector({ mode: "development" }),
    );
    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.filtered.map((item) => item.id)).toEqual(
        expect.arrayContaining(["r2-skill", "public-skill"]),
      );
      expect(result.current.filtered).toHaveLength(2);
    });
  });

  it("hydrates saved display mode without a server/client mismatch", async () => {
    const { BROWSE_DISPLAY_MODE_STORAGE_KEY } = await import("@/lib/browse/displayMode");
    window.localStorage.setItem(
      BROWSE_DISPLAY_MODE_STORAGE_KEY,
      JSON.stringify({ notes: "list" }),
    );

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const router = {
      replace: mockReplace,
      push: jest.fn(),
      prefetch: jest.fn(),
      back: jest.fn(),
    };
    const searchParams = new URLSearchParams("view=notes");

    function DisplayModeProbe() {
      const state = useBrowseState({ router, searchParams });
      return React.createElement(
        "button",
        { type: "button", "aria-pressed": state.displayMode === "list" },
        state.displayMode,
      );
    }

    const Wrapper = createWrapper();
    const element = React.createElement(Wrapper, null, React.createElement(DisplayModeProbe));
    const getItemSpy = jest.spyOn(Storage.prototype, "getItem").mockReturnValue(null);
    const html = renderToString(element);
    getItemSpy.mockRestore();

    const container = document.createElement("div");
    container.innerHTML = html;
    const consoleError = jest.spyOn(console, "error").mockImplementation(() => {});
    let root: ReturnType<typeof hydrateRoot> | null = null;

    await act(async () => {
      root = hydrateRoot(container, element);
    });

    await waitFor(() => {
      expect(container.textContent).toBe("list");
    });
    expect(
      consoleError.mock.calls.some((call) =>
        call.some((part) => String(part).includes("hydrated") || String(part).includes("Hydration")),
      ),
    ).toBe(false);

    await act(async () => {
      root?.unmount();
    });
    consoleError.mockRestore();
  });

  it("applies manual brain filters after focus-mode brain narrowing", async () => {
    mockUseMcpQuery.mockImplementation((_key: unknown, tool: string) => {
      if (tool === "pin-list") {
        return {
          data: { pins: [] },
          loading: false,
          error: null,
          refetch: jest.fn(),
        };
      }
      if (tool === "brain-discovery") {
        return {
          data: {
            active: { brain_id: "personal" },
            current_project: { registered_brain_id: "project-augur" },
            brains: [
              { id: "personal", type: "personal" },
              { id: "project-augur", type: "project" },
            ],
          },
          loading: false,
          error: null,
          refetch: jest.fn(),
        };
      }
      return {
        data: {
          items: [
            {
              id: "personal-skill",
              title: "Personal Skill",
              description: "Personal brain item",
              hub: "workspace",
              type: "skills",
              metadata: { brain_id: "personal", ownership: "augur" },
            },
            {
              id: "project-skill",
              title: "Project Skill",
              description: "Project brain item",
              hub: "dev",
              type: "skills",
              metadata: { brain_id: "project-augur", ownership: "augur" },
            },
          ],
        },
        loading: false,
        error: null,
        refetch: jest.fn(),
      };
    });

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    act(() => {
      result.current.setFocusMode(true);
      result.current.setTypeFilter("decision");
    });

    await waitFor(() => {
      expect(result.current.filtered.map((item) => item.id)).toEqual([]);
    });
  });

  it("filters Browse items by active folder context", async () => {
    mockUseMcpQuery.mockImplementation((_key: unknown, tool: string) => {
      if (tool === "pin-list") {
        return { data: { pins: [] }, loading: false, error: null, refetch: jest.fn() };
      }
      if (tool === "brain-discovery") {
        return {
          data: {
            active: { brain_id: "personal" },
            current_project: { registered_brain_id: "project-augur" },
            brains: [
              { id: "personal", type: "personal" },
              { id: "project-augur", type: "project" },
            ],
          },
          loading: false,
          error: null,
          refetch: jest.fn(),
        };
      }
      if (tool === "brain-active-context") {
        return {
          data: {
            success: true,
            context: {
              scope: "brain",
              brain_id: "project-augur",
              label: "Augur project",
              project_root: "~/Projects/Augur",
              root: "~/Projects/Augur/project-brain",
            },
            options: [
              { id: "all", scope: "all", label: "All Brains", state: "ready" },
              { id: "brain:personal", scope: "brain", brain_id: "personal", label: "Personal", state: "ready" },
              { id: "brain:project-augur", scope: "brain", brain_id: "project-augur", label: "Augur project", state: "ready" },
            ],
          },
          loading: false,
          error: null,
          refetch: jest.fn(),
        };
      }
      return {
        data: {
          items: [
            {
              id: "personal-note",
              title: "Personal note",
              description: "Personal",
              hub: "workspace",
              type: "notes",
              metadata: { brain_id: "personal" },
            },
            {
              id: "project-agent",
              title: "Project agent",
              description: "Project",
              hub: "system",
              type: "agent-profile",
              metadata: { brain_id: "project-augur" },
            },
          ],
        },
        loading: false,
        error: null,
        refetch: jest.fn(),
      };
    });

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.activeFolderContext.label).toBe("Augur project");
      expect(result.current.activeFolderContext.project_root).toBe("~/Projects/Augur");
      expect(result.current.activeFolderContext.root).toBe("~/Projects/Augur/project-brain");
      expect(result.current.filtered.map((item) => item.id)).toEqual(["project-agent"]);
    });
  });

  it("keeps Unassigned as an active folder context", async () => {
    mockUseMcpQuery.mockImplementation((_key: unknown, tool: string) => {
      if (tool === "pin-list") {
        return { data: { pins: [] }, loading: false, error: null, refetch: jest.fn() };
      }
      if (tool === "brain-discovery") {
        return { data: {}, loading: false, error: null, refetch: jest.fn() };
      }
      if (tool === "brain-active-context") {
        return {
          data: {
            success: true,
            context: { scope: "unassigned", label: "Unassigned" },
            options: [
              { id: "all", scope: "all", label: "All Brains", state: "ready" },
              { id: "unassigned", scope: "unassigned", label: "Unassigned", state: "available", badge: "Repair" },
            ],
          },
          loading: false,
          error: null,
          refetch: jest.fn(),
        };
      }
      return {
        data: {
          items: [
            {
              id: "assigned-doc",
              title: "Assigned document",
              description: "Assigned",
              hub: "workspace",
              type: "document",
              metadata: { attachedBrainIds: "personal", brain_id: "personal" },
            },
            {
              id: "unassigned-doc",
              title: "Unassigned document",
              description: "Needs repair",
              hub: "workspace",
              type: "document",
              metadata: { indexStatus: "unassigned" },
            },
          ],
        },
        loading: false,
        error: null,
        refetch: jest.fn(),
      };
    });

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.activeFolderContext).toEqual({ scope: "unassigned", label: "Unassigned" });
      expect(result.current.filtered.map((item) => item.id)).toEqual(["unassigned-doc"]);
    });
  });

  it("defaults malformed active folder context to all folders", async () => {
    mockUseMcpQuery.mockImplementation((_key: unknown, tool: string) => {
      if (tool === "pin-list") {
        return { data: { pins: [] }, loading: false, error: null, refetch: jest.fn() };
      }
      if (tool === "brain-active-context") {
        return {
          data: {
            success: true,
            context: { scope: "brain", brain_id: 123 },
            options: [
              { id: "all", scope: "all", label: "All Brains", state: "ready" },
              { id: "brain:project-augur", scope: "brain", brain_id: "project-augur", label: "Augur project", state: "ready" },
            ],
          },
          loading: false,
          error: null,
          refetch: jest.fn(),
        };
      }
      if (tool === "brain-discovery") {
        return { data: {}, loading: false, error: null, refetch: jest.fn() };
      }
      return {
        data: {
          items: [
            {
              id: "personal-note",
              title: "Personal note",
              description: "Personal",
              hub: "workspace",
              type: "notes",
              metadata: { brain_id: "personal" },
            },
            {
              id: "project-agent",
              title: "Project agent",
              description: "Project",
              hub: "system",
              type: "agent-profile",
              metadata: { brain_id: "project-augur" },
            },
          ],
        },
        loading: false,
        error: null,
        refetch: jest.fn(),
      };
    });

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.activeFolderContext).toEqual({ scope: "all", label: "All Brains" });
      expect(result.current.filtered.map((item) => item.id)).toEqual(["personal-note", "project-agent"]);
    });
  });

  it("folder context loading does not block Browse loading", async () => {
    mockUseMcpQuery.mockImplementation((_key: unknown, tool: string) => {
      if (tool === "pin-list") {
        return { data: { pins: [] }, loading: false, error: null, refetch: jest.fn() };
      }
      if (tool === "brain-active-context") {
        return {
          data: null,
          loading: true,
          error: null,
          refetch: jest.fn(),
        };
      }
      if (tool === "brain-discovery") {
        return { data: {}, loading: false, error: null, refetch: jest.fn() };
      }
      return {
        data: {
          items: [
            {
              id: "project-agent",
              title: "Project agent",
              description: "Project",
              hub: "system",
              type: "agent-profile",
              metadata: { brain_id: "project-augur" },
            },
          ],
        },
        loading: false,
        error: null,
        refetch: jest.fn(),
      };
    });

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.folderContextLoading).toBe(true);
    });
    // Index data has resolved; the pending folder-context query must not
    // gate the card grid (spec 2026-06-10-browse-pages-load-speed).
    expect(result.current.loading).toBe(false);
  });

  it("persists selected folder context through MCP", async () => {
    const folderContextRefetch = jest.fn();
    mockUseMcpQuery.mockImplementation((_key: unknown, tool: string) => {
      if (tool === "pin-list") {
        return { data: { pins: [] }, loading: false, error: null, refetch: jest.fn() };
      }
      if (tool === "brain-active-context") {
        return {
          data: {
            success: true,
            context: { scope: "all", label: "All Brains" },
            options: [
              { id: "all", scope: "all", label: "All Brains", state: "ready" },
              { id: "brain:personal", scope: "brain", brain_id: "personal", label: "Personal", state: "ready" },
            ],
          },
          loading: false,
          error: null,
          refetch: folderContextRefetch,
        };
      }
      if (tool === "brain-discovery") {
        return { data: {}, loading: false, error: null, refetch: jest.fn() };
      }
      return { data: { items: [] }, loading: false, error: null, refetch: jest.fn() };
    });
    (mcpCall as jest.Mock).mockResolvedValue({
      success: true,
      context: { scope: "brain", brain_id: "personal", label: "Personal" },
    });

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    await act(async () => {
      await result.current.setActiveFolderContext({ scope: "brain", brain_id: "personal", label: "Personal" });
    });

    expect(mcpCall).toHaveBeenCalledWith("brain-set-active-context", {
      scope: "brain",
      brain_id: "personal",
    });
    expect(folderContextRefetch).toHaveBeenCalled();
  });

  it("scans folders for context through MCP", async () => {
    (mcpCall as jest.Mock).mockResolvedValue({ success: true });

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    await act(async () => {
      await result.current.scanFolderForContext("/Users/me/Projects/Augur");
    });

    expect(mcpCall).toHaveBeenCalledWith("brain-folder-scan", {
      project_root: "/Users/me/Projects/Augur",
    });
  });

  it("refreshes folder context when Browse data is refetched", async () => {
    const indexRefetch = jest.fn();
    const folderContextRefetch = jest.fn();
    mockUseMcpQuery.mockImplementation((_key: unknown, tool: string) => {
      if (tool === "pin-list") {
        return { data: { pins: [] }, loading: false, error: null, refetch: jest.fn() };
      }
      if (tool === "brain-active-context") {
        return {
          data: {
            success: true,
            context: { scope: "all", label: "All Brains" },
            options: [{ id: "all", scope: "all", label: "All Brains", state: "ready" }],
          },
          loading: false,
          error: null,
          refetch: folderContextRefetch,
        };
      }
      if (tool === "brain-discovery") {
        return { data: {}, loading: false, error: null, refetch: jest.fn() };
      }
      return { data: { items: [] }, loading: false, error: null, refetch: indexRefetch };
    });

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    act(() => {
      result.current.refetch();
    });

    expect(indexRefetch).toHaveBeenCalled();
    expect(folderContextRefetch).toHaveBeenCalled();
  });

  it("builds and applies problem filters from Browse metadata", async () => {
    mockUseMcpQuery.mockImplementation((_key: unknown, tool: string) => {
      if (tool === "pin-list") {
        return {
          data: { pins: [] },
          loading: false,
          error: null,
          refetch: jest.fn(),
        };
      }
      if (tool === "brain-discovery") {
        return {
          data: {},
          loading: false,
          error: null,
          refetch: jest.fn(),
        };
      }
      return {
        data: {
          items: [
            {
              id: "bad-agent",
              title: "Bad agent",
              description: "unknown",
              hub: "system",
              type: "agent-profile",
              metadata: { problem_tags: "unknown_source,missing_mcp_config" },
            },
            {
              id: "ok-agent",
              title: "OK agent",
              description: "known",
              hub: "system",
              type: "agent-profile",
              metadata: {},
            },
          ],
        },
        loading: false,
        error: null,
        refetch: jest.fn(),
      };
    });

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.problemItems).toEqual(
        expect.arrayContaining([{ id: "unknown_source", label: "Unknown source (1)" }]),
      );
    });

    act(() => result.current.setProblemFilter("missing_mcp_config"));

    expect(result.current.filtered.map((item) => item.id)).toEqual(["bad-agent"]);
  });

  it("filters Notes by domain, source, and domain-specific status", async () => {
    localStorage.setItem("augur:browse:view", "notes");
    mockUseMcpQuery.mockImplementation((_key: unknown, tool: string) => {
      if (tool === "pin-list") {
        return { data: { pins: [] }, loading: false, error: null, refetch: jest.fn() };
      }
      if (tool === "brain-discovery") {
        return { data: {}, loading: false, error: null, refetch: jest.fn() };
      }
      if (tool === "brain-active-context") {
        return {
          data: {
            success: true,
            context: { scope: "all", label: "All Brains" },
            options: [{ id: "all", scope: "all", label: "All Brains", state: "ready" }],
          },
          loading: false,
          error: null,
          refetch: jest.fn(),
        };
      }
      return {
        data: {
          items: [
            {
              id: "github-repo-note",
              title: "GitHub repo note",
              description: "Repository URL",
              hub: "workspace",
              type: "source-card",
              source_path: "~/Projects/Au-vault/sources/urls/github-repo.md",
              metadata: {
                "x-augur-note-type": "url",
                canonical_url: "https://github.com/openai/openai-node",
                journey_category: "sources",
              },
            },
            {
              id: "linkedin-job-note",
              title: "LinkedIn job note",
              description: "Job URL",
              hub: "workspace",
              type: "source-card",
              source_path: "~/Projects/Au-vault/sources/urls/linkedin-job.md",
              metadata: {
                "x-augur-note-type": "url",
                "x-augur-domain": "jobs",
                "x-augur-source": "linkedin",
                "x-augur-status": "applied",
                "x-augur-classification-confidence": "high",
                canonical_url: "https://www.linkedin.com/jobs/view/123456789",
                journey_category: "sources",
              },
            },
          ],
        },
        loading: false,
        error: null,
        refetch: jest.fn(),
      };
    });

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.effectiveViewMode).toBe("notes");
      expect(result.current.filtered).toHaveLength(2);
    });

    act(() => result.current.setNoteDomainFilter("projects"));
    expect(result.current.filtered.map((item) => item.title)).toEqual(["GitHub repo note"]);

    act(() => result.current.setNoteSourceFilter("github"));
    expect(result.current.filtered.map((item) => item.title)).toEqual(["GitHub repo note"]);

    act(() => result.current.setNoteStatusFilter("saved"));
    expect(result.current.filtered.map((item) => item.title)).toEqual(["GitHub repo note"]);
  });

  it("counts note status options inside the selected note domain", async () => {
    localStorage.setItem("augur:browse:view", "notes");
    mockUseMcpQuery.mockImplementation((_key: unknown, tool: string) => {
      if (tool === "pin-list") {
        return { data: { pins: [] }, loading: false, error: null, refetch: jest.fn() };
      }
      if (tool === "brain-discovery") {
        return { data: {}, loading: false, error: null, refetch: jest.fn() };
      }
      if (tool === "brain-active-context") {
        return {
          data: {
            success: true,
            context: { scope: "all", label: "All Brains" },
            options: [{ id: "all", scope: "all", label: "All Brains", state: "ready" }],
          },
          loading: false,
          error: null,
          refetch: jest.fn(),
        };
      }
      return {
        data: {
          items: [
            {
              id: "github-repo-note",
              title: "GitHub repo note",
              description: "Repository URL",
              hub: "workspace",
              type: "source-card",
              source_path: "~/Projects/Au-vault/sources/urls/github-repo.md",
              metadata: {
                "x-augur-note-type": "url",
                canonical_url: "https://github.com/openai/openai-node",
                journey_category: "sources",
              },
            },
            {
              id: "linkedin-job-note",
              title: "LinkedIn job note",
              description: "Job URL",
              hub: "workspace",
              type: "source-card",
              source_path: "~/Projects/Au-vault/sources/urls/linkedin-job.md",
              metadata: {
                "x-augur-note-type": "url",
                "x-augur-domain": "jobs",
                "x-augur-source": "linkedin",
                "x-augur-status": "applied",
                "x-augur-classification-confidence": "high",
                canonical_url: "https://www.linkedin.com/jobs/view/123456789",
                journey_category: "sources",
              },
            },
          ],
        },
        loading: false,
        error: null,
        refetch: jest.fn(),
      };
    });

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.effectiveViewMode).toBe("notes");
      expect(result.current.noteDomainItems).toEqual(
        expect.arrayContaining([
          { id: "projects", label: "Project (1)" },
          { id: "jobs", label: "Job (1)" },
        ]),
      );
    });

    act(() => result.current.setNoteDomainFilter("projects"));

    await waitFor(() => {
      expect(result.current.noteStatusItems).toEqual(
        expect.arrayContaining([{ id: "saved", label: "Saved (1)" }]),
      );
    });
  });

  it("builds Notes filter options from the active folder context item set", async () => {
    localStorage.setItem("augur:browse:view", "notes");
    mockUseMcpQuery.mockImplementation((_key: unknown, tool: string) => {
      if (tool === "pin-list") {
        return { data: { pins: [] }, loading: false, error: null, refetch: jest.fn() };
      }
      if (tool === "brain-discovery") {
        return {
          data: {
            active: { brain_id: "project-augur" },
            current_project: { registered_brain_id: "project-augur" },
            brains: [
              { id: "personal", type: "personal", label: "Personal" },
              { id: "project-augur", type: "project", label: "Augur" },
            ],
          },
          loading: false,
          error: null,
          refetch: jest.fn(),
        };
      }
      if (tool === "brain-active-context") {
        return {
          data: {
            success: true,
            context: {
              scope: "brain",
              brain_id: "project-augur",
              label: "Augur project",
              state: "ready",
            },
            options: [
              { id: "all", scope: "all", label: "All Brains", state: "ready" },
              { id: "brain:project-augur", scope: "brain", brain_id: "project-augur", label: "Augur project", state: "ready" },
            ],
          },
          loading: false,
          error: null,
          refetch: jest.fn(),
        };
      }
      return {
        data: {
          items: [
            {
              id: "personal-reading",
              title: "Personal reading",
              description: "Not in the active project folder.",
              type: "vault",
              source_path: "~/Projects/Au-vault/notes/reading/book.md",
              metadata: {
                brain_id: "personal",
                journey_category: "notes",
                note_category: "reading",
                "x-augur-note-type": "thought",
                "x-augur-note-domain": "personal-reading",
                "x-augur-note-source": "kindle",
                "x-augur-note-status": "queued",
              },
            },
            {
              id: "project-notes-filters",
              title: "Project notes filters",
              description: "Active project metadata.",
              type: "vault",
              source_path: "~/Projects/Augur/project-brain/notes/augur/notes-filters.md",
              metadata: {
                brain_id: "project-augur",
                journey_category: "notes",
                note_category: "augur",
                "x-augur-note-type": "thought",
                "x-augur-note-domain": "augur-browse",
                "x-augur-note-source": "codex-session",
                "x-augur-note-status": "needs-review",
                "x-augur-classification-confidence": "high",
              },
            },
          ],
        },
        loading: false,
        error: null,
        refetch: jest.fn(),
      };
    });

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.effectiveViewMode).toBe("notes");
      expect(result.current.filtered.map((item) => item.title)).toEqual(["Project notes filters"]);
      expect(result.current.journeyCategoryItems.map((item) => item.id)).toEqual(["all", "augur"]);
      expect(result.current.noteDomainItems).toEqual([
        { id: "augur-browse", label: "Augur Browse (1)" },
      ]);
      expect(result.current.noteSourceItems).toEqual([
        { id: "codex-session", label: "Codex Session (1)" },
      ]);
    });

    act(() => result.current.setNoteDomainFilter("augur-browse"));

    await waitFor(() => {
      expect(result.current.noteStatusItems).toEqual([
        { id: "needs-review", label: "Needs Review (1)" },
      ]);
    });
  });

  it("clears invalid note status when note domain changes", async () => {
    localStorage.setItem("augur:browse:view", "notes");
    mockUseMcpQuery.mockImplementation((_key: unknown, tool: string) => {
      if (tool === "pin-list") {
        return { data: { pins: [] }, loading: false, error: null, refetch: jest.fn() };
      }
      if (tool === "brain-discovery") {
        return { data: {}, loading: false, error: null, refetch: jest.fn() };
      }
      if (tool === "brain-active-context") {
        return {
          data: {
            success: true,
            context: { scope: "all", label: "All Brains" },
            options: [{ id: "all", scope: "all", label: "All Brains", state: "ready" }],
          },
          loading: false,
          error: null,
          refetch: jest.fn(),
        };
      }
      return {
        data: {
          items: [
            {
              id: "linkedin-job-note",
              title: "LinkedIn job note",
              description: "Job URL",
              hub: "workspace",
              type: "source-card",
              source_path: "~/Projects/Au-vault/sources/urls/linkedin-job.md",
              metadata: {
                "x-augur-note-type": "url",
                "x-augur-domain": "jobs",
                "x-augur-source": "linkedin",
                "x-augur-status": "applied",
                "x-augur-classification-confidence": "high",
                canonical_url: "https://www.linkedin.com/jobs/view/123456789",
                journey_category: "sources",
              },
            },
          ],
        },
        loading: false,
        error: null,
        refetch: jest.fn(),
      };
    });

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.effectiveViewMode).toBe("notes");
      expect(result.current.filtered).toHaveLength(1);
    });

    act(() => result.current.setNoteDomainFilter("jobs"));

    await waitFor(() => {
      expect(result.current.noteStatusItems).toEqual([
        { id: "applied", label: "Applied (1)" },
      ]);
    });

    act(() => {
      result.current.setNoteStatusFilter("applied");
    });
    expect(result.current.noteStatusFilter).toBe("applied");

    act(() => result.current.setNoteDomainFilter("people"));

    await waitFor(() => {
      expect(result.current.noteStatusFilter).toBeNull();
    });
  });

  it("clears Notes classification filters when leaving the Notes view", async () => {
    localStorage.setItem("augur:browse:view", "notes");
    mockUseMcpQuery.mockImplementation((_key: unknown, tool: string) => {
      if (tool === "pin-list") {
        return { data: { pins: [] }, loading: false, error: null, refetch: jest.fn() };
      }
      if (tool === "brain-discovery") {
        return { data: {}, loading: false, error: null, refetch: jest.fn() };
      }
      if (tool === "brain-active-context") {
        return {
          data: {
            success: true,
            context: { scope: "all", label: "All Brains" },
            options: [{ id: "all", scope: "all", label: "All Brains", state: "ready" }],
          },
          loading: false,
          error: null,
          refetch: jest.fn(),
        };
      }
      return {
        data: {
          items: [
            {
              id: "github-repo-note",
              title: "GitHub repo note",
              description: "Repository URL",
              hub: "workspace",
              type: "source-card",
              source_path: "~/Projects/Au-vault/sources/urls/github-repo.md",
              metadata: {
                "x-augur-note-type": "url",
                canonical_url: "https://github.com/openai/openai-node",
                journey_category: "sources",
              },
            },
          ],
        },
        loading: false,
        error: null,
        refetch: jest.fn(),
      };
    });

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.effectiveViewMode).toBe("notes");
    });

    act(() => {
      result.current.setNoteDomainFilter("projects");
      result.current.setNoteSourceFilter("github");
      result.current.setNoteStatusFilter("saved");
    });

    expect(result.current.noteDomainFilter).toBe("projects");
    expect(result.current.noteSourceFilter).toBe("github");
    expect(result.current.noteStatusFilter).toBe("saved");

    act(() => result.current.changeView("skills"));

    expect(result.current.effectiveViewMode).toBe("skills");
    expect(result.current.noteDomainFilter).toBeNull();
    expect(result.current.noteSourceFilter).toBeNull();
    expect(result.current.noteStatusFilter).toBeNull();
  });

  it("builds wiki tag filters from page tags instead of the brain hub", async () => {
    localStorage.setItem("augur:browse:view", "wiki");
    mockUseModeStore.mockImplementation((selector: (state: { mode: string }) => unknown) =>
      selector({ mode: "development" }),
    );
    mockUseMcpQuery.mockReturnValue({
      data: {
        items: [
          {
            id: "concepts/adaptive-ops-command-loop",
            title: "Adaptive Operations Command Loop",
            description: "Command-driven maintenance workflows.",
            hub: "workspace",
            type: "wiki",
            tags: [
              "wiki",
              "concept",
              "adaptive-ops-command-loop",
              "auto-wiki-maintenance-cycle",
              "dev-loops-autonomous-cycles",
              "adaptive",
            ],
            metadata: { modified: "2026-04-22T08:15:51Z" },
          },
          {
            id: "concepts/guriqo-brand-messaging-strategy",
            title: "Guriqo Brand Messaging Strategy",
            description: "Brand messaging workflow.",
            hub: "workspace",
            type: "wiki",
            tags: [
              "wiki",
              "concept",
              "guriqo-brand-messaging-strategy",
              "guriqo",
              "brand",
            ],
            metadata: { modified: "2026-04-22T08:15:51Z" },
          },
        ],
      },
      loading: false,
      error: null,
      refetch: jest.fn(),
    });

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.effectiveViewMode).toBe("wiki");
      expect(result.current.tagItems.map((item) => item.id)).toContain("auto-wiki-maintenance-cycle");
      expect(result.current.tagItems.map((item) => item.id)).not.toContain("brain");
    });

    act(() => {
      result.current.setTagFilter("auto-wiki-maintenance-cycle");
    });

    await waitFor(() => {
      expect(result.current.filtered.map((item) => item.id)).toEqual([
        "concepts/adaptive-ops-command-loop",
      ]);
    });
  });

  it("orders non-narrowed wiki cards by pins, then newest timestamp, then title", async () => {
    localStorage.setItem("augur:browse:view", "wiki");
    mockUseMcpQuery.mockImplementation((_key: unknown, tool: string) => {
      if (tool === "pin-list") {
        return {
          data: {
            pins: [
              {
                category: "wiki",
                itemKey: "wiki::older-pinned",
                url: "/vault/wiki/older-pinned.md",
                title: "Zeta Pinned",
                kind: "browse-card",
                hub: "workspace",
              },
            ],
          },
          loading: false,
          error: null,
          refetch: jest.fn(),
        };
      }
      return {
        data: {
          items: [
            {
              id: "older-pinned",
              title: "Zeta Pinned",
              description: "Pinned but older wiki card.",
              hub: "workspace",
              type: "wiki",
              source_path: "/vault/wiki/older-pinned.md",
              metadata: { modified: "2026-01-01T00:00:00Z" },
            },
            {
              id: "newer-beta",
              title: "Beta Recent",
              description: "Recent wiki card.",
              hub: "workspace",
              type: "wiki",
              source_path: "/vault/wiki/newer-beta.md",
              metadata: { modified: "2026-05-12T00:00:00Z" },
            },
            {
              id: "newer-alpha",
              title: "Alpha Recent",
              description: "Recent wiki card with title tiebreak.",
              hub: "workspace",
              type: "wiki",
              source_path: "/vault/wiki/newer-alpha.md",
              metadata: { modified: "2026-05-12T00:00:00Z" },
            },
            {
              id: "oldest",
              title: "Oldest",
              description: "Older unpinned wiki card.",
              hub: "workspace",
              type: "wiki",
              source_path: "/vault/wiki/oldest.md",
              metadata: { modified: "2026-01-02T00:00:00Z" },
            },
          ],
        },
        loading: false,
        error: null,
        refetch: jest.fn(),
      };
    });

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.effectiveViewMode).toBe("wiki");
      expect(result.current.sortBy).toBe("default");
      expect(result.current.sorted.map((item) => item.id)).toEqual([
        "older-pinned",
        "newer-alpha",
        "newer-beta",
        "oldest",
      ]);
      expect(result.current.pinnedItems.map((item) => item.id)).toEqual(["older-pinned"]);
    });
  });

  it("hides nonmatching pinned wiki cards during search", async () => {
    localStorage.setItem("augur:browse:view", "wiki");
    mockUseMcpQuery.mockImplementation((_key: unknown, tool: string) => {
      if (tool === "pin-list") {
        return {
          data: {
            pins: [
              {
                category: "wiki",
                itemKey: "wiki::pinned-command-loop",
                url: "/vault/wiki/pinned-command-loop.md",
                title: "Pinned Command Loop",
                kind: "browse-card",
                hub: "workspace",
              },
            ],
          },
          loading: false,
          error: null,
          refetch: jest.fn(),
        };
      }
      return {
        data: {
          items: [
            {
              id: "pinned-command-loop",
              title: "Pinned Command Loop",
              description: "Should disappear when it does not match search.",
              hub: "workspace",
              type: "wiki",
              source_path: "/vault/wiki/pinned-command-loop.md",
              metadata: { modified: "2026-01-01T00:00:00Z" },
            },
            {
              id: "profile-synthesis",
              title: "Profile Synthesis",
              description: "Matches the search term.",
              hub: "workspace",
              type: "wiki",
              source_path: "/vault/wiki/profile-synthesis.md",
              metadata: { modified: "2026-05-12T00:00:00Z" },
            },
          ],
        },
        loading: false,
        error: null,
        refetch: jest.fn(),
      };
    });

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.pinnedItems.map((item) => item.id)).toEqual(["pinned-command-loop"]);
    });

    act(() => {
      result.current.setSearch("profile");
    });

    await waitFor(() => {
      expect(result.current.sorted.map((item) => item.id)).toEqual(["profile-synthesis"]);
      expect(result.current.pinnedItems).toEqual([]);
    });
  });

  it("hydrates Browse search from deep-linked URLs", async () => {
    const searchParams = new URLSearchParams("view=notes&type=file&search=demo-hard-photo");
    mockUseSearchParams.mockReturnValue(searchParams);
    mockUseMcpQuery.mockImplementation((_key: unknown, tool: string) => {
      if (tool === "pin-list") {
        return {
          data: { pins: [] },
          loading: false,
          error: null,
          refetch: jest.fn(),
        };
      }
      if (tool === "brain-discovery") {
        return {
          data: {},
          loading: false,
          error: null,
          refetch: jest.fn(),
        };
      }
      return {
        data: {
          items: [
            {
              id: "/Users/<user>/Projects/Au-vault/notes/2026-05-30-demo-hard-photo.md",
              title: "2026-05-30-demo-hard-photo",
              description: "NORTHWIND LABS PHOTO INVOICE",
              hub: "finance",
              type: "file",
              source_path: "/Users/<user>/Projects/Au-vault/notes/2026-05-30-demo-hard-photo.md",
              metadata: {
                "x-augur-note-type": "file",
                cloud_used: false,
                tags: ["demo", "ocr"],
              },
            },
            {
              id: "~/Projects/Au-vault/notes/2026-05-30-unrelated.md",
              title: "2026-05-30-unrelated",
              description: "A normal finance note",
              hub: "finance",
              type: "file",
              source_path: "~/Projects/Au-vault/notes/2026-05-30-unrelated.md",
              metadata: {
                "x-augur-note-type": "file",
                reviewed: true,
                tags: ["finance"],
              },
            },
          ],
        },
        loading: false,
        error: null,
        refetch: jest.fn(),
      };
    });

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(
      () => useBrowseState({ router: { replace: mockReplace }, searchParams }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => {
      expect(result.current.effectiveViewMode).toBe("notes");
      expect(result.current.search).toBe("demo-hard-photo");
      expect(result.current.sorted.map((item) => item.title)).toEqual([
        "2026-05-30-demo-hard-photo",
      ]);
    });
  });

  it("uses a deep-linked Browse view on the first render", async () => {
    localStorage.setItem("augur:browse:view", "skills");
    const searchParams = new URLSearchParams("view=notes");
    mockUseSearchParams.mockReturnValue(searchParams);

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(
      () => useBrowseState({ router: { replace: mockReplace }, searchParams }),
      { wrapper: createWrapper() },
    );

    expect(result.current.effectiveViewMode).toBe("notes");
  });

  it("pins an unpinned browse card with category and item key metadata", async () => {
    localStorage.setItem("augur:browse:view", "wiki");
    const pinsRefetch = jest.fn();
    (mcpCall as jest.Mock).mockResolvedValue({ added: true });
    mockUseMcpQuery.mockImplementation((_key: unknown, tool: string) => {
      if (tool === "pin-list") {
        return {
          data: { pins: [] },
          loading: false,
          error: null,
          refetch: pinsRefetch,
        };
      }
      return {
        data: {
          items: [
            {
              id: "article-one",
              title: "Article One",
              description: "Wiki article.",
              hub: "workspace",
              type: "wiki",
              source_path: "/vault/wiki/article-one.md",
              metadata: { modified: "2026-05-12T00:00:00Z" },
            },
          ],
        },
        loading: false,
        error: null,
        refetch: jest.fn(),
      };
    });

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.effectiveViewMode).toBe("wiki");
      expect(result.current.sorted).toHaveLength(1);
    });

    await act(async () => {
      await result.current.togglePin(result.current.sorted[0]);
    });

    expect(mcpCall).toHaveBeenCalledWith(
      "pin-add",
      expect.objectContaining({
        category: "wiki",
        itemKey: "wiki::article-one",
        kind: "browse-card",
        title: "Article One",
      }),
    );
    expect(pinsRefetch).toHaveBeenCalled();
    expect(toast.success).toHaveBeenCalled();
  });

  it("does not report unpin success when the scoped pin is missing", async () => {
    localStorage.setItem("augur:browse:view", "wiki");
    const pinsRefetch = jest.fn();
    (mcpCall as jest.Mock).mockResolvedValue({ removed: false });
    mockUseMcpQuery.mockImplementation((_key: unknown, tool: string) => {
      if (tool === "pin-list") {
        return {
          data: {
            pins: [
              {
                category: "wiki",
                itemKey: "wiki::article-one",
                url: "/vault/wiki/article-one.md",
                title: "Article One",
                kind: "browse-card",
                hub: "workspace",
              },
            ],
          },
          loading: false,
          error: null,
          refetch: pinsRefetch,
        };
      }
      return {
        data: {
          items: [
            {
              id: "article-one",
              title: "Article One",
              description: "Wiki article.",
              hub: "workspace",
              type: "wiki",
              source_path: "/vault/wiki/article-one.md",
              metadata: { modified: "2026-05-12T00:00:00Z" },
            },
          ],
        },
        loading: false,
        error: null,
        refetch: jest.fn(),
      };
    });

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.isPinned(result.current.sorted[0])).toBe(true);
    });

    await act(async () => {
      await result.current.togglePin(result.current.sorted[0]);
    });

    expect(pinsRefetch).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalledWith("Pin update failed", expect.any(Object));
    expect(toast.success).not.toHaveBeenCalled();
  });

  it("unpins an existing browse card without optimistic local changes on failure", async () => {
    localStorage.setItem("augur:browse:view", "wiki");
    const pinsRefetch = jest.fn();
    (mcpCall as jest.Mock).mockRejectedValue(new Error("pin service unavailable"));
    mockUseMcpQuery.mockImplementation((_key: unknown, tool: string) => {
      if (tool === "pin-list") {
        return {
          data: {
            pins: [
              {
                category: "wiki",
                itemKey: "wiki::article-one",
                url: "/vault/wiki/article-one.md",
                title: "Article One",
                kind: "browse-card",
                hub: "workspace",
              },
            ],
          },
          loading: false,
          error: null,
          refetch: pinsRefetch,
        };
      }
      return {
        data: {
          items: [
            {
              id: "article-one",
              title: "Article One",
              description: "Wiki article.",
              hub: "workspace",
              type: "wiki",
              source_path: "/vault/wiki/article-one.md",
              metadata: { modified: "2026-05-12T00:00:00Z" },
            },
          ],
        },
        loading: false,
        error: null,
        refetch: jest.fn(),
      };
    });

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.effectiveViewMode).toBe("wiki");
      expect(result.current.pinnedItems.map((item) => item.id)).toEqual(["article-one"]);
      expect(result.current.isPinned(result.current.sorted[0])).toBe(true);
    });

    await act(async () => {
      await result.current.togglePin(result.current.sorted[0]);
    });

    expect(mcpCall).toHaveBeenCalledWith(
      "pin-remove",
      {
        category: "wiki",
        itemKey: "wiki::article-one",
        url: "/vault/wiki/article-one.md",
      },
    );
    expect(pinsRefetch).not.toHaveBeenCalled();
    expect(result.current.pinnedItems.map((item) => item.id)).toEqual(["article-one"]);
    expect(result.current.isPinned(result.current.sorted[0])).toBe(true);
    expect(toast.error).toHaveBeenCalled();
  });

  it("builds and applies exposure status and surface filters from capability metadata", async () => {
    localStorage.setItem("augur:browse:view", "skills");
    mockUseMcpQuery.mockReturnValue({
      data: {
        items: [
          {
            id: "skill:geo-audit",
            title: "Geo Audit",
            description: "Geo skill",
            hub: "ai",
            type: "skill",
            metadata: {
              classificationStatus: "approved",
              primarySurface: "skill",
              ownerKind: "external",
              management: "unmanaged",
              preferredClient: "claude",
            },
          },
          {
            id: "skill:ui-ux-pro-max",
            title: "UI UX Pro Max",
            description: "Design skill",
            hub: "ai",
            type: "skill",
            metadata: {
              classificationStatus: "unclassified",
              primarySurface: "skill",
              ownerKind: "external",
              management: "unmanaged",
              preferredClient: "none",
            },
          },
          {
            id: "command:ask",
            title: "Ask",
            description: "Ask command",
            hub: "ai",
            type: "command",
            metadata: {
              classificationStatus: "approved",
              primarySurface: "command",
              ownerKind: "augur",
              management: "generated",
              preferredClient: "codex",
            },
          },
        ],
      },
      loading: false,
      error: null,
      refetch: jest.fn(),
    });

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.exposureItems).toEqual([
        { id: "approved", label: "Approved" },
        { id: "unclassified", label: "Unclassified" },
      ]);
      expect(result.current.surfaceItems).toEqual([
        { id: "command", label: "Command" },
        { id: "skill", label: "Skill" },
      ]);
    });

    act(() => {
      result.current.setExposureFilter("approved");
    });

    await waitFor(() => {
      expect(result.current.filtered.map((item) => item.id)).toEqual([
        "skill:geo-audit",
        "command:ask",
      ]);
    });

    act(() => {
      result.current.setExposureFilter(null);
      result.current.setSurfaceFilter("command");
    });

    await waitFor(() => {
      expect(result.current.filtered.map((item) => item.id)).toEqual(["command:ask"]);
    });
  });

  it("builds and applies owner, drift, and capability client filters from capability metadata", async () => {
    localStorage.setItem("augur:browse:view", "skills");
    mockUseMcpQuery.mockReturnValue({
      data: {
        items: [
          {
            id: "skill:geo-audit",
            title: "Geo Audit",
            description: "Geo skill",
            hub: "ai",
            type: "skill",
            metadata: {
              capabilityId: "geo-audit",
              ownerKind: "external",
              currentExposure: "browse, claude",
              drift: "duplicate",
            },
          },
          {
            id: "mcp-tool:dashboard-cache-clear",
            title: "Dashboard Cache Clear",
            description: "Clear dashboard cache",
            hub: "ai",
            type: "mcp-tool",
            metadata: {
              capabilityId: "dashboard-cache-clear",
              ownerKind: "augur",
              currentExposure: "codex, gemini, mcp",
              drift: "unclassified_export",
            },
          },
        ],
      },
      loading: false,
      error: null,
      refetch: jest.fn(),
    });

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.ownerItems).toEqual([
        { id: "augur", label: "Augur" },
        { id: "external", label: "External" },
      ]);
      expect(result.current.driftItems).toEqual([
        { id: "duplicate", label: "Duplicate" },
        { id: "unclassified_export", label: "Unclassified Export" },
      ]);
      expect(result.current.capabilityClientItems).toEqual([
        { id: "browse", label: "Browse" },
        { id: "claude", label: "Claude" },
        { id: "codex", label: "Codex" },
        { id: "gemini", label: "Gemini" },
        { id: "mcp", label: "Mcp" },
      ]);
    });

    act(() => {
      result.current.setOwnerFilter("external");
    });

    await waitFor(() => {
      expect(result.current.filtered.map((item) => item.id)).toEqual(["skill:geo-audit"]);
    });

    act(() => {
      result.current.setOwnerFilter(null);
      result.current.setCapabilityClientFilter("gemini");
    });

    await waitFor(() => {
      expect(result.current.filtered.map((item) => item.id)).toEqual([
        "mcp-tool:dashboard-cache-clear",
      ]);
    });
  });

  it("builds and applies capability management and policy scope filters", async () => {
    localStorage.setItem("augur:browse:view", "skills");
    mockUseMcpQuery.mockReturnValue({
      data: {
        items: [
          {
            id: "skill:geo-audit",
            title: "Geo Audit",
            description: "Geo skill",
            hub: "ai",
            type: "skill",
            metadata: {
              capabilityId: "skill:geo-audit",
              scope: "shared",
              capabilityScope: "global",
              management: "manual",
              capabilityManagement: "unmanaged",
            },
          },
          {
            id: "mcp-tool:dashboard-cache-clear",
            title: "Dashboard Cache Clear",
            description: "Clear dashboard cache",
            hub: "ai",
            type: "mcp-tool",
            metadata: {
              capabilityId: "mcp-tool:dashboard-cache-clear",
              scope: "project",
              management: "generated",
            },
          },
        ],
      },
      loading: false,
      error: null,
      refetch: jest.fn(),
    });

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.managementItems).toEqual([
        { id: "generated", label: "Generated" },
        { id: "unmanaged", label: "Unmanaged" },
      ]);
      expect(result.current.policyScopeItems).toEqual([
        { id: "global", label: "Global" },
        { id: "project", label: "Project" },
      ]);
    });

    act(() => {
      result.current.setManagementFilter("unmanaged");
    });

    await waitFor(() => {
      expect(result.current.filtered.map((item) => item.id)).toEqual(["skill:geo-audit"]);
    });

    act(() => {
      result.current.setManagementFilter(null);
      result.current.setPolicyScopeFilter("project");
    });

    await waitFor(() => {
      expect(result.current.filtered.map((item) => item.id)).toEqual([
        "mcp-tool:dashboard-cache-clear",
      ]);
    });
  });

  it("builds command tag filters from quality tiers instead of grade metadata", async () => {
    localStorage.setItem("augur:browse:view", "commands");
    mockUseModeStore.mockImplementation((selector: (state: { mode: string }) => unknown) =>
      selector({ mode: "development" }),
    );
    mockUseMcpQuery.mockReturnValue({
      data: {
        items: [
          {
            id: "command:ask",
            title: "/ask",
            description: "Ask memory",
            hub: "command",
            type: "command",
            metadata: { qualityTier: "A", qualityScore: "88" },
          },
          {
            id: "command:sweep",
            title: "/sweep",
            description: "Sweep stale files",
            hub: "command",
            type: "command",
            metadata: { qualityTier: "C", qualityScore: "56" },
          },
        ],
      },
      loading: false,
      error: null,
      refetch: jest.fn(),
    });

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.effectiveViewMode).toBe("commands");
      expect(result.current.tagItems).toEqual([
        { id: "all", label: "All" },
        { id: "A", label: "A (1)" },
        { id: "C", label: "C (1)" },
      ]);
    });

    act(() => {
      result.current.setTagFilter("A");
    });

    await waitFor(() => {
      expect(result.current.filtered.map((item) => item.id)).toEqual(["command:ask"]);
    });
  });

  it("resets exposure and surface filters when changing browse view", async () => {
    localStorage.setItem("augur:browse:view", "skills");
    mockUseMcpQuery.mockReturnValue({
      data: {
        items: [
          {
            id: "skill:geo-audit",
            title: "Geo Audit",
            description: "Geo skill",
            hub: "ai",
            type: "skill",
            metadata: {
              classificationStatus: "approved",
              primarySurface: "skill",
            },
          },
        ],
      },
      loading: false,
      error: null,
      refetch: jest.fn(),
    });

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.exposureItems).toEqual([{ id: "approved", label: "Approved" }]);
      expect(result.current.surfaceItems).toEqual([{ id: "skill", label: "Skill" }]);
    });

    act(() => {
      result.current.setExposureFilter("approved");
      result.current.setSurfaceFilter("skill");
    });

    await waitFor(() => {
      expect(result.current.exposureFilter).toBe("approved");
      expect(result.current.surfaceFilter).toBe("skill");
    });

    act(() => {
      result.current.changeView("notes");
    });

    expect(result.current.exposureFilter).toBeNull();
    expect(result.current.surfaceFilter).toBeNull();
  });

  it("hydrates background routine detail from the schedule query param", async () => {
    localStorage.setItem("augur:browse:view", "background-routines");
    mockUseSearchParams.mockReturnValue(
      new URLSearchParams("schedule=codex:update-agents-md"),
    );
    mockUseMcpQuery.mockReturnValue({
      data: {
        items: [
          {
            id: "codex:update-agents-md",
            title: "Update AGENTS.md",
            description: "Update AGENTS.md with newly discovered workflows/commands",
            hub: "system",
            type: "background-routines",
            metadata: {
              source_kind: "daemon-script",
              status: "enabled",
              cadence: "triggered by daemon-service or other",
            },
          },
        ],
      },
      loading: false,
      error: null,
      refetch: jest.fn(),
    });

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.effectiveViewMode).toBe("background-routines");
      expect(result.current.selectedSchedule).toBe("codex:update-agents-md");
      expect(result.current.scheduledExecutionDetail?.title).toBe("Update AGENTS.md");
    });
  });

  it("uses the category query param as the initial browse view", async () => {
    localStorage.setItem("augur:browse:view", "skills");
    mockUseSearchParams.mockReturnValue(
      new URLSearchParams("category=documents"),
    );

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.effectiveViewMode).toBe("documents");
      expect(mockUseMcpQuery).toHaveBeenCalledWith(
        ["browse-index", "documents", "all", "", "all"],
        "browse-index",
        "config",
        { args: { category: "documents" } },
      );
    });
  });

  it("keeps overlay duplicates and filters notes by scope", async () => {
    localStorage.setItem("augur:browse:view", "notes");
    mockUseMcpQuery.mockReturnValue({
      data: {
        items: [
          {
            id: "daily-note",
            title: "Daily Note",
            description: "Shared note",
            hub: "workspace",
            type: "vault",
            path: "notes/daily.md",
            metadata: {
              journey_category: "notes",
              vault_scope: "shared",
              source_root: "vault",
              format: "md",
              skill: "notes",
            },
          },
          {
            id: "daily-note",
            title: "Daily Note",
            description: "Private note",
            hub: "workspace",
            type: "vault",
            path: "notes/daily.md",
            metadata: {
              journey_category: "notes",
              vault_scope: "private",
              source_root: "private",
              format: "md",
              skill: "notes",
            },
          },
        ],
      },
      loading: false,
      error: null,
      refetch: jest.fn(),
    });

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.effectiveViewMode).toBe("notes");
      expect(result.current.filtered.map((item) => item.metadata?.vault_scope)).toEqual([
        "shared",
        "private",
      ]);
      expect(result.current.scopeItems.map((item) => item.id)).toEqual([
        "all",
        "shared",
        "private",
        "packet",
      ]);
    });

    act(() => {
      result.current.setScopeFilter("private");
    });

    await waitFor(() => {
      expect(result.current.filtered.map((item) => item.metadata?.vault_scope)).toEqual([
        "private",
      ]);
      expect(mockUseMcpQuery).toHaveBeenCalledWith(
        ["browse-index", "vault", "notes", "", "private"],
        "browse-index",
        "config",
        { args: { category: "vault", journey_category: "notes", scope: "private" } },
      );
    });
  });

  it("exposes sweepFilteredItems and sweepFilterSummary from active filters", async () => {
    localStorage.setItem("augur:browse:view", "notes");
    mockUseMcpQuery.mockReturnValue({
      data: {
        items: [
          {
            id: "note-alpha-private",
            title: "Alpha Note",
            description: "Private markdown note",
            hub: "workspace",
            type: "vault",
            path: "notes/alpha.md",
            metadata: {
              journey_category: "notes",
              vault_scope: "private",
              source_root: "private",
              format: "md",
              skill: "knowledge",
            },
          },
          {
            id: "note-beta-shared",
            title: "Beta Note",
            description: "Shared text note",
            hub: "workspace",
            type: "vault",
            path: "notes/beta.txt",
            metadata: {
              journey_category: "notes",
              vault_scope: "shared",
              source_root: "vault",
              format: "txt",
              skill: "knowledge",
            },
          },
        ],
      },
      loading: false,
      error: null,
      refetch: jest.fn(),
    });

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.effectiveViewMode).toBe("notes");
    });

    act(() => {
      result.current.setSearch("alpha");
      result.current.setTagFilter("md");
      result.current.setScopeFilter("private");
    });

    await waitFor(() => {
      expect(result.current.sweepFilteredItems.map((item) => item.id)).toEqual([
        "note-alpha-private",
      ]);
      expect(result.current.sweepFilterSummary).toEqual({
        search: "alpha",
        scope: "private",
        tag: "md",
        kind: "all",
        source: "all",
        viewMode: "notes",
      });
    });
  });

  it("deactivates unified search results when the query or category scope changes", async () => {
    (mcpCall as jest.Mock).mockResolvedValue({
      success: true,
      results: [
        {
          file: "project-brain/capabilities/skills/knowledge/SKILL.md",
          content: "knowledge management result",
          scope: "brain",
        },
      ],
    });

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    await act(async () => {
      result.current.setSearch("knowledge management");
      await result.current.handleSemanticSearch("knowledge management");
    });

    expect(result.current.semanticResults).toHaveLength(1);
    expect(result.current.semanticSearchActive).toBe(true);
    expect(result.current.semanticResultsActive).toBe(true);

    act(() => {
      result.current.setSearch("different query");
    });

    expect(result.current.semanticResults).toHaveLength(0);
    expect(result.current.semanticSearchActive).toBe(false);
    expect(result.current.semanticResultsActive).toBe(false);

    await act(async () => {
      result.current.setSearch("knowledge management");
      await result.current.handleSemanticSearch("knowledge management");
    });

    expect(result.current.semanticResultsActive).toBe(true);

    act(() => {
      result.current.setTypeFilter("decision");
    });

    expect(result.current.semanticResults).toHaveLength(1);
    expect(result.current.semanticSearchActive).toBe(false);
    expect(result.current.semanticResultsActive).toBe(false);

    act(() => {
      result.current.changeView("notes");
    });

    expect(result.current.semanticResults).toHaveLength(0);
    expect(result.current.semanticResultsActive).toBe(false);
    expect(result.current.semanticSearched).toBe(false);
  });

  it("deactivates unified search results when Notes classification filters change", async () => {
    localStorage.setItem("augur:browse:view", "notes");
    (mcpCall as jest.Mock).mockResolvedValue({
      success: true,
      results: [
        {
          file: "sources/urls/github-repo.md",
          content: "GitHub repository result",
          scope: "brain",
        },
      ],
    });

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.effectiveViewMode).toBe("notes");
    });

    await act(async () => {
      result.current.setSearch("github repository");
      await result.current.handleSemanticSearch("github repository");
    });

    expect(result.current.semanticResults).toHaveLength(1);
    expect(result.current.semanticResultsActive).toBe(true);

    act(() => result.current.setNoteDomainFilter("projects"));

    expect(result.current.semanticResults).toHaveLength(1);
    expect(result.current.semanticSearchActive).toBe(false);
    expect(result.current.semanticResultsActive).toBe(false);
  });

  it("ignores failed unified search completions after the query or filter scope changes", async () => {
    const createDeferredFailure = () => {
      let reject!: (error: Error) => void;
      const promise = new Promise((_, rejectPromise) => {
        reject = rejectPromise;
      });
      return { promise, reject };
    };

    const queryFailure = createDeferredFailure();
    (mcpCall as jest.Mock).mockReturnValueOnce(queryFailure.promise);

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    await act(async () => {
      result.current.setSearch("foo");
    });

    let querySearch: Promise<void>;
    act(() => {
      querySearch = result.current.handleSemanticSearch("foo");
    });

    act(() => {
      result.current.setSearch("bar");
    });

    await act(async () => {
      queryFailure.reject(new Error("foo failed"));
      await querySearch;
    });

    expect(result.current.search).toBe("bar");
    expect(result.current.semanticError).toBeNull();
    expect(result.current.semanticSearchActive).toBe(false);
    expect(result.current.semanticSearched).toBe(false);

    const filterFailure = createDeferredFailure();
    (mcpCall as jest.Mock).mockReturnValueOnce(filterFailure.promise);

    await act(async () => {
      result.current.setSearch("baz");
    });

    let filterSearch: Promise<void>;
    act(() => {
      filterSearch = result.current.handleSemanticSearch("baz");
    });

    act(() => {
      result.current.setTypeFilter("decision");
    });

    await act(async () => {
      filterFailure.reject(new Error("baz failed"));
      await filterSearch;
    });

    expect(result.current.search).toBe("baz");
    expect(result.current.typeFilter).toBe("decision");
    expect(result.current.semanticError).toBeNull();
    expect(result.current.semanticSearchActive).toBe(false);
    expect(result.current.semanticSearched).toBe(false);
  });

  it("keeps current failed unified searches active for scoped error context", async () => {
    (mcpCall as jest.Mock).mockResolvedValue({
      success: false,
      error: "Search backend unavailable",
    });

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    await act(async () => {
      result.current.setSearch("broken pitch lookup");
      await result.current.handleSemanticSearch("broken pitch lookup");
    });

    expect(result.current.semanticError).toBe("Search backend unavailable");
    expect(result.current.semanticSearched).toBe(true);
    expect(result.current.semanticSearchActive).toBe(true);
    expect(result.current.semanticResultsActive).toBe(true);
    expect(result.current.semanticResults).toHaveLength(0);

    act(() => {
      result.current.setTypeFilter("decision");
    });

    expect(result.current.semanticSearchActive).toBe(false);
  });

  it("keeps empty successful unified searches active for the result surface", async () => {
    (mcpCall as jest.Mock).mockResolvedValue({
      success: true,
      results: [],
    });

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    await act(async () => {
      result.current.setSearch("missing pitch artifact");
      await result.current.handleSemanticSearch("missing pitch artifact");
    });

    expect(result.current.semanticResults).toHaveLength(0);
    expect(result.current.semanticSearched).toBe(true);
    expect(result.current.semanticSearchActive).toBe(true);
    expect(result.current.semanticResultsActive).toBe(true);

    act(() => {
      result.current.setTypeFilter("decision");
    });

    expect(result.current.semanticSearchActive).toBe(false);
    expect(result.current.semanticResultsActive).toBe(false);
  });

  it("shows the operation-first Browse categories in operation mode", async () => {
    mockUseModeStore.mockImplementation((selector: (state: { mode: string }) => unknown) =>
      selector({ mode: "operation" }),
    );

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    await waitFor(() => {
      // Three-concept regroup (spec 2026-06-09 §3 amended 2026-06-11):
      // context, prompt, loop groups; actions removed by ADR-806.
      expect(result.current.visibleCategories.map((category) => category.id)).toEqual([
        "notes",
        "documents",
        "wiki",
        "pages",
        "archive",
        "prompts",
        "commands",
        "skills",
        "background-routines",
        "agent-profiles",
        "integrations",
      ]);
    });
  });

  it("keeps Pages visible while moving commands, profiles, and MCP servers to development mode", async () => {
    localStorage.setItem("augur:browse:view", "dashboard-surfaces");
    mockUseModeStore.mockImplementation((selector: (state: { mode: string }) => unknown) =>
      selector({ mode: "development" }),
    );

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.visibleCategories.map((category) => category.id)).toEqual(
        expect.arrayContaining([
          "pages",
          "agent-profiles",
          "commands",
          "mcp-servers",
          "mcp-tools",
          "system-metadata",
        ]),
      );
      expect(result.current.activeCategory.label).toBe("Pages");
    });
  });

  it("normalizes legacy Browse URLs to Pages", async () => {
    mockUseSearchParams.mockReturnValue(new URLSearchParams("category=dashboard-surfaces"));
    mockUseModeStore.mockImplementation((selector: (state: { mode: string }) => unknown) =>
      selector({ mode: "development" }),
    );

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.effectiveViewMode).toBe("pages");
      expect(result.current.activeCategory.label).toBe("Pages");
    });
  });

  it("shows dashboard surface fallback pages when the pages index is not indexed", async () => {
    mockPluginTabRegistry.brain = {
      tabs: [
        {
          href: "/workspace/memory",
          label: "Workspace",
          icon: "PanelsTopLeft",
          pageSource: "tsx",
          skillId: "brain",
        },
      ],
      overflow: [],
      configPages: [],
      autoPages: [],
    };
    mockUseSearchParams.mockReturnValue(new URLSearchParams("category=pages"));
    mockUseModeStore.mockImplementation((selector: (state: { mode: string }) => unknown) =>
      selector({ mode: "development" }),
    );
    mockUseMcpQuery.mockReturnValue({
      data: { status: "not_indexed", items: [] },
      loading: false,
      error: null,
      refetch: jest.fn(),
    });

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.effectiveViewMode).toBe("pages");
      expect(result.current.notIndexed).toBe(false);
      expect(result.current.sorted.map((item) => item.id)).toContain("live:/workspace/memory");
    });
  });

  it("keeps dashboard surface pages visible under active folder context", async () => {
    mockPluginTabRegistry.brain = {
      tabs: [
        {
          href: "/workspace/memory",
          label: "Workspace",
          icon: "PanelsTopLeft",
          pageSource: "tsx",
          skillId: "brain",
        },
      ],
      overflow: [],
      configPages: [],
      autoPages: [],
    };
    mockUseSearchParams.mockReturnValue(new URLSearchParams("category=pages"));
    mockUseModeStore.mockImplementation((selector: (state: { mode: string }) => unknown) =>
      selector({ mode: "development" }),
    );
    mockUseMcpQuery.mockImplementation((_key: unknown, tool: string) => {
      if (tool === "browse-index") {
        return {
          data: { status: "not_indexed", items: [] },
          loading: false,
          error: null,
          refetch: jest.fn(),
        };
      }
      if (tool === "artifacts-list") {
        return {
          data: { artifacts: [] },
          loading: false,
          error: null,
          refetch: jest.fn(),
        };
      }
      if (tool === "pin-list") {
        return {
          data: { pins: [] },
          loading: false,
          error: null,
          refetch: jest.fn(),
        };
      }
      if (tool === "brain-active-context") {
        return {
          data: {
            success: true,
            context: { scope: "brain", brain_id: "project-augur", label: "Augur project" },
            options: [],
          },
          loading: false,
          error: null,
          refetch: jest.fn(),
        };
      }
      if (tool === "brain-discovery") {
        return { data: {}, loading: false, error: null, refetch: jest.fn() };
      }
      return {
        data: { items: [] },
        loading: false,
        error: null,
        refetch: jest.fn(),
      };
    });

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.effectiveViewMode).toBe("pages");
      expect(result.current.activeFolderContext.label).toBe("Augur project");
      expect(result.current.sorted.map((item) => item.id)).toContain("live:/workspace/memory");
    });
  });

  it("attaches indexed source paths to live Pages items in actual Browse state", async () => {
    mockPluginTabRegistry.brain = {
      tabs: [
        {
          href: "/workspace/memory",
          label: "Workspace",
          icon: "PanelsTopLeft",
          pageSource: "tsx",
          skillId: "brain",
        },
      ],
      overflow: [],
      configPages: [],
      autoPages: [],
    };
    mockUseSearchParams.mockReturnValue(new URLSearchParams("category=pages"));
    mockUseModeStore.mockImplementation((selector: (state: { mode: string }) => unknown) =>
      selector({ mode: "development" }),
    );
    mockUseMcpQuery.mockImplementation((_key: unknown, tool: string) => {
      if (tool === "browse-index") {
        return {
          data: {
            items: [
              {
                route: "/workspace/memory",
                source_path: "/Users/me/Projects/Augur/project-brain/capabilities/skills/brain/SKILL.md",
              },
            ],
          },
          loading: false,
          error: null,
          refetch: jest.fn(),
        };
      }
      if (tool === "artifacts-list") {
        return {
          data: { artifacts: [] },
          loading: false,
          error: null,
          refetch: jest.fn(),
        };
      }
      if (tool === "pin-list") {
        return {
          data: { pins: [] },
          loading: false,
          error: null,
          refetch: jest.fn(),
        };
      }
      return {
        data: { items: [] },
        loading: false,
        error: null,
        refetch: jest.fn(),
      };
    });

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    await waitFor(() => {
      const livePage = result.current.sorted.find((item) => item.id === "live:/workspace/memory");
      expect(livePage?.metadata?.sourcePath).toBe(
        "/Users/me/Projects/Augur/project-brain/capabilities/skills/brain/SKILL.md",
      );
    });
  });

  it("shows wiki pages as a normal Browse category in operation mode", async () => {
    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    await waitFor(() => {
      expect(result.current.visibleCategories.map((category) => category.id)).toContain("wiki");
    });
  });

  it("removes the schedule query param when closing background routine detail", async () => {
    localStorage.setItem("augur:browse:view", "background-routines");
    mockUseSearchParams.mockReturnValue(
      new URLSearchParams("schedule=codex:update-agents-md"),
    );
    mockUseMcpQuery.mockReturnValue({
      data: { items: [] },
      loading: false,
      error: null,
      refetch: jest.fn(),
    });

    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    result.current.closeDetail();
    expect(mockReplace).toHaveBeenCalledWith("/browse");
  });

  it("runs browse card action targets through raw CLI exec", async () => {
    const { useBrowseState } = await import("@/app/(views)/browse/useBrowseState");
    const { result } = renderHook(() => useBrowseState(), { wrapper: createWrapper() });

    result.current.handleRunMcp("/harden knowledge:ide");

    await waitFor(() => {
      expect(mockRunCliExecPrompt).toHaveBeenCalledWith(
        "/harden knowledge",
        expect.objectContaining({
          onStream: expect.any(Function),
          onStreamClose: expect.any(Function),
        }),
      );
    });
  });

});
