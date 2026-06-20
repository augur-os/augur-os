import { App, Plugin, PluginSettingTab, Setting, Notice } from "obsidian";
import * as child_process from "child_process";
import * as path from "path";
import * as fs from "fs";
import * as os from "os";

interface AugurSettings {
  installDir: string;
  dashboardPort: number;
}

const DEFAULT_SETTINGS: AugurSettings = {
  installDir: path.join(os.homedir(), "Projects", "Augur"),
  dashboardPort: 3000,
};

export default class AugurPlugin extends Plugin {
  settings: AugurSettings = DEFAULT_SETTINGS;

  async onload() {
    await this.loadSettings();
    this.addSettingTab(new AugurSettingTab(this.app, this));

    // Status bar item
    const statusBarEl = this.addStatusBarItem();
    this.updateStatusBar(statusBarEl);

    // Ribbon icon to open dashboard
    this.addRibbonIcon("brain", "Open Augur Dashboard", () => {
      window.open(`http://localhost:${this.settings.dashboardPort}`);
    });

    // Commands
    this.addCommand({
      id: "augur-status",
      name: "Check Augur Status",
      callback: () => this.showStatus(),
    });

    this.addCommand({
      id: "augur-install",
      name: "Install Augur",
      callback: () => this.installAugur(),
    });

    this.addCommand({
      id: "augur-open-dashboard",
      name: "Open Dashboard",
      callback: () => {
        window.open(`http://localhost:${this.settings.dashboardPort}`);
      },
    });

    this.addCommand({
      id: "augur-sync",
      name: "Sync Now",
      callback: () => this.syncNow(),
    });
  }

  // === Capability 1: Detect ===
  detect(): { installed: boolean; path: string } {
    const dir = process.env.AUGUR_DIR || this.settings.installDir;
    const exists = fs.existsSync(dir) && fs.existsSync(path.join(dir, ".git"));
    return { installed: exists, path: dir };
  }

  // === Capability 2: Install ===
  async installAugur(): Promise<void> {
    const detection = this.detect();
    if (detection.installed) {
      new Notice("Augur is already installed at " + detection.path);
      return;
    }

    new Notice("Installing Augur... This may take a few minutes.");

    try {
      const installScript = "curl -fsSL https://raw.githubusercontent.com/augur-os/augur-os/main/scripts/install.sh | bash -s -- --from obsidian";
      child_process.exec(installScript, { timeout: 600000 }, (error, stdout, stderr) => {
        if (error) {
          new Notice("Augur installation failed. Check console for details.");
          console.error("Augur install error:", error);
          console.error("stderr:", stderr);
        } else {
          new Notice("Augur installed successfully!");
          console.log("Augur install output:", stdout);
        }
      });
    } catch (e) {
      new Notice("Failed to start installation: " + String(e));
    }
  }

  // === Capability 3: Configure ===
  async configure(): Promise<void> {
    const detection = this.detect();
    if (!detection.installed) {
      new Notice("Augur is not installed. Run 'Install Augur' first.");
      return;
    }

    try {
      const configScript = path.join(detection.path, "scripts", "configure_mcp.py");
      if (fs.existsSync(configScript)) {
        child_process.exec(
          `cd "${detection.path}" && uv run python "${configScript}" --client obsidian`,
          (error) => {
            if (error) {
              new Notice("MCP configuration failed. Check console.");
              console.error("Configure error:", error);
            } else {
              new Notice("MCP configured for Obsidian.");
            }
          }
        );
      }
    } catch (e) {
      new Notice("Configuration failed: " + String(e));
    }
  }

  // === Capability 4: Status ===
  async showStatus(): Promise<void> {
    const detection = this.detect();
    const health = await this.checkHealth();

    const statusLines = [
      `Installed: ${detection.installed ? "Yes" : "No"}`,
      `Path: ${detection.path}`,
      `MCP: ${health.mcp_healthy ? "Connected" : "Disconnected"}`,
      `Dashboard: ${health.dashboard_running ? "Running" : "Stopped"}`,
    ];
    if (health.last_sync) {
      statusLines.push(`Last sync: ${health.last_sync}`);
    }

    new Notice(statusLines.join("\n"), 10000);
  }

  // === Capability 5: Link ===
  getDashboardUrl(): string {
    return `http://localhost:${this.settings.dashboardPort}`;
  }

