/**
 * @jest-environment node
 */

import path from "path";

const VAULT_CONFIG_DIR = path.join("/vault", "config");
const MACHINE_CONFIG_DIR = path.join("/vault", "_augur", "config");
const CONFIG_AI_PATH = path.join("/vault", "config", "ai", "cli_agents.yaml");
const MACHINE_AI_PATH = path.join("/vault", "_augur", "config", "ai", "cli_agents.yaml");
const LEGACY_AI_PATH = path.join("/vault", "ai", "cli_agents.yaml");
const PREFERENCES_PATH = path.join("/state", "preferences.yaml");
const ORIGINAL_ENV = { ...process.env };
const ORIGINAL_PLATFORM = Object.getOwnPropertyDescriptor(process, "platform");

function mockFsWithExistingPath(existingPath: string) {
  const existsSync = jest.fn((candidate: string) => candidate === existingPath);
  const readFileSync = jest.fn((candidate: string) => {
    if (candidate !== existingPath) {
      throw new Error(`unexpected read: ${candidate}`);
    }
    return [
      "agents:",
      "  codex:",
      "    label: Codex",
      "    cmd:",
      "      - codex",
      "      - exec",
      "    category: local",
      "",
    ].join("\n");
  });
  const fsMock = {
    existsSync,
    readFileSync,
    accessSync: jest.fn(),
    constants: { X_OK: 1 },
    mkdirSync: jest.fn(),
    writeFileSync: jest.fn(),
  };

  jest.doMock("fs", () => ({
    __esModule: true,
    default: fsMock,
    ...fsMock,
  }));

  return { existsSync, readFileSync };
}

function mockFsWithConfigAndPrefs(
  agentsYaml: string,
  preferencesYaml: string | null = null,
) {
  const existsSync = jest.fn((candidate: string) =>
    candidate === CONFIG_AI_PATH ||
    (preferencesYaml !== null && candidate === PREFERENCES_PATH)
  );
  const readFileSync = jest.fn((candidate: string) => {
    if (candidate === CONFIG_AI_PATH) {
      return agentsYaml;
    }
    if (candidate === PREFERENCES_PATH && preferencesYaml !== null) {
      return preferencesYaml;
    }
    throw new Error(`unexpected read: ${candidate}`);
  });
  const fsMock = {
    existsSync,
    readFileSync,
    accessSync: jest.fn(),
    constants: { X_OK: 1 },
    mkdirSync: jest.fn(),
    writeFileSync: jest.fn(),
  };

  jest.doMock("fs", () => ({
    __esModule: true,
    default: fsMock,
    ...fsMock,
  }));

  return { existsSync, readFileSync };
}

async function loadCliConfig(
  existingPath: string,
  vaultConfigDir: string = VAULT_CONFIG_DIR,
) {
  jest.resetModules();
  jest.doMock("@/lib/paths", () => ({
    AUGUR_STATE_DIR: "/state",
    AUGUR_VAULT_DIR: "/vault",
    AUGUR_VAULT_CONFIG_DIR: vaultConfigDir,
  }));
  return {
    fsCalls: mockFsWithExistingPath(existingPath),
    module: await import("@/app/api/cli/cli-config"),
  };
}

async function loadCliConfigWithPrefs(
  agentsYaml: string,
  preferencesYaml: string | null = null,
) {
  jest.resetModules();
  jest.doMock("@/lib/paths", () => ({
    AUGUR_STATE_DIR: "/state",
    AUGUR_VAULT_DIR: "/vault",
    AUGUR_VAULT_CONFIG_DIR: VAULT_CONFIG_DIR,
  }));
  return {
    fsCalls: mockFsWithConfigAndPrefs(agentsYaml, preferencesYaml),
    module: await import("@/app/api/cli/cli-config"),
  };
}

function restoreProcessGlobals() {
  process.env = { ...ORIGINAL_ENV };
  if (ORIGINAL_PLATFORM) {
    Object.defineProperty(process, "platform", ORIGINAL_PLATFORM);
  }
  jest.dontMock("@/lib/paths");
  jest.dontMock("fs");
  jest.resetModules();
}

