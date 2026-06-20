import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import InboxPage from "@/features/pages/workspace/inbox/page";

const mockRefetch = jest.fn();
const mockUseMcpQuery = jest.fn();

jest.mock("@/lib/mcp/useMcpQuery", () => ({
  useMcpQuery: (...args: unknown[]) => mockUseMcpQuery(...args),
}));

const unifiedInboxPayload = {
  source_lanes: [
    {
      id: "claude-chat",
      type: "chat_mcp",
      name: "Claude Chat",
      domain: "docs",
      drop_root: "/Users/example/Projects/Au-docs/inbox/claude",
      write_modes: ["mcp_content", "filesystem_mcp", "pending_drop"],
      default_target_vault: "personal",
      allowed_targets: ["personal"],
      enabled: true,
      health_state: "ready",
    },
  ],
  vault_targets: [
    {
      id: "personal",
      kind: "private",
      name: "Personal",
      vault_root: "/Users/example/Projects/Au-vault",
      docs_root: "/Users/example/Projects/Au-docs",
      default: true,
      writable: true,
    },
  ],
  discovered_vaults: [
    {
      candidate_id: "project-alpha",
      kind: "project",
      name: "Project Alpha",
      vault_root: "/Users/example/Projects/alpha/vault",
      docs_root: "/Users/example/Projects/alpha/docs",
      reason: "found .augur/vault.yaml in cloned repo",
      status: "unapproved",
      writable: false,
    },
  ],
  routing_queue: [
    {
      packet_id: "packet-1",
      title: "Augur Office Hours deck",
      source_id: "claude-chat",
      status: "needs_route",
      failure_state: "needs_route",
      packet_dir: "/Users/example/Projects/Au-docs/inbox/claude/packet-1",
    },
  ],
  latest_unified_runs: [
    {
      id: "packet-run-1",
      status: "success",
      source_id: "claude-chat",
      moved: 1,
      archived: 2,
      questions: 0,
    },
  ],
};

function setInboxQuery(overrides: Record<string, unknown> = {}) {
  mockUseMcpQuery.mockReturnValue({
    data: {
      success: true,
      ...unifiedInboxPayload,
      folders: [
        {
          id: "downloads",
          name: "Downloads",
          path: "/Users/example/Downloads",
          enabled: true,
          counts: { new_files: 3, document_candidates: 2, trash_candidates: 1, failed: 0 },
          last_scan_at: "2026-04-23T10:30:00.000Z",
          last_run_status: "partial_success",
        },
      ],
      run_status: {
        state: "idle",
        message: "Last scan found 3 new files.",
        updated_at: "2026-04-23T10:30:00.000Z",
      },
      ...overrides,
    },
    loading: false,
    error: null,
    refetch: mockRefetch,
  });
}

function setInboxQueryState(overrides: Record<string, unknown> = {}) {
  mockUseMcpQuery.mockReturnValue({
    data: null,
    loading: false,
    error: null,
    refetch: mockRefetch,
    ...overrides,
  });
}

const mockMcpCall = jest.fn(async () => ({ success: true }));

jest.mock("@/lib/mcp/client", () => ({
  mcpCall: (...args: unknown[]) => mockMcpCall(...args),
}));

