import { expect, test, type Page } from "@playwright/test";

const E2E_GATE = process.env.AUGUR_E2E_OLLAMA === "1";
const DASHBOARD_URL =
  process.env.AUGUR_DASHBOARD_URL?.replace(/\/$/, "") ??
  "http://localhost:3000";

type AirplaneStatus = {
  airplane_mode?: {
    enabled?: boolean;
  };
  ollama?: {
    ready?: boolean;
    has_configured_model?: boolean;
    configured_model?: string;
  };
};

async function readAirplaneStatus(page: Page) {
  const response = await page.request.post(`${DASHBOARD_URL}/api/mcp/tool`, {
    data: {
      tool: "get-local-backend-status",
      args: {},
    },
  });
  expect(response.ok()).toBe(true);

  const body = await response.json();
  return body as AirplaneStatus;
}

async function setAirplaneMode(
  page: Page,
  action: "on" | "off",
) {
  const response = await page.request.post(`${DASHBOARD_URL}/api/airplane`, {
    data: { action },
  });
  expect(response.ok()).toBe(true);
}

async function openDashboardWithAirplaneOff(page: Page) {
  await setAirplaneMode(page, "off");
  await page.goto(DASHBOARD_URL, { waitUntil: "domcontentloaded" });
  await expect(
    page.getByRole("button", { name: /airplane mode is off/i }),
  ).toBeVisible({ timeout: 15_000 });
}

async function toggleAirplaneOn(page: Page) {
  const pill = page.getByRole("button", { name: /airplane mode is off/i });
  await pill.click();
  await expect(
    page.getByRole("button", { name: /airplane mode is on/i }),
  ).toBeVisible({ timeout: 15_000 });
}

async function openChat(page: Page) {
  await page.getByRole("button", { name: /^open chat$/i }).click();
  await expect(
    page.getByRole("button", { name: /start cli process/i }),
  ).toBeVisible({ timeout: 15_000 });
}

test.describe("airplane mode end-to-end", () => {
  test.skip(
    !E2E_GATE,
    "Set AUGUR_E2E_OLLAMA=1 to run (requires local Ollama setup)",
  );

  test.afterEach(async ({ page }) => {
    await setAirplaneMode(page, "off").catch(() => {
      // Best-effort cleanup; the test assertions above own failure reporting.
    });
  });

  test("happy path toggles on and shows the offline route sheet", async ({ page }) => {
    const status = await readAirplaneStatus(page);
    const localReady =
      status.ollama?.ready === true &&
      status.ollama?.has_configured_model === true;

    test.skip(!localReady, "Local Ollama backend is not ready for happy path");

    await openDashboardWithAirplaneOff(page);
    await toggleAirplaneOn(page);

    await expect(
      page.getByRole("button", { name: /airplane mode is on/i }),
    ).toContainText(/airplane\s+(?!off\b)(local|setup needed|[\w./:-]+)/i);

    await openChat(page);
    const routeButton = page.getByRole("button", {
      name: /use cloud for chat routing/i,
    });
    await expect(routeButton).toBeVisible({ timeout: 15_000 });
    await routeButton.click();
    await expect(page.getByRole("dialog")).toContainText(
      /preference: offline/i,
    );
  });

  test("setup-needed path surfaces setup guidance when local backend is not ready", async ({
    page,
  }) => {
    const status = await readAirplaneStatus(page);
    const localReady =
      status.ollama?.ready === true &&
      status.ollama?.has_configured_model === true;

    test.skip(localReady, "Local Ollama backend is ready; setup path not applicable");

    await openDashboardWithAirplaneOff(page);
    await openChat(page);
    const routeButton = page.getByRole("button", {
      name: /use offline for chat routing/i,
    });
    await expect(routeButton).toBeVisible({ timeout: 15_000 });
    await routeButton.click();

    const routeDialog = page.getByRole("dialog");
    await expect(routeDialog).toContainText(
      /local backend setup is required before chats can use offline routing/i,
    );
    await expect(
      routeDialog.getByRole("button", { name: /switch for new chats/i }),
    ).toBeHidden();
    await expect(
      routeDialog.getByRole("link", { name: /open settings/i }),
    ).toHaveAttribute("href", "/settings/ai");
    await page.keyboard.press("Escape");
    await expect(routeDialog).toBeHidden();
  });
});
