import os from "os";
import path from "path";
import { defineConfig, devices } from "@playwright/test";

function resolveStateDir(): string {
  const stateEnv =
    process.env.AUGUR_STATE ||
    process.env.AUGUR_RUNTIME ||
    process.env.AUGUR_RUNTIME_DIR;

  if (stateEnv && stateEnv.trim()) {
    return path.resolve(stateEnv.trim().replace(/^~(?=$|\/)/, os.homedir()));
  }

  if (process.platform === "darwin") {
    return path.join(
      os.homedir(),
      "Library",
      "Application Support",
      "Augur",
      "state",
    );
  }
  if (process.platform === "win32") {
    return path.join(
      process.env.LOCALAPPDATA || path.join(os.homedir(), "AppData", "Local"),
      "Augur",
      "state",
    );
  }

  const xdgStateHome =
    process.env.XDG_STATE_HOME || path.join(os.homedir(), ".local", "state");
  return path.join(xdgStateHome, "augur");
}

export default defineConfig({
  testDir: "../../tests/dashboard/visual",
  outputDir: path.join(resolveStateDir(), "visual-regression"),
  snapshotDir: "../../tests/dashboard/visual/screenshots",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: "html",

  expect: {
    toHaveScreenshot: {
      maxDiffPixelRatio: 0.002, // 0.2% threshold
    },
  },

  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },

  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1280, height: 720 },
      },
    },
  ],

  webServer: {
    command: "npm run dev",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
    timeout: 120 * 1000,
  },
});
