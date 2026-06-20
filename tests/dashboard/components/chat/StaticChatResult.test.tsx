import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { StaticChatResult } from "@/features/components/chat/ChatLayout";
import type { OneshotResult } from "@/lib/stores/chatStore";

describe("StaticChatResult", () => {
  it("offers an explicit live workflow run button for demo previews", () => {
    const result: OneshotResult = {
      actionId: "demo_01",
      actionLabel: "Workflow Example 01",
      resultText: "Workflow Example 01 is running.\nExample status: pass.",
      prompt: "Run Workflow Example 01 for real",
      timestamp: new Date("2026-06-01T15:00:00Z"),
    };
    const onRunLive = jest.fn();

    render(<StaticChatResult result={result} onRunLive={onRunLive} />);

    expect(screen.getByText("Preview output")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Run live workflow" }));

    expect(onRunLive).toHaveBeenCalledWith(result);
  });
});
