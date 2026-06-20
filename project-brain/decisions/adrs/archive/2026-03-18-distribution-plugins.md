# Distribution Plugin Architecture (ADR-437) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Augur discoverable and installable from Obsidian and VS Code marketplaces via thin platform-native plugins that detect/install/configure Augur, show connection health, and link to the dashboard.

**Architecture:** Each platform plugin implements the same 5-capability contract (detect, install, configure, status, link). Plugins call `scripts/install.sh --from <platform>` for installation and share a TypeScript health check library at `dist/platform-plugins/lib/health.ts`. Plugins are intentionally thin distribution wrappers -- they do NOT execute skills, run AI, or duplicate Augur functionality.

**Tech Stack:** Bash (installer), TypeScript (Obsidian plugin API, VS Code extension API, shared health lib), Node.js (build tooling)

**Spec:** `get_vault_dir()/dev/adrs/ADR-437-distribution-plugin-architecture.md`

---

## File Structure

### New files

| File | Responsibility |
|---|---|
| `dist/platform-plugins/lib/package.json` | Package manifest for shared lib (vitest dev dep) |
| `dist/platform-plugins/lib/tsconfig.json` | TypeScript config for shared lib |
| `dist/platform-plugins/lib/health.ts` | Shared health check library: detect install dir, ping MCP, ping dashboard, read last sync |
| `dist/platform-plugins/lib/health.test.ts` | Unit tests for health check library |
| `dist/platform-plugins/obsidian/manifest.json` | Obsidian community plugin manifest |
| `dist/platform-plugins/obsidian/src/main.ts` | Obsidian plugin: detect, install, configure, status, link |
| `dist/platform-plugins/obsidian/styles.css` | Status panel styling |
| `dist/platform-plugins/vscode/package.json` | VS Code extension manifest |
| `dist/platform-plugins/vscode/src/extension.ts` | VS Code extension: detect, install, configure, status, link (sidebar webview) |
| `dist/platform-plugins/vscode/tsconfig.json` | TypeScript config for VS Code extension |
| `dist/platform-plugins/README.md` | Platform plugin development guide |

### Modified files

| File | Change |
|---|---|
| `scripts/install.sh` (after line 25) | Add `--from <platform>` flag parsing, install-source.json write, auto-configure MCP |

---

## Task 1: install.sh --from Flag + Install Source Tracking

**Files:**
- Modify: `scripts/install.sh`
- Verify: `~/Library/Application Support/Augur/state/install-source.json` written after install

- [ ] **Step 1: Add --from flag parsing to install.sh**

Add argument parsing at the top of `main()` and a `record_install_source()` helper. Insert after the `RUN_TESTS` config line (line 25):

```bash
# In the CONFIGURATION section, after line 25:
INSTALL_FROM=""  # Set via --from <platform>
```

Add argument parsing at the start of `main()`, before `print_header`:

```bash
main() {
    # ─────────────────────────────────────────────────────────────────────────
    # Parse arguments
    # ─────────────────────────────────────────────────────────────────────────
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --from)
                INSTALL_FROM="$2"
                shift 2
                ;;
            --from=*)
                INSTALL_FROM="${1#*=}"
                shift
                ;;
            *)
                print_error "Unknown argument: $1"
                echo "Usage: install.sh [--from <platform>]"
                echo "  --from    Source platform (obsidian, vscode, cursor, claude-code)"
                exit 1
                ;;
        esac
    done

    print_header "Augur Installer"
```

- [ ] **Step 2: Add record_install_source helper function**

Add to the HELPERS section, after `version_ge()`:

```bash
record_install_source() {
    # Record which platform triggered the install
    local platform="$1"
    if [ -z "$platform" ]; then
        return
    fi

    local state_dir="$HOME/Library/Application Support/Augur/state"
    mkdir -p "$state_dir"

    local source_file="$state_dir/install-source.json"
    local timestamp
    timestamp="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

    cat > "$source_file" <<EOJSON
{
  "platform": "$platform",
  "installed_at": "$timestamp",
  "install_dir": "$INSTALL_DIR",
  "installer_version": "$(git -C \"$INSTALL_DIR\" describe --tags 2>/dev/null || echo dev)"
}
EOJSON

    print_success "Install source recorded: $platform"
}
```

- [ ] **Step 3: Add post-install hooks for --from flag**

Add at the end of `main()`, right before `print_success "Environment ready."` (before line 350):

```bash
    # ─────────────────────────────────────────────────────────────────────────
    # Record install source and auto-configure MCP (--from flag)
    # ─────────────────────────────────────────────────────────────────────────

    if [ -n "$INSTALL_FROM" ]; then
        record_install_source "$INSTALL_FROM"

        # Auto-configure MCP for the originating platform
        CONFIGURE_SCRIPT="${INSTALL_DIR}/scripts/configure_mcp.py"
        if [ -f "$CONFIGURE_SCRIPT" ]; then
            print_step "Auto-configuring MCP for ${INSTALL_FROM}..."
            uv run python "$CONFIGURE_SCRIPT" --apply --auto || \
                print_warning "MCP auto-configuration failed — run manually: python scripts/configure_mcp.py --apply --auto"
        fi

        # If --from obsidian, also scaffold the vault
        if [ "$INSTALL_FROM" = "obsidian" ]; then
            print_step "Scaffolding Obsidian vault..."
            # TODO_BUG: obsidian-scaffold is an MCP tool (ADR-436), not a shell script.
            # For now, scaffold .obsidian/ inline. Replace with MCP tool call when available.
            OBSIDIAN_SCAFFOLD="${INSTALL_DIR}/.claude/skills/obsidian/scripts/mcp/__init__.py"
            if [ -f "$OBSIDIAN_SCAFFOLD" ]; then
                bash "$OBSIDIAN_SCAFFOLD" || print_warning "Vault scaffolding failed — run obsidian-scaffold MCP tool manually"
            else
                print_info "Obsidian vault scaffolding available via obsidian-scaffold MCP tool"
            fi
        fi
    fi
```

