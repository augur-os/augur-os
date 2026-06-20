import { fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { createQueryWrapper } from "../helpers/component-test-utils";

const { Wrapper } = createQueryWrapper();

jest.mock("next/navigation", () => ({
  redirect: jest.fn(),
  notFound: jest.fn(),
  useRouter: () => ({ push: jest.fn(), replace: jest.fn(), back: jest.fn() }),
  usePathname: () => "/settings",
  useSearchParams: () => ({ get: jest.fn() }),
}));

const mockUsePathConfig = jest.fn();

jest.mock("@/components/StorageSection", () => ({
  __esModule: true,
  usePathConfig: () => mockUsePathConfig(),
}));

jest.mock("@/components/storage/RagIndexCard", () => ({
  __esModule: true,
  RagIndexCard: () => <div data-testid="rag-index-card">RAG Index Card</div>,
}));

jest.mock("@/components/EditorPreferences", () => ({
  __esModule: true,
  EditorPreferences: () => (
    <div data-testid="editor-preferences">Editor Preferences</div>
  ),
}));

import GeneralTab from "@/app/settings/tabs/GeneralTab";

describe("GeneralTab", () => {
  const pathRefresh = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    mockUsePathConfig.mockReturnValue({
      config: null,
      loading: false,
      error: null,
      refresh: pathRefresh,
    });
  });

  it("renders loading skeletons while storage config is loading", () => {
    mockUsePathConfig.mockReturnValue({
      config: null,
      loading: true,
      error: null,
      refresh: pathRefresh,
    });

    render(<GeneralTab />, { wrapper: Wrapper });
    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders storage cards and total storage when config exists", () => {
    // GeneralTab reads the categorized PathConfig shape (core/data/plugins/
    // runtime) from get-path-config and maps each category to a friendly label
    // (core→Code, data→Vault, plugins→Skills, runtime→Runtime).
    mockUsePathConfig.mockReturnValue({
      config: {
        success: true,
        core: { id: "core", path: "/tmp/repo", size_mb: 10, gitignored: false, subdirs: [] },
        data: { id: "data", path: "/tmp/vault", size_mb: 20, gitignored: false, subdirs: [] },
        plugins: { id: "plugins", path: "/tmp/plugins", size_mb: 30, gitignored: false, subdirs: [] },
        runtime: { id: "runtime", path: "/tmp/state", size_mb: 40, gitignored: true, subdirs: [] },
        is_monorepo: false,
        repo_count: 1,
        rag_index: { path: "/tmp/rag", size_mb: 5, project_count: 0, exists: true },
      },
      loading: false,
      error: null,
      refresh: pathRefresh,
    });

    render(<GeneralTab />, { wrapper: Wrapper });

    // Target card titles by heading role — some categories also render a
    // group badge with the same word (e.g. the "Runtime" group badge).
    expect(screen.getByRole("heading", { name: "Code" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Vault" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Skills" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Runtime" })).toBeInTheDocument();
    expect(screen.getByText("Total Storage: 105 MB")).toBeInTheDocument();
    expect(screen.getByTestId("rag-index-card")).toBeInTheDocument();
  });

  it("shows editor preferences by default and hides them when filter is toggled off", () => {
    render(<GeneralTab />, { wrapper: Wrapper });
    expect(screen.getByTestId("editor-preferences")).toBeInTheDocument();
    expect(screen.queryByText("Dashboard Mode")).not.toBeInTheDocument();

    fireEvent.click(screen.getByText("Editors"));
    expect(screen.queryByTestId("editor-preferences")).not.toBeInTheDocument();
  });

  // Dashboard Mode was extracted from GeneralTab into DashboardModeCard on the
  // Appearance settings page (ADR-773), so GeneralTab no longer owns that
  // toggle. Coverage for the mode card belongs with the Appearance page.

  it("shows empty state when all filters are cleared", () => {
    render(<GeneralTab />, { wrapper: Wrapper });

    fireEvent.click(screen.getByText("None"));
    expect(screen.getByText("Select a filter to view items")).toBeInTheDocument();
    expect(screen.queryByTestId("editor-preferences")).not.toBeInTheDocument();
  });

  it("calls storage refresh when refresh button is clicked", () => {
    render(<GeneralTab />, { wrapper: Wrapper });

    const refreshButton = screen.getByRole("button", {
      name: "Refresh storage paths",
    });
    fireEvent.click(refreshButton);
    expect(pathRefresh).toHaveBeenCalledTimes(1);
  });
});
