import { expect, type Page, test } from "@playwright/test";

type ToolRequest = {
  tool?: string;
  args?: Record<string, unknown>;
};

const wikiStatus = {
  success: true,
  verdict: "structure_ok_compile_backlog",
  healthy: false,
  structure: {
    pages: 72,
    missing_required: [],
    missing_links: [],
    orphan_pages: [],
    broken_links: [],
    schema_violations: [],
  },
  compiler: {
    current: false,
    sources_total: 648,
    sources_compiled_with_concepts: 391,
    sources_pending_or_changed: 1,
  },
  coverage: {
    concept_coverage_ratio: 0.603,
    top_uncovered_source_families: [
      { family: "vault", total: 210, uncovered: 88 },
    ],
  },
  index: {
    indexed: true,
    wiki_rag_entries: 71,
  },
  batches: {
    batch_count: 4,
    needs_update: true,
  },
  compounding_health: {
    target_sources_per_page: "8-15",
    concept_page_count: 35,
    average_sources_per_concept_page: 11.17,
    thin_page_count: 0,
  },
  actions: [
    {
      id: "prepare-incremental-batch",
      priority: "high",
      tool: "wiki-update",
      command: "/wiki update",
      reason: "Changed sources need concept extraction.",
      inputs: { limit: 20 },
    },
  ],
};

const wikiItem = {
  id: "concepts/local-first-systems.md",
  title: "Local-First Systems",
  description: "Concept page synthesized from durable cross-source wiki evidence.",
  hub: "workspace",
  source_path: "/Users/test/Au-vault/wiki/concepts/local-first-systems.md",
  page_type: "concept",
  tags: ["local-first-systems", "offline", "sync"],
  metadata: {
    page_type: "concept",
    tags: ["offline", "sync"],
  },
};

async function installWikiSurfaceMocks(page: Page) {
  let folders = [
    {
      id: "downloads",
      name: "Downloads",
      path: "/Users/me/Downloads",
      enabled: true,
      counts: {
        new_files: 3,
        document_candidates: 2,
        trash_candidates: 1,
        failed: 0,
      },
    },
  ];
  const emailSources = [
    {
      id: "self-mail",
      type: "email",
      adapter: "apple_mail",
      display_name: "Self Mail",
      enabled: true,
      filters: {
        from_addresses: ["gur.sannikov@me.com"],
        mailbox_or_label: "Augur Intake",
        unread_only: true,
      },
      batch: { limit: 5, order: "newest_first" },
      after_success: { action: "archive_or_move", target: "Augur Consumed" },
      counts: {
        matching_messages: 2,
        attachments: 1,
        article_links: 3,
        failed: 0,
      },
      last_scan_at: "2026-04-27T10:30:00.000Z",
      health_state: "ok",
    },
  ];

  await page.addInitScript(() => {
    window.localStorage.setItem("augur-welcome-dismissed", "true");
  });

  await page.route("**/api/mcp/tool", async (route) => {
    const body = route.request().postDataJSON() as ToolRequest;
    const tool = body.tool;
    const args = body.args ?? {};

    if (tool === "brain-insights") {
      await route.fulfill({
        json: {
          success: true,
          latest_runs: [
            {
              id: "inbox-run-1",
              status: "completed",
              started_at: "2026-04-24T08:00:00Z",
              files_seen: 3,
              files_moved: 2,
              files_indexed: 2,
              files_failed: 0,
              insights: [
                {
                  title: "Downloads intake needs review",
                  summary: "Recent files can strengthen the local-first wiki page after consume.",
                  sources: [{ title: "Downloads" }],
                  next_actions: ["Consume Downloads", "Run wiki update"],
                },
              ],
            },
          ],
          wiki_status: wikiStatus,
          retained_ask_outcomes: [
            {
              question: "How should inbox files update the wiki?",
              summary: "Retained outcomes should become wiki update inputs when durable.",
            },
          ],
          retained_ask_clusters: [
            {
              id: "wiki-compounding",
              label: "Wiki compounding",
              summary: "Ask outcomes and file intake converge into concept updates.",
            },
          ],
        },
      });
      return;
    }

    if (tool === "wiki-update") {
      await route.fulfill({
        json: {
          success: true,
          status: "agent_action_required",
          message: "Wiki update batch prepared.",
          batch: { count: 1 },
          backlog: {
            sources_pending_or_changed: 1,
            batch_count: 1,
            remaining_after_batch: 0,
          },
        },
      });
      return;
    }

    if (tool === "inbox-folders") {
      if (args.action === "add") {
        folders = [
          ...folders,
          {
            id: "desktop",
            name: String(args.name || "Desktop"),
            path: String(args.path || "/Users/me/Desktop"),
            enabled: true,
            counts: {
              new_files: 0,
              document_candidates: 0,
              trash_candidates: 0,
              failed: 0,
            },
          },
        ];
        await route.fulfill({ json: { success: true, message: "Folder added." } });
        return;
      }

      await route.fulfill({
        json: {
          success: true,
          folders,
          email_sources: emailSources,
          run_status: {
            state: "idle",
            message: "Ready for folder actions.",
          },
        },
      });
      return;
    }

    if (tool === "email-scan-source") {
      await route.fulfill({ json: { success: true, message: "Email scan completed." } });
      return;
    }

    if (tool === "email-consume-source") {
      await route.fulfill({ json: { success: true, message: "Email consume completed." } });
      return;
    }

    if (tool === "inbox-scan-folder") {
      await route.fulfill({ json: { success: true, message: "Scan completed." } });
      return;
    }

    if (tool === "inbox-consume-folder") {
      await route.fulfill({ json: { success: true, message: "Consume completed." } });
      return;
    }

    if (tool === "inbox-purge-folder") {
      await route.fulfill({ json: { success: true, message: "Purge completed." } });
      return;
    }

    if (tool === "browse-index") {
      await route.fulfill({
        json: {
          status: "ok",
          count: 1,
          total_count: 1,
          last_indexed: "2026-04-24T08:00:00Z",
          items: args.category === "wiki" ? [wikiItem] : [],
        },
      });
      return;
    }

    if (tool === "file-info") {
      await route.fulfill({ json: { exists: true } });
      return;
    }

    if (tool === "open-file" || tool === "reveal-in-finder" || tool === "wiki-reindex") {
      await route.fulfill({ json: { success: true, message: `${tool} completed.` } });
      return;
    }

    await route.fulfill({ json: { success: true } });
  });
}