- [ ] **Step 4: Test the --from flag manually**

Run:
```bash
cd "$(git rev-parse --show-toplevel)" && bash scripts/install.sh --from test-platform 2>&1 | head -5
```
Expected: Installer starts, shows "Augur Installer" header. (Ctrl-C to cancel -- we just verify arg parsing works.)

Verify unknown arg rejection:
```bash
cd "$(git rev-parse --show-toplevel)" && bash scripts/install.sh --badarg 2>&1
```
Expected: "Unknown argument: --badarg" error message.

- [ ] **Step 5: Commit**

```bash
git add scripts/install.sh
git commit -m "feat: add --from flag to install.sh for platform tracking (ADR-437)"
```

---

## Task 2: Shared Health Check Library

**Files:**
- Create: `dist/platform-plugins/lib/package.json`
- Create: `dist/platform-plugins/lib/tsconfig.json`
- Create: `dist/platform-plugins/lib/health.ts`
- Create: `dist/platform-plugins/lib/health.test.ts`

- [ ] **Step 1: Create directory structure and package.json**

```bash
mkdir -p dist/platform-plugins/lib
```

```json
// dist/platform-plugins/lib/package.json
{
  "name": "@augur/platform-health",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "main": "dist/health.js",
  "scripts": {
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "devDependencies": {
    "vitest": "^3.0.0",
    "typescript": "^5.7.0"
  }
}
```

```json
// dist/platform-plugins/lib/tsconfig.json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ES2022",
    "moduleResolution": "bundler",
    "lib": ["ES2022"],
    "strict": true,
    "esModuleInterop": true,
    "declaration": true,
    "outDir": "dist",
    "rootDir": "."
  },
  "include": ["*.ts"],
  "exclude": ["*.test.ts", "dist"]
}
```

- [ ] **Step 2: Write failing tests for health check**

```typescript
// dist/platform-plugins/lib/health.test.ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import { checkHealth, type HealthStatus } from "./health";

// Mock fetch globally
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

// Mock fs access
vi.mock("fs", () => ({
  existsSync: vi.fn(),
  readFileSync: vi.fn(),
}));

import { existsSync, readFileSync } from "fs";
const mockExistsSync = vi.mocked(existsSync);
const mockReadFileSync = vi.mocked(readFileSync);

beforeEach(() => {
  vi.clearAllMocks();
});

describe("checkHealth", () => {
  it("returns all-healthy when everything is running", async () => {
    mockExistsSync.mockReturnValue(true);
    mockReadFileSync.mockReturnValue(
      JSON.stringify({ last_sync: "2026-03-18T12:00:00Z" })
    );
    mockFetch.mockResolvedValue({ ok: true });

    const result = await checkHealth();

    expect(result.installed).toBe(true);
    expect(result.mcp_healthy).toBe(true);
    expect(result.dashboard_running).toBe(true);
    expect(result.last_sync).toBe("2026-03-18T12:00:00Z");
  });

  it("returns installed=false when install dir missing", async () => {
    mockExistsSync.mockReturnValue(false);
    mockFetch.mockRejectedValue(new Error("ECONNREFUSED"));

    const result = await checkHealth();

    expect(result.installed).toBe(false);
    expect(result.mcp_healthy).toBe(false);
    expect(result.dashboard_running).toBe(false);
    expect(result.last_sync).toBeNull();
  });

  it("returns mcp_healthy=false when MCP server unreachable", async () => {
    mockExistsSync.mockReturnValue(true);
    mockReadFileSync.mockReturnValue("{}");
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("3001")) return Promise.reject(new Error("ECONNREFUSED"));
      return Promise.resolve({ ok: true });
    });

    const result = await checkHealth();

    expect(result.installed).toBe(true);
    expect(result.mcp_healthy).toBe(false);
    expect(result.dashboard_running).toBe(true);
  });

  it("returns dashboard_running=false when dashboard unreachable", async () => {
    mockExistsSync.mockReturnValue(true);
    mockReadFileSync.mockReturnValue("{}");
    mockFetch.mockImplementation((url: string) => {
      if (url.includes("3000")) return Promise.reject(new Error("ECONNREFUSED"));
      return Promise.resolve({ ok: true });
    });

    const result = await checkHealth();

    expect(result.installed).toBe(true);
    expect(result.mcp_healthy).toBe(true);
    expect(result.dashboard_running).toBe(false);
  });

  it("returns last_sync=null when state file missing", async () => {
    mockExistsSync.mockImplementation((p: string) => {
      // Install dir exists but state file does not
      return !String(p).includes("state");
    });
    mockFetch.mockResolvedValue({ ok: true });

    const result = await checkHealth();

    expect(result.last_sync).toBeNull();
  });

  it("respects custom install dir via options", async () => {
    mockExistsSync.mockReturnValue(true);
    mockReadFileSync.mockReturnValue("{}");
    mockFetch.mockResolvedValue({ ok: true });

    const result = await checkHealth({ installDir: "/custom/augur" });

    expect(result.installed).toBe(true);
  });
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd ~/Projects/Augur/dist/platform-plugins/lib && npm install && npx vitest run`
Expected: FAIL -- module `./health` not found

