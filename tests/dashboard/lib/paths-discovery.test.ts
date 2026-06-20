import fs from "fs";
import os from "os";
import path from "path";

describe("dashboard path discovery", () => {
  const originalCwd = process.cwd;
  const originalEnv = { ...process.env };
  const originalPlatform = Object.getOwnPropertyDescriptor(process, "platform");
  let tempRoot: string;

  beforeEach(() => {
    tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), "augur-paths-"));
    jest.resetModules();
  });

  afterEach(() => {
    process.cwd = originalCwd;
    process.env = { ...originalEnv };
    if (originalPlatform) {
      Object.defineProperty(process, "platform", originalPlatform);
    }
    jest.dontMock("os");
    jest.resetModules();
    fs.rmSync(tempRoot, { recursive: true, force: true });
  });

  function loadPathsWithHome(home: string, repoRoot: string) {
    const cwd = path.join(repoRoot, "apps", "dashboard");
    fs.mkdirSync(cwd, { recursive: true });
    process.cwd = () => cwd;
    process.env.PWD = cwd;
    process.env.INIT_CWD = cwd;
    process.env.AUGUR_STATE = path.join(tempRoot, "state");
    delete process.env.AUGUR_ROOT;
    delete process.env.AUGUR_VAULT;
    delete process.env.AUGUR_DOCUMENTS;

    jest.doMock("os", () => ({
      ...jest.requireActual("os"),
      homedir: () => home,
    }));

    return require("@/lib/paths") as typeof import("@/lib/paths");
  }

  it("discovers moved vault and documents roots when project.yaml paths are stale", () => {
    const home = path.join(tempRoot, "home");
    const repoRoot = path.join(tempRoot, "repo");
    const vault = path.join(home, "Projects", "Au-vault");
    const documents = path.join(home, "Projects", "Au-docs");

    fs.mkdirSync(path.join(repoRoot, "config", "system"), { recursive: true });
    fs.writeFileSync(
      path.join(repoRoot, "project.yaml"),
      [
        "name: Augur",
        "paths:",
        "  vault: ~/Vault/Augur",
        "  documents: ~/Documents/Augur",
        "",
      ].join("\n"),
    );
    fs.mkdirSync(vault, { recursive: true });
    fs.writeFileSync(path.join(vault, ".augur-vault"), "project: Augur\n");
    fs.mkdirSync(documents, { recursive: true });
    fs.writeFileSync(path.join(documents, ".augur-docs"), "project: Augur\n");

    const paths = loadPathsWithHome(home, repoRoot);

    expect(paths.AUGUR_VAULT_DIR).toBe(vault);
    expect(paths.AUGUR_DOCUMENTS_DIR).toBe(documents);
  });

  it("uses LocalAppData for Windows runtime, logs, and cache defaults", () => {
    Object.defineProperty(process, "platform", { value: "win32" });
    const home = path.join(tempRoot, "home");
    const repoRoot = path.join(tempRoot, "repo");
    const localAppData = path.join(home, "AppData", "Local");
    const roamingAppData = path.join(home, "AppData", "Roaming");
    const cwd = path.join(repoRoot, "apps", "dashboard");

    fs.mkdirSync(path.join(repoRoot, "config", "system"), { recursive: true });
    fs.mkdirSync(cwd, { recursive: true });
    process.cwd = () => cwd;
    process.env.PWD = cwd;
    process.env.INIT_CWD = cwd;
    process.env.LOCALAPPDATA = localAppData;
    process.env.APPDATA = roamingAppData;
    delete process.env.AUGUR_STATE;
    delete process.env.AUGUR_RUNTIME;
    delete process.env.AUGUR_RUNTIME_DIR;
    delete process.env.AUGUR_LOGS;
    delete process.env.AUGUR_CACHE_DIR;
    delete process.env.AUGUR_CACHE_PATH;
    delete process.env.AUGUR_ROOT;

    jest.doMock("os", () => ({
      ...jest.requireActual("os"),
      homedir: () => home,
    }));

    const paths = require("@/lib/paths") as typeof import("@/lib/paths");

    expect(paths.AUGUR_STATE_DIR).toBe(path.join(localAppData, "Augur", "state"));
    expect(paths.AUGUR_RUNTIME_DIR).toBe(path.join(localAppData, "Augur", "state"));
    expect(paths.AUGUR_LOGS_DIR).toBe(path.join(localAppData, "Augur", "logs"));
    expect(paths.AUGUR_CACHE_DIR).toBe(path.join(localAppData, "Augur", "cache"));
  });
});