describe("getCliAgentsConfig", () => {
  afterEach(restoreProcessGlobals);

  it("reads cli_agents.yaml from the vault config/ai directory", async () => {
    const { fsCalls, module } = await loadCliConfig(CONFIG_AI_PATH);

    const agents = module.getCliAgentsConfig();

    expect(fsCalls.existsSync).toHaveBeenCalledWith(CONFIG_AI_PATH);
    expect(fsCalls.readFileSync).toHaveBeenCalledWith(CONFIG_AI_PATH, "utf-8");
    expect(agents.codex).toEqual({
      label: "Codex",
      cmd: ["codex", "exec"],
      category: "local",
    });
    expect(agents.ollama.cmd).toEqual(["ollama", "run", "qwen3.5:9b"]);
  });

  it("falls back to the legacy vault ai directory", async () => {
    const { fsCalls, module } = await loadCliConfig(LEGACY_AI_PATH);

    const agents = module.getCliAgentsConfig();

    expect(fsCalls.existsSync).toHaveBeenCalledWith(CONFIG_AI_PATH);
    expect(fsCalls.existsSync).toHaveBeenCalledWith(LEGACY_AI_PATH);
    expect(fsCalls.readFileSync).toHaveBeenCalledWith(LEGACY_AI_PATH, "utf-8");
    expect(agents.codex.cmd).toEqual(["codex", "exec"]);
  });

  it("resolves cli_agents.yaml under the _augur domains-layout config dir", async () => {
    // Regression for the 'Unknown CLI' break: the vault reorg moved machine
    // config under _augur/, so AUGUR_VAULT_CONFIG_DIR points there. The file
    // exists ONLY at _augur/config/ai/ — the legacy flat paths must not be
    // required for the chat to find a CLI.
    const { fsCalls, module } = await loadCliConfig(
      MACHINE_AI_PATH,
      MACHINE_CONFIG_DIR,
    );

    const agents = module.getCliAgentsConfig();

    expect(fsCalls.existsSync).toHaveBeenCalledWith(MACHINE_AI_PATH);
    expect(fsCalls.readFileSync).toHaveBeenCalledWith(MACHINE_AI_PATH, "utf-8");
    expect(agents.codex.cmd).toEqual(["codex", "exec"]);
    expect(module.isValidCli("codex")).toBe(true);
  });

  it("finds _augur config even when AUGUR_VAULT_CONFIG_DIR cached the legacy path", async () => {
    // Boot-race regression: AUGUR_VAULT_CONFIG_DIR is resolved ONCE at module
    // load via existsSync. If the server booted before _augur/config existed
    // (e.g. mid vault-sync during `aug dev build`), it cached the LEGACY path
    // and every CLI chat failed with "Unknown CLI". The explicit _augur
    // candidate must still resolve the file regardless of that cached choice.
    const { fsCalls, module } = await loadCliConfig(MACHINE_AI_PATH, VAULT_CONFIG_DIR);

    const agents = module.getCliAgentsConfig();

    expect(fsCalls.readFileSync).toHaveBeenCalledWith(MACHINE_AI_PATH, "utf-8");
    expect(agents.codex.cmd).toEqual(["codex", "exec"]);
    expect(module.isValidCli("codex")).toBe(true);
  });

  it("adds a direct Ollama CLI backed by the configured local model", async () => {
    const { module } = await loadCliConfigWithPrefs(
      [
        "agents:",
        "  claude:",
        "    label: Claude",
        "    cmd: [\"claude\"]",
        "    category: remote",
      ].join("\n"),
      [
        "local_backends:",
        "  ollama:",
        "    model: augur-codex-llama3.2:3b-4k",
      ].join("\n"),
    );

    const agents = module.getCliAgentsConfig();

    expect(agents.ollama).toEqual({
      label: "Ollama",
      cmd: ["ollama", "run", "augur-codex-llama3.2:3b-4k"],
      cwd: ".",
      category: "local",
      group: "ollama",
    });
    expect(module.isValidCli("ollama")).toBe(true);
  });
});

describe("default CLI selection", () => {
  afterEach(restoreProcessGlobals);

  it("uses client_routing.default_client from runtime preferences", async () => {
    const { module } = await loadCliConfigWithPrefs(
      [
        "agents:",
        "  claude:",
        "    cmd: [\"claude\"]",
        "  codex:",
        "    cmd: [\"codex\"]",
      ].join("\n"),
      [
        "client_routing:",
        "  default_client: codex",
      ].join("\n"),
    );

    expect(module.resolveDefaultCliId()).toBe("codex");
  });

  it("maps agent bubbles to the configured default CLI", async () => {
    const { module } = await loadCliConfigWithPrefs(
      [
        "agents:",
        "  claude:",
        "    cmd: [\"claude\"]",
        "  codex:",
        "    cmd: [\"codex\"]",
      ].join("\n"),
      [
        "client_routing:",
        "  default_client: codex",
      ].join("\n"),
    );

    expect(module.resolveConfigKey("agent-bubble-123")).toBe("codex");
  });

  it("falls back to cli_agents.yaml order when no default client is configured", async () => {
    const { module } = await loadCliConfigWithPrefs(
      [
        "agents:",
        "  codex:",
        "    cmd: [\"codex\"]",
        "  claude:",
        "    cmd: [\"claude\"]",
      ].join("\n"),
    );

    expect(module.resolveDefaultCliId()).toBe("codex");
  });

  it("validates CLI IDs from cli_agents.yaml instead of a hardcoded list", async () => {
    const { module } = await loadCliConfigWithPrefs(
      [
        "agents:",
        "  new-agent:",
        "    cmd: [\"new-agent\"]",
      ].join("\n"),
    );

    expect(module.isValidCli("new-agent")).toBe(true);
  });

  it("allows Ollama to be the configured default even when cli_agents.yaml does not define it", async () => {
    const { module } = await loadCliConfigWithPrefs(
      [
        "agents:",
        "  claude:",
        "    cmd: [\"claude\"]",
      ].join("\n"),
      [
        "client_routing:",
        "  default_client: ollama",
        "local_backends:",
        "  ollama:",
        "    model: augur-codex-llama3.2:3b-4k",
      ].join("\n"),
    );

    expect(module.resolveDefaultCliId()).toBe("ollama");
  });
});

