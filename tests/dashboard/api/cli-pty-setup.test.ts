/** @jest-environment node */

import path from "path";
import { resolvePtySpawnHelper } from "@/app/api/cli/pty-setup";

describe("resolvePtySpawnHelper", () => {
  it("does not require a spawn-helper binary on Windows", () => {
    const dashboardCwd = path.join(path.parse(process.cwd()).root, "no-such-dashboard");
    const fakeResolve = () => {
      throw new Error("node-pty resolution should not be needed on Windows");
    };

    const result = resolvePtySpawnHelper(fakeResolve, dashboardCwd, {
      platform: "win32",
      arch: "x64",
    });

    expect(result.exists).toBe(true);
    expect(result.required).toBe(false);
    expect(result.path).toBe("not-required-on-win32");
  });

  it("ignores Turbopack pseudo-paths and falls back to a real package path", () => {
    const repoRoot = path.resolve(__dirname, "../../..");
    const dashboardCwd = path.join(repoRoot, "apps/dashboard");
    const fakeResolve = (request: string) => {
      if (request === "node-pty/package.json") {
        return path.join(dashboardCwd, "node_modules/node-pty/package.json");
      }
      if (request === "node-pty") {
        return `${dashboardCwd}/[externals]/node-pty [external] (node-pty, cjs, [project]/node_modules/.pnpm/node-pty@1.1.0/prebuilds/darwin-arm64/spawn-helper`;
      }
      throw new Error(`unexpected request: ${request}`);
    };

    const result = resolvePtySpawnHelper(fakeResolve, dashboardCwd, {
      platform: "darwin",
      arch: "arm64",
    });

    expect(result.exists).toBe(true);
    expect(result.required).toBe(true);
    expect(result.path).toContain(path.join("node-pty", "prebuilds"));
    expect(result.path).toContain("spawn-helper");
    expect(result.path).not.toContain("[externals]");
  });
});