async function expectNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => ({
    documentOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    bodyOverflow: document.body.scrollWidth - document.body.clientWidth,
  }));
  expect(overflow.documentOverflow).toBeLessThanOrEqual(2);
  expect(overflow.bodyOverflow).toBeLessThanOrEqual(2);
}

test.describe("Wiki LLM user surfaces", () => {
  test.beforeEach(async ({ page }) => {
    await installWikiSurfaceMocks(page);
  });

  test("Brain Insights exposes wiki status, retained asks, and update action", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto("/workspace/insights", { waitUntil: "networkidle" });

    await expect(page.getByRole("heading", { name: "Brain Insights" })).toBeVisible();
    await expect(page.getByText("Source coverage")).toBeVisible();
    await expect(page.getByText("Downloads intake needs review")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Retained ask outcomes" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Wiki compounding" })).toBeVisible();

    await page.getByRole("button", { name: "Prepare wiki update" }).click();
    await expect(page.getByText("Wiki update batch prepared.")).toBeVisible();
    await expectNoHorizontalOverflow(page);
  });

  test("Brain Inbox supports folder and email intake interactions", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto("/workspace/inbox", { waitUntil: "networkidle" });

    await expect(page.getByRole("heading", { name: "Brain Inbox" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Email sources" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Self Mail" })).toBeVisible();
    await expect(page.getByText("2 matching emails")).toBeVisible();
    await expect(page.getByText("3 article links")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Downloads" })).toBeVisible();
    await expect(page.getByText("/Users/me/Downloads")).toBeVisible();

    await page.getByRole("textbox", { name: "Name" }).fill("Desktop");
    await page.getByRole("textbox", { name: "Folder path" }).fill("/Users/me/Desktop");
    await page.getByRole("button", { name: "Add Folder" }).click();
    await expect(page.getByText("Folder added.")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Desktop" })).toBeVisible();
    await expect(page.getByText("/Users/me/Desktop")).toBeVisible();

    await page.getByRole("button", { name: "Scan Downloads" }).click();
    await expect(page.getByText("Scan completed.")).toBeVisible();
    await page.getByRole("button", { name: "Consume Downloads" }).click();
    await expect(page.getByText("Consume completed.")).toBeVisible();
    await page.getByRole("button", { name: "Scan Self Mail" }).click();
    await expect(page.getByText("Email scan completed.")).toBeVisible();
    await page.getByRole("button", { name: "Consume Self Mail" }).click();
    await expect(page.getByText("Email consume completed.")).toBeVisible();
    await page.getByRole("button", { name: "Prepare wiki update for Self Mail" }).click();
    await expect(page.getByText("Wiki update batch prepared.")).toBeVisible();
    await expectNoHorizontalOverflow(page);
  });

  test("Browse wiki category ranks pages and keeps secondary actions in the menu", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto("/browse?category=wiki", { waitUntil: "networkidle" });

    await expect(page.getByRole("heading", { name: "Browse" })).toBeVisible();
    await expect(page.getByText("1 wiki")).toBeVisible();
    await expect(page.getByText("Local-First Systems")).toBeVisible();
    await expect(page.getByRole("button", { name: "Read Wiki" })).toBeVisible();

    await page.getByTestId("browse-card-overflow").click();
    await expect(page.getByRole("menuitem", { name: "Copy Markdown Link" })).toBeVisible();
    await expect(page.getByRole("menuitem", { name: "Prepare Wiki Update" })).toBeVisible();
    await expect(page.getByRole("menuitem", { name: "Reindex Wiki" })).toBeVisible();
    await page.getByRole("menuitem", { name: "Prepare Wiki Update" }).click();
    await expect(page.getByText("Wiki update batch prepared.")).toBeVisible();
    await expectNoHorizontalOverflow(page);
  });

  test("mobile wiki surfaces keep primary content readable", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });

    await page.goto("/workspace/insights", { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: "Brain Insights" })).toBeVisible();
    await expect(page.getByText("Wiki status")).toBeVisible();
    await expectNoHorizontalOverflow(page);

    await page.goto("/workspace/inbox", { waitUntil: "networkidle" });
    await expect(page.getByRole("heading", { name: "Brain Inbox" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Self Mail" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Consume Downloads" })).toBeVisible();
    await expectNoHorizontalOverflow(page);

    await page.goto("/browse?category=wiki", { waitUntil: "networkidle" });
    await expect(page.getByText("Local-First Systems")).toBeVisible();
    await expectNoHorizontalOverflow(page);
  });
});
