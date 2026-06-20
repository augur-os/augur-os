import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import MarkdownBlock from "@/components/blocks/types/MarkdownBlock";

jest.mock("@/lib/blocks/useBlockData", () => ({
  useBlockData: () => ({
    data: null,
    loading: false,
    error: null,
    invalidate: jest.fn(),
    refetch: jest.fn(),
  }),
}));

const mockUpdateSkillDoc = jest.fn();

jest.mock("@/lib/mcp/useMcpMutation", () => ({
  useMcpMutation: () => ({
    mutate: mockUpdateSkillDoc,
    loading: false,
    error: null,
  }),
}));

describe("MarkdownBlock", () => {
  beforeEach(() => {
    mockUpdateSkillDoc.mockReset();
    mockUpdateSkillDoc.mockResolvedValue({ success: true });
  });

  it("renders markdown content through the shared markdown renderer", () => {
    render(
      <MarkdownBlock
        instanceId="docs"
        mode="compact"
        config={{
          title: "Content",
          content: `<!-- AUTO-GENERATED FILE - DO NOT EDIT DIRECTLY -->

# ADR

| Status | Implemented |
| --- | --- |
| Owner | Augur |`,
        }}
      />,
    );

    const rendered = screen.getByTestId("react-markdown");
    expect(rendered).toHaveTextContent("ADR");
    expect(rendered).toHaveTextContent("Status");
    expect(rendered).not.toHaveTextContent("AUTO-GENERATED");
  });

  it("enables editing for skill documentation markdown blocks", async () => {
    render(
      <MarkdownBlock
        instanceId="docs"
        mode="compact"
        dataSource={{ mcpTool: "get-skill-doc" }}
        config={{
          title: "Content",
          skillId: "adr",
          content: "# Old Body",
        }}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Edit markdown" }));
    fireEvent.change(screen.getByLabelText("Markdown source"), {
      target: { value: "# New Body" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save markdown" }));

    await waitFor(() => {
      expect(mockUpdateSkillDoc).toHaveBeenCalledWith({
        skill_id: "adr",
        content: "# New Body",
      });
    });

    expect(screen.getByTestId("react-markdown")).toHaveTextContent("New Body");
  });

  it("keeps generated skill documentation blocks read-only", () => {
    render(
      <MarkdownBlock
        instanceId="docs"
        mode="compact"
        dataSource={{ mcpTool: "get-skill-doc" }}
        data={{
          content: "# Generated Command",
          editable: false,
          generated: true,
        }}
        config={{
          title: "Content",
          skillId: "adr",
        }}
      />,
    );

    expect(screen.getByTestId("react-markdown")).toHaveTextContent(
      "Generated Command",
    );
    expect(
      screen.queryByRole("button", { name: "Edit markdown" }),
    ).not.toBeInTheDocument();
  });
});
