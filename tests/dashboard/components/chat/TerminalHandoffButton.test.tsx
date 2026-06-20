/**
 * @jest-environment jsdom
 */

import "@testing-library/jest-dom";
import { fireEvent, render, screen } from "@testing-library/react";

import { TerminalHandoffButton } from "@/features/components/chat/ChatHeader";

describe("TerminalHandoffButton", () => {
  it("is disabled without a running supported CLI", () => {
    const onOpenTerminal = jest.fn();
    render(
      <TerminalHandoffButton
        isRunning={false}
        selectedCli="codex"
        isOpening={false}
        onOpenTerminal={onOpenTerminal}
      />,
    );

    const button = screen.getByRole("button", {
      name: /open in native terminal/i,
    });
    expect(button).toBeDisabled();
    fireEvent.click(button);
    expect(onOpenTerminal).not.toHaveBeenCalled();
  });

  it("is disabled for unsupported clients", () => {
    const onOpenTerminal = jest.fn();
    render(
      <TerminalHandoffButton
        isRunning={true}
        selectedCli="opencode"
        isOpening={false}
        onOpenTerminal={onOpenTerminal}
      />,
    );

    const button = screen.getByRole("button", {
      name: /open in native terminal/i,
    });
    expect(button).toBeDisabled();
    fireEvent.click(button);
    expect(onOpenTerminal).not.toHaveBeenCalled();
  });

  it("is disabled while opening", () => {
    const onOpenTerminal = jest.fn();
    render(
      <TerminalHandoffButton
        isRunning={true}
        selectedCli="codex"
        isOpening={true}
        onOpenTerminal={onOpenTerminal}
      />,
    );

    const button = screen.getByRole("button", {
      name: /open in native terminal/i,
    });
    expect(button).toBeDisabled();
    fireEvent.click(button);
    expect(onOpenTerminal).not.toHaveBeenCalled();
  });

  it("calls the parent handoff callback", () => {
    const onOpenTerminal = jest.fn();
    render(
      <TerminalHandoffButton
        isRunning={true}
        selectedCli="codex"
        isOpening={false}
        onOpenTerminal={onOpenTerminal}
      />,
    );

    fireEvent.click(
      screen.getByRole("button", { name: /open in native terminal/i }),
    );

    expect(onOpenTerminal).toHaveBeenCalledTimes(1);
  });
});
