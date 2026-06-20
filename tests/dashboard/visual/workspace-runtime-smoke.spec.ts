import { expect, test } from "@playwright/test";

const WORKSPACE_ROUTES = [
  "/workspace",
  "/workspace/memory",
  "/workspace/daily-logs",
  "/workspace/profile",
  "/workspace/inbox",
  "/workspace/insights",
];

test.describe("Workspace runtime smoke", () => {
  test.describe.configure({ mode: "serial" });

  for (const route of WORKSPACE_ROUTES) {
    test(`${route} hydrates without stuck loading placeholders`, async ({
      page,
    }) => {
      const pageErrors: string[] = [];
      const consoleErrors: string[] = [];

      page.on("pageerror", (error) => {
        pageErrors.push(error.stack || error.message);
      });
      page.on("console", (message) => {
        if (message.type() === "error") {
          consoleErrors.push(message.text());
        }
      });

      await page.setViewportSize({ width: 1440, height: 1000 });
      await page.goto(route, { waitUntil: "domcontentloaded" });
      await page.waitForLoadState("networkidle", { timeout: 15_000 }).catch(
        () => {
          // Some MCP calls can keep the network busy; the assertions below are
          // the real user-visible contract.
        },
      );

      const body = page.locator("body");
      await expect(body).toContainText("Workspace", { timeout: 15_000 });
      await expect(page.getByText("MCP server is down")).toHaveCount(0);
      await expect(page.getByText(/Failed to load chunk/i)).toHaveCount(0);
      await expect(page.getByText(/Application error/i)).toHaveCount(0);
      await expect(page.getByText(/^Loading .*\.\.\.$/)).toHaveCount(0, {
        timeout: 15_000,
      });
      expect(pageErrors).toEqual([]);
      expect(consoleErrors).toEqual([]);
    });
  }
});