  // === Health Check ===
  async checkHealth(): Promise<{
    installed: boolean;
    mcp_healthy: boolean;
    dashboard_running: boolean;
    last_sync: string | null;
  }> {
    const detection = this.detect();

    let mcp_healthy = false;
    let dashboard_running = false;
    let last_sync: string | null = null;

    if (detection.installed) {
      // Check MCP
      try {
        const resp = await fetch("http://localhost:3001/health", {
          signal: AbortSignal.timeout(3000),
        });
        mcp_healthy = resp.ok;
      } catch {
        mcp_healthy = false;
      }

      // Check dashboard
      try {
        const resp = await fetch(`http://localhost:${this.settings.dashboardPort}`, {
          signal: AbortSignal.timeout(3000),
        });
        dashboard_running = resp.ok;
      } catch {
        dashboard_running = false;
      }

      // Read last sync
      const stateFile = path.join(
        os.homedir(),
        "Library",
        "Application Support",
        "Augur",
        "state",
        "install-source.json"
      );
      if (fs.existsSync(stateFile)) {
        try {
          const data = JSON.parse(fs.readFileSync(stateFile, "utf-8"));
          last_sync = data.installed_at || null;
        } catch {
          // ignore
        }
      }
    }

    return {
      installed: detection.installed,
      mcp_healthy,
      dashboard_running,
      last_sync,
    };
  }

  async updateStatusBar(el: HTMLElement): Promise<void> {
    const detection = this.detect();
    if (!detection.installed) {
      el.setText("Augur: Not installed");
      return;
    }

    const health = await this.checkHealth();
    const status = health.mcp_healthy ? "Connected" : "Disconnected";
    el.setText(`Augur: ${status}`);
  }

  async loadSettings() {
    this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
  }

  async saveSettings() {
    await this.saveData(this.settings);
  }

  async syncNow(): Promise<void> {
    const detection = this.detect();
    if (!detection.installed) {
      new Notice("Augur is not installed.");
      return;
    }

    new Notice("Syncing Augur...");
    try {
      // `skills.ai.scripts.sync_agents` resolves from project-brain/capabilities
      // (ADR-770 layout). Pass it via env/cwd options and use execFile (no shell —
      // avoids injection and POSIX-only `VAR=val cmd` syntax, rule 30).
      const sep = process.platform === "win32" ? ";" : ":";
      const pythonPath = [
        path.join(detection.path, "project-brain", "capabilities"),
        detection.path,
        path.join(detection.path, "src", "mcp"),
        process.env.PYTHONPATH || "",
      ]
        .filter(Boolean)
        .join(sep);
      child_process.execFile(
        "uv",
        ["run", "python", "-m", "skills.ai.scripts.sync_agents", "sync", "all"],
        { cwd: detection.path, env: { ...process.env, PYTHONPATH: pythonPath } },
        (error) => {
          if (error) {
            new Notice("Sync failed. Check console.");
            console.error("Sync error:", error);
          } else {
            new Notice("Augur sync complete.");
          }
        }
      );
    } catch (e) {
      new Notice("Sync failed: " + String(e));
    }
  }
}

class AugurSettingTab extends PluginSettingTab {
  plugin: AugurPlugin;

  constructor(app: App, plugin: AugurPlugin) {
    super(app, plugin);
    this.plugin = plugin;
  }

  display(): void {
    const { containerEl } = this;
    containerEl.empty();

    containerEl.createEl("h2", { text: "Augur Settings" });

    new Setting(containerEl)
      .setName("Install Directory")
      .setDesc("Path to the Augur installation")
      .addText((text) =>
        text
          .setPlaceholder(DEFAULT_SETTINGS.installDir)
          .setValue(this.plugin.settings.installDir)
          .onChange(async (value) => {
            this.plugin.settings.installDir = value;
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName("Dashboard Port")
      .setDesc("Port for the Augur dashboard")
      .addText((text) =>
        text
          .setPlaceholder(String(DEFAULT_SETTINGS.dashboardPort))
          .setValue(String(this.plugin.settings.dashboardPort))
          .onChange(async (value) => {
            this.plugin.settings.dashboardPort = parseInt(value) || 3000;
            await this.plugin.saveSettings();
          })
      );
  }
}
