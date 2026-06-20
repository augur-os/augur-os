import os from "os";
import path from "path";
import { defineConfig, devices } from "@playwright/test";

// Fresh-env onboarding gate (M4): CI-only Playwright config.
// Deliberately has NO `webServer` block — the fresh-env-onboard.yml workflow
// backgrounds `aug dev build` and scripts/ci/fresh_env_verify.py polls it for
// readiness. Playwright must NOT manage the server lifecycle here, otherwise it
// would try to start its own dev server on :3000 (reuseExistingServer is false
// when CI=true) and collide with the workflow's server.

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
  testMatch: "fresh-env-browse.spec.ts",
  outputDir: path.join(resolveStateDir(), "fresh-env-verify"),
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: "list",

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

  // No webServer: the CI workflow owns the server lifecycle.
});
