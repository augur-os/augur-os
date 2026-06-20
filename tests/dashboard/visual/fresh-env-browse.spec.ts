import { test, expect } from "@playwright/test";

// Fresh-env gate (M4): prove the dashboard actually MOUNTS on a clean install —
// not just that the server returns SSR HTML (rule 28). A chunk-load failure or
// an error boundary must fail this test.
test("Browse mounts to interactive state on a fresh install", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(msg.text());
  });
  page.on("pageerror", (err) => errors.push(String(err)));

  await page.goto("/browse", { waitUntil: "domcontentloaded" });

  // No chunk-load / error-boundary text rendered.
  const body = await page.locator("body").innerText();
  expect(body).not.toContain("Failed to load chunk");
  expect(body).not.toContain("Application error");
  expect(body).not.toContain("Something went wrong");

  // The client mounted: the Next app root has rendered children.
  const appRoot = page.locator("#__next, [data-nextjs-router], main").first();
  await expect(appRoot).toBeVisible({ timeout: 30_000 });

  // No fatal client console/page errors (chunk/runtime).
  const fatal = errors.filter((e) => /chunk|is not defined|Cannot read/i.test(e));
  expect(fatal, `fatal client errors:\n${fatal.join("\n")}`).toHaveLength(0);
});