- [ ] **Step 4: Implement health check library**

```typescript
// dist/platform-plugins/lib/health.ts
/**
 * Shared health check library for Augur platform plugins.
 *
 * Detects Augur installation, pings MCP server and dashboard,
 * reads last sync timestamp. Used by Obsidian and VS Code plugins.
 *
 * Protocol:
 *   1. Check install dir exists (~/Projects/augur or $AUGUR_DIR)
 *   2. Check MCP server reachable (localhost:3001)
 *   3. Check dashboard reachable (localhost:3000)
 *   4. Read last sync timestamp from state directory
 */

import { existsSync, readFileSync } from "fs";
import { join } from "path";
import { homedir } from "os";

export interface HealthStatus {
  installed: boolean;
  mcp_healthy: boolean;
  dashboard_running: boolean;
  last_sync: string | null;
  install_dir: string;
}

export interface HealthOptions {
  /** Override install directory (default: $AUGUR_DIR or ~/Projects/augur) */
  installDir?: string;
  /** MCP server port (default: 3001) */
  mcpPort?: number;
  /** Dashboard port (default: 3000) */
  dashboardPort?: number;
  /** Timeout in ms for HTTP pings (default: 3000) */
  timeout?: number;
}

/**
 * Check Augur system health.
 *
 * Returns a status object with installation, MCP, dashboard,
 * and sync state. All checks are non-throwing -- failures return
 * false/null for the relevant field.
 */
export async function checkHealth(
  options: HealthOptions = {}
): Promise<HealthStatus> {
  const installDir =
    options.installDir ??
    process.env.AUGUR_DIR ??
    join(homedir(), "Projects", "augur");
  const mcpPort = options.mcpPort ?? 3001;
  const dashboardPort = options.dashboardPort ?? 3000;
  const timeout = options.timeout ?? 3000;

  const installed = existsSync(installDir);

  const [mcp_healthy, dashboard_running] = await Promise.all([
    pingHttp(`http://localhost:${mcpPort}/health`, timeout),
    pingHttp(`http://localhost:${dashboardPort}`, timeout),
  ]);

  const last_sync = readLastSync();

  return {
    installed,
    mcp_healthy,
    dashboard_running,
    last_sync,
    install_dir: installDir,
  };
}

/**
 * Ping an HTTP endpoint. Returns true if response is ok.
 */
async function pingHttp(url: string, timeout: number): Promise<boolean> {
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);
    const response = await fetch(url, { signal: controller.signal });
    clearTimeout(timer);
    return response.ok;
  } catch {
    return false;
  }
}

/**
 * Read last sync timestamp from state directory.
 *
 * Looks for ~/Library/Application Support/Augur/state/sync-state.json
 * or the install-source.json as a fallback for install timestamp.
 */
