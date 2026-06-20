/**
 * @jest-environment jsdom
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import { BrowseAttachDocumentSourceDialog } from "@/app/(views)/browse/BrowseAttachDocumentSourceDialog";
import { mcpCall } from "@/lib/mcp/client";

jest.mock("@/lib/mcp/client", () => ({
  mcpCall: jest.fn().mockResolvedValue({ success: true, record: { id: "project-y-drive" } }),
}));

jest.mock("sonner", () => ({
  toast: { success: jest.fn(), error: jest.fn(), loading: jest.fn(() => "toast-1") },
}));

describe("BrowseAttachDocumentSourceDialog", () => {
  beforeEach(() => jest.clearAllMocks());

  it("collects shared source fields and calls the attachment MCP tool", async () => {
    const onAttached = jest.fn();
    const onOpenChange = jest.fn();

    render(
      <BrowseAttachDocumentSourceDialog
        open
        brainId="project-y"
        brainLabel="Project Y"
        onOpenChange={onOpenChange}
        onAttached={onAttached}
      />,
    );

    fireEvent.change(screen.getByLabelText("Source name"), { target: { value: "Project Y Drive" } });
    fireEvent.change(screen.getByLabelText("Shared URL or remote id"), { target: { value: "folders/abc123" } });
    fireEvent.change(screen.getByLabelText("Summary"), { target: { value: "Shared project references." } });
    fireEvent.click(screen.getByRole("button", { name: "Attach source" }));

    await waitFor(() =>
      expect(mcpCall).toHaveBeenCalledWith("attach-project-document-source", {
        source_id: "project-y-drive",
        name: "Project Y Drive",
        provider: "google-drive",
        remote_id: "folders/abc123",
        attached_brain_ids: ["project-y"],
        catalog_summary: "Shared project references.",
        summary_status: "human",
      }),
    );
    expect(onAttached).toHaveBeenCalledTimes(1);
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
