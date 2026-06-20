import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createQueryWrapper } from "../../helpers/component-test-utils";

const mockRunAction = jest.fn().mockResolvedValue({ type: "success", message: "Done" });
jest.mock("@/hooks/useActionRunner", () => ({
  useActionRunner: () => ({ runAction: mockRunAction, isExecuting: false }),
}));

import ActionFormModal from "@/components/blocks/ActionFormModal";
import type { FormField } from "@/lib/plugin-schema/types";

const { Wrapper } = createQueryWrapper();

const baseFields: FormField[] = [
  { name: "title", label: "Title", type: "text", required: true },
  { name: "status", label: "Status", type: "select", options: [
    { value: "active", label: "Active" },
    { value: "archived", label: "Archived" },
  ]},
];

describe("ActionFormModal", () => {
  beforeEach(() => { mockRunAction.mockClear(); });

  it("renders form fields from config", () => {
    render(
      <ActionFormModal
        open={true}
        onClose={jest.fn()}
        actionId="edit-item"
        actionLabel="Edit Item"
        dispatch="fire"
        fields={baseFields}
      />,
      { wrapper: Wrapper },
    );
    expect(screen.getByLabelText("Title")).toBeInTheDocument();
    expect(screen.getByLabelText("Status")).toBeInTheDocument();
  });

  it("validates required fields before submit", async () => {
    const user = userEvent.setup();
    render(
      <ActionFormModal
        open={true}
        onClose={jest.fn()}
        actionId="edit-item"
        actionLabel="Edit Item"
        dispatch="fire"
        fields={baseFields}
      />,
      { wrapper: Wrapper },
    );
    await user.click(screen.getByRole("button", { name: /run action/i }));
    expect(mockRunAction).not.toHaveBeenCalled();
  });

  it("dispatches action with form values on valid submit", async () => {
    const onClose = jest.fn();
    const user = userEvent.setup();
    render(
      <ActionFormModal
        open={true}
        onClose={onClose}
        actionId="edit-item"
        actionLabel="Edit Item"
        dispatch="fire"
        fields={baseFields}
      />,
      { wrapper: Wrapper },
    );
    await user.type(screen.getByLabelText("Title"), "My Item");
    await user.click(screen.getByRole("button", { name: /run action/i }));
    await waitFor(() => {
      expect(mockRunAction).toHaveBeenCalledWith(
        expect.objectContaining({
          id: "edit-item",
          dispatch: "fire",
          args: expect.objectContaining({ title: "My Item" }),
        }),
      );
    });
  });

  it("disables submit until confirmText matches", async () => {
    const user = userEvent.setup();
    render(
      <ActionFormModal
        open={true}
        onClose={jest.fn()}
        actionId="delete-item"
        actionLabel="Delete Item"
        dispatch="fire"
        fields={[]}
        confirmText="DELETE"
      />,
      { wrapper: Wrapper },
    );
    const submitBtn = screen.getByRole("button", { name: /run action/i });
    expect(submitBtn).toBeDisabled();
    await user.type(screen.getByPlaceholderText(/type DELETE/i), "DELETE");
    expect(submitBtn).toBeEnabled();
  });

  it("invalidates block data queries when refetch is specified", async () => {
    const user = userEvent.setup();
    const { queryClient } = createQueryWrapper();
    const invalidateSpy = jest.spyOn(queryClient, "invalidateQueries");

    const WrapperWithClient = ({ children }: { children: React.ReactNode }) => {
      const { QueryClientProvider } = require("@tanstack/react-query");
      return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
    };

    render(
      <ActionFormModal
        open={true}
        onClose={jest.fn()}
        actionId="edit-item"
        actionLabel="Edit"
        dispatch="fire"
        fields={[{ name: "title", label: "Title", type: "text" as const }]}
        refetch={["stats-block", "chart-block"]}
      />,
      { wrapper: WrapperWithClient },
    );

    await user.type(screen.getByLabelText("Title"), "Test");
    await user.click(screen.getByRole("button", { name: /run action/i }));

    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["block-data"] });
    });

    invalidateSpy.mockRestore();
  });

  it("does not render when open is false", () => {
    const { container } = render(
      <ActionFormModal
        open={false}
        onClose={jest.fn()}
        actionId="test"
        actionLabel="Test"
        dispatch="fire"
        fields={baseFields}
      />,
      { wrapper: Wrapper },
    );
    expect(container.querySelector("[role='dialog']")).not.toBeInTheDocument();
  });
});
