import { test, expect } from "@playwright/test";

test("knowledge page hydrates built-in blocks without mismatch warnings", async ({
  page,
}) => {
  const errors: string[] = [];

  page.on("console", (msg) => {
    if (msg.type() === "error") {
      errors.push(msg.text());
    }
  });

  page.on("pageerror", (err) => {
    errors.push(`PAGEERROR: ${err.message}`);
  });

  await page.goto("/workspace/memory", { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(6000);

  await expect(
    page.getByRole("heading", { name: "Knowledge Actions", exact: true }),
  ).toBeVisible();

  expect(
    errors.some((message) => message.includes("hydrated but some attributes")),
  ).toBe(false);
});
