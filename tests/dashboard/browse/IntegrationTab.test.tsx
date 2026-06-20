/**
 * @jest-environment jsdom
 */
import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";

const mockUseMcpQuery = jest.fn();

jest.mock("@/lib/mcp/useMcpQuery", () => ({
  useMcpQuery: (...args: unknown[]) => mockUseMcpQuery(...args),
}));

jest.mock("@/components/Markdown", () => ({
  __esModule: true,
  default: ({ markdown }: { markdown: string }) => (
    <div data-testid="markdown">{markdown}</div>
  ),
}));

const { IntegrationTab } = require("@/components/browse/IntegrationTab") as typeof import("@/components/browse/IntegrationTab");

describe("IntegrationTab", () => {
  beforeEach(() => {
    mockUseMcpQuery.mockReset();
  });

  it("shows loading state while the CLI reference is pending", () => {
    mockUseMcpQuery.mockReturnValue({
      data: null,
      loading: true,
      error: null,
      refetch: jest.fn(),
    });

    render(<IntegrationTab skillId="knowledge" skillLabel="Knowledge" />);

    expect(screen.getByText("Loading CLI reference…")).toBeInTheDocument();
    expect(mockUseMcpQuery).toHaveBeenCalledWith(
      ["skill-cli-help", "knowledge"],
      "get-skill-cli-help",
      "config",
      {
        enabled: true,
        args: { skill_id: "knowledge" },
      },
    );
  });

  it("does not render previous help output while a new skill is loading", () => {
    mockUseMcpQuery.mockReturnValue({
      data: {
        defaultCli: "codex",
        markdown: "Old skill help",
      },
      loading: true,
      error: null,
      refetch: jest.fn(),
    });

    render(<IntegrationTab skillId="knowledge" skillLabel="Knowledge" />);

    expect(screen.getByText("Loading CLI reference…")).toBeInTheDocument();
    expect(screen.queryByText("Default CLI: codex")).not.toBeInTheDocument();
    expect(screen.queryByTestId("markdown")).not.toBeInTheDocument();
  });

  it("shows an error state when the MCP query fails", () => {
    mockUseMcpQuery.mockReturnValue({
      data: null,
      loading: false,
      error: "Tool get-skill-cli-help is not registered",
      refetch: jest.fn(),
    });

    render(<IntegrationTab skillId="knowledge" skillLabel="Knowledge" />);

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Tool get-skill-cli-help is not registered",
    );
  });

  it("shows an empty state when no CLI reference is available", () => {
    mockUseMcpQuery.mockReturnValue({
      data: null,
      loading: false,
      error: null,
      refetch: jest.fn(),
    });

    render(<IntegrationTab skillId="knowledge" skillLabel="Knowledge" />);

    expect(
      screen.getByText("No CLI reference is available for this skill yet."),
    ).toBeInTheDocument();
  });

  it("does not render stale data when no skill is selected", () => {
    mockUseMcpQuery.mockReturnValue({
      data: {
        defaultCli: "codex",
        markdown: "Old skill help",
      },
      loading: false,
      error: null,
      refetch: jest.fn(),
    });

    render(<IntegrationTab skillId={null} />);

    expect(
      screen.getByText("Select a skill to load its CLI reference."),
    ).toBeInTheDocument();
    expect(screen.queryByText("Default CLI: codex")).not.toBeInTheDocument();
    expect(screen.queryByTestId("markdown")).not.toBeInTheDocument();
  });

  it("renders the default CLI and help output when data is available", () => {
    mockUseMcpQuery.mockReturnValue({
      data: {
        defaultCli: "codex",
        markdown: "## codex\n\nUse `codex --help` for full options.",
      },
      loading: false,
      error: null,
      refetch: jest.fn(),
    });

    render(<IntegrationTab skillId="knowledge" skillLabel="Knowledge" />);

    expect(screen.getByText("Default CLI: codex")).toBeInTheDocument();
    expect(screen.getByTestId("markdown")).toHaveTextContent(
      "Use `codex --help` for full options.",
    );
  });
});
