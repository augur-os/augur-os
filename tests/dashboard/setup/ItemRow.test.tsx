import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";

import { ItemRow } from "@/features/setup/SetupWidget/ItemRow";
import type { ItemStatus } from "@/features/setup/types";

function makeItem(overrides: Partial<ItemStatus> = {}): ItemStatus {
  return {
    id: "wiki-pages-5",
    label: "Compile 5 wiki pages",
    description: "Have at least 5 compiled wiki pages",
    status: "pending",
    action: {
      type: "command",
      label: "Run wiki update",
      command: "/wiki-update",
    },
    last_checked: "2026-05-13T12:00:00Z",
    ...overrides,
  };
}

describe("ItemRow", () => {
  it("renders the item label and description", () => {
    render(<ItemRow item={makeItem()} onAction={() => {}} onSkip={() => {}} />);

    expect(screen.getByText("Compile 5 wiki pages")).toBeInTheDocument();
    expect(screen.getByText("Have at least 5 compiled wiki pages")).toBeInTheDocument();
  });

  it("prefers details over description when present", () => {
    render(
      <ItemRow
        item={makeItem({ details: "2/5 wiki pages" })}
        onAction={() => {}}
        onSkip={() => {}}
      />,
    );

    expect(screen.getByText("2/5 wiki pages")).toBeInTheDocument();
    expect(screen.queryByText("Have at least 5 compiled wiki pages")).not.toBeInTheDocument();
  });

  it("shows the action button for pending items and calls onAction on click", () => {
    const onAction = jest.fn();
    render(<ItemRow item={makeItem()} onAction={onAction} onSkip={() => {}} />);

    fireEvent.click(screen.getByText("Run wiki update"));

    expect(onAction).toHaveBeenCalledTimes(1);
    expect(onAction.mock.calls[0][0].id).toBe("wiki-pages-5");
  });

  it("shows the action button for regressed items", () => {
    render(
      <ItemRow
        item={makeItem({ status: "regressed" })}
        onAction={() => {}}
        onSkip={() => {}}
      />,
    );

    expect(screen.getByText("Run wiki update")).toBeInTheDocument();
  });

  it("hides the action button for done items", () => {
    render(
      <ItemRow item={makeItem({ status: "done" })} onAction={() => {}} onSkip={() => {}} />,
    );

    expect(screen.queryByText("Run wiki update")).not.toBeInTheDocument();
  });

  it("renders Skip toggle for actionable items and calls onSkip with true", () => {
    const onSkip = jest.fn();
    render(<ItemRow item={makeItem()} onAction={() => {}} onSkip={onSkip} />);

    fireEvent.click(screen.getByLabelText("Skip Compile 5 wiki pages"));

    expect(onSkip).toHaveBeenCalledWith(
      expect.objectContaining({ id: "wiki-pages-5" }),
      true,
    );
  });

  it("renders Unskip toggle for already-skipped items and calls onSkip with false", () => {
    const onSkip = jest.fn();
    render(
      <ItemRow item={makeItem({ status: "skipped" })} onAction={() => {}} onSkip={onSkip} />,
    );

    fireEvent.click(screen.getByLabelText("Unskip Compile 5 wiki pages"));

    expect(onSkip).toHaveBeenCalledWith(
      expect.objectContaining({ id: "wiki-pages-5" }),
      false,
    );
  });

  it("does not render Skip toggle for done items", () => {
    render(
      <ItemRow item={makeItem({ status: "done" })} onAction={() => {}} onSkip={() => {}} />,
    );

    expect(screen.queryByLabelText(/^Skip /)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/^Unskip /)).not.toBeInTheDocument();
  });
});
