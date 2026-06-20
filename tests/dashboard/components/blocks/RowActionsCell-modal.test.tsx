/**
 * @jest-environment jsdom
 */
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import { createQueryWrapper } from "../../helpers/component-test-utils";

const mockRunAction = jest.fn().mockResolvedValue({ type: "success", message: "Done" });
jest.mock("@/hooks/useActionRunner", () => ({
  useActionRunner: () => ({ runAction: mockRunAction, isExecuting: false }),
}));

import RowActionsCell from "@/components/blocks/RowActionsCell";

const { Wrapper } = createQueryWrapper();

describe("RowActionsCell with fields", () => {
  beforeEach(() => { mockRunAction.mockClear(); });

  it("opens ActionFormModal when action has fields", async () => {
    render(
      <RowActionsCell
        actions={[
          {
            id: "edit",
            icon: "Pencil",
            label: "Edit",
            dispatch: "fire",
            fields: [
              { name: "title", label: "Title", type: "text" as const, required: true },
            ],
          },
        ]}
        row={{ id: "1", title: "Test" }}
      />,
      { wrapper: Wrapper },
    );

    fireEvent.click(screen.getByTitle("Edit"));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByLabelText("Title")).toBeInTheDocument();
  });

  it("dispatches directly when action has no fields", () => {
    render(
      <RowActionsCell
        actions={[
          { id: "delete", icon: "Trash", label: "Delete", dispatch: "fire" },
        ]}
        row={{ id: "1" }}
      />,
      { wrapper: Wrapper },
    );

    fireEvent.click(screen.getByTitle("Delete"));
    expect(mockRunAction).toHaveBeenCalled();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
