/**
 * @jest-environment jsdom
 */
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import { SelectionActionBar } from "@/components/shared/SelectionActionBar";
import { selectionActionsForViewMode } from "@/lib/browse/selectionActions";

describe("SelectionActionBar", () => {
  it("shows the count and only applicable actions, wiring callbacks", () => {
    const onAction = jest.fn();
    const onSelectAll = jest.fn();
    const onClear = jest.fn();
    render(
      <SelectionActionBar
        count={2}
        actions={selectionActionsForViewMode("notes")}
        onAction={onAction}
        onSelectAllVisible={onSelectAll}
        onClear={onClear}
      />,
    );
    expect(screen.getByText("2 selected")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Send to chat" }));
    expect(onAction).toHaveBeenCalledWith(expect.objectContaining({ id: "send-to-chat" }));
    fireEvent.click(screen.getByRole("button", { name: "Select all visible" }));
    expect(onSelectAll).toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Clear" }));
    expect(onClear).toHaveBeenCalled();
  });

  it("uses singular wording for one item", () => {
    render(
      <SelectionActionBar
        count={1}
        actions={selectionActionsForViewMode("skills")}
        onAction={jest.fn()}
        onSelectAllVisible={jest.fn()}
        onClear={jest.fn()}
      />,
    );
    expect(screen.getByText("1 selected")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Summarize" })).not.toBeInTheDocument();
  });
});
