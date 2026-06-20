import { transformIndexEntry } from "@/lib/browse/transforms";

describe("transformIndexEntry", () => {
  it("maps skill entry to BrowseItem with navigate action", () => {
    const entry = {
      id: "career",
      name: "career",
      description: "Job tracking",
      hub: "career",
      type: "skill",
      source_path: "project-brain/capabilities/skills/career-ops/SKILL.md",
    };

    const result = transformIndexEntry(entry, "skills");
    expect(result.id).toBe("career");
    expect(result.primaryAction.type).toBe("navigate");
    expect(result.primaryAction.target).toBe("/browse/career");
  });

  it("maps external registry integration entries to read-only setup actions", () => {
    const entry = {
      id: "cli:gh",
      name: "gh",
      title: "GitHub CLI",
      description: "GitHub CLI for repository management",
      hub: "system",
      type: "integration",
      source_path: "/repo/config/integrations/external_mcp_registry.yaml",
      cli_tools: [
        {
          name: "gh",
          installed: true,
          version: "gh version 2.70.0",
          configured: null,
          install_hint: "",
          homepage: "https://cli.github.com/",
        },
      ],
      metadata: {
        registry: "external_mcp_registry",
        service_type: "cli",
        status: "connected",
        setup_url: "https://cli.github.com/",
        check_command: "gh --version",
        ownerKind: "external",
        management: "unmanaged",
        scope: "global",
        primarySurface: "cli",
      },
    };

    const result = transformIndexEntry(entry, "integrations");

    expect(result.typeBadge).toBe("cli");
    expect(result.primaryAction).toEqual({
      label: "Copy Setup",
      type: "copy",
      target: "https://cli.github.com/",
    });
    expect(result.cliTools).toEqual(entry.cli_tools);
    expect(result.metadata?.ownerKind).toBe("external");
    expect(result.metadata?.primarySurface).toBe("cli");
    expect(result.actions?.map((action) => action.label)).toEqual([
      "CLI --help",
      "Copy Check",
      "Copy Setup",
      "Reveal Config",
    ]);
  });

  it("preserves skill group and release metadata on the live browse transform path", () => {
    const entry = {
      id: "knowledge",
      name: "knowledge",
      description: "Knowledge retrieval",
      hub: "workspace",
      type: "skill",
      source_path: "project-brain/capabilities/skills/knowledge/SKILL.md",
      metadata: {
        group: "brain",
        release: "mvp",
      },
    };

    const result = transformIndexEntry(entry, "skills");
    expect(result.metadata?.group).toBe("brain");
    expect(result.metadata?.release).toBe("mvp");
  });

  it("preserves supported client sources for skill entries", () => {
    const entry = {
      id: "dev-loops",
      name: "dev-loops",
      description: "Manage adaptive loops",
      hub: "external",
      type: "skill",
      source_path: "/tmp/project/.codex/skills/dev-loops/SKILL.md",
      source: "codex-local",
      ownership: "external",
      skill_clients: ["codex", "gemini", "claude"],
      client_sources: ["codex-local", "gemini-local", "claude-local"],
      metadata: {
        skill_client: "codex",
      },
    };

    const result = transformIndexEntry(entry, "skills");
    expect(result.metadata?.skillClients).toBe("codex,gemini,claude");
    expect(result.metadata?.clientSources).toBe("codex-local,gemini-local,claude-local");
    expect(result.metadata?.masterClient).toBe("codex");
  });

  it("preserves AI artifact inventory metadata on system metadata cards", () => {
    const entry = {
      id: "ai-artifact:project-repo:abc123",
      name: "ai-artifact:project-repo:abc123",
      title: "Agents",
      description: "project instruction artifact in repo",
      hub: "system",
      type: "instruction",
      source_path: "/tmp/repo/AGENTS.md",
      metadata: {
        inventory_source: "ai-artifact-inventory",
        brain_id: "project-repo",
        artifact_type: "instruction",
        client: "project",
        vendor: "project",
        classification: "unknown",
        warnings: "unknown_source",
      },
    };

    const result = transformIndexEntry(entry, "system-metadata");

    expect(result.id).toBe("ai-artifact:project-repo:abc123");
    expect(result.typeBadge).toBe("instruction");
    expect(result.primaryAction).toEqual({
      label: "Open",
      type: "open-file",
      target: "/tmp/repo/AGENTS.md",
    });
    expect(result.metadata?.brain_id).toBe("project-repo");
    expect(result.metadata?.classification).toBe("unknown");
    expect(result.metadata?.warnings).toBe("unknown_source");
  });

  it("keeps private-vault skill entries user-owned", () => {
    const entry = {
      id: "skill:private-vault:books",
      name: "books",
      description: "Personal library",
      hub: "workspace",
      type: "skill",
      source_path: "/Users/example/Projects/Au-vault/skills/books/SKILL.md",
      source: "private-vault",
      ownership: "user",
      metadata: {
        source_root: "private-vault",
        ownerKind: "user",
      },
    };

    const result = transformIndexEntry(entry, "skills");

    expect(result.metadata?.ownership).toBe("user");
    expect(result.metadata?.ownerKind).toBe("user");
  });

  it("maps Browse Inbox email packet entries to readable email cards", () => {
    const entry = {
      id: "email-drop:mail-drop:abc123",
      name: "first",
      title: "First invoice",
      description: "billing@example.com · Thu, 14 May 2026 12:00:00 +0000",
      hub: "workspace",
      type: "email-drop",
      source_path: "/tmp/Documents/Augur/inbox/email/first.eml",
      metadata: {
        journey_category: "inbox",
        source_root: "documents-inbox-email",
        email_from: "billing@example.com",
        attachment_count: "1",
        link_count: "1",
      },
    };

    const result = transformIndexEntry(entry, "vault");

    expect(result.id).toBe("email-drop:mail-drop:abc123");
    expect(result.title).toBe("First invoice");
    expect(result.typeBadge).toBe("Email");
    expect(result.primaryAction).toEqual({
      label: "Open Email",
      type: "open-file",
      target: "/tmp/Documents/Augur/inbox/email/first.eml",
    });
    expect(result.metadata?.email_from).toBe("billing@example.com");
  });

  it("normalizes operational skill metadata from top-level snake_case fields", () => {
    const entry = {
      id: "knowledge",
      name: "knowledge",
      description: "Knowledge retrieval",
      hub: "workspace",
      type: "skill",
      source_path: "project-brain/capabilities/skills/knowledge/SKILL.md",
      ownership: "augur",
      skill_type: "domain",
      quality_tier: "A",
      quality_score: 91,
      mcp_tool_count: 8,
      action_count: 3,
      page_count: 5,
      dashboard_path: "/workspace/memory",
      has_docs: true,
      needs_setup: true,
      enabled: true,
      update_available: false,
      adoption_ready: true,
      master_client: "codex",
      skill_clients: ["codex", "gemini"],
    };

    const result = transformIndexEntry(entry, "skills");
    expect(result.metadata?.qualityTier).toBe("A");
    expect(result.metadata?.qualityScore).toBe("91");
    expect(result.metadata?.mcpToolCount).toBe("8");
    expect(result.metadata?.actionCount).toBe("3");
    expect(result.metadata?.pageCount).toBe("5");
    expect(result.metadata?.dashboardPath).toBe("/workspace/memory");
    expect(result.metadata?.ownership).toBe("augur");
    expect(result.metadata?.skillType).toBe("domain");
    expect(result.metadata?.hasDashboardPage).toBe("true");
    expect(result.metadata?.needsSetup).toBe("true");
    expect(result.metadata?.enabled).toBe("true");
    expect(result.metadata?.updateAvailable).toBe("false");
    expect(result.metadata?.adoptionReady).toBe("true");
    expect(result.metadata?.masterClient).toBe("codex");
    expect(result.metadata?.skillClients).toBe("codex,gemini");
    expect(result.metadata?.hasDocs).toBe("true");
  });

  it("normalizes operational skill metadata from metadata snake_case fields and preserves existing metadata", () => {
    const entry = {
      id: "knowledge",
      name: "knowledge",
      description: "Knowledge retrieval",
      hub: "workspace",
      type: "skill",
      source_path: "project-brain/capabilities/skills/knowledge/SKILL.md",
      metadata: {
        quality_tier: "B",
        quality_score: "81",
        mcp_tool_count: 2,
        action_count: 4,
        page_count: 1,
        has_dashboard_page: "false",
        has_docs: "false",
        needs_setup: "true",
        enabled: "false",
        update_available: "false",
        adoption_ready: "true",
        skill_type: "domain",
        skill_clients: ["claude", "gemini"],
        qualityTier: "C",
      },
    };

    const result = transformIndexEntry(entry, "skills");
    expect(result.metadata?.qualityTier).toBe("C");
    expect(result.metadata?.qualityScore).toBe("81");
    expect(result.metadata?.mcpToolCount).toBe("2");
    expect(result.metadata?.actionCount).toBe("4");
    expect(result.metadata?.pageCount).toBe("1");
    expect(result.metadata?.hasDashboardPage).toBe("false");
    expect(result.metadata?.needsSetup).toBe("true");
    expect(result.metadata?.enabled).toBe("false");
    expect(result.metadata?.updateAvailable).toBe("false");
    expect(result.metadata?.adoptionReady).toBe("true");
    expect(result.metadata?.skillType).toBe("domain");
    expect(result.metadata?.hasDocs).toBe("false");
    expect(result.metadata?.skillClients).toBe("claude,gemini");
  });

  it("maps command entry to copy action", () => {
    const entry = {
      id: "dev-debug",
      title: "/dev-debug",
      name: "dev-debug",
      hub: "dev",
      description: "Debug issues",
      type: "command",
      source_path: "project-brain/capabilities/skills/platform-admin/commands/dev-debug.md",
    };

    const result = transformIndexEntry(entry, "commands");
    expect(result.primaryAction.type).toBe("copy");
    expect(result.primaryAction.target).toBe("/dev-debug");
  });

  it("cleans wiki page tags and maps wiki cards to source-first actions", () => {
    const entry = {
      id: "concepts/adaptive-ops-command-loop",
      name: "concepts/adaptive-ops-command-loop",
      title: "Adaptive Operations Command Loop",
      hub: "workspace",
      description: "Adaptive operations loops are command-driven maintenance workflows.",
      type: "wiki",
      source_path: "/Users/test/Au-vault/wiki/concepts/adaptive-ops-command-loop.md",
      tags: [
        "wiki",
        "concept",
        "adaptive-ops-command-loop",
        "auto-wiki-maintenance-cycle",
        "dev-loops-autonomous-cycles",
        "adaptive",
      ],
      metadata: {
        modified: "2026-04-22T08:15:51Z",
        pageTags: "wiki,page,brain,Adaptive Operations Command Loop,knowledge-maintenance",
      },
    };

    const result = transformIndexEntry(entry, "wiki");
    expect(result.typeBadge).toBe("Concept");
    expect(result.tags).toEqual([
      "auto-wiki-maintenance-cycle",
      "dev-loops-autonomous-cycles",
      "adaptive",
      "knowledge-maintenance",
    ]);
    expect(result.metadata?.pageType).toBe("concept");
    expect(result.metadata?.pageTags).toBe(
      "auto-wiki-maintenance-cycle,dev-loops-autonomous-cycles,adaptive,knowledge-maintenance",
    );
    expect(result.tags).not.toEqual(expect.arrayContaining([
      "wiki",
      "concept",
      "page",
      "brain",
      "Adaptive Operations Command Loop",
      "adaptive-ops-command-loop",
    ]));
    expect(result.primaryAction).toEqual({
      label: "Read Wiki",
      type: "open-file",
      target: "/Users/test/Au-vault/wiki/concepts/adaptive-ops-command-loop.md",
    });
    expect(result.actions?.map((action) => action.label)).toEqual([
      "Reveal Source",
      "Copy Path",
      "Copy Markdown Link",
      "Prepare Wiki Update",
      "Reindex Wiki",
    ]);
    expect(result.actions).toContainEqual(expect.objectContaining({
      label: "Copy Markdown Link",
      type: "copy",
      target: "[[concepts/adaptive-ops-command-loop|Adaptive Operations Command Loop]]",
    }));
    expect(result.actions).toContainEqual(expect.objectContaining({
      label: "Prepare Wiki Update",
      type: "mcp-tool",
      target: "wiki-update",
      args: { limit: 20 },
    }));
    expect(result.actions).toContainEqual(expect.objectContaining({
      label: "Reveal Source",
      type: "reveal-file",
      target: "/Users/test/Au-vault/wiki/concepts/adaptive-ops-command-loop.md",
    }));
  });

  it("maps grouped log entry to source card actions and preserves readable title", () => {
    const entry = {
      id: "daemon",
      title: "Daemon",
      name: "daemon",
      hub: "system",
      description: "Daemon services and background job logs",
      type: "log",
      source_path: "/tmp/logs/daemon/stderr.log",
      metadata: {
        category: "daemon",
        source_count: "4",
        file_count: "18",
        total_size_human: "12.5 KB",
        logs_root_path: "/tmp/logs",
        latest_folder_path: "/tmp/logs/daemon",
        latest_file_path: "/tmp/logs/daemon/stderr.log",
        latest_file_name: "stderr.log",
      },
    };

    const result = transformIndexEntry(entry, "logs");
    expect(result.title).toBe("Daemon");
    expect(result.icon).toBe("Activity");
    expect(result.typeBadge).toBe("4 sources");
    expect(result.description).toBe(
      "Daemon services and background job logs · 18 files · 12.5 KB",
    );
    expect(result.primaryAction.type).toBe("open-file");
    expect(result.primaryAction.target).toBe("/tmp/logs/daemon/stderr.log");
    expect(result.actions?.map((action) => action.label)).toEqual([
      "Open Logs Root",
      "Open Recent Folder",
      "Reveal Latest",
      "Copy Latest Path",
    ]);
  });

  it("maps job ledger log entry to an MCP-powered inspector card", () => {
    const entry = {
      id: "job-ledger",
      title: "Job Ledger",
      name: "job-ledger",
      hub: "command",
      description: "1 job ledger record(s), 0 active, 1 terminal. Latest: adr-743-smoke.",
      type: "job-ledger",
      source_path: "/Users/test/Library/Application Support/Augur/state/jobs/adr-743-smoke/events.jsonl",
      metadata: {
        category: "job-ledger",
        jobs_root_path: "/Users/test/Library/Application Support/Augur/state/jobs",
        latest_folder_path: "/Users/test/Library/Application Support/Augur/state/jobs/adr-743-smoke",
        latest_file_path: "/Users/test/Library/Application Support/Augur/state/jobs/adr-743-smoke/events.jsonl",
        latest_job_id: "adr-743-smoke",
        job_count: "1",
        active_job_count: "0",
        terminal_job_count: "1",
        state_counts: "complete:1",
        total_size_human: "95 B",
      },
    };

    const result = transformIndexEntry(entry, "logs");

    expect(result.title).toBe("Job Ledger");
    expect(result.typeBadge).toBe("1 job");
    expect(result.primaryAction).toEqual({
      label: "Inspect Jobs",
      type: "mcp-tool",
      target: "jobs-list",
    });
    expect(result.description).toContain("states: complete:1");
    expect(result.metadata?.latestJob).toBe("adr-743-smoke");
    expect(result.actions?.map((action) => action.label)).toEqual([
      "Open Jobs Root",
      "Open Latest Job",
      "Reveal Latest Events",
      "Copy Latest Path",
    ]);
  });

  it("maps background routine entry to browse item metadata", () => {
    const entry = {
      id: "insight_scanner",
      title: "Insight Scanner",
      name: "Insight Scanner",
      hub: "system",
      description: "Scans dashboard pages and asks Claude for improvements",
      type: "background-routines",
      source_path: "project-brain/capabilities/skills/daemon/scripts/insight_scanner.py",
      metadata: {
        source_kind: "daemon-script",
        spawn_kind: "ai-cli-spawn",
        status: "enabled",
        cadence: "triggered by daemon-service or other",
        lastRun: "2026-05-11T05:00:00Z",
        tokensPerDay: "780000",
      },
    };

    const result = transformIndexEntry(entry, "background-routines");
    expect(result.id).toBe("insight_scanner");
    expect(result.typeBadge).toBe("daemon-script");
    expect(result.description).toContain("triggered by daemon-service or other");
    expect(result.description).toContain("last:");
    expect(result.description).toContain("780K tokens/day");
    expect(result.metadata?.status).toBe("enabled");
    expect(result.metadata?.spawn_kind).toBe("ai-cli-spawn");
    expect(result.actions?.map((action) => action.label)).toContain("Reveal");
  });

  it("defaults to open-file for unknown categories", () => {
    const entry = {
      id: "some-script",
      name: "some-script",
      hub: "ai",
      description: "A script",
      type: "script",
      source_path: "project-brain/capabilities/skills/rag/scripts/indexer.py",
    };

    const result = transformIndexEntry(entry, "scripts");
    expect(result.primaryAction.type).toBe("open-file");
    expect(result.primaryAction.target).toBe("project-brain/capabilities/skills/rag/scripts/indexer.py");
  });

  it("sets id from entry.id field", () => {
    const entry = {
      id: "my-skill",
      name: "my-skill",
      hub: "dev",
      description: "A skill",
      type: "skill",
      source_path: "project-brain/capabilities/skills/my-skill/SKILL.md",
    };

    const result = transformIndexEntry(entry, "skills");
    expect(result.id).toBe("my-skill");
  });

  it("uses explicit ids before source_path for source-backed browse entries", () => {
    const first = transformIndexEntry(
      {
        id: "vault:shared:README",
        name: "README",
        title: "README",
        hub: "system",
        source_path: "/Users/test/Au-vault/wiki/README.md",
        metadata: {
          vault_scope: "shared",
        },
      },
      "vault",
    );
    const second = transformIndexEntry(
      {
        id: "vault:private:README",
        name: "README",
        title: "README",
        hub: "system",
        source_path: "/Users/test/Au-docs/README.md",
        metadata: {
          vault_scope: "private",
        },
      },
      "vault",
    );

    expect(first.id).toBe("vault:shared:README");
    expect(second.id).toBe("vault:private:README");
    expect(first.id).not.toBe(second.id);
  });

  it("uses source_path as the stable id for source-backed browse entries without explicit ids", () => {
    const result = transformIndexEntry(
      {
        name: "README",
        title: "README",
        hub: "system",
        source_path: "/Users/test/Au-vault/wiki/README.md",
      },
      "vault",
    );

    expect(result.id).toBe("/Users/test/Au-vault/wiki/README.md");
  });

  it("uses source_path for non-overlay source-backed entries with generic duplicate ids", () => {
    const first = transformIndexEntry(
      {
        id: "README",
        name: "README",
        title: "README",
        hub: "system",
        source_path: "/Users/test/Au-vault/wiki/README.md",
      },
      "vault",
    );
    const second = transformIndexEntry(
      {
        id: "README",
        name: "README",
        title: "README",
        hub: "system",
        source_path: "/Users/test/Au-docs/README.md",
      },
      "vault",
    );

    expect(first.id).toBe("/Users/test/Au-vault/wiki/README.md");
    expect(second.id).toBe("/Users/test/Au-docs/README.md");
    expect(first.id).not.toBe(second.id);
  });

  it("sets path from source_path", () => {
    const entry = {
      id: "rag",
      name: "rag",
      hub: "ai",
      description: "RAG skill",
      type: "skill",
      source_path: "project-brain/capabilities/skills/rag/SKILL.md",
    };

    const result = transformIndexEntry(entry, "skills");
    expect(result.path).toBe("project-brain/capabilities/skills/rag/SKILL.md");
  });

  it("sets description from entry.description", () => {
    const entry = {
      id: "rag",
      name: "rag",
      hub: "ai",
      description: "RAG skill description",
      type: "skill",
      source_path: "project-brain/capabilities/skills/rag/SKILL.md",
    };

    const result = transformIndexEntry(entry, "skills");
    expect(result.description).toBe("RAG skill description");
  });

  it("gives prompts entries an open-template primary action", () => {
    const item = transformIndexEntry(
      {
        id: "ide-prompt-resume-tailor",
        title: "ide-prompt-resume-tailor",
        description: "Tailor a resume to a job posting",
        source_path: "/tmp/skills/resume/prompts/resume-tailor.md",
        type: "prompt",
      },
      "prompts",
    );
    expect(item.primaryAction).toEqual({
      label: "Open Template",
      type: "open-file",
      target: "/tmp/skills/resume/prompts/resume-tailor.md",
    });
  });

  it("pages entry with explicit route navigates to that route", () => {
    // Regression: pages entries with entry.route must use it directly (fix 82dea8b92)
    const item = transformIndexEntry(
      {
        id: "rag",
        name: "rag",
        title: "RAG",
        description: "Retrieval-Augmented Generation",
        type: "page",
        route: "/workspace/rag",
      },
      "pages",
    );
    expect(item.primaryAction).toEqual({
      label: "Open",
      type: "navigate",
      target: "/workspace/rag",
    });
  });

  it("pages entry with no route falls back to /workspace/{name} and never /unknown", () => {
    // Regression: pages entries without route or metadata.route fall back to
    // /workspace/${entry.name || ""} — must never produce /unknown
    const item = transformIndexEntry(
      {
        id: "memory",
        name: "memory",
        title: "Memory",
        description: "Knowledge memory surface",
        type: "page",
      },
      "pages",
    );
    expect(item.primaryAction.target).toBe("/workspace/memory");
    expect(item.primaryAction.target).not.toBe("/unknown");
    expect(item.primaryAction).toEqual({
      label: "Open",
      type: "navigate",
      target: "/workspace/memory",
    });
  });

});
