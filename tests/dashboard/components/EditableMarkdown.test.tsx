import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import EditableMarkdown from "@/components/EditableMarkdown";

const mockUpdateSkillDoc = jest.fn();

jest.mock("@/lib/mcp/useMcpMutation", () => ({
  useMcpMutation: () => ({
    mutate: mockUpdateSkillDoc,
    loading: false,
    error: null,
  }),
}));

describe("EditableMarkdown", () => {
  beforeEach(() => {
    mockUpdateSkillDoc.mockReset();
    mockUpdateSkillDoc.mockResolvedValue({ success: true });
  });

  it("saves editable skill markdown through the skill-doc MCP mutation", async () => {
    render(
      <EditableMarkdown
        markdown="# Old Heading"
        editable
        skillId="adr"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Edit markdown" }));
    fireEvent.change(screen.getByLabelText("Markdown source"), {
      target: { value: "# New Heading" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save markdown" }));

    await waitFor(() => {
      expect(mockUpdateSkillDoc).toHaveBeenCalledWith({
        skill_id: "adr",
        content: "# New Heading",
      });
    });

    expect(screen.getByTestId("react-markdown")).toHaveTextContent(
      "New Heading",
    );
  });

  it("keeps non-editable markdown in preview-only mode", () => {
    render(<EditableMarkdown markdown="# Preview Only" />);

    expect(screen.getByTestId("react-markdown")).toHaveTextContent(
      "Preview Only",
    );
    expect(
      screen.queryByRole("button", { name: "Edit markdown" }),
    ).not.toBeInTheDocument();
  });
});
