import { test, expect } from "@playwright/test";

test.describe("Hub overview network wiring", () => {
  test("life/apple resolves canonical hub view and telemetry endpoints", async ({
    page,
  }) => {
    const responses = new Map<string, number>();

    page.on("response", (response) => {
      const url = response.url();
      if (
        url.includes("/api/views/hub-life-overview") ||
        url.includes("/api/usage/track") ||
        url.includes("/api/telemetry/performance")
      ) {
        responses.set(url, response.status());
      }
    });

    await page.goto("/life/apple", { waitUntil: "domcontentloaded" });
    await page.getByText("Apple Overview").first().waitFor({ state: "visible" });
    await page.waitForTimeout(4000);

    const viewStatus = [...responses.entries()].find(([url]) =>
      url.includes("/api/views/hub-life-overview"),
    )?.[1];
    const usageStatus = [...responses.entries()].find(([url]) =>
      url.includes("/api/usage/track"),
    )?.[1];
    const telemetryStatus = [...responses.entries()].find(([url]) =>
      url.includes("/api/telemetry/performance"),
    )?.[1];

    expect(viewStatus).toBe(200);
    expect(usageStatus).toBe(200);
    expect(telemetryStatus).toBe(200);
  });
});
