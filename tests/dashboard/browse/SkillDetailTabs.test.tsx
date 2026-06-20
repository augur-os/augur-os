/**
 * @jest-environment jsdom
 */
import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";

jest.mock("@/components/browse/PromptCard", () => ({
  __esModule: true,
  PromptCard: jest.fn(
    ({ prompt }: { prompt: { id: string; label: string } }) => (
      <div data-testid="prompt-card">{prompt.label}</div>
    ),
  ),
}));

jest.mock("@/components/browse/CommandCard", () => ({
  __esModule: true,
  CommandCard: jest.fn(
    ({ command }: { command: { id: string; label: string } }) => (
      <div data-testid="command-card">{command.label}</div>
    ),
  ),
}));

jest.mock("@/components/browse/IntegrationTab", () => ({
  __esModule: true,
  IntegrationTab: ({
    skillId,
    skillLabel,
  }: {
    skillId: string;
    skillLabel?: string;
  }) => (
    <div data-testid="integration-tab">
      {skillId}
      {skillLabel ? `:${skillLabel}` : ""}
    </div>
  ),
}));

const { SkillDetailTabs } = require("@/components/browse/SkillDetailTabs") as typeof import("@/components/browse/SkillDetailTabs");
const { PromptCard } = require("@/components/browse/PromptCard") as {
  PromptCard: jest.Mock;
};
const { CommandCard } = require("@/components/browse/CommandCard") as {
  CommandCard: jest.Mock;
};

function renderTabs(
  props: React.ComponentProps<typeof SkillDetailTabs>,
) {
  render(<SkillDetailTabs {...props} />);
}

