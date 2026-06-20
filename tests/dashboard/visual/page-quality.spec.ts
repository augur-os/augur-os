import { expect, test } from "@playwright/test";

test.describe("Page quality", () => {
  test("knowledge page exposes real memory actions and data", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/workspace/memory", { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(7000);

    await expect(
      page.getByRole("heading", { name: "Session Memory", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Curate Memory" }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Memory Search", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Recent Decisions", exact: true }),
    ).toBeVisible();
  });

  test("retired health hub is no longer exposed as a live dashboard page", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    const response = await page.goto("/life/health", { waitUntil: "domcontentloaded" });

    expect(response?.status()).toBe(404);
    await expect(page.getByText(/Page Not Available/i)).toBeVisible();
    await expect(
      page.locator("#main-content").getByRole("link", { name: /^Browse$/i }),
    ).toBeVisible();
  });
});