describe("Brain Inbox page", () => {
  beforeEach(() => {
    mockMcpCall.mockReset();
    mockMcpCall.mockResolvedValue({ success: true });
    mockRefetch.mockClear();
    mockUseMcpQuery.mockReset();
    setInboxQuery();
  });

  it("queries the inbox-folders MCP list contract", () => {
    render(<InboxPage />);

    expect(mockUseMcpQuery).toHaveBeenCalledWith(["brain-inbox"], "inbox-folders", "live", {
      args: { action: "list" },
    });
  });

  it("renders watched folders and consume action", async () => {
    render(<InboxPage />);

    expect(screen.getByText("Brain Inbox")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "Brain Inbox" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 1, name: "Brain Inbox" })).not.toBeInTheDocument();
    expect(screen.getByText("Downloads")).toBeInTheDocument();
    expect(screen.getByText("3 new")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /consume downloads/i }));

    expect(mockMcpCall).toHaveBeenCalledWith("inbox-consume-folder", { folder_id: "downloads" });
  });

  it("renders unified inbox control layer and actions", async () => {
    render(<InboxPage />);

    expect(screen.getByText("Claude Chat")).toBeInTheDocument();
    expect(screen.getByText("Personal")).toBeInTheDocument();
    expect(screen.getByText("Project Alpha")).toBeInTheDocument();
    expect(screen.getByText("Augur Office Hours deck")).toBeInTheDocument();
    expect(screen.getByText("packet-run-1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /register Project Alpha/i })).toBeEnabled();

    await userEvent.click(screen.getByRole("button", { name: /register Project Alpha/i }));
    expect(mockMcpCall).toHaveBeenCalledWith("inbox-register-vault", { candidate_id: "project-alpha" });

    await userEvent.click(screen.getByRole("button", { name: /route packet-1/i }));
    expect(mockMcpCall).toHaveBeenCalledWith("inbox-route-packets", { packet_id: "packet-1" });
  });

  it("summarizes watched folder impact before batch actions", () => {
    render(<InboxPage />);

    const totals = screen.getByLabelText("Inbox totals");
    expect(totals).toHaveTextContent("New files to inspect");
    expect(totals).toHaveTextContent("Document candidates");
    expect(totals).toHaveTextContent("Trash candidates");
    expect(screen.getByText(/Downloads impact: scan reviews 3 new files/i)).toBeInTheDocument();
  });

  it("shows scan history and current run status from the inbox contract", () => {
    render(<InboxPage />);

    expect(screen.getByText(/Last scan found 3 new files/i)).toBeInTheDocument();
    expect(screen.getByText(/Last scan: Apr 23, 2026/i)).toBeInTheDocument();
    expect(screen.getByText(/Last action: partial_success/i)).toBeInTheDocument();
  });

  it("runs scan and purge actions through MCP", async () => {
    render(<InboxPage />);

    await userEvent.click(screen.getByRole("button", { name: /scan downloads/i }));
    expect(mockMcpCall).toHaveBeenCalledWith("inbox-scan-folder", { folder_id: "downloads" });

    await userEvent.click(screen.getByRole("button", { name: /purge downloads to trash/i }));
    expect(mockMcpCall).toHaveBeenCalledWith("inbox-purge-folder", { folder_id: "downloads" });
  });

  it("adds a folder through the inbox-folders MCP tool", async () => {
    render(<InboxPage />);

    await userEvent.type(screen.getByLabelText(/folder name/i), "Desktop");
    await userEvent.type(screen.getByLabelText(/folder path/i), "/Users/example/Desktop");
    await userEvent.click(screen.getByRole("button", { name: /add folder/i }));

    expect(mockMcpCall).toHaveBeenCalledWith("inbox-folders", {
      action: "add",
      name: "Desktop",
      path: "/Users/example/Desktop",
    });
  });

  it("keeps the folder form values when add fails", async () => {
    mockMcpCall.mockResolvedValueOnce({ success: false, error: "path does not exist" });
    render(<InboxPage />);

    await userEvent.type(screen.getByLabelText(/folder name/i), "Desktop");
    await userEvent.type(screen.getByLabelText(/folder path/i), "/Users/example/Desktop");
    await userEvent.click(screen.getByRole("button", { name: /add folder/i }));

    expect(screen.getByDisplayValue("Desktop")).toBeInTheDocument();
    expect(screen.getByDisplayValue("/Users/example/Desktop")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("path does not exist");
  });

  it("offers first-run folder presets when no watched folders exist", async () => {
    setInboxQuery({ folders: [] });

    render(<InboxPage />);

    expect(screen.getByText("Start with a folder you already use.")).toBeInTheDocument();
    expect(screen.getByText(/Scan previews candidates before anything moves/i)).toBeInTheDocument();
    expect(screen.queryByText("New files")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /use downloads/i }));

    expect(screen.getByDisplayValue("Downloads")).toBeInTheDocument();
    expect(screen.getByDisplayValue("~/Downloads")).toBeInTheDocument();
  });

  it("surfaces MCP query failures instead of showing an empty inbox", () => {
    setInboxQuery({ success: false, folders: [], error: "mcp unavailable" });

    render(<InboxPage />);

    expect(screen.getByText(/mcp unavailable/i)).toBeInTheDocument();
  });

  it("does not keep loading copy visible after the query has failed", () => {
    setInboxQueryState({ loading: true, error: "Unknown tool: inbox-folders" });

    const { container } = render(<InboxPage />);

    expect(screen.getByText(/Unknown tool: inbox-folders/i)).toBeInTheDocument();
    expect(screen.queryByText(/Loading inbox folders/i)).not.toBeInTheDocument();
    expect(container.querySelectorAll("main")).toHaveLength(0);
  });

  it("surfaces partial folder actions without calling them complete failures", async () => {
    mockMcpCall.mockResolvedValueOnce({ success: false, partial: true, status: "partial_success" });

    render(<InboxPage />);

    await userEvent.click(screen.getByRole("button", { name: /consume downloads/i }));

    expect(await screen.findByRole("status")).toHaveTextContent("partially completed");
  });

  it("disables sibling actions while one folder action is running", async () => {
    mockMcpCall.mockImplementationOnce(() => new Promise(() => undefined));

    render(<InboxPage />);

    await userEvent.click(screen.getByRole("button", { name: /consume downloads/i }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /scan downloads/i })).toBeDisabled();
      expect(screen.getByRole("button", { name: /purge downloads to trash/i })).toBeDisabled();
    });
  });

  it("renders Mail Drop sources and consumes through email-drop MCP tools", async () => {
    setInboxQuery({
      mail_drop_sources: [
        {
          id: "mail-drop",
          type: "email_drop_folder",
          name: "Mail Drop",
          path: "/Users/example/Documents/Augur/inbox/email",
          enabled: true,
          formats: [".eml", ".msg", ".mbox", ".zip"],
          batch_limit: 5,
          batch_order: "newest_first",
          after_success_action: "move_file",
          after_success_target: "processed",
          counts: {
            pending_files: 2,
            email_native: 1,
            archives: 1,
            degraded: 0,
            unsupported: 0,
            contained_messages: 2,
            attachments: 1,
            article_links: 3,
            failed: 0,
          },
          last_scan_at: "2026-04-27T10:30:00.000Z",
          health_state: "ok",
        },
      ],
    });

    render(<InboxPage />);

    expect(screen.getByRole("heading", { name: "Mail Drop sources" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: /^Mail Drop$/ })).toBeInTheDocument();
    expect(screen.getByText(/2 pending files/i)).toBeInTheDocument();
    expect(screen.getByText(/2 email packets/i)).toBeInTheDocument();
    expect(screen.getByText(/3 article links/i)).toBeInTheDocument();
    expect(screen.getByText(/\/Users\/example\/Documents\/Augur\/inbox\/email/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /consume mail drop/i }));

    expect(mockMcpCall).toHaveBeenCalledWith("email-drop-consume-source", { source_id: "mail-drop" });
  });

  it("runs Mail Drop scan and prepare wiki update actions", async () => {
    setInboxQuery({
      mail_drop_sources: [
        {
          id: "mail-drop",
          type: "email_drop_folder",
          name: "Mail Drop",
          path: "/Users/example/Mail Drop",
          enabled: true,
          formats: [".eml"],
          batch_limit: 5,
          batch_order: "newest_first",
          counts: {
            pending_files: 0,
            email_native: 0,
            archives: 0,
            degraded: 0,
            unsupported: 0,
            contained_messages: 0,
            attachments: 0,
            article_links: 0,
            failed: 0,
          },
          health_state: "ok",
        },
      ],
    });

    render(<InboxPage />);

    await userEvent.click(screen.getByRole("button", { name: /scan mail drop/i }));
    expect(mockMcpCall).toHaveBeenCalledWith("email-drop-scan-source", { source_id: "mail-drop" });

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /prepare wiki update for mail drop/i })).not.toBeDisabled();
    });
    await userEvent.click(screen.getByRole("button", { name: /prepare wiki update for mail drop/i }));
    expect(mockMcpCall).toHaveBeenCalledWith("wiki-update", { limit: 20 });
  });

  it("shows latest Mail Drop run value after consumed files leave the folder", () => {
    setInboxQuery({
      mail_drop_sources: [
        {
          id: "mail-drop",
          type: "email_drop_folder",
          name: "Mail Drop",
          path: "/Users/example/Mail Drop",
          enabled: true,
          formats: [".eml"],
          batch_limit: 5,
          batch_order: "newest_first",
          counts: {
            pending_files: 0,
            email_native: 0,
            archives: 0,
            degraded: 0,
            unsupported: 0,
            contained_messages: 0,
            attachments: 0,
            article_links: 0,
            failed: 0,
          },
          last_run_status: "success",
          health_state: "ok",
        },
      ],
      email_drop_latest_runs: [
        {
          id: "email_run_1",
          source_id: "mail-drop",
          status: "success",
          files_moved: 1,
          packets_created: 1,
          links_seen: 1,
          attachments_seen: 1,
        },
      ],
    });

    render(<InboxPage />);

    expect(screen.getByText(/0 pending files/i)).toBeInTheDocument();
    expect(screen.getByText(/Last run: 1 packet, 1 link, 1 attachment, 1 file moved/i)).toBeInTheDocument();
  });

  it("adds a Mail Drop source through the email-drop MCP tool", async () => {
    render(<InboxPage />);

    await userEvent.type(screen.getByLabelText(/display name/i), "Mail Drop");
    await userEvent.type(screen.getByLabelText(/mail drop path/i), "/Users/example/Mail Drop");
    await userEvent.click(screen.getByRole("button", { name: /add mail drop/i }));

    expect(mockMcpCall).toHaveBeenCalledWith("email-drop-sources", {
      action: "add",
      name: "Mail Drop",
      path: "/Users/example/Mail Drop",
    });
  });

  it("renders latest run file results with local backend evidence", () => {
    setInboxQuery({
      latest_runs: [
        {
          id: "run_ai_pc",
          status: "partial_success",
          airplane_mode: true,
          files_seen: 2,
          files_moved: 1,
          files_indexed: 1,
          files_needing_review: 1,
          cloud_calls: 0,
          local_agent_calls: 1,
          file_results: [
            {
              source_path: "C:/Users/example/Desktop/scan.pdf",
              final_path: "C:/Users/example/Projects/Au-vault/finance/2026-05-07-scan.pdf",
              source_card_path: "C:/Users/example/Projects/Au-vault/sources/files/2026-05-07-scan.md",
              content_type: "pdf",
              extraction_method: "openvino-ocr",
              hardware_backend: "NPU",
              confidence: "medium",
              route: "finance",
              renamed_to: "2026-05-07-scan.pdf",
              rag_indexed: true,
              status: "success",
              local_agent_used: true,
              cloud_used: false,
            },
          ],
        },
      ],
    });

    render(<InboxPage />);

    expect(screen.getByText("run_ai_pc")).toBeInTheDocument();
    expect(screen.getByText("Airplane mode")).toBeInTheDocument();
    expect(screen.getByText("openvino-ocr")).toBeInTheDocument();
    expect(screen.getByText("NPU")).toBeInTheDocument();
    expect(screen.getByText("cloud: no")).toBeInTheDocument();
  });

  it("renders latest run file results with cloud escalation evidence", () => {
    setInboxQuery({
      latest_runs: [
        {
          id: "run_cloud",
          status: "success",
          airplane_mode: false,
          files_seen: 4,
          files_moved: 3,
          files_indexed: 3,
          cloud_calls: 1,
          local_agent_calls: 2,
          files_needing_review: 1,
          file_results: [
            {
              source_path: "C:/Users/example/Desktop/demo-hard-photo.png",
              final_path: "C:/Users/example/Projects/Au-vault/finance/2026-05-07-cloud-invoice.png",
              source_card_path: "C:/Users/example/Projects/Au-vault/sources/files/2026-05-07-cloud-invoice.md",
              extracted_path: "C:/Users/example/Projects/Au-vault/sources/extracted/2026-05-07-cloud-invoice.extracted.md",
              content_type: "image",
              extraction_method: "document-extractor:1",
              hardware_backend: "cloud-vision",
              confidence: "high",
              route: "finance",
              renamed_to: "2026-05-07-cloud-invoice.png",
              rag_indexed: true,
              status: "success",
              cloud_used: true,
              escalation_reason: "local OCR and local vision did not produce usable text",
              cloud_provider: "OpenAICompatibleClient",
              cloud_model: "gpt-4o-mini",
              content_hash: "sha256:demo-cloud-invoice",
            },
          ],
        },
      ],
    });

    render(<InboxPage />);

    expect(screen.getByText(/cloud: 1/i)).toBeInTheDocument();
    expect(screen.getByText(/cloud-vision/i)).toBeInTheDocument();
    expect(screen.getByText(/local OCR and local vision/i)).toBeInTheDocument();
    expect(screen.getByText(/2026-05-07-cloud-invoice\.extracted\.md/i)).toBeInTheDocument();
    expect(screen.getByText(/OpenAICompatibleClient \/ gpt-4o-mini/i)).toBeInTheDocument();
  });
});
