/** @jest-environment jsdom */
import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import { BrowsePromptTrigger } from "@/components/shared/BrowsePromptTrigger";

describe("BrowsePromptTrigger", () => {
  it("dispatches immediately when the prompt has no placeholders", () => {
    const onTrigger = jest.fn();
    render(<BrowsePromptTrigger promptBody="plain prompt" placeholders={[]} onTrigger={onTrigger} />);
    fireEvent.click(screen.getByRole("button", { name: /trigger/i }));
    expect(onTrigger).toHaveBeenCalledWith("plain prompt");
  });

  it("shows a form for placeholders and dispatches the resolved prompt", () => {
    const onTrigger = jest.fn();
    render(
      <BrowsePromptTrigger
        promptBody="State your {{goal}}."
        placeholders={["goal"]}
        onTrigger={onTrigger}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /trigger/i }));
    fireEvent.change(screen.getByLabelText("goal"), { target: { value: "ship ADR-748" } });
    fireEvent.click(screen.getByRole("button", { name: /send|run|dispatch/i }));
    expect(onTrigger).toHaveBeenCalledWith("State your ship ADR-748.");
  });

  it("merges multiple slot values into the resolved prompt", () => {
    const onTrigger = jest.fn();
    render(
      <BrowsePromptTrigger
        promptBody="Goal: {{goal}} | Context: {{ctx}}"
        placeholders={["goal", "ctx"]}
        onTrigger={onTrigger}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /trigger/i }));
    fireEvent.change(screen.getByLabelText("goal"), { target: { value: "ship it" } });
    fireEvent.change(screen.getByLabelText("ctx"), { target: { value: "ADR-748" } });
    fireEvent.click(screen.getByRole("button", { name: /send|run|dispatch/i }));
    expect(onTrigger).toHaveBeenCalledWith("Goal: ship it | Context: ADR-748");
  });

  it("toggles the form closed when Trigger is clicked again", () => {
    const onTrigger = jest.fn();
    render(
      <BrowsePromptTrigger
        promptBody="State your {{goal}}."
        placeholders={["goal"]}
        onTrigger={onTrigger}
      />,
    );
    const triggerButton = screen.getByRole("button", { name: /trigger/i });
    fireEvent.click(triggerButton);
    expect(screen.getByLabelText("goal")).toBeInTheDocument();
    fireEvent.click(triggerButton);
    expect(screen.queryByLabelText("goal")).toBeNull();
    expect(onTrigger).not.toHaveBeenCalled();
  });

  it("collapses the form and fires onTrigger exactly once after submit", () => {
    const onTrigger = jest.fn();
    render(
      <BrowsePromptTrigger
        promptBody="State your {{goal}}."
        placeholders={["goal"]}
        onTrigger={onTrigger}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /trigger/i }));
    fireEvent.change(screen.getByLabelText("goal"), { target: { value: "ship ADR-748" } });
    fireEvent.click(screen.getByRole("button", { name: /send|run|dispatch/i }));
    expect(onTrigger).toHaveBeenCalledTimes(1);
    expect(screen.queryByLabelText("goal")).toBeNull();
  });
});