describe("SkillDetailTabs", () => {
  const overviewContent = <div>Overview content</div>;

  beforeEach(() => {
    PromptCard.mockClear();
    CommandCard.mockClear();
  });

  it("defaults to Prompts when prompts exist", () => {
    renderTabs({
      skillId: "test-skill",
      skillLabel: "Test Skill",
      prompts: [{ id: "prompt-1", label: "Prompt One", prompt: "hello" }],
      commands: [],
      overviewContent,
    });

    expect(screen.getByRole("tab", { name: "Prompts 1" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByTestId("prompt-card")).toHaveTextContent("Prompt One");
    expect(PromptCard.mock.calls[0]?.[0]).toEqual(
      expect.objectContaining({ onResult: expect.any(Function) }),
    );
  });

  it("defaults to Commands when prompts are empty and commands exist", () => {
    renderTabs({
      skillId: "test-skill",
      skillLabel: "Test Skill",
      prompts: [],
      commands: [{ id: "command-1", label: "Command One", command: "/run" }],
      overviewContent,
    });

    expect(screen.getByRole("tab", { name: "Commands 1" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByTestId("command-card")).toHaveTextContent("Command One");
    expect(CommandCard.mock.calls[0]?.[0]).toEqual(
      expect.objectContaining({ onResult: expect.any(Function) }),
    );
  });

  it("defaults to Overview when prompts and commands are empty", () => {
    renderTabs({
      skillId: "test-skill",
      skillLabel: "Test Skill",
      prompts: [],
      commands: [],
      overviewContent,
    });

    expect(screen.getByRole("tab", { name: "Overview" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.queryByRole("tab", { name: /Prompts/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: /Commands/i })).not.toBeInTheDocument();
    expect(screen.getByText("Overview content")).toBeInTheDocument();
  });

  it("switches between Overview and Integration tabs", () => {
    renderTabs({
      skillId: "test-skill",
      skillLabel: "Test Skill",
      prompts: [{ id: "prompt-1", label: "Prompt One", prompt: "hello" }],
      commands: [{ id: "command-1", label: "Command One", command: "/run" }],
      overviewContent,
    });

    fireEvent.click(screen.getByRole("tab", { name: "Overview" }));
    expect(screen.getByText("Overview content")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Integration" }));
    expect(screen.getByTestId("integration-tab")).toHaveTextContent(
      "test-skill:Test Skill",
    );
  });

  it("renders generated capability profile sections in the Overview tab", () => {
    renderTabs({
      skillId: "gmail-triage",
      skillLabel: "Gmail Triage",
      prompts: [{ id: "prompt-1", label: "Prompt One", prompt: "hello" }],
      commands: [],
      overviewContent,
      capabilityProfileSections: [
        {
          id: "integrations",
          title: "Integrations",
          kind: "integrations",
          items: [{ label: "Gmail", description: "connected" }],
        },
      ],
    });

    expect(screen.getByRole("tab", { name: "Prompts 1" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.queryByText("Integrations")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Overview" }));

    expect(screen.getByText("Overview content")).toBeInTheDocument();
    expect(screen.getByText("Integrations")).toBeInTheDocument();
    expect(screen.getByText("Gmail")).toBeInTheDocument();
    expect(screen.getByText("connected")).toBeInTheDocument();
  });

  it("renders prompt and command tabs only when their arrays are populated", () => {
    renderTabs({
      skillId: "test-skill",
      skillLabel: "Test Skill",
      prompts: [{ id: "prompt-1", label: "Prompt One", prompt: "hello" }],
      commands: [],
      overviewContent,
    });

    expect(screen.getByRole("tab", { name: "Prompts 1" })).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: /Commands/i })).not.toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Integration" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Overview" })).toBeInTheDocument();
  });

  it("reapplies the default tab when the skill changes", () => {
    const { rerender } = render(
      <SkillDetailTabs
        skillId="skill-a"
        skillLabel="Skill A"
        prompts={[]}
        commands={[]}
        overviewContent={<div>Overview A</div>}
      />,
    );

    fireEvent.click(screen.getByRole("tab", { name: "Integration" }));
    expect(screen.getByRole("tab", { name: "Integration" })).toHaveAttribute(
      "aria-selected",
      "true",
    );

    rerender(
      <SkillDetailTabs
        skillId="skill-b"
        skillLabel="Skill B"
        prompts={[{ id: "prompt-b", label: "Prompt B", prompt: "hello" }]}
        commands={[]}
        overviewContent={<div>Overview B</div>}
      />,
    );

    expect(screen.getByRole("tab", { name: "Prompts 1" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByTestId("prompt-card")).toHaveTextContent("Prompt B");
  });

  it("supports arrow key and Home/End tab navigation", () => {
    renderTabs({
      skillId: "test-skill",
      skillLabel: "Test Skill",
      prompts: [{ id: "prompt-1", label: "Prompt One", prompt: "hello" }],
      commands: [{ id: "command-1", label: "Command One", command: "/run" }],
      overviewContent,
    });

    const promptsTab = screen.getByRole("tab", { name: "Prompts 1" });
    expect(promptsTab).toHaveAttribute("tabindex", "0");

    fireEvent.keyDown(promptsTab, { key: "ArrowRight" });
    expect(screen.getByRole("tab", { name: "Commands 1" })).toHaveAttribute(
      "aria-selected",
      "true",
    );

    fireEvent.keyDown(screen.getByRole("tab", { name: "Commands 1" }), {
      key: "Home",
    });
    expect(screen.getByRole("tab", { name: "Overview" })).toHaveAttribute(
      "aria-selected",
      "true",
    );

    fireEvent.keyDown(screen.getByRole("tab", { name: "Overview" }), {
      key: "End",
    });
    expect(screen.getByRole("tab", { name: "Integration" })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it("keeps stable tabpanel elements for every available tab", () => {
    const { container } = render(
      <SkillDetailTabs
        skillId="test-skill"
        skillLabel="Test Skill"
        prompts={[{ id: "prompt-1", label: "Prompt One", prompt: "hello" }]}
        commands={[{ id: "command-1", label: "Command One", command: "/run" }]}
        overviewContent={overviewContent}
      />,
    );

    expect(container.querySelector("#skill-detail-tabpanel-overview")).not.toBeNull();
    expect(container.querySelector("#skill-detail-tabpanel-prompts")).not.toBeNull();
    expect(container.querySelector("#skill-detail-tabpanel-commands")).not.toBeNull();
    expect(container.querySelector("#skill-detail-tabpanel-integration")).not.toBeNull();
  });
});
