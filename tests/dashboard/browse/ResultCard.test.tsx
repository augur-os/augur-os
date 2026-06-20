/**
 * @jest-environment jsdom
 */
import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";

jest.mock("@/components/Markdown", () => ({
  __esModule: true,
  default: ({ markdown, basePath }: { markdown: string; basePath?: string }) => (
    <div data-testid="markdown" data-base-path={basePath}>
      {markdown}
    </div>
  ),
}));

const mockWriteText = jest.fn(() => Promise.resolve());

Object.defineProperty(navigator, "clipboard", {
  value: {
    writeText: mockWriteText,
  },
  configurable: true,
});

describe("ResultCard", () => {
  beforeEach(() => {
    mockWriteText.mockClear();
  });

  it("renders markdown answer text and heading", async () => {
    const { ResultCard } = await import("@/components/browse/ResultCard");

    render(
      <ResultCard
        result={{
          promptId: "brainstorm-ideas",
          input: "brainstorm ideas",
          answer: "## Heading\n\nResult body",
          sessionId: "session-123",
          cliId: "codex",
          durationMs: 1250,
          timestamp: new Date("2026-04-21T00:00:00.000Z"),
        }}
        onContinueInSession={jest.fn()}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "brainstorm-ideas" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("markdown")).toHaveTextContent("Heading");
    expect(screen.getByTestId("markdown")).toHaveTextContent("Result body");
  });

  it("shows duration in seconds", async () => {
    const { ResultCard } = await import("@/components/browse/ResultCard");

    render(
      <ResultCard
        result={{
          promptId: "brainstorm-ideas",
          input: "brainstorm ideas",
          answer: "Result body",
          sessionId: "session-123",
          cliId: "codex",
          durationMs: 1250,
          timestamp: new Date("2026-04-21T00:00:00.000Z"),
        }}
        onContinueInSession={jest.fn()}
      />,
    );

    expect(screen.getByText("1.25s")).toBeInTheDocument();
  });

  it("shows sub-second duration in milliseconds", async () => {
    const { ResultCard } = await import("@/components/browse/ResultCard");

    render(
      <ResultCard
        result={{
          promptId: "brainstorm-ideas",
          input: "brainstorm ideas",
          answer: "Result body",
          sessionId: "session-123",
          cliId: "codex",
          durationMs: 999,
          timestamp: new Date("2026-04-21T00:00:00.000Z"),
        }}
        onContinueInSession={jest.fn()}
      />,
    );

    expect(screen.getByText("999ms")).toBeInTheDocument();
  });

  it("passes a markdown basePath for relative links", async () => {
    const { ResultCard } = await import("@/components/browse/ResultCard");

    render(
      <ResultCard
        result={{
          promptId: "brainstorm-ideas",
          input: "brainstorm ideas",
          answer: "[doc](relative.md)",
          sessionId: "session-123",
          cliId: "codex",
          durationMs: 1250,
          timestamp: new Date("2026-04-21T00:00:00.000Z"),
        }}
        onContinueInSession={jest.fn()}
        basePath="/project-brain/capabilities/skills/workspace/prompts/example.md"
      />,
    );

    expect(screen.getByTestId("markdown")).toHaveAttribute(
      "data-base-path",
      "/project-brain/capabilities/skills/workspace/prompts/example.md",
    );
  });

  it("clicking Continue in session calls handler with sessionId", async () => {
    const onContinueInSession = jest.fn();
    const { ResultCard } = await import("@/components/browse/ResultCard");

    render(
      <ResultCard
        result={{
          promptId: "brainstorm-ideas",
          input: "brainstorm ideas",
          answer: "Result body",
          sessionId: "session-123",
          cliId: "codex",
          durationMs: 1250,
          timestamp: new Date("2026-04-21T00:00:00.000Z"),
        }}
        onContinueInSession={onContinueInSession}
      />,
    );

    fireEvent.click(
      screen.getByRole("button", { name: /continue in session/i }),
    );

    expect(onContinueInSession).toHaveBeenCalledWith("session-123");
  });

  it("copy button calls navigator.clipboard.writeText with answer", async () => {
    const { ResultCard } = await import("@/components/browse/ResultCard");

    render(
      <ResultCard
        result={{
          promptId: "brainstorm-ideas",
          input: "brainstorm ideas",
          answer: "Result body",
          sessionId: "session-123",
          cliId: "codex",
          durationMs: 1250,
          timestamp: new Date("2026-04-21T00:00:00.000Z"),
        }}
        onContinueInSession={jest.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /copy result/i }));

    expect(mockWriteText).toHaveBeenCalledWith("Result body");
  });

  it("does not render Continue in session when sessionId is empty", async () => {
    const { ResultCard } = await import("@/components/browse/ResultCard");

    render(
      <ResultCard
        result={{
          promptId: "brainstorm-ideas",
          input: "brainstorm ideas",
          answer: "Result body",
          sessionId: "",
          cliId: "codex",
          durationMs: 1250,
          timestamp: new Date("2026-04-21T00:00:00.000Z"),
        }}
        onContinueInSession={jest.fn()}
      />,
    );

    expect(
      screen.queryByRole("button", { name: /continue in session/i }),
    ).not.toBeInTheDocument();
  });
});
