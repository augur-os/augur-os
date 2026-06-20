import { test, expect } from "@playwright/test";

async function dismissBlockingOverlay(page: import("@playwright/test").Page) {
  const backdrop = page.locator("div.fixed.inset-0.z-\\[80\\]").first();
  for (let attempt = 0; attempt < 20; attempt += 1) {
    const visible = await backdrop.isVisible().catch(() => false);
    if (!visible) {
      await page.waitForTimeout(150);
      const stillVisible = await backdrop.isVisible().catch(() => false);
      if (!stillVisible) return;
      continue;
    }

    await page.keyboard.press("Escape").catch(() => {});
    await backdrop.click({ position: { x: 8, y: 8 } }).catch(() => {});
    const overlayClose = page
      .getByRole("button", { name: /close/i })
      .filter({ hasNot: page.locator(".floating-action-bar") })
      .first();

    if (await overlayClose.isVisible().catch(() => false)) {
      await overlayClose.click().catch(() => {});
    }

    await page.waitForTimeout(300);
  }
}

test.describe("Browse UX", () => {
  test("desktop keeps the Apps section expanded on first load", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto("/browse", { waitUntil: "networkidle" });

    const appsToggle = page.getByRole("button", { name: /apps/i });
    await expect(appsToggle).toHaveAttribute("aria-expanded", "true");
    await expect(page.getByRole("link", { name: "Workspace", exact: true })).toBeVisible();
  });

  test("browse welcome banner exposes quick links to primary hubs", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto("/browse", { waitUntil: "networkidle" });

    await expect(page.getByRole("link", { name: "Open Workspace" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Open Command" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Open Settings" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Open Career" })).toHaveCount(0);
    await expect(page.getByText("Press / to jump into search")).toBeVisible();
    await expect(page.getByText("Workspace library")).toBeVisible();
  });

  test("default shell uses editorial typography instead of code-style headings", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto("/browse", { waitUntil: "networkidle" });

    const shellStyles = await page.evaluate(() => {
      const rootStyles = getComputedStyle(document.documentElement);
      const heading = document.querySelector("h1, h2, h3");
      const headingStyles = heading ? getComputedStyle(heading) : null;

      return {
        theme: document.documentElement.getAttribute("data-theme"),
        fontSans: rootStyles.getPropertyValue("--font-sans").trim(),
        headingFont: headingStyles?.fontFamily ?? "",
      };
    });

    expect(shellStyles.theme?.startsWith("futuristic")).toBe(true);
    expect(shellStyles.fontSans.indexOf('"Inter"')).toBeGreaterThan(-1);
    expect(shellStyles.fontSans.indexOf('"Fira Sans"')).toBeGreaterThan(
      shellStyles.fontSans.indexOf('"Inter"'),
    );
    expect(shellStyles.headingFont).not.toContain("Fira Code");
  });

  test("desktop shows the action bar and hides the chat FAB", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto("/browse", { waitUntil: "networkidle" });

    const actionBar = page.locator(".floating-action-bar");
    await expect(actionBar).toBeVisible();
    await expect(
      actionBar.getByRole("button", { name: "Open chat" }),
    ).toBeVisible();
    await expect(
      actionBar.getByRole("button", { name: "Collapse action bar" }),
    ).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "Add note" }),
    ).toBeVisible();

    const barBox = await actionBar.boundingBox();
    expect(barBox).not.toBeNull();
    expect((barBox?.x ?? 0) + (barBox?.width ?? 0)).toBeGreaterThan(1100);
    await expect(actionBar).not.toContainText("USER");
    await expect(actionBar).not.toContainText("BUILDER");
    await expect(actionBar).not.toHaveClass(/liquid-glass/);
    await expect(page.getByRole("button", { name: "Add note" })).toHaveCount(1);
  });

  test("desktop chat launcher stays a single surface on hover", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto("/browse", { waitUntil: "networkidle" });

    const actionBar = page.locator(".floating-action-bar");
    const mergedLauncher = actionBar.getByTestId("collapsed-chat-launcher");
    await expect(mergedLauncher).toBeVisible();
    await expect(mergedLauncher).toHaveAttribute("aria-label", "Open chat");
    await expect(mergedLauncher.getByRole("button", { name: "Expand action bar" })).toHaveCount(0);
    await expect(actionBar.getByText("Actions")).toHaveCount(0);

    const chrome = await mergedLauncher.evaluate((el) => {
      if (!(el instanceof HTMLElement)) {
        return {
          dividerCount: -1,
          nestedButtonCount: -1,
          tag: "",
          className: "",
        };
      }
      return {
        dividerCount: el.querySelectorAll(".fab-divider").length,
        nestedButtonCount: el.querySelectorAll("button").length,
        tag: el.tagName,
        className: el.className,
      };
    });

    expect(chrome.dividerCount).toBe(0);
    expect(chrome.nestedButtonCount).toBe(0);
    expect(chrome.tag).toBe("BUTTON");
    expect(chrome.className).toContain("rounded-full");
    expect(chrome.className).toContain("h-12");
    expect(chrome.className).toContain("w-12");

    await mergedLauncher.hover();
    await page.waitForTimeout(250);
    await expect(actionBar.getByRole("button", { name: "Expand action bar" })).toHaveCount(0);
    await expect(actionBar.getByRole("button", { name: "Collapse action bar" })).toHaveCount(0);
    await expect(actionBar.getByText("Actions")).toHaveCount(0);

    const hoverChrome = await mergedLauncher.evaluate((el) => {
      if (!(el instanceof HTMLElement)) {
        return { dividerCount: -1 };
      }
      return {
        dividerCount: el.querySelectorAll(".fab-divider").length,
      };
    });

    expect(hoverChrome.dividerCount).toBe(0);
  });

  test("desktop chat header owns the mode badge instead of the outer action bar", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto("/browse", { waitUntil: "networkidle" });
    await dismissBlockingOverlay(page);

    const actionBar = page.locator(".floating-action-bar");
    await actionBar.getByRole("button", { name: "Open chat" }).click();

    await expect(
      page.getByRole("button", { name: /close chat window|end chat session/i }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: /switch to ai builder mode/i }),
    ).toBeVisible();
    await expect(actionBar).toHaveCount(0);

    const headerChrome = await page.evaluate(() => {
      const modeToggle = document.querySelector(
        '[aria-label="Switch to AI Builder mode"], [aria-label="Switch to User mode"]',
      ) as HTMLElement | null;
      const closeButton = document.querySelector(
        '[aria-label="Close chat window"]',
      ) as HTMLElement | null;

      return {
        modeRadius: modeToggle
          ? Number.parseFloat(getComputedStyle(modeToggle).borderRadius || "0")
          : 0,
        closeRadius: closeButton
          ? Number.parseFloat(getComputedStyle(closeButton).borderRadius || "0")
          : 0,
      };
    });

    expect(headerChrome.modeRadius).toBeGreaterThanOrEqual(999);
    expect(headerChrome.closeRadius).toBeGreaterThanOrEqual(999);

    const toolbarChrome = await page.evaluate(() => {
      const toolbar = document.querySelector(
        '[data-testid="chat-toolbar-rail"]',
      ) as HTMLElement | null;
      const composer = document
        .querySelector('[aria-label="Attach file"]')
        ?.closest(".rounded-2xl") as HTMLElement | null;

      return {
        toolbarRadius: toolbar
          ? Number.parseFloat(getComputedStyle(toolbar).borderRadius || "0")
          : 0,
        composerRadius: composer
          ? Number.parseFloat(getComputedStyle(composer).borderRadius || "0")
          : 0,
      };
    });

    expect(toolbarChrome.toolbarRadius).toBeGreaterThanOrEqual(999);
    expect(toolbarChrome.composerRadius).toBeGreaterThanOrEqual(16);

    await page
      .getByTestId("chat-toolbar-rail")
      .getByRole("button", { name: "Actions" })
      .click();

    await expect(
      page.getByPlaceholder("Search actions, tools, commands..."),
    ).toBeVisible();

    await page
      .getByTestId("chat-toolbar-rail")
      .getByRole("button", { name: "Search" })
      .click();
    await page.getByPlaceholder("Search RAG index...").fill("knowledge");
    const firstSearchResult = page.getByRole("button", { name: /attach skill\.md/i }).first();
    await expect(firstSearchResult).toBeVisible({ timeout: 10000 });
    await expect(page.getByText("Skills").first()).toBeVisible();
  });

  test("builder mode keeps the CLI selector in front of the chat body", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto("/browse", { waitUntil: "networkidle" });
    await dismissBlockingOverlay(page);

    await page
      .locator(".floating-action-bar")
      .getByRole("button", { name: "Open chat" })
      .click();

    await page.getByRole("button", { name: /switch to ai builder mode/i }).click();
    const selector = page.getByRole("button", { name: "Select CLI instance" });
    await selector.click();

    const kimiOption = page.getByRole("button", { name: /select cli: kimi/i });
    await expect(kimiOption).toBeVisible();

    const layering = await kimiOption.evaluate((el) => {
      if (!(el instanceof HTMLElement)) {
        return { topTag: null, topMatchesOption: false };
      }
      const rect = el.getBoundingClientRect();
      const topEl = document.elementFromPoint(
        rect.left + rect.width / 2,
        rect.top + rect.height / 2,
      );

      return {
        topTag: topEl?.tagName ?? null,
        topMatchesOption: topEl === el || !!topEl?.closest('[aria-label*="Select CLI: Kimi"]'),
      };
    });

    expect(layering.topTag).toBe("BUTTON");
    expect(layering.topMatchesOption).toBe(true);
  });

  test("builder mode exposes Customize Tabs inside the tab More menu", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto("/workspace", { waitUntil: "networkidle" });
    await dismissBlockingOverlay(page);

    await page
      .locator(".floating-action-bar")
      .getByRole("button", { name: "Open chat" })
      .click();
    await page.getByRole("button", { name: /switch to ai builder mode/i }).click();
    await page
      .getByRole("button", { name: /close chat window|end chat session/i })
      .click();

    await page.getByRole("button", { name: "More" }).first().click();

    await expect(
      page.getByRole("menuitem", { name: "Customize Workspace tabs" }),
    ).toBeVisible();
  });

  test("settings layout exposes sidebar skill controls", async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto("/settings/layout", { waitUntil: "networkidle" });

    await expect(page.getByText("Sidebar Skills")).toBeVisible();
    await expect(
      page.getByText(
        /No standalone skills are available for sidebar toggling|in sidebar/i,
      ),
    ).toBeVisible();
  });

  test("desktop chat composer owns the file attach affordance", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto("/browse", { waitUntil: "networkidle" });
    await dismissBlockingOverlay(page);

    await page
      .locator(".floating-action-bar")
      .getByRole("button", { name: "Open chat" })
      .click();

    await expect(page.getByLabel("Chat message input")).toBeVisible();
    await expect(page.getByText("Drop files here or click attach")).toBeVisible();
    await expect(page.getByLabel("Attach file")).toBeVisible();
    await expect(page.getByText("Drop files to attach them")).toHaveCount(0);
  });

  test("desktop chat composer uses a single dense control row", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto("/browse", { waitUntil: "networkidle" });
    await dismissBlockingOverlay(page);

    await page
      .locator(".floating-action-bar")
      .getByRole("button", { name: "Open chat" })
      .click();

    const composerRow = page.getByTestId("chat-composer-main-row");
    await expect(composerRow).toBeVisible();
    await expect(composerRow.getByLabel("Attach file")).toBeVisible();
    await expect(composerRow.getByLabel("Chat message input")).toBeVisible();
    await expect(composerRow.getByLabel("Send message")).toBeVisible();
  });

  test("desktop chat uses a denser terminal transcript shell", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto("/browse", { waitUntil: "networkidle" });
    await dismissBlockingOverlay(page);

    await page
      .locator(".floating-action-bar")
      .getByRole("button", { name: "Open chat" })
      .click();

    const terminal = page.getByRole("region", { name: "Terminal output" });
    await expect(terminal).toBeVisible();

    const terminalChrome = await terminal.evaluate((el) => {
      if (!(el instanceof HTMLElement)) {
        return { padding: "", marginTop: "", marginRight: "", borderRadius: "" };
      }
      const styles = getComputedStyle(el);
      return {
        padding: styles.padding,
        marginTop: styles.marginTop,
        marginRight: styles.marginRight,
        borderRadius: styles.borderRadius,
      };
    });

    expect(terminalChrome.padding).toBe("6px");
    expect(terminalChrome.marginTop).toBe("4px");
    expect(terminalChrome.marginRight).toBe("6px");
    expect(parseFloat(terminalChrome.borderRadius)).toBeGreaterThanOrEqual(16);
  });

  test("desktop chat composer keeps attachments in a compact tray", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto("/browse", { waitUntil: "networkidle" });
    await dismissBlockingOverlay(page);

    await page
      .locator(".floating-action-bar")
      .getByRole("button", { name: "Open chat" })
      .click();

    await page.getByLabel("Select files to attach").setInputFiles([
      {
        name: "sleep-protocol.pdf",
        mimeType: "application/pdf",
        buffer: Buffer.from("sleep"),
      },
      {
        name: "recovery-notes.txt",
        mimeType: "text/plain",
        buffer: Buffer.from("recover"),
      },
    ]);

    await expect(page.getByText(/2 files attached/i)).toBeVisible();
    const tray = page.getByTestId("composer-attachments-tray");
    await expect(tray).toBeVisible();
    await expect(tray.getByText("PDF", { exact: true })).toBeVisible();
    await expect(tray.getByText("TXT", { exact: true })).toBeVisible();
    const trayChrome = await tray.evaluate((el) => {
      if (!(el instanceof HTMLElement)) {
        return { overflowX: "", flexWrap: "" };
      }
      const styles = getComputedStyle(el);
      return {
        overflowX: styles.overflowX,
        flexWrap: styles.flexWrap,
      };
    });

    expect(trayChrome.overflowX).toBe("auto");
    expect(trayChrome.flexWrap).toBe("nowrap");
  });

  test("minimized desktop chat keeps a single right-edge launcher surface", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto("/browse", { waitUntil: "networkidle" });

    await page
      .locator(".floating-action-bar")
      .getByRole("button", { name: "Open chat" })
      .click();

    await page.getByTitle("Minimize").click();

    await expect(page.getByRole("button", { name: "Restore chat window" })).toBeVisible();
    await expect(page.locator(".floating-action-bar")).toHaveCount(0);

    const minimizedPill = page.getByRole("button", { name: "Restore chat window" });
    const pillBox = await minimizedPill.boundingBox();
    expect(pillBox).not.toBeNull();
    expect((pillBox?.x ?? 0) + (pillBox?.width ?? 0)).toBeGreaterThan(1100);

    const pillChrome = await minimizedPill.evaluate((el) => {
      if (!(el instanceof HTMLElement)) {
        return { dividerCount: -1, radius: 0 };
      }
      return {
        dividerCount: el.querySelectorAll(".fab-divider").length,
        radius: Number.parseFloat(getComputedStyle(el).borderRadius || "0"),
      };
    });

    expect(pillChrome.dividerCount).toBe(0);
    expect(pillChrome.radius).toBeGreaterThanOrEqual(999);
  });

  test("mobile shows the chat FAB and hides the desktop action bar", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/browse", { waitUntil: "networkidle" });

    await expect(
      page.getByRole("button", { name: "Open chat" }),
    ).toBeVisible();
    await expect(page.locator(".floating-action-bar")).toBeHidden();
  });

  test("mobile drawer closes after tapping a navigation link", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/browse", { waitUntil: "networkidle" });

    await page.getByRole("button", { name: "Open menu" }).click();
    await expect(
      page.getByRole("button", { name: "Close menu" }),
    ).toBeVisible();

    await page.getByRole("link", { name: "Settings" }).click();
    await page.waitForURL(/\/settings(?:\?|#|$)/);

    await expect(
      page.getByRole("button", { name: "Open menu" }),
    ).toBeVisible();
  });

  test("browse uses the shell scroll region instead of a nested list scroller", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto("/browse", { waitUntil: "networkidle" });

    await expect(
      page.getByRole("heading", { name: "Browse" }),
    ).toBeVisible();

    const nestedScroller = page.locator(
      "div.overflow-y-auto.overflow-x-hidden.shrink-0",
    );
    await expect(nestedScroller).toHaveCount(0);

    const mainScrollTop = await page.locator("#main-content").evaluate((el) => {
      if (!(el instanceof HTMLElement)) return -1;
      el.scrollTop = 300;
      return el.scrollTop;
    });

    expect(mainScrollTop).toBeGreaterThan(0);
  });

  test("skill pages render compact content-first block shells", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto("/browse/onboard", { waitUntil: "networkidle" });

    const blockRegions = page.locator("#main-content [role='region']");
    await expect(blockRegions.first()).toBeVisible();
    expect(await blockRegions.count()).toBeGreaterThanOrEqual(2);
    await expect(
      page.getByRole("heading", { name: "Actions", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: /local backend status/i }),
    ).toBeVisible();

    const chrome = await blockRegions.first().evaluate((el) => {
      if (!(el instanceof HTMLElement)) {
        return { borderRadius: 0, minHeight: 0, headerPaddingX: 0 };
      }

      const shellStyle = getComputedStyle(el);
      const header = el.querySelector("[role='heading']")?.parentElement;
      const headerStyle = header ? getComputedStyle(header) : null;

      return {
        borderRadius: Number.parseFloat(shellStyle.borderRadius || "0"),
        minHeight: Number.parseFloat(shellStyle.minHeight || "0"),
        headerPaddingX: Number.parseFloat(headerStyle?.paddingLeft || "0"),
      };
    });

    expect(chrome.borderRadius).toBeGreaterThanOrEqual(14);
    expect(chrome.minHeight).toBeLessThanOrEqual(160);
    expect(chrome.headerPaddingX).toBeLessThanOrEqual(16);
  });
});
