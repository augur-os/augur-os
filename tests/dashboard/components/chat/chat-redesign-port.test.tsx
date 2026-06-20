import React from "react";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import {
  TerminalInputSection,
  TerminalBottomSection,
} from "@/features/components/chat/ChatInput";
import { FloatingChatWindow } from "@/features/components/chat/ChatWindow";
import { FloatingChatMinimizedPill } from "@/features/components/chat/ChatHeader";
import { SearchButton } from "@/features/components/chat/SearchButton";
import { mcpCall } from "@/lib/mcp/client";

jest.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
}));

jest.mock("@/features/components/chat/ChatSidePopover", () => ({
  ChatSidePopover: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

jest.mock("@/features/components/chat/FileContextMenu", () => ({
  FileContextMenu: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

jest.mock("@/lib/mcp/client", () => ({
  mcpCall: jest.fn(),
}));

const mockFetch = jest.fn();
const mockMcpCall = mcpCall as jest.MockedFunction<typeof mcpCall>;

beforeEach(() => {
  jest.clearAllMocks();
  global.fetch = mockFetch as typeof fetch;
});

describe("chat redesign port", () => {
  it("shows attachment summary with total size and per-file sizes", () => {
    render(
      <TerminalInputSection
        handleSubmit={(e) => e.preventDefault()}
        toolbarButtons={<div>Toolbar</div>}
        pathname="/browse"
        fileInputRef={{ current: null }}
        handleFileSelect={jest.fn()}
        textareaRef={{ current: null }}
        input="hello"
        handleTextareaChange={jest.fn()}
        handleTextareaKeyDown={jest.fn()}
        isRunning={true}
        isOperationMode={false}
        attachedFiles={[
          {
            stagedPath: "/tmp/a.pdf",
            originalName: "sleep-protocol.pdf",
            size: 1024,
          },
          {
            stagedPath: "/tmp/b.png",
            originalName: "recovery-chart.png",
            size: 2048,
          },
        ]}
        removeAttachedFile={jest.fn()}
        isDragOver={false}
      />,
    );

    expect(screen.getByText(/2 files attached/i)).toBeInTheDocument();
    expect(screen.getByText(/3\.0 kb/i)).toBeInTheDocument();
    expect(screen.getByText("1.0 KB")).toBeInTheDocument();
    expect(screen.getByText("2.0 KB")).toBeInTheDocument();
  });

  it("renders the chat composer tall enough for multi-line action drafts", () => {
    render(
      <TerminalInputSection
        handleSubmit={(e) => e.preventDefault()}
        toolbarButtons={<div>Toolbar</div>}
        pathname="/browse"
        fileInputRef={{ current: null }}
        handleFileSelect={jest.fn()}
        textareaRef={{ current: null }}
        input={[
          "Inspect the selected skill.",
          "Check the user value, structure, tests, and dashboard wiring.",
          "Propose focused improvements.",
        ].join("\n")}
        handleTextareaChange={jest.fn()}
        handleTextareaKeyDown={jest.fn()}
        isRunning={true}
        isOperationMode={false}
        attachedFiles={[]}
        removeAttachedFile={jest.fn()}
        isDragOver={false}
      />,
    );

    const composer = screen.getByRole("textbox", { name: /chat message input/i });
    expect(composer).toHaveAttribute("rows", "1");
    expect(composer).toHaveStyle({ minHeight: "48px", maxHeight: "200px" });
  });

  it("keeps the floating chat window inside narrow mobile viewports", () => {
    const { container } = render(
      <FloatingChatWindow
        chatContainerRef={{ current: null }}
        state={{
          isEnlarged: false,
          isDragOver: false,
          isOnline: true,
          isCliStale: false,
          isRunning: false,
          terminalFocused: false,
          chatView: "terminal",
          isOperationMode: false,
        }}
        handleDragOver={jest.fn()}
        handleDragLeave={jest.fn()}
        handleDrop={jest.fn()}
        header={<div>Header</div>}
        terminalContainerRef={{ current: null }}
        setTerminalFocused={jest.fn()}
      >
        <div>Input</div>
      </FloatingChatWindow>,
    );

    const windowRoot = container.firstElementChild;
    expect(windowRoot).toHaveClass("left-3", "right-3", "w-auto");
    expect(windowRoot).toHaveClass("sm:left-auto", "sm:right-6", "sm:w-[700px]");
  });

  it("renders setup hints as monospace copyable system messages", () => {
    const writeText = jest.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: { writeText },
    });

    render(
      <TerminalBottomSection
        chatView="terminal"
        terminalFocused={false}
        latestSystemMsg={{
          role: "system",
          content:
            "Failed to start claude: Airplane launch override is not ready\n\nSetup hint:\n```bash\nPull the model: ollama pull qwen3.5:9b\n```",
          timestamp: Date.now(),
        }}
        inputSection={<div>Input</div>}
        isOperationMode={false}
      />,
    );

    expect(screen.getByText(/failed to start claude/i)).toBeInTheDocument();
    expect(screen.getByText("Pull the model: ollama pull qwen3.5:9b")).toHaveClass(
      "font-mono",
    );

    fireEvent.click(screen.getByRole("button", { name: /copy setup hint/i }));

    expect(writeText).toHaveBeenCalledWith(
      "Pull the model: ollama pull qwen3.5:9b",
    );
  });

  it("renders the minimized pill with the active cli label", () => {
    const onRestore = jest.fn();
    render(
      <FloatingChatMinimizedPill
        onRestore={onRestore}
        statusColor="bg-emerald-500"
        isRunning={true}
        statusLabel="running"
        cliLabel="Claude Code"
      />,
    );

    const pill = screen.getByRole("button", { name: "Restore chat window" });
    expect(pill).toHaveTextContent("Claude Code");

    fireEvent.click(pill);
    expect(onRestore).toHaveBeenCalled();
  });

  it("shows top-ranked search results with overflow hidden behind a toggle", async () => {
    jest.useFakeTimers();
    mockMcpCall.mockImplementation(async (tool, args) => {
      if (tool === "unified-search") {
        expect(args).toMatchObject({
          q: "sleep",
          scopes: expect.arrayContaining(["knowledge", "skills", "decisions"]),
        });
        return {
          results: [
            {
              content: "Sleep protocol for recovery and performance",
              file_path: "/tmp/sleep-protocol.md",
              scope: "knowledge",
            },
            {
              content: "Sleep guide and recovery checklist",
              file_path: "/tmp/sleep-guide.md",
              scope: "knowledge",
            },
          ],
        };
      }

      if (tool === "get-context-files" && typeof args === "object" && args && "tab" in args) {
        const tab = String(args.tab);
        if (tab === "vault") {
          return {
            files: [
              {
                name: "sleep-summary.md",
                relativePath: "vault/sleep-summary.md",
                absolutePath: "/vault/sleep-summary.md",
                size: 128,
                modified: 1,
                extension: ".md",
                isDirectory: false,
              },
            ],
            hubFiles: [],
          };
        }
        if (tab === "docs") {
          return {
            files: [
              {
                name: "sleep-plan.pdf",
                relativePath: "docs/sleep-plan.pdf",
                absolutePath: "/docs/sleep-plan.pdf",
                size: 128,
                modified: 1,
                extension: ".pdf",
                isDirectory: false,
              },
            ],
            hubFiles: [],
          };
        }
        if (tab === "documents") {
          return {
            files: [
              {
                name: "diagnostics.log",
                relativePath: "logs/sleep-diagnostics.log",
                absolutePath: "/logs/sleep-diagnostics.log",
                size: 128,
                modified: 1,
                extension: ".log",
                isDirectory: false,
              },
            ],
            hubFiles: [],
          };
        }
      }

      return { files: [], hubFiles: [] };
    });

    const chatContainerRef = { current: null };
    const portalRef = { current: null };
    const popoverRef = { current: null };

    render(
      <SearchButton
        isOperationMode={false}
        pathname="/brain"
        isOpen={true}
        onToggle={jest.fn()}
        onAttachFile={jest.fn()}
        chatContainerRef={chatContainerRef}
        portalRef={portalRef}
        popoverRef={popoverRef}
      />,
    );

    fireEvent.change(screen.getByLabelText("Search knowledge and files"), {
      target: { value: "sleep" },
    });

    await act(async () => {
      jest.advanceTimersByTime(350);
    });

    await waitFor(() => {
      expect(screen.getByText("Top Results")).toBeInTheDocument();
    });

    const overflowToggle = screen.getByRole("button", { name: /more results/i });
    expect(overflowToggle).toBeInTheDocument();
    expect(screen.queryByText("diagnostics.log")).not.toBeInTheDocument();

    fireEvent.click(overflowToggle);
    expect(screen.getByText("diagnostics.log")).toBeInTheDocument();

    jest.useRealTimers();
  });
});
