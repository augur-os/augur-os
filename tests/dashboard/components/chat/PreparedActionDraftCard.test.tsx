import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import type React from "react";
import { PreparedActionDraftCard } from "@/features/components/chat/PreparedActionDraftCard";
import type { PreparedActionDraft } from "@/lib/actions/preparedActionDraft";

const draft: PreparedActionDraft = {
  id: "browse.deep-search",
  label: "Ask AI",
  description: "Investigate Browse results",
  prompt: "Inspect selected source paths before answering.",
  page: "browse",
  tier: "deep",
  dispatch: "ide",
  recommendedAgent: "claude",
  createdAt: "2026-05-24T00:00:00.000Z",
};

function renderCard(
  overrides: Partial<React.ComponentProps<typeof PreparedActionDraftCard>> = {},
) {
  const props = {
    draft,
    selectedClientLabel: "Claude Code",
    userRemarks: "",
    onUserRemarksChange: jest.fn(),
    onSend: jest.fn(),
    onCancel: jest.fn(),
    canSend: true,
    isSending: false,
    error: null,
    ...overrides,
  };
  render(<PreparedActionDraftCard {...props} />);
  return props;
}

describe("PreparedActionDraftCard", () => {
  it("renders action metadata, current client, and prompt preview summary", () => {
    renderCard();

    expect(screen.getByText("Prepared action")).toBeInTheDocument();
    expect(screen.getByText("Ask AI")).toBeInTheDocument();
    expect(screen.getByText("Investigate Browse results")).toBeInTheDocument();
    expect(screen.getByText("Claude Code")).toBeInTheDocument();
    expect(screen.getByText("AI draft")).toBeInTheDocument();
    expect(screen.getByText("System prompt preview")).toBeInTheDocument();
  });

  it("emits user remarks changes", () => {
    const props = renderCard();

    fireEvent.change(
      screen.getByRole("textbox", { name: "Prepared action remarks" }),
      {
        target: { value: "Use the newest deck." },
      },
    );

    expect(props.onUserRemarksChange).toHaveBeenCalledWith("Use the newest deck.");
  });

  it("calls send and cancel handlers", () => {
    const props = renderCard();

    fireEvent.click(screen.getByRole("button", { name: "Send prepared action" }));
    fireEvent.click(
      screen.getByRole("button", { name: "Cancel prepared action" }),
    );

    expect(props.onSend).toHaveBeenCalledTimes(1);
    expect(props.onCancel).toHaveBeenCalledTimes(1);
  });

  it("disables send when there is no enabled client", () => {
    renderCard({ canSend: false, error: "Select an enabled chat client." });

    expect(
      screen.getByRole("button", { name: "Send prepared action" }),
    ).toBeDisabled();
    expect(screen.getByText("Select an enabled chat client.")).toBeInTheDocument();
  });
});