function readLastSync(): string | null {
  const stateDir = join(
    homedir(),
    "Library",
    "Application Support",
    "Augur",
    "state"
  );

  // Try sync-state.json first (written by sync engine)
  const syncStatePath = join(stateDir, "sync-state.json");
  if (existsSync(syncStatePath)) {
    try {
      const data = JSON.parse(readFileSync(syncStatePath, "utf-8"));
      if (data.last_sync) return data.last_sync;
    } catch {
      // Corrupted file, fall through
    }
  }

  // Fallback: install-source.json (written by installer)
  const installSourcePath = join(stateDir, "install-source.json");
  if (existsSync(installSourcePath)) {
    try {
      const data = JSON.parse(readFileSync(installSourcePath, "utf-8"));
      if (data.installed_at) return data.installed_at;
    } catch {
      // Corrupted file
    }
  }

  return null;
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd ~/Projects/Augur/dist/platform-plugins/lib && npx vitest run`
Expected: All 6 tests PASS

- [ ] **Step 6: Commit**

```bash
git add dist/platform-plugins/lib/
git commit -m "feat: add shared health check library for platform plugins (ADR-437)"
```

---

## Task 3: Obsidian Community Plugin

**Files:**
- Create: `dist/platform-plugins/obsidian/manifest.json`
- Create: `dist/platform-plugins/obsidian/src/main.ts`
- Create: `dist/platform-plugins/obsidian/styles.css`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p dist/platform-plugins/obsidian/src
```

- [ ] **Step 2: Create manifest.json**

```json
// dist/platform-plugins/obsidian/manifest.json
{
  "id": "augur",
  "name": "Augur",
  "version": "0.1.0",
  "minAppVersion": "1.5.0",
  "description": "Connect to your Augur second brain — install, configure, and monitor your personal knowledge system.",
  "author": "Gur Sannikov",
  "authorUrl": "https://github.com/gsannikov/augur",
  "isDesktopOnly": true,
  "fundingUrl": ""
}
```

- [ ] **Step 3: Create styles.css**

```css
/* dist/platform-plugins/obsidian/styles.css */

/* Status panel container */
.augur-status-panel {
  padding: 16px;
}

.augur-status-panel h3 {
  margin: 0 0 12px 0;
  font-size: 1.1em;
}

/* Status indicator row */
.augur-status-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  font-size: 0.9em;
}

.augur-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.augur-status-dot--healthy {
  background-color: var(--color-green);
}

.augur-status-dot--unhealthy {
  background-color: var(--color-red);
}

.augur-status-dot--unknown {
  background-color: var(--text-muted);
}

/* Not-installed state */
.augur-not-installed {
  text-align: center;
  padding: 24px 16px;
}

.augur-not-installed p {
  color: var(--text-muted);
  margin-bottom: 16px;
}

/* Action buttons */
.augur-action-btn {
  margin: 4px 0;
  width: 100%;
}

/* Last sync timestamp */
.augur-last-sync {
  color: var(--text-muted);
  font-size: 0.85em;
  margin-top: 8px;
}
```

- [ ] **Step 4: Implement main.ts with 5 capabilities**

```typescript
// dist/platform-plugins/obsidian/src/main.ts
/**
 * Augur distribution plugin for Obsidian.
 *
 * 5 capabilities (ADR-437 contract):
 *   1. Detect  — check if Augur is installed
 *   2. Install — call install.sh --from obsidian
 *   3. Configure — run configure_mcp.py --apply --auto
 *   4. Status  — show connection health panel
 *   5. Link    — open dashboard in browser
 */

import {
  App,
  Plugin,
  PluginSettingTab,
  Setting,
  Notice,
  ItemView,
  WorkspaceLeaf,
} from "obsidian";

import { existsSync, readFileSync } from "fs";
import { join } from "path";
import { homedir } from "os";
import { execFile } from "child_process";

// ─── Health Check (inlined from shared lib to avoid build complexity) ────────

interface HealthStatus {
  installed: boolean;
  mcp_healthy: boolean;
  dashboard_running: boolean;
  last_sync: string | null;
  install_dir: string;
}

async function checkHealth(): Promise<HealthStatus> {
  const installDir = process.env.AUGUR_DIR ?? join(homedir(), "Projects", "augur");
  const installed = existsSync(installDir);

  let mcp_healthy = false;
  let dashboard_running = false;

  try {
    const mcpResp = await fetch("http://localhost:3001/health", {
      signal: AbortSignal.timeout(3000),
    });
    mcp_healthy = mcpResp.ok;
  } catch {
    // unreachable
  }

  try {
    const dashResp = await fetch("http://localhost:3000", {
      signal: AbortSignal.timeout(3000),
    });
    dashboard_running = dashResp.ok;
  } catch {
    // unreachable
  }

  let last_sync: string | null = null;
  const stateDir = join(homedir(), "Library", "Application Support", "Augur", "state");
  for (const file of ["sync-state.json", "install-source.json"]) {
    const p = join(stateDir, file);
    if (existsSync(p)) {
      try {
        const data = JSON.parse(readFileSync(p, "utf-8"));
        last_sync = data.last_sync ?? data.installed_at ?? null;
        if (last_sync) break;
      } catch {
        // skip
      }
    }
  }

  return { installed, mcp_healthy, dashboard_running, last_sync, install_dir: installDir };
}

// ─── Status View ─────────────────────────────────────────────────────────────

const AUGUR_VIEW_TYPE = "augur-status";

class AugurStatusView extends ItemView {
  private health: HealthStatus | null = null;
  private refreshInterval: ReturnType<typeof setInterval> | null = null;

  getViewType(): string {
    return AUGUR_VIEW_TYPE;
  }

  getDisplayText(): string {
    return "Augur";
  }

  getIcon(): string {
    return "activity";
  }

  async onOpen(): Promise<void> {
    await this.refresh();
    // Auto-refresh every 30 seconds
    this.refreshInterval = setInterval(() => this.refresh(), 30_000);
  }

  async onClose(): Promise<void> {
    if (this.refreshInterval) {
      clearInterval(this.refreshInterval);
      this.refreshInterval = null;
    }
  }

  async refresh(): Promise<void> {
    this.health = await checkHealth();
    this.render();
  }

  private render(): void {
    const container = this.containerEl.children[1];
    container.empty();

    if (!this.health) {
      container.createEl("p", { text: "Checking Augur status..." });
      return;
    }

    if (!this.health.installed) {
      this.renderNotInstalled(container);
    } else {
      this.renderStatus(container);
    }
  }

  private renderNotInstalled(container: Element): void {
    const div = container.createDiv({ cls: "augur-not-installed" });
    div.createEl("h3", { text: "Augur" });
    div.createEl("p", { text: "Augur is not installed on this machine." });

    const btn = div.createEl("button", {
      text: "Install Augur",
      cls: "mod-cta augur-action-btn",
    });
    btn.addEventListener("click", () => this.installAugur());
  }

  private renderStatus(container: Element): void {
    const panel = container.createDiv({ cls: "augur-status-panel" });
    panel.createEl("h3", { text: "Augur" });

    // Status rows
    this.addStatusRow(panel, "Installation", this.health!.installed);
    this.addStatusRow(panel, "MCP Server", this.health!.mcp_healthy);
    this.addStatusRow(panel, "Dashboard", this.health!.dashboard_running);

    // Last sync
    if (this.health!.last_sync) {
      const syncDiv = panel.createDiv({ cls: "augur-last-sync" });
      const date = new Date(this.health!.last_sync);
      syncDiv.setText(`Last sync: ${date.toLocaleString()}`);
    }

    // Action buttons
    const actions = panel.createDiv({ cls: "augur-actions" });
    actions.style.marginTop = "12px";

    // Open Dashboard button
    if (this.health!.dashboard_running) {
      const dashBtn = actions.createEl("button", {
        text: "Open Dashboard",
        cls: "augur-action-btn",
      });
      dashBtn.addEventListener("click", () => {
        window.open("http://localhost:3000");
      });
    }

    // Refresh button
    const refreshBtn = actions.createEl("button", {
      text: "Refresh Status",
      cls: "augur-action-btn",
    });
    refreshBtn.style.marginTop = "4px";
    refreshBtn.addEventListener("click", () => this.refresh());
  }

  private addStatusRow(parent: Element, label: string, healthy: boolean): void {
    const row = parent.createDiv({ cls: "augur-status-row" });
    row.createSpan({
      cls: `augur-status-dot augur-status-dot--${healthy ? "healthy" : "unhealthy"}`,
    });
    row.createSpan({ text: `${label}: ${healthy ? "Connected" : "Disconnected"}` });
  }

  /** Capability 2: Install — opens Terminal.app with install command */
  private installAugur(): void {
    const installUrl =
      "https://raw.githubusercontent.com/gsannikov/augur/main/scripts/install.sh";
    new Notice("Opening terminal to install Augur...");
    // Use execFile (not exec) to avoid shell injection — static args only
    execFile("osascript", [
      "-e",
      `tell app "Terminal" to do script "curl -fsSL ${installUrl} | bash -s -- --from obsidian"`,
    ], (err) => {
      if (err) {
        new Notice(
          "Failed to open terminal. Run manually:\n" +
          `curl -fsSL ${installUrl} | bash -s -- --from obsidian`
        );
      }
    });
  }
}

// ─── Plugin ──────────────────────────────────────────────────────────────────

export default class AugurPlugin extends Plugin {
  async onload(): Promise<void> {
    // Register the status view
    this.registerView(AUGUR_VIEW_TYPE, (leaf) => new AugurStatusView(leaf));

    // Add ribbon icon to open status panel
    this.addRibbonIcon("activity", "Augur Status", () => {
      this.activateView();
    });

    // Add command: open status panel
    this.addCommand({
      id: "open-augur-status",
      name: "Open Augur status panel",
      callback: () => this.activateView(),
    });

    // Add command: open dashboard (Capability 5: Link)
    this.addCommand({
      id: "open-augur-dashboard",
      name: "Open Augur dashboard",
      callback: () => window.open("http://localhost:3000"),
    });

    // Add command: refresh status
    this.addCommand({
      id: "refresh-augur-status",
      name: "Refresh Augur status",
      callback: async () => {
        const leaves = this.app.workspace.getLeavesOfType(AUGUR_VIEW_TYPE);
        for (const leaf of leaves) {
          const view = leaf.view as AugurStatusView;
          await view.refresh();
        }
        new Notice("Augur status refreshed");
      },
    });

    // Auto-open status view on first load
    if (this.app.workspace.layoutReady) {
      this.activateView();
    } else {
      this.app.workspace.onLayoutReady(() => this.activateView());
    }
  }

  async onunload(): Promise<void> {
    // Cleanup views
    this.app.workspace.detachLeavesOfType(AUGUR_VIEW_TYPE);
  }

  private async activateView(): Promise<void> {
    const { workspace } = this.app;

    let leaf = workspace.getLeavesOfType(AUGUR_VIEW_TYPE)[0];
    if (!leaf) {
      const rightLeaf = workspace.getRightLeaf(false);
      if (rightLeaf) {
        leaf = rightLeaf;
        await leaf.setViewState({ type: AUGUR_VIEW_TYPE, active: true });
      }
    }
    if (leaf) {
      workspace.revealLeaf(leaf);
    }
  }
}
```

- [ ] **Step 5: Verify files are syntactically valid**

Run: `cd "$(git rev-parse --show-toplevel)" && npx tsc --noEmit --strict --target ES2022 --module ES2022 --moduleResolution bundler dist/platform-plugins/obsidian/src/main.ts --skipLibCheck 2>&1 | head -20`

Note: Full type checking requires Obsidian's type stubs (`obsidian` npm package). This is a syntax/structure check. Full build setup is out of scope for phase 1 -- Obsidian plugin compilation follows their community plugin template.

- [ ] **Step 6: Commit**

```bash
git add dist/platform-plugins/obsidian/
git commit -m "feat: add Obsidian community plugin scaffold (ADR-437)"
```

---

## Task 4: VS Code Extension

**Files:**
- Create: `dist/platform-plugins/vscode/package.json`
- Create: `dist/platform-plugins/vscode/tsconfig.json`
- Create: `dist/platform-plugins/vscode/src/extension.ts`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p dist/platform-plugins/vscode/src
```

- [ ] **Step 2: Create package.json (VS Code extension manifest)**

```json
// dist/platform-plugins/vscode/package.json
{
  "name": "augur",
  "displayName": "Augur",
  "description": "Connect to your Augur second brain — install, configure, and monitor your personal knowledge system.",
  "version": "0.1.0",
  "publisher": "gsannikov",
  "engines": {
    "vscode": "^1.85.0"
  },
  "categories": [
    "Other"
  ],
  "activationEvents": [
    "onStartupFinished"
  ],
  "main": "./dist/extension.js",
  "contributes": {
    "viewsContainers": {
      "activitybar": [
        {
          "id": "augur",
          "title": "Augur",
          "icon": "$(pulse)"
        }
      ]
    },
    "views": {
      "augur": [
        {
          "type": "webview",
          "id": "augur.statusPanel",
          "name": "Status"
        }
      ]
    },
    "commands": [
      {
        "command": "augur.openDashboard",
        "title": "Augur: Open Dashboard"
      },
      {
        "command": "augur.refreshStatus",
        "title": "Augur: Refresh Status"
      },
      {
        "command": "augur.installAugur",
        "title": "Augur: Install Augur"
      }
    ]
  },
  "scripts": {
    "vscode:prepublish": "npm run compile",
    "compile": "tsc -p ./",
    "watch": "tsc -watch -p ./"
  },
  "devDependencies": {
    "@types/vscode": "^1.85.0",
    "typescript": "^5.7.0"
  }
}
```

- [ ] **Step 3: Create tsconfig.json**

```json
// dist/platform-plugins/vscode/tsconfig.json
{
  "compilerOptions": {
    "module": "commonjs",
    "target": "ES2022",
    "lib": ["ES2022"],
    "outDir": "dist",
    "rootDir": "src",
    "strict": true,
    "esModuleInterop": true,
    "sourceMap": true,
    "declaration": true,
    "skipLibCheck": true
  },
  "include": ["src/**/*.ts"],
  "exclude": ["node_modules", "dist"]
}
```

- [ ] **Step 4: Implement extension.ts with sidebar webview**

```typescript
// dist/platform-plugins/vscode/src/extension.ts
/**
 * Augur distribution extension for VS Code.
 *
 * 5 capabilities (ADR-437 contract):
 *   1. Detect  — check if Augur is installed
 *   2. Install — call install.sh --from vscode in integrated terminal
 *   3. Configure — run configure_mcp.py --apply --auto
 *   4. Status  — sidebar webview showing connection health
 *   5. Link    — open dashboard in browser
 */

import * as vscode from "vscode";
import { existsSync, readFileSync } from "fs";
import { join } from "path";
import { homedir } from "os";

// ─── Health Check (inlined from shared lib) ──────────────────────────────────

interface HealthStatus {
  installed: boolean;
  mcp_healthy: boolean;
  dashboard_running: boolean;
  last_sync: string | null;
  install_dir: string;
}

async function checkHealth(): Promise<HealthStatus> {
  const installDir = process.env.AUGUR_DIR ?? join(homedir(), "Projects", "augur");
  const installed = existsSync(installDir);

  let mcp_healthy = false;
  let dashboard_running = false;

  try {
    const mcpResp = await fetch("http://localhost:3001/health", {
      signal: AbortSignal.timeout(3000),
    });
    mcp_healthy = mcpResp.ok;
  } catch {
    // unreachable
  }

  try {
    const dashResp = await fetch("http://localhost:3000", {
      signal: AbortSignal.timeout(3000),
    });
    dashboard_running = dashResp.ok;
  } catch {
    // unreachable
  }

  let last_sync: string | null = null;
  const stateDir = join(homedir(), "Library", "Application Support", "Augur", "state");
  for (const file of ["sync-state.json", "install-source.json"]) {
    const p = join(stateDir, file);
    if (existsSync(p)) {
      try {
        const data = JSON.parse(readFileSync(p, "utf-8"));
        last_sync = data.last_sync ?? data.installed_at ?? null;
        if (last_sync) break;
      } catch {
        // skip
      }
    }
  }

  return { installed, mcp_healthy, dashboard_running, last_sync, install_dir: installDir };
}

// ─── Webview Provider ────────────────────────────────────────────────────────

class AugurStatusProvider implements vscode.WebviewViewProvider {
  public static readonly viewType = "augur.statusPanel";
  private _view?: vscode.WebviewView;

  constructor(private readonly _extensionUri: vscode.Uri) {}

  resolveWebviewView(
    webviewView: vscode.WebviewView,
    _context: vscode.WebviewViewResolveContext,
    _token: vscode.CancellationToken
  ): void {
    this._view = webviewView;

    webviewView.webview.options = {
      enableScripts: true,
    };

    // Handle messages from webview
    webviewView.webview.onDidReceiveMessage(async (message) => {
      switch (message.command) {
        case "install":
          installAugur("vscode");
          break;
        case "openDashboard":
          vscode.env.openExternal(vscode.Uri.parse("http://localhost:3000"));
          break;
        case "refresh":
          await this.refresh();
          break;
      }
    });

    this.refresh();
  }

  async refresh(): Promise<void> {
    if (!this._view) return;
    const health = await checkHealth();
    this._view.webview.html = getWebviewHtml(health);
  }
}

// ─── Install Command ─────────────────────────────────────────────────────────

function installAugur(platform: string): void {
  const terminal = vscode.window.createTerminal("Augur Install");
  terminal.show();
  terminal.sendText(
    `curl -fsSL https://raw.githubusercontent.com/gsannikov/augur/main/scripts/install.sh | bash -s -- --from ${platform}`
  );
}

// ─── Webview HTML ────────────────────────────────────────────────────────────

function getWebviewHtml(health: HealthStatus): string {
  const dot = (ok: boolean) =>
    `<span class="dot ${ok ? "healthy" : "unhealthy"}"></span>`;
  const label = (ok: boolean) => (ok ? "Connected" : "Disconnected");

  if (!health.installed) {
    return `<!DOCTYPE html>
<html>
<head><style>${CSS}</style></head>
<body>
  <div class="panel not-installed">
    <h3>Augur</h3>
    <p>Augur is not installed on this machine.</p>
    <button class="btn primary" onclick="post('install')">Install Augur</button>
  </div>
  <script>
    const vscode = acquireVsCodeApi();
    function post(cmd) { vscode.postMessage({ command: cmd }); }
  </script>
</body>
</html>`;
  }

  const syncText = health.last_sync
    ? `Last sync: ${new Date(health.last_sync).toLocaleString()}`
    : "No sync recorded";

  return `<!DOCTYPE html>
<html>
<head><style>${CSS}</style></head>
<body>
  <div class="panel">
    <h3>Augur</h3>
    <div class="row">${dot(health.installed)} Installation: ${label(health.installed)}</div>
    <div class="row">${dot(health.mcp_healthy)} MCP Server: ${label(health.mcp_healthy)}</div>
    <div class="row">${dot(health.dashboard_running)} Dashboard: ${label(health.dashboard_running)}</div>
    <div class="sync">${syncText}</div>
    <div class="actions">
      ${health.dashboard_running ? '<button class="btn" onclick="post(\'openDashboard\')">Open Dashboard</button>' : ""}
      <button class="btn" onclick="post('refresh')">Refresh Status</button>
    </div>
  </div>
  <script>
    const vscode = acquireVsCodeApi();
    function post(cmd) { vscode.postMessage({ command: cmd }); }
  </script>
</body>
</html>`;
}

const CSS = `
  body { font-family: var(--vscode-font-family); padding: 12px; margin: 0; color: var(--vscode-foreground); }
  h3 { margin: 0 0 12px 0; }
  .panel { padding: 8px 0; }
  .not-installed { text-align: center; padding: 24px 0; }
  .not-installed p { color: var(--vscode-descriptionForeground); margin-bottom: 16px; }
  .row { display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 13px; }
  .dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; flex-shrink: 0; }
  .dot.healthy { background-color: var(--vscode-testing-iconPassed); }
  .dot.unhealthy { background-color: var(--vscode-testing-iconFailed); }
  .sync { color: var(--vscode-descriptionForeground); font-size: 12px; margin-top: 8px; }
  .actions { margin-top: 12px; }
  .btn { display: block; width: 100%; padding: 6px 12px; margin: 4px 0; border: 1px solid var(--vscode-button-border, transparent);
         background: var(--vscode-button-secondaryBackground); color: var(--vscode-button-secondaryForeground);
         cursor: pointer; font-size: 13px; border-radius: 2px; }
  .btn:hover { background: var(--vscode-button-secondaryHoverBackground); }
  .btn.primary { background: var(--vscode-button-background); color: var(--vscode-button-foreground); }
  .btn.primary:hover { background: var(--vscode-button-hoverBackground); }
`;

// ─── Extension Activation ────────────────────────────────────────────────────

export function activate(context: vscode.ExtensionContext): void {
  // Register webview provider for sidebar
  const provider = new AugurStatusProvider(context.extensionUri);
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider(
      AugurStatusProvider.viewType,
      provider
    )
  );

  // Command: Open Dashboard (Capability 5: Link)
  context.subscriptions.push(
    vscode.commands.registerCommand("augur.openDashboard", () => {
      vscode.env.openExternal(vscode.Uri.parse("http://localhost:3000"));
    })
  );

  // Command: Refresh Status (Capability 4: Status)
  context.subscriptions.push(
    vscode.commands.registerCommand("augur.refreshStatus", () => {
      provider.refresh();
    })
  );

  // Command: Install Augur (Capability 2: Install)
  context.subscriptions.push(
    vscode.commands.registerCommand("augur.installAugur", () => {
      installAugur("vscode");
    })
  );

  // Status bar item showing connection health
  const statusBarItem = vscode.window.createStatusBarItem(
    vscode.StatusBarAlignment.Right,
    100
  );
  statusBarItem.command = "augur.refreshStatus";
  context.subscriptions.push(statusBarItem);

  // Initial status check
  checkHealth().then((health) => {
    if (!health.installed) {
      statusBarItem.text = "$(pulse) Augur: Not Installed";
      statusBarItem.tooltip = "Click to check status";
    } else if (health.mcp_healthy) {
      statusBarItem.text = "$(pulse) Augur: Connected";
      statusBarItem.tooltip = "MCP server connected";
    } else {
      statusBarItem.text = "$(pulse) Augur: Disconnected";
      statusBarItem.tooltip = "MCP server not reachable";
    }
    statusBarItem.show();
  });

  // Refresh every 60 seconds
  const interval = setInterval(async () => {
    const health = await checkHealth();
    if (!health.installed) {
      statusBarItem.text = "$(pulse) Augur: Not Installed";
    } else if (health.mcp_healthy) {
      statusBarItem.text = "$(pulse) Augur: Connected";
    } else {
      statusBarItem.text = "$(pulse) Augur: Disconnected";
    }
  }, 60_000);

  context.subscriptions.push({ dispose: () => clearInterval(interval) });
}

