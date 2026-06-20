/**
 * @jest-environment jsdom
 */
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";

import { BrowseAddFolderDialog } from "@/app/(views)/browse/BrowseAddFolderDialog";

describe("BrowseAddFolderDialog", () => {
  it("scans before showing initialize and does not initialize during scan", async () => {
    const user = userEvent.setup();
    const onScan = jest.fn().mockResolvedValue({
      success: true,
      project_root: "/Users/me/Projects/Demo",
      inventory_count: 3,
      inventory_warning_count: 1,
      writes_metadata: false,
    });
    const onInitialize = jest.fn();

    render(
      <BrowseAddFolderDialog
        open
        onOpenChange={jest.fn()}
        onScan={onScan}
        onInitialize={onInitialize}
      />,
    );

    await user.type(screen.getByRole("textbox", { name: /folder path/i }), "  /Users/me/Projects/Demo  ");
    await user.click(screen.getByRole("button", { name: /scan folder/i }));

    expect(onScan).toHaveBeenCalledWith("/Users/me/Projects/Demo");
    expect(onInitialize).not.toHaveBeenCalled();

    expect(await screen.findByText(/3 artifacts/i)).toBeInTheDocument();
    expect(screen.getByText(/1 warning/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /initialize folder/i })).toBeInTheDocument();
    expect(onInitialize).not.toHaveBeenCalled();
  });

  it("calls initialize only after explicit approval", async () => {
    const user = userEvent.setup();
    const onOpenChange = jest.fn();
    const onScan = jest.fn().mockResolvedValue({
      success: true,
      project_root: "/Users/me/Projects/Demo",
      inventory_count: 3,
      inventory_warning_count: 0,
      warnings: [],
      writes_metadata: true,
    });
    const onInitialize = jest.fn().mockResolvedValue({ success: true });

    render(
      <BrowseAddFolderDialog
        open
        onOpenChange={onOpenChange}
        onScan={onScan}
        onInitialize={onInitialize}
      />,
    );

    await user.type(screen.getByRole("textbox", { name: /folder path/i }), "/Users/me/Projects/Demo");
    await user.click(screen.getByRole("button", { name: /scan folder/i }));
    await screen.findByText(/3 artifacts/i);

    expect(onInitialize).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: /initialize folder/i }));

    await waitFor(() => expect(onInitialize).toHaveBeenCalledWith("/Users/me/Projects/Demo"));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("keeps the dialog open and shows an error when initialize reports failure", async () => {
    const user = userEvent.setup();
    const onOpenChange = jest.fn();
    const onScan = jest.fn().mockResolvedValue({
      success: true,
      project_root: "/Users/me/Projects/Demo",
      inventory_count: 1,
      inventory_warning_count: 0,
      writes_metadata: false,
    });
    const onInitialize = jest.fn().mockResolvedValue({ success: false, error: "Cannot initialize folder" });

    render(
      <BrowseAddFolderDialog
        open
        onOpenChange={onOpenChange}
        onScan={onScan}
        onInitialize={onInitialize}
      />,
    );

    await user.type(screen.getByRole("textbox", { name: /folder path/i }), "/Users/me/Projects/Demo");
    await user.click(screen.getByRole("button", { name: /scan folder/i }));
    await screen.findByText(/1 artifact/i);
    await user.click(screen.getByRole("button", { name: /initialize folder/i }));

    expect(await screen.findByText("Cannot initialize folder")).toBeInTheDocument();
    expect(onOpenChange).not.toHaveBeenCalledWith(false);
  });

  it("resets stale scan state after close and reopen", async () => {
    const user = userEvent.setup();
    const onScan = jest.fn().mockResolvedValue({
      success: true,
      project_root: "/Users/me/Projects/Demo",
      inventory_count: 2,
      inventory_warning_count: 0,
      writes_metadata: false,
    });
    const onInitialize = jest.fn();
    const props = {
      open: true,
      onOpenChange: jest.fn(),
      onScan,
      onInitialize,
    };

    const { rerender } = render(<BrowseAddFolderDialog {...props} />);

    await user.type(screen.getByRole("textbox", { name: /folder path/i }), "/Users/me/Projects/Demo");
    await user.click(screen.getByRole("button", { name: /scan folder/i }));
    expect(await screen.findByText(/2 artifacts/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /initialize folder/i })).toBeInTheDocument();

    rerender(<BrowseAddFolderDialog {...props} open={false} />);
    rerender(<BrowseAddFolderDialog {...props} open />);

    expect(screen.getByRole("textbox", { name: /folder path/i })).toHaveValue("");
    expect(screen.queryByRole("button", { name: /initialize folder/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/2 artifacts/i)).not.toBeInTheDocument();
  });

  it("ignores a pending scan result after the dialog closes", async () => {
    const user = userEvent.setup();
    let resolveScan!: (value: unknown) => void;
    const scanPromise = new Promise((resolve) => {
      resolveScan = resolve;
    });
    const onScan = jest.fn(() => scanPromise);
    const props = {
      open: true,
      onOpenChange: jest.fn(),
      onScan,
      onInitialize: jest.fn(),
    };

    const { rerender } = render(<BrowseAddFolderDialog {...props} />);

    await user.type(screen.getByRole("textbox", { name: /folder path/i }), "/Users/me/Projects/Demo");
    await user.click(screen.getByRole("button", { name: /scan folder/i }));
    rerender(<BrowseAddFolderDialog {...props} open={false} />);
    await act(async () => {
      resolveScan({
        success: true,
        project_root: "/Users/me/Projects/Demo",
        inventory_count: 5,
        inventory_warning_count: 0,
        writes_metadata: false,
      });
      await scanPromise;
    });
    rerender(<BrowseAddFolderDialog {...props} open />);

    expect(screen.getByRole("textbox", { name: /folder path/i })).toHaveValue("");
    expect(screen.queryByText(/5 artifacts/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /initialize folder/i })).not.toBeInTheDocument();
  });

  it("ignores a pending scan result after the path changes", async () => {
    const user = userEvent.setup();
    let resolveScan!: (value: unknown) => void;
    let scanCount = 0;
    const scanPromise = new Promise((resolve) => {
      resolveScan = resolve;
    });
    const onScan = jest.fn(() => {
      scanCount += 1;
      if (scanCount === 1) return scanPromise;
      return Promise.resolve({
        success: true,
        project_root: "/Users/me/Projects/New",
        inventory_count: 2,
        inventory_warning_count: 0,
        writes_metadata: false,
      });
    });

    render(
      <BrowseAddFolderDialog
        open
        onOpenChange={jest.fn()}
        onScan={onScan}
        onInitialize={jest.fn()}
      />,
    );

    const input = screen.getByRole("textbox", { name: /folder path/i });
    await user.type(input, "/Users/me/Projects/Old");
    await user.click(screen.getByRole("button", { name: /scan folder/i }));
    await user.clear(input);
    await user.type(input, "/Users/me/Projects/New");
    await act(async () => {
      resolveScan({
        success: true,
        project_root: "/Users/me/Projects/Old",
        inventory_count: 4,
        inventory_warning_count: 0,
        writes_metadata: false,
      });
      await scanPromise;
    });

    expect(input).toHaveValue("/Users/me/Projects/New");
    expect(screen.queryByText(/4 artifacts/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /initialize folder/i })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /scan folder/i }));
    expect(onScan).toHaveBeenLastCalledWith("/Users/me/Projects/New");
    expect(await screen.findByText(/2 artifacts/i)).toBeInTheDocument();
  });

  it("keeps the path input locked while initialize is pending", async () => {
    const user = userEvent.setup();
    let resolveInitialize!: (value: unknown) => void;
    const initializePromise = new Promise((resolve) => {
      resolveInitialize = resolve;
    });
    const onInitialize = jest.fn(() => initializePromise);

    render(
      <BrowseAddFolderDialog
        open
        onOpenChange={jest.fn()}
        onScan={jest.fn().mockResolvedValue({
          success: true,
          project_root: "/Users/me/Projects/Demo",
          inventory_count: 1,
          inventory_warning_count: 0,
          writes_metadata: false,
        })}
        onInitialize={onInitialize}
      />,
    );

    const input = screen.getByRole("textbox", { name: /folder path/i });
    await user.type(input, "/Users/me/Projects/Demo");
    await user.click(screen.getByRole("button", { name: /scan folder/i }));
    await screen.findByText(/1 artifact/i);
    await user.click(screen.getByRole("button", { name: /initialize folder/i }));

    expect(input).toBeDisabled();
    await act(async () => {
      resolveInitialize({ success: true });
      await initializePromise;
    });
  });

  it("focuses the path input, closes on Escape, and keeps Tab focus inside the dialog", async () => {
    const user = userEvent.setup();
    const onOpenChange = jest.fn();

    render(
      <BrowseAddFolderDialog
        open
        onOpenChange={onOpenChange}
        onScan={jest.fn()}
        onInitialize={jest.fn()}
      />,
    );

    const input = screen.getByRole("textbox", { name: /folder path/i });
    await waitFor(() => expect(input).toHaveFocus());

    const cancel = screen.getByRole("button", { name: /cancel/i });
    const close = screen.getByRole("button", { name: /close/i });
    cancel.focus();
    fireEvent.keyDown(document, { key: "Tab" });
    expect(close).toHaveFocus();

    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(cancel).toHaveFocus();

    await user.keyboard("{Escape}");
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
