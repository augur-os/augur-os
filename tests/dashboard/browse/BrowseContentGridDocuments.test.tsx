/**
 * @jest-environment jsdom
 */
import { fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { BrowseContentGrid } from "@/app/(views)/browse/BrowseContentGrid";
import { BrowseCategoryActions } from "@/components/shared/BrowseCategoryActions";
import type { BrowseCategory } from "@/lib/browse/types";

jest.mock("@/lib/mcp/client", () => ({
  mcpCall: jest.fn().mockResolvedValue({}),
}));

jest.mock("@/lib/browse/cliExecClient", () => ({
  runCliExecPrompt: jest.fn().mockResolvedValue({ answer: "ok" }),
}));

jest.mock("@/features/browse/AddSkillModal", () => ({
  AddSkillModal: ({ open }: { open: boolean }) => (open ? <div>Add Skill Modal</div> : null),
}));

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push: jest.fn() }),
}));

jest.mock("sonner", () => ({
  toast: { loading: jest.fn(() => "toast-1"), success: jest.fn(), error: jest.fn() },
}));

const documentsCategory: BrowseCategory = {
  id: "documents",
  label: "Documents",
  singularLabel: "Document",
  icon: "FolderOpen",
  devOnly: false,
  group: "content",
};

function renderEmptyDocuments({
  onAttachDocumentSource = jest.fn(),
  brainId = "project-y",
  label = "Project Y",
}: {
  onAttachDocumentSource?: () => void;
  brainId?: string;
  label?: string;
} = {}) {
  render(
    <BrowseContentGrid
      effectiveViewMode="documents"
      activeCategory={documentsCategory}
      displayMode="card"
      sorted={[]}
      pinnedItems={[]}
      semanticResultsActive={false}
      semanticResults={[]}
      semanticLoading={false}
      loading={false}
      error={null}
      refetch={jest.fn()}
      notIndexed={false}
      visibleCount={20}
      onLoadMore={jest.fn()}
      pageSize={20}
      selectedSkill={null}
      selectedSchedule={null}
      search=""
      onRunMcp={jest.fn()}
      onChatResult={jest.fn()}
      onSelectSkill={jest.fn()}
      onSelectItem={jest.fn()}
      onSelectCapability={jest.fn()}
      onSelectScheduledExecution={jest.fn()}
      isPinned={() => false}
      onTogglePin={jest.fn()}
      onTriggerPrompt={jest.fn()}
      onAttachDocumentSource={onAttachDocumentSource}
      activeFolderContext={{ scope: "brain", brain_id: brainId, label }}
    />,
  );
}

describe("BrowseContentGrid document empty state", () => {
  it("shows an attach source action for empty project documents", () => {
    const onAttachDocumentSource = jest.fn();
    renderEmptyDocuments({ onAttachDocumentSource });

    expect(
      screen.getByText(
        "No shared document source is attached to Project Y yet. Attach a shared folder such as Google Drive or SharePoint for this project.",
      ),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Attach shared source" }));
    expect(onAttachDocumentSource).toHaveBeenCalledTimes(1);
  });

  it("does not show the attach source action for personal documents", () => {
    renderEmptyDocuments({ brainId: "personal", label: "Personal" });

    expect(screen.queryByRole("button", { name: "Attach shared source" })).not.toBeInTheDocument();
  });
});

describe("BrowseCategoryActions document source attachment", () => {
  it("adds an attach source item to the Documents Manage menu when provided", () => {
    const onAttachDocumentSource = jest.fn();

    render(
      <BrowseCategoryActions
        category="documents"
        activeCategory={documentsCategory}
        itemCount={0}
        onRefetch={jest.fn()}
        onAttachDocumentSource={onAttachDocumentSource}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Manage" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Attach shared source" }));

    expect(onAttachDocumentSource).toHaveBeenCalledTimes(1);
  });

  it("does not add the Documents attach source item without a project callback", () => {
    render(
      <BrowseCategoryActions
        category="documents"
        activeCategory={documentsCategory}
        itemCount={0}
        onRefetch={jest.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Manage" }));

    expect(screen.queryByRole("menuitem", { name: "Attach shared source" })).not.toBeInTheDocument();
  });
});