export function deactivate(): void {
  // cleanup handled by disposables
}
```

- [ ] **Step 5: Verify file structure**

Run: `find dist/platform-plugins/vscode -type f | sort`
Expected:
```
dist/platform-plugins/vscode/package.json
dist/platform-plugins/vscode/src/extension.ts
dist/platform-plugins/vscode/tsconfig.json
```

- [ ] **Step 6: Commit**

```bash
git add dist/platform-plugins/vscode/
git commit -m "feat: add VS Code extension scaffold with sidebar webview (ADR-437)"
```

---

## Task 5: Platform Plugin Development README

**Files:**
- Create: `dist/platform-plugins/README.md`

- [ ] **Step 1: Write development guide**

````markdown
<!-- dist/platform-plugins/README.md -->
# Platform Plugin Development

Distribution plugins for Augur that live in tool-specific marketplaces.
Each plugin implements the ADR-437 five-capability contract.

## Directory Structure

```
dist/platform-plugins/
├── lib/                    # Shared health check library (TypeScript)
│   ├── health.ts           # checkHealth() — detect, ping MCP, ping dashboard, read sync
│   ├── health.test.ts      # Unit tests (vitest)
│   └── package.json
├── obsidian/               # Obsidian community plugin
│   ├── manifest.json       # Obsidian plugin manifest
│   ├── src/main.ts         # Plugin source (detect, install, configure, status, link)
│   └── styles.css          # Status panel CSS
├── vscode/                 # VS Code extension
│   ├── package.json        # Extension manifest (also VS Code contribution points)
│   ├── src/extension.ts    # Extension source (sidebar webview)
│   └── tsconfig.json
└── README.md               # This file
```

## Five-Capability Contract

Every platform plugin MUST implement exactly these 5 capabilities:

| # | Capability | Description |
|---|-----------|-------------|
| 1 | **Detect** | Check if Augur is installed (`~/Projects/augur` or `$AUGUR_DIR`) |
| 2 | **Install** | Run `scripts/install.sh --from <platform>` if not installed |
| 3 | **Configure** | Run `scripts/configure_mcp.py --apply --auto` to wire MCP |
| 4 | **Status** | Show connection health (MCP running, last sync, dashboard URL) |
| 5 | **Link** | Open dashboard at `localhost:3000` |

## Health Check Protocol

All plugins use the same health check (see `lib/health.ts`):

1. Check install dir exists (`~/Projects/augur` or `$AUGUR_DIR`)
2. Ping MCP server at `localhost:3001/health`
3. Ping dashboard at `localhost:3000`
4. Read last sync from `~/Library/Application Support/Augur/state/`

Returns: `{ installed, mcp_healthy, dashboard_running, last_sync }`

## Adding a New Platform Plugin

1. Create `dist/platform-plugins/<platform>/` with the platform's required manifest format
2. Implement the 5 capabilities using the platform's native APIs
3. Use `lib/health.ts` for the health check (inline it if the platform has no module import support)
4. Call `install.sh --from <platform>` for the install capability
5. The `--from` flag records the install source in `~/Library/Application Support/Augur/state/install-source.json`

## Install Source Tracking

When `install.sh` runs with `--from <platform>`, it writes:

```json
{
  "platform": "<platform>",
  "installed_at": "2026-03-18T12:00:00Z",
  "install_dir": "~/Projects/augur",
  "installer_version": "$(git -C \"$INSTALL_DIR\" describe --tags 2>/dev/null || echo dev)"
}
```

to `~/Library/Application Support/Augur/state/install-source.json`.

## Building

### Shared lib
```bash
cd dist/platform-plugins/lib
npm install
npm test          # run vitest
```

### Obsidian plugin
Obsidian plugins compile TypeScript to a single `main.js` using esbuild.
Follow the [Obsidian plugin template](https://github.com/obsidianmd/obsidian-sample-plugin).

### VS Code extension
```bash
cd dist/platform-plugins/vscode
npm install
npm run compile   # tsc
```

Package with `vsce package` for marketplace submission.
````

- [ ] **Step 2: Commit**

```bash
git add dist/platform-plugins/README.md
git commit -m "docs: add platform plugin development guide (ADR-437)"
```

---

## Verification Checklist

After all tasks complete:

- [ ] `bash scripts/install.sh --from test 2>&1 | head -3` -- starts without arg parsing errors
- [ ] `bash scripts/install.sh --badarg 2>&1` -- shows "Unknown argument" error
- [ ] `cd dist/platform-plugins/lib && npm install && npx vitest run` -- all 6 health check tests PASS
- [ ] `cat dist/platform-plugins/obsidian/manifest.json | python3 -m json.tool` -- valid JSON, id=augur
- [ ] `cat dist/platform-plugins/vscode/package.json | python3 -m json.tool` -- valid JSON, has contributes.views
- [ ] `ls dist/platform-plugins/` -- shows lib/, obsidian/, vscode/, README.md
- [ ] `cat ~/Library/Application\ Support/Augur/state/install-source.json` -- contains platform field (after test install)
- [ ] Obsidian `main.ts` exports default class extending Plugin
- [ ] VS Code `extension.ts` exports activate/deactivate functions
- [ ] Both plugins implement all 5 capabilities (detect, install, configure, status, link)
