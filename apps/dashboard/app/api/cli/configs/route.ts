import { NextResponse } from "next/server";
import {
  getCliAgentsConfig,
  resolveCommand,
  resolveDefaultCliId,
  type CliCategory,
} from "../cli-config";
import { callMCPTool, MCPBridge } from "@/lib/mcp/MCPBridge";

/**
 * GET /api/cli/configs
 *
 * Returns the list of available CLI agents from cli_agents.yaml.
 * Merges config + binary availability + user preferences (enabled groups/variants).
 */
export async function GET() {
  try {
    const agents = getCliAgentsConfig();

    // Load user preferences for enabled groups/variants
    let enabledGroups: string[] | null = null;
    let variantOverrides: Record<string, boolean> = {};
    try {
      const prefResult = await callMCPTool("get-preferences", { key: "dispatch_targets" });
      const raw = MCPBridge.extractText(prefResult).trim();
      if (raw) {
        const prefs = JSON.parse(raw);
        const dt = prefs?.dispatch_targets ?? prefs;
        if (dt?.enabled_groups) enabledGroups = dt.enabled_groups;
        if (dt?.variant_overrides) variantOverrides = dt.variant_overrides;
      }
    } catch {
      // Prefs unavailable — treat all as enabled (first-run default)
    }

    const configs = Object.entries(agents).map(([id, config]: [string, any]) => {
      const cmd = config.cmd?.[0];
      let available = false;
      if (cmd) {
        try {
          resolveCommand(cmd);
          available = true;
        } catch {
          available = false;
        }
      }

      const category: CliCategory = config.category || "remote";
      const group: string = config.group || id;

      // Enabled = group is in enabled list (or all enabled if no prefs yet)
      // AND variant is not explicitly disabled
      const groupEnabled = enabledGroups === null || enabledGroups.includes(group);
      const variantEnabled = variantOverrides[id] !== false;
      const enabled = groupEnabled && variantEnabled;

      return {
        cli_id: id,
        label: config.label || id,
        cmd: config.cmd,
        category,
        group,
        available,
        enabled,
      };
    });

    const defaultCli = resolveDefaultCliId(agents);

    return NextResponse.json({
      configs,
      default_cli: defaultCli,
    });
  } catch (err: any) {
    return NextResponse.json(
      { error: err.message || "Failed to load CLI configs" },
      { status: 500 },
    );
  }
}
