/**
 * @jest-environment jsdom
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";

import { BrowseFolderContextMenu } from "@/app/(views)/browse/BrowseFolderContextMenu";

describe("BrowseFolderContextMenu", () => {
  it("renders a compact selected-folder button and menu options", async () => {
    const onSelect = jest.fn();
    const onAddFolder = jest.fn();
    render(
      <BrowseFolderContextMenu
        context={{ scope: "all", label: "All Brains" }}
        options={[
          { id: "all", scope: "all", label: "All Brains", state: "ready" },
          { id: "brain:personal", scope: "brain", brain_id: "personal", label: "Personal", state: "ready", count: 639 },
          { id: "brain:project-augur", scope: "brain", brain_id: "project-augur", label: "Augur project", state: "repairable", badge: "Repair" },
          { id: "add-folder", scope: "action", label: "+ Add folder", state: "ready" },
        ]}
        loading={false}
        onSelect={onSelect}
        onAddFolder={onAddFolder}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: /browse context: all brains/i }));

    expect(screen.getByRole("menuitemradio", { name: /personal/i })).toBeInTheDocument();
    expect(screen.getByText("Repair")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("menuitemradio", { name: /personal/i }));
    expect(onSelect).toHaveBeenCalledWith({ scope: "brain", brain_id: "personal", label: "Personal" });
  });

  it("calls Add folder without changing the active context", async () => {
    const onSelect = jest.fn();
    const onAddFolder = jest.fn();
    render(
      <BrowseFolderContextMenu
        context={{ scope: "all", label: "All Brains" }}
        options={[
          { id: "all", scope: "all", label: "All Brains", state: "ready" },
          { id: "add-folder", scope: "action", label: "+ Add folder", state: "ready" },
        ]}
        loading={false}
        onSelect={onSelect}
        onAddFolder={onAddFolder}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: /browse context: all brains/i }));
    await userEvent.click(screen.getByRole("menuitem", { name: /\+ add folder/i }));

    expect(onAddFolder).toHaveBeenCalled();
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("selects the All Brains context", async () => {
    const onSelect = jest.fn();
    render(
      <BrowseFolderContextMenu
        context={{ scope: "brain", brain_id: "personal", label: "Personal" }}
        options={[
          { id: "all", scope: "all", label: "All Brains", state: "ready" },
          { id: "brain:personal", scope: "brain", brain_id: "personal", label: "Personal", state: "ready" },
        ]}
        loading={false}
        onSelect={onSelect}
        onAddFolder={jest.fn()}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: /browse context: personal/i }));
    await userEvent.click(screen.getByRole("menuitemradio", { name: /all brains/i }));

    expect(onSelect).toHaveBeenCalledWith({ scope: "all", label: "All Brains" });
  });

  it("selects and marks the Unassigned repair context", async () => {
    const onSelect = jest.fn();
    render(
      <BrowseFolderContextMenu
        context={{ scope: "unassigned", label: "Unassigned" }}
        options={[
          { id: "all", scope: "all", label: "All Brains", state: "ready" },
          { id: "unassigned", scope: "unassigned", label: "Unassigned", state: "available", badge: "Repair" },
        ]}
        loading={false}
        onSelect={onSelect}
        onAddFolder={jest.fn()}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: /browse context: unassigned/i }));
    const unassigned = screen.getByRole("menuitemradio", { name: /unassigned/i });

    expect(unassigned).toHaveAttribute("aria-checked", "true");
    await userEvent.click(unassigned);
    expect(onSelect).toHaveBeenCalledWith({ scope: "unassigned", label: "Unassigned" });
  });

  it("shows detected, unregistered, and missing options without allowing selection", async () => {
    const onSelect = jest.fn();
    render(
      <BrowseFolderContextMenu
        context={{ scope: "all", label: "All Brains" }}
        options={[
          { id: "all", scope: "all", label: "All Brains", state: "ready" },
          { id: "brain:detected", scope: "brain", brain_id: "detected", label: "Detected project", state: "detected", disabled: true, badge: "Detected" },
          { id: "brain:unregistered", scope: "brain", brain_id: "unregistered", label: "Unregistered project", state: "unregistered", disabled: true, badge: "Add" },
          { id: "brain:missing", scope: "brain", brain_id: "missing", label: "Missing project", state: "missing", disabled: true, badge: "Missing" },
        ]}
        loading={false}
        onSelect={onSelect}
        onAddFolder={jest.fn()}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: /browse context: all brains/i }));

    expect(screen.getByRole("menu", { name: /browse context/i })).toBeInTheDocument();
    expect(screen.getByRole("menuitemradio", { name: /detected project/i })).toBeDisabled();
    expect(screen.getByRole("menuitemradio", { name: /unregistered project/i })).toBeDisabled();
    expect(screen.getByRole("menuitemradio", { name: /missing project/i })).toBeDisabled();
    expect(onSelect).not.toHaveBeenCalled();
  });
});