describe("Windows CLI path resolution", () => {
  afterEach(restoreProcessGlobals);

  it("uses USERPROFILE for the default repo root on Windows", async () => {
    jest.resetModules();
    Object.defineProperty(process, "platform", { value: "win32" });
    process.env.USERPROFILE = "C:\\Users\\tester";
    delete process.env.HOME;
    delete process.env.AUGUR_ROOT;
    jest.doMock("@/lib/paths", () => ({
      AUGUR_STATE_DIR: "C:\\Users\\tester\\AppData\\Local\\Augur\\state",
      AUGUR_VAULT_DIR: "C:\\Users\\tester\\Vault\\Augur",
      AUGUR_VAULT_CONFIG_DIR: path.join("C:\\Users\\tester\\Vault\\Augur", "config"),
    }));
    mockFsWithExistingPath(CONFIG_AI_PATH);

    const module = await import("@/app/api/cli/cli-config");

    expect(module.AUGUR_ROOT).toBe(path.join("C:\\Users\\tester", "Projects", "Augur"));
  });

  it("resolves Windows PATHEXT shims such as codex.cmd", async () => {
    jest.resetModules();
    Object.defineProperty(process, "platform", { value: "win32" });
    process.env.USERPROFILE = "C:\\Users\\tester";
    process.env.APPDATA = "C:\\Users\\tester\\AppData\\Roaming";
    process.env.LOCALAPPDATA = "C:\\Users\\tester\\AppData\\Local";
    process.env.PATHEXT = ".CMD;.EXE";
    process.env.PATH = "";
    const codexShim = path.join("C:\\Users\\tester\\AppData\\Roaming", "npm", "codex.cmd");
    const fsMock = {
      existsSync: jest.fn(),
      readFileSync: jest.fn(),
      accessSync: jest.fn((candidate: string) => {
        if (candidate !== codexShim) {
          throw new Error(`not found: ${candidate}`);
        }
      }),
      constants: { X_OK: 1 },
      mkdirSync: jest.fn(),
      writeFileSync: jest.fn(),
    };
    jest.doMock("fs", () => ({
      __esModule: true,
      default: fsMock,
      ...fsMock,
    }));
    jest.doMock("@/lib/paths", () => ({
      AUGUR_STATE_DIR: "C:\\Users\\tester\\AppData\\Local\\Augur\\state",
      AUGUR_VAULT_DIR: "C:\\Users\\tester\\Vault\\Augur",
      AUGUR_VAULT_CONFIG_DIR: path.join("C:\\Users\\tester\\Vault\\Augur", "config"),
    }));

    const module = await import("@/app/api/cli/cli-config");

    expect(module.resolveCommand("codex")).toBe(codexShim);
  });

  it("prefers executable Windows PATHEXT shims over extensionless npm shims", async () => {
    jest.resetModules();
    Object.defineProperty(process, "platform", { value: "win32" });
    process.env.USERPROFILE = "C:\\Users\\tester";
    process.env.APPDATA = "C:\\Users\\tester\\AppData\\Roaming";
    process.env.LOCALAPPDATA = "C:\\Users\\tester\\AppData\\Local";
    process.env.PATHEXT = ".CMD;.EXE";
    process.env.PATH = "";
    const npmDir = path.join("C:\\Users\\tester\\AppData\\Roaming", "npm");
    const extensionlessShim = path.join(npmDir, "codex");
    const cmdShim = path.join(npmDir, "codex.cmd");
    const fsMock = {
      existsSync: jest.fn(),
      readFileSync: jest.fn(),
      accessSync: jest.fn((candidate: string) => {
        if (candidate !== extensionlessShim && candidate !== cmdShim) {
          throw new Error(`not found: ${candidate}`);
        }
      }),
      constants: { X_OK: 1 },
      mkdirSync: jest.fn(),
      writeFileSync: jest.fn(),
    };
    jest.doMock("fs", () => ({
      __esModule: true,
      default: fsMock,
      ...fsMock,
    }));
    jest.doMock("@/lib/paths", () => ({
      AUGUR_STATE_DIR: "C:\\Users\\tester\\AppData\\Local\\Augur\\state",
      AUGUR_VAULT_DIR: "C:\\Users\\tester\\Vault\\Augur",
      AUGUR_VAULT_CONFIG_DIR: path.join("C:\\Users\\tester\\Vault\\Augur", "config"),
    }));

    const module = await import("@/app/api/cli/cli-config");

    expect(module.resolveCommand("codex")).toBe(cmdShim);
  });
});
