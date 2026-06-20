/**
 * @jest-environment jsdom
 */
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import { BrowseCardShell } from "@/components/shared/BrowseCardShell";
import { BrowseListRowCard } from "@/components/shared/BrowseListRowCard";
import { buildBrowseCardModel } from "@/lib/browse/cardModel";
import type { BrowseItem } from "@/lib/browse/types";

jest.mock("next/navigation", () => ({ useRouter: () => ({ push: jest.fn() }) }));

function model() {
  const item: BrowseItem = {
    id: "a",
    title: "Note A",
    description: "desc",
    hub: "workspace",
    primaryAction: { label: "Open", type: "open-file", target: "notes/a.md" },
    path: "notes/a.md",
  };
  return buildBrowseCardModel(item, { viewMode: "notes" });
}

describe("BrowseCardShell selection mode", () => {
  it("shows a select overlay and toggles via it, not opening detail", () => {
    const onToggle = jest.fn();
    const onSelect = jest.fn();
    render(
      <BrowseCardShell
        model={model()}
        selectionMode
        isMultiSelected={false}
        onToggleMultiSelect={onToggle}
        onSelect={onSelect}
      />,
    );
    fireEvent.click(screen.getByTestId("browse-card-select-overlay"));
    expect(onToggle).toHaveBeenCalledTimes(1);
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("reflects checked state and has no overlay outside select mode", () => {
    const { rerender } = render(
      <BrowseCardShell model={model()} selectionMode isMultiSelected onToggleMultiSelect={jest.fn()} />,
    );
    expect(screen.getByTestId("browse-card-checkbox")).toBeChecked();
    rerender(<BrowseCardShell model={model()} onSelect={jest.fn()} />);
    expect(screen.queryByTestId("browse-card-select-overlay")).not.toBeInTheDocument();
  });
});

describe("BrowseListRowCard selection mode", () => {
  it("toggles via the overlay", () => {
    const onToggle = jest.fn();
    render(
      <BrowseListRowCard
        model={model()}
        selectionMode
        isMultiSelected={false}
        onToggleMultiSelect={onToggle}
        onSelect={jest.fn()}
      />,
    );
    fireEvent.click(screen.getByTestId("browse-list-row-select-overlay"));
    expect(onToggle).toHaveBeenCalledTimes(1);
  });
});
