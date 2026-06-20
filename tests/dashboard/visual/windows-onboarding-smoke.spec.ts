import { expect, test } from "@playwright/test";

test("dashboard reaches interactive state for Windows onboarding", async ({ page }) => {
  const pageErrors: string[] = [];
  const consoleErrors: string[] = [];

  page.on("pageerror", (error) => {
    const detail = error.stack || error.message;
    // Next dev instrumentation can emit a Performance.measure timestamp error
    // even when the application remains interactive; keep app errors strict.
    if (
      detail.includes("Failed to execute 'measure' on 'Performance'") &&
      detail.includes("cannot have a negative time stamp")
    ) {
      return;
    }
    pageErrors.push(detail);
  });
  page.on("console", (message) => {
    if (message.type() === "error") {
      consoleErrors.push(message.text());
    }
  });

  await page.addInitScript(() => {
    window.localStorage.setItem("augur-welcome-dismissed", "true");
  });

  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.waitForLoadState("networkidle", { timeout: 15000 }).catch(() => {
    // Some MCP calls can keep the network busy; the assertions below are the
    // user-visible interactive contract.
  });

  await expect(page.locator("body")).toBeVisible();
  await expect(page.getByText(/Failed to load chunk/i)).toHaveCount(0);
  await expect(page.getByText(/Application error/i)).toHaveCount(0);
  await expect(page.locator("button, a, [role='button']").first()).toBeVisible({
    timeout: 15000,
  });
  expect(pageErrors).toEqual([]);
  expect(consoleErrors).toEqual([]);
});
