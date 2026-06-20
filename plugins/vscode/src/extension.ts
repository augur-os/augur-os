import * as vscode from "vscode";
import * as child_process from "child_process";
import * as path from "path";
import * as fs from "fs";
import * as os from "os";

function getInstallDir(): string {
  return process.env.AUGUR_DIR || path.join(os.homedir(), "Projects", "Augur");
}

function getStateDir(): string {
  if (process.platform === "darwin") {
    return path.join(os.homedir(), "Library", "Application Support", "Augur", "state");
  }
  const xdgState = process.env.XDG_STATE_HOME || path.join(os.homedir(), ".local", "state");
  return path.join(xdgState, "augur");
}

// === Capability 1: Detect ===
function detect(): { installed: boolean; path: string } {
  const dir = getInstallDir();
  const exists = fs.existsSync(dir) && fs.existsSync(path.join(dir, ".git"));
  return { installed: exists, path: dir };
}

// === Health Check ===
async function checkHealth(): Promise<{
  installed: boolean;
  mcp_healthy: boolean;
  dashboard_running: boolean;
  last_sync: string | null;
}> {
  const detection = detect();
  if (!detection.installed) {
    return { installed: false, mcp_healthy: false, dashboard_running: false, last_sync: null };
  }

  let mcp_healthy = false;
  let dashboard_running = false;
  let last_sync: string | null = null;

  try {
    const resp = await fetch("http://localhost:3001/health", {
      signal: AbortSignal.timeout(3000),
    });
    mcp_healthy = resp.ok;
  } catch {
    // not running
  }

  try {
    const resp = await fetch("http://localhost:3000", {
      signal: AbortSignal.timeout(3000),
    });
    dashboard_running = resp.ok;
  } catch {
    // not running
  }

  const stateFile = path.join(getStateDir(), "install-source.json");
  if (fs.existsSync(stateFile)) {
    try {
      const data = JSON.parse(fs.readFileSync(stateFile, "utf-8"));
      last_sync = data.installed_at || null;
    } catch {
      // ignore
    }
  }

  return { installed: true, mcp_healthy, dashboard_running, last_sync };
}

export function activate(context: vscode.ExtensionContext) {
  // Status bar
  const statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
  statusBar.command = "augur.status";
  context.subscriptions.push(statusBar);
  updateStatusBar(statusBar);

  // === Capability 4: Status ===
  context.subscriptions.push(
    vscode.commands.registerCommand("augur.status", async () => {
      const health = await checkHealth();
      const detection = detect();

      const lines = [
        `Installed: ${detection.installed ? "Yes" : "No"}`,
        `Path: ${detection.path}`,
        `MCP: ${health.mcp_healthy ? "Connected" : "Disconnected"}`,
        `Dashboard: ${health.dashboard_running ? "Running" : "Stopped"}`,
      ];
      if (health.last_sync) {
        lines.push(`Last sync: ${health.last_sync}`);
      }

      if (!detection.installed) {
        const action = await vscode.window.showInformationMessage(
          "Augur is not installed.",
          "Install Now"
        );
        if (action === "Install Now") {
          vscode.commands.executeCommand("augur.install");
        }
      } else {
        vscode.window.showInformationMessage(lines.join(" | "));
      }
    })
  );

  // === Capability 2: Install ===
  context.subscriptions.push(
    vscode.commands.registerCommand("augur.install", async () => {
      const detection = detect();
      if (detection.installed) {
        vscode.window.showInformationMessage("Augur is already installed at " + detection.path);
        return;
      }

      const terminal = vscode.window.createTerminal("Augur Install");
      terminal.show();
      terminal.sendText(
        'curl -fsSL https://raw.githubusercontent.com/augur-os/augur-os/main/scripts/install.sh | bash -s -- --from vscode'
      );
    })
  );

  // === Capability 5: Link ===
  context.subscriptions.push(
    vscode.commands.registerCommand("augur.openDashboard", () => {
      vscode.env.openExternal(vscode.Uri.parse("http://localhost:3000"));
    })
  );

  // === Capability 3: Configure ===
  context.subscriptions.push(
    vscode.commands.registerCommand("augur.configure", async () => {
      const detection = detect();
      if (!detection.installed) {
        vscode.window.showErrorMessage("Augur is not installed. Run 'Augur: Install' first.");
        return;
      }

      const configScript = path.join(detection.path, "scripts", "configure_mcp.py");
      if (!fs.existsSync(configScript)) {
        vscode.window.showErrorMessage("Configure script not found at " + configScript);
        return;
      }

      const terminal = vscode.window.createTerminal("Augur Configure");
      terminal.show();
      terminal.sendText(
        `cd "${detection.path}" && uv run python "${configScript}" --client vscode`
      );
      vscode.window.showInformationMessage("MCP configuration started for VS Code.");
    })
  );

  // Sync command
  context.subscriptions.push(
    vscode.commands.registerCommand("augur.sync", async () => {
      const detection = detect();
      if (!detection.installed) {
        vscode.window.showErrorMessage("Augur is not installed.");
        return;
      }

      // `skills.ai.scripts.sync_agents` resolves from project-brain/capabilities
      // (ADR-770 layout). Set it via the terminal API (cross-OS safe, rule 30)
      // instead of inlining POSIX-only `VAR=val cmd` syntax.
      const sep = process.platform === "win32" ? ";" : ":";
      const pythonPath = [
        path.join(detection.path, "project-brain", "capabilities"),
        detection.path,
        path.join(detection.path, "src", "mcp"),
        process.env.PYTHONPATH || "",
      ]
        .filter(Boolean)
        .join(sep);
      const terminal = vscode.window.createTerminal({
        name: "Augur Sync",
        cwd: detection.path,
        env: { PYTHONPATH: pythonPath },
      });
      terminal.show();
      terminal.sendText("uv run python -m skills.ai.scripts.sync_agents sync all");
    })
  );

  // Auto-check on activation
  checkHealth().then((health) => {
    if (!health.installed) {
      vscode.window
        .showInformationMessage(
          "Augur is not installed. Would you like to install it?",
          "Install",
          "Later"
        )
        .then((choice) => {
          if (choice === "Install") {
            vscode.commands.executeCommand("augur.install");
          }
        });
    }
  });
}

async function updateStatusBar(statusBar: vscode.StatusBarItem) {
  const detection = detect();
  if (!detection.installed) {
    statusBar.text = "$(warning) Augur: Not installed";
    statusBar.tooltip = "Click to check status";
    statusBar.show();
    return;
  }

  const health = await checkHealth();
  if (health.mcp_healthy) {
    statusBar.text = "$(check) Augur: Connected";
    statusBar.tooltip = "Augur MCP is running";
  } else {
    statusBar.text = "$(circle-slash) Augur: Disconnected";
    statusBar.tooltip = "Augur MCP is not running";
  }
  statusBar.show();
}

export function deactivate() {}
